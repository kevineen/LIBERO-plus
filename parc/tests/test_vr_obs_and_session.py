"""obs_util / video / fake session の単体テスト。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from parc.vr.obs_util import extract_state8, flip_image_180, obs_to_frame_dict
from parc.vr.recorder import EpisodeRecorder
from parc.vr.session import run_fake_episode
from parc.vr.video import rgb_to_jpeg


def _fake_obs(h: int = 32, w: int = 32) -> dict:
    return {
        "agentview_image": np.full((h, w, 3), 10, dtype=np.uint8),
        "robot0_eye_in_hand_image": np.full((h, w, 3), 20, dtype=np.uint8),
        "robot0_eef_pos": np.array([0.1, 0.2, 0.3], dtype=np.float32),
        "robot0_eef_quat": np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
        "robot0_gripper_qpos": np.array([0.04, -0.04], dtype=np.float32),
    }


def test_extract_state8_shape():
    state = extract_state8(_fake_obs())
    assert state.shape == (8,)
    np.testing.assert_allclose(state[:3], [0.1, 0.2, 0.3])


def test_flip_image_180():
    img = np.zeros((4, 4, 3), dtype=np.uint8)
    img[0, 0] = [1, 2, 3]
    out = flip_image_180(img)
    np.testing.assert_array_equal(out[-1, -1], [1, 2, 3])


def test_obs_to_frame_dict_keys():
    action = np.zeros(7, dtype=np.float32)
    fr = obs_to_frame_dict(_fake_obs(), action, flip_images=True)
    assert fr["front"].shape == (32, 32, 3)
    assert fr["state"].shape == (8,)
    assert fr["action"].shape == (7,)


def test_rgb_to_jpeg_roundtrip_header():
    rgb = np.zeros((16, 16, 3), dtype=np.uint8)
    rgb[0, 0] = [255, 0, 0]
    jpeg = rgb_to_jpeg(rgb, quality=50)
    assert jpeg[:2] == b"\xff\xd8"


def test_frame_buffer_and_recorder_without_lerobot(tmp_path: Path):
    rec = EpisodeRecorder(root=tmp_path, create_dataset=False, image_size=(32, 32))
    rec.start_episode("demo")
    for _ in range(4):
        rec.add_frame(
            {
                "front": np.zeros((32, 32, 3), dtype=np.uint8),
                "wrist": np.zeros((32, 32, 3), dtype=np.uint8),
                "state": np.zeros(8, dtype=np.float32),
                "action": np.zeros(7, dtype=np.float32),
            }
        )
    idx = rec.save_episode()
    assert idx == 0
    assert rec.buffer.num_frames == 0


def test_run_fake_episode(tmp_path: Path):
    n = run_fake_episode(
        dataset_root=tmp_path,
        num_frames=8,
        create_dataset=False,
        image_size=(32, 32),
    )
    assert n == 1
