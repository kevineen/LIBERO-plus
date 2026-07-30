"""LIBERO タスク env の生成と init_state 多様化。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from parc.env.make_env import make_offscreen_env
from parc.vr.session import EnvLike, FakeLiberoEnv


@dataclass
class TeleopEnvBundle:
    """テレオプ用 env と初期状態リストをまとめた束。"""

    env: EnvLike
    language: str
    suite: str
    task_id: int
    init_states: list[Any] = field(default_factory=list)

    @property
    def n_init_states(self) -> int:
        """サイクル可能な init 数（無い場合は 1）。"""
        return max(1, len(self.init_states))

    def apply_init_state(self, index: int) -> Any:
        """index 番目の init_state を適用して観測を返す。"""
        if not self.init_states:
            return self.env.reset()
        i = int(index) % len(self.init_states)
        self.env.reset()
        set_fn = getattr(self.env, "set_init_state", None)
        if callable(set_fn):
            return set_fn(self.init_states[i])
        return self.env.reset()


def make_teleop_env(
    suite: str,
    task_id: int,
    *,
    camera_height: int = 128,
    camera_width: int = 128,
    fake: bool = False,
    n_fake_init_states: int = 3,
) -> TeleopEnvBundle:
    """テレオプ用 env 束を返す。fake=True ならダミー env。"""
    if fake:
        env = FakeLiberoEnv(
            height=camera_height,
            width=camera_width,
            n_init_states=n_fake_init_states,
            success_after=1,
        )
        return TeleopEnvBundle(
            env=env,
            language="fake vr teleop demo",
            suite=suite,
            task_id=task_id,
            init_states=list(range(n_fake_init_states)),
        )

    import torch
    from libero.libero import benchmark

    # LIBERO init_states 用（評価ランナーと同様）
    _orig_load = torch.load

    def _load_trusted(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("weights_only", False)
        return _orig_load(*args, **kwargs)

    torch.load = _load_trusted  # type: ignore[assignment]

    bench_cls = benchmark.get_benchmark(suite)
    bench = bench_cls()
    task = bench.get_task(task_id)
    bddl = bench.get_task_bddl_file_path(task_id)
    language = str(getattr(task, "language", "") or "") or f"{suite}:{task_id}"
    env = make_offscreen_env(
        bddl,
        camera_heights=camera_height,
        camera_widths=camera_width,
    )
    init_states: list[Any] = []
    try:
        raw = bench.get_task_init_states(task_id)
        if raw is not None and len(raw) > 0:
            init_states = list(raw)
    except Exception:
        init_states = []

    bundle = TeleopEnvBundle(
        env=env,
        language=language,
        suite=suite,
        task_id=task_id,
        init_states=init_states,
    )
    # 最初の init を適用
    bundle.apply_init_state(0)
    return bundle
