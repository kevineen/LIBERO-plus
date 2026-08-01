"""CLAIR near-miss / pairs schema の単体テスト。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from parc.data.clair_nearmiss import (
    ACTION_L2_MAX,
    ACTION_L2_MIN,
    NearMissProbeEnv,
    PerturbSpec,
    append_human_revise_pair,
    build_fake_clair_pairs,
    classify_fail_mode,
    contrast_score_physics,
    grasp_window,
    mean_action_l2,
    perturb_actions,
    rollout_perturbed,
    validate_pairs_dataset,
)


def test_perturb_actions_local_window() -> None:
    actions = [np.zeros(7, dtype=np.float64) for _ in range(20)]
    spec = PerturbSpec(mode="ee_trans", window_start=8, window_end=12, ee_trans_scale=0.05, seed=0)
    out = perturb_actions(actions, spec)
    # 窓外はほぼゼロ
    assert float(np.linalg.norm(out[0][:3])) < 1e-9
    assert float(np.linalg.norm(out[9][:3])) > 0.0


def test_contrast_and_fail_mode_band() -> None:
    score = contrast_score_physics(
        action_l2_mean=0.25,
        tip_angle_proxy=0.4,
        final_ee_obj_dist=0.1,
        success=False,
    )
    assert score > 0.15
    mode = classify_fail_mode(
        success=False,
        action_l2_mean=0.25,
        tip_angle_proxy=0.4,
        final_ee_obj_dist=0.1,
        diverged_early=False,
    )
    assert mode == "tip"
    assert classify_fail_mode(
        success=False,
        action_l2_mean=3.0,
        tip_angle_proxy=0.0,
        final_ee_obj_dist=1.0,
        diverged_early=True,
    ) == "far_diverge"


def test_rollout_nearmiss_probe() -> None:
    pref = [np.zeros(7, dtype=np.float64) for _ in range(16)]
    w0, w1 = grasp_window(16)
    spec = PerturbSpec(mode="ee_trans", window_start=w0, window_end=w1, ee_trans_scale=0.05, seed=1)
    pert = perturb_actions(pref, spec)
    env = NearMissProbeEnv(fail_trans_norm=0.01)
    result = rollout_perturbed(env, pref, pert)
    assert result.success is False
    assert result.action_l2_mean > 0.0


def test_build_fake_clair_pairs_gate_p1(tmp_path: Path) -> None:
    out = tmp_path / "clair_pairs"
    result = build_fake_clair_pairs(out, n_pairs=20, n_steps=32, seed=0)
    assert result.n_pairs == 20
    assert ACTION_L2_MIN <= result.action_l2_mean <= ACTION_L2_MAX
    summary = validate_pairs_dataset(out)
    assert summary["ok"] is True
    assert summary["n_pairs"] == 20


def test_append_human_revise(tmp_path: Path) -> None:
    out = tmp_path / "clair_pairs"
    build_fake_clair_pairs(out, n_pairs=2, n_steps=16, seed=1)
    rec = append_human_revise_pair(out, preferred_episode_id=0, rejected_episode_id=0)
    assert rec["source"] == "human_revise"
    summary = validate_pairs_dataset(out)
    # human 行は action_l2=0 で平均帯を崩し得る → preferred/rejected ファイルは存在する
    assert summary["n_pairs"] == 3
    assert (out / "meta" / "pairs.jsonl").is_file()


def test_mean_action_l2() -> None:
    a = [np.ones(7)]
    b = [np.zeros(7)]
    assert mean_action_l2(a, b) == np.sqrt(7.0)
