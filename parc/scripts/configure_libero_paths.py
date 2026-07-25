#!/usr/bin/env python3
"""~/.libero/config.yaml をこの LIBERO-plus リポジトリに向ける。"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIBERO_PKG = ROOT / "libero" / "libero"
CONFIG_DIR = Path(os.environ.get("LIBERO_CONFIG_PATH", Path.home() / ".libero"))
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def main() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cfg = {
        "benchmark_root": str(LIBERO_PKG),
        "bddl_files": str(LIBERO_PKG / "bddl_files"),
        "init_states": str(LIBERO_PKG / "init_files"),
        "datasets": str(ROOT / "parc" / "data" / "datasets"),
        "assets": str(LIBERO_PKG / "assets"),
    }
    if CONFIG_FILE.is_file():
        backup = CONFIG_FILE.with_suffix(".yaml.bak")
        backup.write_text(CONFIG_FILE.read_text())
        print(f"[parc] backed up existing config → {backup}")

    CONFIG_FILE.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"[parc] wrote {CONFIG_FILE}")
    for k, v in cfg.items():
        exists = Path(v).exists()
        print(f"  {k}: {v}  [{'OK' if exists else 'MISSING'}]")


if __name__ == "__main__":
    main()
