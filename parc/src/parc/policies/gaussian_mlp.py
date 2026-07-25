"""状態観測 → 対角ガウス方策（GRPO/GSPO スモーク用）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import math

from parc.policies.base import Policy


def _obs_state(obs: dict[str, Any], state_dim: int = 8) -> np.ndarray:
    """LIBERO / LeRobot 互換の state ベクトルを取り出す。"""
    for key in ("robot0_eef_pos", "ee_pos", "eef_pos"):
        if key not in obs:
            continue
        eef = np.asarray(obs[key], dtype=np.float32).reshape(-1)
        aa = obs.get("robot0_eef_quat")
        if aa is None:
            aa = obs.get("robot0_eef_mat")
        grip = obs.get("robot0_gripper_qpos")
        parts = [eef[:3]]
        if aa is not None:
            parts.append(np.asarray(aa, dtype=np.float32).reshape(-1)[:3])
        else:
            parts.append(np.zeros(3, dtype=np.float32))
        if grip is not None:
            parts.append(np.asarray(grip, dtype=np.float32).reshape(-1)[:2])
        else:
            parts.append(np.zeros(2, dtype=np.float32))
        vec = np.concatenate(parts)
        if vec.shape[0] >= state_dim:
            return vec[:state_dim]
        return np.pad(vec, (0, state_dim - vec.shape[0]))
    if "observation.state" in obs:
        return np.asarray(obs["observation.state"], dtype=np.float32).reshape(-1)[:state_dim]
    if "state" in obs:
        return np.asarray(obs["state"], dtype=np.float32).reshape(-1)[:state_dim]
    return np.zeros(state_dim, dtype=np.float32)


class GaussianMLPPolicy(Policy):
    """小さな MLP + 対角ガウス（torch）。評価・学習の両方で使う。"""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        state_dim: int = 8,
        action_dim: int = 7,
        hidden: int = 128,
        device: str | None = None,
        deterministic: bool = False,
    ):
        import torch

        self.action_dim = action_dim
        self.state_dim = state_dim
        self.hidden = hidden
        self.deterministic = deterministic
        self._torch = torch
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        self.net = self._build_net(state_dim, action_dim, hidden).to(self.device)
        self._path = Path(path) if path else None
        if self._path is not None:
            self.load(self._path)

    def _build_net(self, state_dim: int, action_dim: int, hidden: int) -> Any:
        """状態次元・隠れ層に合わせた MLP を生成する。"""
        import torch
        import torch.nn as nn

        class Net(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.body = nn.Sequential(
                    nn.Linear(state_dim, hidden),
                    nn.Tanh(),
                    nn.Linear(hidden, hidden),
                    nn.Tanh(),
                )
                self.mean = nn.Linear(hidden, action_dim)
                self.log_std = nn.Parameter(torch.zeros(action_dim))

            def forward(self, x: Any) -> tuple[Any, Any]:
                h = self.body(x)
                return self.mean(h), self.log_std.clamp(-5.0, 2.0)

        return Net()

    def reset(self) -> None:
        return None

    def act(self, obs: dict[str, Any]) -> np.ndarray:
        torch = self._torch
        s = _obs_state(obs, self.state_dim)
        with torch.no_grad():
            x = torch.as_tensor(s, device=self.device).unsqueeze(0)
            mean, log_std = self.net(x)
            if self.deterministic:
                a = mean
            else:
                std = log_std.exp()
                a = mean + std * torch.randn_like(mean)
            a = a.squeeze(0).cpu().numpy().astype(np.float32)
        # gripper は [-1, 1] 付近にクリップ
        a = np.clip(a, -1.0, 1.0)
        return a

    def log_prob_actions(
        self,
        states: Any,
        actions: Any,
    ) -> Any:
        """token(=action dim) ごとの log π。shape (B, T, A) または (B, A)。"""
        torch = self._torch
        mean, log_std = self.net(states)
        std = log_std.exp()
        # broadcast
        var = std**2
        log_prob = -0.5 * (
            ((actions - mean) ** 2) / (var + 1e-8)
            + 2 * log_std
            + math.log(2 * math.pi)
        )
        return log_prob

    def save(self, directory: str | Path) -> Path:
        """pretrained_model 風ディレクトリへ保存。"""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        ckpt = directory / "grpo_policy.pt"
        self._torch.save(
            {
                "state_dict": self.net.state_dict(),
                "state_dim": self.state_dim,
                "action_dim": self.action_dim,
                "hidden": self.hidden,
            },
            ckpt,
        )
        meta = {
            "type": "grpo_gaussian",
            "state_dim": self.state_dim,
            "action_dim": self.action_dim,
            "hidden": self.hidden,
        }
        (directory / "parc_policy.json").write_text(json.dumps(meta, indent=2))
        return directory

    def load(self, directory: str | Path) -> None:
        directory = Path(directory)
        ckpt = directory / "grpo_policy.pt"
        if not ckpt.is_file():
            ckpt = directory / "policy.pt"
        if not ckpt.is_file():
            raise FileNotFoundError(f"no grpo_policy.pt under {directory}")
        blob = self._torch.load(ckpt, map_location=self.device, weights_only=False)
        # ckpt / parc_policy.json の次元を優先（train.hidden と eval デフォルト差を吸収）
        state_dim = int(blob.get("state_dim", self.state_dim))
        action_dim = int(blob.get("action_dim", self.action_dim))
        hidden = blob.get("hidden")
        meta_path = directory / "parc_policy.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text())
            state_dim = int(meta.get("state_dim", state_dim))
            action_dim = int(meta.get("action_dim", action_dim))
            if meta.get("hidden") is not None:
                hidden = int(meta["hidden"])
        # 古い ckpt に hidden が無い場合は weight 形状から推定
        if hidden is None:
            w0 = blob["state_dict"].get("body.0.weight")
            if w0 is not None:
                hidden = int(w0.shape[0])
                state_dim = int(w0.shape[1])
            mean_w = blob["state_dict"].get("mean.weight")
            if mean_w is not None:
                action_dim = int(mean_w.shape[0])
            hidden = int(hidden if hidden is not None else self.hidden)
        else:
            hidden = int(hidden)
        if (state_dim, action_dim, hidden) != (self.state_dim, self.action_dim, self.hidden):
            self.state_dim = state_dim
            self.action_dim = action_dim
            self.hidden = hidden
            self.net = self._build_net(state_dim, action_dim, hidden).to(self.device)
        self.net.load_state_dict(blob["state_dict"])
