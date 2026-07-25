"""experiments/queue.jsonl ベースのジョブキュー。"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from parc.paths import get_paths

try:
    import fcntl
except ImportError:  # Windows 等
    fcntl = None  # type: ignore[assignment]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class QueueJob:
    """1 キュージョブ。"""

    job_id: str
    kind: str  # train_eval | train | eval | prune
    status: str  # queued | running | done | failed | cancelled
    created_at: str
    updated_at: str
    config_path: str = ""
    eval_config_path: str = ""
    sweep_id: str = ""
    trial_index: int | None = None
    notes: str = ""
    run_id: str | None = None
    error: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    # 展開済み設定を直載せする場合（一時ファイル不要）
    config: dict[str, Any] | None = None


def queue_dir() -> Path:
    d = get_paths()["experiments_dir"] / "queue"
    d.mkdir(parents=True, exist_ok=True)
    return d


def queue_path() -> Path:
    return queue_dir() / "queue.jsonl"


def lock_path() -> Path:
    return queue_dir() / "queue.lock"


class _FileLock:
    """単純な排他ロック（単一 GPU ワーカー想定）。"""

    def __init__(self, path: Path, timeout: float = 60.0):
        self.path = path
        self.timeout = timeout
        self._fh: Any = None

    def __enter__(self) -> _FileLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+")
        start = time.time()
        while True:
            try:
                if fcntl is not None:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if time.time() - start > self.timeout:
                    self._fh.close()
                    raise TimeoutError(f"queue lock timeout: {self.path}")
                time.sleep(0.05)
        return self

    def __exit__(self, *args: Any) -> None:
        if self._fh is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self._fh = None


def _read_all_locked() -> dict[str, QueueJob]:
    """job_id → 最新状態。"""
    path = queue_path()
    latest: dict[str, QueueJob] = {}
    if not path.is_file():
        return latest
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            known = {fld.name for fld in QueueJob.__dataclass_fields__.values()}  # type: ignore[attr-defined]
            filtered = {k: v for k, v in d.items() if k in known}
            job = QueueJob(**filtered)
            latest[job.job_id] = job
    return latest


def _append(job: QueueJob) -> None:
    path = queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(asdict(job), ensure_ascii=False) + "\n")


def enqueue(
    *,
    kind: str = "train_eval",
    config_path: str = "",
    eval_config_path: str = "",
    sweep_id: str = "",
    trial_index: int | None = None,
    notes: str = "",
    params: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> QueueJob:
    """ジョブをキュー末尾に追加する。"""
    now = _utc_now()
    job = QueueJob(
        job_id=job_id or f"q_{now.replace(':', '').replace('-', '').replace('.', '')}_{uuid.uuid4().hex[:8]}",
        kind=kind,
        status="queued",
        created_at=now,
        updated_at=now,
        config_path=config_path,
        eval_config_path=eval_config_path,
        sweep_id=sweep_id,
        trial_index=trial_index,
        notes=notes,
        params=params or {},
        config=config,
    )
    with _FileLock(lock_path()):
        _append(job)
    # Web / 外部向けに個別 JSON も残す
    (queue_dir() / f"{job.job_id}.json").write_text(
        json.dumps(asdict(job), indent=2, ensure_ascii=False)
    )
    return job


def update_job(job_id: str, **kwargs: Any) -> QueueJob:
    """状態更新を追記し、スナップショット JSON も更新する。"""
    with _FileLock(lock_path()):
        latest = _read_all_locked()
        if job_id not in latest:
            raise KeyError(f"unknown job_id: {job_id}")
        job = latest[job_id]
        data = asdict(job)
        data.update(kwargs)
        data["updated_at"] = _utc_now()
        known = {fld.name for fld in QueueJob.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        updated = QueueJob(**filtered)
        _append(updated)
    (queue_dir() / f"{job_id}.json").write_text(
        json.dumps(asdict(updated), indent=2, ensure_ascii=False)
    )
    return updated


def claim_next(*, kinds: list[str] | None = None) -> QueueJob | None:
    """queued の最古ジョブを running にして返す。無ければ None。"""
    with _FileLock(lock_path()):
        latest = _read_all_locked()
        # 作成時刻順
        queued = sorted(
            [j for j in latest.values() if j.status == "queued"],
            key=lambda j: j.created_at,
        )
        if kinds:
            queued = [j for j in queued if j.kind in kinds]
        if not queued:
            return None
        job = queued[0]
        data = asdict(job)
        data["status"] = "running"
        data["updated_at"] = _utc_now()
        claimed = QueueJob(**data)
        _append(claimed)
    (queue_dir() / f"{claimed.job_id}.json").write_text(
        json.dumps(asdict(claimed), indent=2, ensure_ascii=False)
    )
    return claimed


def list_jobs(limit: int = 50) -> list[QueueJob]:
    """新しい順のジョブ一覧（最新状態）。"""
    with _FileLock(lock_path()):
        latest = _read_all_locked()
    rows = sorted(latest.values(), key=lambda j: j.updated_at, reverse=True)
    return rows[:limit]


def write_job_config(job: QueueJob) -> Path:
    """ジョブの設定を queue/configs/ に実体化しパスを返す。"""
    cfg_dir = queue_dir() / "configs"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    out = cfg_dir / f"{job.job_id}.yaml"
    if job.config is not None:
        import yaml

        cleaned = {k: v for k, v in job.config.items() if not str(k).startswith("_")}
        out.write_text(yaml.safe_dump(cleaned, allow_unicode=True, sort_keys=False))
        return out
    if job.config_path:
        src = Path(job.config_path)
        if not src.is_absolute():
            from parc.paths import PARC_ROOT

            cand = PARC_ROOT / job.config_path
            src = cand if cand.is_file() else Path(job.config_path)
        if src.is_file():
            out.write_text(src.read_text())
            return out
    raise FileNotFoundError(f"job {job.job_id} has no resolvable config")
