# 03. 今後実施すべき内容（バックログ）

優先は上から。完了したら `[x]` にして、結果を [02_results_and_findings.md](02_results_and_findings.md) に追記する。

## 進行中

- [x] **thor**: 厚い eval 2 本完了（unfreeze 0.429 / continue expert 0.286）
- [x] **nuc**: Gate3 薄い 0.357 · 厚い **0.257**
- [x] **親 ckpt クロス厚い** — 完了  
  - +15k on thor **0.343** · unfreeze on winpc **0.400** → 当時親 = thor unfreeze
- [x] **thor**: Camera deep unfreeze（608–612×10）— **SR=0.08**  
  - job `q_20260729T093137…4e2a1fe6` · run `20260729T093144Z_thor_fa549217_…`  
  - 608:0.20 · 609:0.10 · 610–611:0 · 612:0.10（continue 深掘り 0.16 より弱い）
- [x] **thor**: +15k mild Camera deep（608/609×10）— **SR=0.30**  
  - 608:0.40 · 609:0.20 · run `20260729T174037Z_thor_abf2aca9_…`
- [x] **thor**: 弱点深掘りバッチ — **完了**  
  - Sensor 0.20 · Language 0.20 · RobotInit 0.16 · continue Cam 0.04 · +15k Cam 0.12
- [x] **フォロー評価（2026-07-30）** — thor 側完了（Lang hard / +15k Cam hard）
- [x] **mix10k 評価（thor）** — 完了  
  - Camera deep **0.12** · `20260730T043236Z_thor_36e4bb0a_…`  
  - 厚い **0.514** · `20260730T044841Z_thor_db324def_…`
- [x] **winpc: mix continue +10k** — 完了  
  - job `q_20260730T070854…a66dc81d` · run `20260730T071018Z_winpc_cbbf5c8b_…` · ckpt `010000`  
  - 薄い Cam-only smoke **SR=0.000**（親決めに使わない）
- [x] **thor: continue10k 厚い + Camera deep** — 完了  
  - thick **0.514** · `q_…7903a580` · `20260730T090125Z_thor_2798bc08_…`  
  - Cam deep **0.20** · `q_…72667de5` · `20260730T091211Z_thor_ea7c443f_…`  
  - → **親 = continue10k**（厚い同点 · Cam deep 改善）
- [x] **winpc: lr↓ 短 FT**（5e-6 · +5k · 同 mix）— **完了**  
  - job `q_20260730T184655…380a43e2` · run `20260730T184742Z_winpc_c7e7c8f2_…` · ckpt `005000`  
  - 薄い smoke **SR=0.500**（Camera 0.000 · 親決め未使用）
- [x] **thor: lr↓5k 厚い + Camera deep** — **完了（親未満）**  
  - thick **0.371** · `q_…8aa312ee` · `20260730T200910Z_thor_a4d14910_…`  
  - Cam deep **0.14** · `q_…3283952d` · `20260730T202113Z_thor_fded971f_…`  
  - → **親 = continue10k 維持** · lr↓ 同軸延長は打ち切り
- [x] **winpc: mix v2 Phase A**（base120+cam60 · +5k · 1e-5 · from continue10k）— **完了・敗北**  
  - job `q_20260730T220954…a908742f` · run `20260730T221003Z_winpc_c9dc1b28_…` · ckpt `005000`  
  - 薄い **SR=0.571**（Cam/Lang **0.000** · 親決め未使用）
- [x] **thor: mix v2 厚い + Camera deep** — **完了（親未満）**  
  - thick **0.400** · `q_…c054cdce` · `20260730T231841Z_thor_907a8bc1_…`  
  - Cam deep **0.10** · `q_…3e13c45d` · `20260730T233024Z_thor_5ba94471_…`  
  - → 親維持 · **Phase B（cam 増量）へ**
- [x] **nuc: continue10k 薄い cross** — 完了 · **SR=0.143**（親決め不使用 · 02 追記）
- [x] **nuc: unfreeze 薄い**（TdrDelay 後 requeue）— 完了 · **SR=0.571**（winpc/thor 薄と一致）
- [x] **thor: continue10k Sensor/Language 深掘り** — 完了 · Sensor **0.16** · Language **0.32**
- [x] **nuc: continue10k 厚い cross** — 完了 · **SR=0.371**（thor 0.514 より低 · 親維持）
- [x] **Phase C: Camera 診断 + 空き埋め** — C1/C2 完了  
  - 仕様: [2026-08-01-phase-c-cam-diagnosis-design.md](../docs/superpowers/specs/2026-08-01-phase-c-cam-diagnosis-design.md)  
  - C2: Language deep **0.20** · Sensor deep **0.24**（`q_…7bbbffb5` · 親決め禁止）  
