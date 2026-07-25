"""古い実験ランの削除（keep_best / keep_last / protected）。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from parc.disk.budget import DiskBudget, get_disk_budget, usage_bytes
from parc.paths import get_paths
from parc.tracking.run import RunMeta, list_registry


def _success_rate(meta: RunMeta) -> float:
    m = meta.metrics or {}
    sr = m.get("success_rate")
    if sr is None:
        return float("-inf")
    try:
        return float(sr)
    except (TypeError, ValueError):
        return float("-inf")


def _run_dir_size(run_dir: Path) -> int:
    return usage_bytes(run_dir)


def _is_protected(meta: RunMeta, tags: list[str]) -> bool:
    return any(t in (meta.tags or []) for t in tags)


def _latest_meta_by_run() -> dict[str, RunMeta]:
    """registry の最新行を run_id ごとに返す。"""
    latest: dict[str, RunMeta] = {}
    # list_registry は新しい順。初出が最新。
    for row in list_registry(limit=None):
        if row.run_id not in latest:
            latest[row.run_id] = row
    return latest


def _discover_run_dirs(exp_dir: Path) -> list[Path]:
    if not exp_dir.is_dir():
        return []
    return sorted(
        [p for p in exp_dir.iterdir() if p.is_dir() and p.name != "queue"],
        key=lambda p: p.name,
    )


def prune_experiments(
    budget: DiskBudget | None = None,
    *,
    dry_run: bool = False,
    force_budget: bool = True,
) -> dict[str, Any]:
    """keep_best（SR）+ keep_last + protected 以外を削除し、予算内に収める。

    Args:
        budget: 省略時は paths.yaml の disk 節。
        dry_run: True なら削除候補のみ返す。
        force_budget: True なら keep 規則後も予算超過なら SR の低い順に追加削除。
    """
    b = budget or get_disk_budget()
    exp_dir = b.experiments_dir or get_paths()["experiments_dir"]
    latest = _latest_meta_by_run()

    # ディレクトリ実体と meta を突き合わせ
    runs: list[tuple[Path, RunMeta | None]] = []
    for d in _discover_run_dirs(exp_dir):
        meta = latest.get(d.name)
        if meta is None:
            meta_path = d / "meta.json"
            if meta_path.is_file():
                try:
                    meta = RunMeta(**json.loads(meta_path.read_text()))
                except Exception:
                    meta = None
        runs.append((d, meta))

    # 新しい順（run_id のタイムスタンプ接頭辞）
    runs_sorted_new = sorted(runs, key=lambda x: x[0].name, reverse=True)
    keep_last_ids = {d.name for d, _ in runs_sorted_new[: max(0, b.keep_last)]}

    # SR 上位
    scored = [
        (d, meta, _success_rate(meta) if meta else float("-inf"))
        for d, meta in runs
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    keep_best_ids = {d.name for d, _, sr in scored[: max(0, b.keep_best)] if sr > float("-inf")}
    # SR 不明でも keep_best 枠が余っていれば新しいものを残す
    if len(keep_best_ids) < b.keep_best:
        for d, _, sr in scored:
            if d.name in keep_best_ids:
                continue
            keep_best_ids.add(d.name)
            if len(keep_best_ids) >= b.keep_best:
                break

    protected_ids = {
        d.name
        for d, meta in runs
        if meta is not None and _is_protected(meta, b.protected_tags)
    }

    keep_ids = keep_last_ids | keep_best_ids | protected_ids
    candidates = [(d, meta) for d, meta in runs if d.name not in keep_ids]

    deleted: list[dict[str, Any]] = []
    kept = [d.name for d, _ in runs if d.name in keep_ids]

    def _delete(d: Path, meta: RunMeta | None, reason: str) -> None:
        size = _run_dir_size(d)
        entry = {
            "run_id": d.name,
            "bytes": size,
            "reason": reason,
            "success_rate": _success_rate(meta) if meta else None,
        }
        if not dry_run:
            shutil.rmtree(d, ignore_errors=True)
        deleted.append(entry)

    for d, meta in candidates:
        _delete(d, meta, "outside_keep_best_last")

    # 予算超過なら keep 内でも SR 低い・古い順に削る（protected は守る）
    if force_budget:
        used = usage_bytes(exp_dir) if not dry_run else (
            usage_bytes(exp_dir) - sum(x["bytes"] for x in deleted)
        )
        # dry_run 時は削除後サイズを近似
        if dry_run:
            used = usage_bytes(exp_dir) - sum(x["bytes"] for x in deleted)

        survivors = [
            (d, meta)
            for d, meta in runs
            if d.name not in {x["run_id"] for x in deleted}
            and d.name not in protected_ids
        ]
        # SR 昇順、同率なら古い順
        survivors.sort(
            key=lambda x: (
                _success_rate(x[1]) if x[1] else float("-inf"),
                x[0].name,
            )
        )
        while used > b.max_bytes and survivors:
            d, meta = survivors.pop(0)
            size = _run_dir_size(d)
            _delete(d, meta, "over_budget")
            used -= size
            if d.name in kept:
                kept.remove(d.name)

    report = {
        "dry_run": dry_run,
        "experiments_dir": str(exp_dir),
        "kept": kept,
        "deleted": deleted,
        "usage_after": check_after(exp_dir, b, dry_run, deleted),
    }
    return report


def check_after(
    exp_dir: Path,
    budget: DiskBudget,
    dry_run: bool,
    deleted: list[dict[str, Any]],
) -> dict[str, Any]:
    from parc.disk.budget import check_budget

    if dry_run:
        used = usage_bytes(exp_dir) - sum(int(x["bytes"]) for x in deleted)
        return {
            "ok": used < budget.max_bytes,
            "used_bytes": max(0, used),
            "max_bytes": budget.max_bytes,
            "used_gb": round(max(0, used) / (1024**3), 3),
            "max_gb": round(budget.max_bytes / (1024**3), 3),
            "experiments_dir": str(exp_dir),
        }
    return check_budget(budget)
