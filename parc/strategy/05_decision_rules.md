# 05. 判断ルール

方針がぶれないよう、数値の見方と「やってよい / だめ」を固定する。

## Eval の信頼度

| 種類 | 設定目安 | 用途 |
|------|----------|------|
| 薄い | `tasks_per_category: 2`（n≈14） | 学習直後のスモーク・並びの荒い確認 |
| 厚い | `tasks_per_category: 5`（n≈35） | **親 ckpt 決定・延長の可否** |
| 深掘り | 特定 `task_ids` + `num_trials_per_task`↑ | 弱点カテゴリの失敗モード確認 |

ルール:

1. **薄い eval だけで次の長い FT / RL を決めない**
2. 薄いと厚いで順位が逆転したら **厚いを正**とする（2026-07-28 に実例あり）
3. カテゴリ SR=0 が厚いでも続くなら、同レシピ延長より **データ / aug / 深掘り** を優先

## Gate（社内運用）

| Gate | 条件（目安） | 意味 |
|------|----------------|------|
| Gate1 | smoke / パイプラインが通る | 環境 OK |
| Gate2 | subset eval で SR > 0 | 学習が何か解けている |
| Gate3 | 別マシンで同レシピ再現 | 偶然でない |
| Gate-RL | 厚い eval で全体 SR に余裕 + 最悪カテゴリが極端ゼロでない | GRPO 等を開始してよい |

現状（2026-08-01）: Gate2/3 OK。**親 = continue10k**（厚い 0.514 · Cam deep **0.20**）。lr↓5k / mix v2 / Phase B / **Phase A'** はいずれも敗北 → **親維持**。**Gate-RL 未達**。

### cam 軸（再レンダ短 FT）— 禁止

continue10k からの cam mix 短 FT（比率高低・hard-near 含む）は **全体 forgetting** が再現した。  
**Phase D 以降、cam 再レンダ系の学習投入はしない**（cam-only / mix v2–v4 延長 / exact hard リーク実験も当面禁止）。  
Camera は親の現状天井として記録し、改善は **非 cam 軸**（Language / Sensor / VR 新データ / 将来 Pi0）に限定する。


## 学習レシピ

- 採用ベース: **official_aligned**（`expert_width_multiplier=0.5`、Instruct VLM、480 幅系）
- 使わない: width 未整合の旧 `from_official_*`、SR0 だった `continue_unfreeze50k` 延長
- unfreeze 時は lr を下げる（例 2e-5）。微調整はさらに下げる（例 1e-5）
- Resume より **ckpt path を明示した新規 YAML** を優先（HF path 差し替え事故防止）

## 投入のしかた

- 1 マシンに同時に重い train を複数積まない（eval ならキュー直列で可）
- **重いジョブ（長時間 GPU / EGL 再レンダ / 厚い・深掘り）の既定は thor**（ネイティブ GPU）。詳細は `04`
- winpc（WSL）・nuc（WSL）で長時間 EGL 再レンダをしない（BSOD `dxgmms2`/`vmmem` 実績あり）
- 空き埋め: nuc/thor に **再現 or 厚い/深掘り eval**。短 FT は winpc（承認後）
- 完了通知を見るときは Discord の **`PARC · <machine>`** と `machine=` を信じる（旧通知の表示名事故に注意）

## 親 ckpt の更新条件

新しい ckpt を親にするのは次をすべて満たすとき:

1. 厚い eval の全体 SR が現行親以上（またはカテゴリ弱点が明確に改善）
2. Camera / Sensor など最悪カテゴリが「全部ゼロのまま悪化のみ」でない
3. 再現（別マシン or 再 eval）で同傾向

満たさなければ親を維持し、別軸（データ・aug）を試す。
