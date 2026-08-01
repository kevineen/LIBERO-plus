# 05. モデル・データセット変更への対応度

**Updated:** 2026-07-31  
キャッチアップ後に「公式モデルが来たら？」「データを差し替えたら？」を判断するための地図です。  
操作の詳細は [docs/07_custom_data_and_algos.md](../docs/07_custom_data_and_algos.md)。方針の正本は [strategy/03_next_actions.md](../strategy/03_next_actions.md)。

## 一言で言うと

| 変えたいもの | いまの対応度 | 典型コスト |
|--------------|--------------|------------|
| **同一スキーマの学習データ**（Hub / ローカル / mix / VR success-only） | **高い** | YAML 差し替え ± mix CLI |
| **評価プロトコル**（suite / task_ids / 厚い・薄い / Camera deep） | **高い** | 実験 YAML のみ |
| **評価ベンチそのもの**（LIBERO → MT50 等） | **中**（枠あり・本戦は LIBERO） | `BenchmarkBackend` + `eval.backend` + 別 venv |
| **LeRobot 内の別 policy_type**（act / diffusion 等） | **中** | YAML + 評価ラッパ確認 |
| **本選配布 Pi0 / Gr00t / OpenVLA** | **低い（差し込み口のみ）** | アダプタ実装が必要 |
| **観測・行動の次元やキー名そのもの** | **低い〜中** | 学習・評価・変換を同期改修 |

設計思想は「**評価・実験管理は固定、学習 backend / Policy アダプタだけ差し替える**」。  
研究用にベンチを増やすときは同思想で **`eval.backend` / `BenchmarkBackend`** を差し替える（[07 §D2](../docs/07_custom_data_and_algos.md)）。

```text
configs/experiments/*.yaml
        │
        ├─ eval.backend → parc.benchmarks registry → parc-eval  ← ベンチ差し替え点
        ├─ eval  → Policy.act()                                 ← モデル差し替え点
        └─ train → train.backend / policy_type / dataset_*      ← データ・学習差し替え点
                    → experiments/<run_id>/metrics.json         ← 比較尺は共通
```

---

## 1. データセット変更（対応度: 高）

### すぐできること

| やり方 | どこを触る | 備考 |
|--------|------------|------|
| Hub 公開 DS 差し替え | `train.dataset_repo_id` | 例: `lerobot/libero_plus` |
| ローカル DS | `dataset_repo_id` + `dataset_root` | VR / mix 出力先 |
| 複数源の混合 | `parc-mix-datasets` → 単一 root | **MultiLeRobotDataset は現行無効** |
| 失敗混在 → 学習用 | `parc-filter-demos --success-only` | raw は上書きしない |
| 品質ゲート | `parc-verify-demos` / replay / coverage | VR 収集経路 |

契約（変えると学習も評価も壊れる）:

- `observation.images.front` / `wrist`
- `observation.state` float32 `(8,)`
- `action` float32 `(7,)`（LIBERO 相対 EE）
- `task`（言語）
- LeRobot **v3.x**（`codebase_version`）

この契約を守る限り、**データ源の差し替えは YAML 中心で回る**。

### まだ弱い / 注意点

- リスト形式の `repo_id` mix は不可 → 必ず物理マージ
- action 空間が絶対姿勢・関節角なら **変換か制御モード合わせ**が必要
- camera 解像度・flip 慣習がズレると掴み位置が壊れる（[docs/07](../docs/07_custom_data_and_algos.md) C3）
- exclusion **理由付き**ログ（M5）は未実装。manifest 再生成は可、監査は薄い
- train/eval は **episode 単位分割**（frame ランダムは禁止）

---

## 2. モデル変更（対応度: 層による）

### 層ごとの現状

| 層 | 状態 | 意味 |
|----|------|------|
| 評価ループ・Fleet・metrics | **モデル非依存で完成** | `Policy` さえあれば同じ尺で比較できる |
| `policy.type=checkpoint` | **LeRobot ckpt 接続済** | SmolVLA 等の `pretrained_model` |
| `policy.type=molmoact2` | **HF 直呼びスパイク** | `allenai/MolmoAct2-LIBERO`（LeRobot 0.5.1 には未収録） |
| `train.backend=lerobot` | **接続済** | `policy_type` で LeRobot 内アーキを指定 |
| `policy.type=openpi/openvla` | **NotImplementedError の差し込み口のみ** | 配布コード待ち |
| `train.backend=openpi/gr00t/openvla` | **`not_implemented` 返却のみ** | 同上 |
| GRPO/GSPO | **状態ガウス方策のスモーク** | SmolVLA 本格 RL ではない |

