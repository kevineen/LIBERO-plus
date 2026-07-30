from __future__ import annotations

import json

from parc.fleet import gpu_watch


def test_gpu_check_requests_dry_run_reboot_at_required_streak(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "hosts": {
                    "nuc": {
                        "status": "gpu_dead",
                        "gpu_dead_streak": 1,
                        "last_reboot_at": None,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        gpu_watch,
        "fleet_targets",
        lambda: [{"alias": "nuc", "kind": "remote"}],
    )
    monkeypatch.setattr(
        gpu_watch,
        "probe_remote_gpu",
        lambda alias, **kwargs: {
            "alias": alias,
            "kind": "remote",
            "status": "gpu_dead",
            "detail": "NVIDIA-SMI has failed",
            "gpus": [],
            "checked_at": "2026-07-30T12:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        gpu_watch,
        "host_gpu_recover_config",
        lambda alias: {
            "auto_reboot": True,
            "reboot_method": "windows_shutdown",
            "streak_needed": 2,
            "cooldown_hours": 1.0,
            "parc_dir": "/tmp",
        },
    )
    monkeypatch.setattr(
        gpu_watch,
        "collect_gpu_evidence",
        lambda alias: {"ok": True, "path": None},
    )
    events = []
    monkeypatch.setattr(gpu_watch, "append_event", lambda payload: events.append(payload))
    reboot_calls = []

    def fake_request_reboot(alias, *, method, dry_run):
        reboot_calls.append(
            {"alias": alias, "method": method, "dry_run": dry_run}
        )
        return {"ok": True, "dry_run": dry_run, "alias": alias}

    monkeypatch.setattr(gpu_watch, "request_reboot", fake_request_reboot)

    result = gpu_watch.gpu_check(
        auto_reboot=True,
        dry_run_reboot=True,
        notify=False,
        state_file=state_file,
    )

    assert reboot_calls == [
        {"alias": "nuc", "method": "windows_shutdown", "dry_run": True}
    ]
    assert result["reboots"]
    assert result["reboots"][0]["dry_run"] is True
    assert any(event["event"] == "reboot_sent" for event in events)
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["hosts"]["nuc"]["gpu_dead_streak"] == 2
    # dry-run はクールダウンを開始しない
    assert saved["hosts"]["nuc"].get("last_reboot_at") in (None, "")
