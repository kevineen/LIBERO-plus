"""GPU 自動再起動・復帰・イベント記録（hub gpu-check から利用）。"""

from __future__ import annotations

import json
import os
import shlex
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from parc.paths import apply_runtime_env, get_paths

DEFAULT_STREAK_NEEDED = 2
DEFAULT_COOLDOWN_HOURS = 1.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def next_gpu_dead_streak(prev_streak: int, status: str) -> int:
    """gpu_dead 連続回数。ok / unreachable では 0 に戻す。"""
    if status == "gpu_dead":
        return max(0, int(prev_streak)) + 1
    return 0


def should_attempt_reboot(
    *,
    auto_reboot_enabled: bool,
    host_auto_reboot: bool,
    status: str,
    streak: int,
    last_reboot_at: str | None,
    cooldown_hours: float = DEFAULT_COOLDOWN_HOURS,
    streak_needed: int = DEFAULT_STREAK_NEEDED,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """再起動してよいか。理由コードはテスト・jsonl 用。"""
    if not auto_reboot_enabled:
        return False, "switch_off"
    if not host_auto_reboot:
        return False, "host_disabled"
    if status != "gpu_dead":
        return False, "status_not_gpu_dead"
    if int(streak) < int(streak_needed):
        return False, "streak_low"
    ts = _parse_iso(last_reboot_at)
    if ts is not None and float(cooldown_hours) > 0:
        age_h = ((_utc_now() if now is None else now) - ts.astimezone(timezone.utc)).total_seconds() / 3600.0
        if age_h < float(cooldown_hours):
            return False, "cooldown"
    return True, "ok"


def auto_reboot_enabled_from_env() -> bool:
    raw = (os.environ.get("PARC_GPU_AUTO_REBOOT") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def events_path() -> Path:
    """GPU 監視イベント JSONL のパス。"""
    apply_runtime_env()
    return get_paths()["experiments_dir"] / "gpu_watch_events.jsonl"


def dumps_dir() -> Path:
    """再起動前後の診断ダンプ保存ディレクトリ（存在しなければ作成）。"""
    apply_runtime_env()
    d = get_paths()["experiments_dir"] / "gpu_watch_dumps"
    d.mkdir(parents=True, exist_ok=True)
    return d


def append_event(payload: dict[str, Any], *, path: Path | None = None) -> Path:
    """1 行 JSON を追記。ts が無ければ UTC ISO を付与。"""
    p = path or events_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    row = dict(payload)
    row.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p


def reboot_remote_command(method: str) -> str:
    if method == "linux_reboot":
        return "sudo -n /sbin/reboot"
    return (
        "/mnt/c/Windows/System32/shutdown.exe /r /t 5 /f "
        '/c "PARC GPU auto-reboot"'
    )


def request_reboot(
    alias: str,
    *,
    method: str,
    dry_run: bool,
    connect_timeout: int = 8,
) -> dict[str, Any]:
    from parc.remote.hosts import remote_shell

    cmd = reboot_remote_command(method)
    if dry_run:
        return {"ok": True, "dry_run": True, "command": cmd, "alias": alias}
    proc = remote_shell(alias, cmd, capture=True, connect_timeout=connect_timeout)
    return {
        "ok": proc.returncode == 0,
        "dry_run": False,
        "command": cmd,
        "alias": alias,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[:400],
        "stderr": (proc.stderr or "")[:400],
    }


def collect_gpu_evidence(
    alias: str,
    *,
    connect_timeout: int = 8,
) -> dict[str, Any]:
    """SSH 経由で GPU 障害の診断情報を収集し、ローカルへ保存する。"""
    from parc.remote.hosts import remote_shell

    diagnostic_script = "\n".join(
        [
            "export PATH=/usr/lib/wsl/lib:$HOME/.local/bin:$PATH",
            "export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}",
            "echo '=== uname ==='; uname -a",
            "echo '=== nvidia-smi ==='; nvidia-smi 2>&1 | head -40",
            (
                "echo '=== dmesg nvidia ==='; "
                "dmesg 2>/dev/null | grep -iE 'nvrm|nvidia|xid' | tail -30"
            ),
        ]
    )
    try:
        proc = remote_shell(
            alias,
            diagnostic_script,
            capture=True,
            connect_timeout=connect_timeout,
        )
        timestamp = _utc_now().strftime("%Y%m%dT%H%M%S%fZ")
        path = dumps_dir() / f"{alias}_{timestamp}.txt"
        output = proc.stdout or ""
        if proc.stderr:
            output += f"\n=== stderr ===\n{proc.stderr}"
        path.write_text(output, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "path": None, "detail": str(exc)[:400]}

    ok = proc.returncode == 0
    detail = "collected" if ok else (proc.stderr or f"returncode={proc.returncode}")[:400]
    return {"ok": ok, "path": str(path), "detail": detail}


def ensure_remote_worker(
    alias: str,
    parc_dir: str,
    *,
    connect_timeout: int = 8,
) -> dict[str, Any]:
    """リモート GPU 復帰後に PARC worker が一つ稼働している状態を保証する。"""
    from parc.remote.hosts import remote_shell

    command = "\n".join(
        [
            f"cd {shlex.quote(parc_dir)}",
            "export PATH=/usr/lib/wsl/lib:$HOME/.local/bin:$PATH",
            "export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}",
            f"export PARC_MACHINE_ID={shlex.quote(alias)}",
            "mkdir -p experiments/queue",
            (
                "if ps -ef | grep -Eq "
                "'[u]v run parc-worker|[.]venv/bin/parc-worker'; then "
                "echo ALREADY; exit 0; fi"
            ),
            (
                "nohup uv run parc-worker --loop --poll-sec 15 "
                ">> experiments/queue/worker.log 2>&1 &"
            ),
            "echo STARTED",
        ]
    )
    try:
        proc = remote_shell(
            alias,
            command,
            capture=True,
            connect_timeout=connect_timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "already": False,
            "stdout": "",
            "stderr": str(exc),
            "returncode": None,
        }

    stdout = proc.stdout or ""
    return {
        "ok": proc.returncode == 0,
        "already": "ALREADY" in stdout,
        "stdout": stdout,
        "stderr": proc.stderr or "",
        "returncode": proc.returncode,
    }


def probe_remote_gpu_for_recover(alias: str, **kwargs: Any) -> dict[str, Any]:
    """循環 import を避けてリモート GPU プローブを呼び出す。"""
    from parc.fleet.gpu_watch import probe_remote_gpu

    return probe_remote_gpu(alias, **kwargs)


def recover_after_reboot(
    alias: str,
    *,
    parc_dir: str,
    timeout_sec: float = 600.0,
    poll_sec: float = 15.0,
    connect_timeout: int = 8,
) -> dict[str, Any]:
    """再起動後の GPU 復帰を待ち、復帰時にリモート worker を起動する。"""
    deadline = time.monotonic() + timeout_sec
    while True:
        probe = probe_remote_gpu_for_recover(
            alias,
            connect_timeout=connect_timeout,
        )
        if probe.get("status") == "ok":
            worker = ensure_remote_worker(
                alias,
                parc_dir,
                connect_timeout=connect_timeout,
            )
            return {
                "ok": True,
                "event": "recovered",
                "worker": worker,
                "probe": probe,
            }
        if time.monotonic() >= deadline:
            return {"ok": False, "event": "recover_timeout"}
        if poll_sec > 0:
            time.sleep(poll_sec)
