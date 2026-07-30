"""pose → action7 写像の単体テスト。"""

from __future__ import annotations

import numpy as np

from parc.vr.action_map import ActionMapConfig, PoseActionMapper
from parc.vr.protocol import Pose


def test_first_frame_is_zero_motion_with_gripper():
    mapper = PoseActionMapper(ActionMapConfig())
    action = mapper.map(Pose(pos=(0.0, 0.0, 0.0)), gripper=1.0)
    assert action.shape == (7,)
    np.testing.assert_allclose(action[:6], 0.0)
    np.testing.assert_allclose(action[6], 1.0)


def test_open_gripper_maps_to_minus_one():
    mapper = PoseActionMapper(ActionMapConfig())
    action = mapper.map(Pose(), gripper=0.0)
    np.testing.assert_allclose(action[6], -1.0)


def test_position_delta_scaled_and_clipped():
    cfg = ActionMapConfig(pos_scale=1.0, max_pos=0.05)
    mapper = PoseActionMapper(cfg)
    mapper.map(Pose(pos=(0.0, 0.0, 0.0)), gripper=0.5)
    # 0.2m 移動 → max_pos でクリップ
    action = mapper.map(Pose(pos=(0.2, 0.0, 0.0)), gripper=0.5)
    np.testing.assert_allclose(action[0], 0.05, atol=1e-6)
    np.testing.assert_allclose(action[1:6], 0.0, atol=1e-6)


def test_small_translation_passes_through():
    mapper = PoseActionMapper(ActionMapConfig(max_pos=0.05))
    mapper.map(Pose(pos=(0.0, 0.0, 0.0)), gripper=0.0)
    action = mapper.map(Pose(pos=(0.01, -0.02, 0.03)), gripper=0.0)
    np.testing.assert_allclose(action[:3], [0.01, -0.02, 0.03], atol=1e-6)


def test_reset_clears_reference_pose():
    mapper = PoseActionMapper(ActionMapConfig())
    mapper.map(Pose(pos=(1.0, 0.0, 0.0)), gripper=0.0)
    mapper.reset()
    action = mapper.map(Pose(pos=(1.0, 0.0, 0.0)), gripper=0.0)
    np.testing.assert_allclose(action[:6], 0.0)


def test_yaw_rotation_produces_nonzero_axis_angle():
    """z 軸まわり 90° 相当の相対回転で daz が出る。"""
    mapper = PoseActionMapper(ActionMapConfig(max_rot=2.0))
    # identity
    mapper.map(Pose(quat=(0.0, 0.0, 0.0, 1.0)), gripper=0.0)
    # 90 deg about z: quat = (0,0,sin45,cos45)
    s = float(np.sin(np.pi / 4))
    c = float(np.cos(np.pi / 4))
    action = mapper.map(Pose(quat=(0.0, 0.0, s, c)), gripper=0.0)
    assert abs(float(action[5])) > 0.5
    np.testing.assert_allclose(action[:3], 0.0, atol=1e-6)
