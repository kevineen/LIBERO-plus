# 09. 無人実験ループと GRPO/GSPO

アイデアが無いとき・PC に触れないときも、ディスクを溢れさせずに train→eval を回し続けるための運用手順です。

## 全体像

```text
configs/sweeps/*.yaml
        │
        ▼
 parc-enqueue  →  experiments/queue/queue.jsonl
        │
        ▼
 parc-worker   →  train.sh / GRPO  →  eval_ckpt（固定 subset）
        │
        ▼
 registry.jsonl + metrics.json
        │
        ▼
 parc-prune（keep_best / keep_last / 予算）
```

比較軸は常に同じ eval テンプレ（カテゴリ別 `success_rate`）。

## セットアップ（一度だけ）

1. [`configs/paths.yaml`](../configs/paths.yaml) で `experiments_dir` / `data_dir` / `hf_home` を `/mnt/sda/...` に向ける（リポジトリ既定済み）
2. ディレクトリ作成は `parc-smoke --skip-env` または初回 enqueue で自動
3. ワーカーは tmux / systemd で常駐

```bash
cd /path/to/LIBERO-plus/parc
uv sync
uv run parc-smoke --skip-env
```

## 一晩回す（SFT スイープ）

```bash
uv run parc-enqueue --sweep configs/sweeps/overnight_ft_smoke.yaml
# 常駐
uv run parc-worker --loop --poll-sec 30
```

本番寄り:

```bash
uv run parc-enqueue --sweep configs/sweeps/overnight_ft_v1.yaml
uv run parc-worker --loop
```

単発:

```bash
uv run parc-enqueue -c configs/experiments/smolvla_ft_smoke.yaml \
  --eval-config configs/experiments/smolvla_ckpt_smoke_eval.yaml
uv run parc-worker --once
```

## スコア・進捗・再開（UI）

Web の **Jobs / Queue** パネルと **Docs** から操作できます。詳細は [10_ops_ui.md](10_ops_ui.md)。

```bash
uv run parc-queue status
uv run parc-queue recover-stale --max-age-sec 3600
uv run parc-queue requeue <job_id>
uv run parc-queue resume <run_id> --mode auto
```

ワーカー起動時に stale `running` を自動回収します（`--no-recover-stale` で無効化）。

## ディスク予算

| コマンド | 意味 |
|----------|------|
| `uv run parc-prune --dry-run` | 削除候補だけ表示 |
| `uv run parc-prune` | `keep_best` + `keep_last` + `protected` 以外を削除し予算内へ |

`paths.yaml` の `disk:`:

```yaml
disk:
  max_bytes_gb: 80
  keep_best: 5
  keep_last: 3
  protected_tags: [protected, baseline]
```

ワーカーは予算超過時に prune を試し、それでもダメなら **新規 train を拒否**します。  
自動ループでは `save_video: false`（スイープ展開時に強制）。ckpt は最終 1 個に刈り込みます。

## 再現性メタ

各 run の `meta.json` に以下が入ります。

- `seed` / `config_hash` / `git_sha` / `git_dirty`
- `eval_fingerprint` / `env_fingerprint`
- `sweep_id` / `trial_index` / `parent_run_id`

一覧:

```bash
uv run parc-list --limit 50
uv run parc-list --sweep-id overnight_ft_smoke
```

## Web 監視

```bash
export PARC_WEB_ALLOW_JOBS=1
export PARC_WEB_LAUNCHER=queue   # start_web.sh の既定
bash scripts/start_web.sh
```

POST `/api/v1/jobs` はキューへ書くだけです。消化は別ターミナルの `parc-worker` が行います。

## Phase 2: GRPO / GSPO

**前提:** 教師あり FT で固定 subset の **Gate2（`success_rate > 0`）** を先に達成する。  
SR=0 のまま大規模 RL を載せない（掴み精度改善は `long_ft_v1` → 必要なら `long_ft_unfreeze_v1`。手順は [07](07_custom_data_and_algos.md) / [10](10_ops_ui.md)）。

`train.backend: grpo`（token-level）または `gspo`（sequence-level）。  
報酬はエピソード success（0/1）。方策は状態→対角ガウス MLP（スモーク用）。ロールアウト生データは `save_rollouts: false` 既定で捨てます。

```bash
# robot venv + CUDA（Jetson Thor）
bash scripts/train.sh configs/experiments/grpo_smoke.yaml
bash scripts/train.sh configs/experiments/gspo_smoke.yaml

# キュー経由（worker が train.sh を呼ぶ）
uv run parc-enqueue --sweep configs/sweeps/overnight_grpo_smoke.yaml
uv run parc-worker --loop
```

ckpt は `train_output/pretrained_model/`（`grpo_policy.pt`）。評価は `policy.type: grpo_gaussian`。

本選の Pi0 / Gr00t や SmolVLA 本体の log-prob 対応は、同じ `train.backend` 契約にアダプタを足す想定です。

## スイープ YAML の約束

- 変える軸は **最大 2**（超過はエラー）
- `base` + `eval_template` + `search` + `disk`
- 例: [`configs/sweeps/overnight_ft_smoke.yaml`](../configs/sweeps/overnight_ft_smoke.yaml)

## 関連

- [05_experiments.md](05_experiments.md)
- [00_overview.md](00_overview.md)
- [08_remote_and_ui.md](08_remote_and_ui.md)
- [07_custom_data_and_algos.md](07_custom_data_and_algos.md)
