# Evo-1 — LIBERO-plus

最終更新: 2026-08-03  
親判定: **しない**（研究サイドカー）  
調査メモ: [`../../00_research/turbovla_evo1.md`](../../00_research/turbovla_evo1.md)

## 共通

| 項目 | 値 |
|------|-----|
| Upstream | [MINT-SJTU/Evo-1](https://github.com/MINT-SJTU/Evo-1) · `libero-plus-eval/` |
| Checkpoint | `MINT-SJTU/Evo1_LIBERO` |
| Clone (thor) | `/mnt/sda/parc_libero_plus/third_party/Evo-1` |
| Weights (thor) | `/mnt/sda/parc_libero_plus/checkpoints/Evo1_LIBERO`（**1.5G · done**） |
| 推論 I/F | WebSocket policy server ↔ sim client |
| 親 SmolVLA | continue10k thick **0.514** · Cam deep **0.20** · Lang hard **0.10** |

---

## Upstream 公表（著者 `libero-plus-eval/README.md` · 自前再測ではない）

| Suite | background | camera | language | layout | light | noise | robot | avg |
|-------|----------:|-------:|---------:|-------:|------:|------:|------:|----:|
| Spatial | 86.43 | **38.03** | 68.97 | 67.53 | 86.64 | 75.21 | 49.14 | 67.42 |
| Object | 91.13 | 60.35 | 78.81 | 71.46 | 88.22 | 76.07 | 49.50 | 73.65 |
| Goal | 83.63 | 50.74 | **38.29** | 52.47 | 89.61 | 66.49 | 48.41 | 61.38 |
| 10 | 80.97 | **30.31** | 68.41 | 59.94 | 67.88 | 63.92 | 50.64 | 60.30 |
| **Avg.** | **85.54** | **44.86** | **63.62** | **62.85** | **83.09** | **70.42** | **49.42** | **65.69** |

PARC 接点:

- Camera ~45% / Robot ~49% → continue10k の Camera/Robot 弱点と整合する外部天井
- Goal language 38% → Language OOD もスイート依存で弱い

**parc-eval 同尺の自前薄スライスが正。** 公表表は仮説立て用。

---

## Setup 進捗（thor · 2026-08-03）

| Step | Status | Notes |
|------|--------|-------|
| Clone Evo-1 | **done** | `/mnt/sda/parc_libero_plus/third_party/Evo-1` |
| HF `Evo1_LIBERO` | **done** | `/mnt/sda/parc_libero_plus/checkpoints/Evo1_LIBERO`（1.5G） |
| `libero_plus` / `Evo1` env | **in progress** | micromamba → `/mnt/sda/parc_libero_plus/mamba`（ルート逼迫回避） |
| Patch LIBERO-plus + assets | **pending** | env 後 |
| Thin / Language hard 実測 | **pending** | Stage1 FT（`q_…fce856bb`）完了後に GPU 空きで実行 |

GPU 競合: Stage1 expert-only FT が thor で running のため、Evo-1 推論は **完了待ち**。

---

## Reproduce（upstream harness · env 準備後）

```bash
# Terminal 1 — policy server
# （Evo1 env · checkpoint = /mnt/sda/parc_libero_plus/checkpoints/Evo1_LIBERO）
cd /mnt/sda/parc_libero_plus/third_party/Evo-1/Evo_1
python scripts/Evo1_server.py

# Terminal 2 — LIBERO-plus client（薄スライスは client 側 task 制限）
export LIBERO_CONFIG_PATH="$HOME/.libero-plus"
cd /mnt/sda/parc_libero_plus/third_party/Evo-1/libero-plus-eval
bash test_libero_plus.sh libero_spatial
```

### PARC 同尺

| 目的 | 寄せ方 |
|------|--------|
| Thin subset | `tasks_per_category=2`（n=14）相当に client task を制限 |
| Language hard | **984 / 986 / 988** ×10 |
| 監査 | action 24→7 crop · gripper 二値化 |
| 記録 | 下表 + `parent_ckpt_eligible=false` |

---

## PARC 実測

| Slice | Status | SR | n | Notes |
|-------|--------|---:|--:|-------|
| Thin (tpc=2) | **not run** | — | — | env + Stage1 完了後 |
| Language hard | **not run** | — | — | vs SmolVLA 0.10 / Molmo 1.000 |
| Thick (tpc=5) | **deferred** | — | — | thin 後 |

---

## 解釈（現状）

- 公表 Camera/Robot 弱さは Phase C/D と整合 → 外部ベースラインとして有用。
- 自前再測は env ブートストラップ待ち（conda 無し）。
- 親昇格・提出接続はしない。
