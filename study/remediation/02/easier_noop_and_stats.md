<!-- tags: [no-noop, stats_key] -->
# もっと易しく: no-noop と stats_key

## 比喩

- **no-noop**: 料理動画から「ずっと手を止めてるシーン」をカットする。
- **stats_key**: 「どのものさし（平均・分散）で味付けしたか」のラベル。学習と評価で同じラベルを使う。

## 要点

1. 静止に近いステップが多いと、真似しても動きが鈍くなりやすい
2. 正規化統計が学習と評価で違うと、行動スケールが壊れる
3. PARC では VR の idle trim + versioned `stats_key`（M5）に翻訳する

## 反例

「全部 RLDS no-noop に置き換える」は PARC ではやらない（LeRobot / VR v3 方向と逆）。

戻る: [02_turbovla.md](../../02_turbovla.md)
