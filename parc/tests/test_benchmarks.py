"""汎用ベンチマーク枠のユニットテスト。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from parc.benchmarks import get_benchmark, list_benchmarks
from parc.benchmarks.metaworld_mt50 import MT50_TASK_NAMES, metaworld_available
from parc.data.benchmark_dataset import (
    ensure_train_benchmark_supported,
    get_dataset_spec,
    write_dataset_skeleton,
)
from parc.env.metrics import EpisodeMetrics, aggregate
from parc.eval.runner import _resolve_backend_name


def test_list_benchmarks_includes_libero_and_mt50() -> None:
    names = list_benchmarks()
    assert "libero" in names
    assert "metaworld_mt50" in names


def test_get_benchmark_unknown_raises() -> None:
    with pytest.raises(KeyError, match="Unknown benchmark"):
        get_benchmark("not_a_real_backend")


def test_mt50_task_count_is_50() -> None:
    assert len(MT50_TASK_NAMES) == 50
    assert len(set(MT50_TASK_NAMES)) == 50


def test_resolve_backend_name_defaults_and_aliases() -> None:
    assert _resolve_backend_name({}) == "libero"
    assert _resolve_backend_name({"suite": "libero_spatial"}) == "libero"
    assert _resolve_backend_name({"backend": "metaworld_mt50"}) == "metaworld_mt50"
    assert _resolve_backend_name({"suite": "mt50"}) == "metaworld_mt50"


def test_libero_dataset_spec_action_dim() -> None:
    spec = get_dataset_spec("libero")
    assert spec.action_dim == 7
    assert spec.robot_type == "panda"


def test_mt50_dataset_spec_and_skeleton(tmp_path: Path) -> None:
    spec = get_dataset_spec("metaworld_mt50")
    assert spec.action_dim == 4
    assert spec.robot_type == "sawyer"
    path = write_dataset_skeleton(tmp_path / "ds", spec)
    assert path.is_file()
    assert "metaworld_mt50" in path.read_text()


def test_ensure_train_blocks_mt50() -> None:
    result = ensure_train_benchmark_supported(
        {
            "benchmark": {"backend": "metaworld_mt50"},
            "train": {"dataset_root": None},
        }
    )
    assert result is not None
    assert result["status"] == "not_implemented"
    assert result["backend"] == "metaworld_mt50"


def test_ensure_train_allows_libero_default() -> None:
    assert ensure_train_benchmark_supported({"train": {"backend": "lerobot"}}) is None


def test_aggregate_includes_by_task() -> None:
    eps = [
        EpisodeMetrics(
            suite="mt50",
            task_id=0,
            task_name="reach-v3",
            category="reach-v3",
            trial=0,
            success=True,
            steps=10,
        ),
        EpisodeMetrics(
            suite="mt50",
            task_id=0,
            task_name="reach-v3",
            category="reach-v3",
            trial=1,
            success=False,
            steps=20,
        ),
    ]
    summary = aggregate(eps)
    assert "reach-v3" in summary.by_task
    assert summary.by_task["reach-v3"]["success_rate"] == pytest.approx(0.5)


def test_mt50_list_task_ids_requires_explicit() -> None:
    backend = get_benchmark("metaworld_mt50")()
    with pytest.raises(ValueError, match="task_ids"):
        backend.list_task_ids({})
    assert backend.list_task_ids({"task_ids": [0, 2]}) == [0, 2]


@pytest.mark.skipif(not metaworld_available(), reason="metaworld optional dep missing")
def test_mt50_make_env_and_one_step() -> None:
    backend = get_benchmark("metaworld_mt50")()
    reach_id = MT50_TASK_NAMES.index("reach-v3")
    eval_cfg = {"task_ids": [reach_id], "_seed": 0}
    env = backend.make_env(reach_id, eval_cfg)
    try:
        obs = backend.reset_episode(
            env, task_id=reach_id, trial=0, seed=0, eval_cfg=eval_cfg
        )
        assert "state" in obs
        action = np.zeros(backend.action_dim, dtype=np.float32)
        obs2, reward, done, info = env.step(action)
        assert isinstance(obs2, dict)
        assert isinstance(reward, float)
        _ = backend.success(obs2, reward, done, info, env)
    finally:
        env.close()
