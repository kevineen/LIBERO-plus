"""GRPO / GSPO 風オンライン RL（LIBERO-plus success 報酬）。

連続アクションの対角ガウス方策向け最小実装。
- GRPO: action 次元を token とみなし token-level ratio + clip
- GSPO: 軌道全体の sequence-level ratio（長さ正規化）+ clip
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def _group_advantages(rewards: list[float]) -> np.ndarray:
    """グループ内正規化 advantage。"""
    r = np.asarray(rewards, dtype=np.float64)
    if r.size == 0:
        return r
    mean = r.mean()
    std = r.std()
    if std < 1e-6:
        return r - mean
    return (r - mean) / (std + 1e-6)


def run_grpo_gspo_training(config: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """rollout → group advantage → clipped PG 更新ループ。"""
    import torch
    from libero.libero import benchmark

    from parc.env.make_env import make_offscreen_env, select_task_ids
    from parc.policies.gaussian_mlp import GaussianMLPPolicy, _obs_state

    train_cfg = config.get("train") or {}
    backend = str(train_cfg.get("backend", "grpo"))
    is_gspo = backend == "gspo" or str(train_cfg.get("importance_sampling_level", "")) == "sequence"

    seed = int(config.get("seed", 0))
    torch.manual_seed(seed)
    np.random.seed(seed)

    group_size = int(train_cfg.get("group_size", 4))
    updates = int(train_cfg.get("updates", train_cfg.get("steps", 20)))
    lr = float(train_cfg.get("lr", 1e-4))
    clip_eps = float(train_cfg.get("clip_eps", 0.2))
    kl_coef = float(train_cfg.get("kl_coef", 0.01))
    max_steps = int((config.get("eval") or {}).get("max_steps", 50))
    cam_h = int((config.get("eval") or {}).get("camera_height", 128))
    cam_w = int((config.get("eval") or {}).get("camera_width", 128))
    suite = str((config.get("eval") or {}).get("suite", "libero_spatial"))
    save_rollouts = bool(train_cfg.get("save_rollouts", False))
    eval_every = int(train_cfg.get("eval_every", max(1, updates // 5)))

    eval_cfg = config.get("eval") or {}
    task_ids = select_task_ids(
        suite,
        task_ids=list(eval_cfg["task_ids"]) if eval_cfg.get("task_ids") is not None else None,
        tasks_per_category=int(eval_cfg["tasks_per_category"])
        if eval_cfg.get("tasks_per_category") is not None
        else None,
    )
    if not task_ids:
        task_ids = [0]

    init_path = train_cfg.get("init_policy_path") or (config.get("policy") or {}).get("path")
    policy = GaussianMLPPolicy(
        path=init_path,
        state_dim=int(train_cfg.get("state_dim", 8)),
        action_dim=int(train_cfg.get("action_dim", 7)),
        hidden=int(train_cfg.get("hidden", 128)),
        device=train_cfg.get("device"),
        deterministic=False,
    )
    # 参照方策（周期スナップショット）
    ref = GaussianMLPPolicy(
        path=None,
        state_dim=policy.state_dim,
        action_dim=policy.action_dim,
        hidden=int(train_cfg.get("hidden", 128)),
        device=str(policy.device),
    )
    ref.net.load_state_dict(policy.net.state_dict())
    ref.net.eval()
    for p in ref.net.parameters():
        p.requires_grad_(False)

    opt = torch.optim.Adam(policy.net.parameters(), lr=lr)

    bench_cls = benchmark.get_benchmark(suite)
    bench = bench_cls()

    # torch.load 互換（LIBERO init）
    _orig_load = torch.load

    def _load_trusted(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("weights_only", False)
        return _orig_load(*args, **kwargs)

    torch.load = _load_trusted  # type: ignore[assignment]

    history: list[dict[str, Any]] = []
    out_dir = run_dir / "train_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    best_sr = -1.0
    best_dir = out_dir / "pretrained_model"

    try:
        for upd in range(updates):
            # タスクをラウンドロビン
            task_id = int(task_ids[upd % len(task_ids)])
            task = bench.get_task(task_id)
            bddl = bench.get_task_bddl_file_path(task_id)
            init_states = bench.get_task_init_states(task_id)
            lang = str(getattr(task, "language", "") or "")

            env = make_offscreen_env(bddl, camera_heights=cam_h, camera_widths=cam_w)
            group_rewards: list[float] = []
            group_trajs: list[dict[str, Any]] = []
            try:
                for g in range(group_size):
                    init = init_states[g % len(init_states)]
                    # 軌道収集（状態・アクション）
                    policy.reset()
                    env.reset()
                    obs = env.set_init_state(init)
                    states: list[np.ndarray] = []
                    actions: list[np.ndarray] = []
                    success = False
                    steps = 0
                    for t in range(max_steps):
                        if lang:
                            obs = dict(obs)
                            obs["task"] = lang
                        s = _obs_state(obs, policy.state_dim)
                        a = policy.act(obs)
                        states.append(s)
                        actions.append(a)
                        obs, reward, done, info = env.step(a.tolist())
                        steps = t + 1
                        if bool(done) or float(reward) > 0.5 or bool(info.get("success", False)):
                            success = True
                            break
                        check = getattr(env, "check_success", None)
                        if callable(check) and bool(check()):
                            success = True
                            break
                    r = 1.0 if success else 0.0
                    group_rewards.append(r)
                    group_trajs.append(
                        {
                            "states": np.asarray(states, dtype=np.float32),
                            "actions": np.asarray(actions, dtype=np.float32),
                            "reward": r,
                            "steps": steps,
                        }
                    )
            finally:
                env.close()

            adv = _group_advantages(group_rewards)
            # 旧方策 logprob（importance 用）— 更新前のスナップショット
            old = GaussianMLPPolicy(
                path=None,
                state_dim=policy.state_dim,
                action_dim=policy.action_dim,
                hidden=int(train_cfg.get("hidden", 128)),
                device=str(policy.device),
            )
            old.net.load_state_dict(policy.net.state_dict())
            old.net.eval()
            for p in old.net.parameters():
                p.requires_grad_(False)

            opt.zero_grad()
            losses = []
            for traj, advantage in zip(group_trajs, adv):
                if traj["states"].shape[0] == 0:
                    continue
                st = torch.as_tensor(traj["states"], device=policy.device)
                ac = torch.as_tensor(traj["actions"], device=policy.device)
                logp = policy.log_prob_actions(st, ac)  # (T, A)
                with torch.no_grad():
                    logp_old = old.log_prob_actions(st, ac)
                    logp_ref = ref.log_prob_actions(st, ac)

                if is_gspo:
                    # sequence-level: sum_t sum_a logπ / |y|
                    seq_new = logp.sum() / max(1, logp.numel())
                    seq_old = logp_old.sum() / max(1, logp_old.numel())
                    ratio = torch.exp(seq_new - seq_old)
                    clipped = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps)
                    pg = -torch.min(ratio * float(advantage), clipped * float(advantage))
                    kl = (seq_old - seq_new).abs()  # 簡易
                    loss = pg + kl_coef * kl
                else:
                    # GRPO token-level
                    ratio = torch.exp(logp - logp_old)
                    clipped = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps)
                    adv_t = torch.as_tensor(advantage, device=policy.device, dtype=ratio.dtype)
                    pg = -torch.min(ratio * adv_t, clipped * adv_t).mean()
                    kl = (logp_old - logp).mean().abs()
                    loss = pg + kl_coef * kl
                losses.append(loss)

            if losses:
                total = torch.stack(losses).mean()
                total.backward()
                torch.nn.utils.clip_grad_norm_(policy.net.parameters(), 1.0)
                opt.step()
                loss_v = float(total.detach().cpu())
            else:
                loss_v = 0.0

            # 参照方策の周期更新
            if (upd + 1) % max(1, int(train_cfg.get("ref_update_every", 5))) == 0:
                ref.net.load_state_dict(policy.net.state_dict())

            mean_r = float(np.mean(group_rewards)) if group_rewards else 0.0
            row = {
                "update": upd,
                "task_id": task_id,
                "mean_reward": mean_r,
                "loss": loss_v,
                "backend": "gspo" if is_gspo else "grpo",
            }
            history.append(row)
            (run_dir / "logs" / "rl_history.jsonl").open("a").write(
                json.dumps(row, ensure_ascii=False) + "\n"
            )

            if not save_rollouts:
                # 生 trajectory は保持しない
                group_trajs.clear()

            # 定期保存 + best
            if (upd + 1) % eval_every == 0 or upd == updates - 1:
                ckpt_dir = out_dir / "pretrained_model"
                policy.save(ckpt_dir)
                if mean_r >= best_sr:
                    best_sr = mean_r
                    best_dir = ckpt_dir
                    policy.save(out_dir / "best_pretrained_model")

    finally:
        torch.load = _orig_load  # type: ignore[assignment]

    # 最終 ckpt
    final_dir = policy.save(out_dir / "pretrained_model")
    (run_dir / "logs" / "rl_summary.json").write_text(
        json.dumps(
            {
                "updates": updates,
                "backend": "gspo" if is_gspo else "grpo",
                "best_mean_reward": best_sr,
                "history_tail": history[-10:],
                "checkpoint": str(final_dir),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return {
        "status": "finished",
        "backend": "gspo" if is_gspo else "grpo",
        "updates": updates,
        "best_mean_reward": best_sr,
        "checkpoint": str(final_dir),
        "best_checkpoint": str(best_dir),
    }
