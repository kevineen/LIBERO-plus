# notebooks

`notebooks/` は授業課題まわりの実験と提出物を整理する場所です。日常の試行錯誤と、最終提出する Colab ノートを分けて管理します。

## 役割

- `upstream/`: 配布元原本。
- `lib/`: 実験で再利用する Python コード。ローカル実行や薄いノートから読み込みます。
- `experiments/`: 1 実験 1 ノートの作業場所。先頭セルに仮説、変更点、成功条件、結果、次を書く運用です。
- `experiments/sweeps/`: パラメータグリッド（parc / lifelong）。`_schema.md` を参照。
- `configs/profiles/`: 実験条件を切り替える YAML。suite、task、seed、モデルパスをここで管理します。
- `runs/`: notebook 由来の一時成果物と `results.sqlite`。**スコアはここに記録する**が、実行ごとに変わるため **Git では追跡しない**（`.gitignore`）。ディレクトリだけ `.gitkeep` で残す。
- `submit/`: 提出用に凍結した単一ノートだけを置きます。

## 今の提出候補

- `submit/advanced_colab.ipynb`

このファイルを日常の実験場にせず、`experiments/` や `lib/` で固めた内容だけを移植します。

## よく使うコマンド

リポジトリルートで実行します。

```bash
export PYTHONPATH=notebooks/lib

# 既存モデルの比較評価（lerobot-eval）
uv run -m libero_eval_compare list-profiles
uv run -m libero_eval_compare compare --profile spatial \
  --baseline-eval workdir/eval/base \
  --finetuned-eval workdir/eval/spatial_lora
uv run -m libero_eval_compare run --profile all

# スイープ投入（SmolVLA / parc）。別ターミナルで worker を起動する。
#   cd parc && uv run parc-worker --loop --poll-sec 30
python -m exp_orchestrator enqueue --sweep notebooks/experiments/sweeps/smolvla_lora_r_steps.yaml
python -m exp_orchestrator status --parc
python -m exp_orchestrator pause <job_id>
python -m exp_orchestrator resume <run_id>
python -m exp_orchestrator collect
python -m exp_orchestrator ranking --sweep-id smolvla_lora_r_steps

# lifelong を順次実行（途中停止は pause --lifelong → resume_latest.pth から再開）
python -m exp_orchestrator lifelong-run --sweep notebooks/experiments/sweeps/lifelong_policy_seed.yaml
python -m exp_orchestrator pause lifelong_policy_seed_t000 --lifelong
```

## 実験オーケストレータ

| 役割 | 置き場 |
|------|--------|
| スイープ YAML | `experiments/sweeps/`（スキーマは `_schema.md`） |
| CLI | `python -m exp_orchestrator`（`lib/exp_orchestrator/`） |
| SmolVLA 学習〜評価 | `parc` の queue（enqueue / cancel=Pause / resume） |
| lifelong 学習 | `libero/lifelong` + `resume_latest.pth` |
| スコア DB | `runs/results.sqlite`（ローカルのみ。人間向け要約は `configs/experiments.md`） |

## 実験ログ

- 実験一覧と結果メモ: `configs/experiments.md`（Git で共有する要約）
- 比較ノート例: `experiments/2026-08-24_spatial-lora-compare.ipynb`
- 新規ノート開始用: `experiments/_template.ipynb`（投入・停止・再開・ランキングセル付き）
- sweep 定義: `experiments/sweeps/_schema.md`

## 運用ルール

- upstream ノートを `Copy1` や `のコピー` で増やさない
- 変更ロジックは notebook に埋め込まず、まず `lib/` に寄せる
- 提出前に Colab で最初から最後まで実行確認する
- `runs/` の sqlite / ログはコミットしない。再現に必要な知見は `configs/experiments.md` かノートに残す
