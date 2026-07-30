"""LeRobot Dataset v3.0 への実書き込みスモーク。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parc.vr.session import run_fake_episode


def test_lerobot_v3_create_write_finalize(tmp_path: Path) -> None:
    pytest.importorskip("lerobot")

    root = tmp_path / "v3_ds"
    n = run_fake_episode(
        dataset_root=root,
        num_frames=4,
        create_dataset=True,
        image_size=(32, 32),
        require_success=False,
        success_after=1,
    )
    assert n == 1

    info = json.loads((root / "meta" / "info.json").read_text(encoding="utf-8"))
    assert str(info.get("codebase_version", "")).startswith("v3")
    assert "timestamp" in info.get("features", {})
    assert "observation.images.front" in info.get("features", {})
    assert (root / "meta" / "collection_info.json").is_file()
    assert (root / "meta" / "episode_quality.jsonl").is_file()
    assert (root / "meta" / "episode_timestamps.jsonl").is_file()
    # v3 layout: data/ and/or videos/ shards
    assert (root / "data").exists() or (root / "videos").exists() or (root / "meta" / "episodes").exists()
