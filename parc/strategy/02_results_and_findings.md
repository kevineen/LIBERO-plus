# 02. 結果と知見

時点: **2026-07-28**

## 学習ライン（薄い eval = tpc=2, n=14）

| 段階 | winpc | thor | メモ |
|------|-------|------|------|
| official_aligned @30k | ≈0.21 | 0.214 | Gate2/3。width=0.5 + Instruct |
| +30k expert-only continue | — | 0.286 | Camera 等は弱いまま |
| +30k vision unfreeze (lr 2e-5) | **0.571** | **0.571** | 薄い eval では最強に見える |
| +30k unfreeze continue (lr 2e-5) | 0.500 | — | 薄い eval では低下 |

打ち切り:

- `from_official_*`（width 未整合）
- `continue_unfreeze50k`（SR≈0）

## 厚い eval（tpc=5, n=35）— 方針を変えた根拠

winpc のみ完了（thor は走行中）:

| ckpt | 薄い SR | **厚い SR** | 判定 |
|------|---------|-------------|------|
| unfreeze@30k | 0.571 | **0.229** | 薄い eval が過大評価 |
| continue unfreeze@30k | 0.500 | **0.314** | **親として採用** |

### カテゴリ別（厚い · winpc）

| カテゴリ | unfreeze@30k | continue@30k |
|----------|-------------:|-------------:|
| Objects Layout | 0.40 | **1.00** |
| Background | **0.60** | 0.20 |
| Sensor Noise | 0.20 | **0.40** |
| Robot Initial | 0.00 | **0.20** |
| Light | 0.40 | 0.20 |
| Language | 0.00 | 0.20 |
| **Camera Viewpoints** | **0.00** | **0.00** |

共通の最大弱点: **Camera Viewpoints**。

## Camera 深掘り（continue@30k · trials=10）

Run: `20260728T001828Z_winpc_f59aeb6a_…` · 全体 **SR=0.16**（8/50）

| task_id | SR |
|--------:|---:|
| 608 | 0.30 |
| 609 | 0.50 |
| 610 | 0.00 |
| 611 | 0.00 |
| 612 | 0.00 |

「Camera=0」は一枚岩ではなく、**610–612 が特に壊滅**。動画は同 run の `videos/`。

## 解釈（短く）

1. **親 ckpt は continue@30k（厚い 0.31）**。薄い 0.57 の unfreeze を親にしない。
2. unfreeze からの同 lr 延長は、厚い評価では優位にならなかった。
3. Gate2（SR>0）は満たすが、**実効 SR≈0.3・Camera 弱**の段階で GRPO は早い。
4. 次の学習は **lr↓ の短い微調整**か、Camera/Sensor 向けデータ・aug。学習前に厚い eval で確認する。

## 主要 Run ID（参照用）

| 内容 | run_id |
|------|--------|
| winpc unfreeze@30k train | `20260727T034050Z_winpc_7cb13dbc_…` |
| winpc continue unfreeze@30k | `20260727T091901Z_winpc_ef97e24e_…` |
| winpc thick unfreeze | `20260727T225455Z_winpc_cb66c529_…` |
| winpc thick continue | `20260727T233503Z_winpc_c56ad1c7_…` |
| winpc camera deep | `20260728T001828Z_winpc_f59aeb6a_…` |
| winpc +15k finetune（走行中） | `20260728T010727Z_winpc_cb240365_…` |
| thor unfreeze@30k | `20260727T084158Z_thor_4e89a1ad_…` |
| thor continue@30k expert-only | `20260727T034002Z_thor_be2cc0ee_…` |
| thor aligned@30k | `20260726T203202Z_thor_9ff610fd_…` |
