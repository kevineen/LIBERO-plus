# 04. ローカル評価

## LIBERO-plus の約束事

- 公式 README: **`num_trials_per_task = 1`**（素の LIBERO の 50 ではない）
- 摂動メタ: `libero/libero/benchmark/task_classification.json`
- タスク数が suite あたり数千あるため、**必ず task_ids か tasks_per_category で絞る**

## 実行

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
export MUJOCO_GL=egl

# ランダム方策スモーク（LIBERO-plus .venv）
./scripts/parc.sh eval -c configs/experiments/smoke_random.yaml

# カテゴリごとに 2 タスクずつ
./scripts/parc.sh eval -c configs/experiments/subset_eval.yaml

# SmolVLA 等の LeRobot checkpoint（robot venv + CUDA）
bash scripts/eval_ckpt.sh configs/experiments/molmoact2_hf_smoke_eval.yaml
```

### upstream `lerobot-eval`（Web モニター対応）

PARC の `parc-eval` とは別経路。出力先は sibling の `lerobot/eval_logs/`（Web の **Evals** タブが読む）。

```bash
cd /home/kevin/Matsuo/LIBERO-plus/lerobot
lerobot-eval \
  --policy.path=lerobot/pi05_libero_finetuned \
  --policy.device=cuda \
  --policy.compile_model=false \
  --policy.n_action_steps=10 \
  --env.type=libero_plus \
  --env.task=libero_spatial,libero_object,libero_goal,libero_10 \
  --eval.batch_size=1 \
  --eval.n_episodes=10 \
  --eval.use_async_envs=false \
  --env.max_parallel_tasks=1 \
  --output_dir=./eval_logs/libero_plus_full_benchmark/
```

| ファイル | 内容 |
|----------|------|
| `eval_info.json` | 集約 SR・`per_task` / `per_group` / `overall`。**各タスク完了後に上書き**（`status`: `running` \| `finished`、`completed_tasks` / `total_tasks`） |
| `videos/<suite>_<taskId>/eval_episode_N.mp4` | エピソード動画 |

ブラウザ: `bash scripts/start_web.sh` → **Evals** `/evals` → run → タスク詳細（[10_ops_ui.md](10_ops_ui.md)）。  
`LEROBOT_EVAL_LOGS_DIR` でログ親を変更可能（[08_remote_and_ui.md](08_remote_and_ui.md)）。

成果物（`experiments/<run_id>/` · `parc-eval` / `eval_ckpt.sh`）:

| ファイル | 内容 |
|----------|------|
| `config.yaml` | 実行時設定 |
| `metrics.json` | 成功率・カテゴリ別・エピソード一覧 |
| `episodes.jsonl` | 1 行 1 エピソード |
| `meta.json` | ステータス |

## 設定の要点

```yaml
eval:
  # 省略時は libero。研究用 MT50 は backend: metaworld_mt50（別 venv・01_setup §5b）
  # backend: libero
  suite: libero_spatial
  num_trials_per_task: 1
  task_ids: [0, 1, 2]          # または
  # tasks_per_category: 2
  max_steps: 280
  use_classification: true
policy:
  type: random                 # zero / checkpoint
  # type: checkpoint
  # path: experiments/<run>/train_output/checkpoints/000200/pretrained_model
  # device: cuda
```

## メトリクス

現時点で集計しているもの:

- **success_rate**（全体・カテゴリ別・タスク別 `by_task`）
- **mean_steps**
- **path_length** / **jerk**（アクション差分の簡易代理。PARC 公式定義が出たら差し替え）
- **collision**（プレースホルダ）
- **backend**（`metrics.json` に評価バックエンド名）

説明会の最終スコアは「重み付け正規化（重み非公開）」なので、  
ローカルでは **カテゴリ別成功率の改善** を主指標にするのが安全です。

## 全ベンチは重い

4 suite × 約 1 万タスクは現実的ではありません。  
開発中は `tasks_per_category: 2〜5`、提出前にだけ規模を拡大してください。

## 動画・フレーム

```yaml
eval:
  save_frames: true
  save_video: true      # imageio/ffmpeg が必要。失敗時は PNG にフォールバック
  frame_stride: 5
  max_save_frames: 40
```

成果物は `experiments/<run_id>/videos/`。  
ブラウザプレビューは `bash scripts/start_web.sh` → Run 詳細（[08_remote_and_ui.md](08_remote_and_ui.md)）。

upstream `lerobot-eval` の動画は **Evals** タブ（上記 §upstream）でタスク単位に閲覧します。

## 注視マップ（SmolVLA saliency）

失敗エピソードで「どこを見ているか」を確認する。真の cross-attention ではなく、vision encoder の **活性化マップ**（既定）または **Grad-CAM**（action L2 標的）。

```yaml
eval:
  save_video: true
  save_attention: true
  attention_on_failure_only: true   # 既定 true（成功時は *_attn を捨てる）
  attention_method: activation      # or gradcam
  attention_stride: 5               # 省略時は frame_stride
policy:
  type: checkpoint
  flip_images: true
  path: .../pretrained_model
```

薄スライス例: 既存 run の checkpoint パスを YAML に指定（旧 `smolvla_lang_hard_attention*.yaml` は git 履歴参照）  
配線スモーク（短尺）: `configs/experiments/molmoact2_hf_smoke_eval.yaml` 等

```bash
bash scripts/eval_ckpt.sh configs/experiments/molmoact2_hf_smoke_eval.yaml
# 注視マップ付き評価は eval YAML に save_attention: true を追加
# PARC_EVAL_NO_NOTIFY=1 bash scripts/eval_ckpt.sh … --no-notify
```

成果物（失敗時）:

| ファイル | 内容 |
|----------|------|
| `videos/task####_trial##_attn.mp4` | 左=env RGB / 右=注視オーバーレイ |
| `videos/manifest.json` | `attention_video` パス |

**向き:** 保存動画の RGB は unflipped env 画像。方策入力は 180° flip のため、ヒートマップは計算後に unflip して重ねている。

**解釈:** 活性化 / Grad-CAM は因果の証明ではなく仮説生成用。語彙 OOD では「正しい物体を見ていても行動が死ぬ」こともある。
