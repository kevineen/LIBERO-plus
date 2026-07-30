"""データセット収集メタ（カメラ・座標系・オペレータ等）。

LIBERO sim の宣言的デフォルトを持ち、実機キャリブ JSON で上書きできる。
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

COLLECTION_INFO_NAME = "collection_info.json"
SCHEMA_VERSION = 1


def default_libero_sim_cameras(
    *,
    image_size: tuple[int, int] = (256, 256),
    render_size: tuple[int, int] = (128, 128),
) -> dict[str, Any]:
    """LIBERO OffScreenRenderEnv 向けの宣言的カメラ定義。"""
    h, w = image_size
    rh, rw = render_size
    return {
        "front": {
            "name": "agentview",
            "stream_key": "observation.images.front",
            "env_key": "agentview_image",
            "frame_id": "cam_front",
            "resolution": [h, w],
            "render_resolution": [rh, rw],
            "model": "pinhole_declared",
            # 実機差し込み用。sim 既定は null（宣言のみ）
            "intrinsics": None,
            "extrinsics": None,
            "notes": "LIBERO agentview; set intrinsics/extrinsics via calib_override",
        },
        "wrist": {
            "name": "eye_in_hand",
            "stream_key": "observation.images.wrist",
            "env_key": "robot0_eye_in_hand_image",
            "frame_id": "cam_wrist",
            "resolution": [h, w],
            "render_resolution": [rh, rw],
            "model": "pinhole_declared",
            "intrinsics": None,
            "extrinsics": None,
            "notes": "LIBERO eye-in-hand; set intrinsics/extrinsics via calib_override",
        },
    }


def default_coordinate_frames() -> dict[str, Any]:
    """座標系の宣言（親子関係のみ。数値変換は後段で差し込み可）。"""
    return {
        "world": {
            "description": "MuJoCo / LIBERO world frame",
            "parent": None,
        },
        "robot_base": {
            "description": "Franka Panda base",
            "parent": "world",
        },
        "eef": {
            "description": "end-effector (OSC pose frame)",
            "parent": "robot_base",
        },
        "cam_front": {
            "description": "agentview camera",
            "parent": "world",
        },
        "cam_wrist": {
            "description": "wrist / eye-in-hand camera",
            "parent": "eef",
        },
    }


def build_collection_info(
    *,
    fps: int = 20,
    robot_type: str = "panda",
    backend: str = "libero_sim",
    image_size: tuple[int, int] = (256, 256),
    render_size: tuple[int, int] = (128, 128),
    operator_id: str = "",
    device_id: str = "",
    location: str = "",
    suite: str = "",
    calib_override: Mapping[str, Any] | None = None,
    calib_override_path: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """collection_info.json 用の dict を組み立てる。"""
    now = datetime.now(timezone.utc).isoformat()
    info: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "backend": backend,
        "fps": int(fps),
        "robot_type": robot_type,
        "suite": suite,
        "sync_policy": "approximate_time",
        "frames": default_coordinate_frames(),
        "cameras": default_libero_sim_cameras(
            image_size=image_size,
            render_size=render_size,
        ),
        "collection": {
            "operator_id": operator_id,
            "device_id": device_id,
            "location": location,
            "created_at": now,
            "updated_at": now,
            "timezone": "UTC",
        },
        "calib_source": "builtin_libero_sim",
        "calib_override_path": calib_override_path,
    }
    if calib_override:
        info = merge_calib_override(info, calib_override)
        info["calib_source"] = "override"
    if extra:
        for key, value in extra.items():
            if key in {"cameras", "frames", "collection"} and isinstance(value, dict):
                info[key] = _deep_merge(dict(info.get(key) or {}), value)
            else:
                info[key] = value
    return info


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """dict を再帰マージする（override 優先）。"""
    out = deepcopy(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, Mapping):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def merge_calib_override(
    info: dict[str, Any],
    override: Mapping[str, Any],
) -> dict[str, Any]:
    """キャリブ上書きを cameras / frames にマージする。"""
    merged = deepcopy(info)
    if "cameras" in override and isinstance(override["cameras"], Mapping):
        merged["cameras"] = _deep_merge(
            dict(merged.get("cameras") or {}),
            override["cameras"],
        )
    if "frames" in override and isinstance(override["frames"], Mapping):
        merged["frames"] = _deep_merge(
            dict(merged.get("frames") or {}),
            override["frames"],
        )
    # ルートに intrinsics を直接置いた場合は front に当てる（簡易）
    for cam_key in ("front", "wrist"):
        if cam_key in override and isinstance(override[cam_key], Mapping):
            cams = dict(merged.get("cameras") or {})
            cams[cam_key] = _deep_merge(dict(cams.get(cam_key) or {}), override[cam_key])
            merged["cameras"] = cams
    return merged


def load_calib_override(path: str | Path) -> dict[str, Any]:
    """キャリブ上書き JSON を読む。"""
    p = Path(path).expanduser().resolve()
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"calib override must be a JSON object: {p}")
    return raw


def write_collection_info(root: Path, info: dict[str, Any]) -> Path:
    """`meta/collection_info.json` を書く（既存があれば updated_at だけ更新マージ）。"""
    meta = Path(root) / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    path = meta / COLLECTION_INFO_NAME
    payload = deepcopy(info)
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                # 収集メタの created_at は初回を保持
                created = (existing.get("collection") or {}).get("created_at")
                payload = _deep_merge(existing, payload)
                if created and isinstance(payload.get("collection"), dict):
                    payload["collection"]["created_at"] = created
        except json.JSONDecodeError:
            pass
    if isinstance(payload.get("collection"), dict):
        payload["collection"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_collection_info(root: Path) -> dict[str, Any]:
    """collection_info.json を読む。"""
    path = Path(root) / "meta" / COLLECTION_INFO_NAME
    if not path.is_file():
        raise FileNotFoundError(f"missing collection_info: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"collection_info must be object: {path}")
    return raw
