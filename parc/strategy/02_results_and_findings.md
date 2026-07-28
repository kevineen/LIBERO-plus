# 02. 結果と知見

時点: **2026-07-28**

## 学習ライン（薄い eval = tpc=2, n=14）

| 段階 | winpc | thor | nuc | メモ |
|------|-------|------|-----|------|
| official_aligned @30k | ≈0.21 | 0.214 | **0.357** | Gate3: nuc でも SR>0。薄い数値はマシン間でばらつく |
| +30k expert-only continue | — | 0.286 | — | Camera 等は弱いまま |
| +30k vision unfreeze (lr 2e-5) | **0.571** | **0.571** | — | 薄い eval では最強に見える |
| +30k unfreeze continue (lr 2e-5) | 0.500 | — | — | 薄い eval では低下 |

打ち切り:

- `from_official_*`（width 未整合）
- `continue_unfreeze50k`（SR≈0）

### nuc Gate3 カテゴリ（薄い · n=2/cat）

| カテゴリ | SR |
|----------|---:|
| Objects Layout | 1.00 |
| Background / Language / Light | 0.50 |
| Camera / Robot Initial / Sensor | **0.00** |

run: `20260728T032038Z_nuc_d9d066c5_…` · job `q_20260727T034627…`  
解釈: レシピ再現は OK。全体 0.357 は winpc/thor 0.21 より高いが **薄い評価のばらつき**として扱い、親決めには使わない。
## 厚い eval（tpc=5, n=35）— 方針を変えた根拠

| ckpt | 薄い SR | **厚い SR (winpc)** | **厚い SR (thor)** | 判定 |
|------|-------:|-------------------:|-------------------:|------|
| unfreeze@30k | 0.571 | **0.229** | **0.429** | 薄い過大評価。thor では winpc より持ち直し |
| continue unfreeze@30k (winpc) | 0.500 | **0.314** | — | winpc 旧親 |
| continue expert-only@30k (thor) | 0.286 | — | **0.286** | 厚い≈薄い。Camera 弱 |
| **+15k finetune (lr 1e-5, winpc)** | — | **0.371** | — | winpc 新親候補（弱点未改善） |

### カテゴリ別（厚い）

| カテゴリ | winpc unfreeze | winpc continue | winpc +15k | thor unfreeze | thor continue(expert) |
|----------|---------------:|---------------:|-----------:|--------------:|----------------------:|
| Objects Layout | 0.40 | **1.00** | 0.80 | **1.00** | 0.80 |
| Background | **0.60** | 0.20 | **0.80** | **0.80** | 0.60 |
| Sensor Noise | 0.20 | **0.40** | **0.00** ↓ | 0.20 | **0.00** |
| Robot Initial | 0.00 | **0.20** | 0.20 | 0.20 | **0.00** |
| Light | 0.40 | 0.20 | **0.80** | **0.60** | 0.20 |
| Language | 0.00 | 0.20 | **0.00** ↓ | 0.20 | 0.20 |
| **Camera Viewpoints** | **0.00** | **0.00** | **0.00** | **0.00** | 0.20 |

メモ: thor では **unfreeze 厚い 0.429 > continue(expert) 0.286**。winpc の continue(unfreeze) 0.314 とは別レシピなので直接逆転とは言えない。  
共通: **Camera は依然ほぼ 0**。+15k の伸びは Background / Light 中心。

## Camera 深掘り（continue@30k · trials=10）

Run: `20260728T001828Z_winpc_f59aeb6a_…` · 全体 **SR=0.16**（8/50）  
動画: `…/videos/task06{08–12}_trial*.mp4`

| task_id | view `(horizon, vertical, scale, ep_rot, ep_vert)` | SR | 帯 |
|--------:|:---|---:|:---|
| 608 | `(0, 0, 1.0, 2, 352)` | 0.30 | **mild**（endpoint 微回転） |
| 609 | `(0, 0, 1.0, 2, 354)` | 0.50 | **mild** |
| 610 | `(11, 15, 1.0, 0, 0)` | 0.00 | **hard**（horizon+vertical 大） |
| 611 | `(13, 15, 1.0, 0, 0)` | 0.00 | **hard** |
| 612 | `(14, 15, 1.0, 0, 0)` | 0.00 | **hard** |

全タスク同一言語: *pick black bowl between plate & ramekin → place on plate*。  
collision=0。失敗は衝突落ちではなく **280 step timeout / 誤到達**。

