"""収録済みデモ → Web/VR ビューア用 scene pack への変換。

scene pack の構成（1 エピソード = 1 ディレクトリ）:

- ``scene.glb``    MuJoCo シーンの静的メッシュ（body ノード + geom 子ノード、
                   z-up→y-up の回転を root に焼き込み済み）
- ``tracks.bin``   float32 [n_frames][nbody][7]（pos xyz + quat wxyz。
                   MuJoCo ワールド座標。client 側で root 回転の下に適用）
- ``meta.json``    fps / フレーム数 / body↔node 対応 / 品質情報
- ``front.mp4`` / ``wrist.mp4``  保存観測からのカメラ映像

HDF5（libero_*_demo.hdf5, ``states`` あり）は決定的リプレイ、LeRobot
データセットは action 再生でポーズを抽出する。
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

import numpy as np

from parc.eval.media import write_mp4
from parc.viewer_export.glb import (
    GlbBuilder,
    GlbMesh,
    box_geometry,
    capsule_geometry,
    cylinder_geometry,
    plane_geometry,
    sphere_geometry,
)

FORMAT_VERSION = 1
PACK_GLB = "scene.glb"
PACK_TRACKS = "tracks.bin"
PACK_META = "meta.json"

# MuJoCo z-up → glTF y-up（X 軸まわり -90°）
ROOT_ROT_WXYZ = (0.7071067811865476, -0.7071067811865476, 0.0, 0.0)

DEFAULT_FPS = 20

# 可視とみなす geom グループ（MuJoCo の mjvOption デフォルトに合わせる）
_DEFAULT_VISIBLE_GROUPS = (0, 1, 2)


@dataclass
class ScenePackResult:
    """1 pack のエクスポート結果。"""

    out_dir: Path
    meta: dict[str, Any]


def _slugify(text: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_.-]+", "_", text.strip()).strip("_")
    return s[:80] or "task"


def _visible_geom_groups() -> frozenset[int]:
    """MuJoCo デフォルトの可視 geom グループを実際に問い合わせる。"""
    try:
        import mujoco

        opt = mujoco.MjvOption()
        return frozenset(i for i in range(6) if opt.geomgroup[i])
    except Exception:
        return frozenset(_DEFAULT_VISIBLE_GROUPS)


def _raw_mujoco_model(model: Any) -> Any:
    """robosuite の MjModel ラッパーを素の mujoco.MjModel に戻す。"""
    return getattr(model, "_model", model)


def _body_name(model: Any, body_id: int) -> str:
    try:
        import mujoco

        name = mujoco.mj_id2name(
            _raw_mujoco_model(model), mujoco.mjtObj.mjOBJ_BODY, int(body_id)
        )
        return str(name) if name else f"body_{body_id}"
    except Exception:
        return f"body_{body_id}"


def _geom_name(model: Any, geom_id: int) -> str:
    try:
        import mujoco

        name = mujoco.mj_id2name(
            _raw_mujoco_model(model), mujoco.mjtObj.mjOBJ_GEOM, int(geom_id)
        )
        return str(name) if name else f"geom_{geom_id}"
    except Exception:
        return f"geom_{geom_id}"


def _geom_to_mesh(model: Any, geom_id: int) -> GlbMesh | None:
    """1 geom を GlbMesh に変換。描画不要なら None。"""
    import mujoco

    gtype = int(model.geom_type[geom_id])
    rgba = tuple(float(c) for c in model.geom_rgba[geom_id])
    if rgba[3] <= 0.0:
        return None

    size = model.geom_size[geom_id]
    name = _geom_name(model, geom_id)

    if gtype == int(mujoco.mjtGeom.mjGEOM_MESH):
        mesh_id = int(model.geom_dataid[geom_id])
        if mesh_id < 0:
            return None
        vadr = int(model.mesh_vertadr[mesh_id])
        vnum = int(model.mesh_vertnum[mesh_id])
        fadr = int(model.mesh_faceadr[mesh_id])
        fnum = int(model.mesh_facenum[mesh_id])
        if vnum == 0 or fnum == 0:
            return None
        verts = np.asarray(model.mesh_vert[vadr : vadr + vnum], dtype=np.float32)
        faces = np.asarray(model.mesh_face[fadr : fadr + fnum], dtype=np.uint32)
        scale = np.asarray(model.mesh_scale[mesh_id], dtype=np.float32).reshape(3)
        if np.any(np.abs(scale - 1.0) > 1e-9):
            verts = verts * scale[None, :]
        from parc.viewer_export.glb import compute_smooth_normals

        normals = compute_smooth_normals(verts, faces)
        return GlbMesh(name=name, vertices=verts, normals=normals, indices=faces, rgba=rgba)

    if gtype == int(mujoco.mjtGeom.mjGEOM_BOX):
        v, n, f = box_geometry(size)
    elif gtype == int(mujoco.mjtGeom.mjGEOM_SPHERE):
        v, n, f = sphere_geometry(float(size[0]))
    elif gtype == int(mujoco.mjtGeom.mjGEOM_CYLINDER):
        v, n, f = cylinder_geometry(float(size[0]), float(size[1]))
    elif gtype == int(mujoco.mjtGeom.mjGEOM_CAPSULE):
        v, n, f = capsule_geometry(float(size[0]), float(size[1]))
    elif gtype == int(mujoco.mjtGeom.mjGEOM_PLANE):
        v, n, f = plane_geometry(float(size[0]) or 1.0, float(size[1]) or float(size[0]) or 1.0)
    else:
        # hfield などはスキップ
        return None
    return GlbMesh(name=name, vertices=v, normals=n, indices=f, rgba=rgba)


def build_scene_glb(
    model: Any,
    frame0_poses: np.ndarray | None = None,
    *,
    visible_groups: frozenset[int] | None = None,
) -> tuple[bytes, list[int]]:
    """MuJoCo model から GLB を組み立てる。

    戻り値: (glb_bytes, body_id→node_index のリスト。world=0 は -1)
    """
    groups = visible_groups if visible_groups is not None else _visible_geom_groups()
    builder = GlbBuilder()

    nbody = int(model.nbody)
    if frame0_poses is None:
        frame0_poses = np.zeros((nbody, 7), dtype=np.float64)
        frame0_poses[:, 3] = 1.0

    root = builder.add_node("parc_root", rotation_wxyz=ROOT_ROT_WXYZ)

    body_nodes: list[int] = [-1] * nbody
    for b in range(1, nbody):
        pose = frame0_poses[b]
        body_nodes[b] = builder.add_node(
            f"body_{b:03d}_{_body_name(model, b)}",
            translation=tuple(float(v) for v in pose[:3]),
            rotation_wxyz=tuple(float(v) for v in pose[3:7]),
        )
        builder.add_child(root, body_nodes[b])

    # geom は body ノード（world は root 直下）に静的ローカル変換でぶら下げる
    for g in range(int(model.ngeom)):
        group = int(model.geom_group[g])
        if group not in groups:
            continue
        mesh = _geom_to_mesh(model, g)
        if mesh is None:
            continue
        mesh_idx = builder.add_mesh(mesh)
        body_id = int(model.geom_bodyid[g])
        parent = body_nodes[body_id] if body_id > 0 else root
        gpos = tuple(float(v) for v in model.geom_pos[g])
        gquat = tuple(float(v) for v in model.geom_quat[g])
        node = builder.add_node(
            f"geom_{g:03d}_{_geom_name(model, g)}",
            mesh=mesh_idx,
            translation=gpos,
            rotation_wxyz=gquat,
        )
        builder.add_child(parent, node)

    return builder.to_glb(), body_nodes


def capture_body_poses(data: Any) -> np.ndarray:
    """MjData から全 body のワールド pose (nbody, 7) を拾う。"""
    poses = np.zeros((int(data.xpos.shape[0]), 7), dtype=np.float32)
    poses[:, :3] = data.xpos
    poses[:, 3:] = data.xquat
    return poses


def extract_poses_from_states(
    model: Any,
    data: Any,
    states: Sequence[Sequence[float]],
    *,
    set_state: Callable[[np.ndarray], None] | None = None,
    forward: Callable[[], None] | None = None,
) -> np.ndarray:
    """フレーム毎に状態を復元して body pose 列 (T, nbody, 7) を返す。"""
    import mujoco

    if forward is None:
        forward = lambda: mujoco.mj_forward(model, data)  # noqa: E731
    nbody = int(model.nbody)
    out = np.zeros((len(states), nbody, 7), dtype=np.float32)
    for t, state in enumerate(states):
        st = np.asarray(state, dtype=np.float64)
        if set_state is not None:
            set_state(st)
        else:
            mujoco.mj_setState(model, data, st, mujoco.mjtState.mjSTATE_FULLPHYSICS)
        forward()
        out[t] = capture_body_poses(data)
    return out


def _scene_bounds(frame0_poses: np.ndarray) -> dict[str, Any]:
    """初期フレームの body 位置からおおよそのシーン範囲（glTF y-up 座標）。"""
    pts = frame0_poses[:, :3]
    min_b = pts.min(axis=0)
    max_b = pts.max(axis=0)
    center = ((min_b + max_b) / 2.0).astype(float)

    def to_yup(p: np.ndarray) -> list[float]:
        return [float(p[0]), float(p[2]), float(-p[1])]

    return {
        "min": to_yup(min_b),
        "max": to_yup(max_b),
        "center": to_yup(center),
        "radius": float(np.linalg.norm(max_b - min_b) / 2.0),
    }


def _write_pack(
    out_dir: Path,
    *,
    model: Any,
    data: Any,
    states: Sequence[Sequence[float]],
    meta: dict[str, Any],
    set_state: Callable[[np.ndarray], None] | None = None,
    forward: Callable[[], None] | None = None,
    videos: dict[str, Path] | None = None,
    video_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """GLB + tracks.bin + meta.json（と動画コピー）を書く。

    ``videos`` は別場所からのコピー、``video_names`` はすでに out_dir に
    書き込まれている動画ファイル名を指す（HDF5 パスで利用）。
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    poses = extract_poses_from_states(model, data, states, set_state=set_state, forward=forward)
    glb_bytes, body_nodes = build_scene_glb(model, frame0_poses=poses[0])

    (out_dir / PACK_GLB).write_bytes(glb_bytes)
    poses.tofile(out_dir / PACK_TRACKS)

    body_names = [_body_name(model, b) for b in range(int(model.nbody))]
    full_meta = {
        "format_version": FORMAT_VERSION,
        "generated": datetime.now(timezone.utc).isoformat(),
        **meta,
        "n_frames": int(poses.shape[0]),
        "n_bodies": int(poses.shape[1]),
        "bodies": [
            {"id": b, "name": body_names[b], "node": body_nodes[b]}
            for b in range(len(body_nodes))
        ],
        "tracks_layout": "float32 [n_frames][n_bodies][7] (pos xyz + quat wxyz, MuJoCo world frame)",
        "files": {
            "glb": PACK_GLB,
            "tracks": PACK_TRACKS,
            "videos": {},
        },
        "up_axis": "y-up (root rotation baked)",
        "view": _scene_bounds(poses[0]),
    }
    if videos:
        copied: dict[str, str] = {}
        for key, src in videos.items():
            dst = out_dir / f"{key}.mp4"
            if src.is_file() and src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
            copied[key] = dst.name
        full_meta["files"]["videos"] = copied
    if video_names:
        full_meta["files"]["videos"] = dict(video_names)
    (out_dir / PACK_META).write_text(
        json.dumps(full_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return full_meta


# ---- HDF5 ソース ----


def _env_sim(env: Any) -> Any:
    sim = getattr(env, "sim", None)
    if sim is None:
        raise AttributeError("env.sim が取れない（robosuite env では？）")
    return sim


def _resolve_bddl(bddl: str, *, dataset_dir: str = "", task_stem: str = "") -> str:
    """env_args の bddl パスを解決する。

    公開 HDF5 の env_args には収集環境の古い相対パス（例:
    ``chiliocosm/bddl_files/...``）が入っていてそのままでは存在しない。
    実態は「HDF5 ファイル名（= タスク名）と同名の bddl」なので、
    複数の bddl ルートから basename / タスク名で探す。
    """
    p = Path(bddl)
    if p.is_file():
        return str(p)

    from parc.paths import PARC_ROOT

    roots: list[Path] = []
    try:
        from libero.libero import get_libero_path

        roots.append(Path(get_libero_path("bddl_files")))
    except Exception:
        pass
    # メインリポジトリ同梱の bddl 群
    roots.append(PARC_ROOT.parent / "libero" / "libero" / "bddl_files")

    names = [p.name]
    if task_stem:
        names.append(f"{task_stem}.bddl")
    for root in roots:
        for name in names:
            for cand in (root / name, root / dataset_dir / name if dataset_dir else root / name):
                if cand.is_file():
                    return str(cand)
    raise FileNotFoundError(f"bddl not found: {bddl} (searched {roots})")


def export_hdf5_pack(
    hdf5_path: str | Path,
    *,
    demo: str | int = 0,
    out_dir: str | Path,
    include_videos: bool = True,
    max_frames: int | None = None,
    fps: int | None = None,
) -> dict[str, Any]:
    """HDF5 デモ（libero *_demo.hdf5）→ scene pack。"""
    import h5py

    from parc.env.make_env import make_offscreen_env

    hdf5_path = Path(hdf5_path)
    demo_key = demo if isinstance(demo, str) else f"demo_{int(demo)}"

    with h5py.File(hdf5_path, "r") as f:
        grp = f[f"data/{demo_key}"]
        states = np.asarray(grp["states"])
        env_args = json.loads(f["data"].attrs["env_args"])
        problem = json.loads(f["data"].attrs.get("problem_info", "{}")) or {}
        obs_front = np.asarray(grp["obs/agentview_rgb"]) if "obs/agentview_rgb" in grp else None
        obs_wrist = np.asarray(grp["obs/eye_in_hand_rgb"]) if "obs/eye_in_hand_rgb" in grp else None

    stride = 1
    if max_frames is not None and len(states) > max_frames:
        stride = int(np.ceil(len(states) / max_frames))
    states_export = states[::stride]

    bddl = env_args.get("bddl_file_name") or env_args.get("bddl_file")
    if not bddl:
        raise ValueError(f"env_args に bddl_file_name が無い: {sorted(env_args)}")
    # hdf5 名は <task_name>_demo.hdf5
    task_stem = hdf5_path.stem.removesuffix("_demo")
    env = make_offscreen_env(
        _resolve_bddl(bddl, dataset_dir=hdf5_path.parent.name, task_stem=task_stem),
        camera_heights=int(env_args.get("camera_heights", 128) or 128),
        camera_widths=int(env_args.get("camera_widths", 128) or 128),
    )
    try:
        env.reset()
        sim = _env_sim(env)

        def set_state(st: np.ndarray) -> None:
            sim.set_state_from_flattened(st)

        task_name = str(problem.get("task_name") or hdf5_path.stem)
        language = str(problem.get("language") or task_name)
        meta = {
            "source": {"type": "hdf5", "path": str(hdf5_path), "demo": demo_key},
            "dataset": hdf5_path.parent.name,
            "task": task_name,
            "task_slug": _slugify(task_name),
            "language": language,
            "fps": int(fps or DEFAULT_FPS),
            "success": True,  # LIBERO 同梱デモは成功例
            "stride": stride,
        }
        out_dir = Path(out_dir)
        video_names: dict[str, str] | None = None
        if include_videos:
            video_names = {}
            out_dir.mkdir(parents=True, exist_ok=True)
            from parc.vr.obs_util import flip_image_180

            if obs_front is not None:
                frames = [flip_image_180(fr) for fr in obs_front[::stride]]
                p = out_dir / "front.mp4"
                if frames and write_mp4(p, frames, fps=meta["fps"]):
                    video_names["front"] = p.name
            if obs_wrist is not None:
                frames = [flip_image_180(fr) for fr in obs_wrist[::stride]]
                p = out_dir / "wrist.mp4"
                if frames and write_mp4(p, frames, fps=meta["fps"]):
                    video_names["wrist"] = p.name
            if not video_names:
                video_names = None

        return _write_pack(
            out_dir,
            model=sim.model,
            data=sim.data,
            states=states_export,
            meta=meta,
            set_state=set_state,
            forward=sim.forward,
            video_names=video_names,
        )
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()


# ---- LeRobot ソース ----


def _find_lerobot_episode_videos(root: Path, episode_index: int) -> dict[str, Path]:
    """LeRobot v3 videos/chunk-XXX/episode_XXXXXX/<key>.mp4 を探す。"""
    out: dict[str, Path] = {}
    for pattern in (
        f"videos/**/episode_{episode_index:06d}/*.mp4",
        f"videos/**/*episode_{episode_index:06d}*.mp4",
    ):
        for p in sorted(root.glob(pattern)):
            stem = p.stem.lower()
            if stem.endswith("front") or "front" in stem:
                out.setdefault("front", p)
            elif stem.endswith("wrist") or "wrist" in stem or "hand" in stem:
                out.setdefault("wrist", p)
        if out:
            break
    return out


def export_lerobot_pack(
    root: str | Path,
    *,
    episode_index: int,
    out_dir: str | Path,
    include_videos: bool = True,
) -> dict[str, Any]:
    """LeRobot データセット（VR テレオプ収集）→ action 再生で scene pack。"""
    from parc.data.replay_demos import (
        load_episode_actions_from_lerobot,
        load_quality_rows,
    )
    from parc.vr.env_factory import make_teleop_env

    root = Path(root)
    rows = load_quality_rows(root)
    row = next((r for r in rows if r.get("episode_index") == episode_index), None)
    if row is None:
        raise KeyError(f"episode_index={episode_index} not in quality jsonl")

    suite = str(row.get("suite", "libero_spatial"))
    task_id = int(row.get("task_id", 0))
    init_idx = int(row.get("init_state_index", 0))
    language = str(row.get("language") or row.get("task") or f"{suite}:{task_id}")

    actions = load_episode_actions_from_lerobot(root, episode_index)
    bundle = make_teleop_env(suite, task_id)
    try:
        bundle.apply_init_state(init_idx)
        env = bundle.env
        sim = _env_sim(env)

        # 初期フレーム + 各 step 後
        states: list[np.ndarray] = [np.asarray(sim.get_state().flatten(), dtype=np.float64)]
        for act in actions:
            env.step(np.asarray(act, dtype=np.float64).tolist())
            states.append(np.asarray(sim.get_state().flatten(), dtype=np.float64))

        def set_state(st: np.ndarray) -> None:
            sim.set_state_from_flattened(st)

        meta = {
            "source": {"type": "lerobot", "path": str(root), "episode_index": episode_index},
            "dataset": root.name,
            "task": language[:80],
            "task_slug": _slugify(language)[:60] or f"ep_{episode_index:04d}",
            "language": language,
            "episode_index": episode_index,
            "suite": suite,
            "task_id": task_id,
            "init_state_index": init_idx,
            "fps": int(row.get("fps", DEFAULT_FPS)),
            "success": bool(row.get("success", True)),
            "replay_success": row.get("replay_success"),
        }
        videos = _find_lerobot_episode_videos(root, episode_index) if include_videos else None
        return _write_pack(
            Path(out_dir),
            model=sim.model,
            data=sim.data,
            states=states,
            meta=meta,
            set_state=set_state,
            forward=sim.forward,
            videos=videos,
        )
    finally:
        close = getattr(bundle.env, "close", None)
        if callable(close):
            close()


# ---- 汎用ユーティリティ（raw mujoco 向け・テスト/拡張用） ----


def export_pack_from_raw_mujoco(
    model: Any,
    data: Any,
    states: Sequence[Sequence[float]],
    out_dir: str | Path,
    meta: dict[str, Any],
) -> dict[str, Any]:
    """robosuite を介さず MjModel/MjData から直接 pack を書く（テスト用）。"""
    return _write_pack(Path(out_dir), model=model, data=data, states=states, meta=meta)


def iter_hdf5_demos(hdf5_path: str | Path) -> Iterator[str]:
    """HDF5 内の demo キー一覧。"""
    import h5py

    with h5py.File(hdf5_path, "r") as f:
        for key in sorted(f["data"].keys(), key=_demo_sort_key):
            yield key


def _demo_sort_key(key: str) -> tuple[int, str]:
    m = re.search(r"(\d+)", key)
    return (int(m.group(1)) if m else 0, key)
