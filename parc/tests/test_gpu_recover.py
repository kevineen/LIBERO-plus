from __future__ import annotations

import json
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
        "auto_reboot_enabled": True,
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


def test_host_gpu_recover_config_reads_flags(tmp_path, monkeypatch):
    import parc.remote.hosts as hosts_mod

    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "hosts.yaml").write_text(
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
    c = hosts_mod.host_gpu_recover_config("nuc")
    assert c["auto_reboot"] is True
    assert c["reboot_method"] == "windows_shutdown"


def test_reboot_command_windows_and_linux():
    from parc.fleet.gpu_recover import reboot_remote_command

    w = reboot_remote_command("windows_shutdown")
    assert "shutdown.exe" in w and "/r" in w
    lin = reboot_remote_command("linux_reboot")
    assert "reboot" in lin and "sudo" in lin


def test_append_event_writes_one_json_line(tmp_path):
    from parc.fleet.gpu_recover import append_event

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


def test_recover_after_reboot_starts_worker_when_gpu_ok(monkeypatch):
    from parc.fleet import gpu_recover as gr

    calls = {"probe": 0, "worker": 0}

    def fake_probe(alias, **kwargs):
        calls["probe"] += 1
        if calls["probe"] < 2:
            return {"status": "unreachable", "detail": "down"}
        return {"status": "ok", "detail": "1 GPU(s)"}

    def fake_worker(alias, parc_dir, **kwargs):
        calls["worker"] += 1
        return {"ok": True, "already": False}

    monkeypatch.setattr(gr, "probe_remote_gpu_for_recover", fake_probe)
    monkeypatch.setattr(gr, "ensure_remote_worker", fake_worker)
    out = gr.recover_after_reboot("nuc", parc_dir="/tmp/p", timeout_sec=5, poll_sec=0)
    assert out["ok"] is True
    assert calls["worker"] == 1
    assert calls["probe"] >= 2
