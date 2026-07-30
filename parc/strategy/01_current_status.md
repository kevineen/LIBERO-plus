# 01. 現在の状況（スナップショット）

時点: **2026-07-31 05:09 JST 頃**

## 一言

- **親 = continue10k** 維持（厚い 0.514 · Cam deep **0.20**）。
- winpc lr↓5k 完了（薄い 0.500）。ckpt を thor `imported/` へ rsync 済み。
- **thor**: lr↓5k 厚い + Camera deep を投入（親更新判定待ち）。
- **VR**: データ品質 M1–M4（filter / RTT / queue / replay / Approx Time）ソフト完了。Quest 実機 E2E は blocked。

## マシン別

### winpc（mainpc）

| 項目 | 状態 |
|------|------|
| worker | 稼働中（キュー空） |
| running / queued | なし |
| 親 ckpt | continue10k `…cbbf5c8b…/010000/pretrained_model` |
| 直近完了 | lr↓5k · job `q_20260730T184655…380a43e2` · run `20260730T184742Z_…c7e7c8f2_…` · 薄い **0.500** · ckpt `005000` |

### thor

| 項目 | 状態 |
|------|------|
| worker | 稼働想定 |
| running / queued | 厚い `q_20260730T200858…8aa312ee` · Cam deep `q_20260730T200859…3283952d` |
| ckpt | `imported/…lr5e6_5k_wi/005000/pretrained_model` |
| 直近完了 | continue10k 厚い **0.514** · Cam deep **0.20** |

### nuc

| 項目 | 状態 |
|------|------|
| 到達 | **不通**（2026-07-31 05:33）WSL `100.82.118.86` ping/SSH timeout |
| Windows | Tailscale `100.77.194.30` は ping・:22 生存。**SSH 鍵未整備**のため `shutdown /r` 不可 |
| 再起動 | リモート不可 → **手元／帯域外**が必要。戻ったら `parc-fleet hosts` / `gpu-check --host nuc` |