### 動画レビュー所見（2026-07-28）

| 帯 | 主な失敗モード | 典型フレーム |
|----|----------------|--------------|
| mild (608/609) | **誤ターゲット到達**（ボウルでなく皿へ接近）・把持直前ミス・タイムアウト。成功時は通常の pick→place が通る | `608_fail` 中盤は皿上、`608_ok` はボウル把持→皿載置 |
| hard (610–612) | **視点 OOD → 空間取り違え**。トップ寄りカメラで腕が徘徊、ラメキン/コンロ側へ誤接近、コンロ開閉などのシーン破壊。ボウル把持まで到達しない | `610/611/612` 全域で timeout |

言語無視ではない（同 instruction で mild は部分成功）。  
**主因は大きな horizon/vertical 視点ずれに対する視覚–行動の破綻**。endpoint 微回転だけなら SR 0.3–0.5 残る。

+15k 厚い Camera 5 eps も 608–612 すべて失敗（各 n=1・参考）。mild も悪化の兆し。

## cam-only 再レンダ FT（+15k 親 → 60 eps local cam data）

Run: `20260728T082624Z_winpc_8cd84fbf_…` · 薄い **SR=0.000**（Camera 5/5 fail）

- 設定: `smolvla_ft_camera_rerender_from15k_winpc`
- データ: `libero_cam_views_v1`（60 eps / 5628 frames）
- 1回目は dataset mix 指定不整合で train_failed、2回目 cam-only は **学習自体は完走したが eval 0**
- checkpoint は `005000` / `007500` / `010000` / `last` が残存

解釈:

- **cam-only 60 eps への短 FT は catastrophic forgetting 寄り**。公開 `libero_plus` を外すと Camera 以外も含めて政策が崩れた可能性が高い。
- 「sim 再レンダ」という方向自体は即否定しないが、**cam-only 短 FT** は現状の有望筋ではない。
- 次に同軸を触るなら、mix 方法を CLI 対応で作り直すか、データ量/重みを再設計する必要がある。

## 解釈（短く）

1. **全体 SR は +15k で 0.31→0.37**。親候補は更新してよいが、最悪カテゴリは未達。
2. Camera は「全部ゼロ」ではなく **hard 視点（≥10° horizon / 15° vertical）が壁**。ただし **cam-only rerender 60 eps** も薄い 0.000 で、単純な追加学習では越えられなかった。
3. 次軸は **視点 OOD 向けデータ / aug** のままだが、今度は **混合方法の再設計**が必要。
4. Gate-RL 未達。thor 厚い結果は揃ったが、**winpc 親は当面 +15k（0.371）維持**。nuc 厚いは stale のため未確定。

## 主要 Run ID（参照用）

| 内容 | run_id |
|------|--------|
| winpc unfreeze@30k train | `20260727T034050Z_winpc_7cb13dbc_…` |
| winpc continue unfreeze@30k | `20260727T091901Z_winpc_ef97e24e_…` |
| winpc thick unfreeze | `20260727T225455Z_winpc_cb66c529_…` |
| winpc thick continue | `20260727T233503Z_winpc_c56ad1c7_…` |
| winpc camera deep | `20260728T001828Z_winpc_f59aeb6a_…` |
| winpc +15k finetune（完了・厚い 0.371） | `20260728T010727Z_winpc_cb240365_…` |
| nuc Gate3 aligned@30k（薄い 0.357） | `20260728T032038Z_nuc_d9d066c5_…` |
| nuc thick aligned（stale / metrics 無し） | `20260728T070752Z_nuc_83a39509_…` |
| winpc camera rerender FT（train_failed: mix 指定不整合） | `20260728T064628Z_winpc_b2a2e871_…` |
| winpc camera rerender FT（cam-only・薄い 0.000） | `20260728T082624Z_winpc_8cd84fbf_…` |
| thor unfreeze@30k | `20260727T084158Z_thor_4e89a1ad_…` |
| thor continue@30k expert-only | `20260727T034002Z_thor_be2cc0ee_…` |
| thor thick unfreeze（0.429） | `20260728T020259Z_thor_076ae49b_…` |
| thor thick continue expert-only（0.286） | `20260728T021430Z_thor_e58b83e0_…` |
| thor aligned@30k | `20260726T203202Z_thor_9ff610fd_…` |
