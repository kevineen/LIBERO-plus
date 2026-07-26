"""実験ランの作成・レジストリ管理。"""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from parc.paths import get_machine_id, get_paths
from parc.tracking.repro import build_repro_fields


@dataclass
class RunMeta:
    """1 実験ランのメタデータ。"""

    run_id: str
    name: str
    created_at: str
    config_path: str
    tags: list[str] = field(default_factory=list)
    status: str = "created"  # created | running | finished | failed
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    # 再現性（無人ループ / スイープ用）
    git_sha: str = ""
    git_dirty: bool = False
    config_hash: str = ""
    eval_fingerprint: str = ""
    env_fingerprint: str = ""
    sweep_id: str = ""
    trial_index: int | None = None
    parent_run_id: str = ""
    seed: int | None = None
    # 複数 PC 分離（旧 registry 行では空文字）
    machine_id: str = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def make_run_id(name: str, *, machine_id: str | None = None) -> str:
    """マシン ID + 短い UUID 付き run_id を生成する。

    形式: ``{utc}_{machine}_{uuid8}_{safe_name}``
    同秒・同名でも衝突しにくく、複数 PC でも識別できる。
    """
    mid = machine_id if machine_id is not None else get_machine_id()
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:40]
    short = uuid.uuid4().hex[:8]
    return f"{_utc_now()}_{mid}_{short}_{safe}"


def registry_path() -> Path:
    return get_paths()["experiments_dir"] / "registry.jsonl"


def append_registry(meta: RunMeta) -> None:
    """レジストリに 1 行追記する。"""
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(asdict(meta), ensure_ascii=False) + "\n")


def list_registry(
    limit: int | None = None,
    *,
    sweep_id: str | None = None,
) -> list[RunMeta]:
    """レジストリを run_id ごとに最新行へ畳み、新しい順で返す。"""
    path = registry_path()
    if not path.is_file():
        return []
    latest: dict[str, RunMeta] = {}
    order: list[str] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            known = {fld.name for fld in RunMeta.__dataclass_fields__.values()}  # type: ignore[attr-defined]
            filtered = {k: v for k, v in d.items() if k in known}
            meta = RunMeta(**filtered)
            if meta.run_id in latest:
                order.remove(meta.run_id)
            latest[meta.run_id] = meta
            order.append(meta.run_id)
    rows = [latest[rid] for rid in reversed(order)]
    if sweep_id:
        rows = [r for r in rows if r.sweep_id == sweep_id]
    if limit is not None:
        rows = rows[:limit]
    return rows


def create_run(
    config: dict[str, Any],
    notes: str = "",
    *,
    sweep_id: str = "",
    trial_index: int | None = None,
    parent_run_id: str = "",
) -> tuple[Path, RunMeta]:
    """実験ディレクトリを作り、設定をコピーしてレジストリ登録する。"""
    paths = get_paths()
    name = str(config.get("name", "unnamed"))
    machine = get_machine_id()
    run_id = make_run_id(name, machine_id=machine)
    run_dir = paths["experiments_dir"] / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    # checkpoints/ は学習バックエンドが作成する（空 dir があると lerobot が拒否する）
    (run_dir / "videos").mkdir()
    (run_dir / "logs").mkdir()

    cfg_out = run_dir / "config.yaml"
    to_dump = {k: v for k, v in config.items() if not str(k).startswith("_")}
    with cfg_out.open("w") as f:
        yaml.safe_dump(to_dump, f, allow_unicode=True, sort_keys=False)

    src = config.get("_config_path")
    if src and Path(src).is_file():
        shutil.copy2(src, run_dir / "config.source.yaml")

    # CLI / スイープ展開済み config からも拾う
    sid = sweep_id or str(config.get("sweep_id") or "")
    tidx = trial_index if trial_index is not None else config.get("trial_index")
    if tidx is not None:
        tidx = int(tidx)
    pid = parent_run_id or str(config.get("parent_run_id") or "")
    repro = build_repro_fields(
        config,
        sweep_id=sid,
        trial_index=tidx,
        parent_run_id=pid,
    )
    tags = list(config.get("tags") or [])
    machine_tag = f"machine:{machine}"
    if machine_tag not in tags:
        tags.append(machine_tag)
    meta = RunMeta(
        run_id=run_id,
        name=name,
        created_at=_utc_now(),
        config_path=str(cfg_out),
        tags=tags,
        status="created",
        notes=notes,
        machine_id=machine,
        **repro,
    )
    with (run_dir / "meta.json").open("w") as f:
        json.dump(asdict(meta), f, indent=2, ensure_ascii=False)
    append_registry(meta)
    return run_dir, meta


