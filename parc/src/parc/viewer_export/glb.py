"""最小 GLB (binary glTF 2.0) ライタ。外部依存なし。

MuJoCo モデルの可視 geom をブラウザ/VR ビューアへ持っていくための、
必要最小限の writer。メッシュ + 階層ノード + RGBA マテリアルのみ対応
（テクスチャ/スキニング/アニメーションは対象外。ポーズは別トラック
``tracks.bin`` で毎フレーム送る）。
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field

import numpy as np

GLB_MAGIC = 0x46546C67  # "glTF"
CHUNK_JSON = 0x4E4F534A  # "JSON"
CHUNK_BIN = 0x004E4942  # "BIN "

_PAD = b" "
_ZPAD = b"\x00"


def _pad(data: bytes, pad_byte: bytes, size: int = 4) -> bytes:
    rem = len(data) % size
    return data if rem == 0 else data + pad_byte * (size - rem)


@dataclass
class GlbMesh:
    """1 geom 分のメッシュ。"""

    name: str
    vertices: np.ndarray  # (V, 3) float32
    normals: np.ndarray  # (V, 3) float32
    indices: np.ndarray  # (F, 3) uint32
    rgba: tuple[float, float, float, float]


@dataclass
class GlbNode:
    """シーングラフノード。"""

    name: str
    mesh: int = -1
    translation: tuple[float, float, float] | None = None
    rotation_xyzw: tuple[float, float, float, float] | None = None
    children: list[int] = field(default_factory=list)


def compute_smooth_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """面法線を頂点に蓄積するスムーズ法線。"""
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    norms = np.zeros_like(vertices)
    for c in range(3):
        np.add.at(norms, faces[:, c], fn)
    length = np.linalg.norm(norms, axis=1, keepdims=True)
    length[length == 0] = 1.0
    return normals_ok(norms / length)


def normals_ok(n: np.ndarray) -> np.ndarray:
    return n.astype(np.float32, copy=False)


# ---- primitive ジオメトリ生成（MuJoCo の非メッシュ geom 用） ----


def box_geometry(half: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """axis-aligned box。面ごとに頂点を分離（フラットシェード風）。"""
    hx, hy, hz = (float(half[0]), float(half[1]), float(half[2]))
    faces = [
        # (normal, 4 corner offsets)
        ((1, 0, 0), [(hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz)]),
        ((-1, 0, 0), [(-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz), (-hx, -hy, -hz)]),
        ((0, 1, 0), [(hx, hy, -hz), (-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz)]),
        ((0, -1, 0), [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)]),
        ((0, 0, 1), [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]),
        ((0, 0, -1), [(hx, -hy, -hz), (-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz)]),
    ]
    verts: list[tuple[float, float, float]] = []
    norms: list[tuple[float, float, float]] = []
    idx: list[int] = []
    for n, corners in faces:
        base = len(verts)
        verts.extend(corners)
        norms.extend([n] * 4)
        idx.extend([base, base + 1, base + 2, base, base + 2, base + 3])
    return (
        np.asarray(verts, dtype=np.float32),
        np.asarray(norms, dtype=np.float32),
        np.asarray(idx, dtype=np.uint32).reshape(-1, 3),
    )


def sphere_geometry(radius: float, seg: int = 20, rings: int = 14) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """UV 球。MuJoCo 同様ローカル z を極軸にする必要はない（対称）。"""
    verts: list[list[float]] = []
    for r in range(rings + 1):
        phi = np.pi * r / rings
        for s in range(seg + 1):
            theta = 2 * np.pi * s / seg
            x = np.sin(phi) * np.cos(theta)
            y = np.sin(phi) * np.sin(theta)
            z = np.cos(phi)
            verts.append([radius * x, radius * y, radius * z])
    v = np.asarray(verts, dtype=np.float32)
    norms = normals_ok(v / max(radius, 1e-9))
    idx: list[list[int]] = []
    for r in range(rings):
        for s in range(seg):
            i0 = r * (seg + 1) + s
            i1 = i0 + seg + 1
            idx.extend([[i0, i1, i0 + 1], [i1, i1 + 1, i0 + 1]])
    return v, norms, np.asarray(idx, dtype=np.uint32).reshape(-1, 3)


def cylinder_geometry(radius: float, half_height: float, seg: int = 20) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ローカル z 軸が円柱軸（MuJoCo と同じ）。"""
    hh = float(half_height)
    verts: list[list[float]] = []
    norms: list[list[float]] = []
    idx: list[list[int]] = []

    def ring(z: float, n_z: float) -> tuple[int, int]:
        base = len(verts)
        # n_z != 0 のキャップは法線が長さ √2 になるので正規化
        scale = float(np.sqrt(1.0 + n_z * n_z))
        for i in range(seg):
            a = 2 * np.pi * i / seg
            c, s = np.cos(a), np.sin(a)
            verts.append([radius * c, radius * s, z])
            norms.append([c / scale, s / scale, n_z / scale])
        return base, base + seg

    # 側面（法線は radial）
    b0, _ = ring(hh, 0.0)
    for i in range(seg):
        i0 = b0 + i
        i1 = b0 + (i + 1) % seg
        idx.append([i0, i1, i0 + seg])
        idx.append([i1, i1 + seg, i0 + seg])
    # 上面
    b1, _ = ring(hh, 1.0)
    # 下面
    b2, _ = ring(-hh, -1.0)
    for base in (b1, b2):
        center = len(verts)
        verts.append([0.0, 0.0, radius * 0.0 + (hh if base == b1 else -hh)])
        norms.append([0.0, 0.0, 1.0 if base == b1 else -1.0])
        for i in range(seg):
            idx.append([center, base + i, base + (i + 1) % seg])
    return (
        np.asarray(verts, dtype=np.float32),
        np.asarray(norms, dtype=np.float32),
        np.asarray(idx, dtype=np.uint32).reshape(-1, 3),
    )


