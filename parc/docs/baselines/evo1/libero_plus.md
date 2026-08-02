# Evo-1 — LIBERO-plus

最終更新: 2026-08-03  
親判定: **しない**（研究サイドカー）  
調査メモ: [`../../00_research/turbovla_evo1.md`](../../00_research/turbovla_evo1.md)

## 共通

| 項目 | 値 |
|------|-----|
| Upstream | [MINT-SJTU/Evo-1](https://github.com/MINT-SJTU/Evo-1) · `libero-plus-eval/` |
| Checkpoint | `MINT-SJTU/Evo1_LIBERO` |
| Policy host | **winpc**（x86 · conda `Evo1`）— thor は aarch64 のため非推奨 |
| Clone (winpc) | `/mnt/b/parc_sidecars/Evo-1` |
| Weights (winpc) | `/mnt/b/parc_sidecars/Evo1_LIBERO`（1.5G） |
| Thin client | `parc/scripts/evo1_parc_thin_client.py` |
| 親 SmolVLA | continue10k thick **0.514** · Cam deep **0.20** · Lang hard **0.10** |

---

## Upstream 公表（著者表 · 自前再測ではない）

| Suite | background | camera | language | layout | light | noise | robot | avg |
|-------|----------:|-------:|---------:|-------:|------:|------:|------:|----:|
| Spatial | 86.43 | **38.03** | 68.97 | 67.53 | 86.64 | 75.21 | 49.14 | 67.42 |
| Object | 91.13 | 60.35 | 78.81 | 71.46 | 88.22 | 76.07 | 49.50 | 73.65 |
| Goal | 83.63 | 50.74 | **38.29** | 52.47 | 89.61 | 66.49 | 48.41 | 61.38 |
| 10 | 80.97 | **30.31** | 68.41 | 59.94 | 67.88 | 63.92 | 50.64 | 60.30 |
| **Avg.** | **85.54** | **44.86** | **63.62** | **62.85** | **83.09** | **70.42** | **49.42** | **65.69** |

---

## PARC 実測（2026-08-03）

### Language hard thin（984 / 986 / 988 · ×1 · max_steps=280）

| Item | Value |
|------|-------|
| Policy | Evo-1 server `ws://127.0.0.1:9000` · ckpt `Evo1_LIBERO` |
| Client | `scripts/evo1_parc_thin_client.py` · LIBERO-plus PYTHONPATH |
| flash-attn | **未導入**（nvcc パス不一致 · `FlashAttention2 is not installed` でロード成功） |
| **SR** | **0.000**（0/3） |
| Log | `/mnt/b/parc_sidecars/evo1_lang_hard_thin.log` |
| Videos | `…/logs/parc_thin/spatial/parc_thin_language_h15_S0/…` |

| task | Evo-1 ×1 | SmolVLA hard ×10 | Molmo ×10 |
|------|---------:|-----------------:|----------:|
| 984 | 0/1 | 0/10 | 10/10 |
| 986 | 0/1 | 0/10 | 10/10 |
| 988 | 0/1 | 3/10 | 10/10 |

解釈: 語彙 OOD hard スライスは Evo-1 も **全滅（n=1）**。公表 language ~64% とは別難度。親決めには使わない。flash-attn 無し・horizon=15・max_steps=280 の制約あり。×10 再測は任意。

| Slice | Status | SR | Notes |
|-------|--------|---:|-------|
| Language hard thin | **done** | **0.000** | n=3 · 親判定外 |
| Camera thin (608–609) | **not run** | — | 任意 |
| Thick (tpc=5) | **deferred** | — | |

---

## Reproduce

```bash
# Terminal 1 — policy server（winpc）
conda activate Evo1
cd /mnt/b/parc_sidecars/Evo-1/Evo_1
# ckpt_dir は /mnt/b/parc_sidecars/Evo1_LIBERO に固定済み
python scripts/Evo1_server.py

# Terminal 2 — thin client
bash ~/.libero/switch_plus.sh
export MUJOCO_GL=egl
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
../../.venv/bin/python scripts/evo1_parc_thin_client.py \
  --task-ids 984 986 988 --num-episodes 1 --max-steps 280
```

---

## Setup 進捗

| Step | Status |
|------|--------|
| Clone + weights (winpc / thor) | **done** |
| conda `Evo1` + requirements | **done**（flash-attn は未） |
| Language hard thin 実測 | **done**（SR=0） |
| flash-attn / ×10 hard | **optional** |
