"""ジョブ実行プロセスの PID 管理と停止。"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import Any

from parc.queue.store import queue_dir


def pid_path(job_id: str) -> Path:
    return queue_dir() / f"{job_id}.pid"


def write_pid(job_id: str, pid: int) -> None:
    """ワーカーが子プロセス起動直後に呼ぶ。"""
    path = pid_path(job_id)
    path.write_text(f"{int(pid)}\n")


def clear_pid(job_id: str) -> None:
    path = pid_path(job_id)
    if path.is_file():
        path.unlink(missing_ok=True)


def read_pid(job_id: str) -> int | None:
    path = pid_path(job_id)
    if not path.is_file():
        return None
    try:
        return int(path.read_text().strip().splitlines()[0])
    except (ValueError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def kill_process_tree(pid: int, *, grace_sec: float = 3.0) -> dict[str, Any]:
    """セッションリーダー前提でプロセスグループへ SIGTERM → SIGKILL。"""
    if pid <= 0:
        return {"killed": False, "reason": "invalid_pid"}
    if not _pid_alive(pid):
        return {"killed": False, "reason": "not_alive", "pid": pid}

    # start_new_session=True で起動した子は pgid == pid
    try:
        pgid = os.getpgid(pid)
    except OSError:
        pgid = pid

    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return {"killed": False, "reason": "gone", "pid": pid, "pgid": pgid}
    except PermissionError as e:
        return {"killed": False, "reason": f"permission: {e}", "pid": pid, "pgid": pgid}

    deadline = time.time() + grace_sec
    while time.time() < deadline:
        if not _pid_alive(pid):
            return {"killed": True, "signal": "SIGTERM", "pid": pid, "pgid": pgid}
        time.sleep(0.2)

    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return {"killed": True, "signal": "SIGTERM", "pid": pid, "pgid": pgid}
    except PermissionError as e:
        return {"killed": False, "reason": f"kill_permission: {e}", "pid": pid, "pgid": pgid}

    return {"killed": True, "signal": "SIGKILL", "pid": pid, "pgid": pgid}


def kill_job_process(job_id: str) -> dict[str, Any]:
    """PID ファイルがあればプロセスツリーを止める。"""
    pid = read_pid(job_id)
    if pid is None:
        return {"killed": False, "reason": "no_pid_file", "job_id": job_id}
    result = kill_process_tree(pid)
    result["job_id"] = job_id
    if result.get("killed") or result.get("reason") in {"not_alive", "gone"}:
        clear_pid(job_id)
    return result
