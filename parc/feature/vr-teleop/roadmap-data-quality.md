# VR Teleop — データ品質・スケーリング改善ロードマップ

**Updated:** 2026-07-31  
**ゴール:** 収録時間ではなく、**単位コストあたりの「同期・多様・正しくラベル付け・検証可能」な軌跡**を増やす。

関連:

- 実装済み品質ゲート: [STATUS.md](STATUS.md) / [design.md](design.md)
- 実機 E2E 手順: [next-sprint-plan.md](next-sprint-plan.md)（Sprint C）
- 運用: [docs/12_vr_teleop.md](../../docs/12_vr_teleop.md)

```text
単位コスト = (人時 + 機時) / 検証済み良質エピソード数
良質 = 同期済み ∧ 多様 ∧ ラベル正しい ∧ 検証可能
```

---

## 現状サマリ（済）

| 能力 | 状態 |
|------|------|
| `(o,a)` + `task` を LeRobot **v3.0** で保存 | done |
| 成功/失敗フラグ（失敗も保存可） | done |
| fps / v3 `timestamp`（自動）+ `control_timestamps` サイドカー | done |
| カメラ名・解像度・座標系宣言 + calib 差し替え器 | done |
| 収集メタ（operator / device / location） | done |
| `parc-verify-demos` | done |
| init_state / task_ids cycle | done |

未達の本丸: **Quest 実機でパイプラインが回ること（M0）**。ソフト側（M1–M4 = 学習フィルタ・RTT・キュー・replay・Approx Time）は 2026-07-31 時点で実装済み。

---

## 優先順位（推奨順）

コスパ順: **1 → 3 → 2 → 4 → 5 → 6**（M0 blocked 時は **3 → 2 → 4 → 5 → 6**）。

### 1. Quest 実機 E2E（最優先・環境依存）

**なぜ:** 品質ゲートは fake/pytest まで。実機 1 ep が無いと単位コストは測れない。

**状態:** **blocked**（Quest / Windows 未接続）。ソフト実装スプリントでは触らない。

**やること:**

- [ ] Windows + Unity + Quest 3 で 1 episode 保存
- [ ] `meta/info.json`（`codebase_version: v3.*`）確認
- [ ] `uv run parc-verify-demos --root data/datasets/vr_libero_demos`
- [ ] `smolvla_ft_vr_demos_smoke.yaml` 起動
- [ ] `STATUS.md` に E2E 結果を記録

**正本手順:** [next-sprint-plan.md](next-sprint-plan.md)

**受け入れ:** Sprint C acceptance 全項目 + verify pass。

---

### 2. RTT / 遅延ゲート

**なぜ:** 学習ラベルは PC 側同ステップでズレにくいが、遅延は失敗・汚い軌跡を増やし単位コストを悪化させる。計測・ゲートが無い。

**やること:**

- [x] `ping`/`pong` で RTT を計測しセッション平均・p95 を記録
- [x] 各 ep の `episode_quality.jsonl` に `rtt_ms_mean` / `rtt_ms_p95` / `control_skew_ms` を追記
- [x] YAML: `max_rtt_ms` 超過で Save 拒否、または `degraded: true` で保存（既定 `latency_policy: degraded`）
- [x] `collection_stats` に degraded / refused_latency を追加
- [x] 単体テスト（fake 遅延注入）

**変更候補:** `protocol.py` / `session.py` / `recorder.py` / `configs/vr/*.yaml` / `verify_demos.py`

**受け入れ:** 人工遅延で拒否または `degraded` が立ち、verify が読める。 **soft done**

---

### 3. 学習時 success フィルタ

**なぜ:** 失敗もデータに残す方針のため、学習が失敗軌跡をそのまま飲むと baseline が汚れる。

**やること:**

- [x] 成功 ep だけの subset root を作る CLI（`parc-filter-demos --success-only`）
- [x] `smolvla_ft_vr_demos_success_smoke.yaml` に success-only 経路を文書化
- [x] `docs/07` / `docs/12` に「失敗は分析用・学習は success-only」を明記

**受け入れ:** 失敗混在 DS から success-only で FT が起動し、混在直読みより手順が短い。 **soft done**

---

### 4. 多様化スケジュール（摂動・カテゴリ）

**なぜ:** いまは同 suite 内 `init_state` / `task_ids` のみ。LIBERO-plus の視点・照明・配置 OOD には足りない。

**やること:**

- [x] 収集キュー YAML（suite / task_id / init_state_index / 摂動カテゴリ）
- [x] Reset/Save 後にキューを消化（不足分を Status 表示）
- [x] `episode_quality` に `perturbation` / `category` を記録
- [x] coverage レポート（カテゴリ × success 数）を `parc-verify-demos --coverage`

