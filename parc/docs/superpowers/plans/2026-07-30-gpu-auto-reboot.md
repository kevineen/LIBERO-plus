# GPU Auto-Reboot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend hub `parc-fleet gpu-check` so allowlisted hosts (`auto_reboot: true`) get recorded evidence, reboot after 2 consecutive `gpu_dead` checks (1h cooldown), then auto-start `parc-worker` when GPU returns.

**Architecture:** Keep probe/notify in `gpu_watch.py`; add pure decision helpers + reboot/recover/event-log in `gpu_recover.py`. `gpu_check()` orchestrates: probe → streak update → jsonl → optional reboot → optional recover poll. Safety requires CLI `--auto-reboot` or `PARC_GPU_AUTO_REBOOT=1`.

**Tech Stack:** Python 3.10+, existing `parc.remote.hosts.remote_shell`, pytest via `uv run`, YAML hosts config.

**Spec:** `docs/superpowers/specs/2026-07-30-gpu-auto-reboot-design.md`

**Commits:** Do **not** auto-commit unless the user explicitly asks.

---

## File map

| File | Responsibility |
|------|----------------|
| `src/parc/fleet/gpu_recover.py` | streak/cooldown decisions, jsonl events, reboot cmds, recover+worker |
| `src/parc/fleet/gpu_watch.py` | wire recover into `gpu_check`; extend state fields |
| `src/parc/remote/hosts.py` | expose `auto_reboot`, `reboot_method`, optional overrides |
| `src/parc/cli.py` | `--auto-reboot`, `--dry-run-reboot` |
| `configs/hosts.example.yaml` | documented keys |
| `configs/hosts.yaml` | enable `nuc` only |
| `docs/10_ops_ui.md` | ops section |
| `tests/test_gpu_recover.py` | unit tests (no real SSH) |

---

### Task 1: Pure decision helpers + unit tests

**Files:**
- Create: `LIBERO-plus/parc/src/parc/fleet/gpu_recover.py`
- Create: `LIBERO-plus/parc/tests/test_gpu_recover.py`
- Create: `LIBERO-plus/parc/tests/__init__.py` (empty)

- [ ] **Step 1: Add empty tests package and failing tests**

```python
# tests/__init__.py
# (empty)
```

```python
# tests/test_gpu_recover.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from parc.fleet.gpu_recover import (
    DEFAULT_COOLDOWN_HOURS,
    DEFAULT_STREAK_NEEDED,
    next_gpu_dead_streak,
    should_attempt_reboot,
)


def test_streak_increments_on_gpu_dead_and_resets_otherwise():
    assert next_gpu_dead_streak(0, "gpu_dead") == 1
    assert next_gpu_dead_streak(1, "gpu_dead") == 2
    assert next_gpu_dead_streak(2, "ok") == 0
    assert next_gpu_dead_streak(2, "unreachable") == 0


def test_should_attempt_reboot_requires_allow_streak_cooldown_and_switch():
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    base = {
        "auto_reboot_enabled": True,  # CLI/env switch
        "host_auto_reboot": True,
        "status": "gpu_dead",
        "streak": 2,
        "last_reboot_at": None,
        "cooldown_hours": DEFAULT_COOLDOWN_HOURS,
        "streak_needed": DEFAULT_STREAK_NEEDED,
        "now": now,
    }
    ok, reason = should_attempt_reboot(**base)
    assert ok and reason == "ok"

    no, reason = should_attempt_reboot(**{**base, "auto_reboot_enabled": False})
    assert not no and reason == "switch_off"

    no, reason = should_attempt_reboot(**{**base, "host_auto_reboot": False})
    assert not no and reason == "host_disabled"

    no, reason = should_attempt_reboot(**{**base, "status": "unreachable"})
    assert not no and reason == "status_not_gpu_dead"

    no, reason = should_attempt_reboot(**{**base, "streak": 1})
    assert not no and reason == "streak_low"

    recent = (now - timedelta(minutes=30)).isoformat()
    no, reason = should_attempt_reboot(**{**base, "last_reboot_at": recent})
    assert not no and reason == "cooldown"
```

- [ ] **Step 2: Run tests — expect import failure**

