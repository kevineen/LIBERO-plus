"""CLI エントリポイント。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from parc.config import load_yaml
from parc.paths import PARC_ROOT, apply_runtime_env, get_machine_id, get_paths
from parc.tracking.run import create_run, list_registry, update_run_meta

console = Console()


def _add_config_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--config",
        "-c",
        required=True,
        help="実験 YAML（例: configs/experiments/smoke_random.yaml）",
    )
    p.add_argument("--notes", default="", help="実験メモ")


def new_experiment(argv: list[str] | None = None) -> None:
    """実験ディレクトリだけ作る。"""
    parser = argparse.ArgumentParser(prog="parc-new")
    _add_config_arg(parser)
    args = parser.parse_args(argv)
    apply_runtime_env()
    cfg = load_yaml(args.config)
    run_dir, meta = create_run(cfg, notes=args.notes)
    console.print(f"[green]created[/green] {run_dir}")
    console.print(meta)


def eval_main(argv: list[str] | None = None) -> None:
    """評価を実行する。"""
    parser = argparse.ArgumentParser(prog="parc-eval")
    _add_config_arg(parser)
    parser.add_argument(
        "--run-dir",
        default=None,
        help="既存 run ディレクトリ。省略時は新規作成",
    )
    parser.add_argument(
        "--eval-config",
        default=None,
        help="既存 run 評価時に eval/policy を上書きする YAML",
    )
    args = parser.parse_args(argv)
    apply_runtime_env()

    if args.run_dir:
        run_dir = Path(args.run_dir)
        cfg = load_yaml(run_dir / "config.yaml")
        if args.eval_config:
            from parc.config import deep_update

            overlay = load_yaml(args.eval_config)
            if overlay.get("eval"):
                cfg["eval"] = deep_update(dict(cfg.get("eval") or {}), overlay["eval"])
            if overlay.get("policy"):
                cfg["policy"] = deep_update(dict(cfg.get("policy") or {}), overlay["policy"])
    else:
        cfg = load_yaml(args.config)
        run_dir, _ = create_run(cfg, notes=args.notes)

    update_run_meta(run_dir, status="running")
    try:
        from parc.eval.runner import evaluate

        metrics = evaluate(cfg, run_dir=run_dir)
        update_run_meta(run_dir, status="finished", metrics={
            "success_rate": metrics.get("success_rate"),
            "n_episodes": metrics.get("n_episodes"),
            "by_category": metrics.get("by_category"),
        })
        console.print_json(json.dumps({
            "run_dir": str(run_dir),
            "success_rate": metrics.get("success_rate"),
            "n_episodes": metrics.get("n_episodes"),
            "by_category": metrics.get("by_category"),
        }, ensure_ascii=False))
    except Exception as e:
        update_run_meta(run_dir, status="failed", notes=str(e))
        console.print(f"[red]eval failed[/red]: {e}")
        raise


def train_main(argv: list[str] | None = None) -> None:
    """学習（または dry-run でコマンド生成）。"""
    parser = argparse.ArgumentParser(prog="parc-train")
    _add_config_arg(parser)
    args = parser.parse_args(argv)
    apply_runtime_env()
    cfg = load_yaml(args.config)
    run_dir, _ = create_run(cfg, notes=args.notes)
    update_run_meta(run_dir, status="running")
    # ワーカーが学習中に run_id を紐づけるための早期通知（flush 必須）
    print(
        json.dumps({"event": "run_created", "run_dir": str(run_dir)}, ensure_ascii=False),
        flush=True,
    )
    try:
        from parc.train.lerobot_train import run_training

        result = run_training(cfg, run_dir)
        (run_dir / "logs" / "train_result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False)
        )
        status = "finished" if result.get("status") in {"dry_run", "finished"} else "failed"
        update_run_meta(run_dir, status=status, metrics=result)
        console.print_json(json.dumps({"run_dir": str(run_dir), **result}, ensure_ascii=False))
        if status == "failed":
            rc = int(result.get("returncode") or 1)
            raise SystemExit(rc if rc != 0 else 1)
    except Exception as e:
        update_run_meta(run_dir, status="failed", notes=str(e))
        console.print(f"[red]train failed[/red]: {e}")
        raise


def list_runs(argv: list[str] | None = None) -> None:
    """実験一覧 / 削除。

    例:
      parc-list --json
      parc-list delete --failed
      parc-list delete <run_id>
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "delete":
        _list_delete_runs(argv[1:])
        return

    parser = argparse.ArgumentParser(prog="parc-list")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--sweep-id", default=None, help="スイープ ID でフィルタ")
    parser.add_argument(
        "--json",
        action="store_true",
        help="機械可読 JSON 配列（Fleet / Web 用）",
    )
    args = parser.parse_args(argv)
    apply_runtime_env()
    rows = list_registry(limit=args.limit, sweep_id=args.sweep_id)
    if args.json:
        # Fleet aggregate は JSON 配列を期待する（object ラッパにしない）
        payload = []
        for r in rows:
            sr = None
            if r.metrics and "success_rate" in r.metrics:
                try:
                    sr = float(r.metrics["success_rate"])
                except (TypeError, ValueError):
                    sr = r.metrics["success_rate"]
            payload.append(
                {
                    "run_id": r.run_id,
                    "machine_id": r.machine_id or "",
                    "name": r.name,
                    "status": r.status,
                    "success_rate": sr,
                    "tags": list(r.tags or []),
                    "sweep_id": r.sweep_id or "",
                    "created_at": r.created_at,
                    "notes": r.notes or "",
                    "metrics": r.metrics or {},
                }
            )
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return
    table = Table(title=f"PARC runs ({get_paths()['experiments_dir']})")
    table.add_column("run_id")
    table.add_column("machine")
    table.add_column("name")
    table.add_column("status")
    table.add_column("success_rate")
    table.add_column("sweep")
    table.add_column("tags")
    for r in rows:
        sr = ""
        if r.metrics and "success_rate" in r.metrics:
            try:
                sr = f"{float(r.metrics['success_rate']):.3f}"
            except (TypeError, ValueError):
                sr = str(r.metrics["success_rate"])
        table.add_row(
            r.run_id,
            r.machine_id or "",
            r.name,
            r.status,
            sr,
            r.sweep_id or "",
            ",".join(r.tags),
        )
    console.print(table)


