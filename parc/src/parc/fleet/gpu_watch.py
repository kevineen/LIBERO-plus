"""Fleet GPU 死活監視（hub から SSH プローブ → Discord/Slack 通知）。

想定運用:
  # hub（winpc 等）で cron / systemd timer
  */5 * * * * cd /path/to/parc && uv run parc-fleet gpu-check

状態は experiments_dir 配下の JSON に保存し、OK↔NG のエッジでのみ通知する
（同じ障害の連投を防ぐ）。``--remind-hours`` で再通知可能。
"""

from __future__ import annotations

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from parc.fleet.aggregate import fleet_targets
from parc.fleet.gpu_recover import (
    append_event,
    auto_reboot_enabled_from_env,
    collect_gpu_evidence,
    next_gpu_dead_streak,
    recover_after_reboot,
    request_reboot,
    should_attempt_reboot,
)
from parc.notify.webhook import discord_username_for_machine, send_webhook
from parc.paths import apply_runtime_env, get_machine_id, get_paths
from parc.remote.hosts import host_gpu_recover_config, remote_shell

# nvidia-smi が返す 1 行 = 1 GPU。空 / 失敗を「GPU 死」とみなす。
# WSL2 では nvidia-smi が /usr/lib/wsl/lib にあり、非対話 SSH の PATH に入らない。
GPU_PROBE_CMD = (
    "export PATH=/usr/lib/wsl/lib:$HOME/.local/bin:$PATH; "
    "export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}; "
    "nvidia-smi --query-gpu=index,name,memory.total,temperature.gpu "
    "--format=csv,noheader"
)

