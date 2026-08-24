# Notebook Experiments

`notebooks/experiments/` で回した試行の要約を書きます。途中参加でもここを見れば、何を試して何が残っているか追える状態を保ちます。

機械可読なスコアは `notebooks/runs/results.sqlite` に溜まりますが、**Git 対象外**です。共有したい結論はこの表に残します。

## 書き方

1. 1 実験につき 1 行追加する
2. ノート名、プロファイル / sweep、変更点、結果、次アクションを書く
3. 数値だけでなく、失敗理由も短く残す

## テンプレート

| Date | Notebook | Profile / Sweep | Change | Result | Next |
|---|---|---|---|---|---|
| 2026-08-24 | `2026-08-24_spatial-lora-compare.ipynb` | `spatial` | compare レイアウト整理後の再集計ノートに移行 | pending | 実行後に成功率と差分を書く |
| 2026-08-25 | `_template.ipynb` + `exp_orchestrator` | `smolvla_lora_r_steps` / `lifelong_policy_seed` | sweep YAML・Pause/Resume・SQLite 集計を追加 | tooling ready | 実スイープを回して SR を記入 |

## オーケストレータ早見

```bash
export PYTHONPATH=notebooks/lib
python -m exp_orchestrator enqueue --sweep notebooks/experiments/sweeps/smolvla_lora_r_steps.yaml
# parc/: uv run parc-worker --loop
python -m exp_orchestrator collect
python -m exp_orchestrator ranking --sweep-id smolvla_lora_r_steps
```

詳細: [notebooks/README.md](../README.md) · [sweeps/_schema.md](../experiments/sweeps/_schema.md)

## メモ

- 日常の比較・検証は `experiments/` と `lib/` に寄せる
- 提出に採用する経路が固まったら `submit/advanced_colab.ipynb` に移植する