def capsule_geometry(radius: float, half_height: float, seg: int = 20, cap_rings: int = 6) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """z 軸円柱 + 両半球キャップ。"""
    hh = float(half_height)
    verts: list[list[float]] = []
    norms: list[list[float]] = []
    idx: list[list[int]] = []

    def lat_ring(zc: float, r: float, nz: float) -> int:
        base = len(verts)
        for i in range(seg):
            a = 2 * np.pi * i / seg
            c, s = np.cos(a), np.sin(a)
            scale = np.linalg.norm([c, s, nz]) or 1.0
            verts.append([r * c, r * s, zc])
            norms.append([c / scale, s / scale, nz / scale])
        return base

    # 上半球の緯線（z = hh ... hh+radius）
    top_rings = []
    for k in range(cap_rings + 1):
        t = k / cap_rings  # 0=赤道側, 1=極
        nz = t
        r = radius * np.sqrt(max(0.0, 1.0 - nz * nz))
        top_rings.append(lat_ring(hh + radius * t, r, nz))
    # 下半球（z = -hh ... -hh-radius）
    bot_rings = []
    for k in range(cap_rings + 1):
        t = k / cap_rings
        nz = -t
        r = radius * np.sqrt(max(0.0, 1.0 - nz * nz))
        bot_rings.append(lat_ring(-hh - radius * t, r, nz))

    def stitch(a: int, b: int) -> None:
        for i in range(seg):
            a0, a1 = a + i, a + (i + 1) % seg
            b0, b1 = b + i, b + (i + 1) % seg
            idx.append([a0, b0, a1])
            idx.append([a1, b0, b1])

    # 下半球: bot_rings[0](赤道) → 極。stitch 順序を反転
    for k in range(cap_rings):
        a, b = bot_rings[k], bot_rings[k + 1]
        for i in range(seg):
            a0, a1 = a + i, a + (i + 1) % seg
            b0, b1 = b + i, b + (i + 1) % seg
            idx.append([a0, a1, b0])
            idx.append([a1, b1, b0])
    # 円柱部: bot_rings[0] ↔ top_rings[0]
    stitch(bot_rings[0], top_rings[0])
    # 上半球
    for k in range(cap_rings):
        stitch(top_rings[k], top_rings[k + 1])

    return (
        np.asarray(verts, dtype=np.float32),
        np.asarray(norms, dtype=np.float32),
        np.asarray(idx, dtype=np.uint32).reshape(-1, 3),
    )


