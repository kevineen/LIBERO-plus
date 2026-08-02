# a04 — 解答（Upstream smoke）

## 選択

| 問 | 正答 | 解説 |
|----|------|------|
| Q1 | **B** | smoke またはウォークスルー記録が必須 |
| Q2 | **B** | server を先に起動 |
| Q3 | **A** | stats と chunk/open-loop を学習時と揃える |
| Q4 | **A** | baselines 記載の thor パス |
| Q5 | **B** | README が成功率・安定性に触れ警告 |

## 短答（模範）

**S1.** 例: `evaluate.py` 必須引数一覧、`chunk_size==num_open_loop_steps` の理由、使う `stats_key`、HF ckpt 一覧メモ。

**S2.** server が生きているか、ポートが一致しているか（その他: ファイアウォール、bind アドレス）。

## トラブルシュート

**T1.** `num_open_loop_steps` を 12 に合わせる（または両方を意図した同一値に）。open-loop 実行長と chunk ホライズンを一致させ、公式・比較可能なプロトコルにする。
