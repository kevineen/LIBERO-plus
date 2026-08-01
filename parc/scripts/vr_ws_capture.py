#!/usr/bin/env python3
"""WS サーバから映像を数枚受信して PNG 保存する（Unity 無しの映像確認）。

例:
  uv run scripts/vr_ws_capture.py --url ws://127.0.0.1:8765 --out /tmp/vr_cap
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path


async def _run(url: str, out: Path, max_frames: int) -> None:
    import numpy as np
    import websockets
    from PIL import Image

    from parc.vr.protocol import unpack_jpeg_frame, unpack_rgb_frame

    out.mkdir(parents=True, exist_ok=True)
    n = 0
    async with websockets.connect(url, max_size=16 * 1024 * 1024, open_timeout=120) as ws:
        async def _pump_control() -> None:
            t = 0.0
            while n < max_frames:
                msg = {
                    "type": "control",
                    "t": t,
                    "pose": {"pos": [0.0, 0.0, 0.0], "quat": [0.0, 0.0, 0.0, 1.0]},
                    "gripper": 0.0,
                    "buttons": {},
                }
                await ws.send(json.dumps(msg))
                t += 0.05
                await asyncio.sleep(0.05)

        pump = asyncio.create_task(_pump_control())
        try:
            while n < max_frames:
                raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
                if isinstance(raw, str):
                    print("json:", raw[:120])
                    continue
                data = bytes(raw)
                if not data:
                    continue
                if data[0] in (0x11, 0x12):
                    cam_id, w, h, rgb = unpack_rgb_frame(data)
                    cam = "front" if cam_id == 0x11 else "wrist"
                    arr = np.frombuffer(rgb, dtype=np.uint8).reshape(h, w, 3)
                    path = out / f"{n:03d}_{cam}.png"
                    Image.fromarray(arr, mode="RGB").save(path)
                    print(f"saved {path} rgb {w}x{h}")
                    n += 1
                    continue
                if data[0] in (0x01, 0x02):
                    cam_id, jpeg = unpack_jpeg_frame(data)
                    cam = "front" if cam_id == 0x01 else "wrist"
                    if jpeg[:2] != b"\xff\xd8":
                        print(f"BAD JPEG cam={cam} len={len(jpeg)}")
                        continue
                    import io

                    img = Image.open(io.BytesIO(jpeg))
                    path = out / f"{n:03d}_{cam}.png"
                    img.save(path)
                    print(f"saved {path} jpeg size={img.size}")
                    n += 1
                    continue
                print(f"skip binary len={len(data)} head={data[:4]!r}")
        finally:
            pump.cancel()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default="ws://127.0.0.1:8765")
    p.add_argument("--out", type=Path, default=Path("/tmp/vr_cap"))
    p.add_argument("--max-frames", type=int, default=6)
    args = p.parse_args()
    asyncio.run(_run(args.url, args.out, args.max_frames))


if __name__ == "__main__":
    main()
