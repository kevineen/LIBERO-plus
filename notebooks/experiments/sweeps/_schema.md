# Sweep / trial YAML スキーマ

`notebooks/experiments/sweeps/` に置く実験定義です。実行は `python -m exp_orchestrator` 経由で、SmolVLA は `parc` キューに流し、lifelong は Hydra 学習を順次起動します。

スコアは `notebooks/runs/results.sqlite` に記録されます（ローカル専用・Git 非追跡）。人間向けの結論は `notebooks/configs/experiments.md` に残します。

## 共通フィールド

| キー | 必須 | 説明 |
|------|------|------|
| `name` | はい | スイープ ID。結果 DB の `sweep_id` になる |
| `kind` | はい | `parc`（SmolVLA/LoRA）または `lifelong` |
| `mode` | いいえ | `grid`（既定）または `random` |
| `max_jobs` | いいえ | 展開する trial の上限（既定 20） |
| `seed` | いいえ | random モードの乱数種 |
| `search` | いいえ | 探索軸。値はリスト。dot-path でネスト指定 |
| `notes` | いいえ | 人間向けメモ |

`parc` のスイープは探索軸が **最大 2**（`parc.sweep.expand` の制約）。軸を増やすときはスイープを分割する。

## kind: parc

`parc-enqueue --sweep` が読む形式。パスは `parc/` からの相対で書く。

```yaml
name: smolvla_example
kind: parc
base: configs/experiments/smolvla_ft_smoke.yaml
eval_template: configs/experiments/smolvla_subset_eval.yaml
mode: grid
max_jobs: 4
force_dry_run: false
search:
  train.steps: [200, 400]
  seed: [42]
```

探索軸の例:

- ベースモデル: `train.extra_args` に `--policy.pretrained_path=...` を含める（リストの要素ごと）
- データ: `train.dataset_repo_id` / `train.dataset_root`
- ハイパラ: `train.steps`, `train.batch_size`, `seed`

## kind: lifelong

`libero/lifelong/main.py` へ渡す Hydra 上書きのグリッド。

```yaml
name: lifelong_example
kind: lifelong
mode: grid
max_jobs: 4
defaults:
  benchmark_name: LIBERO_SPATIAL
  lifelong: multitask
  train.n_epochs: 2
search:
  policy: [bc_transformer_policy]
  seed: [10000, 10001]
```

`defaults` は全 trial 共通の Hydra override。`search` のキーはそのまま CLI になる（`policy=...`, `seed=...`）。
