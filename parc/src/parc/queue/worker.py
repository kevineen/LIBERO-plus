"""キューワーカー: train → 固定 subset eval → prune。"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from parc.config import load_yaml
from parc.disk.budget import check_budget, get_disk_budget
from parc.disk.prune import prune_experiments
from parc.paths import PARC_ROOT, apply_runtime_env, get_paths
from parc.queue.store import QueueJob, claim_next, list_jobs, update_job, write_job_config
from parc.tracking.run import update_run_meta
from parc.queue.ops import write_progress
from parc.queue.process import clear_pid, write_pid


def _find_latest_checkpoint(run_dir: Path) -> Path | None:
    """train_output/checkpoints/<step>/pretrained_model を探す。"""
    ckpt_root = run_dir / "train_output" / "checkpoints"
    if not ckpt_root.is_dir():
        # GRPO 等は直下に pretrained_model を置く
        direct = run_dir / "train_output" / "pretrained_model"
        if direct.is_dir():
            return direct
        alt = run_dir / "pretrained_model"
        return alt if alt.is_dir() else None
    steps: list[tuple[int, Path]] = []
    for p in ckpt_root.iterdir():
        # last シンボリックリンクはスキップ（実体ディレクトリのみ）
        if p.is_symlink() or not p.is_dir():
            continue
        model = p / "pretrained_model"
        if not model.is_dir():
            continue
        try:
            steps.append((int(p.name), model))
        except ValueError:
            continue
    if steps:
        steps.sort(key=lambda x: x[0])
        return steps[-1][1]
    # フォールバック: last → pretrained_model
    last = ckpt_root / "last" / "pretrained_model"
    if last.is_dir():
        return last.resolve()
    return None


def _trim_intermediate_checkpoints(run_dir: Path, keep_last: int = 1) -> None:
    """中間 ckpt を削除して最終だけ残す（ディスク節約）。

    LeRobot は checkpoints/000200 と checkpoints/last→000200 を作る。
    名前ソートで last を残すと実体を消して dangling symlink になるため、
    数字ステップのディレクトリだけを対象にする。
    """
    ckpt_root = run_dir / "train_output" / "checkpoints"
    if not ckpt_root.is_dir():
        return
    numbered: list[tuple[int, Path]] = []
    for p in ckpt_root.iterdir():
        if p.is_symlink() or not p.is_dir():
            continue
        try:
            numbered.append((int(p.name), p))
        except ValueError:
            continue
    numbered.sort(key=lambda x: x[0])
    if keep_last < 1 or len(numbered) <= keep_last:
        return
    import shutil

    for _, p in numbered[:-keep_last]:
        shutil.rmtree(p, ignore_errors=True)


def _job_cancelled(job_id: str) -> bool:
    for j in list_jobs(limit=2000):
        if j.job_id == job_id:
            return j.status == "cancelled"
    return False


def _run_script(
    script: str,
    config: Path,
    extra: list[str] | None = None,
    *,
    job_id: str | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = ["bash", str(PARC_ROOT / "scripts" / script), str(config)]
    if extra:
        cmd.extend(extra)
    if job_id is None:
        return subprocess.run(
            cmd,
            cwd=str(PARC_ROOT),
            capture_output=True,
            text=True,
            check=False,
            env=os.environ.copy(),
        )
    proc = subprocess.Popen(
        cmd,
        cwd=str(PARC_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
        env=os.environ.copy(),
    )
    write_pid(job_id, proc.pid)
    chunks: list[str] = []
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            chunks.append(line)
            if _job_cancelled(job_id):
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except OSError:
                    proc.kill()
                break
        rc = proc.wait()
    except Exception:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        raise
    finally:
        clear_pid(job_id)
    return subprocess.CompletedProcess(cmd, rc, stdout="".join(chunks), stderr="")



_STEP_RE = re.compile(
    r"(?:step[:\s]+|global_step[:\s]+|iteration[:\s]+)(\d+)|(\d+)\s*/\s*(\d+)",
    re.IGNORECASE,
)


def _latest_ckpt_step(run_dir: Path) -> int | None:
    """checkpoints/<step> の最大ステップ番号。"""
    ckpt_root = run_dir / "train_output" / "checkpoints"
    if not ckpt_root.is_dir():
        return None
    best: int | None = None
    for p in ckpt_root.iterdir():
        if p.is_symlink() or not p.is_dir():
            continue
        try:
            n = int(p.name)
        except ValueError:
            continue
        if best is None or n > best:
            best = n
    return best


def _parse_step_from_line(line: str) -> tuple[int | None, int | None]:
    """ログ1行から (step, total) を推定する。"""
    m = _STEP_RE.search(line.replace("\x00", " "))
    if not m:
        return None, None
    if m.group(1):
        return int(m.group(1)), None
    if m.group(2) and m.group(3):
        return int(m.group(2)), int(m.group(3))
    return None, None


def _run_train_with_progress(
    job_id: str,
    cfg_path: Path,
    *,
    notes: str,
    total_steps: int | None,
) -> subprocess.CompletedProcess[str]:
    """train.sh をストリーム実行し、run_id / step を progress に随時書く。"""
    cmd = [
        "bash",
        str(PARC_ROOT / "scripts" / "train.sh"),
        str(cfg_path),
        "--notes",
        notes,
    ]
    log_path = get_paths()["experiments_dir"] / "queue" / f"{job_id}.log"
    chunks: list[str] = []
    run_dir: Path | None = None
    step: int | None = None
    total = total_steps
    last_flush = 0.0

    def _flush_progress(*, force: bool = False) -> None:
        nonlocal last_flush
        now = time.time()
        if not force and now - last_flush < 5.0:
            return
        last_flush = now
        if run_dir is not None:
            ck = _latest_ckpt_step(run_dir)
            use_step = step
            if ck is not None:
                use_step = max(step or 0, ck)
            pct = None
            if total and use_step is not None:
                pct = max(0, min(100, round(100.0 * use_step / total)))
            write_progress(
                job_id,
                phase="train",
                run_id=run_dir.name,
                step=use_step,
                total_steps=total,
                percent=pct,
            )
            update_job(job_id, run_id=run_dir.name)
        else:
            write_progress(
                job_id,
                phase="train",
                step=step,
                total_steps=total,
                percent=(
                    max(0, min(100, round(100.0 * step / total)))
                    if total and step is not None
                    else 0
                ),
            )

    proc = subprocess.Popen(
        cmd,
        cwd=str(PARC_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
        env=os.environ.copy(),
    )
    write_pid(job_id, proc.pid)
    assert proc.stdout is not None
    cancelled = False
    try:
        for line in proc.stdout:
            chunks.append(line)
            # ログは随時追記（巨大化対策で末尾だけでもよいが、失敗解析用に全量）
            if len(chunks) % 20 == 0:
                log_path.write_text("".join(chunks))
            if run_dir is None:
                found = _parse_run_dir_from_output(line)
                if found is not None:
                    run_dir = found
                    update_job(job_id, run_id=run_dir.name)
            s, t = _parse_step_from_line(line)
            if s is not None:
                step = s if step is None else max(step, s)
            if t is not None and t > 0:
                total = t
            _flush_progress()
            if _job_cancelled(job_id):
                cancelled = True
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except OSError:
                    proc.kill()
                break
        rc = proc.wait()
    except Exception:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        raise
    finally:
        clear_pid(job_id)
    text = "".join(chunks)
    log_path.write_text(text)
    if run_dir is None:
        run_dir = _parse_run_dir_from_output(text)
    if run_dir is not None:
        ck = _latest_ckpt_step(run_dir)
        if ck is not None:
            step = ck if step is None else max(step, ck)
        update_job(job_id, run_id=run_dir.name)
    _flush_progress(force=True)
    if cancelled or _job_cancelled(job_id):
        # 負の rc で Pause を downstream に伝える
        return subprocess.CompletedProcess(cmd, -15, stdout=text, stderr="")
    return subprocess.CompletedProcess(cmd, rc, stdout=text, stderr="")


def _parse_run_dir_from_output(text: str) -> Path | None:
    """CLI JSON から run_dir を拾う。"""
    # 末尾付近の JSON オブジェクトを探す
    for match in re.finditer(r"\{[^{}]*\"run_dir\"[^{}]*\}", text, re.DOTALL):
        try:
            obj = json.loads(match.group(0))
            rd = obj.get("run_dir")
            if rd:
                return Path(rd)
        except json.JSONDecodeError:
            continue
    m = re.search(r"created\s+(\S+)", text)
    if m:
        return Path(m.group(1))
    return None


def _prepare_eval_config(
    job: QueueJob,
    train_cfg: dict[str, Any],
    run_dir: Path,
    ckpt: Path,
) -> Path:
    """eval テンプレ + checkpoint path をマージした YAML を書く。"""
    if job.eval_config_path:
        eval_cfg = load_yaml(job.eval_config_path)
    else:
        eval_cfg = {
            "name": train_cfg.get("name", "eval"),
            "seed": train_cfg.get("seed", 0),
            "tags": list(train_cfg.get("tags") or []) + ["auto_eval"],
            "eval": train_cfg.get("eval") or {},
            "policy": {},
        }
    # 比較用サブセットは eval テンプレ優先、無ければ train の eval
    if not eval_cfg.get("eval") and train_cfg.get("eval"):
        eval_cfg["eval"] = dict(train_cfg["eval"])
    # 無人ループでは動画オフを強制
    ev = dict(eval_cfg.get("eval") or {})
    ev.setdefault("save_video", False)
    ev.setdefault("save_frames", False)
    eval_cfg["eval"] = ev

    policy = dict(eval_cfg.get("policy") or {})
    # train 側 policy / train ハイパーを eval に引き継ぐ（hidden 不一致防止）
    src_policy = dict(train_cfg.get("policy") or {})
    train_h = dict(train_cfg.get("train") or {})
    for key in ("state_dim", "action_dim", "hidden", "deterministic"):
        if key in src_policy and key not in policy:
            policy[key] = src_policy[key]
        elif key in train_h and key not in policy:
            policy[key] = train_h[key]
    # GRPO gaussian か LeRobot ckpt か
    marker = ckpt / "grpo_policy.pt"
    if marker.is_file() or (ckpt / "policy.pt").is_file():
        policy["type"] = "grpo_gaussian"
        policy["path"] = str(ckpt)
    else:
        policy["type"] = "checkpoint"
        policy["path"] = str(ckpt)
    policy.setdefault("action_dim", 7)
    policy.setdefault("device", "cuda")
    policy.setdefault("flip_images", True)
    eval_cfg["policy"] = policy
    eval_cfg["name"] = str(train_cfg.get("name", "run")) + "_auto_eval"
    eval_cfg["tags"] = list(dict.fromkeys(list(eval_cfg.get("tags") or []) + ["auto_eval"]))
    if job.sweep_id:
        eval_cfg["sweep_id"] = job.sweep_id

    out = run_dir / "logs" / "auto_eval_config.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    cleaned = {k: v for k, v in eval_cfg.items() if not str(k).startswith("_")}
    out.write_text(yaml.safe_dump(cleaned, allow_unicode=True, sort_keys=False))
    return out


def _merge_eval_into_run_config(run_dir: Path, eval_yaml: Path, ckpt: Path) -> None:
    """既存 run の config.yaml に eval/policy を書き戻し、同一 run で評価できるようにする。"""
    cfg_path = run_dir / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    eval_cfg = yaml.safe_load(eval_yaml.read_text()) or {}
    if eval_cfg.get("eval"):
        cfg["eval"] = eval_cfg["eval"]
    if eval_cfg.get("policy"):
        cfg["policy"] = eval_cfg["policy"]
    else:
        cfg["policy"] = {"type": "checkpoint", "path": str(ckpt), "action_dim": 7, "device": "cuda"}
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))


def execute_job(job: QueueJob) -> dict[str, Any]:
    """1 ジョブを実行する。"""
    apply_runtime_env()
    budget = get_disk_budget(job.params.get("disk") if job.params else None)
    status = check_budget(budget)
    if job.kind in {"train_eval", "train"} and not status["ok"]:
        # 先に prune して再チェック
        prune_experiments(budget, dry_run=False)
        status = check_budget(budget)
        if not status["ok"]:
            update_job(
                job.job_id,
                status="failed",
                error=f"disk budget exceeded: {status['used_gb']}GB / {status['max_gb']}GB",
            )
            return {"status": "failed", "error": "disk_budget", **status}

    if job.kind == "prune":
        report = prune_experiments(budget, dry_run=bool((job.params or {}).get("dry_run", False)))
        update_job(job.job_id, status="done", params={**(job.params or {}), "prune_report": report})
        return {"status": "done", "prune": report}

    cfg_path = write_job_config(job)
    train_cfg = load_yaml(cfg_path)
    write_progress(job.job_id, phase="starting", kind=job.kind)

    # 再現性フィールドを config に埋める
    if job.sweep_id:
        train_cfg["sweep_id"] = job.sweep_id
    if job.trial_index is not None:
        train_cfg["trial_index"] = job.trial_index
    # resume: 既存 ckpt を init に
    resume_run = (job.params or {}).get("resume_run_id")
    init_ckpt = (job.params or {}).get("init_ckpt")
    if init_ckpt and isinstance(train_cfg.get("train"), dict):
        train_cfg["train"] = dict(train_cfg["train"])
        if train_cfg["train"].get("backend") in {"grpo", "gspo"}:
            train_cfg["train"]["init_policy_path"] = str(init_ckpt)
    if resume_run:
        train_cfg["parent_run_id"] = str(resume_run)
    cfg_path.write_text(
        yaml.safe_dump(
            {k: v for k, v in train_cfg.items() if not str(k).startswith("_")},
            allow_unicode=True,
            sort_keys=False,
        )
    )

    result: dict[str, Any] = {"job_id": job.job_id}

    if job.kind in {"train_eval", "train"}:
        total_steps = None
        if isinstance(train_cfg.get("train"), dict):
            try:
                total_steps = int(train_cfg["train"].get("steps") or 0) or None
            except (TypeError, ValueError):
                total_steps = None
        write_progress(
            job.job_id,
            phase="train",
            run_id=None,
            step=0,
            total_steps=total_steps,
            percent=0,
        )
        proc = _run_train_with_progress(
            job.job_id,
            cfg_path,
            notes=job.notes or f"queue:{job.job_id}",
            total_steps=total_steps,
        )
        log_path = get_paths()["experiments_dir"] / "queue" / f"{job.job_id}.log"
        run_dir = _parse_run_dir_from_output((proc.stdout or "") + (proc.stderr or ""))
        if _job_cancelled(job.job_id) or proc.returncode == -15:
            write_progress(job.job_id, phase="paused", run_id=run_dir.name if run_dir else None)
            # cancel_job が既に cancelled にしている。上書きで failed にしない
            if run_dir is not None:
                update_job(job.job_id, run_id=run_dir.name)
                try:
                    update_run_meta(run_dir, status="paused")
                except Exception:
                    pass
            return {
                "status": "cancelled",
                "phase": "train",
                "run_id": run_dir.name if run_dir else None,
                "log": str(log_path),
            }
        if proc.returncode != 0 or run_dir is None:
            write_progress(job.job_id, phase="train_failed", returncode=proc.returncode)
            update_job(
                job.job_id,
                status="failed",
                error=f"train failed rc={proc.returncode}",
                run_id=run_dir.name if run_dir else None,
            )
            return {
                "status": "failed",
                "phase": "train",
                "returncode": proc.returncode,
                "log": str(log_path),
            }
        result["run_dir"] = str(run_dir)
        result["run_id"] = run_dir.name
        update_job(job.job_id, run_id=run_dir.name)
        write_progress(job.job_id, phase="train_done", run_id=run_dir.name)
        # Gate1 用に中間 ckpt を数個残す（ディスクは prune / sweep.disk で管理）
        _trim_intermediate_checkpoints(run_dir, keep_last=3)

        if job.kind == "train":
            write_progress(job.job_id, phase="done", run_id=run_dir.name)
            update_job(job.job_id, status="done")
            prune_experiments(budget, dry_run=False)
            return result

        ckpt = _find_latest_checkpoint(run_dir)
        if ckpt is None:
            write_progress(job.job_id, phase="ckpt_missing", run_id=run_dir.name)
            update_job(job.job_id, status="failed", error="no checkpoint after train", run_id=run_dir.name)
            return {"status": "failed", "phase": "ckpt", "run_dir": str(run_dir)}

        write_progress(job.job_id, phase="eval", run_id=run_dir.name, checkpoint=str(ckpt))
        eval_yaml = _prepare_eval_config(job, train_cfg, run_dir, ckpt)
        _merge_eval_into_run_config(run_dir, eval_yaml, ckpt)

        # 同一 run_dir で評価（robot venv）
        eval_proc = _run_script(
            "eval_ckpt.sh",
            Path(run_dir / "config.yaml"),
            ["--run-dir", str(run_dir)],
            job_id=job.job_id,
        )
        log_path.write_text(
            log_path.read_text()
            + "\n--- eval ---\n"
            + (eval_proc.stdout or "")
            + "\n"
            + (eval_proc.stderr or "")
        )
        if _job_cancelled(job.job_id) or eval_proc.returncode == -15:
            write_progress(job.job_id, phase="paused", run_id=run_dir.name)
            if run_dir is not None:
                try:
                    update_run_meta(run_dir, status="paused")
                except Exception:
                    pass
            return {"status": "cancelled", "phase": "eval", "run_id": run_dir.name}
        if eval_proc.returncode != 0:
            write_progress(job.job_id, phase="eval_failed", run_id=run_dir.name)
            update_job(
                job.job_id,
                status="failed",
                error=f"eval failed rc={eval_proc.returncode}",
                run_id=run_dir.name,
            )
            return {"status": "failed", "phase": "eval", "returncode": eval_proc.returncode}

        # metrics を meta に反映（eval CLI が更新するが念のため）
        metrics_path = run_dir / "metrics.json"
        metrics_summary: dict[str, Any] = {}
        if metrics_path.is_file():
            metrics = json.loads(metrics_path.read_text())
            metrics_summary = {
                "success_rate": metrics.get("success_rate"),
                "n_episodes": metrics.get("n_episodes"),
                "by_category": metrics.get("by_category"),
            }
            update_run_meta(
                run_dir,
                status="finished",
                metrics=metrics_summary,
            )
        write_progress(
            job.job_id,
            phase="done",
            run_id=run_dir.name,
            metrics=metrics_summary,
        )
        update_job(job.job_id, status="done", run_id=run_dir.name)
        prune_experiments(budget, dry_run=False)
        result["status"] = "done"
        return result

    if job.kind == "eval":
        write_progress(job.job_id, phase="eval", kind="eval")
        proc = _run_script("eval_ckpt.sh", cfg_path, job_id=job.job_id)
        log_path = get_paths()["experiments_dir"] / "queue" / f"{job.job_id}.log"
        log_path.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""))
        run_dir = _parse_run_dir_from_output((proc.stdout or "") + (proc.stderr or ""))
        if _job_cancelled(job.job_id) or proc.returncode == -15:
            write_progress(job.job_id, phase="paused", run_id=run_dir.name if run_dir else None)
            return {"status": "cancelled", "phase": "eval"}
        if proc.returncode != 0:
            write_progress(job.job_id, phase="eval_failed", returncode=proc.returncode)
            update_job(job.job_id, status="failed", error=f"eval rc={proc.returncode}")
            return {"status": "failed", "phase": "eval"}
        write_progress(
            job.job_id,
            phase="done",
            run_id=run_dir.name if run_dir else None,
        )
        update_job(job.job_id, status="done", run_id=run_dir.name if run_dir else None)
        return {"status": "done", "run_id": run_dir.name if run_dir else None}

    update_job(job.job_id, status="failed", error=f"unknown kind: {job.kind}")
    return {"status": "failed", "error": "unknown_kind"}


def run_worker_once(
    *,
    max_failures: int = 3,
    failure_count: list[int] | None = None,
) -> QueueJob | None:
    """キューから 1 件 claim して実行。空なら None。"""
    job = claim_next(kinds=["train_eval", "train", "eval", "prune"])
    if job is None:
        return None
    result: dict[str, Any] = {}
    try:
        result = execute_job(job)
        if failure_count is not None:
            if result.get("status") == "failed":
                failure_count[0] += 1
            else:
                failure_count[0] = 0
    except Exception as e:
        update_job(job.job_id, status="failed", error=str(e))
        result = {"status": "failed", "error": str(e)}
        if failure_count is not None:
            failure_count[0] += 1
    # 完了通知（失敗してもワーカーは継続）。Pause/Cancel は通知しない
    if result.get("status") == "cancelled":
        return job
    try:
        import importlib

        import parc.notify as notify_pkg
        import parc.notify.webhook as notify_webhook

        importlib.reload(notify_webhook)
        importlib.reload(notify_pkg)
        from parc.queue.store import list_jobs

        latest = next((j for j in list_jobs(limit=200) if j.job_id == job.job_id), job)
        # progress の metrics を result に載せる
        from parc.queue.ops import read_progress

        prog = read_progress(job.job_id) or {}
        if prog.get("metrics") and "metrics" not in result:
            result = {**result, "metrics": prog["metrics"], "phase": prog.get("phase")}
        notify_pkg.notify_job_finished(latest, result=result)
    except Exception as e:  # noqa: BLE001
        print(f"[parc-worker] notify failed: {e}")
    # Google Drive 等への best ckpt 同期（失敗してもワーカー継続）
    try:
        from parc.sync.gdrive import maybe_upload_after_job

        rid = result.get("run_id") or getattr(job, "run_id", None)
        sync_out = maybe_upload_after_job(result, run_id=rid)
        if sync_out.get("ok"):
            print(f"[parc-worker] gdrive upload ok → {sync_out.get('remote_base')}")
        elif not sync_out.get("skipped"):
            print(f"[parc-worker] gdrive upload failed: {sync_out}")
    except Exception as e:  # noqa: BLE001
        print(f"[parc-worker] gdrive sync failed: {e}")
    return job


def run_worker_loop(
    *,
    poll_sec: float = 30.0,
    max_failures: int = 3,
    once: bool = False,
    stale_after_sec: float = 3600,
    recover_stale_on_start: bool = True,
) -> None:
    """常駐または --once。連続失敗で停止。起動時に stale running を回収。"""
    apply_runtime_env()
    if recover_stale_on_start and not once:
        from parc.queue.ops import recover_stale

        recovered = recover_stale(max_age_sec=stale_after_sec, action="requeue")
        if recovered:
            print(f"[parc-worker] recovered {len(recovered)} stale jobs")
    failures = [0]
    while True:
        job = run_worker_once(max_failures=max_failures, failure_count=failures)
        if once:
            return
        if failures[0] >= max_failures:
            print(f"[parc-worker] stopping after {failures[0]} consecutive failures")
            return
        if job is None:
            time.sleep(poll_sec)