def _list_delete_runs(argv: list[str]) -> None:
    """failed などの実験ディレクトリを削除する。"""
    parser = argparse.ArgumentParser(prog="parc-list delete")
    parser.add_argument("run_ids", nargs="*", help="削除する run_id（プレフィックス可）")
    parser.add_argument("--failed", action="store_true", help="status=failed をすべて削除")
    parser.add_argument(
        "--paused",
        action="store_true",
        help="status=paused をすべて削除（Pause 後に Resume 済みの残骸向け）",
    )
    parser.add_argument(
        "--created",
        action="store_true",
        help="status=created をすべて削除",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    apply_runtime_env()

    from parc.tracking.run import delete_runs

    statuses: list[str] = []
    if args.failed:
        statuses.append("failed")
    if args.paused:
        statuses.append("paused")
    if args.created:
        statuses.append("created")
    if not args.run_ids and not statuses:
        console.print(
            "[red]run_id か --failed / --paused / --created を指定してください[/red]"
        )
        raise SystemExit(2)
    try:
        result = delete_runs(
            run_ids=list(args.run_ids) or None,
            statuses=statuses or None,
            dry_run=args.dry_run,
        )
    except (KeyError, ValueError) as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1) from e
    console.print_json(json.dumps(result, ensure_ascii=False))


