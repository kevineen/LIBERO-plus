"""VR 品質ゲート（成功拒否・多様化・verify）の単体テスト。"""

from __future__ import annotations

import json
from pathlib import Path

from parc.data.verify_demos import verify_demo_dataset
from parc.env.success import is_libero_success
from parc.vr.protocol import Buttons, ControlMessage, Pose
from parc.vr.recorder import COLLECTION_STATS_NAME, QUALITY_JSONL_NAME
from parc.vr.session import FakeLiberoEnv, TeleopSession, TeleopSessionConfig, run_fake_episode


def test_is_libero_success_or_logic() -> None:
    assert is_libero_success(1.0, False, {}) is True
    assert is_libero_success(0.0, True, {}) is True
    assert is_libero_success(0.0, False, {"success": True}) is True
    assert is_libero_success(0.0, False, {}) is False

    class _Env:
        def check_success(self) -> bool:
            return True

    assert is_libero_success(0.0, False, {}, _Env()) is True


def test_save_refused_when_not_successful(tmp_path: Path) -> None:
    sent: list[str | bytes] = []
    session = TeleopSession(
        env=FakeLiberoEnv(height=32, width=32, success_after=None),
        config=TeleopSessionConfig(
            dataset_root=tmp_path,
            create_dataset=False,
            image_size=(32, 32),
            require_success=True,
        ),
        send=sent.append,
        init_states=[0, 1, 2],
    )
    session.handle_control(
        ControlMessage(t=0.0, pose=Pose(), gripper=0.0, buttons=Buttons(record=True))
    )
    session.handle_control(
        ControlMessage(t=0.1, pose=Pose(pos=(0.01, 0.0, 0.0)), gripper=0.0, buttons=Buttons())
    )
    session.handle_control(
        ControlMessage(t=0.2, pose=Pose(), gripper=0.0, buttons=Buttons(save=True))
    )

    assert not any(isinstance(x, str) and '"episode_saved"' in x for x in sent)
    statuses = [
        json.loads(x) for x in sent if isinstance(x, str) and '"status"' in x
    ]
    assert any("save refused" in s.get("message", "") for s in statuses)
    assert not (tmp_path / "meta" / QUALITY_JSONL_NAME).is_file()
    assert session.recorder is not None
    assert session.recorder.stats.refused == 1
    assert session.recorder.stats.saved == 0
    # バッファは残る
    assert session.recording is True
    assert session.recorder.buffer.num_frames >= 1
    session.close()


def test_init_state_cycles_on_reset(tmp_path: Path) -> None:
    sent: list[str | bytes] = []
    session = TeleopSession(
        env=FakeLiberoEnv(height=16, width=16, success_after=None, n_init_states=3),
        config=TeleopSessionConfig(
            dataset_root=tmp_path,
            create_dataset=False,
            image_size=(16, 16),
            require_success=False,
            init_state_mode="cycle",
        ),
        send=sent.append,
        init_states=[0, 1, 2],
    )
    assert session._init_state_index == 0

    def pulse_reset(t: float) -> None:
        session.handle_control(
            ControlMessage(t=t, pose=Pose(), gripper=0.0, buttons=Buttons(reset=True))
        )
        session.handle_control(
            ControlMessage(t=t + 0.01, pose=Pose(), gripper=0.0, buttons=Buttons())
        )

    pulse_reset(0.0)
    assert session._init_state_index == 1
    pulse_reset(0.1)
    assert session._init_state_index == 2
    pulse_reset(0.2)
    assert session._init_state_index == 0
    session.close()


