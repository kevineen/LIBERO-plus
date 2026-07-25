"""LeRobot 学習済みチェックポイント（SmolVLA 等）を parc Policy として使う。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from parc.paths import PARC_ROOT
from parc.policies.base import Policy


def _resolve_ckpt_dir(path: str | Path) -> Path:
    """pretrained_model ディレクトリを解決する。"""
    raw = Path(path).expanduser()
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append((PARC_ROOT / raw).resolve())
        candidates.append(raw.resolve())

    for p in candidates:
        if (p / "config.json").is_file() and (p / "model.safetensors").is_file():
            return p
        # checkpoints/000200/ を渡された場合
        nested = p / "pretrained_model"
        if (nested / "config.json").is_file():
            return nested
    raise FileNotFoundError(
        f"LeRobot checkpoint が見つかりません: {path} "
        "(config.json + model.safetensors が必要)"
    )


def _quat2axisangle(quat: np.ndarray) -> np.ndarray:
    """四元数 (x,y,z,w) → axis-angle (3,)。LiberoProcessor と同等。"""
    q = np.asarray(quat, dtype=np.float64).reshape(4)
    w = float(np.clip(q[3], -1.0, 1.0))
    den = float(np.sqrt(max(1.0 - w * w, 0.0)))
    if den < 1e-10:
        return np.zeros(3, dtype=np.float32)
    angle = 2.0 * float(np.arccos(w))
    axis = q[:3] / den
    return (axis * angle).astype(np.float32)


def raw_libero_obs_to_batch(
    obs: dict[str, Any],
    *,
    task: str,
    flip_images: bool = True,
) -> dict[str, Any]:
    """OffScreenRenderEnv の生観測 → SmolVLA / libero_plus 形式のバッチ dict。

    - images: observation.images.front / wrist  (B,C,H,W) float32 [0,1]
    - state:  eef_pos(3) + axisangle(3) + gripper_qpos(2)
    - task:   言語指示文字列（tokenizer が読む）
    """
    import torch

    def _img(key: str) -> "torch.Tensor":
        arr = np.asarray(obs[key])
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        t = torch.from_numpy(arr).unsqueeze(0)  # 1,H,W,C
        t = t.permute(0, 3, 1, 2).contiguous().float() / 255.0
        if flip_images:
            # HuggingFaceVLA/libero 系（180° 回転）
            t = torch.flip(t, dims=[2, 3])
        return t

    eef_pos = np.asarray(obs["robot0_eef_pos"], dtype=np.float32).reshape(3)
    eef_quat = np.asarray(obs["robot0_eef_quat"], dtype=np.float32).reshape(4)
    grip = np.asarray(obs["robot0_gripper_qpos"], dtype=np.float32).reshape(-1)
    if grip.size == 1:
        grip = np.array([grip[0], -grip[0]], dtype=np.float32)
    state = np.concatenate([eef_pos, _quat2axisangle(eef_quat), grip[:2]], axis=0)

    return {
        "observation.images.front": _img("agentview_image"),
        "observation.images.wrist": _img("robot0_eye_in_hand_image"),
        "observation.state": torch.from_numpy(state).unsqueeze(0).float(),
        "task": task,
    }


class LeRobotCheckpointPolicy(Policy):
    """LeRobot `pretrained_model` ディレクトリを読み、act() で推論する。"""

    action_dim: int = 7

    def __init__(
        self,
        path: str | Path,
        *,
        device: str | None = None,
        action_dim: int = 7,
        flip_images: bool = True,
        default_task: str = "",
    ):
        import torch
        from lerobot.policies.factory import make_pre_post_processors
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

        self.action_dim = action_dim
        self.flip_images = flip_images
        self._task = default_task
        self.ckpt_dir = _resolve_ckpt_dir(path)

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        # from_pretrained は config.json の device を尊重するので上書きする
        self.policy = SmolVLAPolicy.from_pretrained(str(self.ckpt_dir))
        self.policy.to(self.device)
        self.policy.eval()
        self.policy.config.device = self.device

        preprocessor_overrides = {
            "device_processor": {"device": self.device},
        }
        self.preprocessor, self.postprocessor = make_pre_post_processors(
            policy_cfg=self.policy.config,
            pretrained_path=str(self.ckpt_dir),
            preprocessor_overrides=preprocessor_overrides,
        )

    def set_task(self, task: str) -> None:
        """エピソードの言語指示をセットする。"""
        self._task = task

    def reset(self) -> None:
        self.policy.reset()

    def act(self, obs: dict[str, Any]) -> np.ndarray:
        import torch

        task = str(obs.get("task") or self._task or "")
        if not task:
            raise ValueError(
                "言語指示が空です。runner から task.language を渡すか set_task() してください。"
            )

        batch = raw_libero_obs_to_batch(obs, task=task, flip_images=self.flip_images)
        batch = self.preprocessor(batch)
        with torch.inference_mode():
            action = self.policy.select_action(batch)
        action = self.postprocessor(action)

        if hasattr(action, "detach"):
            action_np = action.detach().to("cpu").numpy()
        else:
            action_np = np.asarray(action)
        action_np = np.asarray(action_np, dtype=np.float32).reshape(-1)
        if action_np.size < self.action_dim:
            raise RuntimeError(f"action dim too small: {action_np.shape}")
        return action_np[: self.action_dim]
