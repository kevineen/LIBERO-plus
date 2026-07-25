"""スイープ YAML の展開。"""

from __future__ import annotations

import copy
import itertools
import random
from pathlib import Path
from typing import Any

import yaml

from parc.config import load_yaml
from parc.paths import PARC_ROOT


def _set_by_dot(cfg: dict[str, Any], dotted: str, value: Any) -> None:
    """a.b.c 形式でネスト代入する。"""
    parts = dotted.split(".")
    cur: dict[str, Any] = cfg
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _count_axes(search: dict[str, Any]) -> int:
    return sum(1 for v in search.values() if isinstance(v, list) and len(v) > 0)


def expand_sweep(sweep_path: str | Path) -> list[dict[str, Any]]:
    """スイープ定義から個別実験 config のリストを作る。

    1 ジョブで変える軸は最大 2（超過時は ValueError）。
    """
    path = Path(sweep_path)
    if not path.is_absolute():
        cand = PARC_ROOT / path
        path = cand if cand.is_file() else Path(sweep_path)
    with path.open() as f:
        sweep = yaml.safe_load(f) or {}
    if not isinstance(sweep, dict):
        raise ValueError(f"sweep must be mapping: {path}")

    base_path = sweep.get("base")
    if not base_path:
        raise ValueError("sweep.base is required")
    base = load_yaml(base_path)
    search: dict[str, Any] = dict(sweep.get("search") or {})
    n_axes = _count_axes(search)
    if n_axes > 2:
        raise ValueError(
            f"sweep may vary at most 2 axes at once (got {n_axes}). "
            "Split into multiple sweeps per docs/07 principle."
        )

    mode = str(sweep.get("mode", "grid"))
    max_jobs = int(sweep.get("max_jobs", 20))
    seed = int(sweep.get("seed", 42))
    sweep_id = str(sweep.get("name") or path.stem)
    eval_template = sweep.get("eval_template")
    disk = sweep.get("disk")

    keys = [k for k, v in search.items() if isinstance(v, list) and v]
    values = [search[k] for k in keys]

    trials: list[dict[str, Any]] = []
    if not keys:
        trials.append({})
    elif mode == "random":
        rng = random.Random(seed)
        for _ in range(max_jobs):
            pick = {k: rng.choice(search[k]) for k in keys}
            trials.append(pick)
    else:
        for combo in itertools.product(*values):
            trials.append(dict(zip(keys, combo)))
            if len(trials) >= max_jobs:
                break

    configs: list[dict[str, Any]] = []
    for i, overrides in enumerate(trials):
        cfg = copy.deepcopy(base)
        cfg.pop("_config_path", None)
        for dotted, val in overrides.items():
            _set_by_dot(cfg, dotted, val)
        cfg["name"] = f"{sweep_id}_t{i:03d}"
        cfg["sweep_id"] = sweep_id
        cfg["trial_index"] = i
        tags = list(cfg.get("tags") or [])
        tags.extend(["sweep", sweep_id])
        cfg["tags"] = list(dict.fromkeys(tags))
        if isinstance(cfg.get("eval"), dict):
            cfg["eval"] = dict(cfg["eval"])
            cfg["eval"]["save_video"] = False
            cfg["eval"]["save_frames"] = False
        if "train" in cfg and isinstance(cfg["train"], dict):
            cfg["train"] = dict(cfg["train"])
            if sweep.get("force_dry_run") is True:
                cfg["train"]["dry_run"] = True
            elif sweep.get("force_dry_run") is False:
                cfg["train"]["dry_run"] = False
        meta = {
            "sweep_id": sweep_id,
            "trial_index": i,
            "overrides": overrides,
            "eval_template": eval_template,
            "disk": disk,
            "source_sweep": str(path.resolve()),
        }
        cfg["_sweep_meta"] = meta
        configs.append(cfg)
    return configs


def enqueue_sweep(
    sweep_path: str | Path,
    *,
    notes: str = "",
    notify: bool = False,
) -> list[str]:
    """スイープを展開してキューへ投入し、job_id リストを返す。"""
    from parc.queue.store import enqueue

    configs = expand_sweep(sweep_path)
    job_ids: list[str] = []
    for cfg in configs:
        meta = cfg.pop("_sweep_meta", {})
        params: dict = {"overrides": meta.get("overrides"), "disk": meta.get("disk")}
        if notify:
            params["notify"] = True
        job = enqueue(
            kind="train_eval",
            config=cfg,
            eval_config_path=str(meta.get("eval_template") or ""),
            sweep_id=str(meta.get("sweep_id") or ""),
            trial_index=meta.get("trial_index"),
            notes=notes or f"sweep:{meta.get('sweep_id')}",
            params=params,
        )
        job_ids.append(job.job_id)
    return job_ids
