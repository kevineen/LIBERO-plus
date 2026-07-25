# SmolVLA checkpoint スモーク評価

- 日付: 2026-07-25
- run: `experiments/20260724T171936Z_smolvla_ckpt_smoke_eval`
- コマンド: `bash scripts/eval_ckpt.sh configs/experiments/smolvla_ckpt_smoke_eval.yaml`
- checkpoint: `20260724T164040Z_smolvla_ft_smoke` @ step 200
- suite: `libero_spatial` / `task_ids: [0]` / `max_steps: 50`
- 結果: **SR=0.0**（1 episode、50 steps）— 200 step FT + 短い horizon では成功しないのが正常
- 確認できたこと: LeRobot ckpt → `policy.type=checkpoint` → LIBERO-plus OffScreenRenderEnv の接続

## 再現

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
bash scripts/eval_ckpt.sh configs/experiments/smolvla_ckpt_smoke_eval.yaml
```

通常の `scripts/parc.sh`（LIBERO-plus `.venv`）では lerobot が無いので、checkpoint 評価は必ず `eval_ckpt.sh`（robot venv）を使う。

## 次のステップ

- `steps` を増やした FT（例: 10k）後、同 YAML の `path` を差し替えて subset_eval 相当で比較
- `max_steps: 280`、`tasks_per_category: 2` に広げるとランダム baseline と比較可能
