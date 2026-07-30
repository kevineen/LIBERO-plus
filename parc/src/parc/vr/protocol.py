"""WebSocket メッセージの encode / decode（protocol v1）。

仕様の正本: feature/vr-teleop/protocol.md
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

PROTOCOL_VERSION = 1

# Binary video: first byte = camera id
CAMERA_FRONT = 0x01
CAMERA_WRIST = 0x02


@dataclass(frozen=True)
class Pose:
    """コントローラ姿勢。quat は (x, y, z, w)。"""

    pos: tuple[float, float, float] = (0.0, 0.0, 0.0)
    quat: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)


@dataclass(frozen=True)
class Buttons:
    """録画 UI ボタン（サーバ側で rising edge を検出）。"""

    record: bool = False
    save: bool = False
    discard: bool = False
    reset: bool = False


@dataclass(frozen=True)
class ControlMessage:
    """クライアント → サーバの制御フレーム。"""

    t: float
    pose: Pose
    gripper: float
    buttons: Buttons
    type: str = "control"


@dataclass(frozen=True)
class HelloMessage:
    """接続直後のサーバ挨拶。"""

    fps: int
    jpeg_quality: int = 70
    type: str = "hello"
    protocol_version: int = PROTOCOL_VERSION
    video_front: bool = True
    video_wrist: bool = True


@dataclass(frozen=True)
class TaskInfoMessage:
    """現在のタスク情報。"""

    suite: str
    task_id: int
    language: str
    type: str = "task_info"


@dataclass(frozen=True)
class StatusMessage:
    """録画状態の通知。"""

    recording: bool
    frame_count: int
    message: str = ""
    type: str = "status"


@dataclass(frozen=True)
class EpisodeSavedMessage:
    """エピソード保存完了。"""

    episode_index: int
    num_frames: int
    dataset_root: str
    success: bool = True
    init_state_index: int = 0
    type: str = "episode_saved"


@dataclass(frozen=True)
class EpisodeDiscardedMessage:
    """エピソード破棄。"""

    reason: str = "user"
    type: str = "episode_discarded"


@dataclass(frozen=True)
class ErrorMessage:
    """エラー通知。"""

    code: str
    message: str
    type: str = "error"


@dataclass(frozen=True)
class PingMessage:
    """往復遅延測定用。"""

    t: float
    type: str = "ping"


@dataclass(frozen=True)
class PongMessage:
    """ping 応答。"""

    t: float
    type: str = "pong"


ClientMessage = ControlMessage | PingMessage
ServerMessage = (
    HelloMessage
    | TaskInfoMessage
    | StatusMessage
    | EpisodeSavedMessage
    | EpisodeDiscardedMessage
    | ErrorMessage
    | PongMessage
)


def _as_float_tuple(values: Any, n: int) -> tuple[float, ...]:
    """リスト／タプルを長さ n の float タプルにする。"""
    if not isinstance(values, (list, tuple)) or len(values) != n:
        raise ValueError(f"expected length-{n} sequence, got {values!r}")
    return tuple(float(v) for v in values)


def parse_client_message(raw: str | bytes | Mapping[str, Any]) -> ClientMessage:
    """クライアント JSON を型付きメッセージへ変換する。"""
    if isinstance(raw, (str, bytes)):
        data = json.loads(raw)
    else:
        data = dict(raw)

    msg_type = data.get("type")
    if msg_type == "ping":
        return PingMessage(t=float(data.get("t", 0.0)))
    if msg_type != "control":
        raise ValueError(f"unknown client message type: {msg_type!r}")

    pose_raw = data.get("pose") or {}
    buttons_raw = data.get("buttons") or {}
    pos = _as_float_tuple(pose_raw.get("pos", (0.0, 0.0, 0.0)), 3)
    quat = _as_float_tuple(pose_raw.get("quat", (0.0, 0.0, 0.0, 1.0)), 4)
    pose = Pose(
        pos=(pos[0], pos[1], pos[2]),
        quat=(quat[0], quat[1], quat[2], quat[3]),
    )
    buttons = Buttons(
        record=bool(buttons_raw.get("record", False)),
        save=bool(buttons_raw.get("save", False)),
        discard=bool(buttons_raw.get("discard", False)),
        reset=bool(buttons_raw.get("reset", False)),
    )
    gripper = float(data.get("gripper", 0.0))
    gripper = max(0.0, min(1.0, gripper))
    return ControlMessage(
        t=float(data.get("t", 0.0)),
        pose=pose,
        gripper=gripper,
        buttons=buttons,
    )


def encode_message(msg: ClientMessage | ServerMessage) -> str:
    """メッセージを JSON 文字列にする。"""
    if isinstance(msg, HelloMessage):
        payload = {
            "type": "hello",
            "protocol_version": msg.protocol_version,
            "fps": msg.fps,
            "video": {
                "front": msg.video_front,
                "wrist": msg.video_wrist,
                "jpeg_quality": msg.jpeg_quality,
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    if isinstance(msg, ControlMessage):
        payload = {
            "type": "control",
            "t": msg.t,
            "pose": {"pos": list(msg.pose.pos), "quat": list(msg.pose.quat)},
            "gripper": msg.gripper,
            "buttons": asdict(msg.buttons),
        }
        return json.dumps(payload, ensure_ascii=False)

    return json.dumps(asdict(msg), ensure_ascii=False)


def pack_jpeg_frame(camera_id: int, jpeg_bytes: bytes) -> bytes:
    """カメラ ID + JPEG をバイナリフレームに詰める。"""
    if camera_id not in (CAMERA_FRONT, CAMERA_WRIST):
        raise ValueError(f"invalid camera_id: {camera_id}")
    return bytes([camera_id]) + jpeg_bytes


def unpack_jpeg_frame(payload: bytes) -> tuple[int, bytes]:
    """バイナリフレームを (camera_id, jpeg) に分解する。"""
    if len(payload) < 2:
        raise ValueError("video frame too short")
    return int(payload[0]), payload[1:]


@dataclass
class ButtonEdgeTracker:
    """前回ボタン状態から rising edge を検出する。"""

    _prev: Buttons = field(default_factory=Buttons)

    def update(self, buttons: Buttons) -> Buttons:
        """rising edge だけ True の Buttons を返す。"""
        edges = Buttons(
            record=buttons.record and not self._prev.record,
            save=buttons.save and not self._prev.save,
            discard=buttons.discard and not self._prev.discard,
            reset=buttons.reset and not self._prev.reset,
        )
        self._prev = buttons
        return edges
