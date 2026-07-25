#!/usr/bin/env python3
"""学習データと評価時 policy 入力の向き・キー一致を目視確認する。

出力:
  <out_dir>/dataset_front.png / dataset_wrist.png
  <out_dir>/env_raw_front.png / env_flip_front.png （180°）
  <out_dir>/env_raw_wrist.png / env_flip_wrist.png
  <out_dir>/report.txt

使い方（robot venv + eval と同じ PYTHONPATH）:
  bash scripts/eval_ckpt.sh の代わりに:
  source ../.venv/bin/activate  # Matsuo/robot
  PYTHONPATH=src:.. python scripts/dump_obs_align.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


def _save_rgb(path: Path, arr: np.ndarray) -> None:
    """HWC uint8 / float[0,1] / CHW float を PNG 保存する。"""
    from PIL import Image

    x = np.asarray(arr)
    if x.ndim == 4:
        x = x[0]
    if x.ndim == 3 and x.shape[0] in (1, 3) and x.shape[-1] not in (1, 3):
        x = np.transpose(x, (1, 2, 0))
    if np.issubdtype(x.dtype, np.floating):
        x = (np.clip(x, 0.0, 1.0) * 255.0).astype(np.uint8)
    else:
        x = np.clip(x, 0, 255).astype(np.uint8)
    if x.shape[-1] == 1:
        x = np.repeat(x, 3, axis=-1)
    Image.fromarray(x[..., :3]).save(path)


def _dataset_root() -> Path | None:
    candidates = [
        Path.home() / ".cache/huggingface/lerobot/hub/datasets--lerobot--libero_plus",
        Path("/mnt/sda/huggingface/lerobot/hub/datasets--lerobot--libero_plus"),
    ]
    for base in candidates:
        snaps = base / "snapshots"
        if snaps.is_dir():
            kids = sorted(p for p in snaps.iterdir() if p.is_dir())
            if kids:
                return kids[0]
    return None


def _dump_dataset_frames(out: Path, root: Path) -> list[str]:
    """データセット動画の先頭フレームを保存する（AV1 は ffmpeg 経由）。"""
    import subprocess
    import tempfile

    notes: list[str] = []
    for key, name in (
        ("observation.images.front", "dataset_front.png"),
        ("observation.images.wrist", "dataset_wrist.png"),
    ):
        vids = sorted((root / "videos" / key).rglob("*.mp4"))
        if not vids:
            notes.append(f"MISSING dataset video for {key}")
            continue
        src = vids[0]
        dest = out / name
        # OpenCV は AV1 を読めない環境があるため ffmpeg で 1 フレーム抽出
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "frame.png"
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(src),
                "-vf",
                "select=eq(n\\,0)",
                "-vframes",
                "1",
                str(tmp),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0 or not tmp.is_file():
                notes.append(f"FAILED ffmpeg {src.name}: {(proc.stderr or '')[-200:]}")
                continue
            # そのままコピー
            dest.write_bytes(tmp.read_bytes())
            from PIL import Image

            im = Image.open(dest)
            notes.append(f"dataset {key}: {src.name} size={im.size}")
    return notes


def _dump_env_policy_frames(out: Path, cam: int = 256) -> list[str]:
    """評価 env 生画像と flip 後（policy 入力）を保存する。"""
    from libero.libero import benchmark

    from parc.env.make_env import make_offscreen_env
    from parc.policies.lerobot_ckpt import raw_libero_obs_to_batch

    notes: list[str] = []
    bench = benchmark.get_benchmark_dict()["libero_spatial"]()
    task = bench.get_task(0)
    bddl = bench.get_task_bddl_file_path(0)
    notes.append(f"bddl={bddl}")
    notes.append(f"task_name={getattr(task, 'language', None) or getattr(task, 'name', '')}")
    notes.append(
        "WARNING: task_id=0 is LIBERO-plus (often Background Textures), not vanilla LIBERO."
    )

    env = make_offscreen_env(
        str(bddl),
        camera_heights=cam,
        camera_widths=cam,
    )
    try:
        obs = env.reset()
        if isinstance(obs, tuple):
            obs = obs[0]
        language = str(getattr(task, "language", "") or "pick up the bowl")
        for flip in (False, True):
            batch = raw_libero_obs_to_batch(obs, task=language, flip_images=flip)
            tag = "flip" if flip else "raw"
            _save_rgb(out / f"env_{tag}_front.png", batch["observation.images.front"].numpy())
            _save_rgb(out / f"env_{tag}_wrist.png", batch["observation.images.wrist"].numpy())
            st = batch["observation.state"].numpy().reshape(-1)
            notes.append(f"env flip={flip}: state8={st.tolist()} front={tuple(batch['observation.images.front'].shape)}")
        # 生 env（動画と同じ向き）
        _save_rgb(out / "env_video_front.png", obs["agentview_image"])
        _save_rgb(out / "env_video_wrist.png", obs["robot0_eye_in_hand_image"])
        notes.append(
            "NOTE: eval videos use env_video_* (unflipped). "
            "policy sees env_flip_* when flip_images=true."
        )
    finally:
        env.close()
    return notes


def _ckpt_schema(ckpt: Path) -> dict:
    cfg = json.loads((ckpt / "config.json").read_text())
    return {
        "n_action_steps": cfg.get("n_action_steps"),
        "chunk_size": cfg.get("chunk_size"),
        "input_features": cfg.get("input_features"),
        "output_features": cfg.get("output_features"),
        "freeze_vision_encoder": cfg.get("freeze_vision_encoder"),
        "train_expert_only": cfg.get("train_expert_only"),
        "resize_imgs_with_padding": cfg.get("resize_imgs_with_padding"),
        "optimizer_lr": cfg.get("optimizer_lr"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        default="/mnt/sda/parc_libero_plus/debug/obs_align",
        help="出力ディレクトリ",
    )
    ap.add_argument(
        "--ckpt",
        default=(
            "/mnt/sda/parc_libero_plus/experiments/"
            "20260725T011626Z_overnight_ft_v1_t003/train_output/checkpoints/"
            "010000/pretrained_model"
        ),
    )
    ap.add_argument("--cam", type=int, default=256)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    lines: list[str] = ["# obs align report", f"out={out}"]
    root = _dataset_root()
    if root is None:
        lines.append("ERROR: libero_plus dataset cache not found")
    else:
        lines.append(f"dataset_root={root}")
        lines.extend(_dump_dataset_frames(out, root))

    try:
        lines.extend(_dump_env_policy_frames(out, cam=args.cam))
    except Exception as exc:  # noqa: BLE001 — 診断用に全文
        lines.append(f"ERROR env dump: {type(exc).__name__}: {exc}")

    ckpt = Path(args.ckpt)
    if (ckpt / "config.json").is_file():
        schema = _ckpt_schema(ckpt)
        lines.append("ckpt_schema=" + json.dumps(schema, indent=2))
        expected_keys = {
            "observation.images.front",
            "observation.images.wrist",
            "observation.state",
        }
        got = set((schema.get("input_features") or {}).keys())
        if got == expected_keys:
            lines.append("SCHEMA_OK: input_features match eval wrapper keys")
        else:
            lines.append(f"SCHEMA_MISMATCH: got={sorted(got)} expected={sorted(expected_keys)}")
        out_f = schema.get("output_features") or {}
        act = out_f.get("action") or {}
        shape = act.get("shape") if isinstance(act, dict) else None
        if shape == [7]:
            lines.append("ACTION_OK: action dim 7")
        else:
            lines.append(f"ACTION_CHECK: action shape={shape}")
    else:
        lines.append(f"ERROR: ckpt missing config.json: {ckpt}")

    lines.append("")
    lines.append("HOW_TO_READ:")
    lines.append("- Compare dataset_front.png with env_flip_front.png (same uprightness → flip=true OK).")
    lines.append("- env_video_front.png matches saved eval mp4 orientation (NOT what policy sees if flip).")
    lines.append("- task_ids:[0] is still LIBERO-plus (e.g. Background Textures), not vanilla LIBERO.")

    report = "\n".join(lines) + "\n"
    (out / "report.txt").write_text(report)
    print(report)
    return 0 if "ERROR" not in report else 1


if __name__ == "__main__":
    sys.exit(main())