- [x] **Phase A' FT on thor** — **敗北 · 親維持**  
  - thick **0.286** · Cam deep **0.06** → **cam 軸短 FT 打ち切り**
- [ ] **Phase D: 軸転換** — **D1 Stage2 running · D2 診断完了 · D3 並行**  
  - 正本: [phase-d design](../docs/superpowers/specs/2026-08-01-phase-d-axis-pivot-design.md) · [D1/D3 plan](../docs/superpowers/plans/2026-08-01-phase-d1-language-d3-vr.md)  
  - **D1 thor:** Language hard deep **done** SR=**0.10**（984/986=0 · 988=0.30）`q_…70c96dab` · `20260731T212845Z_thor_ce07fdf3_…`  
  - **D1 続:** Molmo Language hard **1.000** / 厚い **1.000**（親判定外 · 完了）· ラベル置換 FT は別承認  
  - **D1 二段階 Stage1（done）:** `q_20260802T210926…fce856bb` · run `20260802T210934Z_thor_72c5af3f_…` · 薄い Lang hard **SR=0.000** · ckpt `005000` · **親判定外**  
  - **D1 Evo-1 Language hard thin（done）:** SR=**0.000**（984/986/988×1）· [baselines/evo1](../docs/baselines/evo1/) · flash-attn 無し · **親判定外**  
  - **D1 Stage2（承認済 · running）:** `q_20260804T033323…edf56815` · `sidecar_smolvla_ft_twostage_stage2_full_from_stage1_thor.yaml` · 10k · from Stage1 `005000` · 薄い Lang hard smoke · **親判定外**  
  - **D1 残:** ラベル置換 FT / Evo-1 ×10 は未着手  
  - **D2 thor:** Sensor hard deep **done** SR=**0.20** · `q_…369f498f` · `20260802T225414Z_thor_ec7286b4_…`（1375:0.40 · 1377:0.10 · 1378:0.10 · 親決め禁止）· Sensor 短 FT は別承認  
  - **失敗診断ツール:** SmolVLA `save_attention`（activation/Grad-CAM · 失敗時のみ）配線済 · smoke `…695f9fc9_…` · [docs/04_eval](../docs/04_eval.md)  
  - **D3 mainpc:** VR Quest E2E 準備（Unity/Quest 手作業）  
  - cam FT **禁止**
- [x] **Phase B: cam 増量** — **完了・敗北（親維持）**  
  - 再レンダ / convert / mix / 短 FT 完了 · ckpt `…3fa4d513…/005000`  
  - 薄い 0.214（親決め未使用）  
  - 厚い **0.143** · `q_…47040774` · `20260731T170913Z_thor_3c7af49e_…`  
  - Cam deep **0.00** · `q_…175e0e55` · `20260731T172239Z_thor_908a45cb_…`（608–612 全敗）  
  - vs continue10k 0.514 / 0.20 → **同軸延長打ち切り**  
  - 1回目 FT は wrist AV1 破損で failed@3527 → 修復後再走で完走
- [x] **nuc: Language deep クロス（空き埋め）** — **SR=0.20** · `q_…feddce52` · `20260731T172230Z_nuc_9bcfd033_…`（thor 0.32）

## 直近で打ち切ったもの

- [x] **winpc**: Camera 再レンダ FT（cam-only）  
  - job: `q_20260728T082609607849+0000_04e5d231` · 薄い **SR=0.000**（Camera 5/5 fail）
  - 判断: **同系の即延長はしない**。mix 方法を作り直さない限り再投入しない
- [x] **winpc**: lr↓5k（5e-6 · +5k · 同 mix）  
  - 厚い 0.371 / Cam 0.14 < continue10k → **同レシピ延長打ち切り**
- [x] **mix v2 reweight**（base120+cam60）  
  - 厚い 0.400 / Cam 0.10 < continue10k → **重み変更だけでは不足**
- [x] **Phase B cam×120 mix v3 短 FT**  
  - 厚い 0.143 / Cam deep 0.00 < continue10k → **cam 増量短 FT 打ち切り**

## 次にやる（評価・判断）— 優先

