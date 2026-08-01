"""関節角 rad/deg 単位ユーティリティのテスト。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from parc.data.angle_units import (
    TARGET_UNIT,
    AngleUnitsMeta,
    assert_joint_dataset_units,
    check_joint_angle_scale,
    convert_angles,
    load_angle_units_meta,
    normalize_joint_frame_arrays,
    write_angle_units_meta,
)
from parc.data.verify_demos import verify_demo_dataset, verify_joint_angle_units
from parc.vr.recorder import QUALITY_JSONL_NAME


def test_convert_radians_to_degrees() -> None:
    out = convert_angles([0.0, np.pi, np.pi / 2], "radians", "degrees")
    np.testing.assert_allclose(out, [0.0, 180.0, 90.0], rtol=1e-6)


def test_convert_same_unit_copies() -> None:
    src = np.array([1.0, 2.0], dtype=np.float64)
    out = convert_angles(src, "degrees", "degrees")
    np.testing.assert_array_equal(out, src)
    assert out is not src


def test_normalize_joint_frame_selected_indices() -> None:
    state = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    action = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    st, act = normalize_joint_frame_arrays(
        state=state,
        action=action,
        source_unit="radians",
        target_unit="degrees",
        joint_indices=[0, 2],
    )
    assert st is not None and act is not None
    np.testing.assert_allclose(st[0], np.rad2deg(1.0), rtol=1e-5)
    np.testing.assert_allclose(st[2], np.rad2deg(3.0), rtol=1e-5)
    assert st[1] == pytest.approx(2.0)
    np.testing.assert_allclose(act[0], np.rad2deg(0.1), rtol=1e-5)
    assert act[1] == pytest.approx(0.2)


def test_write_and_load_angle_units_meta(tmp_path: Path) -> None:
    meta = AngleUnitsMeta(
        control_mode="joint_position",
        source_unit="radians",
        stored_unit="degrees",
        joint_indices=[0, 1, 2],
        action_is_absolute=True,
    )
    write_angle_units_meta(tmp_path, meta)
    loaded = load_angle_units_meta(tmp_path)
    assert loaded is not None
    assert loaded.control_mode == "joint_position"
    assert loaded.source_unit == "radians"
    assert loaded.stored_unit == TARGET_UNIT
    assert loaded.joint_indices == [0, 1, 2]


def test_assert_joint_rejects_stored_radians() -> None:
    meta = AngleUnitsMeta(
        control_mode="joint_position",
        source_unit="radians",
        stored_unit="radians",
    )
    with pytest.raises(ValueError, match="degrees"):
        assert_joint_dataset_units(meta)


def test_scale_check_flags_rad_as_deg() -> None:
    """radians レンジの絶対角を degrees メタのまま → 微動疑い。"""
    meta = AngleUnitsMeta(
        control_mode="joint_position",
        source_unit="radians",
        stored_unit="degrees",
        action_is_absolute=True,
    )
    # ±0.5 rad 相当を deg 変換せずに保存したケース
    actions = np.linspace(-0.5, 0.5, 64).reshape(32, 2)
    errors = check_joint_angle_scale(actions, meta=meta)
    assert errors
    assert any("micro-motion" in e for e in errors)


def test_scale_check_passes_normal_degrees() -> None:
    meta = AngleUnitsMeta(
        control_mode="joint_position",
        source_unit="degrees",
        stored_unit="degrees",
        action_is_absolute=True,
    )
    t = np.linspace(0, 1, 40)
    actions = np.stack([20 * np.sin(t), -15 * np.cos(t)], axis=1)
    errors = check_joint_angle_scale(actions, meta=meta)
    assert errors == []


def test_ee_delta_skips_scale_and_verify(tmp_path: Path) -> None:
    meta = AngleUnitsMeta(control_mode="ee_delta")
    write_angle_units_meta(tmp_path, meta)
    (tmp_path / "meta" / QUALITY_JSONL_NAME).write_text(
        json_line(
            {
                "episode_index": 0,
                "suite": "libero_spatial",
                "task_id": 0,
                "init_state_index": 0,
                "language": "x",
                "success": True,
                "num_frames": 2,
                "fps": 20,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "meta" / "collection_info.json").write_text(
        '{"cameras":{},"frames":{},"collection":{},"fps":20}\n',
        encoding="utf-8",
    )
    summary = verify_joint_angle_units(tmp_path, check_scale=True)
    assert summary["skipped"] is True

    full = verify_demo_dataset(
        tmp_path,
        require_collection_info=True,
        check_joint_angle_units=True,
    )
    assert full["ok"] is True
    assert full["angle_units"]["skipped"] is True


def test_verify_joint_scale_with_passed_actions(tmp_path: Path) -> None:
    write_angle_units_meta(
        tmp_path,
        AngleUnitsMeta(
            control_mode="joint_position",
            source_unit="radians",
            stored_unit="degrees",
            action_is_absolute=True,
        ),
    )
    bad = np.linspace(-0.4, 0.4, 50).reshape(25, 2)
    with pytest.raises(ValueError, match="micro-motion"):
        verify_joint_angle_units(tmp_path, check_scale=True, actions=bad)

    good = np.stack(
        [np.linspace(-30, 30, 25), np.linspace(10, 40, 25)],
        axis=1,
    )
    ok = verify_joint_angle_units(tmp_path, check_scale=True, actions=good)
    assert ok["ok"] is True


def json_line(obj: dict) -> str:
    import json

    return json.dumps(obj) + "\n"
