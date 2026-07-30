"""デモフレームのバッファと LeRobot 書き込み。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# convert_demo_to_lerobot.py と同スキーマ
LEROBOT_FEATURES: dict[str, dict[str, Any]] = {
    "observation.images.front": {
        "dtype": "video",
        "shape": (256, 256, 3),
        "names": ["height", "width", "channel"],
    },
    "observation.images.wrist": {
        "dtype": "video",
        "shape": (256, 256, 3),
        "names": ["height", "width", "channel"],
    },
    "observation.state": {
        "dtype": "float32",
        "shape": (8,),
        "names": [f"state_{i}" for i in range(8)],
    },
    "action": {
        "dtype": "float32",
        "shape": (7,),
        "names": [f"action_{i}" for i in range(7)],
    },
}


@dataclass
class FrameBuffer:
    """1 エピソード分のフレームをメモリに保持する。"""

    language: str = ""
    frames: list[dict[str, np.ndarray]] = field(default_factory=list)

    def clear(self) -> None:
        """バッファを空にする。"""
        self.frames.clear()

    def append(self, frame: dict[str, np.ndarray]) -> None:
        """front/wrist/state/action を追加する。"""
        required = ("front", "wrist", "state", "action")
        for key in required:
            if key not in frame:
                raise KeyError(f"missing frame key: {key}")
        self.frames.append(
            {
                "front": np.asarray(frame["front"], dtype=np.uint8),
                "wrist": np.asarray(frame["wrist"], dtype=np.uint8),
                "state": np.asarray(frame["state"], dtype=np.float32).reshape(8),
                "action": np.asarray(frame["action"], dtype=np.float32).reshape(7),
            }
        )

    @property
    def num_frames(self) -> int:
        """バッファ内フレーム数。"""
        return len(self.frames)


@dataclass
class EpisodeRecorder:
    """LeRobot v3 データセットへエピソードを追記する。

    lerobot が無い環境では `create_dataset=False` でバッファ検証のみ可能。
    """

    root: Path
    repo_id: str = "local/vr_libero_demos"
    fps: int = 20
    robot_type: str = "panda"
    image_size: tuple[int, int] = (256, 256)
    create_dataset: bool = True
    _ds: Any = field(default=None, init=False, repr=False)
    _episode_count: int = field(default=0, init=False)
    buffer: FrameBuffer = field(default_factory=FrameBuffer)

    def __post_init__(self) -> None:
        """必要ならデータセットをオープン／作成する。"""
        self.root = Path(self.root).expanduser().resolve()
        h, w = self.image_size
        # 特徴量の画像サイズを実行時解像度に合わせる
        features = {
            "observation.images.front": {
                **LEROBOT_FEATURES["observation.images.front"],
                "shape": (h, w, 3),
            },
            "observation.images.wrist": {
                **LEROBOT_FEATURES["observation.images.wrist"],
                "shape": (h, w, 3),
            },
            "observation.state": LEROBOT_FEATURES["observation.state"],
            "action": LEROBOT_FEATURES["action"],
        }
        if not self.create_dataset:
            return
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

        self.root.mkdir(parents=True, exist_ok=True)
        meta = self.root / "meta" / "info.json"
        if meta.is_file():
            self._ds = LeRobotDataset(self.repo_id, root=self.root)
            # 既存エピソード数をメタから推定
            try:
                self._episode_count = int(self._ds.meta.total_episodes)
            except Exception:
                self._episode_count = 0
        else:
            self._ds = LeRobotDataset.create(
                repo_id=self.repo_id,
                fps=self.fps,
                robot_type=self.robot_type,
                features=features,
                root=self.root,
                use_videos=True,
            )

    def start_episode(self, language: str) -> None:
        """新規エピソードのバッファを開始する。"""
        self.buffer = FrameBuffer(language=language)
        self.buffer.clear()
        self.buffer.language = language

    def add_frame(self, frame: dict[str, np.ndarray]) -> None:
        """現エピソードへ 1 フレーム追加。"""
        # 解像度が違う場合は単純リサイズしない（呼び出し側で揃える）
        self.buffer.append(frame)

    def discard_episode(self) -> None:
        """バッファを捨てる。"""
        self.buffer.clear()

    def save_episode(self) -> int:
        """バッファをデータセットへ書き、エピソード index を返す。"""
        if self.buffer.num_frames == 0:
            raise RuntimeError("empty episode; nothing to save")
        lang = self.buffer.language or "vr teleop demo"
        if self._ds is None:
            # ドライラン: ディスク書き込みなし
            idx = self._episode_count
            self._episode_count += 1
            n = self.buffer.num_frames
            self.buffer.clear()
            return idx

        for fr in self.buffer.frames:
            self._ds.add_frame(
                {
                    "observation.images.front": fr["front"],
                    "observation.images.wrist": fr["wrist"],
                    "observation.state": fr["state"],
                    "action": fr["action"],
                    "task": lang,
                }
            )
        self._ds.save_episode()
        idx = self._episode_count
        self._episode_count += 1
        self.buffer.clear()
        return idx

    def finalize(self) -> None:
        """データセットを閉じる。"""
        if self._ds is not None and hasattr(self._ds, "finalize"):
            self._ds.finalize()
