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
    # runner が saliency 対応を判定するためのフラグ
    supports_saliency: bool = True

    def __init__(
        self,
        path: str | Path,
        *,
        device: str | None = None,
        action_dim: int = 7,
        flip_images: bool = True,
        default_task: str = "",
        async_inference: bool = False,
        enable_saliency: bool = False,
        saliency_method: str = "activation",
    ):
        import torch
        from lerobot.policies.factory import make_pre_post_processors
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

        self.action_dim = action_dim
        self.flip_images = flip_images
        # SmolVLA 非同期推論スタック（LeRobot 側フラグがあれば有効化）
        self.async_inference = bool(async_inference)
        self.enable_saliency = bool(enable_saliency)
        method = str(saliency_method or "activation").lower().strip()
        if method not in {"activation", "gradcam"}:
            raise ValueError(
                f"saliency_method は 'activation' か 'gradcam' です（got {saliency_method!r}）"
            )
        self.saliency_method = method
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
        # 存在すれば config に配線（未対応版では無視）
        if self.async_inference:
            for key in ("async_inference", "use_async_inference", "async_mode"):
                if hasattr(self.policy.config, key):
                    setattr(self.policy.config, key, True)

        preprocessor_overrides = {
            "device_processor": {"device": self.device},
        }
        self.preprocessor, self.postprocessor = make_pre_post_processors(
            policy_cfg=self.policy.config,
            pretrained_path=str(self.ckpt_dir),
            preprocessor_overrides=preprocessor_overrides,
        )

        # saliency 有効時は vision tower の存在を起動時に検証する
        if self.enable_saliency:
            self._get_vision_model()

    def set_task(self, task: str) -> None:
        """エピソードの言語指示をセットする。"""
        self._task = task

    def reset(self) -> None:
        self.policy.reset()

    def _get_vision_model(self) -> Any:
        """SmolVLA 内部の SigLIP vision tower を返す。見つからなければエラー。"""
        try:
            vlm = self.policy.model.vlm_with_expert.get_vlm_model()
            vision = vlm.vision_model
        except AttributeError as exc:
            raise RuntimeError(
                "SmolVLA vision_model を解決できません。"
                " LeRobot / transformers 版が想定と異なる可能性があります。"
            ) from exc
        if vision is None:
            raise RuntimeError("SmolVLA vision_model が None です")
        return vision

    def _prepare_obs_batch(self, obs: dict[str, Any]) -> dict[str, Any]:
        """観測 → preprocessor 済み batch。"""
        task = str(obs.get("task") or self._task or "")
        if not task:
            raise ValueError(
                "言語指示が空です。runner から task.language を渡すか set_task() してください。"
            )
        batch = raw_libero_obs_to_batch(obs, task=task, flip_images=self.flip_images)
        return self.preprocessor(batch)

    def _action_from_tensor(self, action: Any) -> np.ndarray:
        """postprocessor 後の action を (action_dim,) float32 にする。"""
        if hasattr(action, "detach"):
            action_np = action.detach().to("cpu").numpy()
        else:
            action_np = np.asarray(action)
        action_np = np.asarray(action_np, dtype=np.float32).reshape(-1)
        if action_np.size < self.action_dim:
            raise RuntimeError(f"action dim too small: {action_np.shape}")
        return action_np[: self.action_dim]

    def _front_image_for_vision(self, prepared_batch: dict[str, Any]) -> Any:
        """prepare_images 後の front 画像テンソル (1,C,H,W) を返す。"""
        images, _img_masks = self.policy.prepare_images(prepared_batch)
        if not images:
            raise RuntimeError("prepare_images が空です（front 画像がありません）")
        return images[0]

    def _activation_map_from_tokens(self, tokens: Any) -> np.ndarray:
        """(B,N,C) token → (H,W) 正規化前マップ。"""
        from parc.eval.attention import tokens_to_spatial_map

        arr = tokens.detach().float().cpu().numpy()
        return tokens_to_spatial_map(arr)

    def _compute_activation_saliency(self, prepared_batch: dict[str, Any]) -> np.ndarray:
        """Vision last_hidden_state の channel L2 マップ（勾配不要）。"""
        import torch

        vision = self._get_vision_model()
        img = self._front_image_for_vision(prepared_batch)
        with torch.inference_mode():
            out = vision(pixel_values=img.to(dtype=vision.dtype))
            hs = out.last_hidden_state
        return self._activation_map_from_tokens(hs)

    def _compute_gradcam_saliency(self, prepared_batch: dict[str, Any]) -> np.ndarray:
        """Action L2 を標的にした Grad-CAM（方策キューは触らない）。"""
        import torch

        from lerobot.utils.constants import OBS_LANGUAGE_ATTENTION_MASK, OBS_LANGUAGE_TOKENS

        vision = self._get_vision_model()
        # prepared_batch は compute_saliency 側で _prepare_batch 済み
        images, img_masks = self.policy.prepare_images(prepared_batch)
        state = self.policy.prepare_state(prepared_batch)
        lang_tokens = prepared_batch[OBS_LANGUAGE_TOKENS]
        lang_masks = prepared_batch[OBS_LANGUAGE_ATTENTION_MASK]

        feat_holder: dict[str, Any] = {}

        def _hook(_module: Any, _inp: Any, out: Any) -> None:
            hs = out.last_hidden_state if hasattr(out, "last_hidden_state") else out
            # グラフ上のテンソルを保持し、逆伝播で grad を取る
            feat_holder["feat"] = hs
            if hs.requires_grad:
                hs.retain_grad()

        handle = vision.register_forward_hook(_hook)
        try:
            was_training = vision.training
            # Grad-CAM では forward がグラフに載る必要がある
            with torch.enable_grad():
                actions = self.policy.model.sample_actions(
                    images, img_masks, lang_tokens, lang_masks, state
                )
                if "feat" not in feat_holder:
                    raise RuntimeError("Grad-CAM: vision forward hook が発火しませんでした")
                target = actions.float().pow(2).mean()
                if feat_holder["feat"].grad is not None:
                    feat_holder["feat"].grad = None
                target.backward()
            feats = feat_holder["feat"]
            grads = feats.grad
            if grads is None:
                raise RuntimeError(
                    "Grad-CAM: vision 特徴に勾配がありません。"
                    " freeze / SDPA 設定を確認してください。"
                )
            # (B, N, C): チャネル重み = トークン平均勾配
            weights = grads.relu().mean(dim=1, keepdim=True)  # (B, 1, C)
            cam = (weights * feats.detach()).sum(dim=-1).relu()  # (B, N)
            heat = self._activation_map_from_tokens(cam)
            if was_training:
                vision.train()
            else:
                vision.eval()
            return heat
        finally:
            handle.remove()
            # グラフ残留を避ける
            if hasattr(self.policy, "zero_grad"):
                self.policy.zero_grad(set_to_none=True)

    def compute_saliency(self, obs: dict[str, Any], *, method: str | None = None) -> dict[str, Any]:
        """現在観測の front 注視マップを返す（act とは独立・キュー非破壊）。"""
        method_use = (method or self.saliency_method).lower().strip()
        prepared = self._prepare_obs_batch(obs)
        # select_action と同じ前処理経路に揃える
        prepared = self.policy._prepare_batch(prepared)

        if method_use == "activation":
            heat = self._compute_activation_saliency(prepared)
        elif method_use == "gradcam":
            heat = self._compute_gradcam_saliency(prepared)
        else:
            raise ValueError(f"unknown saliency method: {method_use!r}")

        return {
            "front": heat,
            "method": method_use,
            "flipped_input": bool(self.flip_images),
        }

    def act(self, obs: dict[str, Any]) -> np.ndarray:
        import torch

        batch = self._prepare_obs_batch(obs)
        with torch.inference_mode():
            action = self.policy.select_action(batch)
        action = self.postprocessor(action)
        return self._action_from_tensor(action)

    def act_with_saliency(self, obs: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
        """アクションと front 注視マップを返す。

        マップは方策入力（flip 済み）基準。表示時は ``unflip_heatmap=True`` で env 向きに合わせる。
        """
        import torch

        batch = self._prepare_obs_batch(obs)
        # saliency はキューを汚さない独立 forward
        saliency = self.compute_saliency(obs, method=self.saliency_method)
        with torch.inference_mode():
            action = self.policy.select_action(batch)
        action = self.postprocessor(action)
        return self._action_from_tensor(action), saliency
