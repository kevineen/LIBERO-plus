"""parc-vr-teleop CLI 本体。"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Any

from rich.console import Console

from parc.paths import PARC_ROOT, apply_runtime_env
from parc.vr.action_map import ActionMapConfig
from parc.vr.config import load_vr_config

console = Console()


def _resolve_root(path: str | Path) -> Path:
    """相対パスを parc ルート基準で解決する。"""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (PARC_ROOT / p).resolve()
    return p


def build_parser() -> argparse.ArgumentParser:
    """引数パーサ。"""
    p = argparse.ArgumentParser(
        prog="parc-vr-teleop",
        description="Quest 3 VR teleop → LIBERO demo recorder (Approach A)",
    )
    p.add_argument("--config", default="", help="configs/vr/*.yaml")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--suite", default=None)
    p.add_argument("--task-id", type=int, default=None)
    p.add_argument(
        "--dataset-root",
        default=None,
        help="LeRobot dataset_root",
    )
    p.add_argument("--repo-id", default=None)
    p.add_argument("--fps", type=int, default=None)
    p.add_argument("--jpeg-quality", type=int, default=None)
    p.add_argument("--camera-height", type=int, default=None)
    p.add_argument("--camera-width", type=int, default=None)
    p.add_argument("--image-size", type=int, default=None, help="録画正方形解像度")
    p.add_argument(
        "--fake",
        action="store_true",
        help="LIBERO 無しでダミー env（スモーク／Quest 無し）",
    )
    p.add_argument(
        "--fake-episode",
        action="store_true",
        help="WS なしでフェイク 1 エピソードを書いて終了",
    )
    p.add_argument(
        "--fake-frames",
        type=int,
        default=16,
        help="--fake-episode のフレーム数",
    )
    p.add_argument(
        "--no-dataset",
        action="store_true",
        help="LeRobot 書き込みをスキップ（バッファのみ）",
    )
    p.add_argument(
        "--no-flip-images",
        action="store_true",
        help="録画時の 180° flip を無効化",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def resolve_runtime_args(args: argparse.Namespace) -> dict[str, Any]:
    """YAML 設定と CLI 引数をマージした実行設定を返す。"""
    raw_cfg = load_vr_config(args.config) if args.config else {}
    action_map_cfg = raw_cfg.get("action_map")
    if action_map_cfg is not None and not isinstance(action_map_cfg, dict):
        raise ValueError("action_map must be a mapping")

    def pick(name: str, fallback: Any) -> Any:
        value = getattr(args, name)
        if value is not None:
            return value
        return raw_cfg.get(name, fallback)

    return {
        "host": str(pick("host", "0.0.0.0")),
        "port": int(pick("port", 8765)),
        "suite": str(pick("suite", "libero_spatial")),
        "task_id": int(pick("task_id", 0)),
        "dataset_root": _resolve_root(pick("dataset_root", "data/datasets/vr_libero_demos")),
        "repo_id": str(pick("repo_id", "local/vr_libero_demos")),
        "fps": int(pick("fps", 20)),
        "jpeg_quality": int(pick("jpeg_quality", 70)),
        "camera_height": int(pick("camera_height", 128)),
        "camera_width": int(pick("camera_width", 128)),
        "image_size": int(pick("image_size", 256)),
        "flip_images": False if args.no_flip_images else bool(raw_cfg.get("flip_images", True)),
        "action_map": ActionMapConfig.from_mapping(action_map_cfg),
    }


def main(argv: list[str] | None = None) -> None:
    """エントリポイント。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    apply_runtime_env()

    runtime = resolve_runtime_args(args)
    dataset_root = runtime["dataset_root"]
    create_dataset = not args.no_dataset
    image_size = (runtime["image_size"], runtime["image_size"])

    if args.fake_episode:
        from parc.vr.session import run_fake_episode

        # lerobot が無い場合は自動でバッファのみ
        if create_dataset:
            try:
                import lerobot  # noqa: F401
            except ImportError:
                console.print(
                    "[yellow]lerobot 未インストール → --no-dataset 相当でバッファ検証のみ[/yellow]"
                )
                create_dataset = False

        n = run_fake_episode(
            dataset_root=dataset_root,
            num_frames=args.fake_frames,
            create_dataset=create_dataset,
            image_size=image_size if create_dataset else (64, 64),
        )
        console.print(
            f"[green]fake episode saved events={n}[/green] root={dataset_root} "
            f"create_dataset={create_dataset}"
        )
        return

    # WS サーバ
    if create_dataset:
        try:
            import lerobot  # noqa: F401
        except ImportError:
            console.print(
                "[yellow]lerobot 未インストール → 録画のディスク書き込みは無効 "
                "(--no-dataset)。robot venv で起動するか uv add 相当が必要[/yellow]"
            )
            create_dataset = False

    from parc.vr.server import serve_vr_teleop

    console.print(
        f"[bold]parc-vr-teleop[/bold] ws://{runtime['host']}:{runtime['port']} "
        f"suite={runtime['suite']} task_id={runtime['task_id']} fake={args.fake}"
    )
    console.print(f"dataset_root={dataset_root} create_dataset={create_dataset}")
    try:
        asyncio.run(
            serve_vr_teleop(
                host=runtime["host"],
                port=runtime["port"],
                suite=runtime["suite"],
                task_id=runtime["task_id"],
                dataset_root=dataset_root,
                repo_id=runtime["repo_id"],
                fps=runtime["fps"],
                jpeg_quality=runtime["jpeg_quality"],
                camera_height=runtime["camera_height"],
                camera_width=runtime["camera_width"],
                image_size=image_size,
                fake=args.fake,
                create_dataset=create_dataset,
                flip_images=runtime["flip_images"],
                action_map=runtime["action_map"],
            )
        )
    except KeyboardInterrupt:
        console.print("stopped")
