# 01. 現在の状況（スナップショット）

時点: **2026-07-30 18:01 JST 頃**

## 一言

- **mix continue+10k 完了**（winpc · job `q_…a66dc81d` · ckpt `010000`）。
- 直後の薄い eval は Camera のみ **SR=0.000**（親決めには使わない）。
- thor では continue10k の **厚い eval が running**、Camera deep が **queued**。
- nuc は本日 NVIDIA TDR（0x116）復旧済み。重いジョブは控えめ。

## マシン別

### winpc（mainpc）

| 項目 | 状態 |
|------|------|
| worker | 稼働中（キュー空） |
| 直近完了 | mix continue10k · `q_20260730T070854…a66dc81d` · train_eval |
| run_id | `20260730T071018Z_winpc_cbbf5c8b_smolvla_ft_libero_cam_mix_continue10k_wi` |
| ckpt | `…/010000/pretrained_model` |
| 薄い eval | Camera 5/5 fail · SR=0.000（設計どおり Cam-only smoke） |

### thor

| 項目 | 状態 |
|------|------|
| worker | 稼働中 |
| running | continue10k 厚い eval · `q_20260730T090115…7903a580` |
| queued | continue10k Camera deep · `q_20260730T090115…72667de5` |
| 直近完了 | mix10k 厚い 0.514 · Camera deep 0.12 |

### nuc

| 項目 | 状態 |
|------|------|
| 到達 | 復旧済み（再起動後 GPU ok） |
| 注意 | WSL/Windows `nvlddmkm` TDR |
| 前回 | 親 Camera deep クロス（クラッシュで中断の可能性） |
