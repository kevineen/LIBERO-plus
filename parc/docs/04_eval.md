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
bash scripts/eval_ckpt.sh configs/experiments/smolvla_ckpt_smoke_eval.yaml
```

成果物（`experiments/<run_id>/`）:

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
