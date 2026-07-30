"""parc-filter-demos の単体テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parc.data.filter_demos import (
    filter_demo_dataset,
    remap_sidecars,
    select_episode_indices,
)
from parc.vr.recorder import QUALITY_JSONL_NAME, TIMESTAMPS_JSONL_NAME


def _write_sidecar_dataset(root: Path) -> None:
    """LeRobot 無しのサイドカーのみ DS を作る。"""
    meta = root / "meta"
    meta.mkdir(parents=True)
    rows = [
        {"episode_index": 0, "success": True, "suite": "libero_spatial", "task_id": 0, "init_state_index": 0, "language": "a", "num_frames": 2, "fps": 20},
        {"episode_index": 1, "success": False, "suite": "libero_spatial", "task_id": 0, "init_state_index": 1, "language": "b", "num_frames": 2, "fps": 20},
        {"episode_index": 2, "success": True, "degraded": True, "suite": "libero_spatial", "task_id": 0, "init_state_index": 2, "language": "c", "num_frames": 2, "fps": 20},
        {"episode_index": 3, "success": True, "suite": "libero_spatial", "task_id": 0, "init_state_index": 0, "language": "d", "num_frames": 2, "fps": 20},
    ]
    (meta / QUALITY_JSONL_NAME).write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    ts_rows = [
        {"episode_index": i, "timestamps": [0.0, 0.05], "control_timestamps": [0.0, 0.05]}
        for i in range(4)
    ]
    (meta / TIMESTAMPS_JSONL_NAME).write_text(
        "\n".join(json.dumps(r) for r in ts_rows) + "\n", encoding="utf-8"
    )
    (meta / "collection_info.json").write_text(
        json.dumps({"cameras": {}, "frames": {}, "collection": {}, "fps": 20}) + "\n",
        encoding="utf-8",
    )


def test_select_episode_indices_success_and_degraded() -> None:
    rows = [
        {"episode_index": 0, "success": True},
        {"episode_index": 1, "success": False},
        {"episode_index": 2, "success": True, "degraded": True},
    ]
    assert select_episode_indices(rows, success_only=True) == [0, 2]
    assert select_episode_indices(rows, success_only=True, exclude_degraded=True) == [0]


def test_remap_sidecars_rewrites_indices(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_sidecar_dataset(src)
    remap_sidecars(src, dst, [0, 3])
    q = [
        json.loads(ln)
        for ln in (dst / "meta" / QUALITY_JSONL_NAME).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert [r["episode_index"] for r in q] == [0, 1]
    assert [r["source_episode_index"] for r in q] == [0, 3]
    assert all(r["success"] is True for r in q)


def test_filter_demo_dataset_sidecar_only(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_sidecar_dataset(src)
    result = filter_demo_dataset(src, dst, success_only=True, exclude_degraded=True)
    assert result.n_kept == 2
    assert result.episode_indices == [0, 3]
    q = [
        json.loads(ln)
        for ln in (dst / "meta" / QUALITY_JSONL_NAME).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert len(q) == 2
    assert (dst / "filter_manifest.json").is_file()


def test_filter_demo_dataset_dry_run(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_sidecar_dataset(src)
    result = filter_demo_dataset(src, dst, dry_run=True)
    assert result.n_kept == 3
    assert not dst.exists()


def test_filter_with_lerobot_split(tmp_path: Path) -> None:
    pytest.importorskip("lerobot")
    from parc.vr.session import run_fake_episode

    src = tmp_path / "lerobot_src"
    # 成功 1 + 失敗 1
    run_fake_episode(
        dataset_root=src,
        num_frames=3,
        create_dataset=True,
        image_size=(32, 32),
        require_success=False,
        success_after=1,
    )
    # 2nd ep: fail
    from parc.vr.session import FakeLiberoEnv, TeleopSession, TeleopSessionConfig
    from parc.vr.protocol import Buttons, ControlMessage, Pose

    sent: list[str | bytes] = []
    session = TeleopSession(
        env=FakeLiberoEnv(height=32, width=32, success_after=None),
        config=TeleopSessionConfig(
            dataset_root=src,
            create_dataset=True,
            image_size=(32, 32),
            require_success=False,
            repo_id="local/vr_libero_demos",
        ),
        send=sent.append,
        init_states=[0, 1, 2],
    )
    session.handle_control(
        ControlMessage(t=0.0, pose=Pose(), gripper=0.0, buttons=Buttons(record=True))
    )
    for i in range(3):
        session.handle_control(
            ControlMessage(
                t=0.05 * (i + 1),
                pose=Pose(pos=(0.01, 0.0, 0.0)),
                gripper=0.0,
                buttons=Buttons(),
            )
        )
    session.handle_control(
        ControlMessage(t=0.2, pose=Pose(), gripper=0.0, buttons=Buttons(save=True))
    )
    session.close()

    dst = tmp_path / "lerobot_success"
    result = filter_demo_dataset(src, dst, success_only=True, overwrite=True)
    assert result.n_kept >= 1
    assert (dst / "meta" / "info.json").is_file()
    q = [
        json.loads(ln)
        for ln in (dst / "meta" / QUALITY_JSONL_NAME).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert all(r.get("success") is True for r in q)
