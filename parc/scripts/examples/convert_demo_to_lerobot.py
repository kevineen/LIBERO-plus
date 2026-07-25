#!/usr/bin/env python3
"""デモ／ログ → LeRobot v3 データセット変換の最小例。

使い方（robot venv）:
  cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
  source ../../.venv/bin/activate
  python scripts/examples/convert_demo_to_lerobot.py \\
      --out data/datasets/my_panda_demos \\
      --repo-id local/my_panda_demos

このスクリプトは **ダミー 1 エピソード** を書き、ディレクトリ構造の確認用です。
本番では `iter_episodes()` を自前ローダに差し替えてください。

必須キー（SmolVLA / libero_plus / parc checkpoint 評価と互換）:
  observation.images.front  (H,W,3) uint8
  observation.images.wrist  (H,W,3) uint8
  observation.state         (8,) float32
  action                    (7,) float32
  task                      str（言語指示）
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterator

import numpy as np


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


def iter_episodes() -> Iterator[dict[str, Any]]:
    """自前データを yield する。

    各 episode:
      language: str
      frames: list[{front, wrist, state, action}]
    """
    # --- ここを差し替え ---
    h = w = 256
    frames = []
    for t in range(16):
        frames.append(
            {
                "front": np.zeros((h, w, 3), dtype=np.uint8),
                "wrist": np.zeros((h, w, 3), dtype=np.uint8),
                "state": np.zeros(8, dtype=np.float32),
                "action": np.zeros(7, dtype=np.float32),
            }
        )
    yield {
        "language": "pick up the bowl and place it on the plate",
        "frames": frames,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="出力ルート（dataset_root）")
    parser.add_argument("--repo-id", default="local/my_panda_demos")
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    out = args.out.expanduser().resolve()
    if out.exists() and any(out.iterdir()) and not args.overwrite:
        raise SystemExit(f"出力先が空ではありません: {out} （--overwrite で再作成）")

    out.mkdir(parents=True, exist_ok=True)
    ds = LeRobotDataset.create(
        repo_id=args.repo_id,
        fps=args.fps,
        robot_type="panda",
        features=FEATURES,
        root=out,
        use_videos=True,
    )

    n_ep = 0
    for ep in iter_episodes():
        lang = str(ep["language"])
        for fr in ep["frames"]:
            ds.add_frame(
                {
                    "observation.images.front": np.asarray(fr["front"], dtype=np.uint8),
                    "observation.images.wrist": np.asarray(fr["wrist"], dtype=np.uint8),
                    "observation.state": np.asarray(fr["state"], dtype=np.float32),
                    "action": np.asarray(fr["action"], dtype=np.float32),
                    "task": lang,
                }
            )
        ds.save_episode()
        n_ep += 1

    ds.finalize()
    print(f"wrote {n_ep} episodes → {out}")
    print("YAML 例:")
    print(f"  dataset_repo_id: {args.repo_id}")
    print(f"  dataset_root: {out}")


if __name__ == "__main__":
    main()
