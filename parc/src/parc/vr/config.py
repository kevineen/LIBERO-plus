"""VR teleop 用 YAML 設定の読み込み。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from parc.paths import PARC_ROOT


def load_vr_config(path: str | Path) -> dict[str, Any]:
    """VR teleop 設定 YAML を辞書として返す。"""
    cfg_path = Path(path).expanduser()
    if not cfg_path.is_absolute():
        cfg_path = (PARC_ROOT / cfg_path).resolve()
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"VR config must be a mapping: {cfg_path}")
    raw["_config_path"] = str(cfg_path)
    return raw
