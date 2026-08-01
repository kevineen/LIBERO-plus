# 07. オリジナルデータの追加と学習アルゴリズム改善

ルール発表前でも、**データ差し替え**と**学習レシピ改善**を再現可能な形で回すための手順書です。  
評価は常に `parc-eval` / `eval_ckpt.sh`、実験は YAML + `experiments/<run_id>/` で追跡します。

対応度の要約（キャッチアップ向け）: [catchup/05_adaptability.md](../catchup/05_adaptability.md)。

## 改善の原則

1. **1 回の実験で変える軸は 1〜2 個**（データ or ハイパーパラ or アーキ）
2. **同じ評価サブセット**で比較する（まず `subset_eval` 相当）
3. 成功の定義は当面 **カテゴリ別 success_rate**（公式重みは非公開）
4. 学習 I/O は評価ラッパ（`policy.type=checkpoint`）と **同じ観測キー**にする

```text
仮説 → YAML コピー → train → eval_ckpt → parc-list で比較 → 次の仮説
```

### データ運用ルール（スケーリング）

要約は [02_data.md](02_data.md)。自前デモ・mix・評価分割では次を守る。

| ルール | 内容 |
|--------|------|
| **多環境 × 少デモ** | 同じ task への収録時間積み上げより、suite / `init_state` / 摂動カテゴリ（VR は `collection_queue`）を先に広げる。デモ本数は閾値で飽和しやすい |
| **train/eval 分割** | **episode 単位**（可能なら operator / collection date / environment 単位）。**frame 単位のランダム分割はリーク**のため禁止 |
| **raw 不変** | 生データセットを上書きしない。変換コード・設定・schema version を残す。`parc-filter-demos` / `parc-mix-datasets` は manifest で再生成可能にし、除外 episode は **ID + 理由**を残す（現状 manifest はあるが理由付き exclusion log は M0 後の M5） |
| **Filter / Relabel / Condition** | 軌道が壊れていれば filter。軌道は有効でラベルだけ怪しければ relabel（指示文ミス等）。有効な軌道は資産、ラベルは修理可能な部品。学習 baseline は当面 success-only filter |
| **同期・対応付け** | 現行 VR は同ステップ `(o,a)`。追従遅れ用の `a_{t+Δ}` は制御周期確定後に設計変数化する（roadmap） |

品質ロードマップ: [feature/vr-teleop/roadmap-data-quality.md](../feature/vr-teleop/roadmap-data-quality.md)。

---

## A. 評価と揃えるデータスキーマ

現行 SmolVLA + `lerobot/libero_plus` 互換の必須キー:

| キー | dtype / shape | 意味 |
|------|----------------|------|
| `observation.images.front` | video / uint8 `(H,W,3)` | agentview（例: 256×256） |
| `observation.images.wrist` | video / uint8 `(H,W,3)` | eye-in-hand |
| `observation.state` | float32 `(8,)` | eef_pos(3) + axis-angle(3) + gripper_qpos(2) |
| `action` | float32 `(7,)` | 相対 EE 制御 6 + gripper 1 |
| `task`（エピソード言語） | string | 言語指示（VLA 必須） |

参考メタ（公開データ）:

- `fps`: 20
- `robot_type`: `panda`
- `codebase_version`: LeRobot dataset v3.x

評価側（`LeRobotCheckpointPolicy`）も同じ front/wrist・8 次元 state・言語を想定しています。  
**キー名や state の並べ方を変えたら、評価ラッパも同じ定義に合わせてください。**

画像の 180° フリップは HuggingFaceVLA/libero 系の慣習です。自前データが未フリップなら:

- 変換時にフリップする、または
- 評価 YAML で `policy.flip_images: false`

のどちらかに揃えます。

**観測アラインメントの注意（掴み位置ずれの切り分け）**

- 保存される評価動画は **env 生 RGB（未 flip）**。`flip_images: true` のとき policy が見る画像は 180° 回転後であり、**動画 ≠ policy 入力**。
- `eval.task_ids: [0]` は「素の LIBERO」ではない。LIBERO-plus の index 0（多くは Background Textures 摂動）である。
- 確認コマンド: `PYTHONPATH=src:..` 付きで `python scripts/dump_obs_align.py`（robot venv）。`dataset_front.png` と `env_flip_front.png` の向きを比べる。

---

## B. オリジナルデータの追加

やり方は 4 通り。上から簡単です。

### B1. 公開データセットを差し替えるだけ

YAML の `train.dataset_repo_id` を変えます。

