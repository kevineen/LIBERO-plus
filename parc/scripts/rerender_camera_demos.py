#!/usr/bin/env python3
"""LIBERO demo states を視点摂動付きで再レンダし、staging (.npz) を書く。

LIBERO-plus .venv + EGL で実行:

  cd /home/kevin/Matsuo/robot/LIBERO-plus
  export MUJOCO_GL=egl
  .venv/bin/python parc/scripts/rerender_camera_demos.py \\
      --demo-glob 'parc/data/datasets/libero_spatial/*between_the_plate_and_the_ramekin*_demo.hdf5' \\
      --out parc/data/datasets/cam_views_staging_v1 \\
      --max-demos 5 \\
      --image-size 256

その後:

  cd parc && uv run scripts/staging_to_lerobot.py \\
      --staging data/datasets/cam_views_staging_v1 \\
      --out data/datasets/libero_cam_views_v1 \\
      --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from glob import glob
from pathlib import Path

import h5py
import numpy as np


# Train-safe grid: avoid exact eval hard views (11_15 / 13_15 / 14_15).
DEFAULT_VIEWS: list[tuple[int, int, int, int, int]] = [
    (h, v, 100, 0, 0)
    for h in (5, 8, 10, 12)
    for v in (5, 10, 15)
]


def _quat2axisangle(quat: np.ndarray) -> np.ndarray:
    """四元数 (x,y,z,w) → axis-angle (3,)。"""
    q = np.asarray(quat, dtype=np.float64).reshape(4)
    w = float(np.clip(q[3], -1.0, 1.0))
    den = float(np.sqrt(max(1.0 - w * w, 0.0)))
    if den < 1e-10:
        return np.zeros(3, dtype=np.float32)
    angle = 2.0 * float(np.arccos(w))
    axis = q[:3] / den
    return (axis * angle).astype(np.float32)


def obs_to_state8(obs: dict) -> np.ndarray:
    """eef_pos(3) + axisangle(3) + gripper_qpos(2)。"""
    eef_pos = np.asarray(obs["robot0_eef_pos"], dtype=np.float32).reshape(3)
    eef_quat = np.asarray(obs["robot0_eef_quat"], dtype=np.float32).reshape(4)
    grip = np.asarray(obs["robot0_gripper_qpos"], dtype=np.float32).reshape(-1)
    if grip.size == 1:
        grip = np.array([grip[0], -grip[0]], dtype=np.float32)
    return np.concatenate([eef_pos, _quat2axisangle(eef_quat), grip[:2]], axis=0)


def flip180(img: np.ndarray) -> np.ndarray:
    """HuggingFaceVLA/libero 慣習: 180° 回転。"""
    arr = np.asarray(img)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr[::-1, ::-1].copy()


def resolve_base_bddl(demo_path: Path, f: h5py.File) -> Path:
    """hdf5 内の bddl 名から実ファイルを解決する。"""
    from libero.libero import get_libero_path

    raw = str(f["data"].attrs.get("bddl_file_name", ""))
    name = Path(raw).name if raw else demo_path.name.replace("_demo.hdf5", ".bddl")
    # strip accidental view suffix if present
    if "_view_" in name:
        name = name.split("_view_")[0] + ".bddl"
    candidates = [
        Path(get_libero_path("bddl_files")) / "libero_spatial" / name,
        Path(get_libero_path("bddl_files")) / name,
        demo_path.with_name(name),
    ]
    for c in candidates:
        if c.is_file():
            return c.resolve()
    raise FileNotFoundError(f"BDDL not found for {demo_path}: tried {candidates}")


def view_bddl_path(base_bddl: Path, view: tuple[int, int, int, int, int]) -> str:
    """ControlEnv が parse できる仮想パス（実ファイルは base.bddl）。"""
    h, v, s, r, e = view
    stem = base_bddl.with_suffix("").as_posix()
    return f"{stem}_view_{h}_{v}_{s}_{r}_{e}_initstate_0.bddl"


def language_from_hdf5(f: h5py.File, fallback: str) -> str:
    try:
        info = json.loads(f["data"].attrs["problem_info"])
        lang = info.get("language_instruction") or info.get("language")
        if lang:
            return str(lang)
    except Exception:
        pass
    return fallback


def make_env(bddl_file_name: str, image_size: int):
    from libero.libero.envs import OffScreenRenderEnv

    return OffScreenRenderEnv(
        bddl_file_name=bddl_file_name,
        camera_heights=image_size,
        camera_widths=image_size,
    )


def render_episode(
    env,
    states: np.ndarray,
    actions: np.ndarray,
) -> dict[str, np.ndarray]:
    """state 再レンダ。actions 長に合わせて frames を切る。"""
    n = int(min(len(actions), max(len(states) - 1, 0), len(states)))
    if n <= 0:
        raise ValueError("empty demo")

    fronts, wrists, states8, acts = [], [], [], []
    for t in range(n):
        obs = env.regenerate_obs_from_state(states[t])
        fronts.append(flip180(obs["agentview_image"]))
        wrists.append(flip180(obs["robot0_eye_in_hand_image"]))
        states8.append(obs_to_state8(obs))
        acts.append(np.asarray(actions[t], dtype=np.float32).reshape(7))

    return {
        "front": np.stack(fronts, axis=0),
        "wrist": np.stack(wrists, axis=0),
        "state": np.stack(states8, axis=0).astype(np.float32),
        "action": np.stack(acts, axis=0).astype(np.float32),
    }


def process_demo(
    demo_path: Path,
    out_dir: Path,
    views: list[tuple[int, int, int, int, int]],
    max_demos: int,
    image_size: int,
    skip_existing: bool,
) -> int:
    written = 0
    with h5py.File(demo_path, "r") as f:
        base_bddl = resolve_base_bddl(demo_path, f)
        lang = language_from_hdf5(
            f,
            fallback=demo_path.name.replace("_demo.hdf5", "").replace("_", " "),
        )
        demo_keys = sorted(
            [k for k in f["data"].keys() if k.startswith("demo")],
            key=lambda x: int(x.split("_")[-1]) if "_" in x else 0,
        )[:max_demos]

        for view in views:
            env = None
            try:
                env = make_env(view_bddl_path(base_bddl, view), image_size)
                for dk in demo_keys:
                    h, v, s, r, e = view
                    out_name = (
                        f"{demo_path.stem}__{dk}"
                        f"__view_{h}_{v}_{s}_{r}_{e}.npz"
                    )
                    out_path = out_dir / out_name
                    if skip_existing and out_path.is_file():
                        print(f"skip {out_path.name}")
                        written += 1
                        continue

                    states = f[f"data/{dk}/states"][()]
                    actions = np.asarray(f[f"data/{dk}/actions"][()])
                    # reset once per demo for cleanliness
                    try:
                        env.reset()
                    except Exception:
                        pass

                    packed = render_episode(env, states, actions)
                    meta = {
                        "source_demo": str(demo_path),
                        "demo_key": dk,
                        "language": lang,
                        "view": {
                            "horizon": h,
                            "vertical": v,
                            "scale": s,
                            "end_point_rot": r,
                            "end_point_vertical": e,
                        },
                        "base_bddl": str(base_bddl),
                        "n_frames": int(packed["action"].shape[0]),
                        "image_size": image_size,
                        "flipped_180": True,
                    }
                    np.savez_compressed(
                        out_path,
                        front=packed["front"],
                        wrist=packed["wrist"],
                        state=packed["state"],
                        action=packed["action"],
                        meta_json=np.asarray(json.dumps(meta)),
                    )
                    written += 1
                    print(f"wrote {out_path.name} frames={meta['n_frames']}")
            finally:
                if env is not None:
                    env.close()
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo-glob",
        required=True,
        help="例: parc/data/datasets/libero_spatial/*between*_demo.hdf5",
    )
    parser.add_argument("--out", type=Path, required=True, help="staging 出力ディレクトリ")
    parser.add_argument("--max-demos", type=int, default=5, help="各 hdf5 から使う demo 数")
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument(
        "--views",
        default="",
        help="カンマ区切り h_v_s_r_e（空なら DEFAULT_VIEWS）",
    )
    parser.add_argument("--limit-episodes", type=int, default=0, help="合計本数上限（0=無制限）")
    parser.add_argument("--skip-existing", action="store_true", default=True)
    parser.add_argument("--no-skip-existing", action="store_true")
    args = parser.parse_args()

    skip_existing = not args.no_skip_existing
    if args.views.strip():
        views = []
        for token in args.views.split(","):
            parts = [int(x) for x in token.strip().split("_")]
            if len(parts) != 5:
                raise SystemExit(f"bad view token: {token}")
            views.append(tuple(parts))  # type: ignore[arg-type]
    else:
        views = list(DEFAULT_VIEWS)

    root = Path(__file__).resolve().parents[2]  # LIBERO-plus/
    # allow running from parc/ or repo root
    os.chdir(root)

    demos = sorted(Path(p).resolve() for p in glob(args.demo_glob))
    if not demos:
        # try relative to repo
        demos = sorted(Path(p).resolve() for p in glob(str(root / args.demo_glob)))
    if not demos:
        raise SystemExit(f"no demos matched: {args.demo_glob}")

    out_dir = args.out if args.out.is_absolute() else (root / args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for demo in demos:
        print(f"=== {demo.name} ===")
        n = process_demo(
            demo,
            out_dir,
            views=views,
            max_demos=args.max_demos,
            image_size=args.image_size,
            skip_existing=skip_existing,
        )
        total += n
        if args.limit_episodes and total >= args.limit_episodes:
            print(f"hit --limit-episodes={args.limit_episodes}")
            break

    manifest = {
        "n_episodes": total,
        "views": [list(v) for v in views],
        "demos": [str(d) for d in demos],
        "image_size": args.image_size,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"done staging episodes≈{total} → {out_dir}")


if __name__ == "__main__":
    # ensure libero is importable when launched from parc/
    # Only add repo root: `import libero` → outer package, `libero.libero` → inner.
    # Do NOT add repo/libero (that makes `libero` resolve to the inner package and
    # breaks `from libero.libero import …` on some hosts, e.g. thor).
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo))
    main()
