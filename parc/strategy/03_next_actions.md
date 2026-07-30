# 03. 今後実施すべき内容（バックログ）

優先は上から。完了したら `[x]` にして、結果を [02_results_and_findings.md](02_results_and_findings.md) に追記する。

## 進行中

- [x] **thor**: 厚い eval 2 本完了（unfreeze 0.429 / continue expert 0.286）
- [x] **nuc**: Gate3 薄い 0.357 · 厚い **0.257**
- [x] **親 ckpt クロス厚い** — 完了  
  - +15k on thor **0.343** · unfreeze on winpc **0.400** → **親 = thor unfreeze**
- [x] **thor**: Camera deep unfreeze（608–612×10）— **SR=0.08**  
  - job `q_20260729T093137…4e2a1fe6` · run `20260729T093144Z_thor_fa549217_…`  
  - 608:0.20 · 609:0.10 · 610–611:0 · 612:0.10（continue 深掘り 0.16 より弱い）
- [x] **thor**: +15k mild Camera deep（608/609×10）— **SR=0.30**  
  - 608:0.40 · 609:0.20 · run `20260729T174037Z_thor_abf2aca9_…`
- [x] **thor**: 弱点深掘りバッチ — **完了**  
  - Sensor 0.20 · Language 0.20 · RobotInit 0.16 · continue Cam 0.04 · +15k Cam 0.12
- [ ] **フォロー評価（2026-07-30）** — running  
  - thor: Language hard 984/986/988×10 · `q_…c8f18f52`  
  - thor: +15k Camera hard 610–612×15 · `q_…96b8aa6d`  
  - nuc: 親 Camera deep クロス · `q_…9ec45635`

## 直近で打ち切ったもの

- [x] **winpc**: Camera 再レンダ FT（cam-only）  
  - job: `q_20260728T082609607849+0000_04e5d231` · 薄い **SR=0.000**（Camera 5/5 fail）
  - 判断: **同系の即延長はしない**。mix 方法を作り直さない限り再投入しない

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
  - 次: thor で Camera deep + 厚い（投入済み）
- [ ] **mix10k 評価（thor）** — queued/running  
  - Camera deep 608–612×10 · `q_20260730T043221…ac6aad22`  
  - 厚い tpc=5 · `q_20260730T043222…6472381a`
- [ ] 必要なら winpc cam-only `010000` を Camera deep だけ再評価（優先低）

## 次の学習候補（レビュー後）

優先候補（互角なら上）:

1. **混合方法を作り直した視点 OOD 学習**  
   - `cam-only` は 0.000 だったため、そのまま再実行しない  
   - **手順**: `parc-mix-datasets`（base≈240 + cam60）→ 親=unfreeze 短 FT（10k · lr 1e-5）→ Camera deep  
   - YAML: `configs/experiments/smolvla_ft_libero_cam_mix_from_unfreeze_winpc.yaml`（初期 `dry_run: true`）
2. **lr↓ 短 FT の継続** — 後回し
3. **unfreeze を親に戻す** — **実施済み（2026-07-29 cross）**  
   - 以降の学習延長は `…4e89a1ad…/030000` を pretrained_path に

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

### その他の中長期

- [ ] suite 拡張（object / goal / libero_10）は spatial で SR 安定後
- [ ] 公式提出テンプレ到着後: I/O アダプタ・`pack_submission`

## 完了後の更新手順

1. `parc-queue status` / Fleet Runs で数値確定  
2. 02 の表を更新  
3. このファイルのチェックを更新し、次の 1 本だけ enqueue  
4. 01 のスナップショット日付を更新