```yaml
train:
  backend: lerobot
  dataset_repo_id: Sylvest/libero_plus_lerobot   # 例
  # dataset_repo_id: your-user/my_libero_demos  # Hub に上げた自前データ
```

実行:

```bash
bash scripts/train.sh configs/experiments/<your_ft>.yaml
```

### B2. ローカル LeRobot データセットを読む

Hub に上げず、ディスク上の LeRobot 形式を使う場合:

```yaml
train:
  dataset_repo_id: local/my_panda_demos   # 任意の ID（メタ用）
  dataset_root: data/datasets/my_panda_demos   # 実体ディレクトリ
```

`dataset_root` は `parc/` からの相対、または絶対パス。  
中身は通常次の形です（LeRobot v3）:

```text
data/datasets/my_panda_demos/
  meta/
    info.json
    episodes.jsonl
    tasks.jsonl
    stats.json
  data/
    chunk-000/
      file-000.parquet
  videos/
    observation.images.front/...
    observation.images.wrist/...
```

`parc-train` は `--dataset.root=...` を付与します（`src/parc/train/lerobot_train.py`）。

### B2.5. Quest 3 VR テレオプでデモを録る（推奨経路の一つ）

シミュ上の LIBERO を Meta Quest 3 で操作し、**変換スクリプト無し**で LeRobot v3 に直接書く。

- 運用: [12_vr_teleop.md](12_vr_teleop.md)
- 設計・進捗: [feature/vr-teleop/](../feature/vr-teleop/)
- 起動例: `bash scripts/vr_teleop.sh --config configs/vr/fake_smoke.yaml --fake --no-dataset`  
  / `PARC_ROBOT_VENV=... bash scripts/vr_teleop.sh --config configs/vr/quest3_libero_spatial_task0.yaml`
- **失敗は分析用・学習は success-only:**  
  `uv run parc-filter-demos --root data/datasets/vr_libero_demos --output data/datasets/vr_libero_demos_success --success-only --overwrite`  
  → `configs/experiments/smolvla_ft_vr_demos_success_smoke.yaml`
- 混在直読み（デバッグ）: `configs/experiments/smolvla_ft_vr_demos_smoke.yaml`

Phase 1 はコントローラ 6DoF + カメラストリーム。ハンド／実機／3D ビューは feature STATUS の backlog。

### B3. デモ・独自ログから LeRobot 形式へ変換

1. 生データ（ROS bag、自前 npz、シミュレータログ等）を用意  
2. `scripts/examples/convert_demo_to_lerobot.py` をコピーして変換  
3. `dataset_root` を YAML に書く  
4. 小規模 FT → `eval_ckpt.sh` で 1 タスク通し確認  

最小の変換イメージ:

```python
from pathlib import Path
from lerobot.datasets.lerobot_dataset import LeRobotDataset

FEATURES = {
    "observation.images.front": {"dtype": "video", "shape": (256, 256, 3), "names": ["height", "width", "channel"]},
    "observation.images.wrist": {"dtype": "video", "shape": (256, 256, 3), "names": ["height", "width", "channel"]},
    "observation.state": {"dtype": "float32", "shape": (8,), "names": [f"state_{i}" for i in range(8)]},
    "action": {"dtype": "float32", "shape": (7,), "names": [f"action_{i}" for i in range(7)]},
}

ds = LeRobotDataset.create(
    repo_id="local/my_panda_demos",
    fps=20,
    robot_type="panda",
    features=FEATURES,
    root=Path("data/datasets/my_panda_demos"),
    use_videos=True,
)

for episode in my_episodes:  # 自前イテレータ
    for frame in episode.frames:
        ds.add_frame({
            "observation.images.front": frame.front_rgb,   # HWC uint8
            "observation.images.wrist": frame.wrist_rgb,
            "observation.state": frame.state8,              # float32 (8,)
            "action": frame.action7,                       # float32 (7,)
            "task": episode.language,                      # 毎フレーム同じで可
        })
    ds.save_episode()
ds.finalize()
```

注意:

- **言語指示**は摂動カテゴリ「Language Instructions」対策にも効くので、言い換えバリエーションを入れる価値が高い  
- アクション空間が絶対姿勢や関節角なら、学習前に **LIBERO 相対 7D へ変換**するか、評価側の制御モードを合わせる  
- **SO-100/101 関節角:** LeRobot ドライバは **degrees** 前提が多い。生ログが radians のときは変換時に deg へ統一する  

