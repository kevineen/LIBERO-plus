#!/usr/bin/env python3
"""PARC thin/hard smoke for Evo-1 via upstream WebSocket client (parent_ckpt_eligible=false).

Limits task ids so we do not run the full 300+ category suite.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Prefer LIBERO-plus source over site-packages classic libero.
PLUS_ROOT = Path("/home/kevin/Matsuo/robot/LIBERO-plus")
EVAL_ROOT = Path("/mnt/b/parc_sidecars/Evo-1/libero-plus-eval")
sys.path.insert(0, str(EVAL_ROOT))
sys.path.insert(0, str(PLUS_ROOT))

# Prefer LIBERO-plus checkout for task_classification / assets via ~/.libero config
os.environ.setdefault("MUJOCO_GL", "egl")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="language")
    parser.add_argument(
        "--task-ids",
        type=int,
        nargs="+",
        default=[984, 986, 988],
        help="0-based LIBERO-plus task ids",
    )
    parser.add_argument("--suite", default="libero_spatial")
    parser.add_argument("--num-episodes", type=int, default=1)
    parser.add_argument("--server-url", default="ws://127.0.0.1:9000")
    parser.add_argument("--horizon", type=int, default=15)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=280)
    args = parser.parse_args()

    from evo_libero_plus_clients.config import ClientConfig
    from evo_libero_plus_clients.runtime import EvaluationClient

    cfg = ClientConfig(
        category=args.category,
        horizon=args.horizon,
        server_url=args.server_url,
        task_suites=(args.suite,),
        max_steps_override=args.max_steps,
        output_dir=EVAL_ROOT / "logs" / "parc_thin",
        ckpt_template="parc_thin_{category}_h{horizon}_S{seed}",
        num_episodes=args.num_episodes,
        seed=args.seed,
        mujoco_gl=os.environ.get("MUJOCO_GL", "egl"),
    )

    client = EvaluationClient(cfg)
    wanted = list(args.task_ids)

    def _filter(_suite: str, json_path=None):
        return wanted

    client.filter_task_ids = _filter  # type: ignore[method-assign]

    # LIBERO-plus env_wrapper expects str bddl paths (PosixPath breaks `_view_` check).
    _orig_get_env = client.get_libero_env

    def _get_env(task, resolution=448):
        from pathlib import Path as _P
        from libero.libero import get_libero_path
        from libero.libero.envs import OffScreenRenderEnv

        task_bddl_file = str(
            _P(get_libero_path("bddl_files"))
            / task.problem_folder
            / task.bddl_file
        )
        env = OffScreenRenderEnv(
            bddl_file_name=task_bddl_file,
            camera_heights=resolution,
            camera_widths=resolution,
        )
        env.seed(cfg.seed)
        return env, task.language

    client.get_libero_env = _get_env  # type: ignore[method-assign]
    del _orig_get_env

    import asyncio

    asyncio.run(client.run_suite(args.suite, cfg.max_steps_for(args.suite)))


if __name__ == "__main__":
    main()
