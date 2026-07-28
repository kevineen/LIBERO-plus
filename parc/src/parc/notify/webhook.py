"""ジョブ完了通知（Slack / Discord Incoming Webhook）。"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from parc.paths import _load_paths_yaml
from parc.queue.store import QueueJob


def notify_config() -> dict[str, Any]:
    """paths.yaml の notify と環境変数をマージした設定。"""
    cfg = dict((_load_paths_yaml().get("notify") or {}))
    # 環境変数が最優先（秘密は YAML に書かない運用を推奨）
    url = os.environ.get("PARC_NOTIFY_WEBHOOK_URL") or cfg.get("webhook_url") or ""
    cfg["webhook_url"] = str(url).strip()
    if "notify_all" not in cfg:
        cfg["notify_all"] = os.environ.get("PARC_NOTIFY_ALL", "").lower() in {
            "1",
            "true",
            "yes",
        }
    return cfg


def webhook_provider(url: str) -> str:
    """URL から送信先を推定する。"""
    u = url.lower()
    if "discord.com/api/webhooks" in u or "discordapp.com/api/webhooks" in u:
        return "discord"
    if "hooks.slack.com" in u:
        return "slack"
    return "generic"


def resolve_notify_machine(*, run_id: str | None = None) -> str:
    """通知に載せる実行マシン名。

    run_id 形式 ``{utc}_{machine}_{uuid8}_{name}`` があればそこを優先し、
    なければ ``PARC_MACHINE_ID`` / paths.yaml / hostname。
    """
    rid = (run_id or "").strip()
    if rid:
        parts = rid.split("_")
        # 例: 20260727T225455Z_winpc_cb66c529_smolvla_...
        if len(parts) >= 3 and "T" in parts[0] and parts[0].endswith("Z"):
            mid = parts[1].strip()
            if mid:
                return mid
    try:
        from parc.paths import get_machine_id

        mid = (get_machine_id() or "").strip()
        if mid:
            return mid
    except Exception:
        pass
    return "unknown"


def discord_username_for_machine(machine_id: str) -> str:
    """Discord webhook の表示名（username 上書き）。"""
    mid = (machine_id or "unknown").strip() or "unknown"
    # Discord username 上限 80。Webhook 既定名（例: thor）を上書きする。
    name = f"PARC · {mid}"
    return name[:80]


def should_notify(job: QueueJob) -> bool:
    """このジョブ完了時に通知するか。"""
    params = job.params or {}
    if params.get("notify") is True:
        return True
    if params.get("notify") is False:
        return False
    return bool(notify_config().get("notify_all"))


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # 2026-07-24T22:43:00.584625+00:00
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "n/a"
    sec = int(round(seconds))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def _load_run_metrics(run_id: str | None) -> dict[str, Any]:
    if not run_id:
        return {}
    exp = Path(str(_load_paths_yaml().get("experiments_dir") or ""))
    path = exp / run_id / "metrics.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _train_summary(job: QueueJob) -> list[str]:
    """学習ハイパーの一行サマリ。"""
    cfg = job.config or {}
    train = cfg.get("train") if isinstance(cfg, dict) else None
    if not isinstance(train, dict):
        return []
    bits: list[str] = []
    for key, label in (
        ("backend", "backend"),
        ("steps", "steps"),
        ("batch_size", "bs"),
        ("lr", "lr"),
        ("updates", "updates"),
        ("group_size", "G"),
    ):
        if train.get(key) is not None:
            bits.append(f"{label}={train.get(key)}")
    extra = train.get("extra_args")
    if isinstance(extra, list) and extra:
        # optimizer_lr を拾う（flat list または nested list）
        toks: list[str] = []
        for x in extra:
            if isinstance(x, str):
                toks.append(x)
            elif isinstance(x, list):
                toks.extend(str(y) for y in x)
        for tok in toks:
            if "optimizer_lr=" in tok:
                bits.append(f"lr={tok.split('=', 1)[-1]}")
                break
    name = cfg.get("name") if isinstance(cfg, dict) else None
    out: list[str] = []
    if name:
        out.append(f"config={name}")
    if bits:
        out.append("train: " + " ".join(bits))
    return out


def _category_lines(by_category: dict[str, Any], *, limit: int = 7) -> list[str]:
    """カテゴリ別 SR を並べる（弱い順）。"""
    rows: list[tuple[float, str, dict[str, Any]]] = []
    for name, stats in by_category.items():
        if not isinstance(stats, dict):
            continue
        try:
            sr = float(stats.get("success_rate", 0.0))
        except (TypeError, ValueError):
            sr = 0.0
        rows.append((sr, str(name), stats))
    rows.sort(key=lambda x: (x[0], x[1]))
    lines: list[str] = []
    for sr, name, stats in rows[:limit]:
        n = stats.get("n")
        mean_steps = stats.get("mean_steps")
        extra = []
        if n is not None:
            extra.append(f"n={int(n) if float(n).is_integer() else n}")
        if mean_steps is not None:
            try:
                extra.append(f"steps={float(mean_steps):.0f}")
            except (TypeError, ValueError):
                pass
        suffix = f" ({', '.join(extra)})" if extra else ""
        lines.append(f"  - {name}: {sr:.3f}{suffix}")
    if len(rows) > limit:
        lines.append(f"  … +{len(rows) - limit} categories")
    return lines


def collect_job_context(job: QueueJob, *, result: dict[str, Any] | None = None) -> dict[str, Any]:
    """通知用に progress / metrics / 所要時間を集約する。"""
    result = result or {}
    prog: dict[str, Any] = {}
    try:
        from parc.queue.ops import read_progress

        prog = read_progress(job.job_id) or {}
    except Exception:
        prog = {}

    metrics: dict[str, Any] = {}
    if isinstance(result.get("metrics"), dict):
        metrics.update(result["metrics"])
    if isinstance(prog.get("metrics"), dict):
        # progress を優先（worker が書き込んだ最終値）
        metrics = {**metrics, **prog["metrics"]}
    run_id = job.run_id or prog.get("run_id") or result.get("run_id")
    if not metrics.get("by_category") or metrics.get("success_rate") is None:
        run_metrics = _load_run_metrics(str(run_id) if run_id else None)
        for k in ("success_rate", "n_episodes", "by_category", "mean_steps"):
            if k not in metrics and k in run_metrics:
                metrics[k] = run_metrics[k]

    created = _parse_ts(job.created_at)
    updated = _parse_ts(job.updated_at) or datetime.now(timezone.utc)
    duration_sec = (updated - created).total_seconds() if created else None

    return {
        "phase": result.get("phase") or prog.get("phase") or job.status,
        "run_id": run_id,
        "metrics": metrics,
        "duration_sec": duration_sec,
        "progress": prog,
    }


def format_job_message(job: QueueJob, *, result: dict[str, Any] | None = None) -> str:
    """スコア・所要時間・カテゴリ内訳を含む完了メッセージ。"""
    ctx = collect_job_context(job, result=result)
    metrics = ctx["metrics"] if isinstance(ctx["metrics"], dict) else {}
    status = job.status
    phase = ctx["phase"]
    run_id = ctx["run_id"]
    machine = resolve_notify_machine(run_id=str(run_id) if run_id else None)

    lines = [
        f"[PARC] {status.upper()} · `{job.job_id}`",
        f"machine={machine}  kind={job.kind}  phase={phase}  elapsed={_fmt_duration(ctx.get('duration_sec'))}",
    ]
    lines.extend(_train_summary(job))
    if job.sweep_id:
        lines.append(f"sweep={job.sweep_id}  trial={job.trial_index}")
    if run_id:
        lines.append(f"run_id={run_id}")
    if job.notes:
        lines.append(f"notes={job.notes[:140]}")

    sr = metrics.get("success_rate")
    n_ep = metrics.get("n_episodes")
    mean_steps = metrics.get("mean_steps")
    score_bits: list[str] = []
    if sr is not None:
        try:
            score_bits.append(f"SR={float(sr):.3f}")
        except (TypeError, ValueError):
            score_bits.append(f"SR={sr}")
    if n_ep is not None:
        score_bits.append(f"episodes={n_ep}")
    if mean_steps is not None:
        try:
            score_bits.append(f"mean_steps={float(mean_steps):.1f}")
        except (TypeError, ValueError):
            pass
    if score_bits:
        lines.append("score: " + "  ".join(score_bits))

    by_cat = metrics.get("by_category")
    if isinstance(by_cat, dict) and by_cat:
        lines.append("by_category (asc SR):")
        lines.extend(_category_lines(by_cat))

    if job.error:
        lines.append(f"error={job.error[:240]}")

    exp = str(_load_paths_yaml().get("experiments_dir") or "").rstrip("/")
    if run_id and exp:
        lines.append(f"path={exp}/{run_id}")
    return "\n".join(lines)


def build_payload(
    text: str,
    *,
    provider: str,
    username: str | None = None,
) -> dict[str, Any]:
    """Slack / Discord / 汎用 webhook 用 JSON。"""
    if provider == "discord":
        # Discord は content 上限 2000。username で Webhook 既定名を上書きできる。
        payload: dict[str, Any] = {"content": text[:1900]}
        if username:
            payload["username"] = username[:80]
        return payload
    if provider == "slack":
        return {"text": text}
    # 両方入れておく（多くの Incoming Webhook はどちらかを見る）
    payload = {"text": text, "content": text[:1900]}
    if username:
        payload["username"] = username[:80]
    return payload


def send_webhook(
    text: str,
    *,
    webhook_url: str | None = None,
    timeout_sec: float = 10.0,
    username: str | None = None,
) -> dict[str, Any]:
    """Webhook へ POST。成功なら ok=True。"""
    url = (webhook_url or notify_config().get("webhook_url") or "").strip()
    if not url:
        return {"ok": False, "error": "webhook_url not set (PARC_NOTIFY_WEBHOOK_URL or paths.yaml notify.webhook_url)"}
    provider = webhook_provider(url)
    # Discord は username 未指定だと Webhook 作成時の名前（例: thor）のままになる
    uname = username
    if uname is None and provider == "discord":
        uname = discord_username_for_machine(resolve_notify_machine())
    payload = build_payload(text, provider=provider, username=uname)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "parc-notify/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {
                "ok": 200 <= getattr(resp, "status", 200) < 300,
                "provider": provider,
                "status": getattr(resp, "status", None),
                "body": body[:500],
                "username": uname,
            }
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        return {"ok": False, "provider": provider, "error": f"HTTP {e.code}", "body": detail}
    except Exception as e:  # noqa: BLE001 — 通知失敗でジョブを落とさない
        return {"ok": False, "provider": provider, "error": str(e)}


def notify_job_finished(
    job: QueueJob,
    *,
    result: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """ジョブ終端時の通知。should_notify が False ならスキップ（force で送信）。"""
    if job.status not in {"done", "failed", "cancelled"} and not force:
        return {"ok": False, "skipped": True, "reason": f"status={job.status}"}
    if not force and not should_notify(job):
        return {"ok": False, "skipped": True, "reason": "notify not enabled for job"}
    text = format_job_message(job, result=result)
    ctx = collect_job_context(job, result=result)
    machine = resolve_notify_machine(run_id=str(ctx.get("run_id") or "") or None)
    out = send_webhook(text, username=discord_username_for_machine(machine))
    out["job_id"] = job.job_id
    out["status"] = job.status
    out["machine"] = machine
    out["preview"] = text[:400]
    return out


def resolve_job_id(job_id: str) -> str:
    """完全一致または一意プレフィックスで job_id を解決する。"""
    from parc.queue.store import list_jobs

    jobs = {j.job_id: j for j in list_jobs(limit=2000)}
    if job_id in jobs:
        return job_id
    matches = [jid for jid in jobs if jid.startswith(job_id)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise KeyError(f"ambiguous job_id prefix {job_id!r}")
    raise KeyError(f"unknown job_id: {job_id}")


def arm_notify(job_id: str, *, enabled: bool = True) -> QueueJob:
    """既存ジョブに notify フラグを付ける / 外す。"""
    from parc.queue.store import list_jobs, update_job

    job_id = resolve_job_id(job_id)
    jobs = {j.job_id: j for j in list_jobs(limit=2000)}
    job = jobs[job_id]
    params = dict(job.params or {})
    params["notify"] = bool(enabled)
    return update_job(job_id, params=params)


def arm_notify_active(*, enabled: bool = True) -> list[dict[str, Any]]:
    """queued / running の全ジョブに notify を付ける。"""
    from parc.queue.store import list_jobs, update_job

    out: list[dict[str, Any]] = []
    for job in list_jobs(limit=2000):
        if job.status not in {"queued", "running"}:
            continue
        params = dict(job.params or {})
        if bool(params.get("notify")) == bool(enabled):
            out.append({"job_id": job.job_id, "status": job.status, "notify": enabled, "changed": False})
            continue
        params["notify"] = bool(enabled)
        update_job(job.job_id, params=params)
        out.append({"job_id": job.job_id, "status": job.status, "notify": enabled, "changed": True})
    return out
