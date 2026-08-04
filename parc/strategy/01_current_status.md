# 01. 現在の状況（スナップショット）

時点: **2026-08-04 12:34 JST 頃**

## 一言

- **親 = continue10k 凍結**。cam FT 禁止。
- **thor**: Phase D1 Stage2 full FT **running**（親判定外 · 10k · from Stage1）。
- D2 Sensor hard deep **done** · SR=**0.20**（親判定外）。
- Evo-1 ×10 / ラベル置換 FT / Sensor 短 FT は未着手。

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
| 走行中 | **Stage2 full FT** · `q_20260804T033323…edf56815` · train · 10k steps |
| YAML | `sidecar_smolvla_ft_twostage_stage2_full_from_stage1_thor.yaml` |
| from | Stage1 `…72c5af3f…/005000` |
| 直後 eval | 薄い Lang hard 984/986/988×1（親決め禁止） |
| キュー | running 1 |
| 直前完了 | D2 Sensor hard · SR=**0.20** · `…ec7286b4_…` |

### nuc

| 項目 | 状態 |
|------|------|
| GPU | reachable · 空き埋め可 |
