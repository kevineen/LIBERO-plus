#!/usr/bin/env python
"""MolmoAct2 Gate0: HF sample 画像で predict_action が動くか確認する（env 不要）。

robot venv で実行:
  cd parc
  export PYTHONPATH=src:..
  python scripts/molmoact2_infer_smoke.py
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import torch
from huggingface_hub import hf_hub_download
from PIL import Image


def _axisangle_to_quat(aa: np.ndarray) -> np.ndarray:
    """axis-angle (3,) → quat (x,y,z,w)。"""
    v = np.asarray(aa, dtype=np.float64).reshape(3)
    angle = float(np.linalg.norm(v))
    if angle < 1e-10:
        return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    axis = v / angle
    s = float(np.sin(angle * 0.5))
    return np.array(
        [axis[0] * s, axis[1] * s, axis[2] * s, float(np.cos(angle * 0.5))],
        dtype=np.float32,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        default="allenai/MolmoAct2-LIBERO",
        help="HF repo id or local checkpoint dir",
    )
    parser.add_argument("--device", default=None)
    parser.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32", "float16"])
    args = parser.parse_args()

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[g0] path={args.path} device={device} dtype={args.dtype}")

    from parc.policies.molmoact2 import MolmoAct2HFPolicy

    # 公式サンプル（カメラ順: agentview → wrist）
    agent = Image.open(
        hf_hub_download(args.path, "assets/sample_agentview_rgb.png")
    ).convert("RGB")
    wrist = Image.open(
        hf_hub_download(args.path, "assets/sample_wrist_rgb.png")
    ).convert("RGB")
    task = (
        "put the white mug on the left plate and put the yellow and white mug "
        "on the right plate"
    )
    state = np.array(
        [
            -0.05338004603981972,
            0.007029631175100803,
            0.6783280968666077,
            3.1407692432403564,
            0.0017593271331861615,
            -0.08994418382644653,
            0.03878866136074066,
            -0.03878721222281456,
        ],
        dtype=np.float32,
    )

    t0 = time.perf_counter()
    policy = MolmoAct2HFPolicy(
        args.path,
        device=device,
        dtype=args.dtype,
        flip_images=False,  # 公式 PNG はそのまま
        enable_cuda_graph=False,
    )
    print(f"[g0] load_sec={time.perf_counter() - t0:.1f}")

    dtype = {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }[args.dtype]
    with torch.inference_mode():
        kwargs = dict(
            processor=policy.processor,
            images=[agent, wrist],
            task=task,
            state=state,
            norm_tag="libero",
            inference_action_mode="continuous",
            enable_depth_reasoning=False,
            num_steps=10,
            normalize_language=True,
            enable_cuda_graph=False,
        )
        t1 = time.perf_counter()
        if dtype in {torch.bfloat16, torch.float16} and device.startswith("cuda"):
            with torch.autocast("cuda", dtype=dtype):
                out = policy.model.predict_action(**kwargs)
        else:
            out = policy.model.predict_action(**kwargs)
        print(f"[g0] direct_predict_sec={time.perf_counter() - t1:.2f}")

    actions_t = out.actions
    if hasattr(actions_t, "detach"):
        actions_t = actions_t.detach().to("cpu").float()
    actions = np.asarray(actions_t, dtype=np.float32)
    print(f"[g0] direct_actions_shape={actions.shape} finite={np.isfinite(actions).all()}")
    if actions.size < 7 or not np.isfinite(actions).all():
        raise SystemExit("G0 FAIL: invalid direct actions")

    fake_obs = {
        "agentview_image": np.asarray(agent, dtype=np.uint8),
        "robot0_eye_in_hand_image": np.asarray(wrist, dtype=np.uint8),
        "robot0_eef_pos": state[:3],
        "robot0_eef_quat": _axisangle_to_quat(state[3:6]),
        "robot0_gripper_qpos": state[6:8],
        "task": task,
    }
    policy.reset()
    t2 = time.perf_counter()
    a0 = policy.act(fake_obs)
    print(f"[g0] act_shape={a0.shape} act_sec={time.perf_counter() - t2:.2f} a0={a0}")
    if a0.shape != (7,) or not np.isfinite(a0).all():
        raise SystemExit("G0 FAIL: invalid Policy.act output")

    if device.startswith("cuda"):
        peak = torch.cuda.max_memory_allocated() / (1024**3)
        print(f"[g0] peak_allocated_gib={peak:.2f}")

    print("[g0] PASS")


if __name__ == "__main__":
    main()