def plane_geometry(size_x: float, size_y: float, subdiv: int = 1) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MuJoCo plane はローカル xy 面で法線 +z。"""
    verts: list[list[float]] = []
    idx: list[list[int]] = []
    for j in range(subdiv + 1):
        for i in range(subdiv + 1):
            u = -size_x + 2 * size_x * i / subdiv
            v = -size_y + 2 * size_y * j / subdiv
            verts.append([u, v, 0.0])
    for j in range(subdiv):
        for i in range(subdiv):
            k = j * (subdiv + 1) + i
            idx.append([k, k + subdiv + 1, k + 1])
            idx.append([k + 1, k + subdiv + 1, k + subdiv + 2])
    n = np.zeros((len(verts), 3), dtype=np.float32)
    n[:, 2] = 1.0
    return (
        np.asarray(verts, dtype=np.float32),
        n,
        np.asarray(idx, dtype=np.uint32).reshape(-1, 3),
    )


class GlbBuilder:
    """シーンを組み立てて GLB バイト列を吐く。"""

    def __init__(self) -> None:
        self.meshes: list[GlbMesh] = []
        self.nodes: list[GlbNode] = []
        self._bin = bytearray()
        self._buffer_views: list[dict] = []
        self._accessors: list[dict] = []
        self._materials: dict[tuple, int] = {}
        self._material_list: list[dict] = []

    # -- buffer helpers --

    def _add_view(self, arr: np.ndarray, target: int) -> tuple[int, int]:
        # little-endian を保証してからバイト列化（astype('<u1') は値変換になるのでNG）
        if arr.dtype == np.float32:
            a = arr.astype("<f4", copy=False)
        elif arr.dtype == np.uint32:
            a = arr.astype("<u4", copy=False)
        else:
            a = arr
        blob = np.ascontiguousarray(a).tobytes()
        offset = len(self._bin)
        if offset % 4 != 0:
            pad = 4 - (offset % 4)
            self._bin.extend(_ZPAD * pad)
            offset = len(self._bin)
        self._bin.extend(blob)
        while len(self._bin) % 4 != 0:
            self._bin.extend(_ZPAD)
        view = {
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": len(blob),
            "target": target,
        }
        self._buffer_views.append(view)
        return len(self._buffer_views) - 1, len(blob)

    def _add_accessor(
        self,
        arr: np.ndarray,
        *,
        target: int,
        component: int,
        typ: str,
        with_minmax: bool,
    ) -> int:
        """accessor を追加。glTF の count は要素数（VEC3 なら頂点数）。"""
        flat = arr.reshape(-1)
        view_idx, _ = self._add_view(flat, target)
        acc = {
            "bufferView": view_idx,
            "componentType": component,
            "count": int(arr.shape[0]),
            "type": typ,
        }
        if with_minmax and arr.ndim == 2:
            acc["min"] = [float(x) for x in arr.min(axis=0)]
            acc["max"] = [float(x) for x in arr.max(axis=0)]
        self._accessors.append(acc)
        return len(self._accessors) - 1

    # -- public API --

    def add_material(self, rgba: tuple[float, float, float, float]) -> int:
        key = tuple(round(float(c), 5) for c in rgba)
        if key in self._materials:
            return self._materials[key]
        idx = len(self._material_list)
        self._materials[key] = idx
        self._material_list.append(
            {
                "name": f"mat_{idx:03d}",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [float(c) for c in rgba],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.85,
                },
                "doubleSided": True,
            }
        )
        return idx

    def add_mesh(self, mesh: GlbMesh) -> int:
        self.meshes.append(mesh)
        return len(self.meshes) - 1

    def add_node(
        self,
        name: str,
        *,
        mesh: int = -1,
        translation: tuple[float, float, float] | None = None,
        rotation_wxyz: tuple[float, float, float, float] | None = None,
        children: list[int] | None = None,
    ) -> int:
        rot_xyzw = None
        if rotation_wxyz is not None:
            w, x, y, z = rotation_wxyz
            rot_xyzw = (x, y, z, w)
        self.nodes.append(
            GlbNode(
                name=name,
                mesh=mesh,
                translation=translation,
                rotation_xyzw=rot_xyzw,
                children=list(children or []),
            )
        )
        return len(self.nodes) - 1

    def add_child(self, parent: int, child: int) -> None:
        self.nodes[parent].children.append(child)

    def to_glb(self) -> bytes:
        if not self.nodes:
            self.add_node("root")
        doc_meshes: list[dict] = []
        used_materials: set[int] = set()
        for i, mesh in enumerate(self.meshes):
            pos_acc = self._add_accessor(
                np.ascontiguousarray(mesh.vertices, dtype=np.float32),
                target=34962,
                component=5126,
                typ="VEC3",
                with_minmax=True,
            )
            nrm_acc = self._add_accessor(
                np.ascontiguousarray(mesh.normals, dtype=np.float32),
                target=34962,
                component=5126,
                typ="VEC3",
                with_minmax=False,
            )
            idx_acc = self._add_accessor(
                np.ascontiguousarray(mesh.indices, dtype=np.uint32).reshape(-1),
                target=34963,
                component=5125,
                typ="SCALAR",
                with_minmax=False,
            )
            mat = self.add_material(mesh.rgba)
            used_materials.add(mat)
            # bufferView 長と accessor 要求の整合チェック（ローダ互換性の早期発見）
            for acc_idx, item_size in ((pos_acc, 3), (nrm_acc, 3), (idx_acc, 1)):
                acc = self._accessors[acc_idx]
                view = self._buffer_views[acc["bufferView"]]
                required = acc["count"] * item_size * 4
                assert view["byteLength"] >= required, (
                    f"bufferView too small for {mesh.name}: "
                    f"{view['byteLength']} < {required}"
                )
            doc_meshes.append(
                {
                    "name": mesh.name,
                    "primitives": [
                        {
                            "attributes": {"POSITION": pos_acc, "NORMAL": nrm_acc},
                            "indices": idx_acc,
                            "material": mat,
                            "mode": 4,
                        }
                    ],
                }
            )

        doc_nodes: list[dict] = []
        for node in self.nodes:
            entry: dict = {"name": node.name}
            if node.mesh >= 0:
                entry["mesh"] = node.mesh
            if node.translation is not None:
                entry["translation"] = [float(c) for c in node.translation]
            if node.rotation_xyzw is not None:
                entry["rotation"] = [float(c) for c in node.rotation_xyzw]
            if node.children:
                entry["children"] = list(node.children)
            doc_nodes.append(entry)

        gltf = {
            "asset": {"version": "2.0", "generator": "parc-viewer-export"},
            "scene": 0,
            "scenes": [{"name": "scene", "nodes": [0]}],
            "nodes": doc_nodes,
            "meshes": doc_meshes,
            "materials": self._material_list,
            "accessors": self._accessors,
            "bufferViews": self._buffer_views,
            "buffers": [{"byteLength": len(self._bin)}],
        }

        json_bytes = _pad(json.dumps(gltf, separators=(",", ":")).encode("utf-8"), _PAD)
        bin_bytes = _pad(bytes(self._bin), _ZPAD)
        total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
        out = bytearray()
        out.extend(struct.pack("<III", GLB_MAGIC, 2, total))
        out.extend(struct.pack("<II", len(json_bytes), CHUNK_JSON))
        out.extend(json_bytes)
        out.extend(struct.pack("<II", len(bin_bytes), CHUNK_BIN))
        out.extend(bin_bytes)
        return bytes(out)
