"""Flow-APO: action-chunk 上のアンカー付き選好最適化（研究サイドカー）。

SmolVLA の Flow-Matching を token log-prob の代わりに、条件付き速度場誤差
（擬似 energy）として用いる。π_ref（SFT）を凍結アンカーにする。

robot venv に SmolVLA が無い場合でも、小さな energy MLP で smoke 可能。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from parc.data.clair_nearmiss import PAIRS_JSONL_NAME, _resolve
from parc.train.aflora import AFLoRACallback, AFLoRAConfig, build_loraplus_param_groups


def load_pair_rows(pairs_root: Path) -> list[dict[str, Any]]:
    """meta/pairs.jsonl を読む。"""
    path = pairs_root / "meta" / PAIRS_JSONL_NAME
    if not path.is_file():
        raise FileNotFoundError(f"missing pairs jsonl: {path}")
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_episode_actions(split_root: Path, episode_id: int) -> np.ndarray:
    """minimal episode の actions.npy を読む。"""
    path = split_root / "episodes" / f"episode_{int(episode_id):06d}" / "actions.npy"
    if not path.is_file():
        raise FileNotFoundError(path)
    return np.load(path).astype(np.float32)


def sample_action_chunk(
    actions: np.ndarray,
    *,
    chunk_size: int,
    rng: np.random.Generator,
    early_chunk_only: bool = False,
) -> np.ndarray:
    """軌道から固定長 action chunk を切り出す（不足はゼロパッド）。"""
    t = int(actions.shape[0])
    if t <= 0:
        return np.zeros((chunk_size, actions.shape[1] if actions.ndim > 1 else 7), dtype=np.float32)
    if early_chunk_only:
        start = 0
    else:
        start = int(rng.integers(0, max(1, t)))
    chunk = actions[start : start + chunk_size]
    if chunk.shape[0] < chunk_size:
        pad = np.zeros((chunk_size - chunk.shape[0], chunk.shape[1]), dtype=np.float32)
        chunk = np.concatenate([chunk, pad], axis=0)
    return chunk.astype(np.float32)


def apo_loss_from_energies(
    e_w: Any,
    e_l: Any,
    e_ref_w: Any,
    e_ref_l: Any,
    *,
    beta: float,
    anchor_coef: float,
) -> Any:
    """APO 風損失（energy が低いほど良い = preferred）。

    L = -log σ(β[(e_l - e_w) - (e_ref_l - e_ref_w)]) + λ * anchor

    anchor は preferred が ref から離れすぎないよう (e_w - e_ref_w)^2。
    """
    import torch
    import torch.nn.functional as F

    delta = (e_l - e_w) - (e_ref_l - e_ref_w)
    pref = -F.logsigmoid(beta * delta)
    anchor = anchor_coef * (e_w - e_ref_w).pow(2)
    return pref + anchor


class ChunkEnergyMLP:
    """SmolVLA 非依存の smoke 用 energy モデル。"""

    def __init__(self, action_dim: int = 7, chunk_size: int = 16, hidden: int = 64) -> None:
        import torch
        from torch import nn

        self.chunk_size = chunk_size
        self.action_dim = action_dim
        self.net = nn.Sequential(
            nn.Linear(chunk_size * action_dim, hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
            nn.SiLU(),
            nn.Linear(hidden, 1),
        )

    def to(self, device: Any) -> ChunkEnergyMLP:
        self.net.to(device)
        return self

    def named_parameters(self):  # noqa: ANN201
        return self.net.named_parameters()

    def parameters(self):  # noqa: ANN201
        return self.net.parameters()

    def train(self) -> None:
        self.net.train()

    def eval(self) -> None:
        self.net.eval()

    def energy(self, chunk: Any) -> Any:
        """(B, T, A) → (B,) energy。"""
        import torch

        x = chunk.reshape(chunk.shape[0], -1)
        return self.net(x).squeeze(-1)


def _maybe_load_smolvla_energy(train_cfg: dict[str, Any]) -> Any | None:
    """可能なら SmolVLA を載せる（親 venv）。失敗時は None。"""
    path = train_cfg.get("policy_path") or train_cfg.get("init_policy_path")
    if not path:
        return None
    try:
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy  # type: ignore

        policy = SmolVLAPolicy.from_pretrained(str(path))
        policy.eval()
        return policy
    except Exception:
        return None


def run_flow_apo_training(config: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Flow-APO 学習ループ。"""
    import torch

    train_cfg = config.get("train") or {}
    if train_cfg.get("dry_run", False):
        return {"status": "dry_run", "backend": "flow_apo", "hint": "dry_run=true — 未実行"}

    seed = int(config.get("seed", 0))
    torch.manual_seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)

    pairs_root = _resolve(train_cfg.get("pairs_root", "data/datasets/clair_libero_pairs_smoke"))
    rows = load_pair_rows(pairs_root)
    if not rows:
        raise ValueError(f"no pairs in {pairs_root}")

    steps = int(train_cfg.get("steps", train_cfg.get("updates", 50)))
    batch_size = int(train_cfg.get("batch_size", 4))
    chunk_size = int(train_cfg.get("chunk_size", 16))
    lr = float(train_cfg.get("lr", 1e-4))
    beta = float(train_cfg.get("beta", 0.1))
    anchor_coef = float(train_cfg.get("anchor_coef", 0.05))
    lr_ratio_b = float(train_cfg.get("lora_plus_lr_ratio", 4.0))
    early_freeze = bool(train_cfg.get("constrain_early_chunk", True))
    device = torch.device(str(train_cfg.get("device", "cpu")))

    # QST フラグはログのみ（実 4bit は robot venv + bitsandbytes 依存）
    qst = bool(train_cfg.get("qst", False))

    policy = _maybe_load_smolvla_energy(train_cfg)
    use_smolvla = policy is not None
    model = ChunkEnergyMLP(chunk_size=chunk_size).to(device)
    # ref = SFT アンカー
    ref = ChunkEnergyMLP(chunk_size=chunk_size).to(device)
    ref.net.load_state_dict(model.net.state_dict())
    ref.eval()
    for p in ref.parameters():
        p.requires_grad_(False)

    # LoRA+ 風 param groups（energy MLP では全パラメータを other/A 扱い）
    # 名前に lora_ が無いので単一 group になるが API は共通
    groups = build_loraplus_param_groups(model, lr=lr, lr_ratio_b=lr_ratio_b)
    if not groups:
        groups = [{"params": list(model.parameters()), "lr": lr}]
    opt = torch.optim.AdamW(groups)

    aflora_cfg = AFLoRAConfig(
        freeze_after_step=int(train_cfg.get("aflora_freeze_after", max(1, steps // 2))),
        eval_every=int(train_cfg.get("aflora_eval_every", max(1, steps // 5))),
        freeze_frac=float(train_cfg.get("aflora_freeze_frac", 0.3)),
    )
    # energy MLP に擬似 LoRA 名を付けるラッパはせず、コールバックは no-op 気味でも履歴を残す
    aflora = AFLoRACallback(model, aflora_cfg)

    out_dir = run_dir / "train_output" / "pretrained_model"
    out_dir.mkdir(parents=True, exist_ok=True)
    history: list[dict[str, Any]] = []
    squeeze_alerts = 0

    model.train()
    for step in range(steps):
        pref_chunks = []
        rej_chunks = []
        for _ in range(batch_size):
            row = rows[int(rng.integers(0, len(rows)))]
            pref = load_episode_actions(pairs_root / "preferred", int(row["preferred_episode_id"]))
            rej = load_episode_actions(pairs_root / "rejected", int(row["rejected_episode_id"]))
            # 初期チャンク制約: 半分の確率で early-only（更新を接近相に寄せすぎない監視用サンプル）
            early = early_freeze and (rng.random() < 0.3)
            pref_chunks.append(sample_action_chunk(pref, chunk_size=chunk_size, rng=rng, early_chunk_only=early))
            rej_chunks.append(sample_action_chunk(rej, chunk_size=chunk_size, rng=rng, early_chunk_only=early))
        pref_t = torch.tensor(np.stack(pref_chunks), device=device)
        rej_t = torch.tensor(np.stack(rej_chunks), device=device)

        e_w = model.energy(pref_t)
        e_l = model.energy(rej_t)
        with torch.no_grad():
            e_ref_w = ref.energy(pref_t)
            e_ref_l = ref.energy(rej_t)
        loss = apo_loss_from_energies(e_w, e_l, e_ref_w, e_ref_l, beta=beta, anchor_coef=anchor_coef).mean()
        if not torch.isfinite(loss):
            return {
                "status": "failed",
                "backend": "flow_apo",
                "error": "non_finite_loss",
                "step": step,
            }
        opt.zero_grad(set_to_none=True)
        loss.backward()
        # スクイージング監視: preferred energy が ref から極端に離れたら記録
        with torch.no_grad():
            drift = float((e_w - e_ref_w).abs().mean().item())
            if drift > float(train_cfg.get("squeeze_alert_threshold", 5.0)):
                squeeze_alerts += 1
        opt.step()
        aflora_report = aflora.on_step_end()
        if step % max(1, steps // 10) == 0 or step == steps - 1:
            history.append(
                {
                    "step": step,
                    "loss": float(loss.item()),
                    "drift": drift,
                    "aflora": aflora_report,
                }
            )

    ckpt_path = out_dir / "flow_apo_energy.pt"
    torch.save({"model": model.net.state_dict(), "chunk_size": chunk_size}, ckpt_path)
    meta = {
        "status": "finished",
        "backend": "flow_apo",
        "steps": steps,
        "n_pairs": len(rows),
        "pairs_root": str(pairs_root),
        "qst": qst,
        "use_smolvla": use_smolvla,
        "beta": beta,
        "anchor_coef": anchor_coef,
        "lora_plus_lr_ratio": lr_ratio_b,
        "squeeze_alerts": squeeze_alerts,
        "history": history,
        "ckpt": str(ckpt_path),
        "sidecar": True,
        "parent_ckpt_eligible": False,
    }
    (run_dir / "train_output" / "flow_apo_metrics.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return meta
