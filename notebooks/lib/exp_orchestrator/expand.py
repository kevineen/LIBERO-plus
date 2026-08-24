"""Expand sweep YAML into trial dicts (parc-compatible + lifelong)."""

from __future__ import annotations

import copy
import itertools
import random
from pathlib import Path
from typing import Any

import yaml

from exp_orchestrator.paths import PARC_ROOT, REPO_ROOT, SWEEPS_DIR


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a mapping YAML file."""
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML must be a mapping: {path}")
    return data


def resolve_sweep_path(raw: str | Path) -> Path:
    """Resolve a sweep path from cwd, notebooks/experiments/sweeps, or repo root."""
    path = Path(raw)
    if path.is_file():
        return path.resolve()
    candidates = [
        Path.cwd() / path,
        SWEEPS_DIR / path,
        REPO_ROOT / path,
        PARC_ROOT / path,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"Sweep YAML not found: {raw}")


def _count_axes(search: dict[str, Any]) -> int:
    return sum(1 for value in search.values() if isinstance(value, list) and value)


def expand_search(
    search: dict[str, Any],
    *,
    mode: str = "grid",
    max_jobs: int = 20,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Cartesian or random combinations of search axes."""
    keys = [key for key, value in search.items() if isinstance(value, list) and value]
    if not keys:
        return [{}]
    trials: list[dict[str, Any]] = []
    if mode == "random":
        rng = random.Random(seed)
        for _ in range(max_jobs):
            trials.append({key: rng.choice(search[key]) for key in keys})
        return trials
    values = [search[key] for key in keys]
    for combo in itertools.product(*values):
        trials.append(dict(zip(keys, combo, strict=True)))
        if len(trials) >= max_jobs:
            break
    return trials


def load_sweep(path: str | Path) -> dict[str, Any]:
    """Load and normalize a sweep document."""
    sweep_path = resolve_sweep_path(path)
    sweep = load_yaml(sweep_path)
    sweep["_source"] = str(sweep_path)
    sweep.setdefault("kind", "parc")
    sweep.setdefault("mode", "grid")
    sweep.setdefault("max_jobs", 20)
    sweep.setdefault("search", {})
    n_axes = _count_axes(dict(sweep.get("search") or {}))
    kind = str(sweep["kind"])
    if kind == "parc" and n_axes > 2:
        raise ValueError(
            f"parc sweeps may vary at most 2 axes (got {n_axes}). Split the sweep."
        )
    return sweep


def expand_lifelong_trials(sweep: dict[str, Any]) -> list[dict[str, Any]]:
    """Build Hydra override lists for lifelong trials."""
    defaults = dict(sweep.get("defaults") or {})
    search = dict(sweep.get("search") or {})
    combos = expand_search(
        search,
        mode=str(sweep.get("mode", "grid")),
        max_jobs=int(sweep.get("max_jobs", 20)),
        seed=int(sweep.get("seed", 42)),
    )
    sweep_id = str(sweep.get("name") or "lifelong")
    trials: list[dict[str, Any]] = []
    for index, overrides in enumerate(combos):
        merged = copy.deepcopy(defaults)
        merged.update(overrides)
        hydra_overrides = [f"{key}={value}" for key, value in merged.items()]
        trial_id = f"{sweep_id}_t{index:03d}"
        trials.append(
            {
                "trial_id": trial_id,
                "sweep_id": sweep_id,
                "trial_index": index,
                "overrides": merged,
                "hydra_overrides": hydra_overrides,
            }
        )
    return trials
