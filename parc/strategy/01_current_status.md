# 01. 現在の状況（スナップショット）

時点: **2026-07-30 08:12 JST 頃**

## 一言

- 弱点深掘りバッチ **完了**。Camera は +15k がわずかに良いが hard 未解決。親は unfreeze 維持。
- **次学習軸 = dataset mix**（公開 + cam 再レンダ）。フォロー eval を thor/nuc で消化中。

## マシン別

### thor

| 項目 | 状態 |
|------|------|
| worker | 稼働中 |
| running | Language hard · `q_…c8f18f52` |
| queued | +15k Camera hard · `q_…96b8aa6d` |
| 直近完了 | 深掘りバッチ（Sensor 0.20 / Lang 0.20 / Robot 0.16 / Cam +15k 0.12） |

### nuc

| 項目 | 状態 |
|------|------|
| worker | 稼働中 |
| running | 親 Camera deep クロス · `q_…9ec45635` |
| ckpt | imported 親 unfreeze `030000` |

### winpc

キュー空。**mix CLI 実装済み**（`parc-mix-datasets`）。次は mix データ生成 → dry-run → 確認後に winpc 短 FT。

## 深掘りサマリ（親 unfreeze 以外）

| eval | SR |
|------|---:|
| +15k mild 608/609 | 0.30 |
| +15k Camera full | 0.12 |
| continue Camera | 0.04 |
| 親 Camera / Sensor / Lang / Robot | 0.08 / 0.20 / 0.20 / 0.16 |