**受け入れ:** 指定カテゴリが最低 N 本ずつ埋まるまでキューが残る。 **soft done**（物理 OOD エンジンは後回し）

---

### 5. 物理リプレイ検証

**なぜ:** `success` は収録時フラグ。action 再生で同じ success になるかを見ると「検証可能」が一段上がる。

**やること:**

- [x] `parc-replay-demos --root … --episode N`（保存 action を env で再生）
- [x] 結果を `episode_quality` に `replay_success` / `replay_steps` 追記
- [x] verify に `--require-replay-success` オプション

**受け入れ:** fake または LIBERO 1 task で replay_success が quality に載る。 **soft done**（fake + 単体）

---

### 6. Approximate Time 本実装（同期器）

**なぜ:** 現状は `control_timestamps` の記録のみ。古い control の drop / 窓内マッチは未実装。

**やること:**

- [x] 許容窓 `approx_time_slop_ms` で古い uplink を破棄
- [x] 間引き・重複 step 防止
- [x] 品質メタに `dropped_stale_controls` を記録
- [ ] （任意）映像フレームと control の対応をログ

**受け入れ:** 故意にバースト送信したとき stale が落ち、軌跡 fps が安定する。 **soft done**

---

## 後回し（効くが急がない）

| 項目 | メモ |
|------|------|
| WebRTC 映像 | JPEG WS の遅延が実測で問題になってから |
| 実機キャリブ実測の差し込み | `calib_override` 器は済み。実機値が来てから |
| オペレータ別 saved_per_hour UI | Web / Fleet ダッシュボード |
| ハンドトラッキング / 3D ビュー / 実機 Franka / パススルー | 既存 Phase 2+ backlog |

### 講義由来・次候補（M0 後にコード化）

運用ルールの正本は [docs/02_data.md](../../docs/02_data.md) / [docs/07_custom_data_and_algos.md](../../docs/07_custom_data_and_algos.md)。ここでは実装バックログのみ。

| 優先 | 項目 | メモ |
|------|------|------|
| 高 | verify 統計監査 | エピソード長・行動次元の分布/レンジ・Δt 分布・タスク別本数・`stats.json` 妥当性。壊れても例外を出さない同期バグの検知 |
| 高 | exclusion log | 除外した episode ID + 理由を残す。`filter_manifest` / `mix_manifest` と契約を揃え、raw を上書きせず再生成可能にする |
| 高 | train/eval 分割ルール | episode 単位（可能なら operator 単位）。frame ランダム分割はリークのため禁止（docs に固定済み） |
| 中 | action lag Δ | `o_t` ↔ `a_{t+Δ}` を YAML 設計変数化。制御周期確定後に Δ=0 vs 小遅延の感度を 1 回測る |
| 中 | Filter / Relabel / Condition | 壊れた軌道は filter。ラベルだけ怪しければ relabel（軌道は資産）。指示文汚染時は success-only だけでは足りない |
| 低 | rerun / Foxglove | 軌道の目視監査。実機エピソードが溜まってから。M0 前の導入はコスパが悪い |

**実装順（コードは承認後・M0 完了後）:**  
`M0 Quest E2E` → `verify 統計監査` → `exclusion log（ID + reason）` →（必要なら）action lag Δ / 可視化。

---

## マイルストーン案

| マイルストーン | 含む項目 | 完了条件 |
|----------------|----------|----------|
| **M0** 実機パイプライン | #1 | Quest 1 ep + verify + FT smoke — **blocked** |
| **M1** 学習に使える混在 DS | #3 | success-only 学習経路が文書化・実行可能 — **done** |
| **M2** 遅延可視化・ゲート | #2 | RTT メタ + しきい値動作 — **done** |
| **M3** スケール多様 | #4 | 摂動キュー + coverage — **done**（ラベル/キュー） |
| **M4** 検証強化 | #5 #6 | replay + Approximate Time 同期器 — **done** |
| **M5** 統計・再現ゲート | 講義由来・次候補の高優先 | verify 統計 + exclusion log — **deferred（M0 後）** |

---

## やらないこと（このロードマップ範囲外）

- 公開データ mix 戦略全体の再設計（別 docs / strategy）
- LeRobot features への `success` 列追加（jsonl サイドカーを正とする）
- Unity クライアントの大規模改修（E2E に必要な最小変更のみ #1 で可）
- SLAM / UMI・rosbag/MCAP 移行・オフライン選別ライブラリ（ReMix 等）の先行実装
- cross-embodiment 翻訳・data flywheel（π0 / RECAP）— 配布データ・閉ループ評価が揃ってから