HostStatus = Literal["ok", "unreachable", "gpu_dead"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(dt: datetime | None = None) -> str:
    return (dt or _utc_now()).isoformat()


def state_path() -> Path:
    """監視状態ファイルのパス（マシンローカル・git 外想定）。"""
    apply_runtime_env()
    root = get_paths()["experiments_dir"]
    return root / ".parc_gpu_watch.json"


def load_state(path: Path | None = None) -> dict[str, Any]:
    """前回チェック結果を読む。無ければ空。"""
    p = path or state_path()
    if not p.is_file():
        return {"hosts": {}, "updated_at": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 壊れていても監視は続行
        return {"hosts": {}, "updated_at": None, "load_error": True}
    if not isinstance(data, dict):
        return {"hosts": {}, "updated_at": None}
    hosts = data.get("hosts")
    if not isinstance(hosts, dict):
        hosts = {}
    return {"hosts": hosts, "updated_at": data.get("updated_at")}


def save_state(state: dict[str, Any], path: Path | None = None) -> Path:
    """状態を atomic に書き込む。"""
    p = path or state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _utc_iso(),
        "hosts": state.get("hosts") or {},
    }
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p


def parse_nvidia_smi(stdout: str) -> list[dict[str, str]]:
    """``nvidia-smi --format=csv,noheader`` の行をパースする。"""
    gpus: list[dict[str, str]] = []
    for raw in (stdout or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        # ドライバ落ち時の定番メッセージは GPU 行ではない
        lower = line.lower()
        if "failed" in lower or "error" in lower or "unable" in lower:
            continue
        parts = [x.strip() for x in line.split(",")]
        if len(parts) < 2:
            continue
        gpus.append(
            {
                "index": parts[0],
                "name": parts[1],
                "memory_total": parts[2] if len(parts) > 2 else "",
                "temperature": parts[3] if len(parts) > 3 else "",
            }
        )
    return gpus


def _classify_probe(
    *,
    returncode: int,
    stdout: str,
    stderr: str,
    ssh_failed: bool,
) -> tuple[HostStatus, str, list[dict[str, str]]]:
    """プローブ結果を ok / unreachable / gpu_dead に分類する。"""
    err = (stderr or stdout or "").strip()
    if ssh_failed or returncode == 255:
        detail = err[:400] or f"ssh rc={returncode}"
        return "unreachable", detail, []

    gpus = parse_nvidia_smi(stdout)
    if returncode != 0 or not gpus:
        detail = err[:400] or (stdout or "").strip()[:400] or f"nvidia-smi rc={returncode}"
        if "NVIDIA-SMI has failed" in (stdout or "") + (stderr or ""):
            detail = "NVIDIA-SMI has failed (driver/GPU)"
        elif not gpus and returncode == 0:
            detail = "nvidia-smi returned no GPUs"
        return "gpu_dead", detail, []

    return "ok", f"{len(gpus)} GPU(s)", gpus


def probe_local_gpu(*, timeout_sec: float = 20.0) -> dict[str, Any]:
    """自マシンの nvidia-smi を実行する。"""
    try:
        proc = subprocess.run(
            GPU_PROBE_CMD,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return {
            "alias": get_machine_id() or "local",
            "kind": "local",
            "status": "gpu_dead",
            "detail": f"nvidia-smi timeout ({timeout_sec}s)",
            "gpus": [],
            "checked_at": _utc_iso(),
        }
    except FileNotFoundError:
        return {
            "alias": get_machine_id() or "local",
            "kind": "local",
            "status": "gpu_dead",
            "detail": "nvidia-smi not found",
            "gpus": [],
            "checked_at": _utc_iso(),
        }
    status, detail, gpus = _classify_probe(
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        ssh_failed=False,
    )
    return {
        "alias": get_machine_id() or "local",
        "kind": "local",
        "status": status,
        "detail": detail,
        "gpus": gpus,
        "checked_at": _utc_iso(),
        "returncode": proc.returncode,
    }


def probe_remote_gpu(alias: str, *, connect_timeout: int = 8) -> dict[str, Any]:
    """SSH 経由でリモートの nvidia-smi を実行する。"""
    try:
        proc = remote_shell(
            alias,
            GPU_PROBE_CMD,
            capture=True,
            connect_timeout=connect_timeout,
        )
    except Exception as e:  # noqa: BLE001
        return {
            "alias": alias,
            "kind": "remote",
            "status": "unreachable",
            "detail": str(e)[:400],
            "gpus": [],
            "checked_at": _utc_iso(),
        }
    # SSH 自体の失敗は多くの場合 rc=255
    ssh_failed = proc.returncode == 255
    status, detail, gpus = _classify_probe(
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        ssh_failed=ssh_failed,
    )
    return {
        "alias": alias,
        "kind": "remote",
        "status": status,
        "detail": detail,
        "gpus": gpus,
        "checked_at": _utc_iso(),
        "returncode": proc.returncode,
    }


def format_gpu_alert(
    row: dict[str, Any],
    *,
    event: str,
    hub: str,
) -> str:
    """Discord 向けアラート本文。"""
    alias = row.get("alias") or "unknown"
    status = row.get("status") or "unknown"
    detail = (row.get("detail") or "").strip()
    gpus = row.get("gpus") if isinstance(row.get("gpus"), list) else []
    lines = [
        f"[PARC] GPU {event.upper()} · `{alias}`",
        f"hub={hub}  host={alias}  status={status}",
    ]
    if detail:
        lines.append(f"detail={detail[:300]}")
    if gpus:
        for g in gpus[:4]:
            if not isinstance(g, dict):
                continue
            bits = [g.get("index", "?"), g.get("name", "?")]
            if g.get("memory_total"):
                bits.append(str(g["memory_total"]))
            if g.get("temperature"):
                bits.append(f"{g['temperature']}C")
            lines.append("  gpu: " + " · ".join(bits))
    lines.append(f"checked_at={row.get('checked_at') or _utc_iso()}")
    return "\n".join(lines)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def should_alert(
    prev: dict[str, Any] | None,
    curr: dict[str, Any],
    *,
    remind_hours: float = 0.0,
    force: bool = False,
) -> tuple[bool, str]:
    """通知すべきかとイベント名（alert / recovered / remind）を返す。

    - 初回 OK: 通知しない（ノイズ防止）
    - 初回 NG: alert
    - OK→NG: alert
    - NG→OK: recovered
    - 同じ NG だが未通知（``--no-notify`` 後など）: alert
    - 同じ NG が remind_hours 以上継続: remind
    - force: 毎回 alert/ok を送る
    """
    status = str(curr.get("status") or "")
    if force:
        return True, "ok" if status == "ok" else "alert"

    if prev is None:
        if status == "ok":
            return False, "skip_initial_ok"
        return True, "alert"

    prev_status = str(prev.get("status") or "")
    if prev_status == "ok" and status != "ok":
        return True, "alert"
    if prev_status != "ok" and status == "ok":
        return True, "recovered"
    if prev_status != "ok" and status != "ok" and prev_status != status:
        # unreachable ↔ gpu_dead の切り替わりも知らせる
        return True, "alert"
    if status != "ok" and prev_status == status:
        # --no-notify で状態だけ書いた場合はまだ未通知扱い
        if not prev.get("last_alert_at"):
            return True, "alert"
        if remind_hours > 0:
            last = _parse_iso(str(prev.get("last_alert_at") or ""))
            if last is not None:
                age_h = (_utc_now() - last.astimezone(timezone.utc)).total_seconds() / 3600.0
                if age_h >= remind_hours:
                    return True, "remind"
    return False, "noop"


def gpu_check(
    *,
    hosts: list[str] | None = None,
    include_local: bool = False,
    notify: bool = True,
    remind_hours: float = 0.0,
    force: bool = False,
    connect_timeout: int = 8,
    state_file: Path | None = None,
    auto_reboot: bool = False,
    dry_run_reboot: bool = False,
    recover_timeout_sec: float = 600.0,
) -> dict[str, Any]:
    """全（または指定）ホストの GPU をプローブし、必要なら webhook 通知する。"""
    apply_runtime_env()
    hub = get_machine_id() or "hub"
    auto_reboot_switch = bool(auto_reboot) or auto_reboot_enabled_from_env()
    targets = fleet_targets()
    # remote のみ既定。local は include_local か hosts 明示時。
    selected: list[dict[str, Any]] = []
    want = {h.strip() for h in (hosts or []) if h and h.strip()}
    for t in targets:
        alias = str(t["alias"])
        if want and alias not in want and not (alias == hub and "local" in want):
            continue
        if t["kind"] == "local":
            if include_local or (want and (alias in want or "local" in want)):
                selected.append(t)
            continue
        if not want or alias in want:
            selected.append(t)

    if want:
        known = {t["alias"] for t in targets} | {"local", hub}
        unknown = sorted(want - known)
        if unknown and not selected:
            raise KeyError(f"unknown host(s): {', '.join(unknown)}")

    prev_state = load_state(state_file)
    prev_hosts: dict[str, Any] = dict(prev_state.get("hosts") or {})

    def _one(t: dict[str, Any]) -> dict[str, Any]:
        if t["kind"] == "local":
            return probe_local_gpu()
        return probe_remote_gpu(t["alias"], connect_timeout=connect_timeout)

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(4, len(selected) or 1)) as pool:
        futs = {pool.submit(_one, t): t["alias"] for t in selected}
        by_alias = {futs[f]: f.result() for f in as_completed(futs)}
    for t in selected:
        rows.append(by_alias[t["alias"]])

    notifications: list[dict[str, Any]] = []
    reboots: list[dict[str, Any]] = []
    new_hosts: dict[str, Any] = dict(prev_hosts)
    unhealthy = 0

    for row in rows:
        alias = str(row["alias"])
        status = str(row["status"])
        if status != "ok":
            unhealthy += 1
        prev = prev_hosts.get(alias) if isinstance(prev_hosts.get(alias), dict) else None
        do_send, event = should_alert(
            prev,
            row,
            remind_hours=remind_hours,
            force=force,
        )
        entry = {
            "status": status,
            "detail": row.get("detail"),
            "gpus": row.get("gpus") or [],
            "checked_at": row.get("checked_at"),
            "kind": row.get("kind"),
            "last_alert_at": (prev or {}).get("last_alert_at") if prev else None,
            "last_event": (prev or {}).get("last_event") if prev else None,
        }
        row["event"] = event
        row["notified"] = False
        is_remote = row.get("kind") == "remote"
        streak = 0
        last_reboot_at = (prev or {}).get("last_reboot_at")

        if is_remote:
            prev_streak = int((prev or {}).get("gpu_dead_streak") or 0)
            streak = next_gpu_dead_streak(prev_streak, status)
            entry["gpu_dead_streak"] = streak
            entry["last_reboot_at"] = last_reboot_at
            entry["last_reboot_result"] = (prev or {}).get("last_reboot_result")
            append_event(
                {
                    "hub": hub,
                    "host": alias,
                    "event": event if do_send else "probe",
                    "status": status,
                    "detail": row.get("detail"),
                    "streak": streak,
                    "action": "none",
                }
            )

        if do_send and notify:
            text = format_gpu_alert(row, event=event, hub=hub)
            # 表示名は問題ホスト。hub 発でも「どの機の GPU か」が一目で分かる。
            out = send_webhook(text, username=discord_username_for_machine(alias))
            out["host"] = alias
            out["event"] = event
            out["preview"] = text[:400]
            notifications.append(out)
            row["notified"] = bool(out.get("ok"))
            if out.get("ok"):
                entry["last_alert_at"] = _utc_iso()
                entry["last_event"] = event
        elif do_send and not notify:
            row["notify_skipped"] = "notify disabled"
            notifications.append(
                {
                    "ok": False,
                    "skipped": True,
                    "host": alias,
                    "event": event,
                    "preview": format_gpu_alert(row, event=event, hub=hub)[:400],
                }
            )

        if auto_reboot_switch and is_remote:
            try:
                cfg = host_gpu_recover_config(alias)
            except KeyError:
                cfg = None
            if cfg is not None:
                should_reboot, reason = should_attempt_reboot(
                    auto_reboot_enabled=auto_reboot_switch,
                    host_auto_reboot=bool(cfg["auto_reboot"]),
                    status=status,
                    streak=streak,
                    last_reboot_at=last_reboot_at,
                    cooldown_hours=float(cfg["cooldown_hours"]),
                    streak_needed=int(cfg["streak_needed"]),
                )
                if not should_reboot and reason in {
                    "streak_low",
                    "cooldown",
                    "host_disabled",
                }:
                    append_event(
                        {
                            "hub": hub,
                            "host": alias,
                            "event": f"reboot_skipped_{reason}",
                            "status": status,
                            "detail": row.get("detail"),
                            "streak": streak,
                            "action": "none",
                        }
                    )
                elif should_reboot:
                    try:
                        evidence = collect_gpu_evidence(alias)
                    except Exception as exc:  # noqa: BLE001 — evidence は best-effort
                        evidence = {"ok": False, "detail": str(exc)[:400]}
                    try:
                        reboot_result = request_reboot(
                            alias,
                            method=str(cfg["reboot_method"]),
                            dry_run=dry_run_reboot,
                        )
                    except Exception as exc:  # noqa: BLE001 — 失敗を状態・イベントへ残す
                        reboot_result = {
                            "ok": False,
                            "dry_run": dry_run_reboot,
                            "detail": str(exc)[:400],
                        }
                    reboot_action = {
                        **reboot_result,
                        "host": alias,
                        "method": str(cfg["reboot_method"]),
                        "evidence": evidence,
                    }
                    reboots.append(reboot_action)
                    reboot_event = (
                        "reboot_sent"
                        if reboot_result.get("ok")
                        else "reboot_failed"
                    )
                    append_event(
                        {
                            "hub": hub,
                            "host": alias,
                            "event": reboot_event,
                            "status": status,
                            "detail": reboot_result.get("detail") or row.get("detail"),
                            "streak": streak,
                            "action": "reboot",
                            "ok": bool(reboot_result.get("ok")),
                            "dry_run": bool(reboot_result.get("dry_run")),
                        }
                    )
                    entry["last_reboot_result"] = reboot_action
                    # dry-run ではクールダウンを汚さない（実再起動時のみ last_reboot_at）
                    if reboot_result.get("ok") and not dry_run_reboot:
                        entry["last_reboot_at"] = _utc_iso()
                    if reboot_result.get("ok") and notify:
                        text = format_gpu_alert(row, event="reboot", hub=hub)
                        out = send_webhook(
                            text,
                            username=discord_username_for_machine(alias),
                        )
                        out["host"] = alias
                        out["event"] = "reboot"
                        out["preview"] = text[:400]
                        notifications.append(out)

                    if reboot_result.get("ok") and not dry_run_reboot:
                        recovery = recover_after_reboot(
                            alias,
                            parc_dir=str(cfg["parc_dir"]),
                            timeout_sec=recover_timeout_sec,
                        )
                        reboot_action["recovery"] = recovery
                        recovery_event = (
                            "recovered" if recovery.get("ok") else "recover_timeout"
                        )
                        append_event(
                            {
                                "hub": hub,
                                "host": alias,
                                "event": recovery_event,
                                "status": "ok" if recovery.get("ok") else status,
                                "detail": recovery.get("detail") or row.get("detail"),
                                "streak": streak,
                                "action": "recover",
                                "ok": bool(recovery.get("ok")),
                            }
                        )
                        worker = recovery.get("worker") if isinstance(recovery, dict) else None
                        if recovery.get("ok") and isinstance(worker, dict):
                            worker_event = (
                                "worker_already_running"
                                if worker.get("already")
                                else "worker_started"
                            )
                            append_event(
                                {
                                    "hub": hub,
                                    "host": alias,
                                    "event": worker_event,
                                    "status": "ok",
                                    "detail": worker.get("stdout") or worker.get("detail"),
                                    "streak": streak,
                                    "action": "worker",
                                    "ok": bool(worker.get("ok")),
                                }
                            )
                        if recovery.get("ok") and notify:
                            recovered_row = recovery.get("probe")
                            if not isinstance(recovered_row, dict):
                                recovered_row = {**row, "status": "ok"}
                            text = format_gpu_alert(
                                recovered_row,
                                event="recovered",
                                hub=hub,
                            )
                            out = send_webhook(
                                text,
                                username=discord_username_for_machine(alias),
                            )
                            out["host"] = alias
                            out["event"] = "recovered"
                            out["preview"] = text[:400]
                            notifications.append(out)

        new_hosts[alias] = entry

    path = save_state({"hosts": new_hosts}, state_file)
    return {
        "hub": hub,
        "checked_at": _utc_iso(),
        "state_path": str(path),
        "hosts": rows,
        "notifications": notifications,
        "reboots": reboots,
        "unhealthy": unhealthy,
        "ok": unhealthy == 0,
    }


def remind_hours_from_env() -> float:
    """``PARC_GPU_WATCH_REMIND_HOURS``（未設定なら 0 = 再通知なし）。"""
    raw = (os.environ.get("PARC_GPU_WATCH_REMIND_HOURS") or "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0
