"""Unit tests for sweep expand and SQLite trial storage."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_PARENT = Path(__file__).resolve().parents[1]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from exp_orchestrator.db import connect, ranking, upsert_trial
from exp_orchestrator.expand import expand_lifelong_trials, expand_search, load_sweep


def test_expand_search_grid_caps() -> None:
    trials = expand_search(
        {"seed": [1, 2], "train.steps": [10, 20]},
        mode="grid",
        max_jobs=3,
    )
    assert len(trials) == 3
    assert trials[0] == {"seed": 1, "train.steps": 10}


def test_lifelong_expand_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "ll.yaml"
    path.write_text(
        """
name: unit_ll
kind: lifelong
max_jobs: 4
defaults:
  benchmark_name: LIBERO_SPATIAL
search:
  seed: [1, 2]
  policy: [bc_transformer_policy]
""",
        encoding="utf-8",
    )
    sweep = load_sweep(path)
    trials = expand_lifelong_trials(sweep)
    assert len(trials) == 2
    assert trials[0]["trial_id"] == "unit_ll_t000"
    assert "seed=1" in trials[0]["hydra_overrides"]


def test_sqlite_ranking(tmp_path: Path) -> None:
    db = tmp_path / "results.sqlite"
    conn = connect(db)
    upsert_trial(
        conn,
        trial_id="a",
        sweep_id="s",
        kind="parc",
        status="done",
        score=0.2,
    )
    upsert_trial(
        conn,
        trial_id="b",
        sweep_id="s",
        kind="parc",
        status="done",
        score=0.9,
    )
    rows = ranking(conn, sweep_id="s")
    assert rows[0]["trial_id"] == "b"
    conn.close()


if __name__ == "__main__":
    test_expand_search_grid_caps()
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp:
        test_lifelong_expand_from_yaml(Path(tmp))
        test_sqlite_ranking(Path(tmp) / "db")
    print("ok")
