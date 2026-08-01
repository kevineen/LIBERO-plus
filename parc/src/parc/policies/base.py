"""方策インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class Policy(ABC):
    """観測 dict → アクションを返す方策（次元は backend / YAML の action_dim）。"""

    action_dim: int = 7

    @abstractmethod
    def reset(self) -> None:
        """エピソード開始時のリセット。"""

    @abstractmethod
    def act(self, obs: dict[str, Any]) -> np.ndarray:
        """1 ステップ分のアクションを返す。shape=(action_dim,)"""


class RandomPolicy(Policy):
    """デバッグ用のランダム方策（成功率はほぼ 0 想定）。"""

    def __init__(self, action_dim: int = 7, seed: int = 0, scale: float = 0.1):
        self.action_dim = action_dim
        self.scale = scale
        self._rng = np.random.default_rng(seed)

    def reset(self) -> None:
        return None

    def act(self, obs: dict[str, Any]) -> np.ndarray:
        # gripper は最後の次元。小さなデルタ動作にする
        a = self._rng.uniform(-self.scale, self.scale, size=self.action_dim)
        a[-1] = self._rng.choice([-1.0, 1.0])
        return a.astype(np.float32)


class ZeroPolicy(Policy):
    """ゼロアクション（環境が動くかの確認用）。"""

    def __init__(self, action_dim: int = 7):
        self.action_dim = action_dim

    def reset(self) -> None:
        return None

    def act(self, obs: dict[str, Any]) -> np.ndarray:
        return np.zeros(self.action_dim, dtype=np.float32)


def build_policy(cfg: dict[str, Any], seed: int = 0) -> Policy:
    """実験 YAML の policy セクションから方策を構築する。"""
    ptype = (cfg or {}).get("type", "random")
    action_dim = int((cfg or {}).get("action_dim", 7))
    if ptype == "random":
        return RandomPolicy(action_dim=action_dim, seed=seed)
    if ptype == "zero":
        return ZeroPolicy(action_dim=action_dim)
    if ptype in {"checkpoint", "lerobot"}:
        # LeRobot pretrained_model（SmolVLA 等）。robot venv + eval_ckpt.sh で実行する。
        path = (cfg or {}).get("path")
        if not path:
            raise ValueError("policy.path に pretrained_model ディレクトリを指定してください")
        from parc.policies.lerobot_ckpt import LeRobotCheckpointPolicy

        return LeRobotCheckpointPolicy(
            path,
            device=(cfg or {}).get("device"),
            action_dim=action_dim,
            flip_images=bool((cfg or {}).get("flip_images", True)),
            default_task=str((cfg or {}).get("default_task", "")),
        )
    if ptype in {"grpo_gaussian", "gaussian", "gspo_gaussian"}:
        path = (cfg or {}).get("path")
        from parc.policies.gaussian_mlp import GaussianMLPPolicy

        return GaussianMLPPolicy(
            path=path,
            state_dim=int((cfg or {}).get("state_dim", 8)),
            action_dim=action_dim,
            hidden=int((cfg or {}).get("hidden", 128)),
            device=(cfg or {}).get("device"),
            deterministic=bool((cfg or {}).get("deterministic", True)),
        )
    if ptype in {"openpi", "openvla", "lerobot_cmd"}:
        # 本選配布・独自ラッパ差し込み用
        path = (cfg or {}).get("path")
        raise NotImplementedError(
            f"policy.type={ptype!r} はまだ未接続です。"
            f" path={path!r} を parc.policies に実装するか、"
            "ランダム/ゼロで評価パイプラインを先に通してください。"
        )
    raise ValueError(f"Unknown policy.type: {ptype}")
