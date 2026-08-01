"""公開 libero_plus と cam 再レンダを 1 本の LeRobot データセットへ物理マージする。

現行 LeRobot は ``MultiLeRobotDataset`` が無効（``factory.make_dataset`` が
非 str の ``repo_id`` で NotImplementedError）。CLI の
``--dataset.repo_id=[a,b]`` は使えないため、事前にマージしてから単一
``dataset_repo_id`` + ``dataset_root`` で学習する。
"""

from __future__ import annotations

import json
import random
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class MixResult:
    """マージ結果の要約（マニフェスト / CLI 表示用）。"""

    output_root: str
    output_repo_id: str
    base_repo_id: str
    base_root: str
    cam_repo_id: str
    cam_root: str
    base_episodes_selected: int
    cam_episodes_selected: int
    total_episodes: int
    total_frames: int
    seed: int
    dry_run: bool


def _resolve(path: Path | str, *, base: Path | None = None) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute() and base is not None:
        p = (base / p).resolve()
    else:
        p = p.resolve()
    return p


def align_feature_schema(target_info: dict[str, Any], reference_info: dict[str, Any]) -> bool:
    """target の features 付帯キーを reference に揃える（追加・削除の両方）。

    libero_cam_views_v1 は ``fps`` キーが各特徴に無く、libero_plus と
    ``features !=`` になり ``aggregate_datasets`` が落ちる。
    split 後は逆に fps が欠ける側もあるため、reference に無いキーは削除する。
    Returns True if info was mutated.
    """
    ref_feats = reference_info.get("features") or {}
    tgt_feats = target_info.get("features") or {}
    changed = False
    for key, ref_spec in ref_feats.items():
        if key not in tgt_feats:
            continue
        tgt_spec = tgt_feats[key]
        if not isinstance(ref_spec, dict) or not isinstance(tgt_spec, dict):
            continue
        if ref_spec.get("dtype") != tgt_spec.get("dtype"):
            continue
        if list(ref_spec.get("shape") or []) != list(tgt_spec.get("shape") or []):
            continue
        for meta_key in ("fps", "names"):
            if meta_key in ref_spec:
                if tgt_spec.get(meta_key) != ref_spec.get(meta_key):
                    tgt_spec[meta_key] = ref_spec[meta_key]
                    changed = True
            elif meta_key in tgt_spec:
                del tgt_spec[meta_key]
                changed = True
    return changed


