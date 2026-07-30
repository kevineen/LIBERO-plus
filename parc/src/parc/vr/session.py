"""テレオプ セッション状態機械（env step + 録画）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import numpy as np
from PIL import Image

from parc.vr.action_map import ActionMapConfig, PoseActionMapper
from parc.vr.obs_util import extract_front_wrist, obs_to_frame_dict
from parc.vr.protocol import (
    ButtonEdgeTracker,
    Buttons,
    ControlMessage,
    EpisodeDiscardedMessage,
    EpisodeSavedMessage,
    Pose,
    StatusMessage,
)
from parc.vr.recorder import EpisodeRecorder
from parc.vr.video import rgb_to_jpeg


class EnvLike(Protocol):
    """LIBERO env の最小インターフェース。"""

    def reset(self) -> Any: ...

    def step(self, action: list[float]) -> tuple[dict[str, Any], float, bool, dict[str, Any]]: ...

    def close(self) -> None: ...


@dataclass
class FakeLiberoEnv:
    """Quest 無し・LIBERO 無しでループを回すダミー環境。"""

    height: int = 128
    width: int = 128
    _t: int = 0

    def reset(self) -> dict[str, Any]:
        """初期観測を返す。"""
        self._t = 0
        return self._obs()

    def step(self, action: list[float]) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        """ダミー step。"""
        del action
        self._t += 1
        return self._obs(), 0.0, False, {}

    def close(self) -> None:
        """何もしない。"""
        return None

    def _obs(self) -> dict[str, Any]:
        """学習互換キーを持つ偽観測。"""
        h, w = self.height, self.width
        # 時間で色が変わるのでストリーム確認しやすい
        front = np.zeros((h, w, 3), dtype=np.uint8)
        wrist = np.zeros((h, w, 3), dtype=np.uint8)
        front[:, :, 0] = (self._t * 7) % 255
        wrist[:, :, 1] = (self._t * 11) % 255
        return {
            "agentview_image": front,
            "robot0_eye_in_hand_image": wrist,
            "robot0_eef_pos": np.array([0.1, 0.0, 0.4], dtype=np.float32),
            "robot0_eef_quat": np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
            "robot0_gripper_qpos": np.array([0.02, -0.02], dtype=np.float32),
        }


def _resize_hwc(img: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """(H,W,3) を (size_h, size_w) にリサイズ。"""
    h, w = size
    if img.shape[0] == h and img.shape[1] == w:
        return img
    pil = Image.fromarray(img, mode="RGB")
    return np.asarray(pil.resize((w, h), Image.Resampling.BILINEAR), dtype=np.uint8)


@dataclass
class TeleopSessionConfig:
    """セッション設定。"""

    suite: str = "libero_spatial"
    task_id: int = 0
    language: str = "vr teleop demo"
    fps: int = 20
    jpeg_quality: int = 70
    flip_images: bool = True
    image_size: tuple[int, int] = (256, 256)
    action_map: ActionMapConfig = field(default_factory=ActionMapConfig)
    dataset_root: Path = Path("data/datasets/vr_libero_demos")
    repo_id: str = "local/vr_libero_demos"
    create_dataset: bool = True


OutboundHandler = Callable[[str | bytes], None]


@dataclass
class TeleopSession:
    """1 クライアント分のテレオプ状態。"""

    env: EnvLike
    config: TeleopSessionConfig
    send: OutboundHandler
    recorder: EpisodeRecorder | None = None
    mapper: PoseActionMapper = field(init=False)
    edges: ButtonEdgeTracker = field(default_factory=ButtonEdgeTracker)
    recording: bool = False
    _obs: dict[str, Any] | None = None
    _closed: bool = False

    def __post_init__(self) -> None:
        """mapper / recorder を初期化し env を reset する。"""
        self.mapper = PoseActionMapper(self.config.action_map)
        if self.recorder is None:
            self.recorder = EpisodeRecorder(
                root=self.config.dataset_root,
                repo_id=self.config.repo_id,
                fps=self.config.fps,
                image_size=self.config.image_size,
                create_dataset=self.config.create_dataset,
            )
        self._obs = self.env.reset()
        self.mapper.reset()

    def close(self) -> None:
        """環境と recorder を閉じる。"""
        if self._closed:
            return
        self._closed = True
        if self.recorder is not None:
            self.recorder.finalize()
        close = getattr(self.env, "close", None)
        if callable(close):
            close()

    def handle_control(self, msg: ControlMessage) -> None:
        """制御メッセージ 1 通を処理する。"""
        rising = self.edges.update(msg.buttons)
        if rising.reset:
            self._handle_reset()
        if rising.record:
            self._start_recording()
        if rising.discard:
            self._discard()
        if rising.save:
            self._save()

        action = self.mapper.map(msg.pose, msg.gripper)
        assert self._obs is not None
        next_obs, _reward, _done, _info = self.env.step(action.tolist())

        if self.recording and self.recorder is not None:
            frame = obs_to_frame_dict(
                self._obs,
                action,
                flip_images=self.config.flip_images,
            )
            # 録画解像度へリサイズ
            h, w = self.config.image_size
            frame["front"] = _resize_hwc(frame["front"], (h, w))
            frame["wrist"] = _resize_hwc(frame["wrist"], (h, w))
            self.recorder.add_frame(frame)

        self._obs = next_obs

    def emit_video(self) -> None:
        """現在観測の JPEG を send する。"""
        if self._obs is None:
            return
        # ストリームは学習 flip 前の生視点の方が操作しやすい → flip=False
        front, wrist = extract_front_wrist(self._obs, flip_images=False)
        from parc.vr.protocol import CAMERA_FRONT, CAMERA_WRIST, pack_jpeg_frame

        q = self.config.jpeg_quality
        self.send(pack_jpeg_frame(CAMERA_FRONT, rgb_to_jpeg(front, quality=q)))
        self.send(pack_jpeg_frame(CAMERA_WRIST, rgb_to_jpeg(wrist, quality=q)))

    def emit_status(self, message: str = "") -> None:
        """status JSON を送る。"""
        from parc.vr.protocol import encode_message

        n = self.recorder.buffer.num_frames if self.recorder else 0
        self.send(
            encode_message(
                StatusMessage(
                    recording=self.recording,
                    frame_count=n,
                    message=message,
                )
            )
        )

    def _start_recording(self) -> None:
        """録画開始。"""
        if self.recorder is None:
            return
        self.recorder.start_episode(self.config.language)
        self.mapper.reset()
        self.recording = True
        self.emit_status("recording")

    def _discard(self) -> None:
        """バッファ破棄。"""
        from parc.vr.protocol import encode_message

        if self.recorder is not None:
            self.recorder.discard_episode()
        self.recording = False
        self.send(encode_message(EpisodeDiscardedMessage(reason="user")))
        self.emit_status("discarded")

    def _save(self) -> None:
        """エピソード保存。"""
        from parc.vr.protocol import encode_message

        if self.recorder is None or self.recorder.buffer.num_frames == 0:
            self.emit_status("nothing to save")
            return
        n = self.recorder.buffer.num_frames
        idx = self.recorder.save_episode()
        self.recording = False
        self.send(
            encode_message(
                EpisodeSavedMessage(
                    episode_index=idx,
                    num_frames=n,
                    dataset_root=str(self.config.dataset_root),
                )
            )
        )
        summary = self.recorder.dataset_summary()
        self.emit_status(
            f"saved meta={summary['meta_exists']} episodes={summary['episode_count']}"
        )

    def _handle_reset(self) -> None:
        """env reset。録画中なら破棄。"""
        if self.recording:
            self._discard()
        self._obs = self.env.reset()
        self.mapper.reset()
        self.emit_status("reset")


def run_fake_episode(
    *,
    dataset_root: Path,
    num_frames: int = 16,
    create_dataset: bool = False,
    language: str = "fake vr teleop",
    image_size: tuple[int, int] = (64, 64),
) -> int:
    """フェイク入力で 1 エピソード分 step して保存する（スモーク用）。"""
    sent: list[str | bytes] = []

    def _send(payload: str | bytes) -> None:
        sent.append(payload)

    cfg = TeleopSessionConfig(
        language=language,
        dataset_root=dataset_root,
        create_dataset=create_dataset,
        image_size=image_size,
        fps=20,
    )
    session = TeleopSession(env=FakeLiberoEnv(height=image_size[0], width=image_size[1]), config=cfg, send=_send)
    # record ON
    session.handle_control(
        ControlMessage(
            t=0.0,
            pose=Pose(),
            gripper=0.0,
            buttons=Buttons(record=True),
        )
    )
    for i in range(num_frames):
        session.handle_control(
            ControlMessage(
                t=float(i + 1) / cfg.fps,
                pose=Pose(pos=(0.001 * i, 0.0, 0.0)),
                gripper=float(i % 2),
                buttons=Buttons(),
            )
        )
    session.handle_control(
        ControlMessage(
            t=1.0,
            pose=Pose(pos=(0.001 * num_frames, 0.0, 0.0)),
            gripper=1.0,
            buttons=Buttons(save=True),
        )
    )
    n_saved = 0
    for item in sent:
        if isinstance(item, str) and '"episode_saved"' in item:
            n_saved += 1
    session.close()
    return n_saved
