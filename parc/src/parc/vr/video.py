"""RGB 画像 → JPEG バイト。"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image


def rgb_to_jpeg(rgb: np.ndarray, *, quality: int = 70) -> bytes:
    """(H,W,3) uint8 → JPEG bytes。"""
    arr = np.asarray(rgb)
    if arr.ndim != 3 or arr.shape[-1] != 3:
        raise ValueError(f"expected HxWx3, got {arr.shape}")
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    quality = int(np.clip(quality, 1, 95))
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
