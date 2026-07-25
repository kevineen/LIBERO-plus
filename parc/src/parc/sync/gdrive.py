"""Google Drive へのベスト / 最新 ckpt アップロード（rclone 経由）。

認証は rclone 側で行う（サービスアカウントまたは OAuth）:

  rclone config          # remote 名は既定で gdrive
  # または
  export RCLONE_CONFIG_PASS=...

paths.yaml 例:

  sync:
    enabled: true
    backend: rclone
    rclone_remote: gdrive
    remote_root: PARC/ckpts
    upload_on_done: true
    only_if_best: true
    min_success_rate: 0.0
    include_training_state: false
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from parc.paths import PARC_ROOT, ensure_dotenv_loaded, get_machine_id, get_paths
from parc.tracking.run import list_registry


def _load_paths_yaml() -> dict[str, Any]:
    ensure_dotenv_loaded()
    path = PARC_ROOT / "configs" / "paths.yaml"
    if not path.is_file():
        example = PARC_ROOT / "configs" / "paths.example.yaml"
        if example.is_file():
            return yaml.safe_load(example.read_text()) or {}
        return {}
    return yaml.safe_load(path.read_text()) or {}


def get_sync_config() -> dict[str, Any]:
    """paths.yaml / 環境変数から sync 設定を返す。"""
    import os

    cfg = _load_paths_yaml().get("sync") or {}
    enabled = cfg.get("enabled", False)
    env_en = os.environ.get("PARC_SYNC_ENABLED")
    if env_en is not None:
        enabled = env_en.strip().lower() in {"1", "true", "yes", "on"}
    return {
        "enabled": bool(enabled),
        "backend": str(cfg.get("backend") or "rclone"),
        "rclone_remote": str(
            os.environ.get("PARC_RCLONE_REMOTE") or cfg.get("rclone_remote") or "gdrive"
        ),
        "remote_root": str(cfg.get("remote_root") or "PARC/ckpts").strip("/"),
        "upload_on_done": bool(cfg.get("upload_on_done", True)),
        "only_if_best": bool(cfg.get("only_if_best", True)),
        "min_success_rate": float(cfg.get("min_success_rate", 0.0)),
        "include_training_state": bool(cfg.get("include_training_state", False)),
    }


def rclone_available() -> bool:
    return shutil.which("rclone") is not None


def _latest_ckpt_dirs(run_dir: Path) -> tuple[Path | None, Path | None, str | None]:
    """(pretrained_model, training_state_or_None, step_name)."""
    root = run_dir / "train_output" / "checkpoints"
    if not root.is_dir():
        direct = run_dir / "train_output" / "pretrained_model"
        if direct.is_dir():
            return direct, None, "pretrained_model"
        return None, None, None
    steps: list[tuple[int, Path]] = []
    for p in root.iterdir():
        if not p.is_dir() or p.name == "last":
            continue
        model = p / "pretrained_model"
        if not model.is_dir():
            continue
        try:
            steps.append((int(p.name), p))
        except ValueError:
            steps.append((0, p))
    if not steps:
        return None, None, None
    steps.sort(key=lambda x: x[0])
    step_dir = steps[-1][1]
    ts = step_dir / "training_state"
    return step_dir / "pretrained_model", (ts if ts.is_dir() else None), step_dir.name


def _success_rate_for_run(run_id: str) -> float | None:
    for row in list_registry(limit=None):
        if row.run_id == run_id:
            m = row.metrics or {}
            if "success_rate" in m and m["success_rate"] is not None:
                try:
                    return float(m["success_rate"])
                except (TypeError, ValueError):
                    return None
            break
    # metrics.json fallback
    p = get_paths()["experiments_dir"] / run_id / "metrics.json"
    if p.is_file():
        try:
            m = json.loads(p.read_text())
            if m.get("success_rate") is not None:
                return float(m["success_rate"])
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
    return None


def _is_best_local(run_id: str, sr: float | None) -> bool:
    if sr is None:
        return False
    best = sr
    for row in list_registry(limit=None):
        m = row.metrics or {}
        if "success_rate" not in m or m["success_rate"] is None:
            continue
        try:
            best = max(best, float(m["success_rate"]))
        except (TypeError, ValueError):
            continue
    return sr >= best - 1e-12


def upload_run_checkpoint(
    run_id: str,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """run の最新 pretrained_model を rclone で Google Drive へ送る。"""
    cfg = get_sync_config()
    if not force and not cfg["enabled"]:
        return {"ok": False, "skipped": True, "reason": "sync.disabled"}
    if cfg["backend"] != "rclone":
        return {"ok": False, "error": f"unsupported backend: {cfg['backend']}"}
    if not rclone_available():
        return {
            "ok": False,
            "error": "rclone not found in PATH (install rclone and run `rclone config`)",
        }

    run_dir = get_paths()["experiments_dir"] / run_id
    if not run_dir.is_dir():
        return {"ok": False, "error": f"run not found: {run_id}"}

    model, training_state, step = _latest_ckpt_dirs(run_dir)
    if model is None:
        return {"ok": False, "error": f"no checkpoint in {run_id}"}

    sr = _success_rate_for_run(run_id)
    if not force:
        if sr is not None and sr < float(cfg["min_success_rate"]):
            return {
                "ok": False,
                "skipped": True,
                "reason": "below_min_success_rate",
                "success_rate": sr,
                "min_success_rate": cfg["min_success_rate"],
            }
        if cfg["only_if_best"] and not _is_best_local(run_id, sr):
            return {
                "ok": False,
                "skipped": True,
                "reason": "not_best_local",
                "success_rate": sr,
            }

    machine = get_machine_id()
    remote_base = (
        f"{cfg['rclone_remote']}:{cfg['remote_root']}/{machine}/{run_id}/{step or 'ckpt'}"
    )
    dest_model = f"{remote_base}/pretrained_model"
    cmds: list[list[str]] = [
        ["rclone", "copy", str(model), dest_model, "--progress", "--create-empty-src-dirs"],
    ]
    if cfg["include_training_state"] and training_state is not None:
        cmds.append(
            [
                "rclone",
                "copy",
                str(training_state),
                f"{remote_base}/training_state",
                "--progress",
                "--create-empty-src-dirs",
            ]
        )

    # メタを小さく同梱
    meta_payload = {
        "run_id": run_id,
        "machine_id": machine,
        "step": step,
        "success_rate": sr,
        "local_pretrained_model": str(model),
    }
    meta_local = run_dir / "logs" / "gdrive_upload_meta.json"
    meta_local.parent.mkdir(parents=True, exist_ok=True)
    meta_local.write_text(json.dumps(meta_payload, indent=2, ensure_ascii=False))
    cmds.append(["rclone", "copy", str(meta_local), remote_base, "--progress"])

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "remote_base": remote_base,
            "commands": [" ".join(c) for c in cmds],
            "meta": meta_payload,
        }

    logs: list[str] = []
    for cmd in cmds:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        logs.append((proc.stdout or "") + (proc.stderr or ""))
        if proc.returncode != 0:
            return {
                "ok": False,
                "error": f"rclone failed rc={proc.returncode}",
                "log": logs[-1][-4000:],
                "remote_base": remote_base,
            }
    return {
        "ok": True,
        "remote_base": remote_base,
        "meta": meta_payload,
        "log_tail": (logs[-1] if logs else "")[-2000:],
    }


def maybe_upload_after_job(result: dict[str, Any], *, run_id: str | None) -> dict[str, Any]:
    """ジョブ完了後フック。成功 + upload_on_done のときだけ試行。"""
    cfg = get_sync_config()
    if not cfg["enabled"] or not cfg["upload_on_done"]:
        return {"ok": False, "skipped": True, "reason": "disabled_or_off"}
    if result.get("status") != "done":
        return {"ok": False, "skipped": True, "reason": "job_not_done"}
    rid = run_id or result.get("run_id")
    if not rid:
        return {"ok": False, "skipped": True, "reason": "no_run_id"}
    return upload_run_checkpoint(str(rid), force=False)