def force_features_equal(target_root: Path, reference_root: Path) -> None:
    """target の features を reference と完全一致させる（merge 直前用）。"""
    target_path = target_root / "meta" / "info.json"
    ref_path = reference_root / "meta" / "info.json"
    target = json.loads(target_path.read_text(encoding="utf-8"))
    reference = json.loads(ref_path.read_text(encoding="utf-8"))
    target["features"] = reference["features"]
    target_path.write_text(json.dumps(target, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def patch_info_json_features(dataset_root: Path, reference_root: Path) -> bool:
    """dataset_root/meta/info.json の features を reference に合わせて書き戻す。"""
    target_path = dataset_root / "meta" / "info.json"
    ref_path = reference_root / "meta" / "info.json"
    target = json.loads(target_path.read_text(encoding="utf-8"))
    reference = json.loads(ref_path.read_text(encoding="utf-8"))
    if not align_feature_schema(target, reference):
        return False
    target_path.write_text(json.dumps(target, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def _sample_episode_indices(n_total: int, n_keep: int, *, seed: int) -> list[int]:
    if n_keep <= 0:
        raise ValueError("n_keep must be > 0")
    if n_keep > n_total:
        raise ValueError(f"n_keep={n_keep} > total_episodes={n_total}")
    rng = random.Random(seed)
    idx = list(range(n_total))
    rng.shuffle(idx)
    return sorted(idx[:n_keep])


def mix_lerobot_datasets(
    *,
    base_repo_id: str,
    base_root: Path,
    cam_repo_id: str,
    cam_root: Path,
    output_repo_id: str,
    output_root: Path,
    base_episodes: int,
    cam_episodes: int | None = None,
    cam_episode_indices: list[int] | None = None,
    seed: int = 42,
    dry_run: bool = False,
    overwrite: bool = False,
    work_dir: Path | None = None,  # 互換のため残置（未使用）
) -> MixResult:
    """base から N ep を抽出し cam とマージして ``output_root`` に書く。

    ``cam_episode_indices`` 指定時はランダムではなくその index を使う
    （Phase A' hard-near など）。``cam_episodes`` より優先。
    """
    try:
        from lerobot.datasets.dataset_metadata import LeRobotDatasetMetadata
        from lerobot.datasets.dataset_tools import merge_datasets
        from lerobot.datasets.lerobot_dataset import LeRobotDataset
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "lerobot が必要です。`bash scripts/mix_datasets.sh ...` "
            "（親 Matsuo/robot/.venv）で実行してください。"
        ) from e

    base_root = _resolve(base_root)
    cam_root = _resolve(cam_root)
    output_root = _resolve(output_root)

    if not (base_root / "meta" / "info.json").is_file():
        raise FileNotFoundError(f"base dataset meta missing: {base_root}")
    if not (cam_root / "meta" / "info.json").is_file():
        raise FileNotFoundError(f"cam dataset meta missing: {cam_root}")

    # cam の features を base に揃える（破壊的だがスキーマ欠落の修正）
    patched = patch_info_json_features(cam_root, base_root)

    # dry-run はメタだけ（14k ep の LeRobotDataset 全ロードを避ける）
    base_meta = LeRobotDatasetMetadata(base_repo_id, root=base_root)
    cam_meta = LeRobotDatasetMetadata(cam_repo_id, root=cam_root)

    n_base = int(base_meta.total_episodes)
    n_cam = int(cam_meta.total_episodes)

    base_idx = _sample_episode_indices(n_base, int(base_episodes), seed=seed)
    if cam_episode_indices is not None:
        cam_idx = sorted({int(i) for i in cam_episode_indices})
        if not cam_idx:
            raise ValueError("cam_episode_indices is empty")
        bad = [i for i in cam_idx if i < 0 or i >= n_cam]
        if bad:
            raise ValueError(f"cam_episode_indices out of range (0..{n_cam - 1}): {bad[:8]}")
    else:
        cam_keep = n_cam if cam_episodes is None else int(cam_episodes)
        if cam_keep <= 0 or cam_keep > n_cam:
            raise ValueError(f"cam_episodes={cam_keep} out of range (1..{n_cam})")
        cam_idx = (
            list(range(n_cam))
            if cam_keep == n_cam
            else _sample_episode_indices(n_cam, cam_keep, seed=seed + 1)
        )

    def _frames_for(meta: LeRobotDatasetMetadata, indices: list[int]) -> int:
        return sum(int(meta.episodes[i]["length"]) for i in indices)

    est_frames = _frames_for(base_meta, base_idx) + _frames_for(cam_meta, cam_idx)
    result = MixResult(
        output_root=str(output_root),
        output_repo_id=output_repo_id,
        base_repo_id=base_repo_id,
        base_root=str(base_root),
        cam_repo_id=cam_repo_id,
        cam_root=str(cam_root),
        base_episodes_selected=len(base_idx),
        cam_episodes_selected=len(cam_idx),
        total_episodes=len(base_idx) + len(cam_idx),
        total_frames=est_frames,
        seed=seed,
        dry_run=dry_run,
    )

    if dry_run:
        return result

    if output_root.exists():
        if not overwrite:
            raise FileExistsError(f"output exists: {output_root} (use --overwrite)")
        shutil.rmtree(output_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)

    # aggregate は root 全体を見るため、episodes= フィルタだけでは足りない。
    # 先に split_dataset で物理サブセットを作り、その root 同士を merge する。
    work = work_dir or (output_root.parent / f".mix_work_{output_root.name}")
    work.mkdir(parents=True, exist_ok=True)
    success = False

    try:
        from lerobot.datasets.dataset_tools import split_dataset

        base_split_root = work / "base_splits" / "mix"
        if (base_split_root / "meta" / "info.json").is_file():
            print(f"[parc-mix] reusing base split at {base_split_root}", flush=True)
            base_subset = LeRobotDataset(
                f"{base_repo_id}_mix", root=base_split_root
            )
        else:
            print(
                f"[parc-mix] loading base ({n_base} eps) — may take minutes on slow mounts…",
                flush=True,
            )
            base_ds = LeRobotDataset(base_repo_id, root=base_root)
            print(f"[parc-mix] splitting base → {len(base_idx)} eps", flush=True)
            base_subset = split_dataset(
                base_ds,
                splits={"mix": base_idx},
                output_dir=work / "base_splits",
            )["mix"]
            del base_ds

        # cam は merge 用に work へコピーしてから features を揃える（元データは壊さない）
        if len(cam_idx) == n_cam:
            cam_work = work / "cam_all"
            if not (cam_work / "meta" / "info.json").is_file():
                print(f"[parc-mix] copying cam → {cam_work}", flush=True)
                if cam_work.exists():
                    shutil.rmtree(cam_work)
                shutil.copytree(cam_root, cam_work)
            cam_load_root = cam_work
            cam_load_id = cam_repo_id
        else:
            cam_split_root = work / "cam_splits" / "mix"
            if (cam_split_root / "meta" / "info.json").is_file():
                print(f"[parc-mix] reusing cam split at {cam_split_root}", flush=True)
                cam_load_root = cam_split_root
                cam_load_id = f"{cam_repo_id}_mix"
            else:
                print(f"[parc-mix] loading+splitting cam → {len(cam_idx)} eps", flush=True)
                cam_ds = LeRobotDataset(cam_repo_id, root=cam_root)
                cam_subset_tmp = split_dataset(
                    cam_ds,
                    splits={"mix": cam_idx},
                    output_dir=work / "cam_splits",
                )["mix"]
                del cam_ds
                cam_load_root = Path(cam_subset_tmp.root)
                cam_load_id = cam_subset_tmp.repo_id

        print("[parc-mix] aligning cam features to base subset", flush=True)
        force_features_equal(Path(cam_load_root), Path(base_subset.root))
        cam_subset = LeRobotDataset(cam_load_id, root=cam_load_root)

        print("[parc-mix] merging…", flush=True)
        merge_datasets(
            [base_subset, cam_subset],
            output_repo_id=output_repo_id,
            output_dir=output_root,
        )

        info = json.loads((output_root / "meta" / "info.json").read_text(encoding="utf-8"))
        result.total_episodes = int(info.get("total_episodes", result.total_episodes))
        result.total_frames = int(info.get("total_frames", result.total_frames))

        manifest = {
            **asdict(result),
            "cam_features_patched": patched,
            "base_episode_indices": base_idx,
            "cam_episode_indices": cam_idx,
            "ratio_episodes_base_cam": [
                result.base_episodes_selected,
                result.cam_episodes_selected,
            ],
        }
        (output_root / "mix_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        success = True
    finally:
        # 成功時のみ work を消す（失敗時は base split を再利用できるように残す）
        if success and work.exists():
            shutil.rmtree(work, ignore_errors=True)

    return result
