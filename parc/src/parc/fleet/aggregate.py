"""hosts.yaml + ローカル registry/queue を横断集約する。"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from parc.paths import apply_runtime_env, get_machine_id, get_paths
from parc.remote.hosts import load_hosts, remote_run, tunnel_hint
from parc.tracking.run import list_registry


def _parse_json_blob(text: str) -> Any:
    """stdout から末尾寄りの JSON オブジェクト/配列を拾う。"""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty remote output")
    # rich print_json は整形済み複数行になり得る
    for opener, closer in (("[", "]"), ("{", "}")):
        start = raw.find(opener)
        end = raw.rfind(closer)
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                continue
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    for line in reversed(lines):
        if line.startswith("{") or line.startswith("["):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise ValueError(f"failed to parse JSON: {raw[:400]}")


def _local_alias() -> str:
    return get_machine_id() or "local"


def fleet_targets() -> list[dict[str, Any]]:
    """集約対象ホスト一覧（local を先頭、hosts.yaml の remote を続く）。"""
    apply_runtime_env()
    local = _local_alias()
    hosts_cfg = load_hosts()
    out: list[dict[str, Any]] = [
        {
            "alias": local,
            "kind": "local",
            "ssh": None,
            "parc_dir": str(get_paths()["parc_root"]),
            "web_port": "3030",
            "local_web_port": None,
            "machine_id": local,
        }
    ]
    for alias, raw in hosts_cfg.items():
        if alias == local:
            # 同じ machine_id のエントリは local に統合
            out[0]["ssh"] = raw.get("ssh")
            out[0]["web_port"] = str(raw.get("web_port") or "3030")
            out[0]["local_web_port"] = raw.get("local_web_port")
            if raw.get("parc_dir"):
                out[0]["parc_dir"] = str(raw["parc_dir"])
            continue
        out.append(
            {
                "alias": alias,
                "kind": "remote",
                "ssh": raw.get("ssh"),
                "parc_dir": raw.get("parc_dir"),
                "web_port": str(raw.get("web_port") or "3030"),
                "local_web_port": raw.get("local_web_port"),
                "machine_id": alias,
            }
        )
    return out


def fleet_hosts() -> dict[str, Any]:
    """ホスト名簿 + 簡易到達性（remote は queue status --json で確認）。"""
    targets = fleet_targets()

    def _one(t: dict[str, Any]) -> dict[str, Any]:
        row = dict(t)
        if t["kind"] == "local":
            row["reachable"] = True
            row["error"] = None
            row["tunnel_hint"] = None
            return row
        try:
            proc = remote_run(
                t["alias"],
                ["parc-queue", "status", "--limit", "1", "--json"],
                capture=True,
            )
            if proc.returncode != 0:
                row["reachable"] = False
                row["error"] = (proc.stderr or proc.stdout or "ssh failed")[:500]
            else:
                row["reachable"] = True
                row["error"] = None
        except Exception as e:  # noqa: BLE001
            row["reachable"] = False
            row["error"] = str(e)
        try:
            row["tunnel_hint"] = tunnel_hint(t["alias"]).strip()
        except Exception:  # noqa: BLE001
            row["tunnel_hint"] = None
        return row

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(4, len(targets))) as pool:
        futs = {pool.submit(_one, t): t["alias"] for t in targets}
        by_alias = {futs[f]: f.result() for f in as_completed(futs)}
    for t in targets:
        rows.append(by_alias[t["alias"]])
    return {"local_alias": _local_alias(), "hosts": rows}


def _local_runs(limit: int) -> list[dict[str, Any]]:
    apply_runtime_env()
    host = _local_alias()
    rows = []
    for r in list_registry(limit=limit):
        sr = None
        if r.metrics and "success_rate" in r.metrics:
            try:
                sr = float(r.metrics["success_rate"])
            except (TypeError, ValueError):
                sr = r.metrics["success_rate"]
        rows.append(
            {
                "host": host,
                "run_id": r.run_id,
                "machine_id": r.machine_id or host,
                "name": r.name,
                "status": r.status,
                "success_rate": sr,
                "tags": list(r.tags),
                "sweep_id": r.sweep_id or "",
                "created_at": r.created_at,
                "notes": r.notes or "",
                "local": True,
            }
        )
    return rows


def _remote_runs(alias: str, limit: int) -> tuple[list[dict[str, Any]], str | None]:
    proc = remote_run(
        alias,
        ["parc-list", "--limit", str(limit), "--json"],
        capture=True,
    )
    if proc.returncode != 0:
        return [], (proc.stderr or proc.stdout or f"rc={proc.returncode}")[:800]
    try:
        data = _parse_json_blob(proc.stdout)
    except ValueError as e:
        return [], str(e)
    if not isinstance(data, list):
        return [], "expected JSON array from parc-list"
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["host"] = alias
        row["local"] = False
        row.setdefault("machine_id", alias)
        out.append(row)
    return out, None


def fleet_runs(*, limit: int = 50) -> dict[str, Any]:
    """全ホストの runs を merge（新しい created_at 優先）。"""
    targets = fleet_targets()
    errors: dict[str, str] = {}
    merged: list[dict[str, Any]] = []

    def _fetch(t: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str | None]:
        if t["kind"] == "local":
            return t["alias"], _local_runs(limit), None
        rows, err = _remote_runs(t["alias"], limit)
        return t["alias"], rows, err

    with ThreadPoolExecutor(max_workers=max(4, len(targets))) as pool:
        futs = [pool.submit(_fetch, t) for t in targets]
        for fut in as_completed(futs):
            alias, rows, err = fut.result()
            if err:
                errors[alias] = err
            else:
                merged.extend(rows)

    merged.sort(key=lambda r: str(r.get("created_at") or r.get("run_id") or ""), reverse=True)
    return {
        "local_alias": _local_alias(),
        "runs": merged[: max(limit * max(1, len(targets)), limit)],
        "errors": errors,
    }


def _local_queue(limit: int) -> dict[str, Any]:
    apply_runtime_env()
    from parc.queue.ops import queue_status

    data = queue_status(limit=limit)
    host = _local_alias()
    jobs = []
    for j in data.get("jobs") or []:
        row = dict(j)
        row["host"] = host
        row["local"] = True
        jobs.append(row)
    return {
        "host": host,
        "reachable": True,
        "error": None,
        "counts": data.get("counts") or {},
        "stale_running": data.get("stale_running") or [],
        "jobs": jobs,
        "top_scores": data.get("top_scores") or [],
        "local": True,
    }


def _remote_queue(alias: str, limit: int) -> dict[str, Any]:
    proc = remote_run(
        alias,
        ["parc-queue", "status", "--limit", str(limit), "--json"],
        capture=True,
    )
    if proc.returncode != 0:
        return {
            "host": alias,
            "reachable": False,
            "error": (proc.stderr or proc.stdout or f"rc={proc.returncode}")[:800],
            "counts": {},
            "stale_running": [],
            "jobs": [],
            "top_scores": [],
            "local": False,
        }
    try:
        data = _parse_json_blob(proc.stdout)
    except ValueError as e:
        return {
            "host": alias,
            "reachable": False,
            "error": str(e),
            "counts": {},
            "stale_running": [],
            "jobs": [],
            "top_scores": [],
            "local": False,
        }
    if not isinstance(data, dict):
        return {
            "host": alias,
            "reachable": False,
            "error": "expected JSON object from parc-queue status",
            "counts": {},
            "stale_running": [],
            "jobs": [],
            "top_scores": [],
            "local": False,
        }
    jobs = []
    for j in data.get("jobs") or []:
        if isinstance(j, dict):
            row = dict(j)
            row["host"] = alias
            row["local"] = False
            jobs.append(row)
    return {
        "host": alias,
        "reachable": True,
        "error": None,
        "counts": data.get("counts") or {},
        "stale_running": data.get("stale_running") or [],
        "jobs": jobs,
        "top_scores": data.get("top_scores") or [],
        "local": False,
    }


def fleet_queue(*, limit: int = 40) -> dict[str, Any]:
    """全ホストの queue を集約。"""
    targets = fleet_targets()
    per_host: list[dict[str, Any]] = []
    all_jobs: list[dict[str, Any]] = []
    errors: dict[str, str] = {}

    def _fetch(t: dict[str, Any]) -> dict[str, Any]:
        if t["kind"] == "local":
            return _local_queue(limit)
        return _remote_queue(t["alias"], limit)

    with ThreadPoolExecutor(max_workers=max(4, len(targets))) as pool:
        futs = {pool.submit(_fetch, t): t["alias"] for t in targets}
        by_alias = {futs[f]: f.result() for f in as_completed(futs)}
    for t in targets:
        block = by_alias[t["alias"]]
        per_host.append(block)
        if block.get("error"):
            errors[t["alias"]] = str(block["error"])
        all_jobs.extend(block.get("jobs") or [])
    return {
        "local_alias": _local_alias(),
        "hosts": per_host,
        "jobs": all_jobs,
        "errors": errors,
    }


def enqueue_on_host(
    host: str,
    *,
    kind: str = "train_eval",
    config: str | None = None,
    sweep: str | None = None,
    eval_config: str = "",
    notes: str = "",
    notify: bool = False,
) -> dict[str, Any]:
    """指定ホストへ parc-enqueue する。host=local / machine_id / hosts alias。"""
    apply_runtime_env()
    local = _local_alias()
    targets = {t["alias"]: t for t in fleet_targets()}
    # "local" エイリアスも許可
    if host in ("local", ".", "self"):
        host = local
    if host not in targets and host != local:
        known = ", ".join(sorted(targets)) or local
        raise KeyError(f"unknown host {host!r}; known: {known}")

    argv = ["parc-enqueue", "--kind", kind]
    if sweep:
        argv.extend(["--sweep", sweep])
    elif config:
        argv.extend(["--config", config])
    else:
        raise ValueError("--config or --sweep required")
    if eval_config:
        argv.extend(["--eval-config", eval_config])
    if notes:
        argv.extend(["--notes", notes])
    if notify:
        argv.append("--notify")

    t = targets.get(host) or {"kind": "local", "alias": local}
    if t.get("kind") == "local" or host == local:
        from parc.config import load_yaml
        from parc.queue.store import enqueue

        if sweep:
            from parc.sweep import enqueue_sweep

            ids = enqueue_sweep(sweep, notes=notes, notify=notify)
            return {"host": local, "job_ids": ids, "kind": "sweep"}
        if kind == "prune":
            job = enqueue(
                kind="prune",
                notes=notes or "fleet prune",
                params={"notify": True} if notify else {},
            )
            return {"host": local, "job_id": job.job_id, "kind": job.kind, "status": job.status}
        cfg = load_yaml(config)  # type: ignore[arg-type]
        params: dict = {"notify": True} if notify else {}
        job = enqueue(
            kind=kind,
            config=cfg,
            config_path=str(config),
            eval_config_path=eval_config,
            sweep_id=str(cfg.get("sweep_id") or ""),
            trial_index=cfg.get("trial_index"),
            notes=notes,
            params=params,
        )
        return {
            "host": local,
            "job_id": job.job_id,
            "kind": job.kind,
            "status": job.status,
        }

    proc = remote_run(host, argv, capture=True)
    out = {
        "host": host,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-1000:],
    }
    if proc.returncode != 0:
        out["ok"] = False
        out["error"] = out["stderr"] or out["stdout"] or f"rc={proc.returncode}"
        return out
    out["ok"] = True
    # job_id 抽出
    m = re.search(r'"job_id"\s*:\s*"([^"]+)"', proc.stdout or "")
    if m:
        out["job_id"] = m.group(1)
    else:
        m2 = re.search(r"q_[\w-]+", proc.stdout or "")
        if m2:
            out["job_id"] = m2.group(0)
    return out
