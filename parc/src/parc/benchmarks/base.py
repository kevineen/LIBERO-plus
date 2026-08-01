"""ベンチマーク共通契約（LIBERO / Meta-World 等）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class DatasetSpec:
    """学習骨格用のデータ契約（LeRobot 向け宣言）。

    実デモ変換は後続。ここでは features / action_dim 等を明示する。
    """

    backend: str
    robot_type: str
    action_dim: int
    fps: int = 10
    # LeRobot features 風の宣言（name → {dtype, shape, ...}）
    features: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Hub / ローカルのプレースホルダ ID
    dataset_repo_id: str = ""
    notes: str = ""


class BenchmarkBackend(ABC):
    """評価・学習骨格が依存するベンチ非依存 API。"""

    #: レジストリキー（例: ``libero``, ``metaworld_mt50``）
    name: str = ""

    @property
    @abstractmethod
    def action_dim(self) -> int:
        """方策アクション次元。"""

    @property
    def obs_keys(self) -> tuple[str, ...]:
        """主要な観測キー（ドキュメント・骨格用）。"""
        return ()

    @abstractmethod
    def list_task_ids(self, eval_cfg: Mapping[str, Any]) -> list[int]:
        """評価する 0-based task index 一覧。"""

    @abstractmethod
    def make_env(self, task_id: int, eval_cfg: Mapping[str, Any]) -> Any:
        """タスク用環境。``reset`` / ``step`` / ``close`` を持つ。

        任意: ``set_init_state`` / ``check_success``。
        ``step`` は ``(obs_dict, reward, done, info)`` の 4-tuple を返すこと
        （Gymnasium の terminated/truncated はアダプタ側で合流させる）。
        """

    @abstractmethod
    def reset_episode(
        self,
        env: Any,
        *,
        task_id: int,
        trial: int,
        seed: int,
        eval_cfg: Mapping[str, Any],
    ) -> dict[str, Any]:
        """エピソード開始。初期観測 dict を返す。"""

    @abstractmethod
    def success(
        self,
        obs: Mapping[str, Any],
        reward: float,
        done: bool,
        info: Mapping[str, Any] | None,
        env: Any,
    ) -> bool:
        """成功判定。"""

    @abstractmethod
    def task_name(self, task_id: int) -> str:
        """タスク識別名。"""

    def task_language(self, task_id: int) -> str:
        """VLA 向け言語指示（無ければタスク名）。"""
        return self.task_name(task_id)

    def category_for_task(self, task_id: int, eval_cfg: Mapping[str, Any]) -> str:
        """摂動カテゴリ等。無い場合はタスク名を返す。"""
        return self.task_name(task_id)

    def uses_perturbation_categories(self) -> bool:
        """``by_category`` を摂動軸として意味づけるか（LIBERO-plus）。"""
        return False

    @abstractmethod
    def dataset_spec(self) -> DatasetSpec:
        """学習レシピ骨格用の DatasetSpec。"""
