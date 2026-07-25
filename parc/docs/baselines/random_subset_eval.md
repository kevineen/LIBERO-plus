# ランダム方策カテゴリ横断ベースライン（subset_eval）

- 日付: 2026-07-25
- run: `experiments/20260724T163417Z_subset_eval`
- policy: `random`
- suite: `libero_spatial`
- `tasks_per_category`: 2（7 カテゴリ × 2 = 14 episodes）
- `num_trials_per_task`: 1
- `max_steps`: 280

| Category | n | success_rate | mean_steps |
|----------|---|--------------|------------|
| Background Textures | 2 | 0.000 | 280.0 |
| Camera Viewpoints | 2 | 0.000 | 280.0 |
| Language Instructions | 2 | 0.000 | 280.0 |
| Light Conditions | 2 | 0.000 | 280.0 |
| Objects Layout | 2 | 0.000 | 280.0 |
| Robot Initial States | 2 | 0.000 | 280.0 |
| Sensor Noise | 2 | 0.000 | 280.0 |
| **Overall** | **14** | **0.000** | **280.0** |

ランダム方策なので成功率 0 は正常。評価パイプライン・カテゴリ集計が動くことの確認用。
学習済み方策を載せたあとの比較基準にする。