- [x] **Camera 動画レビュー（608–612）** — 完了（02 に分類を追記）
- [x] **Camera 耐性 FT の 1 本目（cam-only）** — 完了したが **薄い SR=0.000**、打ち切り
- [x] Camera 再レンダデータ生成（60 eps）
- [x] nuc Gate3 結果を 02 に記録（薄い 0.357 · Camera 等は 0）
- [x] **nuc 厚い eval を復旧**（CUDA 復帰 → worker → 再投入）— **SR=0.257 完了**
- [x] thor 厚い eval の結果表を 02 に追記（unfreeze 0.429 / continue 0.286）
- [x] nuc Gate3 厚い結果を 02 に記録（0.257）
- [x] **親 ckpt 再確定** — 親 = **thor unfreeze@30k**（cross 0.400 ≥ +15k）
- [x] thor unfreeze Camera deep（SR=0.08 · continue 0.16 より弱）
- [x] （任意）+15k mild 608/609 深掘り — **SR=0.30**
- [x] 弱点深掘りバッチ記録（Sensor/Language/Robot/+15k Cam）
- [x] **dataset mix CLI** + **mix FT@10k winpc 完了**  
  - job `q_20260730T023633…a5076171` · run `20260730T023701Z_winpc_6133f628_…` · ckpt `010000`
- [x] **mix10k 評価（thor）** — 厚い 0.514 / Cam deep 0.12
- [x] **mix continue10k 学習** — 完了（薄い Cam smoke 0.000）
- [x] **thor: continue10k 厚い + Camera deep** — 完了 → **親 = continue10k**
- [x] **winpc: lr↓ 短 FT**（5e-6 · +5k）— 完了 · 薄い 0.500 · **厚いで敗北**
- [x] **thor: lr↓5k 厚い + Camera deep** — 完了 · 親維持
- [x] **mix 再設計 Phase A**（base120+cam60）— 完了 · 厚い 0.400 / Cam 0.10 · **敗北**
- [ ] **Phase B: cam 増量再レンダ → mix → 短 FT** — **次の主線**
- [x] （任意・空き埋め）continue10k の Sensor/Language 深掘りを thor で補強 — Sensor 0.16 · Lang 0.32
- [x] nuc continue10k 厚い cross — **0.371**（親維持）
- [ ] **nuc: continue10k Camera deep** — **投入** `q_20260731T060055…5937c732`（vs thor 0.20 · 親決め不使用）
- [ ] 必要なら winpc cam-only `010000` を Camera deep だけ再評価（優先低）

## 次の学習候補（レビュー後）

優先候補（互角なら上）:

1. ~~continue10k の thor 結果待ち~~ — 完了 · 親確定
2. ~~lr↓ 短 FT~~ — **敗北・打ち切り**
3. ~~mix v2 reweight~~ — **敗北・打ち切り**
4. **~~Phase B cam 増量~~** — **敗北・打ち切り**（thick 0.143 / Cam 0.00）
5. （要相談）親 continue10k のまま **別軸**（aug / 別 mix 設計 / 弱点カテゴリ以外のデータ）
6. （任意）親 continue10k の弱点深掘りだけ追加

やらない（現状）:

- [ ] ~~薄い eval だけ見て unfreeze をさらに +30k~~
- [ ] ~~GRPO / GSPO~~（Camera hard=0・Gate-RL 未達）
- [ ] ~~同レシピ +15k をもう一本すぐ~~
- [ ] ~~cam-only rerender FT をそのまま再投入~~（薄い 0.000）
- [ ] ~~lr↓5k のさらなる延長~~（厚いで親未満）
- [ ] ~~mix v2 のさらなる同軸延長~~（厚いで親未満）
- [ ] ~~Phase B mix v3 のさらなる同軸延長~~（厚いで親未満 · Cam 全敗）
- [ ] ~~色 jitter だけの aug を「Camera 対策」と呼ぶ~~（幾何視点が主因）

## インフラ / Fleet

- [x] thor `hosts.yaml` に winpc 追加（Port 2222 + deploy key）
- [x] nuc キュー復旧（stale fail / 重複 cancel / WSL GPU 復帰 / worker 再起動）— 2026-07-28
- [x] nuc の `official_aligned` 結果を確認し、Gate3 再現の有無を 02 に記録（薄い 0.357）
- [x] **VR teleop Phase 1（コード）** — `parc-vr-teleop` / Unity 薄クライアント / `feature/vr-teleop/`  
  - 運用: [docs/12_vr_teleop.md](../docs/12_vr_teleop.md)
  - 残: Quest 実機 E2E・LeRobot 永続化確認（robot venv）
