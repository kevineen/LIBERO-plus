"""Repository and output paths for the experiment orchestrator."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
# notebooks/lib/exp_orchestrator -> notebooks
NOTEBOOKS_DIR = PACKAGE_DIR.parent.parent
REPO_ROOT = NOTEBOOKS_DIR.parent
PARC_ROOT = REPO_ROOT / "parc"
SWEEPS_DIR = NOTEBOOKS_DIR / "experiments" / "sweeps"
RUNS_DIR = NOTEBOOKS_DIR / "runs"
RESULTS_DB = RUNS_DIR / "results.sqlite"
LIFELONG_RUNS_DIR = RUNS_DIR / "lifelong"


def default_python() -> Path:
    """Prefer the repo venv interpreter when present."""
    candidates = [
        REPO_ROOT / ".venv" / "bin" / "python",
        PARC_ROOT / ".venv" / "bin" / "python",
    ]
    for path in candidates:
        if path.is_file():
            return path
    import sys

    return Path(sys.executable)
