#!/usr/bin/env python3
"""staging (.npz) → LeRobot v3 データセット。

  cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
  uv run scripts/staging_to_lerobot.py \\
      --staging data/datasets/cam_views_staging_v1 \\
      --out data/datasets/libero_cam_views_v1 \\
      --repo-id local/libero_cam_views_v1 \\
      --overwrite
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np


# fps は libero_plus と features 完全一致させる（aggregate / mix 用）
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
        "fps": 20,
    },
    "action": {
        "dtype": "float32",
        "shape": (7,),
        "names": [f"action_{i}" for i in range(7)],
        "fps": 20,
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-id", default="local/libero_cam_views_v1")
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    staging = args.staging.expanduser().resolve()
    out = args.out.expanduser().resolve()
    files = sorted(staging.glob("*.npz"))
    if not files:
        raise SystemExit(f"no .npz in {staging}")
    if args.limit > 0:
        files = files[: args.limit]

    if out.exists():
        if not args.overwrite:
            raise SystemExit(f"出力先が既にあります: {out} （--overwrite）")
        shutil.rmtree(out)
    # LeRobotDataset.create が root を mkdir(exist_ok=False) するので親だけ作る
    out.parent.mkdir(parents=True, exist_ok=True)

    # detect image size from first file
    sample = np.load(files[0], allow_pickle=False)
    h, w = int(sample["front"].shape[1]), int(sample["front"].shape[2])
    features = dict(FEATURES)
    features["observation.images.front"] = {
        **FEATURES["observation.images.front"],
        "shape": (h, w, 3),
    }
    features["observation.images.wrist"] = {
        **FEATURES["observation.images.wrist"],
        "shape": (h, w, 3),
    }

    ds = LeRobotDataset.create(
        repo_id=args.repo_id,
        fps=args.fps,
        robot_type="panda",
        features=features,
        root=out,
        use_videos=True,
    )

    n_ep = 0
    for path in files:
        data = np.load(path, allow_pickle=False)
        meta = {}
        if "meta_json" in data.files:
            meta = json.loads(str(data["meta_json"]))
        lang = str(meta.get("language") or "pick up the black bowl and place it on the plate")
        front = np.asarray(data["front"])
        wrist = np.asarray(data["wrist"])
        state = np.asarray(data["state"], dtype=np.float32)
        action = np.asarray(data["action"], dtype=np.float32)
        t_len = int(min(len(front), len(wrist), len(state), len(action)))
        for t in range(t_len):
            ds.add_frame(
                {
                    "observation.images.front": front[t].astype(np.uint8),
                    "observation.images.wrist": wrist[t].astype(np.uint8),
                    "observation.state": state[t].astype(np.float32),
                    "action": action[t].astype(np.float32),
                    "task": lang,
                }
            )
        ds.save_episode()
        n_ep += 1
        print(f"episode {n_ep}: {path.name} frames={t_len}")

    ds.finalize()
    (out / "source_staging.txt").write_text(str(staging) + "\n")
    print(f"wrote {n_ep} episodes → {out}")
    print(f"dataset_repo_id: {args.repo_id}")
    print(f"dataset_root: {out}")


if __name__ == "__main__":
    main()