def smoke_main(argv: list[str] | None = None) -> None:
    """セットアップ確認 + 超短縮評価。"""
    parser = argparse.ArgumentParser(prog="parc-smoke")
    parser.add_argument(
        "--skip-env",
        action="store_true",
        help="シミュレータ評価をスキップ（パス確認のみ）",
    )
    args = parser.parse_args(argv)
    apply_runtime_env()
    paths = get_paths()
    console.print("[bold]PARC smoke check[/bold]")
    console.print(f"parc_root: {paths['parc_root']}")
    console.print(f"libero_plus_root: {paths['libero_plus_root']}")
    console.print(f"experiments_dir: {paths['experiments_dir']}")
    console.print(f"classification: {paths['classification_json'].exists()}")

    assets = paths["libero_plus_root"] / "libero" / "libero" / "assets"
    console.print(f"assets dir: {assets} exists={assets.exists()}")

    try:
        import libero  # noqa: F401

        console.print("[green]import libero: OK[/green]")
    except Exception as e:
        console.print(f"[yellow]import libero: FAIL[/yellow] ({e})")
        console.print("→ docs/01_setup.md のパス設定と assets 配置を確認")

    if args.skip_env:
        return

    cfg_path = PARC_ROOT / "configs" / "experiments" / "smoke_random.yaml"
    console.print(f"running eval with {cfg_path}")
    eval_main(["--config", str(cfg_path), "--notes", "smoke"])


def enqueue_main(argv: list[str] | None = None) -> None:
    """ジョブまたはスイープをキューへ投入する。"""
    parser = argparse.ArgumentParser(prog="parc-enqueue")
    parser.add_argument("--config", "-c", default=None, help="単発実験 YAML")
    parser.add_argument("--sweep", "-s", default=None, help="スイープ YAML")
    parser.add_argument(
        "--kind",
        default="train_eval",
        choices=["train_eval", "train", "eval", "prune"],
    )
    parser.add_argument("--eval-config", default="", help="train_eval 用 eval テンプレ")
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--notify",
        action="store_true",
        help="完了/失敗時に Slack/Discord webhook へ通知（PARC_NOTIFY_WEBHOOK_URL）",
    )
    args = parser.parse_args(argv)
    apply_runtime_env()

    if args.sweep:
        from parc.sweep import enqueue_sweep

        ids = enqueue_sweep(args.sweep, notes=args.notes, notify=args.notify)
        console.print(f"[green]enqueued {len(ids)} jobs[/green] from {args.sweep}")
        for jid in ids:
            console.print(f"  {jid}")
        return

    if args.kind == "prune":
        from parc.queue.store import enqueue

        job = enqueue(
            kind="prune",
            notes=args.notes or "manual prune",
            params={"notify": True} if args.notify else {},
        )
        console.print_json(json.dumps({"job_id": job.job_id, "kind": job.kind}, ensure_ascii=False))
        return

    if not args.config:
        parser.error("--config or --sweep required")

    from parc.queue.store import enqueue

    cfg = load_yaml(args.config)
    params: dict = {"notify": True} if args.notify else {}
    job = enqueue(
        kind=args.kind,
        config=cfg,
        config_path=str(args.config),
        eval_config_path=args.eval_config,
        sweep_id=str(cfg.get("sweep_id") or ""),
        trial_index=cfg.get("trial_index"),
        notes=args.notes,
        params=params,
    )
    console.print_json(
        json.dumps(
            {"job_id": job.job_id, "kind": job.kind, "status": job.status, "notify": bool(args.notify)},
            ensure_ascii=False,
        )
    )


def worker_main(argv: list[str] | None = None) -> None:
    """キューワーカー。"""
    parser = argparse.ArgumentParser(prog="parc-worker")
    parser.add_argument("--loop", action="store_true", help="常駐（デフォルトは 1 件）")
    parser.add_argument("--once", action="store_true", help="1 件だけ（既定）")
    parser.add_argument("--poll-sec", type=float, default=30.0)
    parser.add_argument("--max-failures", type=int, default=3)
    parser.add_argument("--stale-after-sec", type=float, default=3600.0)
    parser.add_argument("--no-recover-stale", action="store_true")
    args = parser.parse_args(argv)
    apply_runtime_env()
    from parc.queue.worker import run_worker_loop, run_worker_once

    if args.loop and not args.once:
        console.print(f"[bold]parc-worker[/bold] loop poll={args.poll_sec}s")
        run_worker_loop(
            poll_sec=args.poll_sec,
            max_failures=args.max_failures,
            once=False,
            stale_after_sec=args.stale_after_sec,
            recover_stale_on_start=not args.no_recover_stale,
        )
    else:
        job = run_worker_once()
        if job is None:
            console.print("queue empty")
        else:
            console.print(f"processed {job.job_id} → check queue status")


