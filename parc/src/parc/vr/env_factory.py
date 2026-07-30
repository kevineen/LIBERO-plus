"""LIBERO タスク env の生成。"""

from __future__ import annotations

from typing import Any

from parc.env.make_env import make_offscreen_env
from parc.vr.session import EnvLike, FakeLiberoEnv


def make_teleop_env(
    suite: str,
    task_id: int,
    *,
    camera_height: int = 128,
    camera_width: int = 128,
    fake: bool = False,
) -> tuple[EnvLike, str]:
    """(env, language) を返す。fake=True ならダミー env。"""
    if fake:
        return FakeLiberoEnv(height=camera_height, width=camera_width), "fake vr teleop demo"

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
    # 初期状態をセットできるなら最初の init state を使う
    try:
        init_states = bench.get_task_init_states(task_id)
        if init_states is not None and len(init_states) > 0:
            env.reset()
            env.set_init_state(init_states[0])
    except Exception:
        env.reset()
    return env, language
