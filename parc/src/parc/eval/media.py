"""評価エピソードのフレーム／動画保存。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def extract_rgb(obs: dict[str, Any]) -> np.ndarray | None:
    """観測から agentview RGB を取る。"""
    for key in ("agentview_image", "agentview_rgb", "front"):
        if key in obs:
            arr = np.asarray(obs[key])
            if arr.ndim == 3 and arr.shape[-1] >= 3:
                return arr[..., :3]
    return None


def save_frame_png(path: Path, rgb: np.ndarray) -> None:
    """PNG 1 枚を書く（Pillow → imageio → 生 PPM の順でフォールバック）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = np.asarray(rgb)
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)

    try:
        from PIL import Image

        Image.fromarray(img).save(path)
        return
    except Exception:
        pass

    try:
        import imageio.v2 as imageio

        imageio.imwrite(path, img)
        return
    except Exception:
        pass

    # 最低限: PPM（ブラウザは読めないがデバッグ用）
    ppm = path.with_suffix(".ppm")
    h, w, _ = img.shape
    header = f"P6\n{w} {h}\n255\n".encode("ascii")
    ppm.write_bytes(header + img.tobytes())


def write_mp4(path: Path, frames: list[np.ndarray], fps: int = 10) -> bool:
    """可能なら mp4 を書く。失敗したら False。"""
    if not frames:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import imageio.v2 as imageio

        writer = imageio.get_writer(str(path), fps=fps, codec="libx264", quality=8)
        try:
            for fr in frames:
                arr = np.asarray(fr)
                if arr.dtype != np.uint8:
                    arr = np.clip(arr, 0, 255).astype(np.uint8)
                writer.append_data(arr)
        finally:
            writer.close()
        return path.is_file()
    except Exception:
        return False


def save_episode_media(
    out_dir: Path,
    *,
    frames: list[np.ndarray],
    stem: str,
    save_video: bool,
    save_frames: bool,
    frame_stride: int,
    max_frames: int,
    fps: int = 10,
) -> dict[str, Any]:
    """エピソード媒体を videos/ 配下に保存し、相対パス情報を返す。"""
    info: dict[str, Any] = {"stem": stem, "n_captured": len(frames)}
    if not frames:
        return info

    sampled = frames[:: max(1, frame_stride)][: max(1, max_frames)]

    if save_frames:
        frame_dir = out_dir / stem
        for i, fr in enumerate(sampled):
            p = frame_dir / f"frame_{i:04d}.png"
            save_frame_png(p, fr)
        info["frames_dir"] = str(frame_dir)
        info["n_frames_saved"] = len(sampled)

    if save_video:
        mp4 = out_dir / f"{stem}.mp4"
        ok = write_mp4(mp4, sampled, fps=fps)
        if ok:
            info["video"] = str(mp4)
        elif save_frames is False:
            # mp4 失敗時はフレームにフォールバック
            frame_dir = out_dir / stem
            for i, fr in enumerate(sampled):
                save_frame_png(frame_dir / f"frame_{i:04d}.png", fr)
            info["frames_dir"] = str(frame_dir)
            info["video_fallback"] = "png_sequence"

    return info