def queue_main(argv: list[str] | None = None) -> None:
    """キュー運用（status / requeue / recover-stale / resume / cancel / delete）。"""
    parser = argparse.ArgumentParser(prog="parc-queue")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="進捗・スコア付き一覧")
    p_status.add_argument("--limit", type=int, default=30)
    p_status.add_argument("--stale-after-sec", type=float, default=3600.0)
    p_status.add_argument("--json", action="store_true")

    p_requeue = sub.add_parser("requeue", help="ジョブを再投入")
    p_requeue.add_argument("job_id")
    p_requeue.add_argument("--no-resume-run", action="store_true")

    p_recover = sub.add_parser("recover-stale", help="放置された running を回収")
    p_recover.add_argument("--max-age-sec", type=float, default=3600.0)
    p_recover.add_argument(
        "--action",
        choices=["requeue", "fail"],
        default="requeue",
    )

    p_resume = sub.add_parser("resume", help="既存 run から続きを投入")
    p_resume.add_argument("run_id")
    p_resume.add_argument(
        "--mode",
        choices=["auto", "eval", "train"],
        default="auto",
    )
    p_resume.add_argument("--notes", default="")

    p_cancel = sub.add_parser(
        "cancel",
        help="queued を取消 / running を Pause（プロセス kill・ckpt は残し Resume 可）",
    )
    p_cancel.add_argument("job_id")

    p_delete = sub.add_parser(
        "delete",
        help="failed / cancelled / done ジョブをキューから削除（run ディレクトリは残す）",
    )
    p_delete.add_argument(
        "job_ids",
        nargs="*",
        help="削除する job_id（プレフィックス可）。--failed 等と併用可",
    )
    p_delete.add_argument(
        "--failed",
        action="store_true",
        help="status=failed をすべて削除",
    )
    p_delete.add_argument(
        "--cancelled",
        action="store_true",
        help="status=cancelled をすべて削除",
    )
    p_delete.add_argument(
        "--done",
        action="store_true",
        help="status=done / succeeded をすべて削除",
    )
    p_delete.add_argument(
        "--keep-sidecars",
        action="store_true",
        help="queue 配下の .log / .json / progress を残す",
    )

    p_notify = sub.add_parser("notify-on", help="既存ジョブ完了時に webhook 通知を有効化")
    p_notify.add_argument("job_id", nargs="?", default=None)
    p_notify.add_argument(
        "--all-active",
        action="store_true",
        help="queued / running の全ジョブに通知を付ける",
    )
    p_notify.add_argument("--off", action="store_true", help="通知を無効化")

    p_notify_test = sub.add_parser("notify-test", help="webhook へテスト送信")
    p_notify_test.add_argument("--message", default="[PARC] notify-test OK")

    p_notify_send = sub.add_parser(
        "notify-send",
        help="既存ジョブのサマリを今すぐ送信（done/failed 向け・スコア含む）",
    )
    p_notify_send.add_argument("job_id")
    p_notify_send.add_argument(
        "--preview",
        action="store_true",
        help="送信せずメッセージだけ表示",
    )

    args = parser.parse_args(argv)
    apply_runtime_env()

    if args.cmd == "status":
        from parc.queue.ops import queue_status

        data = queue_status(limit=args.limit, stale_after_sec=args.stale_after_sec)
        if args.json:
            console.print_json(json.dumps(data, ensure_ascii=False, default=str))
            return
        console.print(f"counts: {data['counts']}")
        if data["stale_running"]:
            console.print(f"[yellow]stale running:[/yellow] {len(data['stale_running'])}")
        table = Table(title="queue")
        table.add_column("job_id")
        table.add_column("status")
        table.add_column("phase")
        table.add_column("progress")
        table.add_column("SR")
        table.add_column("run_id")
        for j in data["jobs"][: args.limit]:
            prog = j.get("progress") or {}
            phase = prog.get("phase", "")
            step = prog.get("step")
            total = prog.get("total_steps")
            pct = prog.get("percent")
            if step is not None and total is not None:
                progress = f"{step}/{total}"
                if pct is not None:
                    progress += f" {pct}%"
            elif pct is not None:
                progress = f"{pct}%"
            else:
                progress = ""
            sr = ""
            if j.get("metrics") and j["metrics"].get("success_rate") is not None:
                sr = f"{float(j['metrics']['success_rate']):.3f}"
            table.add_row(
                j["job_id"],
                j["status"] + (" *" if j.get("stale") else ""),
                str(phase),
                progress,
                sr,
                (j.get("run_id") or "")[:24],
            )
        console.print(table)
        return

    if args.cmd == "requeue":
        from parc.queue.ops import requeue_job

        job = requeue_job(args.job_id, resume_run=not args.no_resume_run)
        console.print_json(json.dumps({"job_id": job.job_id, "status": job.status}, ensure_ascii=False))
        return

    if args.cmd == "recover-stale":
        from parc.queue.ops import recover_stale

        rows = recover_stale(max_age_sec=args.max_age_sec, action=args.action)
        console.print_json(json.dumps({"recovered": rows}, ensure_ascii=False, default=str))
        return

    if args.cmd == "resume":
        from parc.queue.ops import resume_run

        job = resume_run(args.run_id, mode=args.mode, notes=args.notes)
        console.print_json(
            json.dumps(
                {"job_id": job.job_id, "kind": job.kind, "status": job.status, "notes": job.notes},
                ensure_ascii=False,
            )
        )
        return

    if args.cmd == "cancel":
        from parc.queue.ops import cancel_job

        job = cancel_job(args.job_id)
        console.print_json(
            json.dumps(
                {"job_id": job.job_id, "status": job.status, "error": job.error},
                ensure_ascii=False,
            )
        )
        return

    if args.cmd == "delete":
        from parc.queue.ops import delete_jobs

        statuses: list[str] = []
        if args.failed:
            statuses.append("failed")
        if args.cancelled:
            statuses.append("cancelled")
        if args.done:
            statuses.extend(["done", "succeeded"])
        if not args.job_ids and not statuses:
            console.print(
                "[red]job_id か --failed / --cancelled / --done を指定してください[/red]"
            )
            raise SystemExit(2)
        try:
            result = delete_jobs(
                job_ids=list(args.job_ids) or None,
                statuses=statuses or None,
                remove_sidecars=not args.keep_sidecars,
            )
        except (KeyError, ValueError) as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1) from e
        console.print_json(json.dumps(result, ensure_ascii=False))
        return

    if args.cmd == "notify-on":
        from parc.notify import arm_notify, arm_notify_active

        if args.all_active:
            rows = arm_notify_active(enabled=not args.off)
            console.print_json(json.dumps({"updated": rows}, ensure_ascii=False))
            return
        if not args.job_id:
            console.print("[red]job_id か --all-active が必要です[/red]")
            raise SystemExit(2)
        job = arm_notify(args.job_id, enabled=not args.off)
        console.print_json(
            json.dumps(
                {
                    "job_id": job.job_id,
                    "status": job.status,
                    "notify": bool((job.params or {}).get("notify")),
                },
                ensure_ascii=False,
            )
        )
        return

    if args.cmd == "notify-test":
        from parc.notify import notify_config, send_webhook

        cfg = notify_config()
        if not cfg.get("webhook_url"):
            console.print(
                "[red]webhook_url 未設定[/red]: export PARC_NOTIFY_WEBHOOK_URL=... "
                "または configs/paths.yaml の notify.webhook_url"
            )
            raise SystemExit(2)
        out = send_webhook(args.message)
        console.print_json(json.dumps(out, ensure_ascii=False))
        if not out.get("ok"):
            raise SystemExit(1)
        return

    if args.cmd == "notify-send":
        from parc.notify import format_job_message, notify_job_finished, resolve_job_id
        from parc.queue.store import list_jobs

        jid = resolve_job_id(args.job_id)
        jobs = {j.job_id: j for j in list_jobs(limit=2000)}
        job = jobs[jid]
        if args.preview:
            console.print(format_job_message(job))
            return
        out = notify_job_finished(job, force=True)
        console.print_json(json.dumps(out, ensure_ascii=False))
        if not out.get("ok"):
            raise SystemExit(1)
        return


