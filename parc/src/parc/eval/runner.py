"""ベンチ非依存のローカル評価ランナー。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from tqdm import tqdm

from parc.benchmarks import get_benchmark
from parc.benchmarks.base import BenchmarkBackend
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
    backend: BenchmarkBackend,
    *,
    max_steps: int,
    task_language: str = "",
    capture_frames: bool = False,
    frame_stride: int = 5,
    initial_obs: dict[str, Any] | None = None,
) -> tuple[bool, int, list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    """1 エピソードを実行する。

    ``initial_obs`` が無ければ ``env.reset()`` のみ（後方互換・テスト用）。
    通常は ``backend.reset_episode`` の結果を渡す。

    Returns:
        success, steps, actions, ee_positions, frames(RGB list)
    """
    set_task = getattr(policy, "set_task", None)
    if callable(set_task) and task_language:
        set_task(task_language)

    policy.reset()
    if initial_obs is not None:
        obs = dict(initial_obs)
    else:
        reset_out = env.reset()
        obs = dict(reset_out) if isinstance(reset_out, dict) else {"state": reset_out}

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
        if task_language:
            obs = dict(obs)
            obs["task"] = task_language
        action = policy.act(obs)
        step_out = env.step(action.tolist() if hasattr(action, "tolist") else action)
        obs, reward, done, info = step_out
        obs = dict(obs) if isinstance(obs, dict) else {"state": obs}
        actions.append(np.asarray(action, dtype=np.float64))
        ee_positions.append(_ee_pos(obs))
        steps = t + 1
        _maybe_capture(obs, t + 1)
        if backend.success(obs, float(reward), bool(done), info, env):
            success = True
            break

    return success, steps, actions, ee_positions, frames


def _resolve_backend_name(eval_cfg: dict[str, Any]) -> str:
    """YAML の backend / suite からレジストリ名を決める。"""
    explicit = eval_cfg.get("backend")
    if explicit:
        return str(explicit).lower().strip()
    suite = str(eval_cfg.get("suite", "libero_spatial")).lower()
    if suite in {"mt50", "metaworld_mt50", "metaworld"}:
        return "metaworld_mt50"
    return "libero"


def evaluate(config: dict[str, Any], run_dir: Path | None = None) -> dict[str, Any]:
    """実験設定に従い評価し、metrics dict を返す。"""
    eval_cfg = dict(config.get("eval") or {})
    seed = int(config.get("seed", 0))
    eval_cfg["_seed"] = seed

    backend_name = _resolve_backend_name(eval_cfg)
    backend_cls = get_benchmark(backend_name)
    backend = backend_cls()

    suite = str(eval_cfg.get("suite", backend_name))
    num_trials = int(eval_cfg.get("num_trials_per_task", 1))
    max_steps = int(eval_cfg.get("max_steps", 280))

    selected = backend.list_task_ids(eval_cfg)

    policy_cfg = dict(config.get("policy") or {})
    # YAML 未指定時は backend の action_dim を使う
    if "action_dim" not in policy_cfg:
        policy_cfg["action_dim"] = backend.action_dim
    policy = build_policy(policy_cfg, seed=seed)

    save_video = bool(eval_cfg.get("save_video", False))
    save_frames = bool(eval_cfg.get("save_frames", False))
    frame_stride = int(eval_cfg.get("frame_stride", 5))
    max_save_frames = int(eval_cfg.get("max_save_frames", 60))
    capture = save_video or save_frames
    media_manifest: list[dict[str, Any]] = []

    episodes: list[EpisodeMetrics] = []
    pbar = tqdm(selected, desc=f"eval:{backend_name}:{suite}")
    for task_id in pbar:
        task_name = backend.task_name(task_id)
        language = backend.task_language(task_id)
        category = backend.category_for_task(task_id, eval_cfg)

        env = backend.make_env(task_id, eval_cfg)
        try:
            for trial in range(num_trials):
                initial_obs = backend.reset_episode(
                    env,
                    task_id=task_id,
                    trial=trial,
                    seed=seed,
                    eval_cfg=eval_cfg,
                )
                success, steps, actions, ee_positions, frames = run_episode(
                    env,
                    policy,
                    backend,
                    max_steps=max_steps,
                    task_language=language,
                    capture_frames=capture,
                    frame_stride=frame_stride,
                    initial_obs=initial_obs,
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
                            frame_stride=1,
                            max_frames=max_save_frames,
                        )
                    )
                ep = finalize_episode(
                    suite=suite,
                    task_id=task_id,
                    task_name=task_name,
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

    summary = aggregate(episodes)
    result = asdict(summary)
    result["backend"] = backend_name
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
