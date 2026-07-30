"""コントローラ姿勢差分 → LIBERO 相対 7D action。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from parc.vr.protocol import Pose


def _quat_normalize(q: np.ndarray) -> np.ndarray:
    """四元数 (x,y,z,w) を正規化する。"""
    n = float(np.linalg.norm(q))
    if n < 1e-12:
        return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return (q / n).astype(np.float64)


def _quat_conjugate(q: np.ndarray) -> np.ndarray:
    """四元数共役。"""
    return np.array([-q[0], -q[1], -q[2], q[3]], dtype=np.float64)


def _quat_multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """四元数積 a ⊗ b（両方 x,y,z,w）。"""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array(
        [
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        ],
        dtype=np.float64,
    )


def _quat_to_axis_angle(q: np.ndarray) -> np.ndarray:
    """単位四元数 → axis-angle (3,)。"""
    q = _quat_normalize(q)
    # 最短回転のため w>=0 に揃える
    if q[3] < 0.0:
        q = -q
    w = float(np.clip(q[3], -1.0, 1.0))
    den = float(np.sqrt(max(1.0 - w * w, 0.0)))
    if den < 1e-10:
        return np.zeros(3, dtype=np.float64)
    angle = 2.0 * float(np.arccos(w))
    axis = q[:3] / den
    return axis * angle


@dataclass
class ActionMapConfig:
    """相対変位のスケールとクリップ。"""

    pos_scale: float = 1.0
    rot_scale: float = 1.0
    max_pos: float = 0.05
    max_rot: float = 0.5

    @classmethod
    def from_mapping(cls, raw: dict[str, float] | None) -> "ActionMapConfig":
        """YAML/辞書から設定を復元する。"""
        data = raw or {}
        return cls(
            pos_scale=float(data.get("pos_scale", 1.0)),
            rot_scale=float(data.get("rot_scale", 1.0)),
            max_pos=float(data.get("max_pos", 0.05)),
            max_rot=float(data.get("max_rot", 0.5)),
        )

    def to_mapping(self) -> dict[str, float]:
        """設定をシリアライズしやすい dict にする。"""
        return {
            "pos_scale": self.pos_scale,
            "rot_scale": self.rot_scale,
            "max_pos": self.max_pos,
            "max_rot": self.max_rot,
        }


@dataclass
class PoseActionMapper:
    """前フレーム姿勢との差分から action7 を作る。

    action = [dx, dy, dz, dax, day, daz, gripper]
    gripper はトリガ [0,1] を [-1,1] へ線形写像（開→閉）。
    """

    config: ActionMapConfig
    _prev: Pose | None = None

    def reset(self) -> None:
        """基準姿勢を忘れる（エピソード開始時など）。"""
        self._prev = None

    def map(self, pose: Pose, gripper: float) -> np.ndarray:
        """現在姿勢から 7D action を返す。初回はゼロ移動。"""
        cfg = self.config
        g = float(np.clip(gripper, 0.0, 1.0))
        grip_cmd = g * 2.0 - 1.0

        curr_pos = np.asarray(pose.pos, dtype=np.float64).reshape(3)
        curr_quat = _quat_normalize(np.asarray(pose.quat, dtype=np.float64).reshape(4))

        if self._prev is None:
            self._prev = Pose(
                pos=(float(curr_pos[0]), float(curr_pos[1]), float(curr_pos[2])),
                quat=(
                    float(curr_quat[0]),
                    float(curr_quat[1]),
                    float(curr_quat[2]),
                    float(curr_quat[3]),
                ),
            )
            return np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, grip_cmd], dtype=np.float32)

        prev_pos = np.asarray(self._prev.pos, dtype=np.float64)
        prev_quat = _quat_normalize(np.asarray(self._prev.quat, dtype=np.float64))

        dpos = (curr_pos - prev_pos) * cfg.pos_scale
        dpos = np.clip(dpos, -cfg.max_pos, cfg.max_pos)

        # q_rel = q_curr ⊗ q_prev^{-1}
        q_rel = _quat_multiply(curr_quat, _quat_conjugate(prev_quat))
        drot = _quat_to_axis_angle(q_rel) * cfg.rot_scale
        drot = np.clip(drot, -cfg.max_rot, cfg.max_rot)

        self._prev = Pose(
            pos=(float(curr_pos[0]), float(curr_pos[1]), float(curr_pos[2])),
            quat=(
                float(curr_quat[0]),
                float(curr_quat[1]),
                float(curr_quat[2]),
                float(curr_quat[3]),
            ),
        )

        action = np.concatenate([dpos, drot, np.array([grip_cmd])]).astype(np.float32)
        return action
