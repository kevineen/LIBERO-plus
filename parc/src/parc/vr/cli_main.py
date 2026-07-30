"""parc-vr-teleop CLI 本体。"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from rich.console import Console

from parc.paths import PARC_ROOT, apply_runtime_env

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
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--suite", default="libero_spatial")
    p.add_argument("--task-id", type=int, default=0)
    p.add_argument(
        "--dataset-root",
        default="data/datasets/vr_libero_demos",
        help="LeRobot dataset_root",
    )
    p.add_argument("--repo-id", default="local/vr_libero_demos")
    p.add_argument("--fps", type=int, default=20)
    p.add_argument("--jpeg-quality", type=int, default=70)
    p.add_argument("--camera-height", type=int, default=128)
    p.add_argument("--camera-width", type=int, default=128)
    p.add_argument("--image-size", type=int, default=256, help="録画正方形解像度")
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


def main(argv: list[str] | None = None) -> None:
    """エントリポイント。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    apply_runtime_env()

    dataset_root = _resolve_root(args.dataset_root)
    create_dataset = not args.no_dataset
    image_size = (args.image_size, args.image_size)

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
        f"[bold]parc-vr-teleop[/bold] ws://{args.host}:{args.port} "
        f"suite={args.suite} task_id={args.task_id} fake={args.fake}"
    )
    console.print(f"dataset_root={dataset_root} create_dataset={create_dataset}")
    try:
        asyncio.run(
            serve_vr_teleop(
                host=args.host,
                port=args.port,
                suite=args.suite,
                task_id=args.task_id,
                dataset_root=dataset_root,
                repo_id=args.repo_id,
                fps=args.fps,
                jpeg_quality=args.jpeg_quality,
                camera_height=args.camera_height,
                camera_width=args.camera_width,
                image_size=image_size,
                fake=args.fake,
                create_dataset=create_dataset,
                flip_images=not args.no_flip_images,
            )
        )
    except KeyboardInterrupt:
        console.print("stopped")
