"""WebSocket サーバの軽量結合テスト（fake session）。"""

from __future__ import annotations

import asyncio
import json

import pytest

from parc.vr.protocol import CAMERA_FRONT_RGB, unpack_rgb_frame
from parc.vr.server import serve_vr_teleop


@pytest.mark.asyncio
async def test_ws_hello_and_video_on_control(tmp_path):
    """接続 → hello → control → RGB バイナリが返る。"""
    websockets = pytest.importorskip("websockets")

    host = "127.0.0.1"
    port = 18765
    server_task = asyncio.create_task(
        serve_vr_teleop(
            host=host,
            port=port,
            fake=True,
            create_dataset=False,
            dataset_root=tmp_path,
            image_size=(32, 32),
            camera_height=32,
            camera_width=32,
        )
    )
    await asyncio.sleep(0.2)
    try:
        uri = f"ws://{host}:{port}"
        async with websockets.connect(uri) as ws:
            hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert hello["type"] == "hello"
            task = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert task["type"] == "task_info"
            status = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert status["type"] == "status"
            # 接続直後の初期映像 2 枚
            front = await asyncio.wait_for(ws.recv(), timeout=2)
            wrist = await asyncio.wait_for(ws.recv(), timeout=2)
            assert isinstance(front, (bytes, bytearray))
            cam, w, h, rgb = unpack_rgb_frame(bytes(front))
            assert cam == CAMERA_FRONT_RGB
            assert (w, h) == (32, 32)
            assert len(rgb) == 32 * 32 * 3
            assert isinstance(wrist, (bytes, bytearray))

            await ws.send(
                json.dumps(
                    {
                        "type": "control",
                        "t": 0.1,
                        "pose": {"pos": [0, 0, 0], "quat": [0, 0, 0, 1]},
                        "gripper": 0.0,
                        "buttons": {},
                    }
                )
            )
            # control 後にも映像が来る
            got_binary = False
            for _ in range(4):
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                if isinstance(msg, (bytes, bytearray)):
                    got_binary = True
                    break
            assert got_binary
    finally:
        server_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await server_task