def prune_main(argv: list[str] | None = None) -> None:
    """実験ディレクトリを予算内に刈り込む。"""
    parser = argparse.ArgumentParser(prog="parc-prune")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-bytes-gb", type=float, default=None)
    parser.add_argument("--keep-best", type=int, default=None)
    parser.add_argument("--keep-last", type=int, default=None)
    args = parser.parse_args(argv)
    apply_runtime_env()
    from parc.disk.budget import get_disk_budget
    from parc.disk.prune import prune_experiments

    override = {}
    if args.max_bytes_gb is not None:
        override["max_bytes_gb"] = args.max_bytes_gb
    if args.keep_best is not None:
        override["keep_best"] = args.keep_best
    if args.keep_last is not None:
        override["keep_last"] = args.keep_last
    budget = get_disk_budget(override or None)
    report = prune_experiments(budget, dry_run=args.dry_run)
    console.print_json(json.dumps(report, ensure_ascii=False, default=str))


def sync_main(argv: list[str] | None = None) -> None:
    """Google Drive（rclone）へ ckpt を同期する。"""
    parser = argparse.ArgumentParser(prog="parc-sync")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="sync 設定と rclone 有無を表示")
    p_upload = sub.add_parser("upload", help="run の最新 ckpt をアップロード")
    p_upload.add_argument("run_id")
    p_upload.add_argument("--force", action="store_true", help="best / min_sr チェックを無視")
    p_upload.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    apply_runtime_env()
    from parc.sync.gdrive import get_sync_config, rclone_available, upload_run_checkpoint

    if args.cmd == "status":
        cfg = get_sync_config()
        console.print_json(
            json.dumps(
                {
                    "config": cfg,
                    "rclone_available": rclone_available(),
                    "machine_id": __import__("parc.paths", fromlist=["get_machine_id"]).get_machine_id(),
                },
                ensure_ascii=False,
            )
        )
        return

    if args.cmd == "upload":
        out = upload_run_checkpoint(args.run_id, force=args.force, dry_run=args.dry_run)
        console.print_json(json.dumps(out, ensure_ascii=False, default=str))
        if not out.get("ok") and not out.get("skipped"):
            raise SystemExit(1)
        return


