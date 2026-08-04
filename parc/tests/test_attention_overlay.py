"""注視マップオーバーレイの単体テスト（モデル不要）。"""

from __future__ import annotations

import numpy as np

from parc.eval.attention import (
    jet_colormap,
    normalize_map,
    overlay_heatmap,
    side_by_side,
    tokens_to_spatial_map,
    unflip_rgb,
    upsample_map,
)


def test_tokens_to_spatial_map_square() -> None:
    tokens = np.arange(16, dtype=np.float32).reshape(16, 1)
    m = tokens_to_spatial_map(tokens)
    assert m.shape == (4, 4)


def test_normalize_and_upsample() -> None:
    m = np.array([[0.0, 2.0], [1.0, 3.0]], dtype=np.float32)
    n = normalize_map(m)
    assert float(n.min()) == 0.0
    assert float(n.max()) == 1.0
    up = upsample_map(n, 8, 8)
    assert up.shape == (8, 8)


def test_overlay_unflip_matches_env_orientation() -> None:
    # env RGB: 黒背景
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    # 方策入力は 180° flip 済みなので、左上ホットなマップは flip 後の右下に相当
    heat_policy = np.zeros((2, 2), dtype=np.float32)
    heat_policy[0, 0] = 1.0  # flip 空間の左上 = env の右下
    over = overlay_heatmap(rgb, heat_policy, alpha=1.0, unflip_heatmap=True)
    assert over.shape == (4, 4, 3)
    # jet(1) は赤寄り、jet(0) は青寄り
    assert int(over[3, 3, 0]) > int(over[0, 0, 0])
    assert int(over[3, 3, 2]) < int(over[0, 0, 2])


def test_unflip_and_side_by_side() -> None:
    rgb = np.arange(3 * 2 * 2, dtype=np.uint8).reshape(2, 2, 3)
    flipped = unflip_rgb(rgb)
    assert flipped.shape == rgb.shape
    assert not np.array_equal(flipped, rgb)
    combo = side_by_side(rgb, flipped)
    assert combo.shape == (2, 4, 3)


def test_jet_colormap_range() -> None:
    c = jet_colormap(np.linspace(0, 1, 5))
    assert c.shape == (5, 3)
    assert c.dtype == np.uint8
