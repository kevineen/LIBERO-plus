#!/usr/bin/env python3
"""long_ft / overnight の Gate1・Gate2 判定をまとめて表示する。

Gate1: path_length がランダム帯より上、または動画ディレクトリあり（人手確認の合図）
Gate2: success_rate > 0

  cd parc && uv run scripts/check_ft_gates.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_metrics(run_dir: Path) -> dict | None:
    p = run_dir / "metrics.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text())


def _gate_status(metrics: dict | None, run_dir: Path) -> dict:
    videos = run_dir / "videos"
    has_videos = videos.is_dir() and any(videos.glob("*.mp4"))
    if metrics is None:
        return {
            "gate1": "pending" if not has_videos else "review_videos",
            "gate2": "pending",
            "sr": None,
            "mean_steps": None,
            "mean_path_length": None,
            "has_videos": has_videos,
        }
    eps = metrics.get("episodes") or []
    pls = [float(e.get("path_length") or 0.0) for e in eps]
    mean_pl = sum(pls) / len(pls) if pls else None
    sr = float(metrics.get("success_rate") or 0.0)
    # ランダム path_length ≈ 0.3、overnight 失敗帯 ≈ 1.1–1.3
    gate1 = "pass" if (mean_pl is not None and mean_pl >= 0.8) or has_videos else "fail"
    if has_videos and sr <= 0.0:
        gate1 = "review_videos"  # 人手で近傍到達を確認
    if mean_pl is not None and mean_pl >= 0.8:
        gate1 = "pass_proxy"  # 動きはある（掴み精度は動画で確認）
    gate2 = "pass" if sr > 0.0 else "fail"
    return {
        "gate1": gate1,
        "gate2": gate2,
        "sr": sr,
        "mean_steps": metrics.get("mean_steps"),
        "mean_path_length": mean_pl,
        "has_videos": has_videos,
        "n_episodes": metrics.get("n_episodes"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--experiments-dir",
        default="/mnt/sda/parc_libero_plus/experiments",
    )
    ap.add_argument(
        "--name-substr",
        action="append",
        default=None,
        help="run 名フィルタ（複数可）。省略時 long_ft / overnight_ft / clean_task0",
    )
    args = ap.parse_args()
    root = Path(args.experiments_dir)
    substrs = args.name_substr or ["long_ft", "overnight_ft", "clean_task0", "smolvla_subset"]
    runs = sorted(
        (p for p in root.iterdir() if p.is_dir() and any(s in p.name for s in substrs)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    print(f"experiments_dir={root}")
    print(f"filters={substrs}")
    print("")
    any_gate2 = False
    for run in runs[:25]:
        m = _load_metrics(run)
        g = _gate_status(m, run)
        if g["gate2"] == "pass":
            any_gate2 = True
        print(
            f"{run.name}\n"
            f"  Gate1={g['gate1']}  Gate2={g['gate2']}  "
            f"SR={g['sr']}  mean_steps={g['mean_steps']}  "
            f"path_length={g['mean_path_length']}  videos={g['has_videos']}"
        )
    print("")
    if any_gate2:
        print("NEXT: Gate2 passed → GRPO/GSPO (docs/09) may start.")
    else:
        print(
            "NEXT: Gate2 not yet. Wait for long_ft_v1, or if 50k done with SR=0:\n"
            "  uv run parc-enqueue --sweep configs/sweeps/long_ft_unfreeze_v1.yaml"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
