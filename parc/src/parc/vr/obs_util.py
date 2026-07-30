"""LIBERO 生観測 → 学習互換の画像・状態ベクトル。"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def _as_hwc_uint8(img: Any) -> np.ndarray:
    """画像を (H,W,3) uint8 にする。"""
    arr = np.asarray(img)
    if arr.ndim != 3 or arr.shape[-1] not in (3, 4):
        raise ValueError(f"expected HWC image, got shape {arr.shape}")
    if arr.shape[-1] == 4:
        arr = arr[..., :3]
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr


def flip_image_180(img: np.ndarray) -> np.ndarray:
    """HuggingFaceVLA/libero 系の 180° 回転。"""
    return np.ascontiguousarray(np.flip(img, axis=(0, 1)))


def quat_to_axis_angle(quat: np.ndarray) -> np.ndarray:
    """四元数 (x,y,z,w) → axis-angle (3,)。"""
    q = np.asarray(quat, dtype=np.float64).reshape(4)
    w = float(np.clip(q[3], -1.0, 1.0))
    den = float(np.sqrt(max(1.0 - w * w, 0.0)))
    if den < 1e-10:
        return np.zeros(3, dtype=np.float32)
    angle = 2.0 * float(np.arccos(w))
    axis = q[:3] / den
    return (axis * angle).astype(np.float32)


def extract_state8(obs: Mapping[str, Any]) -> np.ndarray:
    """eef_pos(3) + axisangle(3) + gripper_qpos(2)。"""
    eef_pos = np.asarray(obs["robot0_eef_pos"], dtype=np.float32).reshape(3)
    eef_quat = np.asarray(obs["robot0_eef_quat"], dtype=np.float32).reshape(4)
    grip = np.asarray(obs["robot0_gripper_qpos"], dtype=np.float32).reshape(-1)
    if grip.size == 1:
        grip = np.array([grip[0], -grip[0]], dtype=np.float32)
    return np.concatenate([eef_pos, quat_to_axis_angle(eef_quat), grip[:2]], axis=0)


def extract_front_wrist(
    obs: Mapping[str, Any],
    *,
    flip_images: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """agentview / eye-in-hand を (front, wrist) uint8 HWC で返す。"""
    front = _as_hwc_uint8(obs["agentview_image"])
    wrist = _as_hwc_uint8(obs["robot0_eye_in_hand_image"])
    if flip_images:
        front = flip_image_180(front)
        wrist = flip_image_180(wrist)
    return front, wrist


def obs_to_frame_dict(
    obs: Mapping[str, Any],
    action: np.ndarray,
    *,
    flip_images: bool = True,
) -> dict[str, np.ndarray]:
    """1 フレーム分の LeRobot 互換 dict（task 以外）。"""
    front, wrist = extract_front_wrist(obs, flip_images=flip_images)
    action7 = np.asarray(action, dtype=np.float32).reshape(7)
    return {
        "front": front,
        "wrist": wrist,
        "state": extract_state8(obs),
        "action": action7,
    }
