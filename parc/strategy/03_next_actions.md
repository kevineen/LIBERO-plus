# 03. 今後実施すべき内容（バックログ）

優先は上から。完了したら `[x]` にして、結果を [02_results_and_findings.md](02_results_and_findings.md) に追記する。

## 進行中

- [x] **thor**: 厚い eval 2 本完了  
  - unfreeze@30k **SR=0.429** / continue@30k(expert-only) **SR=0.286**
- [x] **nuc**: Gate3 `official_aligned` 30k FT — 薄い SR=0.357（`20260728T032038Z_nuc_d9d066c5_…`）
- [ ] **nuc**: Gate3 ckpt 厚い eval — **running**（再投入後）  
  - job: `q_20260728T214414717408+0000_a4209d02` · run `20260728T214421Z_nuc_bec819ac_…`  
  - 済: stale fail / 再起動 / CUDA 復帰 / worker / 再 enqueue

## 直近で打ち切ったもの

- [x] **winpc**: Camera 再レンダ FT（cam-only）  
  - job: `q_20260728T082609607849+0000_04e5d231` · 薄い **SR=0.000**（Camera 5/5 fail）
  - 判断: **同系の即延長はしない**。mix 方法を作り直さない限り再投入しない

## 次にやる（評価・判断）— 優先

- [x] **Camera 動画レビュー（608–612）** — 完了（02 に分類を追記）
- [x] **Camera 耐性 FT の 1 本目（cam-only）** — 完了したが **薄い SR=0.000**、打ち切り
- [x] Camera 再レンダデータ生成（60 eps）
- [x] nuc Gate3 結果を 02 に記録（薄い 0.357 · Camera 等は 0）
- [x] **nuc 厚い eval を復旧**（CUDA 復帰 → worker → 再投入）— 完了待ち
- [x] thor 厚い eval の結果表を 02 に追記（unfreeze 0.429 / continue 0.286）
- [ ] 親 ckpt 再確定（winpc +15k 0.371 vs thor unfreeze 0.429 はレシピ違い注意）
- [ ] 必要なら winpc cam-only `010000` を Camera deep だけ再評価
- [x] winpc +15k の厚い eval（SR=0.371）
- [ ] （任意）+15k で mild 608/609 だけ深掘り

## 次の学習候補（レビュー後）

優先候補（互角なら上）:

1. **混合方法を作り直した視点 OOD 学習**  
   - `cam-only` は 0.000 だったため、そのまま再実行しない  
   - 次にやるなら、CLI 対応の dataset mix / サンプル重み設計 / データ量見直しが前提
2. **lr↓ 短 FT の継続** — 後回し
3. **unfreeze を親に戻す** — thor 厚いで明確勝利時のみ

やらない（現状）:

- [ ] ~~薄い eval だけ見て unfreeze をさらに +30k~~
- [ ] ~~GRPO / GSPO~~（Camera hard=0・Gate-RL 未達）
- [ ] ~~同レシピ +15k をもう一本すぐ~~
- [ ] ~~cam-only rerender FT をそのまま再投入~~（薄い 0.000）
- [ ] ~~色 jitter だけの aug を「Camera 対策」と呼ぶ~~（幾何視点が主因）

## インフラ / Fleet

- [x] thor `hosts.yaml` に winpc 追加（Port 2222 + deploy key）
- [x] nuc キュー復旧（stale fail / 重複 cancel / WSL GPU 復帰 / worker 再起動）— 2026-07-28
- [x] nuc の `official_aligned` 結果を確認し、Gate3 再現の有無を 02 に記録（薄い 0.357）
- [ ] 必要なら `hosts.example.yaml` / docs に winpc Port 2222 パターンを追記
- [ ] nuc の SSH（thor→nuc / Windows `100.77.194.30`）を安定化。必要なら winpc と同様の鍵整備
## コンペ準備（中長期）

- [ ] 公式提出テンプレ到着後: I/O アダプタ・`pack_submission`（→ `docs/06_competition.md`）
- [ ] suite 拡張（object / goal / libero_10）は spatial で SR 安定後
- [ ] 本選モデル（Pi0 / Gr00t）は評価パイプライン維持のまま backend 差し替え

## 完了後の更新手順

1. `parc-queue status` / Fleet Runs で数値確定  
2. 02 の表を更新  
3. このファイルのチェックを更新し、次の 1 本だけ enqueue  
4. 01 のスナップショット日付を更新
