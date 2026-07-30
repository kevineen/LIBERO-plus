"""Quest 向け WebSocket テレオプサーバ。"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from parc.vr.action_map import ActionMapConfig
from parc.vr.env_factory import make_teleop_env
from parc.vr.protocol import (
    ControlMessage,
    ErrorMessage,
    HelloMessage,
    PingMessage,
    PongMessage,
    TaskInfoMessage,
    encode_message,
    parse_client_message,
)
from parc.vr.session import TeleopSession, TeleopSessionConfig

logger = logging.getLogger(__name__)


async def _handle_client(
    websocket: Any,
    *,
    session_factory: Any,
) -> None:
    """1 接続を処理する。"""
    session: TeleopSession | None = None
    loop = asyncio.get_running_loop()
    outbound: asyncio.Queue[str | bytes] = asyncio.Queue()

    def send_sync(payload: str | bytes) -> None:
        """スレッド／同期側から送信用キューへ積む。"""
        outbound.put_nowait(payload)

    async def writer() -> None:
        """キューから WebSocket へ送る。"""
        while True:
            payload = await outbound.get()
            await websocket.send(payload)

    writer_task = asyncio.create_task(writer())
    try:
        session = session_factory(send_sync)
        await websocket.send(
            encode_message(
                HelloMessage(
                    fps=session.config.fps,
                    jpeg_quality=session.config.jpeg_quality,
                )
            )
        )
        await websocket.send(
            encode_message(
                TaskInfoMessage(
                    suite=session.config.suite,
                    task_id=session.config.task_id,
                    language=session.config.language,
                )
            )
        )
        session.emit_status("ready")
        session.emit_video()

        async for raw in websocket:
            if isinstance(raw, bytes):
                await websocket.send(
                    encode_message(
                        ErrorMessage(code="unexpected_binary", message="client binary not supported")
                    )
                )
                continue
            try:
                msg = parse_client_message(raw)
            except Exception as exc:  # noqa: BLE001 — クライアント入力は雑多
                await websocket.send(
                    encode_message(ErrorMessage(code="bad_message", message=str(exc)))
                )
                continue

            if isinstance(msg, PingMessage):
                await websocket.send(encode_message(PongMessage(t=msg.t)))
                continue

            if isinstance(msg, ControlMessage):
                # env.step はブロッキングし得るので executor へ
                await loop.run_in_executor(None, session.handle_control, msg)
                await loop.run_in_executor(None, session.emit_video)

    finally:
        writer_task.cancel()
        if session is not None:
            session.close()


def build_session_factory(
    *,
    suite: str,
    task_id: int,
    host_dataset_root: Path,
    repo_id: str,
    fps: int,
    jpeg_quality: int,
    camera_height: int,
    camera_width: int,
    image_size: tuple[int, int],
    action_map: ActionMapConfig,
    fake: bool,
    create_dataset: bool,
    flip_images: bool,
) -> Any:
    """接続ごとに TeleopSession を作るファクトリ。"""

    def factory(send_sync: Any) -> TeleopSession:
        env, language = make_teleop_env(
            suite,
            task_id,
            camera_height=camera_height,
            camera_width=camera_width,
            fake=fake,
        )
        cfg = TeleopSessionConfig(
            suite=suite,
            task_id=task_id,
            language=language,
            fps=fps,
            jpeg_quality=jpeg_quality,
            flip_images=flip_images,
            image_size=image_size,
            action_map=action_map,
            dataset_root=host_dataset_root,
            repo_id=repo_id,
            create_dataset=create_dataset,
        )
        return TeleopSession(env=env, config=cfg, send=send_sync)

    return factory


async def serve_vr_teleop(
    *,
    host: str = "0.0.0.0",
    port: int = 8765,
    suite: str = "libero_spatial",
    task_id: int = 0,
    dataset_root: Path = Path("data/datasets/vr_libero_demos"),
    repo_id: str = "local/vr_libero_demos",
    fps: int = 20,
    jpeg_quality: int = 70,
    camera_height: int = 128,
    camera_width: int = 128,
    image_size: tuple[int, int] = (256, 256),
    action_map: ActionMapConfig | None = None,
    fake: bool = False,
    create_dataset: bool = True,
    flip_images: bool = True,
) -> None:
    """WebSocket サーバを起動する（キャンセルまでブロック）。"""
    try:
        from websockets.asyncio.server import serve
    except ImportError:  # pragma: no cover
        from websockets.server import serve  # type: ignore[no-redef]

    factory = build_session_factory(
        suite=suite,
        task_id=task_id,
        host_dataset_root=dataset_root,
        repo_id=repo_id,
        fps=fps,
        jpeg_quality=jpeg_quality,
        camera_height=camera_height,
        camera_width=camera_width,
        image_size=image_size,
        action_map=action_map or ActionMapConfig(),
        fake=fake,
        create_dataset=create_dataset,
        flip_images=flip_images,
    )

    async def handler(websocket: Any) -> None:
        await _handle_client(websocket, session_factory=factory)

    logger.info("VR teleop listening on ws://%s:%s/vr (path ignored)", host, port)
    async with serve(handler, host, port):
        await asyncio.Future()  # run forever
