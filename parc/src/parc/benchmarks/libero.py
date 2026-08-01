"""LIBERO / LIBERO-plus ベンチマークアダプタ。"""

from __future__ import annotations

from typing import Any, Mapping

from parc.benchmarks.base import BenchmarkBackend, DatasetSpec
from parc.benchmarks.registry import register_benchmark
from parc.env.make_env import (
    category_for_task,
    make_offscreen_env,
    select_task_ids,
)
from parc.env.success import is_libero_success


@register_benchmark
class LiberoBackend(BenchmarkBackend):
    """既存 LIBERO-plus OffScreenRenderEnv 経路。"""

    name = "libero"

    def __init__(self) -> None:
        self._bench: Any | None = None
        self._suite: str | None = None

    @property
    def action_dim(self) -> int:
        return 7

    @property
    def obs_keys(self) -> tuple[str, ...]:
        return (
            "agentview_image",
            "robot0_eye_in_hand_image",
            "robot0_eef_pos",
            "robot0_eef_quat",
            "robot0_gripper_qpos",
        )

    def _ensure_bench(self, suite: str) -> Any:
        if self._bench is not None and self._suite == suite:
            return self._bench
        import torch
        from libero.libero import benchmark

        # PyTorch>=2.6: 公式 init_states は weights_only=False で読む
        if not getattr(LiberoBackend, "_torch_patched", False):
            _orig = torch.load

            def _load_trusted(*args: Any, **kwargs: Any) -> Any:
                kwargs.setdefault("weights_only", False)
                return _orig(*args, **kwargs)

            torch.load = _load_trusted  # type: ignore[assignment]
            LiberoBackend._torch_patched = True  # type: ignore[attr-defined]
            LiberoBackend._torch_orig_load = _orig  # type: ignore[attr-defined]

        bench_cls = benchmark.get_benchmark(suite)
        self._bench = bench_cls()
        self._suite = suite
        return self._bench

    def list_task_ids(self, eval_cfg: Mapping[str, Any]) -> list[int]:
        suite = str(eval_cfg.get("suite", "libero_spatial"))
        task_ids = eval_cfg.get("task_ids")
        tasks_per_category = eval_cfg.get("tasks_per_category")
        return select_task_ids(
            suite,
            task_ids=list(task_ids) if task_ids is not None else None,
            tasks_per_category=int(tasks_per_category)
            if tasks_per_category is not None
            else None,
        )

    def make_env(self, task_id: int, eval_cfg: Mapping[str, Any]) -> Any:
        suite = str(eval_cfg.get("suite", "libero_spatial"))
        bench = self._ensure_bench(suite)
        bddl = bench.get_task_bddl_file_path(task_id)
        cam_h = int(eval_cfg.get("camera_height", 128))
        cam_w = int(eval_cfg.get("camera_width", 128))
        return make_offscreen_env(bddl, camera_heights=cam_h, camera_widths=cam_w)

    def reset_episode(
        self,
        env: Any,
        *,
        task_id: int,
        trial: int,
        seed: int,
        eval_cfg: Mapping[str, Any],
    ) -> dict[str, Any]:
        suite = str(eval_cfg.get("suite", "libero_spatial"))
        bench = self._ensure_bench(suite)
        init_states = bench.get_task_init_states(task_id)
        init = init_states[trial % len(init_states)]
        env.reset()
        obs = env.set_init_state(init)
        return dict(obs)

    def success(
        self,
        obs: Mapping[str, Any],
        reward: float,
        done: bool,
        info: Mapping[str, Any] | None,
        env: Any,
    ) -> bool:
        return is_libero_success(reward, done, info, env)

    def task_name(self, task_id: int) -> str:
        if self._bench is None:
            return f"task_{task_id}"
        task = self._bench.get_task(task_id)
        return str(getattr(task, "name", f"task_{task_id}"))

    def task_language(self, task_id: int) -> str:
        if self._bench is None:
            return self.task_name(task_id)
        task = self._bench.get_task(task_id)
        return str(getattr(task, "language", "") or self.task_name(task_id))

    def category_for_task(self, task_id: int, eval_cfg: Mapping[str, Any]) -> str:
        if not eval_cfg.get("use_classification", True):
            return "Unknown"
        suite = str(eval_cfg.get("suite", "libero_spatial"))
        return category_for_task(suite, task_id)

    def uses_perturbation_categories(self) -> bool:
        return True

    def dataset_spec(self) -> DatasetSpec:
        return DatasetSpec(
            backend=self.name,
            robot_type="panda",
            action_dim=7,
            fps=10,
            features={
                "observation.images.image": {
                    "dtype": "image",
                    "shape": [128, 128, 3],
                },
                "observation.images.wrist_image": {
                    "dtype": "image",
                    "shape": [128, 128, 3],
                },
                "observation.state": {"dtype": "float32", "shape": [8]},
                "action": {"dtype": "float32", "shape": [7]},
            },
            dataset_repo_id="lerobot/libero_plus",
            notes="LIBERO-plus / Panda EE 7-DoF（既存パイプライン）。",
        )
