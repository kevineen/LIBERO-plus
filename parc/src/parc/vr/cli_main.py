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
        description="Quest 3 VR teleop → LIBERO demo recorder (LeRobot Dataset v3.0)",
    )
    p.add_argument("--config", default="", help="configs/vr/*.yaml")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--suite", default=None)
    p.add_argument("--task-id", type=int, default=None)
    p.add_argument("--dataset-root", default=None, help="LeRobot dataset_root")
    p.add_argument("--repo-id", default=None)
    p.add_argument("--fps", type=int, default=None)
    p.add_argument("--jpeg-quality", type=int, default=None)
    p.add_argument("--camera-height", type=int, default=None)
    p.add_argument("--camera-width", type=int, default=None)
    p.add_argument("--image-size", type=int, default=None, help="録画正方形解像度")
    p.add_argument("--fake", action="store_true", help="ダミー env")
    p.add_argument("--fake-episode", action="store_true", help="WS なしで 1 ep 書いて終了")
    p.add_argument("--fake-frames", type=int, default=16)
    p.add_argument("--no-dataset", action="store_true", help="LeRobot 書き込みスキップ")
    p.add_argument("--no-flip-images", action="store_true")
    p.add_argument(
        "--require-success",
        action="store_true",
        help="未成功エピソードの Save を拒否（既定は失敗も保存）",
    )
    p.add_argument("--operator-id", default=None)
    p.add_argument("--device-id", default=None)
    p.add_argument("--location", default=None)
    p.add_argument("--calib-override", default=None, help="カメラ校正上書き JSON")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def resolve_runtime_args(args: argparse.Namespace) -> dict[str, Any]:
    """YAML 設定と CLI 引数をマージした実行設定を返す。"""
    raw_cfg = load_vr_config(args.config) if args.config else {}
    action_map_cfg = raw_cfg.get("action_map")
    if action_map_cfg is not None and not isinstance(action_map_cfg, dict):
        raise ValueError("action_map must be a mapping")

    def pick(name: str, fallback: Any) -> Any:
        value = getattr(args, name, None)
        if value is not None:
            return value
        return raw_cfg.get(name, fallback)

    task_ids_raw = raw_cfg.get("task_ids")
    if isinstance(task_ids_raw, list) and task_ids_raw:
        task_ids = [int(x) for x in task_ids_raw]
    else:
        task_ids = [int(pick("task_id", 0))]

    # 既定: 失敗も保存。CLI --require-success または YAML で厳格化。
    if bool(getattr(args, "require_success", False)):
        require_success = True
    elif "require_success" in raw_cfg:
        require_success = bool(raw_cfg["require_success"])
    else:
        require_success = False

    calib = pick("calib_override", None)
    if calib is None:
        calib = raw_cfg.get("calib_override_path") or raw_cfg.get("calib_override") or ""

    queue_raw = raw_cfg.get("collection_queue")
    collection_queue: list[dict[str, Any]] = []
    if isinstance(queue_raw, list):
        collection_queue = [dict(x) for x in queue_raw if isinstance(x, dict)]
    elif isinstance(queue_raw, str) and queue_raw.strip():
        qpath = _resolve_root(queue_raw)
        qdoc = load_vr_config(qpath)
        nested = qdoc.get("queue", qdoc.get("collection_queue", []))
        if isinstance(nested, list):
            collection_queue = [dict(x) for x in nested if isinstance(x, dict)]
        if "min_success_per_category" in qdoc and "min_success_per_category" not in raw_cfg:
            raw_cfg = {**raw_cfg, "min_success_per_category": qdoc["min_success_per_category"]}

    return {
        "host": str(pick("host", "0.0.0.0")),
        "port": int(pick("port", 8765)),
        "suite": str(pick("suite", "libero_spatial")),
        "task_id": int(pick("task_id", task_ids[0])),
        "task_ids": task_ids,
        "dataset_root": _resolve_root(pick("dataset_root", "data/datasets/vr_libero_demos")),
        "repo_id": str(pick("repo_id", "local/vr_libero_demos")),
        "fps": int(pick("fps", 20)),
        "jpeg_quality": int(pick("jpeg_quality", 70)),
        "camera_height": int(pick("camera_height", 128)),
        "camera_width": int(pick("camera_width", 128)),
        "image_size": int(pick("image_size", 256)),
        "flip_images": False if args.no_flip_images else bool(raw_cfg.get("flip_images", True)),
        "action_map": ActionMapConfig.from_mapping(action_map_cfg),
        "require_success": require_success,
        "init_state_mode": str(raw_cfg.get("init_state_mode", "cycle")),
        "operator_id": str(pick("operator_id", "")),
        "device_id": str(pick("device_id", "")),
        "location": str(pick("location", "")),
        "calib_override_path": str(calib or ""),
        "max_rtt_ms": float(raw_cfg.get("max_rtt_ms", 150.0)),
        "latency_policy": str(raw_cfg.get("latency_policy", "degraded")),
        "approx_time_slop_ms": float(raw_cfg.get("approx_time_slop_ms", 100.0)),
        "collection_queue": collection_queue,
        "min_success_per_category": int(raw_cfg.get("min_success_per_category", 0)),
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
            require_success=runtime["require_success"],
        )
        console.print(
            f"[green]fake episode saved events={n}[/green] root={dataset_root} "
            f"create_dataset={create_dataset} require_success={runtime['require_success']} "
            f"format=LeRobotDataset-v3.0"
        )
        return

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
        f"suite={runtime['suite']} task_id={runtime['task_id']} "
        f"task_ids={runtime['task_ids']} fake={args.fake}"
    )
    console.print(
        f"dataset_root={dataset_root} create_dataset={create_dataset} "
        f"require_success={runtime['require_success']} "
        f"init_state_mode={runtime['init_state_mode']} format=v3.0"
    )
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
                require_success=runtime["require_success"],
                init_state_mode=runtime["init_state_mode"],
                task_ids=runtime["task_ids"],
                operator_id=runtime["operator_id"],
                device_id=runtime["device_id"],
                location=runtime["location"],
                calib_override_path=runtime["calib_override_path"],
                max_rtt_ms=runtime["max_rtt_ms"],
                latency_policy=runtime["latency_policy"],
                approx_time_slop_ms=runtime["approx_time_slop_ms"],
                collection_queue=runtime["collection_queue"],
                min_success_per_category=runtime["min_success_per_category"],
            )
        )
    except KeyboardInterrupt:
        console.print("stopped")