```bash
# 例: radians ログ → degrees 正本 + meta/angle_units.json
python scripts/examples/convert_demo_to_lerobot.py \
  --out data/datasets/my_so100_demos \
  --repo-id local/my_so100_demos \
  --robot-type so100 \
  --control-mode joint_position \
  --source-angle-unit radians \
  --overwrite

# メタだけ書く / サンプル変換確認
uv run parc-normalize-angle-units \
  --root data/datasets/my_so100_demos \
  --control-mode joint_position \
  --source-angle-unit radians \
  --sample 0,1.5708

# rad/deg 取り違え（微動・異常振幅）を検査
uv run parc-verify-demos \
  --root data/datasets/my_so100_demos \
  --skip-collection-info \
  --require-angle-units \
  --check-joint-angle-units
```

  - `meta/angle_units.json` に `control_mode` / `source_unit` / `stored_unit=degrees` を記録（joint 必須）  
  - 現行 VR/LIBERO の `ee_delta` は単位検査対象外（スキップ）  
- 失敗デモを混ぜるかは仮説次第（**まずは成功のみで baseline**）。VR 収集は失敗も混在 DS に残し、学習前に `parc-filter-demos --success-only` で subset を切る（[12](12_vr_teleop.md)）

### B4. 複数データセットの混合（物理マージ）

**注意（2026-07）:** 現行 LeRobot は `MultiLeRobotDataset` が無効です。
`factory.make_dataset` は非 str の `repo_id` で `NotImplementedError` になります。
ドキュメントにある `--dataset.repo_id=[a,b]` は **使えません**。

代わりに **事前マージ**してから単一データセットで学習します。

```bash
# 例: libero_plus から 240 ep + cam 全 60 ep → ~80/20（エピソード比）
# ※ lerobot 入りの親 venv を使う（parc 単独 .venv では不可）
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
set -a && source .env.local && set +a

bash scripts/mix_datasets.sh \
  --base-root /mnt/b/hf/hub/lerobot/hub/datasets--lerobot--libero_plus/snapshots/f3f49f426d75030177b18778374005bc12ccd588 \
  --cam-root data/datasets/libero_cam_views_v1 \
  --base-episodes 240 \
  --dry-run

bash scripts/mix_datasets.sh \
  --base-root /mnt/b/hf/hub/lerobot/hub/datasets--lerobot--libero_plus/snapshots/f3f49f426d75030177b18778374005bc12ccd588 \
  --cam-root data/datasets/libero_cam_views_v1 \
  --base-episodes 240 \
  --out data/datasets/libero_plus_cam_mix_v1 \
  --overwrite
```

学習 YAML は単一 `dataset_repo_id` + `dataset_root` を指す
（例: `configs/experiments/smolvla_ft_libero_cam_mix_from_unfreeze_winpc.yaml`）。
**cam-only FT は禁止**（薄い SR=0.000 で打ち切り済み）。

または公式データで warm-start したあと、自前データだけで追加 FT（2 段階）の方が制御しやすいです。

```text
stage1: libero_plus で 5k〜10k step
stage2: 自前データのみ、小さい lr / 短い steps、checkpoint から resume
```

resume は LeRobot の `--resume=true` と既存 `output_dir` 規約に従います（詳細はその版の `lerobot-train --help`）。

### B5. ディスクとパス

- 大きいデータ・キャッシュ: `configs/paths.yaml` の `data_dir`、および `HF_HOME` / `HF_LEROBOT_HOME`
- 学習実行時は `scripts/train.sh` が `HF_HOME` を設定
- ルートディスク逼迫時は **変換出力先を最初から外付け**にする

```bash
df -h /
# 例: data_dir: /mnt/sda/parc_data
```

---

## C. 学習アルゴリズムの改善

「アルゴリズム改善」は次のレイヤに分けて扱います。

| レイヤ | 変更しやすいもの | 主な場所 |
|--------|------------------|----------|
| C1 レシピ | steps, batch, lr, freeze | 実験 YAML |
| C2 方策タイプ | smolvla → act / diffusion 等 | `train.policy_type` |
| C3 前処理・正規化 | flip, resize, norm stats | データ変換 / policy config |
| C4 学習コード | 独自 loss, sampler | `parc.train` 新バックエンド |
| C5 評価ループ | サブセット設計 | eval YAML |

### C1. ハイパーパラメータ実験（まずここ）

1. `configs/experiments/smolvla_ft.yaml` をコピー（例: `smolvla_ft_10k_bs2.yaml`）  
2. `name` / `tags` / `train.*` だけ変える  
3. `dry_run: false`  
4. `bash scripts/train.sh ...`  
5. できた `pretrained_model` を評価 YAML の `policy.path` に書く  
6. `bash scripts/eval_ckpt.sh ...`  
7. `parc-list` と `metrics.json` の `by_category` を比較  

