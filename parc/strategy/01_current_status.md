# 01. 現在の状況（スナップショット）

時点: **2026-07-31 08:26 JST 頃**

## 一言

- **親 = continue10k** 維持（厚い 0.514 · Cam deep **0.20**）。
- **mix v2 Phase A** 完了: winpc FT +5k · 薄い **SR=0.571**（Cam/Lang **0.000**）。
- **thor**: mix v2 厚い **running** · Camera deep **queued**（親判定待ち）。
- nuc 不通のまま。

## マシン別

### winpc（mainpc）

| 項目 | 状態 |
|------|------|
| worker | 稼働想定 |
| running / queued | なし |
| 直近完了 | mix v2 · `q_…a908742f` · run `20260730T221003Z_winpc_c9dc1b28_…` · 薄い **0.571** · ckpt `005000` |
| 親 ckpt | continue10k `…cbbf5c8b…/010000/pretrained_model` |
| dataset | `libero_plus_cam_mix_v2`（120+60=180 eps） |

### thor

| 項目 | 状態 |
|------|------|
| worker | 稼働中 |
| running | mix v2 厚い · `q_…c054cdce` · `smolvla_thick_eval_mix_v2_on_thor` |
| queued | mix v2 Cam deep · `q_…3e13c45d` · `smolvla_camera_deep_eval_mix_v2_on_thor` |
| ckpt 到着 | `…/imported/20260730T221003Z_winpc_c9dc1b28_…/005000/pretrained_model` **確認済** |
| 直近完了 | lr↓5k 厚い **0.371** · Cam deep **0.14**（敗北） |

### nuc

| 項目 | 状態 |
|------|------|
| 到達 | **不通**（`100.82.118.86` SSH timeout） |
| 想定 | Tailscale / WSL sshd 未起動の可能性 |
| 次 | 到達後に `parc-fleet hosts` · worker 確認。ジョブは積まない |
