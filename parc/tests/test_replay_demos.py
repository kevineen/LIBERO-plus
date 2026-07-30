"""parc-replay-demos の単体テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from parc.data.replay_demos import (
    replay_actions_on_env,
    replay_demo_episode,
    update_quality_with_replay,
    write_quality_rows,
)
from parc.data.verify_demos import verify_demo_dataset
from parc.vr.recorder import QUALITY_JSONL_NAME
from parc.vr.session import FakeLiberoEnv


def test_replay_actions_marks_success() -> None:
    env = FakeLiberoEnv(height=8, width=8, success_after=2, n_init_states=2)
    actions = [np.zeros(7, dtype=np.float64) for _ in range(4)]
    result = replay_actions_on_env(env, actions, init_states=[0, 1], init_state_index=0)
    assert result.replay_success is True
    assert result.replay_steps == 4


def test_update_quality_and_verify_require_replay(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    meta.mkdir(parents=True)
    rows = [
        {
            "episode_index": 0,
            "suite": "libero_spatial",
            "task_id": 0,
            "init_state_index": 0,
            "language": "a",
            "success": True,
            "num_frames": 4,
            "fps": 20,
            "category": "baseline",
        }
    ]
    write_quality_rows(tmp_path, rows)
    (meta / "collection_info.json").write_text(
        json.dumps({"cameras": {}, "frames": {}, "collection": {}, "fps": 20}) + "\n",
        encoding="utf-8",
    )

    actions = [np.zeros(7, dtype=np.float64) for _ in range(3)]
    result = replay_demo_episode(
        tmp_path,
        0,
        fake=True,
        actions=actions,
        write=True,
    )
    assert result.replay_success is True
    loaded = [
        json.loads(ln)
        for ln in (tmp_path / "meta" / QUALITY_JSONL_NAME).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert loaded[0]["replay_success"] is True
    assert loaded[0]["replay_steps"] == 3

    summary = verify_demo_dataset(
        tmp_path,
        require_replay_success=True,
        require_collection_info=True,
    )
    assert summary["ok"] is True


def test_update_quality_with_replay_missing_raises() -> None:
    try:
        update_quality_with_replay([], 0, replay_success=True, replay_steps=1)
        raised = False
    except KeyError:
        raised = True
    assert raised