よく触るノブ（SmolVLA / LeRobot）:

| 項目 | YAML / CLI | メモ |
|------|------------|------|
| 学習長 | `train.steps` | smoke 200 → 本番は 5k〜数十 k から |
| バッチ | `train.batch_size` | Thor では 1〜4 から |
| VLM 重み | `load_vlm_weights` | 初回は true |
| 追加引数 | `train.extra_args` | lr, freeze, save_freq など |

例:

```yaml
train:
  steps: 10000
  batch_size: 2
  eval_freq: 0          # 学習中の env eval を切って加速
  extra_args:
    - --policy.optimizer_lr=1e-4
    - --save_freq=2000
    - --log_freq=100
```

学習中の LeRobot env eval は **素の LIBERO** 寄りになりがちです。  
**LIBERO-plus 摂動での本命比較は必ず `eval_ckpt.sh`** で行ってください。

### C2. 方策アーキテクチャの差し替え

```yaml
train:
  policy_type: smolvla    # act / diffusion など、入っている LeRobot 版を確認
```

差し替え後チェックリスト:

- [ ] `input_features` / `output_features` がデータキーと一致  
- [ ] 評価ラッパがその policy の `select_action` + preprocessor に対応（SmolVLA 以外は `lerobot_ckpt.py` を一般化）  
- [ ] カメラ解像度（eval の `camera_height/width`）を学習に近づける（256 推奨）

本選の Pi0 / Gr00t が来たら:

```yaml
train:
  backend: openpi   # or gr00t
```

`parc.train.run_training` にブランチを足し、checkpoint → `build_policy` アダプタを追加します（雛形は既に `not_implemented`）。

### C3. 観測・アクション定義の改善（アルゴリズム以前の I/O）

効果が大きいことが多いです。

- 言語: タスク言い換え、否定・指示の曖昧さへの頑健化  
- 画像: 解像度、wrist の有無、ドメインランダマイズ（光・背景は plus 評価と直結）  
- state: 8D 定義を崩さない／崩すなら eval も同期  
- action: chunk 長（SmolVLA の `n_action_steps`）と制御周波数の整合  

自前にプロセッサを足す場合は、学習時 preprocessor と `LeRobotCheckpointPolicy` の変換を **同じ仕様**にします。

### C4. 独自学習ループ・損失を入れる

薄いラッパでは足りないとき:

1. `src/parc/train/my_algo.py` を追加（`run_training(config, run_dir) -> dict`）  
2. `run_training` の `backend` 分岐に登録  
3. YAML:

```yaml
train:
  backend: my_algo
  # my_algo 固有キー
  lr: 1.0e-4
  loss: flow_matching
```

4. 成果物はできれば LeRobot 互換の `pretrained_model/`（`config.json` + weights + processor）に揃えると、既存の `eval_ckpt.sh` が使える  

独自形式の重みなら `parc.policies` に新しい `policy.type` を追加します。

### C6. GRPO / GSPO（オンライン RL）

`train.backend: grpo` または `gspo`。詳細は [09_autoloop_and_rl.md](09_autoloop_and_rl.md)。

```bash
bash scripts/train.sh configs/experiments/grpo_smoke.yaml
```

### C5. 評価駆動の改善サイクル（推奨ワークフロー）

```text
1. smoke_random / subset_eval（ランダム）で評価パイプライン健全性
2. smolvla_ft_smoke（短い FT）で学習→ckpt 接続
3. 本学習（steps↑ or 自前データ）
4. smolvla_ckpt_smoke_eval をコピーし path だけ更新
5. 比較用に tasks_per_category: 2, max_steps: 280
6. 弱いカテゴリ（Camera / Language / Light 等）を見て次のデータを足す
```

#### 掴み精度が出ないときの段階ゲート（long FT）

overnight（5k–10k）で SR=0・見当違い掴みは **学習不足の典型**。次を優先する:

| Gate | 判定 | 手段 |
|------|------|------|
| Gate1 | ボウル近傍へ接近・グリッパ閉が増える | `smolvla_subset_eval_gates` の動画 |
| Gate2 | `success_rate > 0` | 同 subset の `metrics.json` |
| Gate3 | 再現でも SR>0 | 同一 YAML 再実行 |

レシピ:

- base: `configs/experiments/smolvla_ft_long.yaml`（t003@10k resume, lr=5e-5）
- sweep: `configs/sweeps/long_ft_v1.yaml`（50k / 100k）
- Gate2 未達の次軸: `configs/sweeps/long_ft_unfreeze_v1.yaml`（vision unfreeze）
- 監視: `uv run scripts/check_ft_gates.py`