Run:

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
uv run pytest tests/test_gpu_recover.py -v
```

Expected: FAIL (`ModuleNotFoundError: parc.fleet.gpu_recover` or similar)

- [ ] **Step 3: Implement helpers in `gpu_recover.py`**

```python
# src/parc/fleet/gpu_recover.py
"""GPU 自動再起動・復帰・イベント記録（hub gpu-check から利用）。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
```

- [ ] **Step 4: Re-run tests — expect PASS**

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
uv run pytest tests/test_gpu_recover.py -v
```

Expected: PASS (2 tests)

---

### Task 2: Event log + dump path helpers

**Files:**
- Modify: `LIBERO-plus/parc/src/parc/fleet/gpu_recover.py`
- Modify: `LIBERO-plus/parc/tests/test_gpu_recover.py`

- [ ] **Step 1: Add tests for jsonl append**

```python
def test_append_event_writes_one_json_line(tmp_path):
    from parc.fleet.gpu_recover import append_event, events_path

    path = tmp_path / "gpu_watch_events.jsonl"
    append_event(
        {
            "hub": "winpc",
            "host": "nuc",
            "event": "probe",
            "status": "gpu_dead",
            "detail": "NVML N/A",
            "streak": 1,
            "action": "none",
            "ok": True,
        },
        path=path,
    )
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["host"] == "nuc"
    assert "ts" in row
```

(Add `import json` at top of test file.)

- [ ] **Step 2: Run test — expect FAIL (append_event missing)**

```bash
uv run pytest tests/test_gpu_recover.py::test_append_event_writes_one_json_line -v
```

- [ ] **Step 3: Implement append_event / paths**

```python
# add to gpu_recover.py
from parc.paths import apply_runtime_env, get_paths


def events_path() -> Path:
    apply_runtime_env()
    return get_paths()["experiments_dir"] / "gpu_watch_events.jsonl"


def dumps_dir() -> Path:
    apply_runtime_env()
    d = get_paths()["experiments_dir"] / "gpu_watch_dumps"
    d.mkdir(parents=True, exist_ok=True)
    return d


def append_event(payload: dict[str, Any], *, path: Path | None = None) -> Path:
    """1 行 JSON を追記。ts が無ければ付与。"""
    p = path or events_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    row = dict(payload)
    row.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/test_gpu_recover.py -v
```

---

### Task 3: Host config fields

**Files:**
- Modify: `LIBERO-plus/parc/src/parc/remote/hosts.py`
- Modify: `LIBERO-plus/parc/tests/test_gpu_recover.py` (or new `tests/test_hosts_gpu_flags.py`)

- [ ] **Step 1: Add `host_gpu_recover_config(alias) -> dict`**

In `hosts.py`, add:

```python
def host_gpu_recover_config(alias: str) -> dict[str, Any]:
    """auto_reboot 関連設定。未知ホストは KeyError。"""
    hosts = load_hosts()
    if alias not in hosts:
        raise KeyError(alias)
    raw = hosts[alias]
    method = str(raw.get("reboot_method") or "windows_shutdown").strip()
    if method not in {"windows_shutdown", "linux_reboot"}:
        method = "windows_shutdown"
    streak = raw.get("gpu_dead_streak_needed")
    cool = raw.get("reboot_cooldown_hours")
    return {
        "auto_reboot": bool(raw.get("auto_reboot", False)),
        "reboot_method": method,
        "streak_needed": int(streak) if streak not in (None, "") else 2,
        "cooldown_hours": float(cool) if cool not in (None, "") else 1.0,
        "parc_dir": str(raw.get("parc_dir") or ""),
        "ssh": str(raw.get("ssh") or ""),
    }
```

Also extend `list_host_summaries()` to include `"auto_reboot": bool(raw.get("auto_reboot", False))` for visibility.

- [ ] **Step 2: Unit test with tmp hosts.yaml via monkeypatch**

```python
def test_host_gpu_recover_config_reads_flags(tmp_path, monkeypatch):
    import parc.remote.hosts as hosts_mod

    cfg = tmp_path / "hosts.yaml"
    cfg.write_text(
        """
hosts:
  nuc:
    ssh: kevin@1.2.3.4
    parc_dir: /tmp/parc
    auto_reboot: true
    reboot_method: windows_shutdown
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(hosts_mod, "PARC_ROOT", tmp_path)
    # load_hosts looks at PARC_ROOT/configs/hosts.yaml — put file there
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "hosts.yaml").write_text(cfg.read_text(), encoding="utf-8")
    c = hosts_mod.host_gpu_recover_config("nuc")
    assert c["auto_reboot"] is True
    assert c["reboot_method"] == "windows_shutdown"
```

Note: `load_hosts` uses `PARC_ROOT / "configs" / name` — monkeypatch `PARC_ROOT` on the module as shown.

- [ ] **Step 3: Run test — PASS**

```bash
uv run pytest tests/test_gpu_recover.py::test_host_gpu_recover_config_reads_flags -v
```

---

### Task 4: Reboot command builder + dry-run execute

**Files:**
- Modify: `LIBERO-plus/parc/src/parc/fleet/gpu_recover.py`
- Modify: `LIBERO-plus/parc/tests/test_gpu_recover.py`

- [ ] **Step 1: Tests for command strings**

```python
def test_reboot_command_windows_and_linux():
    from parc.fleet.gpu_recover import reboot_remote_command

    w = reboot_remote_command("windows_shutdown")
    assert "shutdown.exe" in w and "/r" in w
    lin = reboot_remote_command("linux_reboot")
    assert "reboot" in lin and "sudo" in lin
