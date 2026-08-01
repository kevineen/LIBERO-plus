"""Quest 向け WebSocket テレオプサーバ。"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Sequence

from parc.vr.action_map import ActionMapConfig
from parc.vr.env_factory import TeleopEnvBundle, make_teleop_env
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

    def _enqueue(payload: str | bytes) -> None:
        """イベントループスレッド上でキューへ積む。"""
        outbound.put_nowait(payload)

    def send_sync(payload: str | bytes) -> None:
        """任意スレッドから送信用キューへ積む（WS 送信は writer のみ）。

        直接 websocket.send と並行するとフレームが壊れ、Quest でテレビノイズになる。
        """
        loop.call_soon_threadsafe(_enqueue, payload)

    async def writer() -> None:
        """キューから WebSocket へ送る（唯一の送信者）。"""
        while True:
            payload = await outbound.get()
            await websocket.send(payload)

    writer_task = asyncio.create_task(writer())
    try:
        # 接続直後に loading を送り、LIBERO 初期化中の keepalive 切断を避ける
        send_sync('{"type":"status","recording":false,"frame_count":0,"message":"loading env"}')
        # LIBERO 生成は数十秒ブロックし得る → イベントループを止めない
        session = await loop.run_in_executor(None, session_factory, send_sync)
    except Exception:
        writer_task.cancel()
        raise
    try:
        send_sync(
            encode_message(
                HelloMessage(
                    fps=session.config.fps,
                    jpeg_quality=session.config.jpeg_quality,
                )
            )
        )
        send_sync(
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

        try:
            async for raw in websocket:
                if isinstance(raw, bytes):
                    send_sync(
                        encode_message(
                            ErrorMessage(
                                code="unexpected_binary",
                                message="client binary not supported",
                            )
                        )
                    )
                    continue
                try:
                    msg = parse_client_message(raw)
                except Exception as exc:  # noqa: BLE001 — クライアント入力は雑多
                    send_sync(
                        encode_message(ErrorMessage(code="bad_message", message=str(exc)))
                    )
                    continue

                if isinstance(msg, PingMessage):
                    # msg.t = クライアント送信時刻（unix 秒）。片道遅延 ≈ now - t
                    now = time.time()
                    if msg.t > 0:
                        rtt_ms = max(0.0, (now - float(msg.t)) * 1000.0)
                        session.record_rtt(rtt_ms)
                    send_sync(encode_message(PongMessage(t=msg.t)))
                    continue

                if isinstance(msg, ControlMessage):
                    # env.step / JPEG エンコードはブロッキングし得るので executor へ。
                    # 送信自体は send_sync → writer のみ（並行 send 禁止）。
                    await loop.run_in_executor(None, session.handle_control, msg)
                    await loop.run_in_executor(None, session.emit_video)
        except Exception as exc:
            # Quest 切断時は close frame 無しが多く、ハンドラ失敗ログを抑える
            if type(exc).__name__ in {"ConnectionClosed", "ConnectionClosedError", "ConnectionClosedOK"}:
                logger.info("VR client disconnected: %s", exc)
            else:
                raise

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
    require_success: bool = False,
    init_state_mode: str = "cycle",
    task_ids: Sequence[int] | None = None,
    operator_id: str = "",
    device_id: str = "",
    location: str = "",
    calib_override_path: str = "",
    max_rtt_ms: float = 150.0,
    latency_policy: str = "degraded",
    approx_time_slop_ms: float = 100.0,
    collection_queue: Sequence[dict[str, Any]] | None = None,
    min_success_per_category: int = 0,
) -> Any:
    """接続ごとに TeleopSession を作るファクトリ。"""
    ids = list(task_ids) if task_ids else [task_id]
    queue = [dict(x) for x in collection_queue] if collection_queue else []

    def remake(suite_name: str, tid: int) -> TeleopEnvBundle:
        return make_teleop_env(
            suite_name,
            tid,
            camera_height=camera_height,
            camera_width=camera_width,
            fake=fake,
        )

    def factory(send_sync: Any) -> TeleopSession:
        bundle = remake(suite, task_id)
        cfg = TeleopSessionConfig(
            suite=suite,
            task_id=bundle.task_id,
            language=bundle.language,
            fps=fps,
            jpeg_quality=jpeg_quality,
            flip_images=flip_images,
            image_size=image_size,
            action_map=action_map,
            dataset_root=host_dataset_root,
            repo_id=repo_id,
            create_dataset=create_dataset,
            require_success=require_success,
            init_state_mode=init_state_mode,
            task_ids=ids,
            camera_height=camera_height,
            camera_width=camera_width,
            fake=fake,
            operator_id=operator_id,
            device_id=device_id,
            location=location,
            calib_override_path=calib_override_path,
            max_rtt_ms=max_rtt_ms,
            latency_policy=latency_policy,
            approx_time_slop_ms=approx_time_slop_ms,
            collection_queue=queue,
            min_success_per_category=min_success_per_category,
        )
        return TeleopSession(
            env=bundle.env,
            config=cfg,
            send=send_sync,
            init_states=list(bundle.init_states),
            remake_env=remake,
        )

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
    require_success: bool = False,
    init_state_mode: str = "cycle",
    task_ids: Sequence[int] | None = None,
    operator_id: str = "",
    device_id: str = "",
    location: str = "",
    calib_override_path: str = "",
    max_rtt_ms: float = 150.0,
    latency_policy: str = "degraded",
    approx_time_slop_ms: float = 100.0,
    collection_queue: Sequence[dict[str, Any]] | None = None,
    min_success_per_category: int = 0,
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
        require_success=require_success,
        init_state_mode=init_state_mode,
        task_ids=task_ids,
        operator_id=operator_id,
        device_id=device_id,
        location=location,
        calib_override_path=calib_override_path,
        max_rtt_ms=max_rtt_ms,
        latency_policy=latency_policy,
        approx_time_slop_ms=approx_time_slop_ms,
        collection_queue=collection_queue,
        min_success_per_category=min_success_per_category,
    )

    async def handler(websocket: Any) -> None:
        await _handle_client(websocket, session_factory=factory)

    logger.info("VR teleop listening on ws://%s:%s/vr (path ignored)", host, port)
    # LIBERO env 初期化が 20s 超えると既定 ping_timeout で 1011 ServerError になる。
    # テレオプはアプリ層 control で生存確認するため、WS keepalive は無効化。
    async with serve(handler, host, port, ping_interval=None, ping_timeout=None):
        await asyncio.Future()  # run forever