### LeRobot 内の差し替え（中）

```yaml
train:
  backend: lerobot
  policy_type: smolvla   # → act / diffusion 等（入っている LeRobot 版を確認）
```

チェックリスト:

1. データキーと `input_features` / `output_features` が一致するか  
2. `LeRobotCheckpointPolicy`（または同等ラッパ）が `select_action` できるか  
3. 同じ eval YAML（seed / tpc / task_ids）で比較するか  

### 本選モデル（低 → アダプタで高に上げる）

方針は strategy に固定済み:

1. **eval アダプタを先に**（`build_policy` に Pi0/Gr00t）  
2. Gate1: 1 タスク smoke  
3. B0 ゼロショット厚い → B1 軽い FT  
4. 薄い eval だけで採用しない（SmolVLA と同じルール）

ホスト割り振り: [strategy/04_machine_roles.md](../strategy/04_machine_roles.md)。

---

## 3. 「いま実装している VR / 品質ゲート」は何に効くか

VR teleop + M1–M4 は **特定モデル専用ではない**。効く範囲:

| 能力 | モデル変更時 | データ変更時 |
|------|--------------|--------------|
| LeRobot v3 書き込み | 無関係（データ側） | 新デモ源としてそのまま使える |
| success-only / verify / replay | 無関係 | どの FT backend にも渡せる subset |
| RTT / Approx Time / queue | 無関係 | 収録品質。学習ラベル契約は維持 |
| Quest E2E（M0） | 無関係 | **実データが無いと単位コスト未測定** |

つまり品質スタックは **「本選モデルが来ても捨てないインフラ」**。捨てるのは SmolVLA 専用の学習 YAML だけ。

---

## 4. 次に打つべき施策（キャッチアップ後の優先）

チーム正本は [strategy/03](../strategy/03_next_actions.md)。人間メンバー向けに要約すると:

### A. 実験主線（SmolVLA・いま回している）

1. **thor: mix v2 厚い + Camera deep の結果待ち → 親判定**  
   - 勝ち: 親更新候補 / 負け: Phase B（cam 量・重み）  
2. 薄い eval だけで延長・採用しない  
3. cam-only FT・lr↓ 同軸延長は打ち切り済み（再投入しない）

### B. データ収集線（環境が揃ったら）

1. **M0 Quest 実機 E2E**（blocked: Windows + Quest）  
2. `parc-verify-demos` → success-only → `smolvla_ft_vr_demos_success_smoke.yaml`  
3. M5（verify 統計・exclusion log）は **M0 完了・承認後**（先行しない）

### C. モデル差し替え準備（コードは配布後）

1. 配布物の I/O を `docs/06` にメモ  
2. `parc.policies` に eval アダプタ → Gate1  
3. train backend 接続 → B0/B1  
4. 視点 OOD が残るなら **検証済み mix 設計を移植**（cam-only 禁止）

### D. やらない（現状）

- 公式提出 zip の推測実装  
- GRPO/GSPO 本格化（Gate-RL 未達）  
- Pi0/Gr00t の独自 big train を B0 前に開始  
- M0 前の M5 / rerun 可視化の先行実装  

---

## 5. 差し替え時の最短チェックリスト

**データだけ変えるとき**

- [ ] features / fps / robot_type が契約どおり  
- [ ] `parc-verify-demos`（必要なら `--coverage`）  
- [ ] 学習は success-only または意図した filter  
- [ ] 同じ eval サブセットで 1 本比較  

**モデルだけ変えるとき**

- [ ] `Policy.act(obs) → (7,)` が LIBERO 相対アクションか  
- [ ] 観測キー・flip・言語の渡し方が学習時と一致  
- [ ] 薄い → 厚いで地板を取る（薄いだけで決めない）  
- [ ] run を `parc-list` / Fleet で追跡  

詳細手順: [docs/07](../docs/07_custom_data_and_algos.md) / コンペ: [docs/06](../docs/06_competition.md)。

## 6. 次のドキュメント

- 運用に戻る → [04_next_steps.md](04_next_steps.md)  
- チーム現状 → [strategy/01](../strategy/01_current_status.md) / [03](../strategy/03_next_actions.md)  
- VR 品質ロードマップ → [feature/vr-teleop/roadmap-data-quality.md](../feature/vr-teleop/roadmap-data-quality.md)
