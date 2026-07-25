"""LIBERO-plus ローカル評価ランナー。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from tqdm import tqdm

from parc.env.make_env import (
    category_for_task,
    make_offscreen_env,
    select_task_ids,
)
from parc.env.metrics import EpisodeMetrics, aggregate, finalize_episode
from parc.eval.media import extract_rgb, save_episode_media
from parc.policies.base import Policy, build_policy


def _ee_pos(obs: dict[str, Any]) -> np.ndarray:
    """観測から EE 位置を取る（キー揺れに耐える）。"""
    for key in ("robot0_eef_pos", "ee_pos", "eef_pos"):
        if key in obs:
            return np.asarray(obs[key], dtype=np.float64).reshape(-1)
    return np.zeros(3, dtype=np.float64)


def run_episode(
    env: Any,
    policy: Policy,
    init_state: np.ndarray,
    *,
    max_steps: int,
    task_language: str = "",
    capture_frames: bool = False,
    frame_stride: int = 5,
) -> tuple[bool, int, list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    """1 エピソードを実行する。

    Returns:
        success, steps, actions, ee_positions, frames(RGB list)
    """
    # VLA 系は言語指示が必要
    set_task = getattr(policy, "set_task", None)
    if callable(set_task) and task_language:
        set_task(task_language)

    policy.reset()
    env.reset()
    obs = env.set_init_state(init_state)

    actions: list[np.ndarray] = []
    ee_positions: list[np.ndarray] = [_ee_pos(obs)]
    frames: list[np.ndarray] = []
    success = False
    steps = 0

    def _maybe_capture(current: dict[str, Any], t: int) -> None:
        if not capture_frames:
            return
        if t % max(1, frame_stride) != 0:
            return
        rgb = extract_rgb(current)
        if rgb is not None:
            frames.append(np.asarray(rgb).copy())

    _maybe_capture(obs, 0)

    for t in range(max_steps):
        # 観測に言語を載せておく（checkpoint 方策が読む）
        if task_language:
            obs = dict(obs)
            obs["task"] = task_language
        action = policy.act(obs)
        obs, reward, done, info = env.step(action.tolist())
        actions.append(np.asarray(action, dtype=np.float64))
        ee_positions.append(_ee_pos(obs))
        steps = t + 1
        _maybe_capture(obs, t + 1)
        # LIBERO は done / reward / info のいずれかで成功を示す実装差がある
        if bool(done) or float(reward) > 0.5 or bool(info.get("success", False)):
            success = True
            break
        # check_success がある場合
        check = getattr(env, "check_success", None)
        if callable(check) and bool(check()):
            success = True
            break

    return success, steps, actions, ee_positions, frames


def evaluate(config: dict[str, Any], run_dir: Path | None = None) -> dict[str, Any]:
    """実験設定に従い評価し、metrics dict を返す。"""
    import torch
    from libero.libero import benchmark

    # PyTorch>=2.6 は torch.load の weights_only 既定が True。
    # LIBERO 公式 init_states は信頼できるローカル .pruned_init なので False で読む。
    _orig_load = torch.load

    def _load_trusted(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("weights_only", False)
        return _orig_load(*args, **kwargs)

    torch.load = _load_trusted  # type: ignore[assignment]

    eval_cfg = config.get("eval") or {}
    suite = str(eval_cfg.get("suite", "libero_spatial"))
    num_trials = int(eval_cfg.get("num_trials_per_task", 1))
    max_steps = int(eval_cfg.get("max_steps", 280))
    cam_h = int(eval_cfg.get("camera_height", 128))
    cam_w = int(eval_cfg.get("camera_width", 128))
    seed = int(config.get("seed", 0))

    task_ids = eval_cfg.get("task_ids")
    tasks_per_category = eval_cfg.get("tasks_per_category")
    selected = select_task_ids(
        suite,
        task_ids=list(task_ids) if task_ids is not None else None,
        tasks_per_category=int(tasks_per_category)
        if tasks_per_category is not None
        else None,
    )

    policy = build_policy(config.get("policy") or {}, seed=seed)
    bench_cls = benchmark.get_benchmark(suite)
    bench = bench_cls()

    save_video = bool(eval_cfg.get("save_video", False))
    save_frames = bool(eval_cfg.get("save_frames", False))
    frame_stride = int(eval_cfg.get("frame_stride", 5))
    max_save_frames = int(eval_cfg.get("max_save_frames", 60))
    capture = save_video or save_frames
    media_manifest: list[dict[str, Any]] = []

    episodes: list[EpisodeMetrics] = []
    pbar = tqdm(selected, desc=f"eval:{suite}")
    try:
        for task_id in pbar:
            task = bench.get_task(task_id)
            bddl = bench.get_task_bddl_file_path(task_id)
            init_states = bench.get_task_init_states(task_id)
            category = (
                category_for_task(suite, task_id)
                if eval_cfg.get("use_classification", True)
                else "Unknown"
            )

            env = make_offscreen_env(bddl, camera_heights=cam_h, camera_widths=cam_w)
            try:
                for trial in range(num_trials):
                    init = init_states[trial % len(init_states)]
                    success, steps, actions, ee_positions, frames = run_episode(
                        env,
                        policy,
                        init,
                        max_steps=max_steps,
                        task_language=str(getattr(task, "language", "") or ""),
                        capture_frames=capture,
                        frame_stride=frame_stride,
                    )
                    if capture and run_dir is not None:
                        videos_dir = run_dir / "videos"
                        stem = f"task{task_id:04d}_trial{trial:02d}"
                        media_manifest.append(
                            save_episode_media(
                                videos_dir,
                                frames=frames,
                                stem=stem,
                                save_video=save_video,
                                save_frames=save_frames,
                                frame_stride=1,  # 既に stride 済み
                                max_frames=max_save_frames,
                            )
                        )
                    ep = finalize_episode(
                        suite=suite,
                        task_id=task_id,
                        task_name=task.name,
                        category=category,
                        trial=trial,
                        success=success,
                        steps=steps,
                        actions=actions,
                        ee_positions=ee_positions,
                    )
                    episodes.append(ep)
                    pbar.set_postfix(sr=f"{np.mean([e.success for e in episodes]):.2f}")
            finally:
                env.close()
    finally:
        torch.load = _orig_load  # type: ignore[assignment]

    summary = aggregate(episodes)
    result = asdict(summary)
    if media_manifest:
        result["media"] = media_manifest

    if run_dir is not None:
        out = run_dir / "metrics.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        (run_dir / "episodes.jsonl").write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in result["episodes"])
            + ("\n" if result["episodes"] else "")
        )
        if media_manifest:
            (run_dir / "videos" / "manifest.json").write_text(
                json.dumps(media_manifest, indent=2, ensure_ascii=False)
            )
    return result
