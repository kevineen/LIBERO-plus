"""Meta-World MT50 ベンチマークアダプタ（Farama Meta-World v3 / Gymnasium）。"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from parc.benchmarks.base import BenchmarkBackend, DatasetSpec
from parc.benchmarks.registry import register_benchmark

# Farama Meta-World v3 の MT50 = ALL_V3_ENVIRONMENTS 固定順（env_dict.py 準拠）
MT50_TASK_NAMES: tuple[str, ...] = (
    "assembly-v3",
    "basketball-v3",
    "bin-picking-v3",
    "box-close-v3",
    "button-press-topdown-v3",
    "button-press-topdown-wall-v3",
    "button-press-v3",
    "button-press-wall-v3",
    "coffee-button-v3",
    "coffee-pull-v3",
    "coffee-push-v3",
    "dial-turn-v3",
    "disassemble-v3",
    "door-close-v3",
    "door-lock-v3",
    "door-open-v3",
    "door-unlock-v3",
    "hand-insert-v3",
    "drawer-close-v3",
    "drawer-open-v3",
    "faucet-open-v3",
    "faucet-close-v3",
    "hammer-v3",
    "handle-press-side-v3",
    "handle-press-v3",
    "handle-pull-side-v3",
    "handle-pull-v3",
    "lever-pull-v3",
    "pick-place-wall-v3",
    "pick-out-of-hole-v3",
    "pick-place-v3",
    "plate-slide-v3",
    "plate-slide-side-v3",
    "plate-slide-back-v3",
    "plate-slide-back-side-v3",
    "peg-insert-side-v3",
    "peg-unplug-side-v3",
    "soccer-v3",
    "stick-push-v3",
    "stick-pull-v3",
    "push-v3",
    "push-wall-v3",
    "push-back-v3",
    "reach-v3",
    "reach-wall-v3",
    "shelf-place-v3",
    "sweep-into-v3",
    "sweep-v3",
    "window-open-v3",
    "window-close-v3",
)

assert len(MT50_TASK_NAMES) == 50


def metaworld_available() -> bool:
    """optional 依存が入っているか。"""
    try:
        import gymnasium  # noqa: F401
        import metaworld  # noqa: F401

        return True
    except ImportError:
        return False


def _require_metaworld() -> None:
    if metaworld_available():
        return
    raise ImportError(
        "Meta-World MT50 には optional 依存が必要です。\n"
        "  推奨: 別 venv で `uv pip install 'parc[metaworld]'`\n"
        "  または: `uv pip install metaworld gymnasium mujoco`\n"
        "LIBERO 親 venv（gym==0.25.2）への混在は避けてください（docs/01_setup.md）。"
    )


class _GymnasiumEnvAdapter:
    """Gymnasium 5-tuple step を LIBERO 風 4-tuple + obs dict に揃える。"""

    def __init__(self, env: Any, *, task_name: str) -> None:
        self._env = env
        self.task_name = task_name
        self.action_space = getattr(env, "action_space", None)

    def reset(self, *, seed: int | None = None) -> dict[str, Any]:
        if seed is not None:
            obs, info = self._env.reset(seed=seed)
        else:
            obs, info = self._env.reset()
        return self._wrap_obs(obs, info)

    def step(self, action: Any) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        obs, reward, terminated, truncated, info = self._env.step(action)
        done = bool(terminated) or bool(truncated)
        info = dict(info or {})
        info["terminated"] = bool(terminated)
        info["truncated"] = bool(truncated)
        return self._wrap_obs(obs, info), float(reward), done, info

    def close(self) -> None:
        close = getattr(self._env, "close", None)
        if callable(close):
            close()

    def _wrap_obs(self, obs: Any, info: Mapping[str, Any] | None) -> dict[str, Any]:
        state = np.asarray(obs, dtype=np.float32).reshape(-1)
        out: dict[str, Any] = {
            "state": state,
            "observation": state,
            "task": self.task_name,
        }
        # Sawyer EE 位置は観測先頭 3 次元が通例
        if state.size >= 3:
            out["ee_pos"] = state[:3].astype(np.float64)
            out["robot0_eef_pos"] = out["ee_pos"]
        if info:
            out["info"] = dict(info)
        return out


@register_benchmark
class MetaworldMT50Backend(BenchmarkBackend):
    """Meta-World MT50（タスクごとに MT1 環境を生成）。"""

    name = "metaworld_mt50"

    @property
    def action_dim(self) -> int:
        return 4

    @property
    def obs_keys(self) -> tuple[str, ...]:
        return ("state", "ee_pos")

    def list_task_ids(self, eval_cfg: Mapping[str, Any]) -> list[int]:
        task_ids = eval_cfg.get("task_ids")
        if task_ids is not None:
            ids = [int(i) for i in task_ids]
            for i in ids:
                if i < 0 or i >= len(MT50_TASK_NAMES):
                    raise ValueError(
                        f"MT50 task_id は 0..{len(MT50_TASK_NAMES) - 1}: got {i}"
                    )
            return ids
        # 明示なしは全 50（重いので警告相当の ValueError）
        raise ValueError(
            "metaworld_mt50 では eval.task_ids を指定してください（例: [0, 1, 2]）。"
            " 全 50 タスクは明示的に task_ids: [0..49] を書いてください。"
        )

    def make_env(self, task_id: int, eval_cfg: Mapping[str, Any]) -> Any:
        _require_metaworld()
        import gymnasium as gym
        import metaworld  # noqa: F401  — Gymnasium へ環境登録

        name = MT50_TASK_NAMES[int(task_id)]
        seed = eval_cfg.get("_seed")
        kwargs: dict[str, Any] = {"env_name": name}
        if seed is not None:
            kwargs["seed"] = int(seed)
        env = gym.make("Meta-World/MT1", **kwargs)
        return _GymnasiumEnvAdapter(env, task_name=name)

    def reset_episode(
        self,
        env: Any,
        *,
        task_id: int,
        trial: int,
        seed: int,
        eval_cfg: Mapping[str, Any],
    ) -> dict[str, Any]:
        # trial ごとに異なる seed
        ep_seed = int(seed) + int(task_id) * 1009 + int(trial)
        return env.reset(seed=ep_seed)

    def success(
        self,
        obs: Mapping[str, Any],
        reward: float,
        done: bool,
        info: Mapping[str, Any] | None,
        env: Any,
    ) -> bool:
        info = info or {}
        if bool(info.get("success", False)):
            return True
        # 一部実装は success を float で返す
        try:
            if float(info.get("success", 0.0)) > 0.5:
                return True
        except (TypeError, ValueError):
            pass
        return False

    def task_name(self, task_id: int) -> str:
        return MT50_TASK_NAMES[int(task_id)]

    def task_language(self, task_id: int) -> str:
        # reach-v3 → "reach"
        raw = self.task_name(task_id)
        return raw.removesuffix("-v3").replace("-", " ")

    def category_for_task(self, task_id: int, eval_cfg: Mapping[str, Any]) -> str:
        return self.task_name(task_id)

    def dataset_spec(self) -> DatasetSpec:
        return DatasetSpec(
            backend=self.name,
            robot_type="sawyer",
            action_dim=4,
            fps=10,
            features={
                "observation.state": {"dtype": "float32", "shape": [39]},
                "action": {"dtype": "float32", "shape": [4]},
            },
            dataset_repo_id="local/metaworld_mt50_demos",
            notes=(
                "MT50 学習骨格: state 観測 + Sawyer 4-DoF。"
                " 画像・デモ変換は未実装（parc.data.benchmark_dataset）。"
            ),
        )
