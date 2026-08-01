"""VR protocol 単体テスト。"""

from __future__ import annotations

import json

import pytest

from parc.vr.protocol import (
    CAMERA_FRONT,
    CAMERA_WRIST,
    ButtonEdgeTracker,
    Buttons,
    ControlMessage,
    HelloMessage,
    Pose,
    encode_message,
    pack_jpeg_frame,
    parse_client_message,
    unpack_jpeg_frame,
)


def test_parse_control_roundtrip():
    raw = {
        "type": "control",
        "t": 1.5,
        "pose": {"pos": [0.1, 0.2, 0.3], "quat": [0.0, 0.0, 0.0, 1.0]},
        "gripper": 0.75,
        "buttons": {"record": True, "save": False, "discard": False, "reset": False},
    }
    msg = parse_client_message(json.dumps(raw))
    assert isinstance(msg, ControlMessage)
    assert msg.t == 1.5
    assert msg.pose.pos == (0.1, 0.2, 0.3)
    assert msg.gripper == 0.75
    assert msg.buttons.record is True

    encoded = encode_message(msg)
    again = parse_client_message(encoded)
    assert again == msg


def test_gripper_clamped_to_unit_interval():
    msg = parse_client_message(
        {"type": "control", "t": 0, "pose": {}, "gripper": 2.5, "buttons": {}}
    )
    assert isinstance(msg, ControlMessage)
    assert msg.gripper == 1.0


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="unknown"):
        parse_client_message({"type": "nope"})


def test_hello_encode_shape():
    data = json.loads(encode_message(HelloMessage(fps=20, jpeg_quality=60)))
    assert data["type"] == "hello"
    assert data["protocol_version"] == 1
    assert data["video"]["jpeg_quality"] == 60


def test_pack_unpack_jpeg():
    payload = pack_jpeg_frame(CAMERA_FRONT, b"\xff\xd8fake")
    cam, jpeg = unpack_jpeg_frame(payload)
    assert cam == CAMERA_FRONT
    assert jpeg.startswith(b"\xff\xd8")
    with pytest.raises(ValueError):
        pack_jpeg_frame(0x99, b"x")


def test_button_rising_edge_only_once():
    tracker = ButtonEdgeTracker()
    held = Buttons(record=True)
    e1 = tracker.update(held)
    e2 = tracker.update(held)
    assert e1.record is True
    assert e2.record is False
    released = tracker.update(Buttons(record=False))
    assert released.record is False
    again = tracker.update(Buttons(record=True))
    assert again.record is True


def test_wrist_camera_id():
    assert unpack_jpeg_frame(pack_jpeg_frame(CAMERA_WRIST, b"ab"))[0] == CAMERA_WRIST


def test_pack_unpack_rgb():
    from parc.vr.protocol import CAMERA_FRONT_RGB, pack_rgb_frame, unpack_rgb_frame

    rgb = bytes([10, 20, 30] * (4 * 4))
    payload = pack_rgb_frame(CAMERA_FRONT_RGB, rgb, width=4, height=4)
    cam, w, h, out = unpack_rgb_frame(payload)
    assert cam == CAMERA_FRONT_RGB
    assert (w, h) == (4, 4)
    assert out == rgb