- [x] **VR データ品質 M1–M4（ソフト）** — 2026-07-31  
  - M1 `parc-filter-demos` success-only / M2 RTT ゲート / M3 collection_queue / M4 replay + Approx Time  
  - 正本: [feature/vr-teleop/roadmap-data-quality.md](../feature/vr-teleop/roadmap-data-quality.md)  
  - 運用ルール: [docs/02_data.md](../docs/02_data.md)（多環境×少デモ・frame 分割禁止・raw 不変）  
  - **M5 deferred（M0 完了・承認後）:** verify 統計監査 → exclusion log → idle/no-op trim → versioned `stats_key`（この順で固定。先行実装しない）  
  - 参照: [docs/00_research/turbovla_evo1.md](../docs/00_research/turbovla_evo1.md) · roadmap M5 更新 2026-08-03
- [x] **catchup: モデル/データ対応度** — [catchup/05_adaptability.md](../catchup/05_adaptability.md)（2026-07-31）
- [ ] 必要なら `hosts.example.yaml` / docs に winpc Port 2222 パターンを追記
- [ ] nuc の SSH（thor→nuc / Windows `100.77.194.30`）を安定化。必要なら winpc と同様の鍵整備
- [ ] **Quest 実機でデモ 1 本** → `data/datasets/vr_libero_demos` → success-only FT smoke  
  - blocked: Quest / Windows 接続と `PARC_ROBOT_VENV` を使った実保存確認がまだ
  - 学習 YAML: `configs/experiments/smolvla_ft_vr_demos_success_smoke.yaml`

## 将来・本選リスト（いまはやらない）

SmolVLA 主線が Camera/Sensor で頭打ち、または公式 Pi0/Gr00t 学習コードが届いてから着手。  
前提: 評価パイプライン（`parc-eval` / 厚い / 深掘り / Fleet）は維持し **backend だけ差し替え**。  
**ホスト割り振りの正本:** [04_machine_roles.md](04_machine_roles.md)（速度目安・現在表・将来表）。

### マシン割り当て（要約）

| 段階 | thor | nuc | winpc |
|------|------|-----|-------|
| いま（SmolVLA） | 深掘り・厚い **主** | 空き維持 / 軽い再現のみ | 結果後の短 FT |
| Gate1（配布後） | 予備 | **スモーク主** | — |
| B0 ゼロショット厚い | **Pi0** | **Gr00t**（並行） | — |
| B1 軽い FT | eval 受け | — | **train 主** |
| B2 / 提出 | deep eval | 再現 | train + pack |

### Pi0 / Gr00t — ベーススコア＋軽い FT

目標: 「出してすぐの地板」と「短 FT でどこまで伸びるか」を同じ評価尺で固定する。

| 段階 | 内容 | 評価 | 記録先 |
|------|------|------|--------|
| B0 | 公式 ckpt **ゼロショット**（学習なし） | 薄い → 厚いで地板 | 02 に `pi0/gr00t_zero_shot` 行 |
| B1 | **軽い FT**（例: 5k–15k step · lr↓ · 公開 libero_plus のみ） | 薄いスモーク後に厚い | 伸び代 ΔSR = 厚い(B1)−厚い(B0) |
| B2 | （任意）弱点カテゴリだけ短 FT / mix | Camera deep 必須 | cam-only 単体は禁止（SmolVLA 反省） |

比較ルール（SmolVLA と同じ）:

1. **薄いだけでモデル採用・延長しない**
2. 親候補更新は厚い＋最悪カテゴリ（Camera/Sensor 等）を見る
3. Pi0 と Gr00t は **同条件 YAML**（seed / tpc / task_ids）で並べる
4. 本選配布コードの既定レシピを優先。独自 big train は B1 が明確に伸びてから
5. B1 を結果前に両モデルへ投げ得しない（割り振り表どおり）

メモ欄（数値は配布後に埋める）:

```text
Pi0   zero-shot thick SR=____  light-FT thick SR=____  Δ=____
Gr00t zero-shot thick SR=____  light-FT thick SR=____  Δ=____
参照 SmolVLA 親 (thor unfreeze cross) thick ≈ 0.40
```

### お勧め進め方（将来用チェックリスト）

