"""VR / 自前デモの品質メタ検証（LeRobot Dataset v3.0 前提）。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from parc.data.angle_units import (
    ANGLE_UNITS_META_NAME,
    assert_joint_dataset_units,
    check_joint_angle_scale,
    load_angle_units_meta,
)
from parc.paths import PARC_ROOT
from parc.vr.collection_meta import COLLECTION_INFO_NAME, load_collection_info
from parc.vr.recorder import QUALITY_JSONL_NAME, TIMESTAMPS_JSONL_NAME

REQUIRED_QUALITY_KEYS = (
    "episode_index",
    "suite",
    "task_id",
    "init_state_index",
    "language",
    "success",
    "num_frames",
    "fps",
)


def _resolve_root(path: str | Path) -> Path:
    """相対パスを parc ルート基準で解決する。"""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (PARC_ROOT / p).resolve()
    return p


def load_quality_rows(root: Path) -> list[dict[str, Any]]:
    """episode_quality.jsonl を読む。"""
    path = root / "meta" / QUALITY_JSONL_NAME
    if not path.is_file():
        raise FileNotFoundError(f"missing quality jsonl: {path}")
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at {path}:{line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"quality row must be object at {path}:{line_no}")
        rows.append(row)
    return rows


def coverage_by_category(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """category → {success, failed, total} のカバレッジ表。"""
    success_c: Counter[str] = Counter()
    failed_c: Counter[str] = Counter()
    for row in rows:
        cat = str(row.get("category") or "uncategorized")
        if row.get("success") is True:
            success_c[cat] += 1
        else:
            failed_c[cat] += 1
    cats = sorted(set(success_c) | set(failed_c))
    return {
        cat: {
            "success": int(success_c[cat]),
            "failed": int(failed_c[cat]),
            "total": int(success_c[cat] + failed_c[cat]),
        }
        for cat in cats
    }


def _load_actions_from_parquet(
    root: Path,
    *,
    max_rows: int = 5000,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """可能なら parquet から action / state をサンプリングする。無ければ (None, None)。"""
    data_dir = root / "data"
    if not data_dir.is_dir():
        return None, None
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ImportError:
        return None, None

    actions: list[np.ndarray] = []
    states: list[np.ndarray] = []
    n = 0
    for path in sorted(data_dir.rglob("*.parquet")):
        table = pq.read_table(path)
        names = set(table.column_names)
        act_col = "action" if "action" in names else None
        st_col = (
            "observation.state"
            if "observation.state" in names
            else ("state" if "state" in names else None)
        )
        if act_col is None:
            continue
        col = table.column(act_col)
        for i in range(len(col)):
            val = col[i].as_py()
            actions.append(np.asarray(val, dtype=np.float64).reshape(-1))
            n += 1
            if st_col is not None:
                states.append(
                    np.asarray(table.column(st_col)[i].as_py(), dtype=np.float64).reshape(-1)
                )
            if n >= max_rows:
                break
        if n >= max_rows:
            break
    if not actions:
        return None, None
    act_arr = np.stack(actions, axis=0)
    st_arr = np.stack(states, axis=0) if states and len(states) == len(actions) else None
    return act_arr, st_arr


def verify_joint_angle_units(
    root: Path,
    *,
    require_meta: bool = False,
    check_scale: bool = False,
    actions: np.ndarray | None = None,
    states: np.ndarray | None = None,
) -> dict[str, Any]:
    """angle_units.json と（任意で）振幅ヒューリスティックを検査する。"""
    meta = load_angle_units_meta(root)
    out: dict[str, Any] = {
        "meta_present": meta is not None,
        "skipped": False,
        "ok": True,
        "errors": [],
    }
    if meta is None:
        if require_meta:
            raise ValueError(f"missing meta/{ANGLE_UNITS_META_NAME} under {root}")
        out["skipped"] = True
        return out

    out["control_mode"] = meta.control_mode
    out["stored_unit"] = meta.stored_unit
    if meta.control_mode == "ee_delta":
        out["skipped"] = True
        return out

    assert_joint_dataset_units(meta)

    if not check_scale:
        return out

    act = actions
    st = states
    if act is None:
        act, st = _load_actions_from_parquet(root)
    if act is None:
        raise ValueError(
            "check_joint_angle_units requires action samples "
            "(parquet under data/ or pass actions=)"
        )
    errors = check_joint_angle_scale(act, meta=meta, states=st)
    out["errors"] = errors
    if errors:
        out["ok"] = False
        raise ValueError("; ".join(errors))
    return out


def verify_demo_dataset(
    root: Path | str,
    *,
    require_success: bool = False,
    require_info_json: bool = False,
    require_collection_info: bool = True,
    require_replay_success: bool = False,
    require_coverage_min: int = 0,
    require_angle_units: bool = False,
    check_joint_angle_units: bool = False,
    angle_unit_actions: np.ndarray | None = None,
    angle_unit_states: np.ndarray | None = None,
) -> dict[str, Any]:
    """スキーマ外品質メタと（任意で）info.json / collection_info / 角度単位の整合を検査する。"""
    root_path = _resolve_root(root)
    meta = root_path / "meta"
    if not meta.is_dir():
        raise FileNotFoundError(f"missing meta dir: {meta}")

    info_path = meta / "info.json"
    info: dict[str, Any] | None = None
    if info_path.is_file():
        info = json.loads(info_path.read_text(encoding="utf-8"))
        code_ver = str(info.get("codebase_version", ""))
        if code_ver and not code_ver.startswith("v3"):
            raise ValueError(f"expected LeRobot v3.x codebase_version, got {code_ver!r}")
    elif require_info_json:
        raise FileNotFoundError(f"missing info.json: {info_path}")

    if require_collection_info:
        collection = load_collection_info(root_path)
        for key in ("cameras", "frames", "collection", "fps"):
            if key not in collection:
                raise ValueError(f"collection_info missing key: {key}")

    rows = load_quality_rows(root_path)
    if not rows:
        raise ValueError(f"empty quality jsonl under {root_path}")

    errors: list[str] = []
    seen_indices: set[int] = set()
    init_coverage: set[tuple[Any, Any, Any]] = set()
    n_success = 0
    n_failed = 0

    for i, row in enumerate(rows):
        for key in REQUIRED_QUALITY_KEYS:
            if key not in row:
                errors.append(f"row[{i}] missing key: {key}")
        if require_success and row.get("success") is not True:
            errors.append(f"row[{i}] success!=true: {row.get('success')!r}")
        if require_replay_success and row.get("replay_success") is not True:
            errors.append(
                f"row[{i}] replay_success!=true: {row.get('replay_success')!r}"
            )
        if row.get("success") is True:
            n_success += 1
        else:
            n_failed += 1
        idx = row.get("episode_index")
        if isinstance(idx, int):
            if idx in seen_indices:
                errors.append(f"duplicate episode_index={idx}")
            seen_indices.add(idx)
        num_frames = row.get("num_frames")
        if isinstance(num_frames, int) and num_frames <= 0:
            errors.append(f"row[{i}] num_frames must be > 0")
        init_coverage.add((row.get("suite"), row.get("task_id"), row.get("init_state_index")))

    ts_path = meta / TIMESTAMPS_JSONL_NAME
    if ts_path.is_file():
        ts_lines = [ln for ln in ts_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if len(ts_lines) != len(rows):
            errors.append(
                f"episode_timestamps rows={len(ts_lines)} != quality rows={len(rows)}"
            )

    if info is not None:
        total = info.get("total_episodes")
        if total is not None and int(total) != len(rows):
            errors.append(
                f"info.total_episodes={total} != quality rows={len(rows)}"
            )

    coverage = coverage_by_category(rows)
    if require_coverage_min > 0:
        for cat, counts in coverage.items():
            if counts["success"] < require_coverage_min:
                errors.append(
                    f"category={cat!r} success={counts['success']} "
                    f"< require_coverage_min={require_coverage_min}"
                )

    if errors:
        raise ValueError("; ".join(errors))

    angle_summary = verify_joint_angle_units(
        root_path,
        require_meta=require_angle_units,
        check_scale=check_joint_angle_units,
        actions=angle_unit_actions,
        states=angle_unit_states,
    )

    return {
        "root": str(root_path),
        "n_quality_rows": len(rows),
        "n_success": n_success,
        "n_failed": n_failed,
        "n_unique_init": len(init_coverage),
        "require_success": require_success,
        "require_replay_success": require_replay_success,
        "coverage": coverage,
        "info_json": info_path.is_file(),
        "collection_info": (meta / COLLECTION_INFO_NAME).is_file(),
        "codebase_version": (info or {}).get("codebase_version"),
        "angle_units": angle_summary,
        "ok": True,
    }


def build_parser() -> argparse.ArgumentParser:
    """CLI パーサ。"""
    p = argparse.ArgumentParser(
        prog="parc-verify-demos",
        description="Verify VR/custom demo metadata for LeRobot Dataset v3.0",
    )
    p.add_argument("--root", required=True, help="LeRobot dataset root")
    p.add_argument(
        "--require-success-only",
        action="store_true",
        help="success!=true をエラーにする（学習用フィルタ）",
    )
    p.add_argument(
        "--require-replay-success",
        action="store_true",
        help="replay_success!=true をエラーにする",
    )
    p.add_argument("--require-info-json", action="store_true")
    p.add_argument(
        "--skip-collection-info",
        action="store_true",
        help="collection_info.json 検査をスキップ",
    )
    p.add_argument(
        "--coverage",
        action="store_true",
        help="category × success カバレッジを表示",
    )
    p.add_argument(
        "--require-coverage-min",
        type=int,
        default=0,
        help="各 category の success 最低本数（0 で無効）",
    )
    p.add_argument(
        "--require-angle-units",
        action="store_true",
        help="meta/angle_units.json の欠落をエラーにする",
    )
    p.add_argument(
        "--check-joint-angle-units",
        action="store_true",
        help="joint_position データで rad/deg 取り違えの振幅検査を行う",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    """エントリポイント。"""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        summary = verify_demo_dataset(
            args.root,
            require_success=args.require_success_only,
            require_info_json=args.require_info_json,
            require_collection_info=not args.skip_collection_info,
            require_replay_success=args.require_replay_success,
            require_coverage_min=args.require_coverage_min,
            require_angle_units=args.require_angle_units,
            check_joint_angle_units=args.check_joint_angle_units,
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]verify failed[/red]: {exc}")
        raise SystemExit(1) from exc
    console.print(
        f"[green]verify ok[/green] root={summary['root']} "
        f"rows={summary['n_quality_rows']} success={summary['n_success']} "
        f"failed={summary['n_failed']} v={summary.get('codebase_version')}"
    )
    angle = summary.get("angle_units") or {}
    if angle.get("meta_present") and not angle.get("skipped"):
        console.print(
            f"angle_units: mode={angle.get('control_mode')} "
            f"stored={angle.get('stored_unit')} ok={angle.get('ok')}"
        )
    if args.coverage or args.require_coverage_min > 0:
        table = Table(title="category coverage")
        table.add_column("category")
        table.add_column("success", justify="right")
        table.add_column("failed", justify="right")
        table.add_column("total", justify="right")
        for cat, counts in (summary.get("coverage") or {}).items():
            table.add_row(
                cat,
                str(counts["success"]),
                str(counts["failed"]),
                str(counts["total"]),
            )
        console.print(table)
