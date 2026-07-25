# 05. 実験管理

## なぜ必要か

コンペでは「どのデータ・何ステップ・どの評価サブセットで何点か」を追えないと、  
改善が再現できません。`parc` は軽量な **YAML + run ディレクトリ + JSONL レジストリ** にしています。

## ランの作り方

```bash
uv run parc-new -c configs/experiments/subset_eval.yaml --notes "camera弱いか確認"
uv run parc-eval -c configs/experiments/subset_eval.yaml
uv run parc-list
```

`parc-eval` / `parc-train` は内部で run を新規作成します。  
既存 run で再評価する場合:

```bash
uv run parc-eval -c configs/experiments/subset_eval.yaml \
  --run-dir experiments/<run_id>
```

## ディレクトリ規約

```text
experiments/
  registry.jsonl                 # 追記型ログ（最新行が新しい状態）
  20260725T123000Z_thor_a1b2c3d4_smoke_random/
    config.yaml
    config.source.yaml
    meta.json                    # machine_id 含む
    metrics.json
    episodes.jsonl
    checkpoints/
    videos/
    logs/
```

`run_id` は `{utc}_{machine}_{uuid8}_{name}`（詳細は [11_multi_machine.md](11_multi_machine.md)）。

## YAML の書き方

1. `configs/experiments/` のどれかをコピー  
2. `name` / `tags` / `eval` / `policy` / `train` を編集  
3. コミットしてよいのは **configs だけ**（重み・metrics・`paths.yaml` は gitignore）

## 比較のしかた

```bash
uv run parc-list --limit 50
# 詳細は各 run の metrics.json の by_category を見る
python3 - <<'PY'
import json, pathlib
for p in sorted(pathlib.Path("experiments").glob("*/metrics.json"))[-5:]:
    m=json.loads(p.read_text())
    print(p.parent.name, m.get("success_rate"), list((m.get("by_category") or {}) .keys())[:3])
PY
```

## 拡張案（任意）

- Weights & Biases: `logs/` に加えて `wandb.init` を `cli.py` に足す  
- SQLite: `registry.jsonl` を後で移行  
- マルチ suite: `eval.suites: [...]` を runner に追加

## 無人ループ・スイープ・prune

アイデアが無くても回し続ける手順は [09_autoloop_and_rl.md](09_autoloop_and_rl.md)。

```bash
uv run parc-enqueue --sweep configs/sweeps/overnight_ft_smoke.yaml
uv run parc-worker --loop --poll-sec 30
uv run parc-prune --dry-run
uv run parc-list --sweep-id overnight_ft_smoke
```

各 run の `meta.json` には `git_sha` / `config_hash` / `eval_fingerprint` / `sweep_id` / `machine_id` などが入ります。

複数 PC での分離は [11_multi_machine.md](11_multi_machine.md)。
