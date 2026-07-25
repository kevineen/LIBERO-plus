"""評価メトリクス（成功率 + PARC 向け予備指標）。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np


@dataclass
class EpisodeMetrics:
    """1 エピソード分。"""

    suite: str
    task_id: int
    task_name: str
    category: str
    trial: int
    success: bool
    steps: int
    # PARC 説明会で言及された指標のプレースホルダ（ルール確定後に精密化）
    path_length: float = 0.0
    jerk: float = 0.0
    collision: bool = False


@dataclass
class EvalSummary:
    """集計結果。"""

    n_episodes: int = 0
    success_rate: float = 0.0
    mean_steps: float = 0.0
    by_category: dict[str, dict[str, float]] = field(default_factory=dict)
    episodes: list[dict[str, Any]] = field(default_factory=list)


def _jerk(actions: list[np.ndarray]) -> float:
    """アクション差分の L2 平均を簡易ジャーク代理指標にする。"""
    if len(actions) < 2:
        return 0.0
    diffs = [np.linalg.norm(actions[i] - actions[i - 1]) for i in range(1, len(actions))]
    return float(np.mean(diffs))


def _path_length(ee_positions: list[np.ndarray]) -> float:
    """エンドエフェクタ位置の累積移動距離。"""
    if len(ee_positions) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(ee_positions)):
        total += float(np.linalg.norm(ee_positions[i] - ee_positions[i - 1]))
    return total


def finalize_episode(
    *,
    suite: str,
    task_id: int,
    task_name: str,
    category: str,
    trial: int,
    success: bool,
    steps: int,
    actions: list[np.ndarray],
    ee_positions: list[np.ndarray],
    collision: bool = False,
) -> EpisodeMetrics:
    """エピソード終了時にメトリクスを確定する。"""
    return EpisodeMetrics(
        suite=suite,
        task_id=task_id,
        task_name=task_name,
        category=category,
        trial=trial,
        success=success,
        steps=steps,
        path_length=_path_length(ee_positions),
        jerk=_jerk(actions),
        collision=collision,
    )


def aggregate(episodes: list[EpisodeMetrics]) -> EvalSummary:
    """カテゴリ別成功率などを集計する。"""
    if not episodes:
        return EvalSummary()

    succ = [float(e.success) for e in episodes]
    steps = [float(e.steps) for e in episodes]
    by_cat_succ: dict[str, list[float]] = defaultdict(list)
    by_cat_steps: dict[str, list[float]] = defaultdict(list)
    for e in episodes:
        by_cat_succ[e.category].append(float(e.success))
        by_cat_steps[e.category].append(float(e.steps))

    by_category = {
        cat: {
            "n": float(len(vals)),
            "success_rate": float(np.mean(vals)),
            "mean_steps": float(np.mean(by_cat_steps[cat])),
        }
        for cat, vals in sorted(by_cat_succ.items())
    }
    return EvalSummary(
        n_episodes=len(episodes),
        success_rate=float(np.mean(succ)),
        mean_steps=float(np.mean(steps)),
        by_category=by_category,
        episodes=[asdict(e) for e in episodes],
    )