```

- [ ] **Step 2: Implement**

```python
def reboot_remote_command(method: str) -> str:
    if method == "linux_reboot":
        return "sudo -n /sbin/reboot"
    # default windows (WSL)
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
    """SSH で再起動。dry_run ならコマンドだけ返す。"""
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
```

- [ ] **Step 3: pytest PASS**

---

### Task 5: Evidence dump + recover poll + worker start

**Files:**
- Modify: `LIBERO-plus/parc/src/parc/fleet/gpu_recover.py`
- Modify: `LIBERO-plus/parc/tests/test_gpu_recover.py`

- [ ] **Step 1: Implement `collect_gpu_evidence(alias) -> str`**

SSH script (best-effort):

```bash
export PATH=/usr/lib/wsl/lib:$HOME/.local/bin:$PATH
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}
echo '=== uname ==='; uname -a
echo '=== nvidia-smi ==='; nvidia-smi 2>&1 | head -40
echo '=== dmesg nvidia ==='; dmesg 2>/dev/null | grep -iE 'nvrm|nvidia|xid' | tail -30
```

Save under `dumps_dir() / f"{alias}_{ts}.txt"`. On failure return empty string / path None.

- [ ] **Step 2: Implement `ensure_remote_worker(alias, parc_dir) -> dict`**

Remote bash:

```bash
cd <parc_dir>
export PATH=/usr/lib/wsl/lib:$HOME/.local/bin:$PATH
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}
export PARC_MACHINE_ID=<alias>
mkdir -p experiments/queue
if ps -ef | grep -E '[u]v run parc-worker|[.]venv/bin/parc-worker' >/dev/null; then
  echo ALREADY
  exit 0
fi
nohup uv run parc-worker --loop --poll-sec 15 >> experiments/queue/worker.log 2>&1 &
echo STARTED
```

Return `{"ok": True, "already": bool, ...}`.

- [ ] **Step 3: Implement `recover_after_reboot(alias, *, parc_dir, timeout_sec=600, poll_sec=15) -> dict`**

Loop until timeout:

1. `probe_remote_gpu(alias)` from `gpu_watch` (import carefully to avoid cycles — pass probe fn or import inside function)
2. If status `ok`: call `ensure_remote_worker`; return success
3. sleep `poll_sec`

On timeout: return `{"ok": False, "event": "recover_timeout"}`.

- [ ] **Step 4: Unit-test recover with monkeypatched probe / worker** (no real SSH)

```python
def test_recover_after_reboot_starts_worker_when_gpu_ok(monkeypatch):
    from parc.fleet import gpu_recover as gr

    calls = {"probe": 0, "worker": 0}

    def fake_probe(alias, **kwargs):
        calls["probe"] += 1
        if calls["probe"] < 2:
            return {"status": "unreachable", "detail": "down"}
        return {"status": "ok", "detail": "1 GPU(s)"}

    def fake_worker(alias, parc_dir):
        calls["worker"] += 1
        return {"ok": True, "already": False}

    monkeypatch.setattr(gr, "probe_remote_gpu_for_recover", fake_probe)
    monkeypatch.setattr(gr, "ensure_remote_worker", fake_worker)
    out = gr.recover_after_reboot("nuc", parc_dir="/tmp/p", timeout_sec=5, poll_sec=0)
    assert out["ok"] is True
    assert calls["worker"] == 1
