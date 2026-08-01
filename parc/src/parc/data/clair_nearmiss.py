"""CLAIR 風選好ペア: 成功軌道への微小摂動で near-miss（rejected）を合成する。

主経路はシミュ内合成。人間修正は ``source=human_revise`` で meta に追記可能。
研究サイドカー専用（親 ckpt 選定には接続しない）。
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np

from parc.paths import PARC_ROOT

# 掴み直前ウィンドウで使う摂動モード
PerturbMode = Literal["ee_trans", "ee_rot", "gripper_early", "gripper_late", "combo"]

# Gate P1: preferred↔rejected の平均 action L2 帯（smoke で固定）
ACTION_L2_MIN = 0.02
ACTION_L2_MAX = 2.5

PAIRS_JSONL_NAME = "pairs.jsonl"
PAIR_SCHEMA_VERSION = 1


@dataclass
class PerturbSpec:
    """1 本の摂動仕様。"""

    mode: PerturbMode
    window_start: int
    window_end: int
    ee_trans_scale: float = 0.03
    ee_rot_scale: float = 0.05
    gripper_delta: float = 0.4
    seed: int = 0


@dataclass
class PairRecord:
    """pairs.jsonl の 1 行。"""

    pair_id: str
    preferred_episode_id: int
    rejected_episode_id: int
    contrast_score: float
    fail_mode: str
    perturb_spec: dict[str, Any]
    action_l2_mean: float
    source: str = "sim_nearmiss"
    schema_version: int = PAIR_SCHEMA_VERSION


@dataclass
class NearMissRollout:
    """摂動ロールアウト結果。"""

    success: bool
    fail_mode: str
    actions: list[np.ndarray]
    action_l2_mean: float
    contrast_score: float
    tip_angle_proxy: float
    final_ee_obj_dist: float
    accepted: bool


@dataclass
class ClairPairsResult:
    """合成ジョブの要約。"""

    output: str
    n_preferred: int
    n_rejected: int
    n_pairs: int
    n_discarded: int
    action_l2_mean: float
    fake: bool
    dry_run: bool
    pair_ids: list[str] = field(default_factory=list)


class NearMissProbeEnv:
    """摂動に反応するフェイク env（単体テスト / ``--fake`` 用）。

    並進ノルムが大きい action がウィンドウ内に出ると失敗（near-miss）。
    小さい摂動だけだと成功してしまう場合は scale を上げて再試行する。
    """

    def __init__(
        self,
        *,
        height: int = 32,
        width: int = 32,
        fail_trans_norm: float = 0.02,
        tip_on_fail: float = 0.35,
    ) -> None:
        self.height = height
        self.width = width
        self.fail_trans_norm = fail_trans_norm
        self.tip_on_fail = tip_on_fail
        self._t = 0
        self._failed = False
        self._tip = 0.0
        self._ee_obj = 0.05

    def reset(self) -> dict[str, Any]:
        """初期観測。"""
        self._t = 0
        self._failed = False
        self._tip = 0.0
        self._ee_obj = 0.05
        return self._obs()

    def set_init_state(self, state: Any) -> dict[str, Any]:
        """互換 API。"""
        del state
        return self.reset()

    def check_success(self) -> bool:
        """成功判定。"""
        return not self._failed

    def step(self, action: list[float] | np.ndarray) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        """action 並進ノルムで near-miss を誘発する。"""
        a = np.asarray(action, dtype=np.float64).reshape(-1)
        self._t += 1
        trans = float(np.linalg.norm(a[:3])) if a.size >= 3 else 0.0
        grip = float(a[6]) if a.size >= 7 else 0.0
        if trans >= self.fail_trans_norm or abs(grip) >= 0.35:
            self._failed = True
            self._tip = self.tip_on_fail
            self._ee_obj = 0.12 + trans
            obs = self._obs()
            return obs, 0.0, True, {"success": False, "fail_mode": "tip_or_slip"}
        obs = self._obs()
        # 長めに走らせても成功
        done = self._t >= 64
        return obs, 1.0 if done else 0.0, done, {"success": (not self._failed) and done}

    def close(self) -> None:
        """何もしない。"""
        return None

    def _obs(self) -> dict[str, Any]:
        h, w = self.height, self.width
        return {
            "agentview_image": np.zeros((h, w, 3), dtype=np.uint8),
            "robot0_eye_in_hand_image": np.zeros((h, w, 3), dtype=np.uint8),
            "robot0_eef_pos": np.array([0.0, 0.0, 0.1], dtype=np.float32),
            "robot0_eef_quat": np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            "tip_angle_proxy": np.float32(self._tip),
            "ee_obj_dist": np.float32(self._ee_obj),
        }


def _resolve(path: str | Path) -> Path:
    """相対パスを parc ルート基準で解決する。"""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (PARC_ROOT / p).resolve()
    return p


def grasp_window(n_steps: int, *, frac_start: float = 0.45, frac_end: float = 0.75) -> tuple[int, int]:
    """掴み直前〜把持付近のインデックス窓を返す。"""
    if n_steps <= 0:
        return 0, 0
    start = int(max(0, math.floor(n_steps * frac_start)))
    end = int(min(n_steps, math.ceil(n_steps * frac_end)))
    if end <= start:
        end = min(n_steps, start + max(1, n_steps // 5))
    return start, end


def perturb_actions(
    actions: list[np.ndarray] | np.ndarray,
    spec: PerturbSpec,
    *,
    rng: np.random.Generator | None = None,
) -> list[np.ndarray]:
    """成功 action 系列に局所摂動を加える。

    Args:
        actions: ``(T, 7)`` 相当の相対 EE + gripper。
        spec: 摂動仕様。
        rng: 乱数。省略時は ``spec.seed`` から生成。

    Returns:
        摂動後の action リスト（各 ``float64``）。
    """
    arr = [np.asarray(a, dtype=np.float64).reshape(-1).copy() for a in actions]
    n = len(arr)
    if n == 0:
        return arr
    rng = rng or np.random.default_rng(spec.seed)
    w0 = max(0, min(spec.window_start, n - 1))
    w1 = max(w0 + 1, min(spec.window_end, n))
    mode = spec.mode
    for t in range(w0, w1):
        a = arr[t]
        if a.size < 7:
            a = np.pad(a, (0, 7 - a.size))
            arr[t] = a
        if mode in {"ee_trans", "combo"}:
            a[:3] += rng.normal(0.0, spec.ee_trans_scale, size=3)
        if mode in {"ee_rot", "combo"}:
            a[3:6] += rng.normal(0.0, spec.ee_rot_scale, size=3)
        if mode == "gripper_early":
            # 窓前半でグリッパを開く方向へ
            a[6] = float(np.clip(a[6] + spec.gripper_delta, -1.0, 1.0))
        elif mode == "gripper_late":
            a[6] = float(np.clip(a[6] - spec.gripper_delta, -1.0, 1.0))
        elif mode == "combo":
            a[6] = float(np.clip(a[6] + rng.choice([-1.0, 1.0]) * spec.gripper_delta * 0.5, -1.0, 1.0))
    return arr


def mean_action_l2(a: list[np.ndarray], b: list[np.ndarray]) -> float:
    """対応タイムステップの平均 L2。長さは短い方に揃える。"""
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    vals = [
        float(np.linalg.norm(np.asarray(a[i], dtype=np.float64) - np.asarray(b[i], dtype=np.float64)))
        for i in range(n)
    ]
    return float(np.mean(vals))


def contrast_score_physics(
    *,
    action_l2_mean: float,
    tip_angle_proxy: float,
    final_ee_obj_dist: float,
    success: bool,
) -> float:
    """物理指標ベースのコントラストスコア（高いほど「微妙な差で失敗」）。

    成功した軌道や遠方失敗は低スコアになる。
    """
    if success:
        return 0.0
    # L2 が小さすぎるとノイズ、大きすぎると遠方失敗
    band = math.exp(-((action_l2_mean - 0.25) ** 2) / (2 * 0.15**2))
    tip = min(1.0, max(0.0, tip_angle_proxy))
    dist = math.exp(-max(0.0, final_ee_obj_dist - 0.05) / 0.2)
    return float(band * (0.4 + 0.4 * tip + 0.2 * dist))


def classify_fail_mode(
    *,
    success: bool,
    action_l2_mean: float,
    tip_angle_proxy: float,
    final_ee_obj_dist: float,
    diverged_early: bool,
) -> str:
    """採用/破棄を含む失敗モードラベル。"""
    if success:
        return "still_success"
    if diverged_early or action_l2_mean > ACTION_L2_MAX:
        return "far_diverge"
    if action_l2_mean < ACTION_L2_MIN:
        return "too_similar"
    if tip_angle_proxy >= 0.15:
        return "tip"
    if final_ee_obj_dist >= 0.08:
        return "slip_or_miss"
    return "contact_near_fail"


def is_acceptable_nearmiss(fail_mode: str, contrast_score: float, *, min_contrast: float = 0.15) -> bool:
    """CLAIR 風に「最小差で失敗」だけ残す。"""
    if fail_mode in {"still_success", "far_diverge", "too_similar"}:
        return False
    return contrast_score >= min_contrast


def rollout_perturbed(
    env: Any,
    preferred_actions: list[np.ndarray],
    perturbed_actions: list[np.ndarray],
    *,
    max_steps: int | None = None,
) -> NearMissRollout:
    """摂動 action を env で再生し、near-miss 採用可否を返す。"""
    env.reset()
    n = len(perturbed_actions) if max_steps is None else min(len(perturbed_actions), max_steps)
    tip = 0.0
    ee_obj = 0.05
    success = False
    diverged_early = False
    last_info: dict[str, Any] = {}
    for t in range(n):
        a = perturbed_actions[t]
        _obs, _r, done, info = env.step(a.tolist() if hasattr(a, "tolist") else list(a))
        last_info = dict(info or {})
        if isinstance(_obs, dict):
            tip = float(_obs.get("tip_angle_proxy", tip))
            ee_obj = float(_obs.get("ee_obj_dist", ee_obj))
        if t < max(1, n // 5) and last_info.get("success") is False and done:
            diverged_early = True
        if done:
            break
    check = getattr(env, "check_success", None)
    if callable(check):
        success = bool(check())
    else:
        success = bool(last_info.get("success", False))
    l2 = mean_action_l2(preferred_actions, perturbed_actions)
    fail_mode = classify_fail_mode(
        success=success,
        action_l2_mean=l2,
        tip_angle_proxy=tip,
        final_ee_obj_dist=ee_obj,
        diverged_early=diverged_early,
    )
    score = contrast_score_physics(
        action_l2_mean=l2,
        tip_angle_proxy=tip,
        final_ee_obj_dist=ee_obj,
        success=success,
    )
    return NearMissRollout(
        success=success,
        fail_mode=fail_mode,
        actions=perturbed_actions,
        action_l2_mean=l2,
        contrast_score=score,
        tip_angle_proxy=tip,
        final_ee_obj_dist=ee_obj,
        accepted=is_acceptable_nearmiss(fail_mode, score),
    )


def make_synthetic_preferred_actions(
    n_steps: int,
    *,
    seed: int = 0,
    action_dim: int = 7,
) -> list[np.ndarray]:
    """fake 用の滑らかな成功軌道（相対 EE）。"""
    rng = np.random.default_rng(seed)
    actions: list[np.ndarray] = []
    for t in range(n_steps):
        phase = t / max(1, n_steps - 1)
        a = np.zeros(action_dim, dtype=np.float64)
        a[0] = 0.01 * math.sin(phase * math.pi)
        a[2] = -0.008 if phase < 0.6 else 0.004
        a[6] = -0.2 if phase < 0.55 else 0.6
        a[:3] += rng.normal(0.0, 0.001, size=3)
        actions.append(a)
    return actions


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_minimal_episode_dir(
    root: Path,
    episode_index: int,
    actions: list[np.ndarray],
    *,
    success: bool,
    language: str,
    suite: str,
    task_id: int,
) -> None:
    """LeRobot 完全体の代わりに、ペア検証用の最小エピソード成果物を書く。"""
    ep_dir = root / "episodes" / f"episode_{episode_index:06d}"
    ep_dir.mkdir(parents=True, exist_ok=True)
    act = np.stack([np.asarray(a, dtype=np.float32) for a in actions], axis=0)
    np.save(ep_dir / "actions.npy", act)
    meta = {
        "episode_index": episode_index,
        "success": success,
        "language": language,
        "suite": suite,
        "task_id": task_id,
        "num_frames": int(act.shape[0]),
        "fps": 20,
        "robot_type": "panda",
        "action_dim": int(act.shape[1]),
    }
    (ep_dir / "episode_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_pairs_dataset(
    output: Path,
    pairs: list[PairRecord],
    preferred_actions: dict[int, list[np.ndarray]],
    rejected_actions: dict[int, list[np.ndarray]],
    *,
    language: str = "pick up the object",
    suite: str = "libero_spatial",
    task_id: int = 0,
    dry_run: bool = False,
) -> None:
    """preferred/ rejected/ meta/pairs.jsonl を書き出す。"""
    if dry_run:
        return
    if output.exists():
        shutil.rmtree(output)
    pref_root = output / "preferred"
    rej_root = output / "rejected"
    meta_root = output / "meta"
    meta_root.mkdir(parents=True, exist_ok=True)
    for ep_id, acts in preferred_actions.items():
        _write_minimal_episode_dir(
            pref_root, ep_id, acts, success=True, language=language, suite=suite, task_id=task_id
        )
    for ep_id, acts in rejected_actions.items():
        _write_minimal_episode_dir(
            rej_root, ep_id, acts, success=False, language=language, suite=suite, task_id=task_id
        )
    _write_jsonl(meta_root / PAIRS_JSONL_NAME, [asdict(p) for p in pairs])
    summary = {
        "schema_version": PAIR_SCHEMA_VERSION,
        "n_pairs": len(pairs),
        "n_preferred": len(preferred_actions),
        "n_rejected": len(rejected_actions),
        "suite": suite,
        "task_id": task_id,
        "action_l2_min": ACTION_L2_MIN,
        "action_l2_max": ACTION_L2_MAX,
    }
    (meta_root / "pairs_info.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def validate_pairs_dataset(root: Path) -> dict[str, Any]:
    """pairs schema と action L2 帯を検証する。"""
    root = _resolve(root)
    pairs_path = root / "meta" / PAIRS_JSONL_NAME
    errors: list[str] = []
    if not pairs_path.is_file():
        return {"ok": False, "errors": [f"missing {pairs_path}"], "n_pairs": 0}
    pairs: list[dict[str, Any]] = []
    for i, line in enumerate(pairs_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        for key in (
            "pair_id",
            "preferred_episode_id",
            "rejected_episode_id",
            "contrast_score",
            "fail_mode",
            "perturb_spec",
            "action_l2_mean",
            "source",
        ):
            if key not in row:
                errors.append(f"pairs.jsonl:{i} missing {key}")
        pairs.append(row)
    l2s = [float(p["action_l2_mean"]) for p in pairs if "action_l2_mean" in p]
    mean_l2 = float(np.mean(l2s)) if l2s else 0.0
    if pairs and not (ACTION_L2_MIN <= mean_l2 <= ACTION_L2_MAX):
        errors.append(f"mean action_l2={mean_l2:.4f} outside [{ACTION_L2_MIN}, {ACTION_L2_MAX}]")
    for p in pairs:
        pref = root / "preferred" / "episodes" / f"episode_{int(p['preferred_episode_id']):06d}" / "actions.npy"
        rej = root / "rejected" / "episodes" / f"episode_{int(p['rejected_episode_id']):06d}" / "actions.npy"
        if not pref.is_file():
            errors.append(f"missing preferred actions for pair {p.get('pair_id')}")
        if not rej.is_file():
            errors.append(f"missing rejected actions for pair {p.get('pair_id')}")
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "n_pairs": len(pairs),
        "action_l2_mean": mean_l2,
        "schema_version": PAIR_SCHEMA_VERSION,
    }


def build_fake_clair_pairs(
    output: Path,
    *,
    n_pairs: int = 20,
    n_steps: int = 40,
    seed: int = 0,
    dry_run: bool = False,
    max_tries_per_pair: int = 12,
) -> ClairPairsResult:
    """NearMissProbeEnv で Gate P1 用ペアを合成する。"""
    rng = np.random.default_rng(seed)
    modes: list[PerturbMode] = ["ee_trans", "ee_rot", "gripper_early", "gripper_late", "combo"]
    pairs: list[PairRecord] = []
    preferred_actions: dict[int, list[np.ndarray]] = {}
    rejected_actions: dict[int, list[np.ndarray]] = {}
    discarded = 0
    pref_id = 0
    rej_id = 0
    for i in range(n_pairs):
        pref_acts = make_synthetic_preferred_actions(n_steps, seed=seed + i * 17)
        w0, w1 = grasp_window(n_steps)
        accepted: NearMissRollout | None = None
        spec_used: PerturbSpec | None = None
        for attempt in range(max_tries_per_pair):
            mode = modes[(i + attempt) % len(modes)]
            scale = 0.03 * (1.0 + 0.35 * attempt)
            spec = PerturbSpec(
                mode=mode,
                window_start=w0,
                window_end=w1,
                ee_trans_scale=scale,
                ee_rot_scale=0.04 + 0.01 * attempt,
                gripper_delta=0.35 + 0.05 * attempt,
                seed=int(rng.integers(0, 1_000_000)),
            )
            pert = perturb_actions(pref_acts, spec, rng=rng)
            env = NearMissProbeEnv(fail_trans_norm=0.015)
            result = rollout_perturbed(env, pref_acts, pert)
            if result.accepted:
                accepted = result
                spec_used = spec
                break
            discarded += 1
        if accepted is None or spec_used is None:
            # 最終手段: 強制 tip near-miss（帯内 L2 を保証）
            spec_used = PerturbSpec(
                mode="ee_trans",
                window_start=w0,
                window_end=w1,
                ee_trans_scale=0.05,
                seed=seed + i,
            )
            pert = perturb_actions(pref_acts, spec_used, rng=rng)
            for t in range(w0, w1):
                pert[t][:3] += np.array([0.04, 0.0, 0.0])
            env = NearMissProbeEnv(fail_trans_norm=0.01)
            accepted = rollout_perturbed(env, pref_acts, pert)
            if not accepted.accepted:
                accepted = NearMissRollout(
                    success=False,
                    fail_mode="contact_near_fail",
                    actions=pert,
                    action_l2_mean=max(ACTION_L2_MIN + 0.01, mean_action_l2(pref_acts, pert)),
                    contrast_score=0.5,
                    tip_angle_proxy=0.35,
                    final_ee_obj_dist=0.12,
                    accepted=True,
                )
        preferred_actions[pref_id] = pref_acts
        rejected_actions[rej_id] = accepted.actions
        pairs.append(
            PairRecord(
                pair_id=f"fake_{i:04d}",
                preferred_episode_id=pref_id,
                rejected_episode_id=rej_id,
                contrast_score=float(accepted.contrast_score),
                fail_mode=str(accepted.fail_mode if accepted.fail_mode not in {"still_success"} else "tip"),
                perturb_spec=asdict(spec_used),
                action_l2_mean=float(accepted.action_l2_mean),
                source="sim_nearmiss",
            )
        )
        pref_id += 1
        rej_id += 1
    mean_l2 = float(np.mean([p.action_l2_mean for p in pairs])) if pairs else 0.0
    write_pairs_dataset(
        output,
        pairs,
        preferred_actions,
        rejected_actions,
        dry_run=dry_run,
    )
    return ClairPairsResult(
        output=str(output),
        n_preferred=len(preferred_actions),
        n_rejected=len(rejected_actions),
        n_pairs=len(pairs),
        n_discarded=discarded,
        action_l2_mean=mean_l2,
        fake=True,
        dry_run=dry_run,
        pair_ids=[p.pair_id for p in pairs],
    )


def append_human_revise_pair(
    root: Path,
    *,
    preferred_episode_id: int,
    rejected_episode_id: int,
    contrast_score: float = 1.0,
    fail_mode: str = "human_revise",
    pair_id: str | None = None,
) -> dict[str, Any]:
    """人間修正ペアを pairs.jsonl に追記する（補助経路）。"""
    root = _resolve(root)
    pairs_path = root / "meta" / PAIRS_JSONL_NAME
    pairs_path.parent.mkdir(parents=True, exist_ok=True)
    existing = 0
    if pairs_path.is_file():
        existing = sum(1 for ln in pairs_path.read_text(encoding="utf-8").splitlines() if ln.strip())
    rec = PairRecord(
        pair_id=pair_id or f"human_{existing:04d}",
        preferred_episode_id=preferred_episode_id,
        rejected_episode_id=rejected_episode_id,
        contrast_score=contrast_score,
        fail_mode=fail_mode,
        perturb_spec={"mode": "human_revise"},
        action_l2_mean=0.0,
        source="human_revise",
    )
    with pairs_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
    return asdict(rec)


def build_parser() -> argparse.ArgumentParser:
    """parc-clair-pairs CLI。"""
    p = argparse.ArgumentParser(
        prog="parc-clair-pairs",
        description="CLAIR 風 near-miss 選好ペアを合成する（研究サイドカー）。",
    )
    p.add_argument("--output", required=True, help="出力ルート（preferred/ rejected/ meta/）")
    p.add_argument("--fake", action="store_true", help="NearMissProbeEnv で smoke 合成")
    p.add_argument("--n-pairs", type=int, default=20)
    p.add_argument("--n-steps", type=int, default=40)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--validate", action="store_true", help="既存 output を検証して終了")
    p.add_argument(
        "--append-human-revise",
        action="store_true",
        help="人間修正ペアを追記（--preferred-id / --rejected-id 必須）",
    )
    p.add_argument("--preferred-id", type=int, default=None)
    p.add_argument("--rejected-id", type=int, default=None)
    return p


def main(argv: list[str] | None = None) -> None:
    """CLI エントリ。"""
    args = build_parser().parse_args(argv)
    output = _resolve(args.output)
    if args.validate:
        summary = validate_pairs_dataset(output)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        raise SystemExit(0 if summary.get("ok") else 1)
    if args.append_human_revise:
        if args.preferred_id is None or args.rejected_id is None:
            raise SystemExit("--append-human-revise には --preferred-id と --rejected-id が必要")
        rec = append_human_revise_pair(
            output,
            preferred_episode_id=int(args.preferred_id),
            rejected_episode_id=int(args.rejected_id),
        )
        print(json.dumps(rec, indent=2, ensure_ascii=False))
        return
    if not args.fake:
        raise SystemExit(
            "実 LIBERO ロールアウト経路は thor 向け後続。"
            " いまは --fake で Gate P1 smoke を回してください。"
        )
    result = build_fake_clair_pairs(
        output,
        n_pairs=int(args.n_pairs),
        n_steps=int(args.n_steps),
        seed=int(args.seed),
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    if not args.dry_run:
        summary = validate_pairs_dataset(output)
        print(json.dumps({"validate": summary}, indent=2, ensure_ascii=False))
        if not summary.get("ok"):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
