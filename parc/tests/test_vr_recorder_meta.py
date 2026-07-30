"""VR recorder のメタ永続化テスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from parc.vr.session import run_fake_episode


def test_fake_episode_writes_meta_when_dataset_enabled(tmp_path: Path) -> None:
    pytest.importorskip("lerobot")

    written = run_fake_episode(
        dataset_root=tmp_path,
        num_frames=4,
        create_dataset=True,
        image_size=(32, 32),
    )

    assert written == 1
    assert (tmp_path / "meta" / "info.json").is_file()
