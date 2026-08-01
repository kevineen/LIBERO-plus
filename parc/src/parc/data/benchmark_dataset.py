"""ベンチマーク別データセット骨格（LeRobot 向け契約・変換口）。"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Any

from parc.benchmarks import DatasetSpec, get_benchmark
from parc.benchmarks.base import BenchmarkBackend


def resolve_benchmark_name(config: dict[str, Any]) -> str | None:
    """YAML から benchmark backend 名を取る（無ければ None）。"""
    bench = config.get("benchmark") or {}
    if isinstance(bench, dict) and bench.get("backend"):
        return str(bench["backend"]).lower().strip()
    eval_cfg = config.get("eval") or {}
    if isinstance(eval_cfg, dict) and eval_cfg.get("backend"):
        return str(eval_cfg["backend"]).lower().strip()
    train_cfg = config.get("train") or {}
    if isinstance(train_cfg, dict) and train_cfg.get("benchmark"):
        return str(train_cfg["benchmark"]).lower().strip()
    return None


def get_dataset_spec(backend_name: str) -> DatasetSpec:
    """登録済み backend の DatasetSpec。"""
    cls = get_benchmark(backend_name)
    return cls().dataset_spec()


def write_dataset_skeleton(root: Path, spec: DatasetSpec) -> Path:
    """空の meta 骨格を書く（デモは含まない）。

    LeRobot 互換の完全な dataset ではない。契約確認・ディレクトリ用意用。
    """
    root = Path(root)
    meta = root / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    info = {
        "codebase_version": "v3.0-skeleton",
        "robot_type": spec.robot_type,
        "fps": spec.fps,
        "backend": spec.backend,
        "features": spec.features,
        "total_episodes": 0,
        "total_frames": 0,
        "dataset_repo_id": spec.dataset_repo_id,
        "notes": spec.notes,
        "status": "skeleton_only",
    }
    path = meta / "benchmark_spec.json"
    path.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n")
    (meta / "info.json").write_text(
        json.dumps(
            {
                "codebase_version": "v3.0-skeleton",
                "robot_type": spec.robot_type,
                "fps": spec.fps,
                "features": spec.features,
                "total_episodes": 0,
                "total_frames": 0,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    return path


class EpisodeConverter(ABC):
    """raw episodes → LeRobot dataset root の変換プロトコル。"""

    @abstractmethod
    def convert(self, raw_root: Path, out_root: Path, *, overwrite: bool = False) -> Path:
        """変換を実行し、出力 root を返す。"""


class MetaworldMT50Converter(EpisodeConverter):
    """MT50 デモ変換（第1弾は未実装）。"""

    def convert(self, raw_root: Path, out_root: Path, *, overwrite: bool = False) -> Path:
        raise NotImplementedError(
            "Meta-World MT50 の raw→LeRobot 変換は未実装です。"
            " DatasetSpec と write_dataset_skeleton で契約だけ先に確認してください。"
            f" raw={raw_root} out={out_root} overwrite={overwrite}"
        )


def converter_for(backend_name: str) -> EpisodeConverter:
    """backend 名に対応する変換器。"""
    key = backend_name.lower().strip()
    if key in {"metaworld_mt50", "mt50", "metaworld"}:
        return MetaworldMT50Converter()
    raise NotImplementedError(
        f"EpisodeConverter 未実装: {backend_name!r}。"
        " parc.benchmarks に Backend を足したあと、ここへ変換器を登録してください。"
    )


def ensure_train_benchmark_supported(config: dict[str, Any]) -> dict[str, Any] | None:
    """学習前チェック。非 LIBERO backend なら結果 dict（エラー/ヒント）を返す。

    LIBERO（または benchmark 未指定）なら None = 続行可。
    """
    name = resolve_benchmark_name(config)
    if name is None or name == "libero":
        return None

    # 登録確認
    try:
        backend: BenchmarkBackend = get_benchmark(name)()
    except KeyError as e:
        return {
            "status": "failed",
            "backend": name,
            "hint": str(e),
        }

    spec = backend.dataset_spec()
    train_cfg = config.get("train") or {}
    dataset_root = train_cfg.get("dataset_root")
    skeleton_path = None
    if dataset_root:
        from parc.paths import PARC_ROOT

        root = Path(str(dataset_root)).expanduser()
        if not root.is_absolute():
            root = (PARC_ROOT / root).resolve()
        skeleton_path = str(write_dataset_skeleton(root, spec))

    return {
        "status": "not_implemented",
        "backend": name,
        "dataset_spec": asdict(spec),
        "skeleton_path": skeleton_path,
        "hint": (
            f"benchmark.backend={name!r} の本学習は未接続です。"
            " DatasetSpec / write_dataset_skeleton で契約を確認し、"
            " デモ変換（EpisodeConverter）実装後に train.backend=lerobot を接続してください。"
            " 評価は `eval.backend` + parc-eval を使えます。"
        ),
    }
