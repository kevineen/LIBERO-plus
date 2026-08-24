"""CLI: enqueue, pause, resume, collect scores for notebooks experiments."""

from __future__ import annotations

import argparse
import json
import sys

from exp_orchestrator.collect import collect_all, print_ranking, print_status
from exp_orchestrator.expand import load_sweep
from exp_orchestrator.lifelong_jobs import (
    pause_lifelong_trial,
    run_lifelong_sweep,
    run_lifelong_trial,
)
from exp_orchestrator.expand import expand_lifelong_trials
from exp_orchestrator.parc_jobs import (
    enqueue_parc_sweep,
    pause_job,
    queue_status,
    requeue_job,
    resume_run,
    start_worker,
)


def cmd_enqueue(args: argparse.Namespace) -> int:
    sweep = load_sweep(args.sweep)
    kind = str(sweep.get("kind", "parc"))
    if kind == "parc":
        ids = enqueue_parc_sweep(args.sweep, notes=args.notes, notify=args.notify)
        print(json.dumps({"kind": "parc", "job_ids": ids}, ensure_ascii=False))
        return 0
    if kind == "lifelong":
        print(
            "Lifelong sweeps are sequential. Use: "
            "python -m exp_orchestrator lifelong-run --sweep "
            f"{args.sweep}"
        )
        return 0
    raise ValueError(f"unknown kind: {kind}")


def cmd_worker(args: argparse.Namespace) -> int:
    proc = start_worker(loop=not args.once, poll_sec=args.poll_sec)
    print(f"parc-worker pid={proc.pid}")
    if args.once:
        return proc.wait()
    print("Worker started. Stop with Ctrl+C or kill the pid.")
    return proc.wait()


def cmd_status(args: argparse.Namespace) -> int:
    if args.parc:
        data = queue_status(limit=args.limit)
        if isinstance(data, dict):
            print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        else:
            print(data)
        return 0
    print_status(sweep_id=args.sweep_id)
    return 0


def cmd_pause(args: argparse.Namespace) -> int:
    if args.lifelong:
        print(json.dumps(pause_lifelong_trial(args.id), indent=2, ensure_ascii=False))
        return 0
    print(pause_job(args.id))
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    if args.lifelong:
        sweep = load_sweep(args.sweep)
        trials = {t["trial_id"]: t for t in expand_lifelong_trials(sweep)}
        trial = trials.get(args.id)
        if trial is None:
            raise KeyError(f"trial {args.id} not in sweep {args.sweep}")
        print(json.dumps(run_lifelong_trial(trial, resume=True), indent=2, ensure_ascii=False, default=str))
        return 0
    print(resume_run(args.id, mode=args.mode))
    return 0


def cmd_requeue(args: argparse.Namespace) -> int:
    print(requeue_job(args.id))
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    counts = collect_all(sweep_id=args.sweep_id)
    print(json.dumps(counts, ensure_ascii=False))
    return 0


def cmd_ranking(args: argparse.Namespace) -> int:
    collect_all(sweep_id=args.sweep_id)
    print_ranking(sweep_id=args.sweep_id)
    return 0


def cmd_lifelong_run(args: argparse.Namespace) -> int:
    results = run_lifelong_sweep(args.sweep, resume_paused=not args.no_resume)
    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="exp_orchestrator",
        description="Sweep enqueue, pause/resume, and score collection for notebooks/experiments.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_enq = sub.add_parser("enqueue", help="Enqueue a parc sweep (or print lifelong hint)")
    p_enq.add_argument("--sweep", required=True)
    p_enq.add_argument("--notes", default="")
    p_enq.add_argument("--notify", action="store_true")
    p_enq.set_defaults(func=cmd_enqueue)

    p_w = sub.add_parser("worker", help="Start parc-worker")
    p_w.add_argument("--once", action="store_true")
    p_w.add_argument("--poll-sec", type=float, default=30.0)
    p_w.set_defaults(func=cmd_worker)

    p_st = sub.add_parser("status", help="Show SQLite trial status (or parc queue)")
    p_st.add_argument("--sweep-id", default=None)
    p_st.add_argument("--parc", action="store_true")
    p_st.add_argument("--limit", type=int, default=30)
    p_st.set_defaults(func=cmd_status)

    p_pause = sub.add_parser("pause", help="Pause parc job_id or lifelong trial_id")
    p_pause.add_argument("id")
    p_pause.add_argument("--lifelong", action="store_true")
    p_pause.set_defaults(func=cmd_pause)

    p_res = sub.add_parser("resume", help="Resume parc run_id or lifelong trial")
    p_res.add_argument("id")
    p_res.add_argument("--mode", default="auto", choices=["auto", "eval", "train"])
    p_res.add_argument("--lifelong", action="store_true")
    p_res.add_argument("--sweep", default="", help="required with --lifelong")
    p_res.set_defaults(func=cmd_resume)

    p_rq = sub.add_parser("requeue", help="Requeue a parc job")
    p_rq.add_argument("id")
    p_rq.set_defaults(func=cmd_requeue)

    p_col = sub.add_parser("collect", help="Ingest parc/lifelong scores into SQLite")
    p_col.add_argument("--sweep-id", default=None)
    p_col.set_defaults(func=cmd_collect)

    p_rank = sub.add_parser("ranking", help="Collect then print score ranking")
    p_rank.add_argument("--sweep-id", default=None)
    p_rank.set_defaults(func=cmd_ranking)

    p_ll = sub.add_parser("lifelong-run", help="Run lifelong sweep sequentially")
    p_ll.add_argument("--sweep", required=True)
    p_ll.add_argument("--no-resume", action="store_true")
    p_ll.set_defaults(func=cmd_lifelong_run)

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
