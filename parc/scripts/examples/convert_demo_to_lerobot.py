#!/usr/bin/env python3
"""デモ／ログ → LeRobot v3 データセット変換の最小例。

使い方（robot venv）:
  cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
  source ../../.venv/bin/activate
  python scripts/examples/convert_demo_to_lerobot.py \\
      --out data/datasets/my_panda_demos \\
      --repo-id local/my_panda_demos

関節角（SO-100/101 等）の場合は degrees 正本:
  python scripts/examples/convert_demo_to_lerobot.py \\
      --out data/datasets/my_so100_demos \\
      --repo-id local/my_so100_demos \\
      --control-mode joint_position \\
      --source-angle-unit radians \\
      --robot-type so100

このスクリプトは **ダミー 1 エピソード** を書き、ディレクトリ構造の確認用です。
本番では `iter_episodes()` を自前ローダに差し替えてください。

必須キー（SmolVLA / libero_plus / parc checkpoint 評価と互換・ee_delta）:
  observation.images.front  (H,W,3) uint8
  observation.images.wrist  (H,W,3) uint8
  observation.state         (8,) float32
  action                    (7,) float32
  task                      str（言語指示）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterator

import numpy as np

# parc パッケージ（uv run / editable install 前提）。スクリプト直実行時は src を追加。
_PARC_SRC = Path(__file__).resolve().parents[2] / "src"
if _PARC_SRC.is_dir() and str(_PARC_SRC) not in sys.path:
    sys.path.insert(0, str(_PARC_SRC))

from parc.data.angle_units import (  # noqa: E402
    TARGET_UNIT,
    AngleUnitsMeta,
    normalize_joint_frame_arrays,
    write_angle_units_meta,
)

FEATURES = {
    "observation.images.front": {
        "dtype": "video",
        "shape": (256, 256, 3),
        "names": ["height", "width", "channel"],
    },
    "observation.images.wrist": {
        "dtype": "video",
        "shape": (256, 256, 3),
        "names": ["height", "width", "channel"],
    },
    "observation.state": {
        "dtype": "float32",
        "shape": (8,),
        "names": [f"state_{i}" for i in range(8)],
    },
    "action": {
        "dtype": "float32",
        "shape": (7,),
        "names": [f"action_{i}" for i in range(7)],
    },
}


def iter_episodes(
    *,
    control_mode: str,
    source_angle_unit: str | None,
) -> Iterator[dict[str, Any]]:
    """自前データを yield する。

    各 episode:
      language: str
      frames: list[{front, wrist, state, action}]
    """
    # --- ここを差し替え ---
    h = w = 256
    frames = []
    for t in range(16):
        if control_mode == "joint_position":
            # ダミー: radians っぽい小さな絶対角（変換後に deg になる想定）
            # 本番ローダでは生ログの単位で入れる。
            if source_angle_unit == "radians":
                state = np.linspace(-0.5, 0.5, 8, dtype=np.float32) + 0.01 * t
                action = state.copy()
            else:
                state = np.linspace(-20.0, 20.0, 8, dtype=np.float32) + 0.5 * t
                action = state.copy()
        else:
            state = np.zeros(8, dtype=np.float32)
            action = np.zeros(7, dtype=np.float32)
        frames.append(
            {
                "front": np.zeros((h, w, 3), dtype=np.uint8),
                "wrist": np.zeros((h, w, 3), dtype=np.uint8),
                "state": state,
                "action": action,
            }
        )
    yield {
        "language": "pick up the bowl and place it on the plate",
        "frames": frames,
    }


def _parse_joint_indices(raw: str) -> list[int]:
    """comma-separated indices。空なら空リスト（全次元）。"""
    if not raw.strip():
        return []
    return [int(x) for x in raw.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="出力ルート（dataset_root）")
    parser.add_argument("--repo-id", default="local/my_panda_demos")
    parser.add_argument("--robot-type", default="panda")
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--control-mode",
        choices=("ee_delta", "joint_position"),
        default="ee_delta",
        help="ee_delta=現行 LIBERO 互換、joint_position=関節角（degrees 正本）",
    )
    parser.add_argument(
        "--source-angle-unit",
        choices=("radians", "degrees"),
        default=None,
        help="生ログの関節角単位（joint_position 時必須）",
    )
    parser.add_argument(
        "--joint-indices",
        default="",
        help="単位変換する次元（comma-separated、空=全次元）",
    )
    parser.add_argument(
        "--action-relative",
        action="store_true",
        help="action が相対指令のとき（スケール検査用メタ）",
    )
    args = parser.parse_args()

    if args.control_mode == "joint_position" and args.source_angle_unit is None:
        raise SystemExit("joint_position には --source-angle-unit が必要です")

    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    out = args.out.expanduser().resolve()
    if out.exists() and any(out.iterdir()) and not args.overwrite:
        raise SystemExit(f"出力先が空ではありません: {out} （--overwrite で再作成）")

    out.mkdir(parents=True, exist_ok=True)
    ds = LeRobotDataset.create(
        repo_id=args.repo_id,
        fps=args.fps,
        robot_type=args.robot_type,
        features=FEATURES,
        root=out,
        use_videos=True,
    )

    joint_indices = _parse_joint_indices(args.joint_indices)
    n_ep = 0
    for ep in iter_episodes(
        control_mode=args.control_mode,
        source_angle_unit=args.source_angle_unit,
    ):
        lang = str(ep["language"])
        for fr in ep["frames"]:
            state = np.asarray(fr["state"], dtype=np.float32)
            action = np.asarray(fr["action"], dtype=np.float32)
            if args.control_mode == "joint_position" and args.source_angle_unit is not None:
                state_n, action_n = normalize_joint_frame_arrays(
                    state=state,
                    action=action,
                    source_unit=args.source_angle_unit,
                    target_unit=TARGET_UNIT,
                    joint_indices=joint_indices or None,
                )
                state = state_n if state_n is not None else state
                action = action_n if action_n is not None else action
            ds.add_frame(
                {
                    "observation.images.front": np.asarray(fr["front"], dtype=np.uint8),
                    "observation.images.wrist": np.asarray(fr["wrist"], dtype=np.uint8),
                    "observation.state": state,
                    "action": action,
                    "task": lang,
                }
            )
        ds.save_episode()
        n_ep += 1

    ds.finalize()

    meta = AngleUnitsMeta(
        control_mode=args.control_mode,
        source_unit=args.source_angle_unit,
        stored_unit=TARGET_UNIT if args.control_mode == "joint_position" else None,
        joint_indices=joint_indices,
        action_is_absolute=not args.action_relative,
        notes="written by convert_demo_to_lerobot.py",
    )
    write_angle_units_meta(out, meta)

    print(f"wrote {n_ep} episodes → {out}")
    print(f"angle_units: control_mode={args.control_mode} stored={meta.stored_unit}")
    print("YAML 例:")
    print(f"  dataset_repo_id: {args.repo_id}")
    print(f"  dataset_root: {out}")


if __name__ == "__main__":
    main()
