# Mix Phase B — cam 増量（2026-07-31）

## Why

Phase A reweight（base120+cam60）厚い 0.400 / Cam deep 0.10 < continue10k。重みだけでは不足 → **cam 本数を増やす**。

## Spec

| Item | Value |
|------|-------|
| Cam staging | `cam_views_staging_v2` |
| Cam LeRobot | `libero_cam_views_v2`（10 demos × 12 train-safe views = **120** eps） |
| Views | 既存 DEFAULT_VIEWS（eval hard 11/13/14_15 除外） |
| Mix | `libero_plus_cam_mix_v3` = base **180** + cam **120**（≈60/40） |
| FT | continue10k → +5k · lr 1e-5 · bs=8 · **thor**（既定ホスト） |
| Eval | thin smoke ignore; thor thick + Cam deep |
| Parent bar | thick ≥ 0.514 and Cam deep ≥ 0.20 |

## Forbidden

cam-only FT; thin-only parent pick.