def test_successful_save_writes_quality_and_stats(tmp_path: Path) -> None:
    n = run_fake_episode(
        dataset_root=tmp_path,
        num_frames=6,
        create_dataset=False,
        image_size=(32, 32),
        require_success=True,
        success_after=1,
    )
    assert n == 1
    quality_path = tmp_path / "meta" / QUALITY_JSONL_NAME
    stats_path = tmp_path / "meta" / COLLECTION_STATS_NAME
    assert quality_path.is_file()
    assert stats_path.is_file()
    assert (tmp_path / "meta" / "collection_info.json").is_file()
    assert (tmp_path / "meta" / "episode_timestamps.jsonl").is_file()

    row = json.loads(quality_path.read_text(encoding="utf-8").strip().splitlines()[0])
    assert row["success"] is True
    assert row["num_frames"] >= 1
    assert "init_state_index" in row
    assert row.get("fps") == 20
    assert row.get("sync_policy") == "approximate_time"

    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    assert stats["saved"] == 1
    assert "saved_per_hour" in stats

    summary = verify_demo_dataset(tmp_path, require_success=False)
    assert summary["ok"] is True
    assert summary["n_quality_rows"] == 1


def test_failed_episode_can_be_saved(tmp_path: Path) -> None:
    n = run_fake_episode(
        dataset_root=tmp_path,
        num_frames=4,
        create_dataset=False,
        image_size=(32, 32),
        require_success=False,
        success_after=None,
    )
    assert n == 1
    row = json.loads(
        (tmp_path / "meta" / QUALITY_JSONL_NAME).read_text(encoding="utf-8").strip().splitlines()[0]
    )
    assert row["success"] is False
    summary = verify_demo_dataset(tmp_path, require_success=False)
    assert summary["n_failed"] == 1


def test_verify_fails_on_unsuccessful_row_when_required(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    meta.mkdir(parents=True)
    from parc.vr.collection_meta import build_collection_info, write_collection_info

    write_collection_info(tmp_path, build_collection_info(fps=20, image_size=(32, 32)))
    (meta / QUALITY_JSONL_NAME).write_text(
        json.dumps(
            {
                "episode_index": 0,
                "suite": "libero_spatial",
                "task_id": 0,
                "init_state_index": 0,
                "language": "x",
                "success": False,
                "num_frames": 3,
                "fps": 20,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        verify_demo_dataset(tmp_path, require_success=True)
        raised = False
    except ValueError:
        raised = True
    assert raised is True


def test_task_ids_round_robin_remake(tmp_path: Path) -> None:
    """init が一巡したら task_ids を進めて remake_env する。"""
    sent: list[str | bytes] = []
    remakes: list[int] = []

    def remake(suite: str, task_id: int):
        from parc.vr.env_factory import TeleopEnvBundle

        remakes.append(task_id)
        env = FakeLiberoEnv(height=16, width=16, success_after=None, n_init_states=2)
        return TeleopEnvBundle(
            env=env,
            language=f"task-{task_id}",
            suite=suite,
            task_id=task_id,
            init_states=[0, 1],
        )

    session = TeleopSession(
        env=FakeLiberoEnv(height=16, width=16, success_after=None, n_init_states=2),
        config=TeleopSessionConfig(
            suite="libero_spatial",
            task_id=0,
            task_ids=[0, 1],
            dataset_root=tmp_path,
            create_dataset=False,
            image_size=(16, 16),
            require_success=False,
            init_state_mode="cycle",
        ),
        send=sent.append,
        init_states=[0, 1],
        remake_env=remake,
    )
    # init 0 -> 1
    session.handle_control(
        ControlMessage(t=0.0, pose=Pose(), gripper=0.0, buttons=Buttons(reset=True))
    )
    session.handle_control(
        ControlMessage(t=0.05, pose=Pose(), gripper=0.0, buttons=Buttons())
    )
    assert session._init_state_index == 1
    assert session.config.task_id == 0
    # wrap to 0 and switch task
    session.handle_control(
        ControlMessage(t=0.1, pose=Pose(), gripper=0.0, buttons=Buttons(reset=True))
    )
    session.handle_control(
        ControlMessage(t=0.15, pose=Pose(), gripper=0.0, buttons=Buttons())
    )
    assert session.config.task_id == 1
    assert session._init_state_index == 0
    assert remakes == [1]
    session.close()
