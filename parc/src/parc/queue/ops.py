"""キュー運用: stale 回収・再投入・run 再開・進捗読取。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from parc.config import load_yaml
from parc.paths import get_paths
from parc.queue.store import QueueJob, enqueue, list_jobs, queue_dir, update_job


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        # 2026-07-24T18:55:52.953920+00:00 or Z
        t = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(t)
    except ValueError:
        return None


def _age_sec(ts: str) -> float | None:
    dt = _parse_iso(ts)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()


def write_progress(job_id: str, **fields: Any) -> Path:
    """ワーカーが書く進捗スナップショット。"""
    path = queue_dir() / f"{job_id}.progress.json"
    payload = {
        "job_id": job_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def read_progress(job_id: str) -> dict[str, Any] | None:
    path = queue_dir() / f"{job_id}.progress.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _run_dir(run_id: str | None) -> Path | None:
    if not run_id:
        return None
    d = get_paths()["experiments_dir"] / run_id
    return d if d.is_dir() else None


def _latest_ckpt(run_dir: Path) -> Path | None:
    """train_output 配下の最新 pretrained_model を探す。"""
    direct = run_dir / "train_output" / "pretrained_model"
    if direct.is_dir():
        return direct
    alt = run_dir / "pretrained_model"
    if alt.is_dir():
        return alt
    ckpt_root = run_dir / "train_output" / "checkpoints"
    if not ckpt_root.is_dir():
        return None
    steps: list[tuple[int, Path]] = []
    for p in ckpt_root.iterdir():
        if p.is_dir() and (p / "pretrained_model").is_dir():
            try:
                steps.append((int(p.name), p / "pretrained_model"))
            except ValueError:
                steps.append((0, p / "pretrained_model"))
    if not steps:
        return None
    steps.sort(key=lambda x: x[0])
    return steps[-1][1]


def _rl_tail(run_dir: Path) -> dict[str, Any] | None:
    hist = run_dir / "logs" / "rl_history.jsonl"
    if not hist.is_file():
        return None
    last = ""
    with hist.open() as f:
        for line in f:
            if line.strip():
                last = line.strip()
    if not last:
        return None
    try:
        return json.loads(last)
    except json.JSONDecodeError:
        return None


def _metrics_summary(run_dir: Path) -> dict[str, Any] | None:
    mp = run_dir / "metrics.json"
    if not mp.is_file():
        return None
    try:
        m = json.loads(mp.read_text())
    except json.JSONDecodeError:
        return None
    return {
        "success_rate": m.get("success_rate"),
        "n_episodes": m.get("n_episodes"),
        "by_category": m.get("by_category"),
    }


def _parse_run_started(run_id: str | None) -> datetime | None:
    """run_id 先頭の UTC 時刻（YYYYMMDDTHHMMSSZ_...）を開始時刻として使う。"""
    if not run_id:
        return None
    head = run_id.split("_", 1)[0]
    if len(head) < 16 or not head.endswith("Z"):
        return None
    try:
        return datetime.strptime(head, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _train_total_from_run(run_dir: Path | None) -> int | None:
    if run_dir is None:
        return None
    for name in ("config.yaml", "config.source.yaml"):
        p = run_dir / name
        if not p.is_file():
            continue
        try:
            cfg = load_yaml(p)
        except Exception:
            continue
        train = cfg.get("train") if isinstance(cfg, dict) else None
        if not isinstance(train, dict):
            continue
        for key in ("steps", "updates"):
            v = train.get(key)
            if isinstance(v, int) and v > 0:
                return v
            if isinstance(v, float) and v > 0:
                return int(v)
    return None


def estimate_eta(
    *,
    step: int | None,
    total_steps: int | None,
    started_at: str | datetime | None,
    run_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """step/total と開始時刻から残り時間・終了時刻を推定する。"""
    if step is None or total_steps is None:
        return {}
    try:
        step_i = int(step)
        total_i = int(total_steps)
    except (TypeError, ValueError):
        return {}
    # 誤パース（例: 4/83）を除外。本学習は通常数千 step 以上
    if step_i <= 0 or total_i <= step_i:
        return {}
    if total_i < 500 and step_i < 100:
        return {}

    now_dt = now or datetime.now(timezone.utc)
    start_dt: datetime | None = None
    if isinstance(started_at, datetime):
        start_dt = started_at
    elif isinstance(started_at, str) and started_at:
        start_dt = _parse_iso(started_at)
    if start_dt is None:
        start_dt = _parse_run_started(run_id)
    if start_dt is None:
        return {}
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    elapsed = (now_dt - start_dt).total_seconds()
    if elapsed < 60:
        return {"started_at": start_dt.isoformat()}
    sec_per_step = elapsed / step_i
    remain = (total_i - step_i) * sec_per_step
    # 異常値ガード（1 step が 1 時間超、または残り 30 日超）
    if sec_per_step > 3600 or remain > 30 * 24 * 3600:
        return {"started_at": start_dt.isoformat(), "sec_per_step": round(sec_per_step, 3)}
    eta_at = now_dt.timestamp() + remain
    eta_dt = datetime.fromtimestamp(eta_at, tz=timezone.utc)
    return {
        "started_at": start_dt.isoformat(),
        "sec_per_step": round(sec_per_step, 3),
        "eta_sec": int(remain),
        "eta_at": eta_dt.isoformat(),
    }


def enrich_job(job: QueueJob) -> dict[str, Any]:
    """UI 向けに進捗・スコアを付けた dict。"""
    prog = dict(read_progress(job.job_id) or {})
    run = _run_dir(job.run_id or prog.get("run_id"))
    # total_steps がログ誤パースで小さいとき config を優先
    cfg_total = _train_total_from_run(run)
    try:
        prog_total = int(prog["total_steps"]) if prog.get("total_steps") is not None else None
    except (TypeError, ValueError):
        prog_total = None
    if cfg_total and (prog_total is None or prog_total < 1000 or (
        prog.get("step") is not None and int(prog["step"]) > prog_total
    )):
        prog["total_steps"] = cfg_total
        try:
            st = int(prog["step"]) if prog.get("step") is not None else None
        except (TypeError, ValueError):
            st = None
        if st is not None and cfg_total > 0:
            prog["percent"] = max(0, min(100, round(100.0 * st / cfg_total)))

    eta = estimate_eta(
        step=prog.get("step") if isinstance(prog.get("step"), (int, float)) else None,
        total_steps=prog.get("total_steps") if isinstance(prog.get("total_steps"), (int, float)) else None,
        started_at=prog.get("started_at"),
        run_id=prog.get("run_id") or job.run_id,
    )
    if eta:
        prog.update(eta)

    metrics = _metrics_summary(run) if run else None
    rl = _rl_tail(run) if run else None
    age = _age_sec(job.updated_at)
    stale = job.status == "running" and age is not None and age > 3600
    return {
        "job_id": job.job_id,
        "kind": job.kind,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "age_sec": age,
        "stale": stale,
        "run_id": job.run_id,
        "sweep_id": job.sweep_id,
        "trial_index": job.trial_index,
        "notes": job.notes,
        "error": job.error,
        "progress": prog,
        "rl_latest": rl,
        "metrics": metrics,
        "config_path": job.config_path,
        "eval_config_path": job.eval_config_path,
        "params": job.params,
    }


def queue_status(*, limit: int = 50, stale_after_sec: float = 3600) -> dict[str, Any]:
    """キュー全体の状況サマリ。"""
    jobs = list_jobs(limit=limit)
    enriched = []
    seen: set[str] = set()
    for j in jobs:
        if j.job_id in seen:
            continue
        seen.add(j.job_id)
        row = enrich_job(j)
        age = row.get("age_sec")
        row["stale"] = j.status == "running" and age is not None and age > stale_after_sec
        enriched.append(row)

    counts: dict[str, int] = {}
    for j in enriched:
        counts[j["status"]] = counts.get(j["status"], 0) + 1

    # スコア上位（metrics があるもの）
    scored = [
        {
            "run_id": e["run_id"],
            "job_id": e["job_id"],
            "success_rate": (e.get("metrics") or {}).get("success_rate"),
            "sweep_id": e.get("sweep_id"),
        }
        for e in enriched
        if e.get("metrics") and e["metrics"].get("success_rate") is not None
    ]
    scored.sort(key=lambda x: float(x["success_rate"]), reverse=True)

    return {
        "counts": counts,
        "stale_running": [e for e in enriched if e.get("stale")],
        "jobs": enriched,
        "top_scores": scored[:10],
        "stale_after_sec": stale_after_sec,
    }


def recover_stale(
    *,
    max_age_sec: float = 3600,
    action: str = "requeue",
) -> list[dict[str, Any]]:
    """長時間 running のジョブを fail または再キューする。"""
    results: list[dict[str, Any]] = []
    for job in list_jobs(limit=500):
        if job.status != "running":
            continue
        age = _age_sec(job.updated_at)
        if age is None or age < max_age_sec:
            continue
        if action == "fail":
            update_job(
                job.job_id,
                status="failed",
                error=f"stale running recovered (age={int(age)}s)",
            )
            results.append({"job_id": job.job_id, "action": "failed", "age_sec": age})
        else:
            # 同じ内容で新規 queued を作り、元は failed に
            update_job(
                job.job_id,
                status="failed",
                error=f"stale; requeued (age={int(age)}s)",
            )
            new_job = enqueue(
                kind=job.kind,
                config_path=job.config_path,
                eval_config_path=job.eval_config_path,
                sweep_id=job.sweep_id,
                trial_index=job.trial_index,
                notes=(job.notes or "") + " [requeue-stale]",
                params={
                    **(job.params or {}),
                    "parent_job_id": job.job_id,
                    "resume_run_id": job.run_id,
                },
                config=job.config,
            )
            results.append(
                {
                    "job_id": job.job_id,
                    "action": "requeued",
                    "new_job_id": new_job.job_id,
                    "age_sec": age,
                }
            )
    return results


def _resolve_job_id(job_id: str) -> str:
    jobs = {j.job_id: j for j in list_jobs(limit=2000)}
    if job_id in jobs:
        return job_id
    matches = [jid for jid in jobs if jid.startswith(job_id)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise KeyError(f"ambiguous job_id prefix {job_id!r}: {matches[:5]}")
    raise KeyError(f"unknown job_id: {job_id}")


def cancel_job(job_id: str, *, pause: bool = True) -> QueueJob:
    """queued / running ジョブを cancelled にする。

    running の場合は PID ファイルのプロセスツリーを kill し GPU を解放する。
    run ディレクトリと ckpt は残るので、UI の Resume で続きから再開できる。
    """
    from parc.queue.process import kill_job_process
    from parc.tracking.run import update_run_meta

    job_id = _resolve_job_id(job_id)
    job = next(j for j in list_jobs(limit=2000) if j.job_id == job_id)
    if job.status == "running":
        kill_info = kill_job_process(job_id)
        note = "paused by user (process stopped; use Resume to continue)" if pause else "cancelled by user"
        if not kill_info.get("killed") and kill_info.get("reason") not in {
            "not_alive",
            "gone",
            "no_pid_file",
        }:
            note = f"{note}; kill={kill_info}"
        updated = update_job(job_id, status="cancelled", error=note)
        if job.run_id:
            run = _run_dir(job.run_id)
            if run is not None:
                try:
                    update_run_meta(run, status="paused", notes=note)
                except Exception:
                    pass
        write_progress(job_id, phase="paused", run_id=job.run_id, kill=kill_info)
        return updated
    if job.status != "queued":
        raise ValueError(f"cannot cancel status={job.status} (only queued/running)")
    return update_job(job_id, status="cancelled", error="cancelled by user")


# 削除可能な終端ステータス（queued / running は cancel を使う）
_DELETABLE_STATUSES = frozenset({"failed", "cancelled", "done", "succeeded"})


def delete_jobs(
    *,
    job_ids: list[str] | None = None,
    statuses: list[str] | None = None,
    remove_sidecars: bool = True,
) -> dict[str, Any]:
    """終端ジョブをキュー一覧から削除する（run ディレクトリは残す）。

    job_ids と statuses のどちらか（または両方）を指定する。
    両方指定時は積集合（指定 ID かつ指定 status）。
    """
    from parc.queue.store import delete_jobs as store_delete_jobs

    if not job_ids and not statuses:
        raise ValueError("job_ids か statuses のどちらかが必要です")

    status_filter = {s.strip() for s in (statuses or []) if s.strip()}
    if status_filter - _DELETABLE_STATUSES:
        bad = sorted(status_filter - _DELETABLE_STATUSES)
        raise ValueError(f"cannot delete status={bad} (only {sorted(_DELETABLE_STATUSES)})")

    jobs = {j.job_id: j for j in list_jobs(limit=5000)}
    selected: list[str] = []

    if job_ids:
        for raw in job_ids:
            jid = _resolve_job_id(raw)
            job = jobs[jid]
            if job.status not in _DELETABLE_STATUSES:
                raise ValueError(
                    f"cannot delete {jid} status={job.status} "
                    f"(only {sorted(_DELETABLE_STATUSES)}; use cancel for queued/running)"
                )
            if status_filter and job.status not in status_filter:
                continue
            selected.append(jid)
    else:
        selected = [j.job_id for j in jobs.values() if j.status in status_filter]

    # 安定したユニーク順
    selected = list(dict.fromkeys(selected))
    deleted = store_delete_jobs(selected, remove_sidecars=remove_sidecars)
    return {
        "deleted": deleted,
        "count": len(deleted),
        "remove_sidecars": remove_sidecars,
    }


def requeue_job(job_id: str, *, resume_run: bool = True) -> QueueJob:
    """failed / cancelled / done を同じ設定で再投入。

    job_id は完全一致、または一意なプレフィックスでも可（status 表示の短縮対策）。
    """
    job_id = _resolve_job_id(job_id)
    jobs = {j.job_id: j for j in list_jobs(limit=2000)}
    job = jobs[job_id]
    if job.status == "queued":
        return job
    params = dict(job.params or {})
    params["parent_job_id"] = job.job_id
    if resume_run and job.run_id:
        params["resume_run_id"] = job.run_id
    return enqueue(
        kind=job.kind,
        config_path=job.config_path,
        eval_config_path=job.eval_config_path,
        sweep_id=job.sweep_id,
        trial_index=job.trial_index,
        notes=(job.notes or "") + " [requeue]",
        params=params,
        config=job.config,
    )


def resume_run(
    run_id: str,
    *,
    mode: str = "auto",
    notes: str = "",
) -> QueueJob:
    """既存 run の ckpt / config から続きのジョブを投入する。

    mode:
      - auto: metrics 無し + ckpt あり → eval、ckpt あり → RL/FT 再開、無し → train やり直し
      - eval: ckpt 評価のみ
      - train: ckpt を init にして学習から
    """
    run_dir = _run_dir(run_id)
    if run_dir is None:
        raise FileNotFoundError(f"run not found: {run_id}")

    cfg_path = run_dir / "config.yaml"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"no config.yaml in {run_id}")
    cfg = load_yaml(cfg_path)
    cfg.pop("_config_path", None)
    cfg["parent_run_id"] = run_id
    tags = list(cfg.get("tags") or [])
    tags.append("resume")
    cfg["tags"] = list(dict.fromkeys(tags))

    ckpt = _latest_ckpt(run_dir)
    metrics = _metrics_summary(run_dir)
    has_sr = metrics is not None and metrics.get("success_rate") is not None
    backend = str((cfg.get("train") or {}).get("backend", "lerobot"))

    resolved_mode = mode
    if mode == "auto":
        if ckpt is not None and not has_sr:
            resolved_mode = "eval"
        elif ckpt is not None:
            resolved_mode = "train"
        else:
            resolved_mode = "train"

    if resolved_mode == "eval":
        if ckpt is None:
            raise FileNotFoundError(f"no checkpoint to eval in {run_id}")
        # eval 専用ジョブ: config に policy を埋めて kind=eval
        policy = dict(cfg.get("policy") or {})
        if (ckpt / "grpo_policy.pt").is_file():
            policy["type"] = "grpo_gaussian"
        else:
            policy["type"] = "checkpoint"
        policy["path"] = str(ckpt)
        cfg["policy"] = policy
        cfg["name"] = f"{cfg.get('name', run_id)}_resume_eval"
        return enqueue(
            kind="eval",
            config=cfg,
            notes=notes or f"resume-eval:{run_id}",
            params={"resume_run_id": run_id, "resume_mode": "eval"},
        )

    # train / train_eval
    train = dict(cfg.get("train") or {})
    if ckpt is not None:
        if backend in {"grpo", "gspo"}:
            train["init_policy_path"] = str(ckpt)
        else:
            # LeRobot: pretrained からの継続を extra_args で試みる
            extra = list(train.get("extra_args") or [])
            # 既に path 指定が無ければ追加
            if not any("pretrained_path" in str(x) or "from_pretrained" in str(x) for x in extra):
                extra.append(f"--policy.pretrained_path={ckpt}")
            train["extra_args"] = extra
        train["dry_run"] = False
    cfg["train"] = train
    cfg["name"] = f"{cfg.get('name', run_id)}_resume_train"
    eval_template = ""
    # 同一 config 内の eval を使う
    return enqueue(
        kind="train_eval",
        config=cfg,
        eval_config_path=eval_template,
        notes=notes or f"resume-train:{run_id}",
        params={
            "resume_run_id": run_id,
            "resume_mode": "train",
            "init_ckpt": str(ckpt) if ckpt else None,
        },
    )
