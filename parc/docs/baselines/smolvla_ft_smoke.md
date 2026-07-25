# SmolVLA smoke FT（200 steps）

- 日付: 2026-07-25
- run: `experiments/20260724T164040Z_smolvla_ft_smoke`
- コマンド: `bash scripts/train.sh configs/experiments/smolvla_ft_smoke.yaml`
- dataset: `lerobot/libero_plus`（約 15GB キャッシュ、14,347 episodes / 2.2M frames）
- policy: SmolVLA（VLM: SmolVLM2-500M、学習可能パラメータ ~100M）
- 結果: **finished**（約 5.7 step/s on NVIDIA Thor）
- 最終: `loss≈1.775` @ step 200
- checkpoint:
  `train_output/checkpoints/000200/pretrained_model/`

## 再現

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
bash scripts/train.sh configs/experiments/smolvla_ft_smoke.yaml
```

本番スケールは `steps` を増やした YAML をコピーして使う。

チェックポイント評価:

```bash
bash scripts/eval_ckpt.sh configs/experiments/smolvla_ckpt_smoke_eval.yaml
```

詳細は `docs/baselines/smolvla_ckpt_smoke_eval.md`。
