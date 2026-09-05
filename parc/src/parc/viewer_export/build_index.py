"""viewer_packs を走査して index.json を作る + `parc-export-viewer` CLI。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from parc.paths import PARC_ROOT
from parc.viewer_export.scene_pack import (
    DEFAULT_FPS,
    FORMAT_VERSION,
    PACK_META,
    export_hdf5_pack,
    export_lerobot_pack,
    iter_hdf5_demos,
)

DEFAULT_PACKS_ROOT = PARC_ROOT / "data" / "viewer_packs"
INDEX_NAME = "index.json"


def pack_dir_for(out_root: Path, dataset: str, task_slug: str, episode_id: str) -> Path:
    """pack の出力ディレクトリ。"""
    return out_root / dataset / task_slug / episode_id


def build_index(packs_root: Path) -> dict[str, Any]:
    """packs_root 配下の meta.json を集めて index.json を書く。"""
    episodes: list[dict[str, Any]] = []
    for meta_path in sorted(packs_root.rglob(PACK_META)):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rel = meta_path.parent.relative_to(packs_root).as_posix()
        files = meta.get("files", {})
        episodes.append(
            {
                "id": rel,
                "dataset": meta.get("dataset", ""),
                "task": meta.get("task", ""),
                "language": meta.get("language", ""),
                "episode_index": meta.get("episode_index"),
                "demo": (meta.get("source", {}) or {}).get("demo"),
                "n_frames": int(meta.get("n_frames", 0)),
                "fps": int(meta.get("fps", DEFAULT_FPS)),
                "success": meta.get("success"),
                "replay_success": meta.get("replay_success"),
                "suite": meta.get("suite"),
                "task_id": meta.get("task_id"),
                "generated": meta.get("generated"),
                "view": meta.get("view"),
                "files": {
                    "meta": f"{rel}/{PACK_META}",
                    "glb": f"{rel}/{files.get('glb', 'scene.glb')}",
                    "tracks": f"{rel}/{files.get('tracks', 'tracks.bin')}",
                    "videos": {
                        k: f"{rel}/{v}" for k, v in (files.get("videos") or {}).items()
                    },
                },
            }
        )
    index = {
        "format_version": FORMAT_VERSION,
        "generated": datetime.now(timezone.utc).isoformat(),
        "n_episodes": len(episodes),
        "episodes": episodes,
    }
    out = packs_root / INDEX_NAME
    packs_root.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def _episode_id_for_hdf5(demo_key: str) -> str:
    return demo_key.replace("demo_", "ep_")


def export_hdf5_task(
    hdf5_path: Path,
    *,
    out_root: Path,
    demos: list[str] | None = None,
    max_frames: int | None = None,
    include_videos: bool = True,
    force: bool = False,
) -> int:
    """HDF5 内の指定 demo（省略時は全 demo）を pack 化。書いた pack 数を返す。"""
    import h5py

    from parc.viewer_export.scene_pack import _slugify

    all_demos = list(iter_hdf5_demos(hdf5_path))
    if demos:
        wanted: list[str] = []
        for spec in demos:
            key = f"demo_{int(spec)}" if spec.isdigit() else spec
            if key not in all_demos:
                raise KeyError(f"{key} not in {hdf5_path.name}")
            wanted.append(key)
    else:
        wanted = all_demos

    dataset = hdf5_path.parent.name
    with h5py.File(hdf5_path, "r") as f:
        problem = json.loads(f["data"].attrs.get("problem_info", "{}")) or {}
    task_name = str(problem.get("task_name") or hdf5_path.stem)
    task_slug = _slugify(task_name)

    written = 0
    for demo_key in wanted:
        episode_id = _episode_id_for_hdf5(demo_key)
        out_dir = pack_dir_for(out_root, dataset, task_slug, episode_id)
        if not force and (out_dir / PACK_META).is_file():
            continue
        export_hdf5_pack(
            hdf5_path,
            demo=demo_key,
            out_dir=out_dir,
            include_videos=include_videos,
            max_frames=max_frames,
        )
        written += 1
    return written


def export_lerobot_dataset(
    root: Path,
    *,
    out_root: Path,
    episodes: list[int] | None = None,
    include_videos: bool = True,
    force: bool = False,
) -> int:
    """LeRobot データセットの指定エピソード（省略時は全て）を pack 化。"""
    from parc.data.verify_demos import load_quality_rows

    rows = load_quality_rows(root)
    targets = episodes if episodes else sorted(int(r["episode_index"]) for r in rows)
    written = 0
    for ep in targets:
        # suite/task は quality 行から
        row = next((r for r in rows if int(r.get("episode_index", -1)) == ep), None)
        if row is None:
            continue
        language = str(row.get("language") or row.get("task") or f"ep_{ep:04d}")
        from parc.viewer_export.scene_pack import _slugify

        task_slug = _slugify(language)[:60] or f"ep_{ep:04d}"
        out_dir = pack_dir_for(out_root, root.name, task_slug, f"ep_{ep:04d}")
        if not force and (out_dir / "meta.json").is_file():
            continue
        export_lerobot_pack(
            root, episode_index=ep, out_dir=out_dir, include_videos=include_videos
        )
        written += 1
    return written


def build_parser() -> argparse.ArgumentParser:
    """CLI パーサ。"""
    p = argparse.ArgumentParser(
        prog="parc-export-viewer",
        description=(
            "収録済みデモを Web/VR ビューア用 scene pack に変換して index.json を更新する"
        ),
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--hdf5", default="", help="libero *_demo.hdf5 へのパス")
    src.add_argument("--lerobot", default="", help="LeRobot dataset ルート（VR テレオプ収集）")
    src.add_argument(
        "--reindex",
        action="store_true",
        help="既存 packs の index.json を再生成するだけ",
    )
    p.add_argument("--out", default=str(DEFAULT_PACKS_ROOT), help="packs 出力ルート")
    p.add_argument("--demos", nargs="*", default=None, help="HDF5 demo キーまたは番号（省略時は全て）")
    p.add_argument("--episodes", nargs="*", type=int, default=None, help="LeRobot episode_index 一覧")
    p.add_argument("--max-frames", type=int, default=None, help="フレーム数間引き（stride エクスポート）")
    p.add_argument("--no-videos", action="store_true", help="mp4 を出力/コピーしない")
    p.add_argument("--force", action="store_true", help="既存 pack を上書き")
    return p


def main(argv: list[str] | None = None) -> None:
    """エントリポイント。"""
    from rich.console import Console

    console = Console()
    args = build_parser().parse_args(argv)
    out_root = Path(args.out)
    if not out_root.is_absolute():
        out_root = (PARC_ROOT / out_root).resolve()

    try:
        if args.reindex:
            index = build_index(out_root)
            console.print(
                f"[green]index ok[/green] episodes={index['n_episodes']} → {out_root / INDEX_NAME}"
            )
            return

        written = 0
        if args.hdf5:
            hdf5 = Path(args.hdf5)
            if not hdf5.is_absolute():
                hdf5 = (PARC_ROOT / hdf5).resolve()
            written = export_hdf5_task(
                hdf5,
                out_root=out_root,
                demos=args.demos,
                max_frames=args.max_frames,
                include_videos=not args.no_videos,
                force=args.force,
            )
            console.print(f"[green]hdf5 packs[/green] written={written} src={hdf5}")
        elif args.lerobot:
            root = Path(args.lerobot)
            if not root.is_absolute():
                root = (PARC_ROOT / root).resolve()
            written = export_lerobot_dataset(
                root,
                out_root=out_root,
                episodes=args.episodes,
                include_videos=not args.no_videos,
                force=args.force,
            )
            console.print(f"[green]lerobot packs[/green] written={written} src={root}")

        index = build_index(out_root)
        console.print(
            f"[green]index ok[/green] episodes={index['n_episodes']} → {out_root / INDEX_NAME}"
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]export failed[/red]: {exc}")
        raise SystemExit(1) from exc
