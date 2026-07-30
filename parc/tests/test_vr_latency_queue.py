"""RTT / Approximate Time / 収集キューの品質ゲートテスト。"""

from __future__ import annotations

import json
from pathlib import Path

from parc.vr.protocol import Buttons, ControlMessage, Pose
from parc.vr.recorder import COLLECTION_STATS_NAME, QUALITY_JSONL_NAME
from parc.vr.session import FakeLiberoEnv, TeleopSession, TeleopSessionConfig


def _record_and_save(
    session: TeleopSession,
    *,
    frames: int = 3,
    t0: float = 1.0,
) -> None:
    """record → frames → save。"""
    session.handle_control(
        ControlMessage(t=t0, pose=Pose(), gripper=0.0, buttons=Buttons(record=True))
    )
    for i in range(frames):
        session.handle_control(
            ControlMessage(
                t=t0 + 0.05 * (i + 1),
                pose=Pose(pos=(0.01, 0.0, 0.0)),
                gripper=0.0,
                buttons=Buttons(),
            )
        )
    session.handle_control(
        ControlMessage(
            t=t0 + 0.05 * (frames + 1),
            pose=Pose(),
            gripper=0.0,
            buttons=Buttons(save=True),
        )
    )


def test_rtt_degraded_on_high_latency(tmp_path: Path) -> None:
    sent: list[str | bytes] = []
    session = TeleopSession(
        env=FakeLiberoEnv(height=16, width=16, success_after=1),
        config=TeleopSessionConfig(
            dataset_root=tmp_path,
            create_dataset=False,
            image_size=(16, 16),
            max_rtt_ms=50.0,
            latency_policy="degraded",
            approx_time_slop_ms=10_000.0,  # 合成時刻でも stale にしない
        ),
        send=sent.append,
        init_states=[0, 1, 2],
    )
    session.record_rtt(10.0)
    session.record_rtt(200.0)
    session.record_rtt(220.0)
    _record_and_save(session)
    rows = [
        json.loads(ln)
        for ln in (tmp_path / "meta" / QUALITY_JSONL_NAME).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert rows[0]["degraded"] is True
    assert rows[0]["rtt_ms_p95"] >= 200.0
    assert "rtt_ms_mean" in rows[0]
    assert session.recorder is not None
    assert session.recorder.stats.degraded == 1
    session.close()


def test_rtt_refuse_policy(tmp_path: Path) -> None:
    sent: list[str | bytes] = []
    session = TeleopSession(
        env=FakeLiberoEnv(height=16, width=16, success_after=1),
        config=TeleopSessionConfig(
            dataset_root=tmp_path,
            create_dataset=False,
            image_size=(16, 16),
            max_rtt_ms=50.0,
            latency_policy="refuse",
            approx_time_slop_ms=10_000.0,
        ),
        send=sent.append,
        init_states=[0],
    )
    session.record_rtt(300.0)
    _record_and_save(session)
    assert not (tmp_path / "meta" / QUALITY_JSONL_NAME).is_file()
    assert session.recorder is not None
    assert session.recorder.stats.refused_latency == 1
    statuses = [json.loads(x) for x in sent if isinstance(x, str) and '"status"' in x]
    assert any("save refused: latency" in s.get("message", "") for s in statuses)
    session.close()


def test_approx_time_drops_stale_and_duplicate(tmp_path: Path) -> None:
    sent: list[str | bytes] = []
    session = TeleopSession(
        env=FakeLiberoEnv(height=16, width=16, success_after=None),
        config=TeleopSessionConfig(
            dataset_root=tmp_path,
            create_dataset=False,
            image_size=(16, 16),
            max_rtt_ms=0.0,
            approx_time_slop_ms=50.0,
        ),
        send=sent.append,
        init_states=[0],
    )
    session.handle_control(
        ControlMessage(t=10.0, pose=Pose(), gripper=0.0, buttons=Buttons(record=True))
    )
    # 受理
    session.handle_control(
        ControlMessage(t=10.05, pose=Pose(pos=(0.01, 0.0, 0.0)), gripper=0.0, buttons=Buttons())
    )
    # 重複
    session.handle_control(
        ControlMessage(t=10.05, pose=Pose(pos=(0.02, 0.0, 0.0)), gripper=0.0, buttons=Buttons())
    )
    # 古い
    session.handle_control(
        ControlMessage(t=10.01, pose=Pose(pos=(0.03, 0.0, 0.0)), gripper=0.0, buttons=Buttons())
    )
    # 受理
    session.handle_control(
        ControlMessage(t=10.10, pose=Pose(pos=(0.04, 0.0, 0.0)), gripper=0.0, buttons=Buttons())
    )
    assert session.recorder is not None
    # record メッセージ自体も 1 frame になり得る + 受理 2
    assert session._dropped_stale_controls >= 2
    assert session.recorder.stats.dropped_stale_controls >= 2
    session.handle_control(
        ControlMessage(t=10.15, pose=Pose(), gripper=0.0, buttons=Buttons(save=True))
    )
    rows = [
        json.loads(ln)
        for ln in (tmp_path / "meta" / QUALITY_JSONL_NAME).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert rows[0]["dropped_stale_controls"] >= 2
    session.close()


def test_collection_queue_advances_on_success(tmp_path: Path) -> None:
    sent: list[str | bytes] = []
    queue = [
        {
            "suite": "libero_spatial",
            "task_id": 0,
            "init_state_index": 0,
            "category": "baseline",
            "perturbation": "none",
        },
        {
            "suite": "libero_spatial",
            "task_id": 0,
            "init_state_index": 1,
            "category": "init_shift",
            "perturbation": "init_state",
        },
    ]
    session = TeleopSession(
        env=FakeLiberoEnv(height=16, width=16, success_after=1, n_init_states=3),
        config=TeleopSessionConfig(
            dataset_root=tmp_path,
            create_dataset=False,
            image_size=(16, 16),
            max_rtt_ms=0.0,
            approx_time_slop_ms=10_000.0,
            collection_queue=queue,
        ),
        send=sent.append,
        init_states=[0, 1, 2],
    )
    assert session._current_category == "baseline"
    assert session.queue_remaining == 2
    _record_and_save(session, t0=1.0)
    rows = [
        json.loads(ln)
        for ln in (tmp_path / "meta" / QUALITY_JSONL_NAME).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert rows[0]["category"] == "baseline"
    assert rows[0]["perturbation"] == "none"
    assert session.queue_remaining == 1
    assert session._current_category == "init_shift"
    assert session._init_state_index == 1

    # 失敗 Save ではキューを消化しない
    session2_sent: list[str | bytes] = []
    session2 = TeleopSession(
        env=FakeLiberoEnv(height=16, width=16, success_after=None, n_init_states=3),
        config=TeleopSessionConfig(
            dataset_root=tmp_path / "fail",
            create_dataset=False,
            image_size=(16, 16),
            max_rtt_ms=0.0,
            approx_time_slop_ms=10_000.0,
            collection_queue=list(queue),
        ),
        send=session2_sent.append,
        init_states=[0, 1, 2],
    )
    _record_and_save(session2, t0=2.0)
    assert session2.queue_remaining == 2
    session.close()
    session2.close()
