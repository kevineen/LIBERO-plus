# Mix v2 reweight (Phase A / A1) — 2026-07-31

## Goal

Increase cam episode share without new re-renders. Parent stays continue10k until thick+Cam deep say otherwise.

## Spec

| Item | Value |
|------|-------|
| Dataset | `libero_plus_cam_mix_v2` |
| Base | 120 eps from same `lerobot/libero_plus` snapshot as v1 |
| Cam | 60 eps from `libero_cam_views_v1` (unchanged) |
| Ratio | ≈67/33 (v1 was 80/20) |
| Seed | 42 |
| FT | continue10k → +5k · lr 1e-5 · bs=8 · winpc |
| Eval | thin smoke ignore; thor thick + Cam deep for parent pick |

## Success

Thick SR ≥ 0.514 and Cam deep ≥ 0.20 (and Camera not all-zero worse). Else keep parent → Phase B (more cam data).

## Forbidden

cam-only FT; extending v1 mix recipe; parent pick from thin eval.
