"""学習バックエンド呼び出し（まず LeRobot コマンド生成）。"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any


def build_lerobot_train_cmd(
    train_cfg: dict[str, Any],
    *,
    output_dir: Path,
    seed: int = 0,
) -> list[str]:
    """lerobot-train の引数リストを組み立てる。"""
    from parc.paths import PARC_ROOT

    policy_type = train_cfg.get("policy_type", "smolvla")
    dataset = train_cfg.get("dataset_repo_id", "lerobot/libero_plus")
    steps = int(train_cfg.get("steps", 10000))
    batch_size = int(train_cfg.get("batch_size", 4))
    env_task = train_cfg.get("env_task", "libero_spatial")
    eval_freq = int(train_cfg.get("eval_freq", 1000))
    eval_n = int(train_cfg.get("eval_n_episodes", 1))
    load_vlm = bool(train_cfg.get("load_vlm_weights", True))
    repo_id = train_cfg.get("policy_repo_id")
    dataset_root = train_cfg.get("dataset_root")

    # 現行 LeRobot は MultiLeRobotDataset 無効。リスト mix は物理マージ後に単一 ID で渡す。
    if isinstance(dataset, (list, tuple)) or (
        isinstance(dataset, str) and dataset.strip().startswith("[")
    ):
        raise ValueError(
            "train.dataset_repo_id にリストは渡せません（LeRobot MultiDataset 無効）。"
            " 先に `parc-mix-datasets` でマージし、単一 repo_id + dataset_root を指定してください。"
        )

    # 任意の追加 CLI（アルゴリズム実験用）
    extra = train_cfg.get("extra_args") or []
    if isinstance(extra, str):
        extra = [extra]
    extra_list = [str(x) for x in extra]
    # extra_args 側で dataset.repo_id / root を既に指定している場合は二重指定を避ける
    extra_has_repo = any(x.startswith("--dataset.repo_id") for x in extra_list)
    extra_has_root = any(x.startswith("--dataset.root") for x in extra_list)
    if extra_has_repo and any(
        ("=[" in x) or (x.rstrip().endswith("]")) for x in extra_list if "repo_id" in x
    ):
        raise ValueError(
            "extra_args の --dataset.repo_id=[...] は現行 LeRobot で未対応。"
            " `parc-mix-datasets` で物理マージしてください。"
        )

    cmd = [
        "lerobot-train",
        f"--policy.type={policy_type}",
    ]
    if not extra_has_repo:
        cmd.append(f"--dataset.repo_id={dataset}")
    # LeRobot 0.5.x: libero_plus env type は未収録。plus fork を import して評価する想定。
    cmd.extend(
        [
            f"--env.type=libero",
            f"--env.task={env_task}",
            f"--output_dir={output_dir}",
            f"--steps={steps}",
            f"--batch_size={batch_size}",
            f"--seed={seed}",
            f"--eval.batch_size=1",
            f"--eval.n_episodes={eval_n}",
            f"--eval_freq={eval_freq}",
            f"--policy.load_vlm_weights={'true' if load_vlm else 'false'}",
            # Hub への自動 push はオフ（ローカル実験用）
            "--policy.push_to_hub=false",
        ]
    )
    if dataset_root and not extra_has_root:
        root = Path(str(dataset_root)).expanduser()
        if not root.is_absolute():
            root = (PARC_ROOT / root).resolve()
        cmd.append(f"--dataset.root={root}")
    if repo_id:
        cmd.append(f"--policy.repo_id={repo_id}")
    cmd.extend(extra_list)
    return cmd


def run_training(config: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """設定に従い学習を起動（または dry-run）。"""
    from parc.data.benchmark_dataset import ensure_train_benchmark_supported

    # 非 LIBERO ベンチは第1弾で本学習未接続 → 明確な結果を返す
    blocked = ensure_train_benchmark_supported(config)
    if blocked is not None:
        (run_dir / "logs" / "train_benchmark.json").write_text(
            __import__("json").dumps(blocked, indent=2, ensure_ascii=False) + "\n"
        )
        return blocked

    train_cfg = config.get("train") or {}
    backend = train_cfg.get("backend", "lerobot")
    seed = int(config.get("seed", 0))
    # lerobot は output_dir が既存だと落ちるので、未作成のサブディレクトリを渡す
    ckpt_dir = run_dir / "train_output"

    if backend == "lerobot":
        cmd = build_lerobot_train_cmd(train_cfg, output_dir=ckpt_dir, seed=seed)
        cmd_str = " ".join(shlex.quote(c) for c in cmd)
        (run_dir / "logs" / "train_cmd.txt").write_text(cmd_str + "\n")

        if train_cfg.get("dry_run", True):
            return {
                "status": "dry_run",
                "backend": backend,
                "command": cmd_str,
                "hint": (
                    "dry_run=true のため未実行。"
                    " configs で dry_run: false にし、"
                    "親の Matsuo/robot で source scripts/thor_cuda_env.sh 後に再実行。"
                ),
            }

        env = os.environ.copy()
        proc = subprocess.run(cmd, cwd=str(run_dir), env=env, check=False)
        return {
            "status": "finished" if proc.returncode == 0 else "failed",
            "backend": backend,
            "command": cmd_str,
            "returncode": proc.returncode,
        }

    if backend in {"grpo", "gspo"}:
        if train_cfg.get("dry_run", False):
            return {
                "status": "dry_run",
                "backend": backend,
                "hint": "dry_run=true — GRPO/GSPO は未実行",
            }
        from parc.train.grpo_gspo import run_grpo_gspo_training

        return run_grpo_gspo_training(config, run_dir)

    if backend == "flow_apo":
        if train_cfg.get("dry_run", False):
            return {
                "status": "dry_run",
                "backend": backend,
                "hint": "dry_run=true — Flow-APO は未実行",
                "sidecar": True,
                "parent_ckpt_eligible": False,
            }
        from parc.train.flow_apo import run_flow_apo_training

        return run_flow_apo_training(config, run_dir)

    if backend in {"openpi", "openvla", "gr00t"}:
        return {
            "status": "not_implemented",
            "backend": backend,
            "hint": (
                "本選で配布される Pi0/Gr00t/OpenVLA 学習コードを "
                "parc.train に接続してください。"
            ),
        }

    raise ValueError(f"Unknown train.backend: {backend}")
