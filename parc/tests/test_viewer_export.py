"""parc-export-viewer（scene pack エクスポート）の単体テスト。

robosuite env は使わず、素の mujoco モデルで GLB/tracks/index を検証する。
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

from parc.viewer_export.build_index import build_index  # noqa: E402
from parc.viewer_export.glb import (  # noqa: E402
    GlbBuilder,
    GlbMesh,
    box_geometry,
    capsule_geometry,
    cylinder_geometry,
    plane_geometry,
    sphere_geometry,
)
from parc.viewer_export.scene_pack import (  # noqa: E402
    PACK_GLB,
    PACK_META,
    PACK_TRACKS,
    build_scene_glb,
    export_pack_from_raw_mujoco,
)

_XML = """
<mujoco>
  <worldbody>
    <geom name="floor" type="plane" size="2 2 0.1" rgba="0.9 0.9 0.9 1" group="0"/>
    <body name="base" pos="0 0 0.1">
      <geom name="box_geom" type="box" size="0.1 0.1 0.1" rgba="1 0 0 1" group="0"/>
      <body name="child" pos="0.2 0 0">
        <joint name="hinge" type="hinge" axis="0 1 0" range="-1 1"/>
        <geom name="ball" type="sphere" size="0.05" rgba="0 1 0 1" group="0"/>
      </body>
    </body>
    <body name="free_obj" pos="0.5 0.3 0.2">
      <freejoint/>
      <geom name="capsule_geom" type="capsule" size="0.03 0.08" rgba="0 0 1 1" group="1"/>
    </body>
    <body name="hidden" pos="1 1 1">
      <geom name="collision_only" type="box" size="0.1 0.1 0.1" rgba="1 1 0 1" group="4"/>
    </body>
  </worldbody>
