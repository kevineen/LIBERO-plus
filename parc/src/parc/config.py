"""YAML 実験設定の読み込み。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from parc.paths import PARC_ROOT


def load_yaml(path: str | Path) -> dict[str, Any]:
    """任意 YAML を dict で返す。"""
    p = Path(path)
    if not p.is_absolute():
        # まず cwd、次に parc ルート相対
        candidates = [Path.cwd() / p, PARC_ROOT / p]
        for c in candidates:
            if c.is_file():
                p = c
                break
    with p.open() as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {p}")
    data["_config_path"] = str(p.resolve())
    return data


def deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """ネストした dict を上書きマージする。"""
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_update(out[k], v)
        else:
            out[k] = v
    return out