- [ ] 配布物到着: 学習コード・提出テンプレ・I/O 仕様を `docs/06` / `submission_spec` にメモ
- [ ] `parc.policies` / `train.backend` に Pi0・Gr00t アダプタ（eval が先、train は後）
- [ ] **Gate1**: Pi0 / Gr00t それぞれで `parc-smoke` / 1 タスク eval が通る（ホストは 04 表）
- [ ] **B0**: ゼロショット薄い → 厚い（Pi0=thor · Gr00t=nuc 並行）
- [ ] **B1**: 軽い FT 1 本ずつ（winpc）→ 厚い（thor）。ΔSR とカテゴリ表を 02 に追記
- [ ] B0/B1 の勝者を本選親候補に。負け側は打ち切り（長 FT に逃げない）
- [ ] 視点 OOD が残るなら SmolVLA で検証済みの **mix 設計**を本選親に移植（cam-only 禁止）
- [ ] Cosmo3-Nano 等は **主線にしない**。使うなら合成データ副線のみ（ポリシー差し替えはスパイク成功後）
- [ ] （条件付き）B-spline Policy — 下記「副指標」節
- [ ] （参考のみ）WARL — 下記「オプション・参考」節。**主線にしない**
- [ ] 提出: `pack_submission` · 公式 I/O 一致確認（→ `docs/06_competition.md`）

### 副指標候補 — B-spline Policy（いまはやらない）