</mujoco>
"""


def _make_model_data() -> tuple[object, object]:
    model = mujoco.MjModel.from_xml_string(_XML)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


def _frame_states(n: int = 3) -> list[np.ndarray]:
    """qpos を少しずつ変えたフル状態列。"""
    import mujoco

    model, data = _make_model_data()
    states = []
    for t in range(n):
        data.qpos[:] = model.qpos0
        # joint 0 = hinge（child body）、joint 1 = freejoint（free_obj）
        hinge_qadr = model.jnt_qposadr[0]
        free_qadr = model.jnt_qposadr[1]
        data.qpos[hinge_qadr] = 0.1 * t
        data.qpos[free_qadr + 2] = 0.2 + 0.05 * t
        mujoco.mj_forward(model, data)
        buf = np.zeros(mujoco.mj_stateSize(model, mujoco.mjtState.mjSTATE_FULLPHYSICS))
        mujoco.mj_getState(model, data, buf, mujoco.mjtState.mjSTATE_FULLPHYSICS)
        states.append(buf.copy())
    return states


# ---- glb.py primitives ----


def test_primitive_geometries_valid() -> None:
    for gen, args in (
        (box_geometry, (np.array([0.1, 0.2, 0.3]),)),
        (sphere_geometry, (0.5,)),
        (cylinder_geometry, (0.2, 0.5)),
        (capsule_geometry, (0.1, 0.4)),
        (plane_geometry, (1.0, 2.0)),
    ):
        verts, normals, faces = gen(*args)
        assert verts.ndim == 2 and verts.shape[1] == 3
        assert normals.shape == verts.shape
        assert faces.ndim == 2 and faces.shape[1] == 3
        assert faces.max() < len(verts)
        # 法線は正規化済み
        lens = np.linalg.norm(normals, axis=1)
        assert np.allclose(lens, 1.0, atol=1e-5)


def test_glb_container_structure() -> None:
    builder = GlbBuilder()
    root = builder.add_node("root")
    v, n, f = box_geometry(np.array([0.5, 0.5, 0.5]))
    mesh_idx = builder.add_mesh(GlbMesh(name="cube", vertices=v, normals=n, indices=f, rgba=(1, 0, 0, 1)))
    child = builder.add_node("cube_node", mesh=mesh_idx, translation=(1.0, 2.0, 3.0))
    builder.add_child(root, child)
    blob = builder.to_glb()

    magic, version, total = struct.unpack_from("<III", blob, 0)
    assert magic == 0x46546C67
    assert version == 2
    assert total == len(blob)
    assert len(blob) % 4 == 0

    json_len, json_type = struct.unpack_from("<II", blob, 12)
    assert json_type == 0x4E4F534A
    doc = json.loads(blob[20 : 20 + json_len].decode("utf-8"))
    assert doc["asset"]["version"] == "2.0"
    assert len(doc["nodes"]) == 2
    assert doc["nodes"][0]["children"] == [1]
    assert doc["nodes"][1]["mesh"] == 0
    assert doc["nodes"][1]["translation"] == [1.0, 2.0, 3.0]
    bin_off = 20 + json_len
    bin_len, bin_type = struct.unpack_from("<II", blob, bin_off)
    assert bin_type == 0x004E4942
    assert bin_len > 0
    assert doc["buffers"][0]["byteLength"] == bin_len


# ---- scene pack ----


def test_build_scene_glb_filters_and_maps_bodies() -> None:
    model, data = _make_model_data()
    blob, body_nodes = build_scene_glb(model, frame0_poses=None)
    assert len(blob) > 0
    # world(body 0) は root 直下のため -1、それ以外は node が降る
    assert body_nodes[0] == -1
    assert all(n > 0 for n in body_nodes[1:])

    json_len = struct.unpack_from("<I", blob, 12)[0]
    doc = json.loads(blob[20 : 20 + json_len].decode("utf-8"))
    geom_names = [n["name"] for n in doc["nodes"] if n["name"].startswith("geom_")]
    # group=4 の collision_only は除外、alpha=0 も無し
    assert any("floor" in g for g in geom_names)
    assert any("box_geom" in g for g in geom_names)
    assert not any("collision_only" in g for g in geom_names)
    # root は z-up→y-up 補正を持つ
    root = doc["nodes"][0]
    rot = root["rotation"]
    assert abs(rot[0] + 0.70710678) < 1e-5
    assert abs(rot[3] - 0.70710678) < 1e-5


def test_export_pack_round_trip(tmp_path: Path) -> None:
    model, data = _make_model_data()
    states = _frame_states(3)
    meta = export_pack_from_raw_mujoco(
        model,
        data,
        states,
        tmp_path,
        meta={"dataset": "test", "task": "test task", "language": "lang", "fps": 20},
    )

    assert (tmp_path / PACK_GLB).is_file()
    assert (tmp_path / PACK_TRACKS).is_file()
    meta_disk = json.loads((tmp_path / PACK_META).read_text(encoding="utf-8"))
    assert meta_disk["n_frames"] == 3
    assert meta_disk["n_bodies"] == int(model.nbody)
    assert meta_disk["fps"] == 20

    tracks = np.fromfile(tmp_path / PACK_TRACKS, dtype=np.float32).reshape(3, model.nbody, 7)
    # クォータニオンは正規化されている
    quats = tracks[:, 1:, 3:]
    assert np.allclose(np.linalg.norm(quats, axis=-1), 1.0, atol=1e-4)
    # free_obj（最後の body）は z が上昇するトラック
    free_b = [i for i, b in enumerate(meta_disk["bodies"]) if b["name"] == "free_obj"][0]
    assert tracks[2, free_b, 2] > tracks[0, free_b, 2]
    # hinge の回転が child body の向きに反映されている（qpos>0 → quat 変化）
    child_b = [i for i, b in enumerate(meta_disk["bodies"]) if b["name"] == "child"][0]
    assert not np.allclose(tracks[0, child_b, 3:], tracks[2, child_b, 3:])


def test_build_index(tmp_path: Path) -> None:
    model, data = _make_model_data()
    states = _frame_states(2)
    pack_dir = tmp_path / "ds_a" / "task_a" / "ep_000"
    export_pack_from_raw_mujoco(
        model,
        data,
        states,
        pack_dir,
        meta={"dataset": "ds_a", "task": "task_a", "language": "lang", "fps": 20, "success": True},
    )
    index = build_index(tmp_path)
    assert index["n_episodes"] == 1
    ep = index["episodes"][0]
    assert ep["dataset"] == "ds_a"
    assert ep["n_frames"] == 2
    assert ep["success"] is True
    assert ep["files"]["glb"] == "ds_a/task_a/ep_000/scene.glb"
    assert (tmp_path / "index.json").is_file()
