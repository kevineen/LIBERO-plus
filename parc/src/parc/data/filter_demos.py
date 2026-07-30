"""成功エピソードだけの物理 subset root を作る（学習用 success-only 経路）。"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from parc.paths import PARC_ROOT
from parc.vr.collection_meta import COLLECTION_INFO_NAME
from parc.vr.recorder import (
    COLLECTION_STATS_NAME,
    QUALITY_JSONL_NAME,
    TIMESTAMPS_JSONL_NAME,
)


@dataclass
class FilterResult:
    """フィルタ結果の要約。"""

    root: str
    output: str
    n_input: int
    n_kept: int
    episode_indices: list[int]
    exclude_degraded: bool
    dry_run: bool


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
        row = json.loads(text)
        if not isinstance(row, dict):
            raise ValueError(f"quality row must be object at {path}:{line_no}")
        rows.append(row)
    return rows


def select_episode_indices(
    rows: list[dict[str, Any]],
    *,
    success_only: bool = True,
    exclude_degraded: bool = False,
) -> list[int]:
    """フィルタ条件に合う episode_index を昇順で返す。"""
    kept: list[int] = []
    for row in rows:
        if success_only and row.get("success") is not True:
            continue
        if exclude_degraded and row.get("degraded") is True:
            continue
        idx = row.get("episode_index")
        if not isinstance(idx, int):
            raise ValueError(f"quality row missing int episode_index: {row!r}")
        kept.append(idx)
    return sorted(set(kept))


def _load_jsonl_by_episode(path: Path) -> dict[int, dict[str, Any]]:
    """jsonl を episode_index → row にマップする。"""
    if not path.is_file():
        return {}
    out: dict[int, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        row = json.loads(text)
        idx = row.get("episode_index")
        if isinstance(idx, int):
            out[idx] = row
    return out


def remap_sidecars(
    src_root: Path,
    dst_root: Path,
    episode_indices: list[int],
) -> None:
    """quality / timestamps / collection_info を出力 index に再マップして書く。"""
    meta_src = src_root / "meta"
    meta_dst = dst_root / "meta"
    meta_dst.mkdir(parents=True, exist_ok=True)

    quality_by = _load_jsonl_by_episode(meta_src / QUALITY_JSONL_NAME)
    ts_by = _load_jsonl_by_episode(meta_src / TIMESTAMPS_JSONL_NAME)

    q_path = meta_dst / QUALITY_JSONL_NAME
    t_path = meta_dst / TIMESTAMPS_JSONL_NAME
    with q_path.open("w", encoding="utf-8") as qf, t_path.open("w", encoding="utf-8") as tf:
        for new_idx, old_idx in enumerate(episode_indices):
            if old_idx not in quality_by:
                raise KeyError(f"quality missing episode_index={old_idx}")
            q_row = dict(quality_by[old_idx])
            q_row["episode_index"] = new_idx
            q_row["source_episode_index"] = old_idx
            qf.write(json.dumps(q_row, ensure_ascii=False) + "\n")

            if old_idx in ts_by:
                t_row = dict(ts_by[old_idx])
                t_row["episode_index"] = new_idx
                t_row["source_episode_index"] = old_idx
                tf.write(json.dumps(t_row, ensure_ascii=False) + "\n")

    info_src = meta_src / COLLECTION_INFO_NAME
    if info_src.is_file():
        shutil.copy2(info_src, meta_dst / COLLECTION_INFO_NAME)

    stats = {
        "attempted": len(episode_indices),
        "saved": len(episode_indices),
        "saved_success": len(episode_indices),
        "saved_failed": 0,
        "discarded": 0,
        "refused": 0,
        "filtered_from": str(src_root),
        "source_episode_indices": episode_indices,
    }
    (meta_dst / COLLECTION_STATS_NAME).write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def filter_demo_dataset(
    root: Path | str,
    output: Path | str,
    *,
    success_only: bool = True,
    exclude_degraded: bool = False,
    repo_id: str | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
) -> FilterResult:
    """成功（任意で非 degraded）エピソードだけを output root へ物理コピーする。"""
    src = _resolve_root(root)
    dst = _resolve_root(output)
    rows = load_quality_rows(src)
    indices = select_episode_indices(
        rows,
        success_only=success_only,
        exclude_degraded=exclude_degraded,
    )
    result = FilterResult(
        root=str(src),
        output=str(dst),
        n_input=len(rows),
        n_kept=len(indices),
        episode_indices=indices,
        exclude_degraded=exclude_degraded,
        dry_run=dry_run,
    )
    if dry_run:
        return result
    if not indices:
        raise ValueError(f"no episodes matched filter under {src}")

    if dst.exists():
        if not overwrite:
            raise FileExistsError(f"output exists: {dst} (use --overwrite)")
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)

    info_json = src / "meta" / "info.json"
    if info_json.is_file():
        try:
            from lerobot.datasets.dataset_tools import split_dataset
            from lerobot.datasets.lerobot_dataset import LeRobotDataset
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "lerobot が必要です。PARC_ROBOT_VENV または親 .venv で実行してください。"
            ) from exc

        src_repo = repo_id or "local/vr_libero_demos"
        if (src / "meta" / "collection_info.json").is_file():
            try:
                cinfo = json.loads(
                    (src / "meta" / "collection_info.json").read_text(encoding="utf-8")
                )
                # collection_info に repo は無いことが多いので info 側は触らない
                _ = cinfo
            except json.JSONDecodeError:
                pass
        # info.json の repo_id があれば優先
        try:
            info = json.loads(info_json.read_text(encoding="utf-8"))
            src_repo = str(info.get("repo_id") or src_repo)
        except json.JSONDecodeError:
            pass

        work = dst.parent / f".filter_work_{dst.name}"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True, exist_ok=True)
        try:
            ds = LeRobotDataset(src_repo, root=src)
            split = split_dataset(
                ds,
                splits={"success": indices},
                output_dir=work,
            )["success"]
            split_root = Path(split.root)
            # split 出力を最終 output へ移動
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(split_root), str(dst))
        finally:
            if work.exists():
                shutil.rmtree(work, ignore_errors=True)
    else:
        # サイドカーのみデータセット（create_dataset=False 相当）
        (dst / "meta").mkdir(parents=True, exist_ok=True)

    remap_sidecars(src, dst, indices)
    manifest = {**asdict(result), "success_only": success_only}
    (dst / "filter_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    """CLI パーサ。"""
    p = argparse.ArgumentParser(
        prog="parc-filter-demos",
        description="Create a physical success-only subset of a VR demo dataset",
    )
    p.add_argument("--root", required=True, help="入力 LeRobot dataset root")
    p.add_argument("--output", required=True, help="出力 subset root")
    p.add_argument(
        "--success-only",
        action="store_true",
        default=True,
        help="success==true のみ残す（既定）",
    )
    p.add_argument(
        "--no-success-only",
        action="store_false",
        dest="success_only",
        help="success フィルタを無効化（degraded 除外のみ等）",
    )
    p.add_argument(
        "--exclude-degraded",
        action="store_true",
        help="degraded==true を除外",
    )
    p.add_argument("--repo-id", default=None, help="入力 repo_id（省略時は info/既定）")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    return p


def main(argv: list[str] | None = None) -> None:
    """エントリポイント。"""
    from rich.console import Console

    console = Console()
    args = build_parser().parse_args(argv)
    try:
        result = filter_demo_dataset(
            args.root,
            args.output,
            success_only=args.success_only,
            exclude_degraded=args.exclude_degraded,
            repo_id=args.repo_id,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]filter failed[/red]: {exc}")
        raise SystemExit(1) from exc
    tag = "dry-run" if result.dry_run else "ok"
    console.print(
        f"[green]filter {tag}[/green] kept={result.n_kept}/{result.n_input} "
        f"→ {result.output}"
    )