出典: [bspline-policy](https://github.com/B-spline-policy/bspline-policy) · [arXiv:2607.09648](https://arxiv.org/abs/2607.09648) · [project](https://b-spline-policy.github.io/)

何をするか: 離散 action chunk の代わりに **B-spline（制御点＋knot）** を予測。Diffusion Policy / ACT 向け。完了時間短縮・軌道滑らかさ（Jerk↓）が主効果。

| 向く | 向かない |
|------|----------|
| PARC の **滑らかさ・実行効率** | **Camera OOD / Success 地板**（視覚問題ではない） |
| DP/ACT 系バックエンド | SmolVLA / Pi0 / Gr00t へのそのまま載替 |
| SR が十分になった後の磨き | LIBERO sim での単純な時間加速（制御周期固定・環境改造が必要なことが多い） |

着手条件（すべて満たしてから）:

1. 厚い SR が十分（親候補が固まっている）
2. 公式評価で Jerk / 完了時間が効くと分かっている（または計測手段がある）
3. 使うバックエンドが chunk ベース（DP/ACT 系）か、本選コードにアダプタ余地がある

やらないこと: Success 改善目的での SmolVLA 置き換え、Camera mix より先の実装。

- [ ] 条件達成後: DP/ACT スパイク（1 タスク）→ Jerk/時間と SR を 02 に記録
- [ ] 効果あれば本選副経路。なければ打ち切り

### オプション・参考 — WARL（いまはやらない・移植しない）

出典: [project](https://keitayoneda.github.io/kleiyn-warl/) · IROS 2026（Yoneda et al.）

何をするか: 四足の RL で action に **wrench（力・トルク）** を足し、Switching Curriculum で徐々に消して **joint-only** にする。動的全身運動の探索加速が主目的。

| 向く（概念だけ） | 向かない（このプロジェクト） |
|------------------|------------------------------|
| 「補助アクションをカリキュラムで消す」一般論 | **アーム操作 VLA / LIBERO 摂動**へのそのまま適用 |
| Gate-RL 後の探索補助の発想メモ | 四足・Isaac Gym 系の実装追従 |
| | Camera / Language OOD・デモ mix より先の実装 |

メモ: 実施形態・タスク空間が違うため **コード移植はしない**。残すのは「補助をフェードアウトするカリキュラム」の参照のみ。着手条件は設けない（主線・副指標のどちらにも入れない）。

- [ ] （任意・読書）サイト / abstract を斜め読みし、GRPO 設計メモに 1 行だけ残す程度

### 研究サイドカー — QuantVLA（低優先・空き GPU 時）

出典: [QuantVLA](https://quantvla.github.io/) · [code](https://github.com/AIoT-MLSys-Lab/QuantVLA) · 正本 [2026-08-01-quantvla-repro-design.md](../docs/superpowers/specs/2026-08-01-quantvla-repro-design.md)

SmolVLA 主線・親判定には接続しない。GR00T N1.5 + 古典 LIBERO 再現 →（到達時）LIBERO-plus 薄い比較。

- [x] QuantVLA サイドカー env（`groot_test` / `libero_test`）— R-Gate1/2（**winpc** · thor ディスク逼迫のため）
- [x] 古典 LIBERO FP16 vs QuantVLA 表 — R-Gate3 → [libero_classic.md](../docs/baselines/quantvla/libero_classic.md)  
  - Avg FP16 **0.875** · Quant **0.850**（n=1/task · Goal↑ / Long↓）
- [x] LIBERO-plus 薄い比較 — R-Gate4 → [libero_plus.md](../docs/baselines/quantvla/libero_plus.md)  
  - FP16 **0.857** · Quant **0.786**（Camera 両条件 0）
- [x] 02 に 1 段落要約

やらない: SmolVLA 移植 · parc `uv` 依存追加 · π0.5 · 提出物接続

### 研究サイドカー — MolmoAct2（低優先・空き GPU 時）

出典: [MolmoAct2](https://allenai.org/blog/molmoact2) · [HF LIBERO](https://huggingface.co/allenai/MolmoAct2-LIBERO) · 正本 [2026-08-02-molmoact2-spike-design.md](../docs/superpowers/specs/2026-08-02-molmoact2-spike-design.md)

SmolVLA 主線・親判定には接続しない。現行 robot **LeRobot 0.5.1 に molmoact2 無し** → eval は HF `predict_action` アダプタ。

- [x] 依存調査 + `MolmoAct2HFPolicy` / smoke YAML / 設計メモ
- [x] G0: `python scripts/molmoact2_infer_smoke.py`（PASS · peak≈11 GiB bf16）
- [x] G1: thor で `molmoact2_hf_smoke_eval.yaml` 完走（SR=0.0 · Background task0 · horizon 不足 · 親判定禁止）
- [x] G2: plus 薄いカテゴリ表 SR=**1.000**（n=14）→ [`docs/baselines/molmoact2/libero_plus.md`](../docs/baselines/molmoact2/libero_plus.md)（親昇格しない）
- [x] Language hard deep 対照 SR=**1.000**（n=30 · vs SmolVLA 0.10）· `20260801T234708Z_thor_99f67642_…`
- [x] 厚い同尺 SR=**1.000**（n=35 · vs SmolVLA 0.514）· `20260802T002529Z_thor_dde26442_…` → [`libero_plus.md`](../docs/baselines/molmoact2/libero_plus.md)
- [x] Ablations E1–E4（なぜ強いか）— E1=0.867 · E2=1.0 · E3=FAIL(state) · E4=1.0 · **H5 見送り** · 正本 [why-stronger-ablations](../docs/superpowers/specs/2026-08-02-molmoact2-why-stronger-ablations.md)
- [ ] （任意）LeRobot main 別 venv で短 FT

やらない: 親 ckpt 置き換え · parc `uv` に Molmo 依存追加 · 薄いだけで採用 · Think/depth

### 研究サイドカー — CLAIR / Flow-APO（低優先・空き GPU 時）

出典: TACL 2025 CLAIR+APO · 正本 [2026-08-02-clair-apo-sidecar-design.md](../docs/superpowers/specs/2026-08-02-clair-apo-sidecar-design.md)

SmolVLA 主線・親判定には接続しない。選好ペア主源は **シミュ合成 near-miss**（人間修正は補助）。目的関数は token log-prob ではなく **Flow-APO**。

- [x] 設計正本 + `parc-clair-pairs` / `flow_apo` / AFLoRA / merge CLI
- [x] P1: fake≥20 ペア（schema + L2 帯）— 実 LIBERO ロールアウトは後続
- [x] P2: QST+LoRA+ SFT YAML（`sidecar_smolvla_ft_clair_sft*_smoke.yaml` · dry_run 既定）
- [x] P3: Flow-APO smoke（energy MLP · winpc）— 薄い SR 比較は空き時
- [x] P4: merge smoke + `async_inference` 配線

やらない: 親 ckpt 置き換え · Quest 人間 CLAIR をブロッカー化 · GRPO 本格化 · 薄いだけで採用

### その他の中長期

- [ ] suite 拡張（object / goal / libero_10）は spatial で SR 安定後
- [ ] 公式提出テンプレ到着後: I/O アダプタ・`pack_submission`
- [ ] （研究用・本戦外）Meta-World MT50: 評価枠は `eval.backend=metaworld_mt50` 済み。デモ変換・本学習・VR は未着手

## 完了後の更新手順

1. `parc-queue status` / Fleet Runs で数値確定  
2. 02 の表を更新  
3. このファイルのチェックを更新し、次の 1 本だけ enqueue  
4. 01 のスナップショット日付を更新