def fleet_main(argv: list[str] | None = None) -> None:
    """複数ホスト横断（hosts / runs / queue / enqueue）。"""
    parser = argparse.ArgumentParser(prog="parc-fleet")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_hosts = sub.add_parser("hosts", help="hosts.yaml + local の名簿と到達性")
    p_hosts.add_argument("--json", action="store_true", default=True)

    p_runs = sub.add_parser("runs", help="全ホストの runs を集約")
    p_runs.add_argument("--limit", type=int, default=50)
    p_runs.add_argument("--json", action="store_true", default=True)

    p_queue = sub.add_parser("queue", help="全ホストの queue を集約")
    p_queue.add_argument("--limit", type=int, default=40)
    p_queue.add_argument("--json", action="store_true", default=True)

    p_enq = sub.add_parser("enqueue", help="指定ホストへジョブ投入")
    p_enq.add_argument("--host", required=True, help="local / machine_id / hosts.yaml alias")
    p_enq.add_argument("--config", "-c", default=None)
    p_enq.add_argument("--sweep", "-s", default=None)
    p_enq.add_argument(
        "--kind",
        default="train_eval",
        choices=["train_eval", "train", "eval", "prune"],
    )
    p_enq.add_argument("--eval-config", default="")
    p_enq.add_argument("--notes", default="")
    p_enq.add_argument("--notify", action="store_true")

    args = parser.parse_args(argv)
    apply_runtime_env()
    from parc.fleet import enqueue_on_host, fleet_hosts, fleet_queue, fleet_runs

    if args.cmd == "hosts":
        console.print_json(json.dumps(fleet_hosts(), ensure_ascii=False, default=str))
        return
    if args.cmd == "runs":
        console.print_json(
            json.dumps(fleet_runs(limit=args.limit), ensure_ascii=False, default=str)
        )
        return
    if args.cmd == "queue":
        console.print_json(
            json.dumps(fleet_queue(limit=args.limit), ensure_ascii=False, default=str)
        )
        return
    if args.cmd == "enqueue":
        try:
            out = enqueue_on_host(
                args.host,
                kind=args.kind,
                config=args.config,
                sweep=args.sweep,
                eval_config=args.eval_config,
                notes=args.notes,
                notify=args.notify,
            )
        except (KeyError, ValueError) as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(2) from e
        console.print_json(json.dumps(out, ensure_ascii=False, default=str))
        if out.get("ok") is False:
            raise SystemExit(1)
        return


