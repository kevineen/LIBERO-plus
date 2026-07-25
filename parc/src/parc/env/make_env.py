"""LIBERO-plus 環境まわりのヘルパ。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from parc.paths import get_paths

# 公式リーダーボードで使う 4 suite
DEFAULT_SUITES = ("libero_spatial", "libero_object", "libero_goal", "libero_10")

# task_classification.json のカテゴリ名（英語）
PERTURBATION_CATEGORIES = (
    "Camera Viewpoints",
    "Robot Initial States",
    "Language Instructions",
    "Light Conditions",
    "Background Textures",
    "Sensor Noise",
    "Objects Layout",
)


def load_classification() -> dict[str, list[dict[str, Any]]]:
    """suite → タスクメタ情報リスト。"""
    path = get_paths()["classification_json"]
    if not path.is_file():
        raise FileNotFoundError(f"task_classification.json not found: {path}")
    return json.loads(path.read_text())


def select_task_ids(
    suite: str,
    task_ids: list[int] | None,
    tasks_per_category: int | None = None,
) -> list[int]:
    """評価する task index を決める。

    LIBERO-plus の Benchmark は 0-based index。
    classification の id は 1-based なので、index = id - 1。
    """
    if task_ids is not None:
        return list(task_ids)

    if tasks_per_category is None:
        # 全タスクは重いので、明示指定なしならエラーにする
        raise ValueError(
            "eval.task_ids か eval.tasks_per_category のどちらかを指定してください。"
        )

    classif = load_classification()
    if suite not in classif:
        raise KeyError(f"suite {suite!r} not in classification")

    by_cat: dict[str, list[int]] = {c: [] for c in PERTURBATION_CATEGORIES}
    for item in classif[suite]:
        cat = item.get("category", "Unknown")
        idx = int(item["id"]) - 1
        by_cat.setdefault(cat, []).append(idx)

    selected: list[int] = []
    for cat in PERTURBATION_CATEGORIES:
        ids = by_cat.get(cat, [])
        selected.extend(ids[:tasks_per_category])
    # 安定のためソート
    return sorted(set(selected))


def category_for_task(suite: str, task_index: int) -> str:
    """0-based task index → 摂動カテゴリ名。"""
    classif = load_classification()
    items = classif.get(suite, [])
    target_id = task_index + 1
    for item in items:
        if int(item["id"]) == target_id:
            return str(item.get("category", "Unknown"))
    return "Unknown"


def make_offscreen_env(
    bddl_file: str,
    *,
    camera_heights: int = 128,
    camera_widths: int = 128,
) -> Any:
    """OffScreenRenderEnv を生成する（libero が必要）。"""
    # robosuite 1.4 × MuJoCo 3.10 の mj_fullM 差を吸収
    from parc.env.mujoco_compat import patch_robosuite_mj_fullM

    patch_robosuite_mj_fullM()
    from libero.libero.envs import OffScreenRenderEnv

    return OffScreenRenderEnv(
        bddl_file_name=bddl_file,
        camera_heights=camera_heights,
        camera_widths=camera_widths,
    )
