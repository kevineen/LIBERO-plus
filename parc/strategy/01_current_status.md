# 01. 現在の状況（スナップショット）

時点: **2026-08-03 06:50 JST 頃**

## 一言

- **親 = continue10k 凍結**。cam FT 禁止。
- **Stage1 二段階 FT 完了**（thor · SR=0.000 on Lang hard thin · 親判定外）。
- **Evo-1 Language hard thin 完了**（winpc · SR=0.000 · 親判定外）。
- Stage2 / Evo-1 ×10 / flash-attn は **別承認**。

## マシン別

### winpc（mainpc）

| 項目 | 状態 |
|------|------|
| 役割 | D3 VR + Evo-1 sidecar |
| 直近 | Evo-1 Lang hard thin **0/3** · server 停止済 |
| 親 ckpt | continue10k |

### thor

| 項目 | 状態 |
|------|------|
| 直近 | Stage1 expert-only **done** · `q_…fce856bb` · run `20260802T210934Z_thor_72c5af3f_…` |
| 薄い Lang hard | **SR=0.000**（984/986/988×1）· 親判定外 |
| ckpt | `…/checkpoints/005000` |
| キュー | idle |
| 次 | Stage2 は結果レビュー後に別承認 |

### nuc

| 項目 | 状態 |
|------|------|
| GPU | reachable · 空き埋め可 |