def update_run_meta(run_dir: Path, **kwargs: Any) -> RunMeta:
    """meta.json を更新し、レジストリにも最新行を追記する。"""
    meta_path = run_dir / "meta.json"
    data = json.loads(meta_path.read_text())
    data.update(kwargs)
    known = {f.name for f in RunMeta.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {k: v for k, v in data.items() if k in known}
    meta = RunMeta(**filtered)
    meta_path.write_text(json.dumps(asdict(meta), indent=2, ensure_ascii=False))
    append_registry(meta)
    return meta


def _rewrite_registry(keep: dict[str, RunMeta]) -> None:
    """registry.jsonl を keep の内容だけに書き直す（作成時刻順）。"""
    path = registry_path()
    rows = sorted(keep.values(), key=lambda m: m.created_at or m.run_id)
    tmp = path.with_suffix(".jsonl.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w") as f:
        for meta in rows:
            f.write(json.dumps(asdict(meta), ensure_ascii=False) + "\n")
    tmp.replace(path)


def delete_runs(
    *,
    run_ids: list[str] | None = None,
    statuses: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """実験ディレクトリを削除し registry から除去する。

    run_ids と statuses のどちらか（または両方＝積集合）を指定する。
    queued/running 相当の status=running は誤削除防止のため除外（明示 ID 指定時は許可）。
    """
    exp_dir = get_paths()["experiments_dir"]
    latest = {r.run_id: r for r in list_registry(limit=None)}
    # ディレクトリだけある orphan も拾う
    if exp_dir.is_dir():
        for d in exp_dir.iterdir():
            if not d.is_dir() or d.name in {"queue"} or d.name in latest:
                continue
            meta_path = d / "meta.json"
            if meta_path.is_file():
                try:
                    known = {f.name for f in RunMeta.__dataclass_fields__.values()}  # type: ignore[attr-defined]
                    raw = json.loads(meta_path.read_text())
                    latest[d.name] = RunMeta(**{k: v for k, v in raw.items() if k in known})
                except Exception:
                    latest[d.name] = RunMeta(
                        run_id=d.name,
                        name=d.name,
                        created_at="",
                        config_path="",
                        status="unknown",
                    )

    status_filter = {s.strip() for s in (statuses or []) if s.strip()}
    selected: list[str] = []

    if run_ids:
        for rid in run_ids:
            rid = rid.strip()
            if not rid:
                continue
            if rid in latest:
                match = rid
            else:
                matches = [k for k in latest if k.startswith(rid)]
                if len(matches) == 1:
                    match = matches[0]
                elif len(matches) > 1:
                    raise KeyError(f"ambiguous run_id prefix {rid!r}: {matches[:5]}")
                else:
                    # ディレクトリ実体だけある場合
                    if (exp_dir / rid).is_dir():
                        match = rid
                        latest.setdefault(
                            rid,
                            RunMeta(
                                run_id=rid,
                                name=rid,
                                created_at="",
                                config_path="",
                                status="unknown",
                            ),
                        )
                    else:
                        raise KeyError(f"unknown run_id: {rid}")
            meta = latest[match]
            if status_filter and meta.status not in status_filter:
                continue
            # ステータス一括削除時は running を守る（ID 明示なら消せる）
            selected.append(match)
    else:
        if not status_filter:
            raise ValueError("run_ids か statuses のどちらかが必要です")
        for rid, meta in latest.items():
            if meta.status in status_filter:
                selected.append(rid)

    selected = list(dict.fromkeys(selected))
    if dry_run:
        return {"deleted": selected, "count": len(selected), "dry_run": True}

    deleted: list[str] = []
    for rid in selected:
        run_dir = exp_dir / rid
        if run_dir.is_dir():
            shutil.rmtree(run_dir)
        latest.pop(rid, None)
        deleted.append(rid)

    _rewrite_registry(latest)
    return {"deleted": deleted, "count": len(deleted), "dry_run": False}
