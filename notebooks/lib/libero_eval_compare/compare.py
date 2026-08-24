"""Compare baseline and fine-tuned eval_info.json results."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from libero_eval_compare.config import CompareConfig


def load_eval_info(path: Path) -> dict[str, Any]:
    """Load one eval_info.json file."""
    return json.loads(path.read_text(encoding="utf-8"))


def per_task_success(eval_info: dict[str, Any]) -> dict[int, float]:
    """Convert per_task successes into task_id -> success rate (%)."""
    result: dict[int, float] = {}
    for task_info in eval_info["per_task"]:
        task_id = int(task_info["task_id"])
        successes = task_info["metrics"]["successes"]
        result[task_id] = 100.0 * sum(bool(value) for value in successes) / len(successes)
    return result


def overall_across_suites(results: dict[str, dict[str, Any]]) -> float:
    """Compute micro-averaged success rate across all rollouts."""
    total_success = 0.0
    total_rollouts = 0
    for info in results.values():
        for task in info["per_task"]:
            successes = task["metrics"]["successes"]
            total_success += sum(bool(value) for value in successes)
            total_rollouts += len(successes)
    return 100.0 * total_success / total_rollouts if total_rollouts else 0.0


def build_spatial_comparison(
    config: CompareConfig,
    baseline_eval: dict[str, dict[str, Any]],
    finetuned_eval: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """Build Section 8.6 compatible per-task comparison table."""
    spatial_info = baseline_eval["libero_spatial"]
    finetuned_spatial = finetuned_eval["libero_spatial"]
    base_per_task = per_task_success(spatial_info)
    finetuned_per_task = per_task_success(finetuned_spatial)

    rows: list[dict[str, Any]] = []
    task_ids = config.suites["libero_spatial"].task_ids
    for task_id in task_ids:
        base_score = base_per_task[task_id]
        finetuned_score = finetuned_per_task[task_id]
        task_name = (
            config.spatial_task_names[task_id]
            if task_id < len(config.spatial_task_names)
            else f"task_{task_id}"
        )
        rows.append(
            {
                "Task ID": task_id,
                "Task": task_name,
                f"{config.baseline.label} (%)": base_score,
                f"{config.finetuned.label} (%)": finetuned_score,
                "Δ (pp)": finetuned_score - base_score,
            }
        )

    base_overall = float(spatial_info["overall"]["pc_success"])
    finetuned_overall = float(finetuned_spatial["overall"]["pc_success"])
    rows.append(
        {
            "Task ID": "Overall",
            "Task": "LIBERO-Spatial",
            f"{config.baseline.label} (%)": base_overall,
            f"{config.finetuned.label} (%)": finetuned_overall,
            "Δ (pp)": finetuned_overall - base_overall,
        }
    )
    return pd.DataFrame(rows)


def build_advanced_comparison(
    config: CompareConfig,
    baseline_eval: dict[str, dict[str, Any]],
    finetuned_eval: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """Build Section 9 compatible per-suite comparison table."""
    rows: list[dict[str, Any]] = []
    for suite_name, suite_cfg in config.suites.items():
        base_score = float(baseline_eval[suite_name]["overall"]["pc_success"])
        finetuned_score = float(finetuned_eval[suite_name]["overall"]["pc_success"])
        rows.append(
            {
                "Suite": suite_name,
                "Tasks": len(suite_cfg.task_ids),
                f"{config.baseline.label} (%)": base_score,
                f"{config.finetuned.label} (%)": finetuned_score,
                "Δ (pp)": finetuned_score - base_score,
            }
        )

    base_overall = overall_across_suites(baseline_eval)
    finetuned_overall = overall_across_suites(finetuned_eval)
    total_tasks = sum(len(suite.task_ids) for suite in config.suites.values())
    rows.append(
        {
            "Suite": f"Overall ({total_tasks} rollouts)",
            "Tasks": total_tasks,
            f"{config.baseline.label} (%)": base_overall,
            f"{config.finetuned.label} (%)": finetuned_overall,
            "Δ (pp)": finetuned_overall - base_overall,
        }
    )
    return pd.DataFrame(rows)


def build_group_comparison(
    config: CompareConfig,
    baseline_eval: dict[str, dict[str, Any]],
    finetuned_eval: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """Dispatch to spatial or advanced table builder based on group profile."""
    if config.profile_name == "spatial":
        return build_spatial_comparison(config, baseline_eval, finetuned_eval)
    return build_advanced_comparison(config, baseline_eval, finetuned_eval)


def _git_revision(repo_root: Path) -> str | None:
    try:
        output = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return output.strip() or None


def save_comparison_results(
    config: CompareConfig,
    *,
    run_dir: Path,
    group_results: dict[str, dict[str, dict[str, Any]]],
    source: str,
) -> dict[str, Path]:
    """Write comparison CSVs and manifest.json for one run."""
    output_paths: dict[str, Path] = {}

    summary_rows: list[dict[str, Any]] = []
    for group_name, eval_results in group_results.items():
        group_config = config.group_config(group_name)
        comparison_df = build_group_comparison(
            group_config,
            eval_results["baseline"],
            eval_results["finetuned"],
        )
        csv_path = run_dir / f"{group_name}_comparison.csv"
        comparison_df.to_csv(csv_path, index=False)
        output_paths[f"{group_name}_csv"] = csv_path

        overall_row = comparison_df.iloc[-1]
        summary_rows.append(
            {
                "group": group_name,
                "baseline_pct": float(overall_row[f"{config.baseline.label} (%)"]),
                "finetuned_pct": float(overall_row[f"{config.finetuned.label} (%)"]),
                "delta_pp": float(overall_row["Δ (pp)"]),
            }
        )

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile": config.profile_name,
        "source": source,
        "seed": config.seed,
        "baseline_model": str(config.baseline.path),
        "finetuned_model": str(config.finetuned.path),
        "git_revision": _git_revision(config.repo_root),
        "groups": list(group_results.keys()),
        "summary": summary_rows,
        "config": {
            "profile_name": config.profile_name,
            "seed": config.seed,
            "baseline": {
                "path": str(config.baseline.path),
                "label": config.baseline.label,
            },
            "finetuned": {
                "path": str(config.finetuned.path),
                "label": config.finetuned.label,
            },
            "sub_profiles": config.sub_profiles,
        },
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    output_paths["manifest"] = manifest_path
    return output_paths
