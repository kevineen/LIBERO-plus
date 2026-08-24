"""Baseline vs fine-tuned SmolVLA evaluation and comparison for LIBERO-plus."""

from libero_eval_compare.compare import (
    build_advanced_comparison,
    build_spatial_comparison,
    load_eval_info,
    save_comparison_results,
)
from libero_eval_compare.config import CompareConfig, load_profile
from libero_eval_compare.runner import check_policy_dir, run_profile_eval

__all__ = [
    "CompareConfig",
    "build_advanced_comparison",
    "build_spatial_comparison",
    "check_policy_dir",
    "load_eval_info",
    "load_profile",
    "run_profile_eval",
    "save_comparison_results",
]