```

Implement thin wrapper `probe_remote_gpu_for_recover` that calls `gpu_watch.probe_remote_gpu`.

---

### Task 6: Wire into `gpu_check`

**Files:**
- Modify: `LIBERO-plus/parc/src/parc/fleet/gpu_watch.py`

- [ ] **Step 1: Extend `gpu_check(...)` signature**

```python
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
```

Effective switch: `auto_reboot or auto_reboot_enabled_from_env()`.

- [ ] **Step 2: Per-host after probe**

For each remote row (skip local for reboot):

1. Load prev entry: `gpu_dead_streak`, `last_reboot_at`
2. `streak = next_gpu_dead_streak(prev, status)`
3. `append_event` probe line (`event=probe` or use alert event name)
4. Update state entry with `gpu_dead_streak=streak`
5. If switch on: `cfg = host_gpu_recover_config(alias)` (catch KeyError for local)
6. `should, reason = should_attempt_reboot(...)`
7. If not should and reason in skip reasons that matter: optional event `reboot_skipped_*`
8. If should:
   - `collect_gpu_evidence` (best-effort)
   - `request_reboot(..., dry_run=dry_run_reboot)`
   - update `last_reboot_at` on successful send (and on dry_run for testing streak/cooldown? **Spec:** update `last_reboot_at` only on real send OR dry_run with flag — prefer: update on dry_run too only if `dry_run_reboot` so cooldown can be tested; document in event `dry_run: true`)
   - Discord via `format_gpu_alert`-like text `[PARC] GPU REBOOT · ...`
   - If real reboot ok (not dry_run): `recover_after_reboot(...)`; append recovered/worker events; notify

- [ ] **Step 3: Include in return JSON**

Add top-level `"reboots": [ ... ]` list of actions taken this run.

- [ ] **Step 4: Manual dry-run on hub (no reboot)**

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
# after hosts.yaml has auto_reboot on nuc — still safe with dry-run
uv run parc-fleet gpu-check --host nuc --auto-reboot --dry-run-reboot --no-notify
```

Expected: JSON with probe result; reboot section only if streak would trigger (may need two forced dead probes — for dry-run testing, allow env `PARC_GPU_FORCE_DEAD=1` **only in tests**, not production).  

**Simpler test path:** unit-test the orchestration with mocked probes in Task 6b below instead of forcing production dead.

---

### Task 6b: Orchestration unit test (mocked)

**Files:**
- Create: `LIBERO-plus/parc/tests/test_gpu_check_reboot.py`

- [ ] **Step 1: Mock `probe_remote_gpu` twice through `gpu_check` with temp state**

Use monkeypatch so first call returns gpu_dead streak builds; second call with same mocked dead triggers reboot dry_run. Assert `request_reboot` called once and event file has `reboot_sent` or dry_run event.

Keep this test hermetic (tmp_path state + events).

---

### Task 7: CLI + hosts + docs

**Files:**
- Modify: `LIBERO-plus/parc/src/parc/cli.py` (gpu-check args + pass-through)
- Modify: `LIBERO-plus/parc/configs/hosts.example.yaml`
- Modify: `LIBERO-plus/parc/configs/hosts.yaml` (nuc only)
- Modify: `LIBERO-plus/parc/docs/10_ops_ui.md`
- Modify: `LIBERO-plus/parc/.env.example` (optional `PARC_GPU_AUTO_REBOOT=0`)

- [ ] **Step 1: CLI flags**

```python
p_gpu.add_argument(
    "--auto-reboot",
    action="store_true",
    help="hosts.yaml で auto_reboot:true の機を連続 gpu_dead 時に再起動",
)
p_gpu.add_argument(
    "--dry-run-reboot",
    action="store_true",
    help="再起動コマンドを実行せず記録・判定のみ",
)
```

Pass into `gpu_check(auto_reboot=..., dry_run_reboot=...)`.

- [ ] **Step 2: hosts.yaml nuc**

```yaml
  nuc:
    ssh: kevin@100.82.118.86
    parc_dir: /home/kevin/Matsuo/LIBERO-plus/parc
    web_port: 3030
    local_web_port: 3031
    auto_reboot: true
    reboot_method: windows_shutdown
```

- [ ] **Step 3: Docs snippet in `10_ops_ui.md`**

Document cron:

```cron
*/5 * * * * cd /path/to/parc && uv run parc-fleet gpu-check --auto-reboot >>/tmp/parc-gpu-check.log 2>&1
```

And point to events file `experiments/gpu_watch_events.jsonl`.

- [ ] **Step 4: Full unit suite**

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
uv run pytest tests/test_gpu_recover.py tests/test_gpu_check_reboot.py -v
```

Expected: all PASS

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Per-host `auto_reboot` | 3, 7 |
| streak=2 | 1, 6 |
| cooldown 1h | 1, 6 |
| only `gpu_dead` | 1 |
| `--auto-reboot` / env | 1 (`auto_reboot_enabled_from_env`), 7 |
| dry-run | 4, 6, 7 |
| jsonl events | 2, 6 |
| evidence dump | 5 |
| windows/linux reboot | 4 |
| recover + worker | 5, 6 |
| Discord reboot/recover | 6 |
| docs / example hosts | 7 |
| unreachable no reboot | 1 |

## Placeholder / consistency self-check

- No TBD steps
- Names: `should_attempt_reboot`, `next_gpu_dead_streak`, `request_reboot`, `recover_after_reboot` used consistently
- Commits omitted per user rule unless requested

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-07-30-gpu-auto-reboot.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — implement in this session with checkpoints  

Which approach?
