"""Collect parc metrics.json and lifelong result.pt into SQLite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exp_orchestrator.db import connect, list_trials, ranking, upsert_trial
from exp_orchestrator.paths import LIFELONG_RUNS_DIR, PARC_ROOT


def _parc_experiments_dir() -> Path:
    """Best-effort experiments directory (default parc/experiments)."""
    override = PARC_ROOT / "configs" / "paths.yaml"
    if override.is_file():
        try:
            import yaml

            data = yaml.safe_load(override.read_text(encoding="utf-8")) or {}
            raw = (data.get("paths") or {}).get("experiments_dir")
            if raw:
                path = Path(str(raw)).expanduser()
                if not path.is_absolute():
                    path = PARC_ROOT / path
                return path
        except Exception:
            pass
    return PARC_ROOT / "experiments"


def collect_parc_runs(*, sweep_id: str | None = None) -> int:
    """Scan parc registry + metrics.json and upsert scores."""
    exp_dir = _parc_experiments_dir()
    registry = exp_dir / "registry.jsonl"
    if not registry.is_file():
        return 0
    conn = connect()
    count = 0
    latest: dict[str, dict[str, Any]] = {}
    with registry.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            run_id = str(row.get("run_id") or "")
            if not run_id:
                continue
            latest[run_id] = row
    try:
        for run_id, row in latest.items():
            sid = str(row.get("sweep_id") or "")
            if sweep_id and sid != sweep_id:
                continue
            if not sid:
                continue
            run_dir = exp_dir / run_id
            metrics_path = run_dir / "metrics.json"
            metrics: dict[str, Any] = {}
            score = None
            n_episodes = None
            if metrics_path.is_file():
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                if metrics.get("success_rate") is not None:
                    score = float(metrics["success_rate"])
                if metrics.get("n_episodes") is not None:
                    n_episodes = int(metrics["n_episodes"])
            overrides = {}
            cfg_path = run_dir / "config.yaml"
            if cfg_path.is_file():
                try:
                    import yaml

                    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
                    overrides = {
                        "name": cfg.get("name"),
                        "seed": cfg.get("seed"),
                        "train": cfg.get("train"),
                    }
                except Exception:
                    overrides = {}
            trial_index = row.get("trial_index")
            trial_id = f"{sid}_t{int(trial_index):03d}" if trial_index is not None else run_id
            upsert_trial(
                conn,
                trial_id=str(trial_id),
                sweep_id=sid,
                kind="parc",
                trial_index=int(trial_index) if trial_index is not None else None,
                status=str(row.get("status") or "unknown"),
                stage="eval" if score is not None else str(row.get("status") or ""),
                run_id=run_id,
                score=score,
                n_episodes=n_episodes,
                metrics=metrics or None,
                overrides=overrides or None,
                notes=str(row.get("notes") or ""),
            )
            count += 1
    finally:
        conn.close()
    return count


def collect_lifelong_runs(*, sweep_id: str | None = None) -> int:
    """Read lifelong state.json files into the DB."""
    if not LIFELONG_RUNS_DIR.is_dir():
        return 0
    conn = connect()
    count = 0
    try:
        for state_path in LIFELONG_RUNS_DIR.glob("*/state.json"):
            state = json.loads(state_path.read_text(encoding="utf-8"))
            sid = str(state.get("sweep_id") or "")
            if sweep_id and sid != sweep_id:
                continue
            trial_id = str(state.get("trial_id") or state_path.parent.name)
            upsert_trial(
                conn,
                trial_id=trial_id,
                sweep_id=sid or trial_id,
                kind="lifelong",
                status=str(state.get("status") or "unknown"),
                stage=str(state.get("stage") or ""),
                run_id=str(state.get("experiment_dir") or ""),
                score=state.get("score"),
                n_episodes=state.get("n_episodes"),
                metrics=state.get("metrics") if isinstance(state.get("metrics"), dict) else None,
                resume_path=str(state.get("resume_path") or ""),
                notes=str(state.get("notes") or ""),
            )
            count += 1
    finally:
        conn.close()
    return count


def collect_all(*, sweep_id: str | None = None) -> dict[str, int]:
    """Collect both backends and return counts."""
    return {
        "parc": collect_parc_runs(sweep_id=sweep_id),
        "lifelong": collect_lifelong_runs(sweep_id=sweep_id),
    }


def print_ranking(*, sweep_id: str | None = None) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = ranking(conn, sweep_id=sweep_id)
    finally:
        conn.close()
    if not rows:
        print("No scored trials yet.")
        return []
    print(f"{'trial_id':40} {'kind':10} {'score':>8}  status")
    for row in rows:
        score = row.get("score")
        score_s = f"{score:.3f}" if isinstance(score, (int, float)) else "-"
        print(f"{row['trial_id'][:40]:40} {row['kind']:10} {score_s:>8}  {row['status']}")
    return rows


def print_status(*, sweep_id: str | None = None) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = list_trials(conn, sweep_id=sweep_id)
    finally:
        conn.close()
    if not rows:
        print("No trials in DB. Run collect after enqueue/worker.")
        return []
    print(f"{'trial_id':40} {'kind':10} {'status':10} {'score'}")
    for row in rows:
        score = row.get("score")
        score_s = f"{score:.3f}" if isinstance(score, (int, float)) else "-"
        print(f"{row['trial_id'][:40]:40} {row['kind']:10} {row['status']:10} {score_s}")
    return rows
