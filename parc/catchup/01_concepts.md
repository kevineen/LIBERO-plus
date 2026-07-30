# 01. 概念と用語（初心者向け）

この章では数式より **絵に描けるイメージ** を優先します。細部は [02_study_urls.md](02_study_urls.md) の論文・公式 docs へ進んでください。

## 1. ロボット学習で何をしているか

シミュレーション（または実機）上のロボットが、**カメラ画像**と**言語指示**（「赤いカップを右に置け」など）を見て、**関節の動き（アクション）**を出す問題です。

```text
観測（画像 + 状態 + 言語）  →  方策（policy）  →  アクション  →  シミュレータが進む
                                                              →  成功 / 失敗
```

- **成功:** タスク条件を満たした（物体が正しい場所にある、など）
- **エピソード:** 1 回の試行（開始〜終了）
- **成功率 (success rate):** 成功したエピソードの割合

## 2. 模倣学習（Imitation Learning）

正解の動き（デモ）を見て真似する学習です。強化学習のように「試して報酬を待つ」より、デモがあれば早く立ち上がります。

| 用語 | 意味 |
|------|------|
| Behavior Cloning (BC) | デモの (観測 → アクション) を教師あり学習で真似る |
| デモ / エピソード | 人間や専門家方策が残した軌跡データ |
| ファインチューニング (FT) | 事前学習済みモデルを、自分のタスク用データで追加学習する |

このプロジェクトの当面の主戦場は **デモデータでの FT** です（本選で配布モデルが来たら差し替え）。

デモの集め方の一例: **Meta Quest 3 で LIBERO をテレオプ**して LeRobot 形式で保存する（[docs/12_vr_teleop.md](../docs/12_vr_teleop.md)）。

## 3. VLA（Vision-Language-Action）

**Vision**（画像）+ **Language**（指示文）→ **Action**（ロボット動作）を一本のモデルで扱う枠組みです。

代表例:

- **OpenVLA** — 大規模 VLA の代表格
- **π₀ (Pi0)** — 本選で配布が想定される系統
- **SmolVLA** — Hugging Face LeRobot の軽量 VLA。いま `parc` で線を通すために使う

重要な直感: 画像だけ見て動く「Vision-Action」になりやすく、**言語を本当に使っているかは摂動実験で炙り出される**（LIBERO-plus の知見）。

## 4. LIBERO と LIBERO-plus

| 名前 | 何か |
|------|------|
| **LIBERO** | 卓上マニピュレーションのシミュレーションベンチマーク（複数 suite） |
| **LIBERO-plus** | 元タスクに **7 種類の摂動**を加えた頑健性ベンチ（約 1 万タスク） |

### 7 摂動カテゴリ（覚え方）

1. **Layout** — 物体配置・邪魔物
2. **Camera** — 視点・FOV
3. **Robot** — 初期姿勢
4. **Language** — 指示文の書き換え
5. **Light** — 照明
6. **Background** — 背景テクスチャ
7. **Noise** — センサノイズ・画質劣化

LIBERO-plus では公式に **`num_trials_per_task = 1`**（素の LIBERO の 50 回ではない）です。

### suite の例

`libero_spatial` / `libero_object` / `libero_goal` / `libero_10` など。  
タスク数が非常に多いので、実験では必ず **task_ids や tasks_per_category で絞る**のが常識です。

## 5. PARC2026 とこの `parc/` リポジトリ

**PARC** は東大松尾研まわりのフィジカル AI コンペです。評価環境は説明会時点で **LIBERO / LIBERO-plus**。

このフォルダ `parc/` は:

- ルール発表前でも **評価・学習・実験管理**を回せる作業場
- 公式提出フォーマットが来たら、アダプタと YAML を差し替える想定

```text
configs/experiments/*.yaml  →  train / eval  →  experiments/<run_id>/
                                                    ├── metrics.json
                                                    └── ...
```

### 用語（parc 固有）

| 用語 | 意味 |
|------|------|
| suite | タスク群の名前（上表） |
| task_id | suite 内の 0-based インデックス |
| category | 7 摂動のいずれか |
| run / run_id | 1 回の実験。結果は `experiments/<run_id>/` |
| policy | アクションを出すモデル（random / checkpoint など） |

詳細は [docs/00_overview.md](../docs/00_overview.md)。コンペチェックリストは [docs/06_competition.md](../docs/06_competition.md)。

## 6. スクリプトと venv の使い分け（超重要）

初心者が一番ハマるポイントです。

| やりたいこと | 使うもの | 環境 |
|--------------|----------|------|
| ランダム評価・スモーク系 | `./scripts/parc.sh eval ...` | 親 `LIBERO-plus/.venv` |
| SmolVLA 学習 | `bash scripts/train.sh ...` | 親 `Matsuo/robot` venv + CUDA |
| 学習済み ckpt 評価 | `bash scripts/eval_ckpt.sh ...` | 同上 |
| 実験一覧 | `uv run parc-list` | `parc` の uv 環境 |

「全部 `uv run` すればよい」わけではない、と覚えてください。

## 7. 次にやること

1. [02_study_urls.md](02_study_urls.md) で Must の URL を読む  
2. [03_first_run.md](03_first_run.md) で手を動かす  
