# 03. 今後実施すべき内容（バックログ）

優先は上から。完了したら `[x]` にして、結果を [02_results_and_findings.md](02_results_and_findings.md) に追記する。

## 進行中

- [ ] **winpc**: continue@30k から +15k finetune（lr=1e-5）完了を待つ  
  - config: `smolvla_ft_continue30k_finetune15k_winpc.yaml`  
  - 完了後: **薄い eval → 厚い eval（tpc=5）** の順で親と比較
- [ ] **thor**: 厚い eval 2 本完了を待つ  
  - unfreeze@30k / continue@30k（expert-only）  
  - winpc 厚い結果と並べ、マシン間で逆転が再現するか確認

## 次にやる（評価・判断）

- [ ] thor 厚い eval の結果表を 02 に追記し、**親 ckpt を再確定**
- [ ] winpc +15k の厚い eval（親 continue@30k 厚い 0.31 と比較）
- [ ] Camera 動画レビュー（task 610–612）— 失敗モード分類（視点ずれ / 把持 / 言語無視 等）
- [ ] 必要なら Camera 深掘りを thor の親候補でも実行

## 次の学習候補（厚い eval 後に選ぶ）

優先候補（互角なら上）:

1. **lr↓ 短 FT の継続**（例 +10–15k / 1e-5）— +15k 結果が改善していれば
2. **Camera / Sensor 向け** — デモ追加・視点 aug・ノイズ aug（学習レシピ変更）
3. **unfreeze を親に戻す** — thor 厚い eval で unfreeze が明確に勝つ場合のみ

やらない（現状）:

- [ ] ~~薄い eval だけ見て unfreeze をさらに +30k~~
- [ ] ~~GRPO / GSPO~~（Camera≈0・全体 SR≈0.3 のままでは見送り。目安は [05_decision_rules.md](05_decision_rules.md)）

## インフラ / Fleet

- [x] thor `hosts.yaml` に winpc 追加（Port 2222 + deploy key）
- [ ] nuc の SSH（thor→nuc）を安定化。必要なら winpc と同様の鍵整備
- [ ] nuc の `official_aligned` 結果を確認し、Gate3 再現の有無を 02 に記録
- [ ] 必要なら `hosts.example.yaml` / docs に winpc Port 2222 パターンを追記

## コンペ準備（中長期）

- [ ] 公式提出テンプレ到着後: I/O アダプタ・`pack_submission`（→ `docs/06_competition.md`）
- [ ] suite 拡張（object / goal / libero_10）は spatial で SR 安定後
- [ ] 本選モデル（Pi0 / Gr00t）は評価パイプライン維持のまま backend 差し替え

## 完了後の更新手順

1. `parc-queue status` / Fleet Runs で数値確定  
2. 02 の表を更新  
3. このファイルのチェックを更新し、次の 1 本だけ enqueue  
4. 01 のスナップショット日付を更新
