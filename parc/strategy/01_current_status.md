# 01. 現在の状況（スナップショット）

時点: **2026-07-30 16:09 JST 頃**

## 一言

- mix10k 評価完了（厚い **0.514** / Camera deep **0.12**）→ 親候補として有望。
- **winpc**: mix10k→+10k continue FT を投入・running。
- nuc は本日 NVIDIA TDR（0x116）で落ちたあと復旧。Camera deep クロスは要再確認。

## マシン別

### winpc（mainpc）

| 項目 | 状態 |
|------|------|
| worker | 稼働中 |
| running | mix continue10k · `q_20260730T070854…a66dc81d` · train |
| config | `smolvla_ft_libero_cam_mix_continue10k_winpc.yaml` |
| pretrained | mix10k `…6133f628…/010000` |

### thor

| 項目 | 状態 |
|------|------|
| worker | （空想定） |
| 直近完了 | mix10k 厚い 0.514 · Camera deep 0.12 |

### nuc

| 項目 | 状態 |
|------|------|
| 到達 | 復旧済み（再起動後 GPU ok · 30°C） |
| 注意 | WSL/Windows `nvlddmkm` TDR。過熱証拠なし |
| 前回 running | 親 Camera deep クロス（クラッシュで中断の可能性） |