def remote_main(argv: list[str] | None = None) -> None:
    """他 PC の parc を SSH 経由で操作する。"""
    parser = argparse.ArgumentParser(
        prog="parc-remote",
        description="Usage: parc-remote <host> <parc-cli...>   e.g. parc-remote thor queue status",
    )
    parser.add_argument("--list-hosts", action="store_true")
    parser.add_argument(
        "--tunnel",
        action="store_true",
        help="Web UI トンネルコマンドを表示して終了（host 必須）",
    )
    parser.add_argument("host", nargs="?", default=None, help="configs/hosts.yaml のエイリアス")
    parser.add_argument(
        "remote_argv",
        nargs=argparse.REMAINDER,
        help="リモートで実行するコマンド（queue status / enqueue ...）",
    )
    args = parser.parse_args(argv)

    from parc.remote.hosts import list_host_summaries, remote_run, tunnel_hint

    if args.list_hosts:
        console.print_json(json.dumps(list_host_summaries(), ensure_ascii=False))
        return

    if not args.host:
        console.print("[red]host required[/red] (or --list-hosts)")
        raise SystemExit(2)

    remote_argv = list(args.remote_argv)
    if remote_argv and remote_argv[0] == "--":
        remote_argv = remote_argv[1:]

    # allow: parc-remote thor --tunnel   (REMAINDER に吸われるケース)
    want_tunnel = bool(args.tunnel) or (remote_argv == ["--tunnel"])
    if want_tunnel:
        console.print(tunnel_hint(args.host))
        return

    if not remote_argv:
        console.print("[red]remote command required[/red]: parc-remote thor queue status")
        raise SystemExit(2)

    # Convenience: bare "queue" / "enqueue" map to entry points
    head = remote_argv[0]
    if head in {
        "queue",
        "enqueue",
        "list",
        "worker",
        "prune",
        "sync",
        "fleet",
        "train",
        "eval",
        "smoke",
        "new",
    }:
        remote_argv = [f"parc-{head}", *remote_argv[1:]]
    elif not head.startswith("parc-"):
        remote_argv = ["parc-queue", *remote_argv]

    proc = remote_run(args.host, remote_argv, capture=False)
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print(
            "Usage: python -m parc.cli "
            "[new|eval|train|list|smoke|enqueue|worker|prune|queue|sync|remote|fleet]"
        )
        sys.exit(1)
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    {
        "new": new_experiment,
        "eval": eval_main,
        "train": train_main,
        "list": list_runs,
        "smoke": smoke_main,
        "enqueue": enqueue_main,
        "worker": worker_main,
        "prune": prune_main,
        "queue": queue_main,
        "sync": sync_main,
        "remote": remote_main,
        "fleet": fleet_main,
    }.get(cmd, lambda _: sys.exit(1))(rest)
