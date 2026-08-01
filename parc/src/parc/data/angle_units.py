"""関節角の rad/deg 単位契約（SO-100/101 は degrees 正本）。

LIBERO / VR の相対 EE（ee_delta）は対象外。joint_position データセットのみ
meta/angle_units.json とスケール検査を使う。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy as np

AngleUnit = Literal["radians", "degrees"]
ControlMode = Literal["ee_delta", "joint_position"]

TARGET_UNIT: AngleUnit = "degrees"
ANGLE_UNITS_META_NAME = "angle_units.json"

# スケール検査（stored_unit=degrees 前提）の既定閾値
# 相対指令の微動疑い: p95(|a|) がこれ未満 → radians を degrees のまま書いた可能性
MICRO_MOTION_REL_P95_DEG = 0.25
# 絶対角の微動疑い: p95(|q|) がこれ未満 → 典型的な rad レンジ(≦π)を deg と誤記
# （正しい deg 軌跡は通常これより大きい）
MICRO_MOTION_ABS_P95_DEG = 5.0
# 暴走疑い（絶対角）: p95(|q|) がこれ超 → スケール崩壊
WILD_ABS_P95_DEG = 400.0
# 連続差分の非現実的ジャンプ（deg）
WILD_DELTA_P95_DEG = 90.0
# 後方互換エイリアス
MICRO_MOTION_P95_DEG = MICRO_MOTION_ABS_P95_DEG


@dataclass
class AngleUnitsMeta:
    """データセット root に保存する関節角単位メタ。"""

    control_mode: ControlMode
    source_unit: AngleUnit | None = None
    stored_unit: AngleUnit | None = None
    joint_indices: list[int] = field(default_factory=list)
    action_is_absolute: bool = True
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON 用 dict。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AngleUnitsMeta":
        """dict から復元する。"""
        mode = str(raw.get("control_mode", "ee_delta"))
        if mode not in ("ee_delta", "joint_position"):
            raise ValueError(f"invalid control_mode: {mode!r}")
        source = raw.get("source_unit")
        stored = raw.get("stored_unit")
        if source is not None and source not in ("radians", "degrees"):
            raise ValueError(f"invalid source_unit: {source!r}")
        if stored is not None and stored not in ("radians", "degrees"):
            raise ValueError(f"invalid stored_unit: {stored!r}")
        indices = raw.get("joint_indices") or []
        return cls(
            control_mode=mode,  # type: ignore[arg-type]
            source_unit=source,  # type: ignore[arg-type]
            stored_unit=stored,  # type: ignore[arg-type]
            joint_indices=[int(i) for i in indices],
            action_is_absolute=bool(raw.get("action_is_absolute", True)),
            notes=str(raw.get("notes") or ""),
        )


def convert_angles(
    x: np.ndarray | Sequence[float],
    source: AngleUnit,
    target: AngleUnit,
) -> np.ndarray:
    """角度配列を source → target に変換する。"""
    arr = np.asarray(x, dtype=np.float64)
    if source == target:
        return arr.astype(np.float64, copy=True)
    if source == "radians" and target == "degrees":
        return np.rad2deg(arr)
    if source == "degrees" and target == "radians":
        return np.deg2rad(arr)
    raise ValueError(f"unsupported conversion {source!r} -> {target!r}")


def normalize_joint_frame_arrays(
    *,
    state: np.ndarray | None,
    action: np.ndarray | None,
    source_unit: AngleUnit,
    target_unit: AngleUnit = TARGET_UNIT,
    joint_indices: Sequence[int] | None = None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """state / action の関節成分だけ単位変換したコピーを返す。

    joint_indices が None のときは全次元を変換する。
    """
    def _convert_vec(vec: np.ndarray | None) -> np.ndarray | None:
        if vec is None:
            return None
        out = np.asarray(vec, dtype=np.float32).copy()
        if source_unit == target_unit:
            return out
        if joint_indices is None:
            converted = convert_angles(out, source_unit, target_unit)
            return converted.astype(np.float32)
        idx = list(joint_indices)
        if idx:
            converted = convert_angles(out[idx], source_unit, target_unit)
            out[idx] = converted.astype(np.float32)
        return out

    return _convert_vec(state), _convert_vec(action)


def angle_units_meta_path(root: Path) -> Path:
    """meta/angle_units.json のパス。"""
    return Path(root) / "meta" / ANGLE_UNITS_META_NAME


def write_angle_units_meta(root: Path, meta: AngleUnitsMeta) -> Path:
    """angle_units.json を書き、パスを返す。"""
    path = angle_units_meta_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(meta.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_angle_units_meta(root: Path) -> AngleUnitsMeta | None:
    """angle_units.json があれば読み、無ければ None。"""
    path = angle_units_meta_path(root)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"angle_units.json must be object: {path}")
    return AngleUnitsMeta.from_dict(raw)


def assert_joint_dataset_units(meta: AngleUnitsMeta) -> None:
    """joint_position なら stored_unit が degrees であることを要求する。"""
    if meta.control_mode != "joint_position":
        return
    if meta.stored_unit != TARGET_UNIT:
        raise ValueError(
            f"joint_position dataset must store angles in {TARGET_UNIT!r}, "
            f"got stored_unit={meta.stored_unit!r}"
        )
    if meta.source_unit is None:
        raise ValueError("joint_position dataset requires source_unit in angle_units.json")


def _select_joint_cols(arr: np.ndarray, joint_indices: Sequence[int] | None) -> np.ndarray:
    """(T, D) から関節列だけ取る。"""
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if joint_indices is None or len(joint_indices) == 0:
        return arr
    return arr[:, list(joint_indices)]


def check_joint_angle_scale(
    actions: np.ndarray,
    *,
    meta: AngleUnitsMeta,
    states: np.ndarray | None = None,
    micro_abs_p95_deg: float = MICRO_MOTION_ABS_P95_DEG,
    micro_rel_p95_deg: float = MICRO_MOTION_REL_P95_DEG,
    wild_abs_p95_deg: float = WILD_ABS_P95_DEG,
    wild_delta_p95_deg: float = WILD_DELTA_P95_DEG,
) -> list[str]:
    """rad/deg 取り違えを振幅ヒューリスティックで検出する。

    control_mode が ee_delta、または stored_unit が degrees 以外のときは空リスト。
    エラーメッセージのリストを返す（空なら OK）。
    """
    if meta.control_mode != "joint_position":
        return []
    if meta.stored_unit != "degrees":
        return [
            f"scale check expects stored_unit=degrees, got {meta.stored_unit!r}"
        ]

    errors: list[str] = []
    act = np.asarray(actions, dtype=np.float64)
    if act.size == 0:
        return ["empty actions for joint angle scale check"]
    joint_act = _select_joint_cols(act, meta.joint_indices or None)
    abs_act = np.abs(joint_act)
    p95_act = float(np.percentile(abs_act, 95)) if abs_act.size else 0.0

    if meta.action_is_absolute:
        if p95_act < micro_abs_p95_deg:
            errors.append(
                f"micro-motion suspicion: action |q| p95={p95_act:.4f} deg "
                f"< {micro_abs_p95_deg} (radians logged as degrees?)"
            )
        if p95_act > wild_abs_p95_deg:
            errors.append(
                f"wild absolute angle: action |q| p95={p95_act:.4f} deg "
                f"> {wild_abs_p95_deg} (degrees treated as radians?)"
            )
        if joint_act.shape[0] >= 2:
            deltas = np.abs(np.diff(joint_act, axis=0))
            p95_delta = float(np.percentile(deltas, 95)) if deltas.size else 0.0
            if p95_delta > wild_delta_p95_deg:
                errors.append(
                    f"wild joint jump: |Δq| p95={p95_delta:.4f} deg "
                    f"> {wild_delta_p95_deg}"
                )
    else:
        # 相対指令: 常に小さいと微動疑い、常に大きすぎると暴走疑い
        if p95_act < micro_rel_p95_deg:
            errors.append(
                f"micro-motion suspicion: relative action |a| p95={p95_act:.4f} deg "
                f"< {micro_rel_p95_deg} (radians logged as degrees?)"
            )
        if p95_act > wild_delta_p95_deg:
            errors.append(
                f"wild relative action: |a| p95={p95_act:.4f} deg "
                f"> {wild_delta_p95_deg}"
            )

    if states is not None:
        st = np.asarray(states, dtype=np.float64)
        joint_st = _select_joint_cols(st, meta.joint_indices or None)
        p95_st = float(np.percentile(np.abs(joint_st), 95)) if joint_st.size else 0.0
        if p95_st < micro_abs_p95_deg and meta.action_is_absolute:
            errors.append(
                f"micro-motion suspicion: state |q| p95={p95_st:.4f} deg "
                f"< {micro_abs_p95_deg}"
            )
        if p95_st > wild_abs_p95_deg:
            errors.append(
                f"wild absolute state: |q| p95={p95_st:.4f} deg > {wild_abs_p95_deg}"
            )

    return errors


def verify_angle_units_for_dataset(
    root: Path,
    *,
    require_meta: bool = False,
    check_scale: bool = False,
    actions: np.ndarray | None = None,
    states: np.ndarray | None = None,
) -> dict[str, Any]:
    """データセット root の単位メタと（任意で）スケールを検査する。"""
    root = Path(root)
    meta = load_angle_units_meta(root)
    result: dict[str, Any] = {
        "root": str(root),
        "meta_present": meta is not None,
        "skipped": False,
        "ok": True,
        "errors": [],
    }
    if meta is None:
        if require_meta:
            raise ValueError(f"missing meta/{ANGLE_UNITS_META_NAME} under {root}")
        result["skipped"] = True
        return result

    if meta.control_mode == "ee_delta":
        result["skipped"] = True
        result["control_mode"] = meta.control_mode
        return result

    assert_joint_dataset_units(meta)
    result["control_mode"] = meta.control_mode
    result["stored_unit"] = meta.stored_unit
    result["source_unit"] = meta.source_unit

    if check_scale:
        if actions is None:
            raise ValueError(
                "check_scale=True requires actions array "
                "(pass sampled joint actions from the dataset)"
            )
        errors = check_joint_angle_scale(actions, meta=meta, states=states)
        result["errors"] = errors
        if errors:
            result["ok"] = False
            raise ValueError("; ".join(errors))
    return result


def build_normalize_cli_parser() -> argparse.ArgumentParser:
    """parc-normalize-angle-units 用パーサ。"""
    p = argparse.ArgumentParser(
        prog="parc-normalize-angle-units",
        description=(
            "Write meta/angle_units.json and optionally convert a sample "
            "joint vector radians→degrees (dataset conversion helper)."
        ),
    )
    p.add_argument("--root", type=Path, required=True, help="dataset root")
    p.add_argument(
        "--control-mode",
        choices=("ee_delta", "joint_position"),
        default="joint_position",
    )
    p.add_argument(
        "--source-angle-unit",
        choices=("radians", "degrees"),
        default=None,
        help="raw log unit (required for joint_position)",
    )
    p.add_argument(
        "--joint-indices",
        default="",
        help="comma-separated joint dims (empty = all)",
    )
    p.add_argument(
        "--action-relative",
        action="store_true",
        help="action is relative delta (not absolute joint pos)",
    )
    p.add_argument(
        "--sample",
        default="",
        help="comma-separated floats to convert and print (debug)",
    )
    return p


def normalize_angle_units_main(argv: list[str] | None = None) -> None:
    """CLI: メタ書き込み + サンプル変換。"""
    from rich.console import Console

    console = Console()
    args = build_normalize_cli_parser().parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    if args.control_mode == "joint_position" and args.source_angle_unit is None:
        console.print("[red]joint_position requires --source-angle-unit[/red]")
        raise SystemExit(2)

    indices = (
        [int(x) for x in args.joint_indices.split(",") if x.strip()]
        if args.joint_indices.strip()
        else []
    )
    meta = AngleUnitsMeta(
        control_mode=args.control_mode,
        source_unit=args.source_angle_unit,
        stored_unit=TARGET_UNIT if args.control_mode == "joint_position" else None,
        joint_indices=indices,
        action_is_absolute=not args.action_relative,
        notes="written by parc-normalize-angle-units",
    )
    if meta.control_mode == "joint_position":
        assert_joint_dataset_units(meta)

    path = write_angle_units_meta(root, meta)
    console.print(f"[green]wrote[/green] {path}")

    if args.sample.strip():
        if args.source_angle_unit is None:
            console.print("[red]--sample needs --source-angle-unit[/red]")
            raise SystemExit(2)
        vals = np.array(
            [float(x) for x in args.sample.split(",") if x.strip()],
            dtype=np.float64,
        )
        out = convert_angles(vals, args.source_angle_unit, TARGET_UNIT)
        console.print(
            f"sample {args.source_angle_unit} {vals.tolist()} "
            f"-> {TARGET_UNIT} {out.tolist()}"
        )
