"""注視マップ（活性化 / Grad-CAM）のオーバーレイユーティリティ。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from parc.eval.media import save_frame_png, write_mp4


def normalize_map(heatmap: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """ヒートマップを [0, 1] に正規化する。"""
    h = np.asarray(heatmap, dtype=np.float32)
    h = np.nan_to_num(h, nan=0.0, posinf=0.0, neginf=0.0)
    h = np.maximum(h, 0.0)
    lo = float(h.min())
    hi = float(h.max())
    if hi - lo < eps:
        return np.zeros_like(h, dtype=np.float32)
    return ((h - lo) / (hi - lo)).astype(np.float32)


def tokens_to_spatial_map(tokens: np.ndarray) -> np.ndarray:
    """Vision token 列 (N, C) または (N,) を空間マップ (H, W) にする。

    N が平方数なら sqrt グリッド。そうでなければ 1 行に並べる。
    """
    arr = np.asarray(tokens, dtype=np.float32)
    if arr.ndim == 3:
        # (B, N, C) → 先頭バッチのみ
        arr = arr[0]
    if arr.ndim == 2:
        # channel L2 → (N,)
        arr = np.linalg.norm(arr, axis=-1)
    if arr.ndim != 1:
        raise ValueError(f"expected 1D/2D/3D token map, got shape {arr.shape}")

    n = int(arr.shape[0])
    side = int(round(n**0.5))
    if side * side == n:
        return arr.reshape(side, side)
    # 非平方: 可能な限り近い矩形
    h = max(1, int(n**0.5))
    w = int(np.ceil(n / h))
    pad = h * w - n
    if pad:
        arr = np.pad(arr, (0, pad), mode="constant")
    return arr.reshape(h, w)


def upsample_map(heatmap: np.ndarray, height: int, width: int) -> np.ndarray:
    """最近傍→双線形に近い簡易リサイズ（Pillow があれば bilinear）。"""
    hmap = normalize_map(heatmap)
    if hmap.shape == (height, width):
        return hmap
    try:
        from PIL import Image

        img = Image.fromarray((hmap * 255.0).astype(np.uint8), mode="L")
        img = img.resize((width, height), resample=Image.BILINEAR)
        return (np.asarray(img, dtype=np.float32) / 255.0).astype(np.float32)
    except Exception:
        # フォールバック: 最近傍
        ys = (np.linspace(0, hmap.shape[0] - 1, height)).astype(np.int32)
        xs = (np.linspace(0, hmap.shape[1] - 1, width)).astype(np.int32)
        return hmap[ys][:, xs]


def jet_colormap(values: np.ndarray) -> np.ndarray:
    """[0,1] → RGB uint8（簡易 jet）。"""
    v = np.clip(np.asarray(values, dtype=np.float32), 0.0, 1.0)
    r = np.clip(1.5 - np.abs(4.0 * v - 3.0), 0.0, 1.0)
    g = np.clip(1.5 - np.abs(4.0 * v - 2.0), 0.0, 1.0)
    b = np.clip(1.5 - np.abs(4.0 * v - 1.0), 0.0, 1.0)
    rgb = np.stack([r, g, b], axis=-1)
    return (rgb * 255.0).astype(np.uint8)


def unflip_rgb(rgb: np.ndarray) -> np.ndarray:
    """180° 回転（方策入力 flip を env 向きに戻す）。"""
    return np.asarray(rgb)[::-1, ::-1].copy()


def overlay_heatmap(
    rgb: np.ndarray,
    heatmap: np.ndarray,
    *,
    alpha: float = 0.45,
    unflip_heatmap: bool = False,
) -> np.ndarray:
    """RGB にヒートマップを重ねる。

    ``unflip_heatmap=True`` のとき、マップは方策入力（180° flip）基準とみなし、
    env 向きの ``rgb`` に合わせるためマップも 180° 回転する。
    """
    img = np.asarray(rgb)
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    img = img[..., :3]
    h, w = img.shape[:2]

    heat = np.asarray(heatmap, dtype=np.float32)
    if unflip_heatmap:
        heat = heat[::-1, ::-1].copy()
    heat = upsample_map(heat, h, w)
    color = jet_colormap(heat)
    out = (
        (1.0 - alpha) * img.astype(np.float32) + alpha * color.astype(np.float32)
    ).astype(np.uint8)
    return out


def side_by_side(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """左右連結。高さが違う場合は小さい方をゼロパディング。"""
    a = np.asarray(left)[..., :3]
    b = np.asarray(right)[..., :3]
    if a.dtype != np.uint8:
        a = np.clip(a, 0, 255).astype(np.uint8)
    if b.dtype != np.uint8:
        b = np.clip(b, 0, 255).astype(np.uint8)
    ha, wa = a.shape[:2]
    hb, wb = b.shape[:2]
    h = max(ha, hb)
    if ha < h:
        pad = np.zeros((h - ha, wa, 3), dtype=np.uint8)
        a = np.concatenate([a, pad], axis=0)
    if hb < h:
        pad = np.zeros((h - hb, wb, 3), dtype=np.uint8)
        b = np.concatenate([b, pad], axis=0)
    return np.concatenate([a, b], axis=1)


def save_attention_media(
    out_dir: Path,
    *,
    frames: list[np.ndarray],
    stem: str,
    save_video: bool = True,
    save_frames: bool = False,
    max_frames: int = 60,
    fps: int = 10,
) -> dict[str, Any]:
    """注視オーバーレイ媒体を保存し、manifest 用 dict を返す。"""
    info: dict[str, Any] = {"stem": stem, "n_attention_captured": len(frames)}
    if not frames:
        return info

    sampled = frames[: max(1, max_frames)]
    attn_stem = f"{stem}_attn"

    if save_frames:
        frame_dir = out_dir / attn_stem
        for i, fr in enumerate(sampled):
            save_frame_png(frame_dir / f"frame_{i:04d}.png", fr)
        info["attention_frames_dir"] = str(frame_dir)
        info["n_attention_frames_saved"] = len(sampled)

    if save_video:
        mp4 = out_dir / f"{attn_stem}.mp4"
        ok = write_mp4(mp4, sampled, fps=fps)
        if ok:
            info["attention_video"] = str(mp4)
        elif not save_frames:
            frame_dir = out_dir / attn_stem
            for i, fr in enumerate(sampled):
                save_frame_png(frame_dir / f"frame_{i:04d}.png", fr)
            info["attention_frames_dir"] = str(frame_dir)
            info["attention_video_fallback"] = "png_sequence"

    return info
