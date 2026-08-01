"""デモフレームのバッファと LeRobot Dataset v3.0 書き込み。

v3.0 注意:
- `timestamp` / `frame_index` / `episode_index` / `index` / `task_index` は
  LeRobot が自動付与する（DEFAULT_FEATURES）。`add_frame` に渡してはいけない。
- 呼び出し側は user features + `task` のみ渡す。
- 書き込み後は必ず `finalize()` する。
- 制御時刻・収集メタは schema 外サイドカー（episode_quality / timestamps / collection_info）。
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from parc.vr.collection_meta import (
    COLLECTION_INFO_NAME,
    build_collection_info,
    write_collection_info,
)

logger = logging.getLogger(__name__)

# 学習互換の user features（DEFAULT_FEATURES は create 時に自動マージ）
LEROBOT_USER_FEATURES: dict[str, dict[str, Any]] = {
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

# 後方互換エイリアス
LEROBOT_FEATURES = LEROBOT_USER_FEATURES

QUALITY_JSONL_NAME = "episode_quality.jsonl"
TIMESTAMPS_JSONL_NAME = "episode_timestamps.jsonl"
COLLECTION_STATS_NAME = "collection_stats.json"
CODEBASE_VERSION_V3 = "v3.0"


@dataclass
class FrameBuffer:
    """1 エピソード分のフレームをメモリに保持する。"""

    language: str = ""
    frames: list[dict[str, Any]] = field(default_factory=list)

    def clear(self) -> None:
        """バッファを空にする。"""
        self.frames.clear()

    def append(self, frame: dict[str, Any]) -> None:
        """front/wrist/state/action[/control_t] を追加する。"""
        required = ("front", "wrist", "state", "action")
        for key in required:
            if key not in frame:
                raise KeyError(f"missing frame key: {key}")
        # control_t = クライアント時刻 or wall 相対。LeRobot の timestamp とは別物。
        control_t = frame.get("control_t", frame.get("timestamp", 0.0))
        self.frames.append(
            {
                "front": np.asarray(frame["front"], dtype=np.uint8),
                "wrist": np.asarray(frame["wrist"], dtype=np.uint8),
                "state": np.asarray(frame["state"], dtype=np.float32).reshape(8),
                "action": np.asarray(frame["action"], dtype=np.float32).reshape(7),
                "control_t": float(control_t),
            }
        )

    @property
    def num_frames(self) -> int:
        """バッファ内フレーム数。"""
        return len(self.frames)

    def control_timestamps(self) -> list[float]:
        """制御／壁時計ベースの相対秒リスト（Approximate Time 用）。"""
        return [float(fr["control_t"]) for fr in self.frames]

    def lerobot_timestamps(self, fps: int) -> list[float]:
        """v3.0 と同じ `frame_index / fps` のタイムスタンプ列。"""
        rate = float(fps) if fps > 0 else 1.0
        return [i / rate for i in range(self.num_frames)]


@dataclass
class CollectionStats:
    """セッション単位の収集コスト指標。"""

    attempted: int = 0
    saved: int = 0
    saved_success: int = 0
    saved_failed: int = 0
    discarded: int = 0
    refused: int = 0
    degraded: int = 0
    refused_latency: int = 0
    dropped_stale_controls: int = 0
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, float | int]:
        """JSON 用 dict。"""
        wall = max(0.0, time.time() - self.started_at)
        hours = wall / 3600.0 if wall > 0 else 0.0
        saved_per_hour = float(self.saved) / hours if hours > 0 else 0.0
        return {
            "attempted": self.attempted,
            "saved": self.saved,
            "saved_success": self.saved_success,
            "saved_failed": self.saved_failed,
            "discarded": self.discarded,
            "refused": self.refused,
            "degraded": self.degraded,
            "refused_latency": self.refused_latency,
            "dropped_stale_controls": self.dropped_stale_controls,
            "wall_sec": round(wall, 3),
            "saved_per_hour": round(saved_per_hour, 3),
        }


@dataclass
class EpisodeRecorder:
    """LeRobot Dataset v3.0 へエピソードを追記する。

    lerobot が無い環境では `create_dataset=False` でバッファ検証のみ可能。
    """

    root: Path
    repo_id: str = "local/vr_libero_demos"
    fps: int = 20
    robot_type: str = "panda"
    image_size: tuple[int, int] = (256, 256)
    create_dataset: bool = True
    collection_info: dict[str, Any] | None = None
    _ds: Any = field(default=None, init=False, repr=False)
    _episode_count: int = field(default=0, init=False)
    buffer: FrameBuffer = field(default_factory=FrameBuffer)
    stats: CollectionStats = field(default_factory=CollectionStats)

    def __post_init__(self) -> None:
        """必要なら v3.0 データセットをオープン／作成し、collection_info を書く。"""
        self.root = Path(self.root).expanduser().resolve()
        h, w = self.image_size
        features = {
            "observation.images.front": {
                **LEROBOT_USER_FEATURES["observation.images.front"],
                "shape": (h, w, 3),
            },
            "observation.images.wrist": {
                **LEROBOT_USER_FEATURES["observation.images.wrist"],
                "shape": (h, w, 3),
            },
            "observation.state": LEROBOT_USER_FEATURES["observation.state"],
            "action": LEROBOT_USER_FEATURES["action"],
        }

        if self.create_dataset:
            self._open_or_create_lerobot_dataset(features)

        info = self.collection_info or build_collection_info(
            fps=self.fps,
            robot_type=self.robot_type,
            image_size=self.image_size,
        )
        info.setdefault("lerobot_codebase_version", CODEBASE_VERSION_V3)
        write_collection_info(self.root, info)

    def _open_or_create_lerobot_dataset(self, features: dict[str, Any]) -> None:
        """既存ローカル DS を resume、無ければ create。不完全な空 DS は作り直す。

        新しめの LeRobot は ``LeRobotDataset(repo_id, root=...)`` が Hub を見に行く。
        書き込み再開は ``resume()``。create 直後（episodes=0・tasks 無し）だと
        resume も Hub 404 になるため、空なら root を消して create し直す。
        """
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

        meta = self.root / "meta" / "info.json"
        tasks = self.root / "meta" / "tasks.parquet"
        if meta.is_file():
            total = 0
            try:
                total = int(json.loads(meta.read_text(encoding="utf-8")).get("total_episodes", 0))
            except Exception:
                total = 0
            # create 直後・未保存のローカル DS は Hub 無しでは resume できない
            if total == 0 and not tasks.is_file():
                logger.warning(
                    "incomplete empty dataset at %s (no tasks.parquet); recreating",
                    self.root,
                )
                shutil.rmtree(self.root)
            else:
                self._ds = LeRobotDataset.resume(repo_id=self.repo_id, root=self.root)
                try:
                    self._episode_count = int(self._ds.meta.total_episodes)
                except Exception:
                    self._episode_count = total
                self._assert_v3_metadata()
                return

        if self.root.exists():
            leftover = [p for p in self.root.rglob("*") if p.is_file()]
            if leftover:
                raise FileExistsError(
                    f"dataset root already has files but no meta/info.json: {self.root}"
                )
            self.root.rmdir()
        self._ds = LeRobotDataset.create(
            repo_id=self.repo_id,
            fps=self.fps,
            robot_type=self.robot_type,
            features=features,
            root=self.root,
            use_videos=True,
        )
        self._episode_count = 0
        self._assert_v3_metadata()

    def _assert_v3_metadata(self) -> None:
        """info.json の codebase_version が v3 系であることを確認する。"""
        if self._ds is None:
            return
        version = str(getattr(self._ds.meta, "_version", "") or "")
        info = getattr(self._ds.meta, "info", {}) or {}
        code_ver = str(info.get("codebase_version", version))
        if not code_ver.startswith("v3"):
            raise RuntimeError(
                f"LeRobotDataset must be v3.x, got codebase_version={code_ver!r}"
            )

    def start_episode(self, language: str) -> None:
        """新規エピソードのバッファを開始する。"""
        self.buffer = FrameBuffer(language=language)
        self.buffer.clear()
        self.buffer.language = language
        self.stats.attempted += 1

    def add_frame(self, frame: dict[str, Any]) -> None:
        """現エピソードへ 1 フレーム追加。"""
        self.buffer.append(frame)

    def discard_episode(self) -> None:
        """バッファを捨てる。"""
        if self.buffer.num_frames > 0 or self.stats.attempted > 0:
            self.stats.discarded += 1
        self.buffer.clear()

    def refuse_save(self) -> None:
        """成功ゲート等で保存を拒否した回数を記録する。"""
        self.stats.refused += 1

    def save_episode(
        self,
        *,
        quality: dict[str, Any] | None = None,
    ) -> int:
        """バッファをデータセットへ書き、エピソード index を返す。"""
        if self.buffer.num_frames == 0:
            raise RuntimeError("empty episode; nothing to save")
        lang = self.buffer.language or "vr teleop demo"
        n_frames = self.buffer.num_frames
        control_ts = self.buffer.control_timestamps()
        lerobot_ts = self.buffer.lerobot_timestamps(self.fps)
        success = True
        if quality is not None and "success" in quality:
            success = bool(quality["success"])

        if self._ds is None:
            idx = self._episode_count
            self._episode_count += 1
            self.buffer.clear()
            self._bump_saved(success)
            self._append_sidecars(idx, n_frames, lang, quality, control_ts, lerobot_ts)
            return idx

        for fr in self.buffer.frames:
            # v3.0: timestamp/frame_index は渡さない。task は必須。
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
        self._bump_saved(success)
        self._append_sidecars(idx, n_frames, lang, quality, control_ts, lerobot_ts)
        return idx

    def _bump_saved(self, success: bool) -> None:
        """保存カウンタを更新する。"""
        self.stats.saved += 1
        if success:
            self.stats.saved_success += 1
        else:
            self.stats.saved_failed += 1

    def _meta_dir(self) -> Path:
        """meta ディレクトリを確保して返す。"""
        meta = self.root / "meta"
        meta.mkdir(parents=True, exist_ok=True)
        return meta

    def _append_sidecars(
        self,
        episode_index: int,
        num_frames: int,
        language: str,
        quality: dict[str, Any] | None,
        control_ts: list[float],
        lerobot_ts: list[float],
    ) -> None:
        """品質メタと Approximate Time 用タイムスタンプを追記する。"""
        t0 = float(lerobot_ts[0]) if lerobot_ts else 0.0
        t1 = float(lerobot_ts[-1]) if lerobot_ts else 0.0
        row: dict[str, Any] = {
            "episode_index": episode_index,
            "language": language,
            "task": language,
            "num_frames": num_frames,
            "success": True,
            "fps": self.fps,
            "t_start": t0,
            "t_end": t1,
            "sync_policy": "approximate_time",
            "lerobot_codebase_version": CODEBASE_VERSION_V3,
        }
        if quality:
            row.update(quality)
            row["episode_index"] = episode_index
            row["num_frames"] = num_frames
            row.setdefault("language", language)
            row.setdefault("task", language)
            row.setdefault("fps", self.fps)
            row.setdefault("sync_policy", "approximate_time")
            row.setdefault("lerobot_codebase_version", CODEBASE_VERSION_V3)
        path = self._meta_dir() / QUALITY_JSONL_NAME
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

        ts_path = self._meta_dir() / TIMESTAMPS_JSONL_NAME
        ts_row = {
            "episode_index": episode_index,
            "fps": self.fps,
            "timestamps": lerobot_ts,  # LeRobot v3 と同一定義 (i/fps)
            "control_timestamps": control_ts,  # Approximate Time / 遅延解析用
            "t0_unix": (quality or {}).get("t0_unix"),
            "t_end_unix": (quality or {}).get("t_end_unix"),
            "sync_policy": "approximate_time",
        }
        with ts_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ts_row, ensure_ascii=False) + "\n")

    def write_collection_stats(self) -> Path:
        """セッション集計を `meta/collection_stats.json` に書く。"""
        path = self._meta_dir() / COLLECTION_STATS_NAME
        path.write_text(
            json.dumps(self.stats.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def dataset_summary(self) -> dict[str, object]:
        """保存先データセットの最低限の状態を返す。"""
        meta = self.root / "meta"
        info_path = meta / "info.json"
        codebase = None
        if info_path.is_file():
            try:
                codebase = json.loads(info_path.read_text(encoding="utf-8")).get(
                    "codebase_version"
                )
            except json.JSONDecodeError:
                codebase = None
        return {
            "root": str(self.root),
            "meta_exists": info_path.is_file(),
            "codebase_version": codebase,
            "episode_count": self._episode_count,
            "quality_jsonl_exists": (meta / QUALITY_JSONL_NAME).is_file(),
            "collection_info_exists": (meta / COLLECTION_INFO_NAME).is_file(),
            "collection_stats": self.stats.to_dict(),
        }

    def finalize(self) -> None:
        """v3.0 必須: parquet writer を閉じ、収集統計を書き出す。"""
        self.write_collection_stats()
        if self._ds is not None and hasattr(self._ds, "finalize"):
            self._ds.finalize()