**Gate2 達成前に GRPO/GSPO を載せない**（ゼロ成功率 policy では探索が壊れる）。RL は [09](09_autoloop_and_rl.md) を Gate2 後に再開。

カテゴリ別の打ち手例:

| 弱いカテゴリ | 試しやすい打ち手 |
|--------------|------------------|
| Camera Viewpoints | 視点ランダマイズ・解像度・front 重視 |
| Language Instructions | 言い換えデモ追加・tokenizer 長 |
| Light / Background | 見た目多様化データ・色 jitter |
| Robot Initial States | 初期姿勢ばらつきのあるデモ |
| Sensor Noise | ノイズ付き画像での FT |
| Objects Layout | 配置バリエーション・失敗からの回復デモ |

---

## D. 設定テンプレ

- 公開データ FT: `configs/experiments/smolvla_ft.yaml`  
- 自前データ FT 雛形: `configs/experiments/smolvla_ft_custom_data.yaml`  
- ckpt 評価雛形: `configs/experiments/smolvla_ckpt_smoke_eval.yaml`  
- 変換例: `scripts/examples/convert_demo_to_lerobot.py`

学習:

```bash
bash scripts/train.sh configs/experiments/smolvla_ft_custom_data.yaml
```

評価:

```bash
# policy.path を学習 run の pretrained_model に書き換え
bash scripts/eval_ckpt.sh configs/experiments/smolvla_ckpt_smoke_eval.yaml
```

---

## D2. ベンチ追加手順（汎用枠）

PARC 本戦は LIBERO 固定。研究用に第2ベンチ（例: Meta-World MT50）を足す場合:

1. **`BenchmarkBackend` を実装** — [`parc/src/parc/benchmarks/base.py`](../src/parc/benchmarks/base.py) の契約（`list_task_ids` / `make_env` / `reset_episode` / `success` / `dataset_spec`）
2. **`@register_benchmark`** — 同ディレクトリにモジュールを置き、`registry.get_benchmark` の遅延 import 一覧へ追加
3. **評価 YAML** — `eval.backend: <name>` + `task_ids`（例: [`configs/experiments/mt50_smoke_random.yaml`](../configs/experiments/mt50_smoke_random.yaml)）
4. **DatasetSpec** — `backend.dataset_spec()` で LeRobot 向け features / `action_dim` を宣言
5. **学習骨格** — `benchmark.backend` を YAML に書く。現状非 LIBERO は `parc-train` が `not_implemented` + skeleton meta を返す（[`benchmark_dataset.py`](../src/parc/data/benchmark_dataset.py)）
6. **デモ変換（後続）** — `EpisodeConverter` を実装して raw → LeRobot root

MT50 依存は optional: `parc[metaworld]`（**別 venv 推奨**、[01_setup.md](01_setup.md) §5b）。VR テレオプは第1弾対象外。

---

## E. チェックリスト

**データ追加**

- [ ] front / wrist / state(8) / action(7) / task が揃っている  
- [ ] 関節角データなら `meta/angle_units.json`（`stored_unit=degrees`）と `parc-verify-demos --check-joint-angle-units`  
- [ ] 評価の `flip_images` とデータ慣習が一致  
- [ ] `dataset_root` または Hub `repo_id` が YAML に書かれている  
- [ ] 1 エピソードだけの overfit smoke で loss が下がることを確認  

**アルゴリズム改善**

- [ ] YAML をコピーし `name`/`tags` を変えた  
- [ ] 比較用 eval サブセットを固定した  
- [ ] ckpt を `eval_ckpt.sh` で回した  
- [ ] `metrics.json` の `by_category` を記録した  

**やってはいけないこと**

- LIBERO-plus `.venv` に依存ごと `parc` / `lerobot` を入れて NumPy を壊す（入れるなら `--no-deps`）  
- 学習中 LeRobot env スコアだけで plus 汎化を判断する  
- 公式提出 zip 形式を推測で固める（テンプレ配布まで待つ）  
- state / action 定義を eval とずらしたまま長時間学習する  

---

## 関連ドキュメント

| 文書 | 内容 |
|------|------|
| [02_data.md](02_data.md) | 公開データセット一覧・置き場 |
| [03_train.md](03_train.md) | train.sh / dry-run |
| [04_eval.md](04_eval.md) | parc-eval / eval_ckpt |
| [05_experiments.md](05_experiments.md) | run 管理・比較 |
| [06_competition.md](06_competition.md) | 本選配布後の接続 |
