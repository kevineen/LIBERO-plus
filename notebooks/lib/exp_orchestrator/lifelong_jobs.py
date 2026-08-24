"""Run LIBERO lifelong trials with pause / resume via checkpoint files."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from exp_orchestrator.db import connect, upsert_trial
from exp_orchestrator.expand import expand_lifelong_trials, load_sweep
from exp_orchestrator.paths import LIFELONG_RUNS_DIR, REPO_ROOT, default_python


def _trial_dir(trial_id: str) -> Path:
    path = LIFELONG_RUNS_DIR / trial_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path(trial_id: str) -> Path:
    return _trial_dir(trial_id) / "state.json"


def read_state(trial_id: str) -> dict[str, Any]:
    path = _state_path(trial_id)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(trial_id: str, **fields: Any) -> dict[str, Any]:
    path = _state_path(trial_id)
    current = read_state(trial_id)
    current.update(fields)
    current["trial_id"] = trial_id
    current["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    return current


def _discover_experiment_dir(trial_dir: Path) -> Path | None:
    """Find the latest resume_latest.pth created under the repo or trial dir."""
    local = trial_dir / "resume_latest.pth"
    if local.is_file():
        return trial_dir
    search_roots = [trial_dir, REPO_ROOT / "experiments"]
    newest: tuple[float, Path] | None = None
    for root in search_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("resume_latest.pth"):
            mtime = path.stat().st_mtime
            if newest is None or mtime > newest[0]:
                newest = (mtime, path.parent)
    return newest[1] if newest else None


def _find_resume_ckpt(trial_id: str) -> Path | None:
    """Look for resume_latest.pth under the trial dir or recorded experiment_dir."""
    local = _trial_dir(trial_id) / "resume_latest.pth"
    if local.is_file():
        return local
    state = read_state(trial_id)
    exp = state.get("experiment_dir")
    if exp:
        candidate = Path(exp) / "resume_latest.pth"
        if candidate.is_file():
            return candidate
    discovered = _discover_experiment_dir(_trial_dir(trial_id))
    if discovered is not None:
        candidate = discovered / "resume_latest.pth"
        if candidate.is_file():
            return candidate
    return None


def _python() -> str:
    return str(default_python())


def build_lifelong_command(
    trial: dict[str, Any],
    *,
    resume: bool = False,
    resume_path: Path | None = None,
    hydra_output_dir: Path | None = None,
) -> list[str]:
    """Build python + Hydra CLI for libero.lifelong.main."""
    cmd = [
        _python(),
        str(REPO_ROOT / "libero" / "lifelong" / "main.py"),
        *trial["hydra_overrides"],
    ]
    if resume and resume_path is not None:
        cmd.extend(
            [
                "train.resume=true",
                f"train.resume_path={resume_path}",
            ]
        )
    else:
        cmd.append("train.resume=false")
    if hydra_output_dir is not None:
        # Keep Hydra run dirs next to the trial so pause/resume stay local.
        cmd.extend(
            [
                f"hydra.run.dir={hydra_output_dir / 'hydra'}",
            ]
        )
    return cmd


def _sync_db(trial: dict[str, Any], state: dict[str, Any]) -> None:
    conn = connect()
    try:
        upsert_trial(
            conn,
            trial_id=trial["trial_id"],
            sweep_id=trial["sweep_id"],
            kind="lifelong",
            trial_index=int(trial["trial_index"]),
            status=str(state.get("status", "created")),
            stage=str(state.get("stage", "train")),
            run_id=str(state.get("experiment_dir") or ""),
            score=state.get("score"),
            n_episodes=state.get("n_episodes"),
            metrics=state.get("metrics"),
            overrides=trial.get("overrides"),
            resume_path=state.get("resume_path"),
            notes=state.get("notes"),
        )
    finally:
        conn.close()


def run_lifelong_trial(
    trial: dict[str, Any],
    *,
    resume: bool = False,
) -> dict[str, Any]:
    """Run one lifelong trial as a subprocess; records pid for pause."""
    trial_id = trial["trial_id"]
    trial_dir = _trial_dir(trial_id)
    resume_ckpt = _find_resume_ckpt(trial_id) if resume else None
    use_resume = bool(resume and resume_ckpt is not None)
    cmd = build_lifelong_command(
        trial,
        resume=use_resume,
        resume_path=resume_ckpt,
        hydra_output_dir=trial_dir,
    )
    log_path = trial_dir / "train.log"
    pid_path = trial_dir / "job.pid"
    state = write_state(
        trial_id,
        status="running",
        stage="train",
        sweep_id=trial["sweep_id"],
        command=cmd,
        resume=use_resume,
        resume_path=str(resume_ckpt) if resume_ckpt else "",
        log_path=str(log_path),
    )
    _sync_db(trial, state)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    with log_path.open("a", encoding="utf-8") as log:
        log.write("\n$ " + " ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        pid_path.write_text(str(proc.pid), encoding="utf-8")
        write_state(trial_id, pid=proc.pid)
        returncode = proc.wait()

    if pid_path.is_file():
        pid_path.unlink()

    exp_dir = _discover_experiment_dir(trial_dir)
    if exp_dir is not None:
        write_state(trial_id, experiment_dir=str(exp_dir), resume_path=str(exp_dir / "resume_latest.pth"))

    latest = _find_resume_ckpt(trial_id)

    current = read_state(trial_id)
    if current.get("status") == "paused":
        _sync_db(trial, current)
        return current

    if returncode != 0:
        state = write_state(
            trial_id,
            status="failed",
            stage="failed",
            returncode=returncode,
            notes=f"lifelong exited {returncode}",
        )
        _sync_db(trial, state)
        raise RuntimeError(f"{trial_id} failed with rc={returncode}; see {log_path}")

    score = _extract_score(trial_id)
    state = write_state(
        trial_id,
        status="done",
        stage="done",
        returncode=0,
        score=score.get("score"),
        n_episodes=score.get("n_episodes"),
        metrics=score,
    )
    _sync_db(trial, state)
    return state


def pause_lifelong_trial(trial_id: str) -> dict[str, Any]:
    """SIGTERM the running process; keep resume_latest.pth."""
    state = read_state(trial_id)
    pid_path = _trial_dir(trial_id) / "job.pid"
    pid = state.get("pid")
    if pid_path.is_file():
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    if not pid:
        raise RuntimeError(f"no pid for {trial_id}")
    try:
        os.killpg(int(pid), signal.SIGTERM)
    except ProcessLookupError:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
    latest = _find_resume_ckpt(trial_id)
    state = write_state(
        trial_id,
        status="paused",
        stage="paused",
        resume_path=str(latest) if latest else state.get("resume_path", ""),
        notes="paused by user",
    )
    conn = connect()
    try:
        upsert_trial(
            conn,
            trial_id=trial_id,
            sweep_id=str(state.get("sweep_id") or trial_id),
            kind="lifelong",
            status="paused",
            stage="paused",
            resume_path=state.get("resume_path"),
        )
    finally:
        conn.close()
    return state


def run_lifelong_sweep(
    sweep_path: str,
    *,
    resume_paused: bool = True,
) -> list[dict[str, Any]]:
    """Run lifelong trials sequentially, skipping completed ones."""
    sweep = load_sweep(sweep_path)
    if str(sweep.get("kind")) != "lifelong":
        raise ValueError(f"expected kind=lifelong, got {sweep.get('kind')}")
    results: list[dict[str, Any]] = []
    for trial in expand_lifelong_trials(sweep):
        state = read_state(trial["trial_id"])
        status = state.get("status")
        if status == "done":
            results.append(state)
            continue
        resume = bool(resume_paused and status in {"paused", "failed", "running"})
        results.append(run_lifelong_trial(trial, resume=resume))
    return results


def _extract_score(trial_id: str) -> dict[str, Any]:
    """Pull a scalar success score from result.pt if present."""
    state = read_state(trial_id)
    exp_dir = state.get("experiment_dir")
    search_dirs = [_trial_dir(trial_id)]
    if exp_dir:
        search_dirs.insert(0, Path(exp_dir))
    result_pt = None
    for directory in search_dirs:
        candidate = directory / "result.pt"
        if candidate.is_file():
            result_pt = candidate
            break
        # Hydra may nest the experiment dir; search one level.
        if directory.is_dir():
            matches = list(directory.rglob("result.pt"))
            if matches:
                result_pt = matches[0]
                break
    if result_pt is None:
        return {"score": None, "source": None}
    try:
        import torch
    except ImportError:
        return {"score": None, "source": str(result_pt), "error": "torch missing"}
    blob = torch.load(result_pt, map_location="cpu")
    score = None
    if isinstance(blob, dict) and "S_conf_mat" in blob:
        matrix = blob["S_conf_mat"]
        try:
            import numpy as np

            arr = np.asarray(matrix)
            # Last trained-task row, mean over seen tasks (upper triangle-ish).
            last_row = arr[-1]
            nonzero = last_row[last_row != 0]
            score = float(nonzero.mean()) if nonzero.size else float(last_row.mean())
        except Exception:
            score = None
    return {
        "score": score,
        "source": str(result_pt),
        "n_episodes": None,
    }
