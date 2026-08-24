"""SQLite store for trial scores and lifecycle state."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from exp_orchestrator.paths import RESULTS_DB, RUNS_DIR


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open the results database, creating tables if needed."""
    path = db_path or RESULTS_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trials (
            trial_id TEXT PRIMARY KEY,
            sweep_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            trial_index INTEGER,
            status TEXT NOT NULL,
            stage TEXT,
            run_id TEXT,
            job_id TEXT,
            score REAL,
            n_episodes INTEGER,
            metrics_json TEXT,
            overrides_json TEXT,
            resume_path TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def upsert_trial(
    conn: sqlite3.Connection,
    *,
    trial_id: str,
    sweep_id: str,
    kind: str,
    trial_index: int | None = None,
    status: str = "created",
    stage: str | None = None,
    run_id: str | None = None,
    job_id: str | None = None,
    score: float | None = None,
    n_episodes: int | None = None,
    metrics: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
    resume_path: str | None = None,
    notes: str | None = None,
) -> None:
    """Insert or update one trial row."""
    conn.execute(
        """
        INSERT INTO trials (
            trial_id, sweep_id, kind, trial_index, status, stage, run_id, job_id,
            score, n_episodes, metrics_json, overrides_json, resume_path, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(trial_id) DO UPDATE SET
            sweep_id=excluded.sweep_id,
            kind=excluded.kind,
            trial_index=COALESCE(excluded.trial_index, trials.trial_index),
            status=excluded.status,
            stage=COALESCE(excluded.stage, trials.stage),
            run_id=COALESCE(excluded.run_id, trials.run_id),
            job_id=COALESCE(excluded.job_id, trials.job_id),
            score=COALESCE(excluded.score, trials.score),
            n_episodes=COALESCE(excluded.n_episodes, trials.n_episodes),
            metrics_json=COALESCE(excluded.metrics_json, trials.metrics_json),
            overrides_json=COALESCE(excluded.overrides_json, trials.overrides_json),
            resume_path=COALESCE(excluded.resume_path, trials.resume_path),
            notes=COALESCE(excluded.notes, trials.notes),
            updated_at=excluded.updated_at
        """,
        (
            trial_id,
            sweep_id,
            kind,
            trial_index,
            status,
            stage,
            run_id,
            job_id,
            score,
            n_episodes,
            json.dumps(metrics, ensure_ascii=False) if metrics is not None else None,
            json.dumps(overrides, ensure_ascii=False) if overrides is not None else None,
            resume_path,
            notes,
            _utc_now(),
        ),
    )
    conn.commit()


def list_trials(
    conn: sqlite3.Connection,
    *,
    sweep_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return trial rows, newest first."""
    if sweep_id:
        rows = conn.execute(
            "SELECT * FROM trials WHERE sweep_id = ? ORDER BY updated_at DESC",
            (sweep_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM trials ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def ranking(
    conn: sqlite3.Connection,
    *,
    sweep_id: str | None = None,
) -> list[dict[str, Any]]:
    """Trials with scores, highest first."""
    if sweep_id:
        rows = conn.execute(
            """
            SELECT * FROM trials
            WHERE score IS NOT NULL AND sweep_id = ?
            ORDER BY score DESC
            """,
            (sweep_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM trials WHERE score IS NOT NULL ORDER BY score DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def ensure_runs_dir() -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return RUNS_DIR
