"""Thin wrappers around parc-enqueue / parc-queue / parc-worker."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from exp_orchestrator.expand import load_sweep, resolve_sweep_path
from exp_orchestrator.paths import PARC_ROOT


def _uv_run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a parc CLI via uv from the parc root."""
    cmd = ["uv", "run", *args]
    proc = subprocess.run(
        cmd,
        cwd=str(PARC_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"{' '.join(cmd)} failed ({proc.returncode})\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
    return proc


def enqueue_parc_sweep(
    sweep_path: str | Path,
    *,
    notes: str = "",
    notify: bool = False,
) -> list[str]:
    """Enqueue a parc-format sweep. Returns job ids when printed by parc."""
    resolved = resolve_sweep_path(sweep_path)
    sweep = load_sweep(resolved)
    if str(sweep.get("kind", "parc")) != "parc":
        raise ValueError(f"{resolved} is kind={sweep.get('kind')}, expected parc")
    argv = ["parc-enqueue", "--sweep", str(resolved)]
    if notes or sweep.get("notes"):
        argv.extend(["--notes", notes or str(sweep.get("notes"))])
    if notify:
        argv.append("--notify")
    proc = _uv_run(argv)
    print(proc.stdout)
    job_ids: list[str] = []
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("q_") or stripped.startswith("job_"):
            job_ids.append(stripped.split()[0])
        elif stripped.startswith("{") and "job_id" in stripped:
            try:
                payload = json.loads(stripped)
                if "job_id" in payload:
                    job_ids.append(str(payload["job_id"]))
            except json.JSONDecodeError:
                pass
    return job_ids


def queue_status(*, limit: int = 30) -> dict[str, Any] | str:
    """Return parc-queue status JSON when possible."""
    proc = _uv_run(["parc-queue", "status", "--limit", str(limit), "--json"], check=False)
    if proc.returncode != 0:
        return proc.stdout + proc.stderr
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.stdout


def pause_job(job_id: str) -> str:
    """Pause a running parc job (keeps checkpoints)."""
    proc = _uv_run(["parc-queue", "cancel", job_id])
    return proc.stdout


def resume_run(run_id: str, *, mode: str = "auto") -> str:
    """Resume a parc run from its latest checkpoint."""
    proc = _uv_run(["parc-queue", "resume", run_id, "--mode", mode])
    return proc.stdout


def requeue_job(job_id: str) -> str:
    """Requeue a failed/cancelled parc job, preferring resume."""
    proc = _uv_run(["parc-queue", "requeue", job_id])
    return proc.stdout


def start_worker(*, loop: bool = True, poll_sec: float = 30.0) -> subprocess.Popen[str]:
    """Start parc-worker in this process's child (caller manages lifetime)."""
    argv = ["uv", "run", "parc-worker"]
    if loop:
        argv.extend(["--loop", "--poll-sec", str(poll_sec)])
    else:
        argv.append("--once")
    return subprocess.Popen(
        argv,
        cwd=str(PARC_ROOT),
        text=True,
    )
