"""再現性メタ（git / config hash / eval fingerprint）。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

from parc.paths import PARC_ROOT, get_paths


def git_info(repo: Path | None = None) -> dict[str, Any]:
    """git SHA と dirty フラグ。git が無い場合は空。"""
    root = repo or PARC_ROOT
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=str(root),
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        )
        return {"git_sha": sha, "git_dirty": dirty}
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return {"git_sha": "", "git_dirty": False}


def config_hash(config: dict[str, Any]) -> str:
    """設定の安定ハッシュ（_ 始まりキー除外）。"""
    cleaned = {k: v for k, v in config.items() if not str(k).startswith("_")}
    blob = json.dumps(cleaned, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def eval_fingerprint(config: dict[str, Any]) -> str:
    """比較用 eval サブセットの指紋。"""
    ev = dict(config.get("eval") or {})
    keys = (
        "suite",
        "task_ids",
        "tasks_per_category",
        "num_trials_per_task",
        "max_steps",
        "camera_height",
        "camera_width",
    )
    subset = {k: ev.get(k) for k in keys}
    blob = json.dumps(subset, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def env_fingerprint() -> str:
    """短い実行環境指紋。"""
    parts = [
        f"hf={os.environ.get('HF_HOME', '')}",
        f"mujoco_gl={os.environ.get('MUJOCO_GL', '')}",
        f"cuda_visible={os.environ.get('CUDA_VISIBLE_DEVICES', '')}",
        f"exp={get_paths()['experiments_dir']}",
    ]
    blob = "|".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def build_repro_fields(
    config: dict[str, Any],
    *,
    sweep_id: str = "",
    trial_index: int | None = None,
    parent_run_id: str = "",
) -> dict[str, Any]:
    """create_run / worker が meta に載せる再現性フィールド。"""
    gi = git_info()
    return {
        "git_sha": gi["git_sha"],
        "git_dirty": gi["git_dirty"],
        "config_hash": config_hash(config),
        "eval_fingerprint": eval_fingerprint(config),
        "env_fingerprint": env_fingerprint(),
        "sweep_id": sweep_id or str(config.get("sweep_id") or ""),
        "trial_index": trial_index
        if trial_index is not None
        else config.get("trial_index"),
        "parent_run_id": parent_run_id or str(config.get("parent_run_id") or ""),
        "seed": int(config.get("seed", 0)),
    }


def dump_resolved_config(path: Path, config: dict[str, Any]) -> None:
    """展開後設定を YAML で保存する。"""
    cleaned = {k: v for k, v in config.items() if not str(k).startswith("_")}
    path.write_text(
        yaml.safe_dump(cleaned, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
