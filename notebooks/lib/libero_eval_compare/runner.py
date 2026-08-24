"""lerobot-eval subprocess runner for baseline vs fine-tuned comparison."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections import deque
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from libero_eval_compare.config import CompareConfig

_REQUIRED_FILES = [
    "model.safetensors",
    "config.json",
    "policy_preprocessor.json",
    "policy_postprocessor.json",
]
_REQUIRED_GLOBS = [
    "policy_preprocessor*.safetensors",
    "policy_postprocessor*.safetensors",
]


def check_policy_dir(policy_dir: Path, label: str) -> None:
    """Verify a policy directory satisfies lerobot-eval loading requirements."""
    if not policy_dir.is_dir():
        raise FileNotFoundError(
            f"{label}: directory not found at {policy_dir}. "
            "Run Advanced notebook Section 8.3/8.4 first."
        )

    missing: list[str] = []
    for name in _REQUIRED_FILES:
        if not (policy_dir / name).is_file():
            missing.append(name)
    for pattern in _REQUIRED_GLOBS:
        if not list(policy_dir.glob(pattern)):
            missing.append(pattern)

    if missing:
        raise FileNotFoundError(
            f"{label}: missing required files {missing}. "
            "Ensure SmolVLAPolicy.save_pretrained was used."
        )


def preflight_models(config: CompareConfig) -> None:
    """Validate baseline and fine-tuned policy directories."""
    check_policy_dir(config.baseline.path, config.baseline.label)
    check_policy_dir(config.finetuned.path, config.finetuned.label)


def build_eval_env(config: CompareConfig) -> dict[str, str]:
    """Build subprocess environment for lerobot-eval."""
    env = os.environ.copy()
    env["MUJOCO_GL"] = "egl"
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(config.libero_plus_dir),
            str(config.lerobot_src),
            env.get("PYTHONPATH", ""),
        ]
    )
    env["LEROBOT_MAX_RECORDED"] = "0"
    env["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    env["HF_DATASETS_DISABLE_PROGRESS_BARS"] = "1"
    env["HF_HUB_VERBOSITY"] = "error"
    env["TQDM_DISABLE"] = "1"
    env["PYTHONWARNINGS"] = "ignore"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def build_eval_command(
    config: CompareConfig,
    *,
    policy_path: Path,
    suite_name: str,
    task_ids: list[int],
    n_episodes: int,
    output_dir: Path,
) -> list[str]:
    """Build lerobot-eval CLI arguments shared by baseline and fine-tuned runs."""
    return [
        "lerobot-eval",
        f"--policy.path={policy_path}",
        f"--policy.device={config.policy_device}",
        "--policy.use_amp=false",
        "--env.type=libero",
        "--env.is_libero_plus=true",
        f"--env.task={suite_name}",
        "--env.task_ids=" + json.dumps(task_ids, separators=(",", ":")),
        "--env.camera_name_mapping="
        + json.dumps(config.camera_mapping, separators=(",", ":")),
        f"--env.observation_height={config.observation_height}",
        f"--env.observation_width={config.observation_width}",
        f"--env.control_mode={config.control_mode}",
        "--env.max_parallel_tasks=1",
        "--eval.batch_size=1",
        f"--eval.n_episodes={n_episodes}",
        "--eval.use_async_envs=false",
        "--eval.recording=false",
        f"--seed={config.seed}",
        f"--output_dir={output_dir}",
    ]


def run_single_suite_eval(
    config: CompareConfig,
    *,
    policy_path: Path,
    suite_name: str,
    task_ids: list[int],
    n_episodes: int,
    output_dir: Path,
    label: str,
    show_progress: bool = True,
) -> dict[str, Any]:
    """Run lerobot-eval for one suite and return eval_info.json contents."""
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    process = subprocess.Popen(
        build_eval_command(
            config,
            policy_path=policy_path,
            suite_name=suite_name,
            task_ids=task_ids,
            n_episodes=n_episodes,
            output_dir=output_dir,
        ),
        cwd=config.lerobot_dir,
        env=build_eval_env(config),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    recent_lines: deque[str] = deque(maxlen=120)
    progress_pattern = re.compile(
        r"^EVAL_PROGRESS task=(\d+)/(\d+) episode=(\d+)/(\d+)$"
    )
    total_rollouts = len(task_ids) * n_episodes
    progress_bar = None

    if show_progress:
        from tqdm.auto import tqdm

        progress_bar = tqdm(
            total=total_rollouts,
            desc=f"{label} {suite_name}",
            unit="ep",
        )

    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.replace("\r", "").strip()
        if not line:
            continue
        recent_lines.append(line)
        match = progress_pattern.match(line)
        if match and progress_bar is not None:
            task_idx, _, ep_idx, _ = match.groups()
            progress_bar.update(1)
            progress_bar.set_postfix_str(f"task {task_idx} ep {ep_idx}")

    if progress_bar is not None:
        progress_bar.close()

    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError("\n".join(recent_lines))

    result_path = output_dir / "eval_info.json"
    if not result_path.is_file():
        raise FileNotFoundError(f"Missing eval output: {result_path}")

    return json.loads(result_path.read_text(encoding="utf-8"))


def run_model_eval(
    config: CompareConfig,
    *,
    policy_path: Path,
    output_root: Path,
    label: str,
    show_progress: bool = True,
) -> dict[str, dict[str, Any]]:
    """Evaluate one model across all suites in the profile."""
    shutil.rmtree(output_root, ignore_errors=True)
    suite_results: dict[str, dict[str, Any]] = {}

    for suite_name, suite_cfg in config.suites.items():
        sub_dir = output_root / suite_name
        suite_results[suite_name] = run_single_suite_eval(
            config,
            policy_path=policy_path,
            suite_name=suite_name,
            task_ids=suite_cfg.task_ids,
            n_episodes=suite_cfg.n_episodes,
            output_dir=sub_dir,
            label=label,
            show_progress=show_progress,
        )

    return suite_results


def run_profile_eval(
    config: CompareConfig,
    *,
    run_dir: Path | None = None,
    show_progress: bool = True,
    skip_preflight: bool = False,
) -> dict[str, Any]:
    """Run baseline and fine-tuned evaluation for one or more comparison groups."""
    if not skip_preflight:
        preflight_models(config)

    resolved_run_dir = run_dir or config.make_run_dir()
    resolved_run_dir.mkdir(parents=True, exist_ok=True)

    group_outputs: dict[str, dict[str, Any]] = {}
    for group_name in config.comparison_groups:
        group_config = config.group_config(group_name)
        group_dir = resolved_run_dir / group_name

        baseline_results = run_model_eval(
            group_config,
            policy_path=config.baseline.path,
            output_root=group_dir / "baseline",
            label=config.baseline.label,
            show_progress=show_progress,
        )
        finetuned_results = run_model_eval(
            group_config,
            policy_path=config.finetuned.path,
            output_root=group_dir / "finetuned",
            label=config.finetuned.label,
            show_progress=show_progress,
        )

        group_outputs[group_name] = {
            "baseline": baseline_results,
            "finetuned": finetuned_results,
        }

    return {
        "run_dir": resolved_run_dir,
        "groups": group_outputs,
    }


def load_existing_eval_results(
    baseline_eval_dir: Path,
    finetuned_eval_dir: Path,
    suites: Iterable[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Load previously saved eval_info.json files for compare-only mode."""
    baseline_results: dict[str, dict[str, Any]] = {}
    finetuned_results: dict[str, dict[str, Any]] = {}
    suite_names = list(suites)
    single_suite_flat = len(suite_names) == 1

    for suite_name in suite_names:
        baseline_path = baseline_eval_dir / suite_name / "eval_info.json"
        finetuned_path = finetuned_eval_dir / suite_name / "eval_info.json"

        if baseline_path.is_file():
            baseline_results[suite_name] = json.loads(
                baseline_path.read_text(encoding="utf-8")
            )
        elif single_suite_flat and (baseline_eval_dir / "eval_info.json").is_file():
            baseline_results[suite_name] = json.loads(
                (baseline_eval_dir / "eval_info.json").read_text(encoding="utf-8")
            )
        else:
            raise FileNotFoundError(f"Missing baseline eval_info for suite {suite_name}")

        if finetuned_path.is_file():
            finetuned_results[suite_name] = json.loads(
                finetuned_path.read_text(encoding="utf-8")
            )
        elif single_suite_flat and (finetuned_eval_dir / "eval_info.json").is_file():
            finetuned_results[suite_name] = json.loads(
                (finetuned_eval_dir / "eval_info.json").read_text(encoding="utf-8")
            )
        else:
            raise FileNotFoundError(f"Missing finetuned eval_info for suite {suite_name}")

    return baseline_results, finetuned_results
