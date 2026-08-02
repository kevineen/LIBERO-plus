"""MolmoAct2（HF transformers）を parc Policy として使うアダプタ。

LeRobot 0.5.1 には ``policy.type=molmoact2`` が無いため、公式
``allenai/MolmoAct2-LIBERO`` の ``predict_action`` API を直接呼ぶ。
学習（LeRobot main + ``--extra molmoact2``）はサイドカー扱い（設計ドキュメント参照）。
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
from PIL import Image

from parc.policies.base import Policy
from parc.policies.lerobot_ckpt import _quat2axisangle


def _libero_state_from_obs(obs: dict[str, Any]) -> np.ndarray:
    """OffScreenRenderEnv 観測 → MolmoAct2/LIBERO の state (8,)。

    eef_pos(3) + axis-angle(3) + gripper_qpos(2)。公式サンプルと同順。
    """
    eef_pos = np.asarray(obs["robot0_eef_pos"], dtype=np.float32).reshape(3)
    eef_quat = np.asarray(obs["robot0_eef_quat"], dtype=np.float32).reshape(4)
    grip = np.asarray(obs["robot0_gripper_qpos"], dtype=np.float32).reshape(-1)
    if grip.size == 1:
        grip = np.array([grip[0], -grip[0]], dtype=np.float32)
    return np.concatenate([eef_pos, _quat2axisangle(eef_quat), grip[:2]], axis=0)


def _obs_rgb_to_pil(obs: dict[str, Any], key: str, *, flip: bool) -> Image.Image:
    """環境 RGB → PIL。flip=True なら HuggingFaceVLA/libero 系の 180° 回転。"""
    arr = np.asarray(obs[key])
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if flip:
        arr = np.ascontiguousarray(arr[::-1, ::-1])
    return Image.fromarray(arr, mode="RGB")


class MolmoAct2HFPolicy(Policy):
    """``AutoModelForImageTextToText.predict_action`` で連続アクションを出す。"""

    action_dim: int = 7

    def __init__(
        self,
        path: str = "allenai/MolmoAct2-LIBERO",
        *,
        device: str | None = None,
        action_dim: int = 7,
        flip_images: bool = True,
        default_task: str = "",
        dtype: str = "bfloat16",
        norm_tag: str = "libero",
        num_steps: int = 10,
        enable_cuda_graph: bool = False,
        normalize_language: bool = True,
        task_override: str | None = None,
    ):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.action_dim = action_dim
        self.flip_images = flip_images
        self._task = default_task
        # E1 ablation: env の言語より優先して固定指示を渡す（空文字は無効）。
        self.task_override = (task_override or "").strip() or None
        self.norm_tag = norm_tag
        self.num_steps = int(num_steps)
        self.enable_cuda_graph = bool(enable_cuda_graph)
        self.normalize_language = bool(normalize_language)
        self.path = path

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        # 4090 24GB では float32+CUDA graph は逼迫しやすい。既定は bf16。
        torch_dtype = {
            "bfloat16": torch.bfloat16,
            "bf16": torch.bfloat16,
            "float16": torch.float16,
            "fp16": torch.float16,
            "float32": torch.float32,
            "fp32": torch.float32,
        }.get(str(dtype).lower())
        if torch_dtype is None:
            raise ValueError(f"unsupported dtype: {dtype!r}")
        self._torch_dtype = torch_dtype
        self._use_autocast = torch_dtype in {torch.bfloat16, torch.float16} and device.startswith(
            "cuda"
        )

        self.processor = AutoProcessor.from_pretrained(path, trust_remote_code=True)
        self.model = AutoModelForImageTextToText.from_pretrained(
            path,
            trust_remote_code=True,
            dtype=torch_dtype,
        ).to(device)
        self.model.eval()

        # action chunk キュー（horizon × dim）。reset で空にする。
        self._action_queue: deque[np.ndarray] = deque()

    def set_task(self, task: str) -> None:
        """エピソードの言語指示をセットする。"""
        self._task = task

    def reset(self) -> None:
        self._action_queue.clear()

    def _predict_chunk(self, obs: dict[str, Any], task: str) -> np.ndarray:
        """1 回の predict_action で (T, D) チャンクを得る。"""
        import torch

        images = [
            _obs_rgb_to_pil(obs, "agentview_image", flip=self.flip_images),
            _obs_rgb_to_pil(obs, "robot0_eye_in_hand_image", flip=self.flip_images),
        ]
        state = _libero_state_from_obs(obs)

        kwargs = dict(
            processor=self.processor,
            images=images,
            task=task,
            state=state,
            norm_tag=self.norm_tag,
            inference_action_mode="continuous",
            enable_depth_reasoning=False,
            num_steps=self.num_steps,
            normalize_language=self.normalize_language,
            enable_cuda_graph=self.enable_cuda_graph,
        )

        with torch.inference_mode():
            if self._use_autocast:
                with torch.autocast("cuda", dtype=self._torch_dtype):
                    out = self.model.predict_action(**kwargs)
            else:
                out = self.model.predict_action(**kwargs)

        actions = getattr(out, "actions", out)
        if hasattr(actions, "detach"):
            actions = actions.detach().to("cpu").float().numpy()
        arr = np.asarray(actions, dtype=np.float32)
        # 公式は (1, T, D) / (T, D) / (D,) があり得る
        if arr.ndim == 3 and arr.shape[0] == 1:
            arr = arr[0]
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.ndim != 2:
            raise RuntimeError(f"unexpected MolmoAct2 actions shape: {arr.shape}")
        return arr

    def act(self, obs: dict[str, Any]) -> np.ndarray:
        # task_override があれば ablation 用に env 言語を無視する。
        task = str(self.task_override or obs.get("task") or self._task or "")
        if not task:
            raise ValueError(
                "言語指示が空です。runner から task.language を渡すか set_task() / "
                "task_override を設定してください。"
            )

        if not self._action_queue:
            chunk = self._predict_chunk(obs, task)
            for row in chunk:
                self._action_queue.append(np.asarray(row, dtype=np.float32).reshape(-1))

        action = self._action_queue.popleft()
        if action.size < self.action_dim:
            raise RuntimeError(f"action dim too small: {action.shape}")
        # 公式は max action dim 32 に pad することがある → 先頭 action_dim を使う
        return action[: self.action_dim].astype(np.float32)
