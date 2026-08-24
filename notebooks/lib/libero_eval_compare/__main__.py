"""CLI entry point for baseline vs fine-tuned evaluation comparison."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from libero_eval_compare.compare import (
    build_group_comparison,
    save_comparison_results,
)
from libero_eval_compare.config import CompareConfig, list_profiles, load_profile
from libero_eval_compare.runner import (
    load_existing_eval_results,
    preflight_models,
    run_profile_eval,
)


def _apply_overrides(
    config: CompareConfig,
    *,
    baseline: str | None,
    finetuned: str | None,
    seed: int | None,
    workdir: str | None,
) -> CompareConfig:
    if baseline:
        config.baseline.path = Path(baseline).resolve()
    if finetuned:
        config.finetuned.path = Path(finetuned).resolve()
    if seed is not None:
        config.seed = seed
    if workdir:
        config.workdir = Path(workdir).resolve()
    return config


def _print_tables(config: CompareConfig, group_results: dict[str, dict[str, dict[str, object]]]) -> None:
    for group_name, eval_results in group_results.items():
        group_config = config.group_config(group_name)
        comparison_df = build_group_comparison(
            group_config,
            eval_results["baseline"],
            eval_results["finetuned"],
        )
        print(f"\n=== {group_name} comparison ===")
        print(comparison_df.round(1).to_string(index=False))


def cmd_list_profiles(_: argparse.Namespace) -> int:
    profiles = list_profiles()
    print("Available profiles:")
    for profile in profiles:
        print(f"  - {profile}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = load_profile(args.profile)
    config = _apply_overrides(
        config,
        baseline=args.baseline,
        finetuned=args.finetuned,
        seed=args.seed,
        workdir=args.workdir,
    )

    if not args.skip_preflight:
        preflight_models(config)

    eval_output = run_profile_eval(
        config,
        run_dir=Path(args.run_dir).resolve() if args.run_dir else None,
        show_progress=not args.quiet,
        skip_preflight=args.skip_preflight,
    )
    run_dir = eval_output["run_dir"]
    group_results = eval_output["groups"]

    output_paths = save_comparison_results(
        config,
        run_dir=run_dir,
        group_results=group_results,
        source="run",
    )
    _print_tables(config, group_results)

    print(f"\nRun directory: {run_dir}")
    for name, path in output_paths.items():
        print(f"Saved {name}: {path}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    config = load_profile(args.profile)
    config = _apply_overrides(
        config,
        baseline=args.baseline,
        finetuned=args.finetuned,
        seed=args.seed,
        workdir=args.workdir,
    )

    run_dir = (
        Path(args.run_dir).resolve()
        if args.run_dir
        else config.workdir / "eval" / "compare_runs" / f"compare_only_{args.profile}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    group_results: dict[str, dict[str, dict[str, object]]] = {}
    for group_name in config.comparison_groups:
        group_config = config.group_config(group_name)

        if args.baseline_eval and args.finetuned_eval:
            baseline_root = Path(args.baseline_eval).resolve()
            finetuned_root = Path(args.finetuned_eval).resolve()
            if config.comparison_groups == [group_name]:
                baseline_results, finetuned_results = load_existing_eval_results(
                    baseline_root,
                    finetuned_root,
                    group_config.suites.keys(),
                )
            else:
                baseline_results, finetuned_results = load_existing_eval_results(
                    baseline_root / group_name if (baseline_root / group_name).exists() else baseline_root,
                    finetuned_root / group_name if (finetuned_root / group_name).exists() else finetuned_root,
                    group_config.suites.keys(),
                )
        elif args.skip_run:
            group_dir = run_dir / group_name
            baseline_results, finetuned_results = load_existing_eval_results(
                group_dir / "baseline",
                group_dir / "finetuned",
                group_config.suites.keys(),
            )
        else:
            raise ValueError(
                "compare mode requires --baseline-eval and --finetuned-eval, "
                "or an existing run directory via --run-dir."
            )

        group_results[group_name] = {
            "baseline": baseline_results,
            "finetuned": finetuned_results,
        }

    output_paths = save_comparison_results(
        config,
        run_dir=run_dir,
        group_results=group_results,
        source="compare_only",
    )
    _print_tables(config, group_results)

    print(f"\nRun directory: {run_dir}")
    for name, path in output_paths.items():
        print(f"Saved {name}: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="libero_eval_compare",
        description="Compare baseline and fine-tuned SmolVLA models on LIBERO-plus.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-profiles", help="List available YAML profiles")
    list_parser.set_defaults(func=cmd_list_profiles)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--profile", default="spatial", help="Profile name (default: spatial)")
    common.add_argument("--baseline", help="Override baseline model directory")
    common.add_argument("--finetuned", help="Override fine-tuned model directory")
    common.add_argument("--seed", type=int, help="Override evaluation seed")
    common.add_argument("--workdir", help="Override workdir root")
    common.add_argument("--run-dir", help="Explicit output directory for this run")
    common.add_argument("--quiet", action="store_true", help="Disable tqdm progress bars")

    run_parser = subparsers.add_parser("run", parents=[common], help="Run eval and compare")
    run_parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip policy directory validation",
    )
    run_parser.set_defaults(func=cmd_run)

    compare_parser = subparsers.add_parser(
        "compare",
        parents=[common],
        help="Compare existing eval_info.json outputs without rerunning eval",
    )
    compare_parser.add_argument(
        "--baseline-eval",
        help="Existing baseline eval output directory",
    )
    compare_parser.add_argument(
        "--finetuned-eval",
        help="Existing fine-tuned eval output directory",
    )
    compare_parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Load eval results from --run-dir/<group>/{baseline,finetuned}",
    )
    compare_parser.set_defaults(func=cmd_compare)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
