"""AFLoRA: 学習中盤以降に寄与の低い LoRA モジュールを動的凍結する。

研究サイドカー（CLAIR / Flow-APO）用。PEFT が無い環境でも名前ベースで動作する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AFLoRAConfig:
    """動的凍結のハイパーパラメータ。"""

    # このステップ以降で凍結判定を開始
    freeze_after_step: int = 100
    # 何ステップごとに再評価するか
    eval_every: int = 50
    # 勾配ノルム下位この割合を凍結（0–1）
    freeze_frac: float = 0.3
    # 名前に含まれると LoRA 候補とみなす
    name_substrings: tuple[str, ...] = ("lora_", "lora_A", "lora_B", "lora")
    # 初期軌道チャンク向け: 名前に含まれると常に低優先（早期凍結候補）
    early_chunk_substrings: tuple[str, ...] = ("early_chunk", "timestep_embed")


@dataclass
class AFLoRAState:
    """コールバック状態。"""

    step: int = 0
    grad_ema: dict[str, float] = field(default_factory=dict)
    frozen: set[str] = field(default_factory=set)
    history: list[dict[str, Any]] = field(default_factory=list)


def is_lora_param_name(name: str, cfg: AFLoRAConfig) -> bool:
    """パラメータ名が LoRA 系か。"""
    lower = name.lower()
    return any(s.lower() in lower for s in cfg.name_substrings)


def _ema_update(prev: float, value: float, *, beta: float = 0.9) -> float:
    return beta * prev + (1.0 - beta) * value


class AFLoRACallback:
    """Optimizer step 前後で呼ぶ動的凍結コールバック。"""

    def __init__(self, model: Any, cfg: AFLoRAConfig | None = None) -> None:
        self.model = model
        self.cfg = cfg or AFLoRAConfig()
        self.state = AFLoRAState()

    def on_step_end(self) -> dict[str, Any]:
        """1 step 終了後に勾配 EMA を更新し、必要なら凍結する。"""
        self.state.step += 1
        norms = _collect_grad_norms(self.model, self.cfg)
        for name, norm in norms.items():
            prev = self.state.grad_ema.get(name, norm)
            self.state.grad_ema[name] = _ema_update(prev, norm)
        report: dict[str, Any] = {
            "step": self.state.step,
            "n_tracked": len(self.state.grad_ema),
            "n_frozen": len(self.state.frozen),
            "newly_frozen": [],
        }
        cfg = self.cfg
        if self.state.step < cfg.freeze_after_step:
            return report
        if self.state.step % max(1, cfg.eval_every) != 0:
            return report
        newly = self._freeze_low_contribution()
        report["newly_frozen"] = newly
        report["n_frozen"] = len(self.state.frozen)
        self.state.history.append(report)
        return report

    def _freeze_low_contribution(self) -> list[str]:
        """EMA 勾配が小さい LoRA を凍結。"""
        cfg = self.cfg
        candidates = {
            k: v
            for k, v in self.state.grad_ema.items()
            if k not in self.state.frozen and is_lora_param_name(k, cfg)
        }
        if not candidates:
            return []
        # 初期チャンク関連は凍結候補にボーナス（先に落ちやすくする）
        scored = []
        for name, ema in candidates.items():
            score = ema
            if any(s.lower() in name.lower() for s in cfg.early_chunk_substrings):
                score *= 0.5
            scored.append((score, name))
        scored.sort(key=lambda x: x[0])
        n_freeze = max(1, int(len(scored) * cfg.freeze_frac))
        newly: list[str] = []
        named_params = dict(self.model.named_parameters())
        for _, name in scored[:n_freeze]:
            param = named_params.get(name)
            if param is None:
                continue
            param.requires_grad_(False)
            self.state.frozen.add(name)
            newly.append(name)
        return newly


def _collect_grad_norms(model: Any, cfg: AFLoRAConfig) -> dict[str, float]:
    """LoRA パラメータの勾配 L2。"""
    out: dict[str, float] = {}
    for name, param in model.named_parameters():
        if not is_lora_param_name(name, cfg):
            continue
        if param.grad is None:
            continue
        out[name] = float(param.grad.detach().float().norm().item())
    return out


def build_loraplus_param_groups(
    model: Any,
    *,
    lr: float,
    lr_ratio_b: float = 4.0,
    weight_decay: float = 0.0,
) -> list[dict[str, Any]]:
    """LoRA+: A 行列と B 行列で非対称 LR の param group を作る。"""
    group_a: list[Any] = []
    group_b: list[Any] = []
    group_other: list[Any] = []
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        lower = name.lower()
        if "lora_a" in lower or lower.endswith(".a") and "lora" in lower:
            group_a.append(param)
        elif "lora_b" in lower or lower.endswith(".b") and "lora" in lower:
            group_b.append(param)
        elif "lora_" in lower:
            # 不明な LoRA は A 側 LR
            group_a.append(param)
        else:
            group_other.append(param)
    groups: list[dict[str, Any]] = []
    if group_a:
        groups.append({"params": group_a, "lr": lr, "weight_decay": weight_decay, "name": "lora_A"})
    if group_b:
        groups.append(
            {
                "params": group_b,
                "lr": lr * lr_ratio_b,
                "weight_decay": weight_decay,
                "name": "lora_B",
            }
        )
    if group_other:
        groups.append({"params": group_other, "lr": lr, "weight_decay": weight_decay, "name": "other"})
    return groups
