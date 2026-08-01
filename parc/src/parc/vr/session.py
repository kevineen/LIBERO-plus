"""テレオプ セッション状態機械（env step + 録画 + 品質ゲート）。"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import numpy as np
from PIL import Image

from parc.env.metrics import _jerk, _path_length
from parc.env.success import is_libero_success
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
    """Quest 無し・LIBERO 無しでループを回すダミー環境。

    既定では 1 step 後に成功扱い（品質ゲート付きスモーク用）。
    `success_after=None` で永不成功。
    """

    height: int = 128
    width: int = 128
    n_init_states: int = 3
    success_after: int | None = 1
    _t: int = 0
    _init_index: int = 0
    _succeeded: bool = False

    def reset(self) -> dict[str, Any]:
        """初期観測を返す。"""
        self._t = 0
        self._succeeded = False
        return self._obs()

    def set_init_state(self, state: Any) -> dict[str, Any]:
        """フェイク init index をセットする。"""
        if isinstance(state, (int, np.integer)):
            self._init_index = int(state) % max(1, self.n_init_states)
        self._t = 0
        self._succeeded = False
        return self._obs()

    def check_success(self) -> bool:
        """成功フラグ。"""
        return self._succeeded

    def step(self, action: list[float]) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        """ダミー step。成功条件を満たせば reward/done を立てる。"""
        del action
        self._t += 1
        # init index で EE 位置を少しずらして多様化を可視化
        obs = self._obs()
        if self.success_after is not None and self._t >= self.success_after:
            self._succeeded = True
            return obs, 1.0, True, {"success": True}
        return obs, 0.0, False, {}

    def close(self) -> None:
        """何もしない。"""
        return None

    def _obs(self) -> dict[str, Any]:
        """学習互換キーを持つ偽観測。"""
        h, w = self.height, self.width
        # 時間で色が変わるのでストリーム確認しやすい。
        # t=0 でも黒にしない（接続直後の1枚目が見えるようにする）
        front = np.zeros((h, w, 3), dtype=np.uint8)
        wrist = np.zeros((h, w, 3), dtype=np.uint8)
        front[:, :, 0] = (64 + self._t * 7) % 255
        wrist[:, :, 1] = (64 + self._t * 11) % 255
        front[:, :, 2] = 32
        wrist[:, :, 2] = 32
        x_off = 0.01 * float(self._init_index)
        return {
            "agentview_image": front,
            "robot0_eye_in_hand_image": wrist,
            "robot0_eef_pos": np.array([0.1 + x_off, 0.0, 0.4], dtype=np.float32),
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


def _ee_pos(obs: dict[str, Any]) -> np.ndarray:
    """観測から EE 位置を取る。"""
    for key in ("robot0_eef_pos", "ee_pos", "eef_pos"):
        if key in obs:
            return np.asarray(obs[key], dtype=np.float64).reshape(-1)
    return np.zeros(3, dtype=np.float64)


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
    require_success: bool = False
    init_state_mode: str = "cycle"
    task_ids: list[int] = field(default_factory=list)
    camera_height: int = 128
    camera_width: int = 128
    fake: bool = False
    operator_id: str = ""
    device_id: str = ""
    location: str = ""
    calib_override_path: str = ""
    collection_info: dict[str, Any] | None = None
    # RTT / 遅延ゲート（max_rtt_ms<=0 で無効）
    max_rtt_ms: float = 150.0
    latency_policy: str = "degraded"  # degraded | refuse
    # Approximate Time 同期器（#6）
    approx_time_slop_ms: float = 100.0
    # 収集キュー（#4）— 空なら従来の init/task cycle
    collection_queue: list[dict[str, Any]] = field(default_factory=list)
    min_success_per_category: int = 0


OutboundHandler = Callable[[str | bytes], None]
EnvRemakeHandler = Callable[[str, int], Any]  # returns TeleopEnvBundle-like


@dataclass
class TeleopSession:
    """1 クライアント分のテレオプ状態。"""

    env: EnvLike
    config: TeleopSessionConfig
    send: OutboundHandler
    recorder: EpisodeRecorder | None = None
    init_states: list[Any] = field(default_factory=list)
    remake_env: EnvRemakeHandler | None = None
    mapper: PoseActionMapper = field(init=False)
    edges: ButtonEdgeTracker = field(default_factory=ButtonEdgeTracker)
    recording: bool = False
    _obs: dict[str, Any] | None = None
    _closed: bool = False
    _env_done: bool = False
    _episode_success: bool = False
    _init_state_index: int = 0
    _task_index: int = 0
    _episode_actions: list[np.ndarray] = field(default_factory=list)
    _episode_ee: list[np.ndarray] = field(default_factory=list)
    _episode_started_at: float = 0.0
    _rtt_samples_ms: list[float] = field(default_factory=list)
    _last_accepted_control_t: float | None = None
    _dropped_stale_controls: int = 0
    _queue_index: int = 0
    _current_category: str = ""
    _current_perturbation: str = ""
    _category_success_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """mapper / recorder を初期化し env を reset する。"""
        self.mapper = PoseActionMapper(self.config.action_map)
        if self.recorder is None:
            from parc.vr.collection_meta import build_collection_info, load_calib_override

            override = None
            override_path = self.config.calib_override_path or None
            if override_path:
                override = load_calib_override(override_path)
            info = self.config.collection_info or build_collection_info(
                fps=self.config.fps,
                image_size=self.config.image_size,
                render_size=(self.config.camera_height, self.config.camera_width),
                operator_id=self.config.operator_id,
                device_id=self.config.device_id,
                location=self.config.location,
                suite=self.config.suite,
                calib_override=override,
                calib_override_path=override_path,
            )
            self.recorder = EpisodeRecorder(
                root=self.config.dataset_root,
                repo_id=self.config.repo_id,
                fps=self.config.fps,
                image_size=self.config.image_size,
                create_dataset=self.config.create_dataset,
                collection_info=info,
            )
        if not self.config.task_ids:
            self.config.task_ids = [self.config.task_id]
        self._task_index = 0
        for i, tid in enumerate(self.config.task_ids):
            if tid == self.config.task_id:
                self._task_index = i
                break
        self._init_state_index = 0
        if self.config.collection_queue:
            self._apply_queue_entry(0, advance_after=False)
        else:
            self._obs = self._apply_current_init()
        self.mapper.reset()

    @property
    def n_init_states(self) -> int:
        """サイクル可能な init 数。"""
        return max(1, len(self.init_states))

    @property
    def queue_remaining(self) -> int:
        """未消化の収集キュー件数。"""
        q = self.config.collection_queue
        if not q:
            return 0
        return max(0, len(q) - self._queue_index)

    def record_rtt(self, rtt_ms: float) -> None:
        """ping/pong 由来の RTT サンプルを記録する。"""
        if rtt_ms < 0:
            return
        self._rtt_samples_ms.append(float(rtt_ms))

    def _rtt_summary(self) -> tuple[float | None, float | None]:
        """セッション平均・p95 RTT (ms)。サンプル無なら (None, None)。"""
        samples = self._rtt_samples_ms
        if not samples:
            return None, None
        mean = float(sum(samples) / len(samples))
        ordered = sorted(samples)
        # nearest-rank p95
        idx = min(len(ordered) - 1, max(0, int(math.ceil(0.95 * len(ordered)) - 1)))
        p95 = float(ordered[idx])
        return mean, p95

    def _control_skew_ms(self) -> float | None:
        """最終 control_t と壁時計相対の差 (ms)。"""
        if self.recorder is None or self.recorder.buffer.num_frames == 0:
            return None
        control_ts = self.recorder.buffer.control_timestamps()
        if not control_ts:
            return None
        last_c = float(control_ts[-1])
        wall_rel = max(0.0, time.time() - self._episode_started_at) if self._episode_started_at else 0.0
        return abs(wall_rel - last_c) * 1000.0

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
        # robosuite は done 後の step で落ちる。Save/Reset で init し直した直後の
        # 同一メッセージでも追加 step しない（auto-reset ループ防止）。
        was_done = self._env_done
        rising = self.edges.update(msg.buttons)
        if rising.reset:
            self._handle_reset()
        if rising.record:
            self._start_recording()
        if rising.discard:
            self._discard()
        if rising.save:
            self._save()

        if was_done:
            return

        # Approximate Time: 録画中の古い / 重複 uplink は step・frame を落とす
        control_t: float | None = None
        if msg.t > 0:
            control_t = float(msg.t)
        elif self.recording and self._episode_started_at > 0:
            control_t = time.time() - self._episode_started_at

        if self.recording and control_t is not None and self._should_drop_control(control_t):
            self._dropped_stale_controls += 1
            if self.recorder is not None:
                self.recorder.stats.dropped_stale_controls += 1
            return

        if self._env_done:
            return

        action = self.mapper.map(msg.pose, msg.gripper)
        assert self._obs is not None
        try:
            next_obs, reward, done, info = self.env.step(action.tolist())
        except ValueError as exc:
            # robosuite: horizon 到達後も LIBERO は done=success だけ返すことがあり、
            # 内部 self.done=True のまま次 step で落ちる。読み込み中に溜まった
            # control バーストでも同様。
            if "terminated episode" not in str(exc):
                raise
            self._env_done = True
            if self.recording:
                self.emit_status("env terminated — Save (B) or Reset (Menu)")
            else:
                self._obs = self._apply_current_init()
                self.mapper.reset()
                self.emit_status("env terminated — auto reset")
            return

        # LIBERO は success のみを done に載せ、horizon の self.done を隠すことがある
        inner_done = bool(getattr(getattr(self.env, "env", None), "done", False))
        done = bool(done) or inner_done

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
            # Approximate Time 用の制御時刻（LeRobot v3 の timestamp とは別・サイドカーへ）
            if control_t is not None:
                frame["control_t"] = control_t
            else:
                frame["control_t"] = 0.0
            self.recorder.add_frame(frame)
            self._episode_actions.append(np.asarray(action, dtype=np.float64))
            self._last_accepted_control_t = float(frame["control_t"])

        if is_libero_success(reward, done, info, self.env):
            self._episode_success = True

        self._obs = next_obs
        if self.recording:
            self._episode_ee.append(_ee_pos(next_obs))

        if done:
            self._env_done = True
            if self.recording:
                self.emit_status("env done — Save (B) or Reset (Menu)")
            else:
                # 自由操作中は同じ init で自動復帰（接続を落とさない）
                self._obs = self._apply_current_init()
                self.mapper.reset()
                self.emit_status("env done — auto reset")

    def _should_drop_control(self, control_t: float) -> bool:
        """許容窓外・重複の control を落とすか判定する。"""
        slop_s = max(0.0, float(self.config.approx_time_slop_ms) / 1000.0)
        last = self._last_accepted_control_t
        if last is not None:
            if control_t < last - 1e-9:
                # 古い（巻き戻り）
                return True
            if abs(control_t - last) < 1e-9:
                # 同一時刻の重複
                return True
            # last より新しすぎてバースト、かつ壁時計窓を大きく超える場合は落とさない
            # （未来時刻は許容。古いものだけ落とす）
        if self._episode_started_at > 0 and slop_s > 0:
            wall_rel = time.time() - self._episode_started_at
            # control_t が壁時計相対より slop 以上古い → stale
            if control_t < wall_rel - slop_s:
                return True
        return False

    def emit_video(self) -> None:
        """現在観測の RGB フレームを send する。"""
        if self._obs is None:
            return
        # ストリームは学習 flip 前の生視点の方が操作しやすい → flip=False
        front, wrist = extract_front_wrist(self._obs, flip_images=False)
        from parc.vr.protocol import (
            CAMERA_FRONT_RGB,
            CAMERA_WRIST_RGB,
            pack_rgb_frame,
        )

        # JPEG 経由だと Quest/一部クライアントで破損→テレビノイズになる事例あり。
        # LAN 向けに非圧縮 RGB24 を送る（256²×2×20Hz でも数 MB/s）。
        fh, fw = int(front.shape[0]), int(front.shape[1])
        wh, ww = int(wrist.shape[0]), int(wrist.shape[1])
        self.send(
            pack_rgb_frame(
                CAMERA_FRONT_RGB,
                np.ascontiguousarray(front, dtype=np.uint8).tobytes(),
                width=fw,
                height=fh,
            )
        )
        self.send(
            pack_rgb_frame(
                CAMERA_WRIST_RGB,
                np.ascontiguousarray(wrist, dtype=np.uint8).tobytes(),
                width=ww,
                height=wh,
            )
        )

    def emit_status(self, message: str = "") -> None:
        """status JSON を送る。"""
        from parc.vr.protocol import encode_message

        n = self.recorder.buffer.num_frames if self.recorder else 0
        q_rem = self.queue_remaining
        if self.config.collection_queue and "queue_remaining" not in message:
            suffix = f" queue_remaining={q_rem}"
            message = f"{message}{suffix}" if message else f"queue_remaining={q_rem}"
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
        self._episode_success = False
        self._episode_actions = []
        self._episode_ee = [_ee_pos(self._obs)] if self._obs is not None else []
        self._episode_started_at = time.time()
        self._last_accepted_control_t = None
        self._dropped_stale_controls = 0
        self.emit_status("recording")

    def _discard(self) -> None:
        """バッファ破棄。"""
        from parc.vr.protocol import encode_message

        if self.recorder is not None:
            self.recorder.discard_episode()
        self.recording = False
        self._episode_success = False
        self._episode_actions = []
        self._episode_ee = []
        self._last_accepted_control_t = None
        self.send(encode_message(EpisodeDiscardedMessage(reason="user")))
        self.emit_status("discarded")

    def _save(self) -> None:
        """エピソード保存（require_success / 遅延ゲート）。"""
        from parc.vr.protocol import encode_message

        if self.recorder is None or self.recorder.buffer.num_frames == 0:
            self.emit_status("nothing to save")
            return

        if self.config.require_success and not self._episode_success:
            self.recorder.refuse_save()
            self.emit_status("save refused: episode not successful")
            return

        rtt_mean, rtt_p95 = self._rtt_summary()
        skew = self._control_skew_ms()
        degraded = False
        max_rtt = float(self.config.max_rtt_ms)
        if max_rtt > 0 and rtt_p95 is not None and rtt_p95 > max_rtt:
            policy = (self.config.latency_policy or "degraded").lower()
            if policy == "refuse":
                self.recorder.refuse_save()
                self.recorder.stats.refused_latency += 1
                self.emit_status(
                    f"save refused: latency p95={rtt_p95:.1f}ms > max_rtt_ms={max_rtt}"
                )
                return
            degraded = True

        n = self.recorder.buffer.num_frames
        wall = max(0.0, time.time() - self._episode_started_at) if self._episode_started_at else 0.0
        t0_unix = self._episode_started_at if self._episode_started_at else time.time()
        quality: dict[str, Any] = {
            "suite": self.config.suite,
            "task_id": self.config.task_id,
            "init_state_index": self._init_state_index,
            "language": self.config.language,
            "task": self.config.language,
            "success": bool(self._episode_success),
            "path_length": float(_path_length(self._episode_ee)),
            "jerk": float(_jerk(self._episode_actions)),
            "wall_time_sec": round(wall, 3),
            "t0_unix": t0_unix,
            "t_end_unix": time.time(),
            "fps": self.config.fps,
            "operator_id": self.config.operator_id,
            "device_id": self.config.device_id,
            "location": self.config.location,
            "sync_policy": "approximate_time",
            "dropped_stale_controls": int(self._dropped_stale_controls),
            "degraded": bool(degraded),
        }
        if self._current_category:
            quality["category"] = self._current_category
        if self._current_perturbation:
            quality["perturbation"] = self._current_perturbation
        if rtt_mean is not None:
            quality["rtt_ms_mean"] = round(rtt_mean, 3)
        if rtt_p95 is not None:
            quality["rtt_ms_p95"] = round(rtt_p95, 3)
        if skew is not None:
            quality["control_skew_ms"] = round(skew, 3)

        idx = self.recorder.save_episode(quality=quality)
        if degraded:
            self.recorder.stats.degraded += 1
        self.recording = False
        self._last_accepted_control_t = None

        # 成功 Save でキューエントリを消化
        if self._episode_success and self.config.collection_queue:
            cat = self._current_category or "default"
            self._category_success_counts[cat] = self._category_success_counts.get(cat, 0) + 1
            self._queue_index = min(self._queue_index + 1, len(self.config.collection_queue))

        self.send(
            encode_message(
                EpisodeSavedMessage(
                    episode_index=idx,
                    num_frames=n,
                    dataset_root=str(self.config.dataset_root),
                    success=bool(self._episode_success),
                    init_state_index=self._init_state_index,
                )
            )
        )
        summary = self.recorder.dataset_summary()
        self.emit_status(
            f"saved meta={summary['meta_exists']} episodes={summary['episode_count']} "
            f"success={self._episode_success} degraded={degraded}"
        )
        # 保存後（成功/失敗問わず）に多様化を進める
        self._advance_diversity()

    def _handle_reset(self) -> None:
        """env reset。録画中なら破棄し、多様化を進める。"""
        if self.recording:
            self._discard()
        self._advance_diversity()
        self.emit_status(
            f"reset task_id={self.config.task_id} init_state_index={self._init_state_index}"
        )

    def _advance_diversity(self) -> None:
        """キュー優先、無ければ init_state / task cycle。"""
        if self.config.collection_queue:
            self._apply_queue_entry(self._queue_index, advance_after=False)
            self.mapper.reset()
            return

        if self.config.init_state_mode != "cycle":
            self._obs = self._apply_current_init()
            self.mapper.reset()
            return

        prev_task = self.config.task_id
        n_init = self.n_init_states
        self._init_state_index = (self._init_state_index + 1) % n_init
        if self._init_state_index == 0 and len(self.config.task_ids) > 1:
            self._task_index = (self._task_index + 1) % len(self.config.task_ids)
            next_task = self.config.task_ids[self._task_index]
            if next_task != prev_task and self.remake_env is not None:
                bundle = self.remake_env(self.config.suite, next_task)
                close = getattr(self.env, "close", None)
                if callable(close):
                    close()
                self.env = bundle.env
                self.init_states = list(bundle.init_states)
                self.config.task_id = bundle.task_id
                self.config.language = bundle.language
                self._init_state_index = 0

        self._obs = self._apply_current_init()
        self.mapper.reset()

    def _apply_queue_entry(self, index: int, *, advance_after: bool) -> None:
        """収集キューの index 番を suite/task/init/category に反映する。"""
        q = self.config.collection_queue
        if not q:
            self._obs = self._apply_current_init()
            return
        if index >= len(q):
            # キュー完了 — 最後のエントリを維持
            entry = q[-1]
            self._queue_index = len(q)
        else:
            entry = q[index]
            self._queue_index = index
        suite = str(entry.get("suite", self.config.suite))
        task_id = int(entry.get("task_id", self.config.task_id))
        init_idx = int(entry.get("init_state_index", 0))
        self._current_category = str(entry.get("category", ""))
        self._current_perturbation = str(entry.get("perturbation", ""))

        if (suite != self.config.suite or task_id != self.config.task_id) and self.remake_env is not None:
            bundle = self.remake_env(suite, task_id)
            close = getattr(self.env, "close", None)
            if callable(close):
                close()
            self.env = bundle.env
            self.init_states = list(bundle.init_states)
            self.config.suite = suite
            self.config.task_id = bundle.task_id
            self.config.language = bundle.language
        elif suite != self.config.suite:
            self.config.suite = suite
            self.config.task_id = task_id

        self._init_state_index = init_idx
        self._obs = self._apply_current_init()
        if advance_after and index < len(q):
            self._queue_index = index + 1

    def _apply_current_init(self) -> Any:
        """現在の init_state_index を env に適用する。"""
        self._env_done = False
        if not self.init_states:
            return self.env.reset()
        i = self._init_state_index % len(self.init_states)
        self.env.reset()
        set_fn = getattr(self.env, "set_init_state", None)
        if callable(set_fn):
            return set_fn(self.init_states[i])
        return self.env.reset()


def run_fake_episode(
    *,
    dataset_root: Path,
    num_frames: int = 16,
    create_dataset: bool = False,
    language: str = "fake vr teleop",
    image_size: tuple[int, int] = (64, 64),
    require_success: bool = False,
    success_after: int | None = 1,
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
        require_success=require_success,
        fake=True,
    )
    env = FakeLiberoEnv(
        height=image_size[0],
        width=image_size[1],
        success_after=success_after,
        n_init_states=3,
    )
    session = TeleopSession(
        env=env,
        config=cfg,
        send=_send,
        init_states=list(range(3)),
    )
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
