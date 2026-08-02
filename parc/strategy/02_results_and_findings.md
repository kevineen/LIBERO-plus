# 02. 結果と知見

時点: **2026-08-03**

## サイドカー（2026-08-03 · 親判定外）

| 実験 | Host | SR | n | メモ |
|------|------|---:|--:|------|
| SmolVLA Stage1 expert-only FT（continue10k→5k）薄い Lang hard | thor | **0.000** | 3 | `20260802T210934Z_thor_72c5af3f_…` · 984/986/988×1 · ckpt `005000` |
| Evo-1 Language hard thin（upstream WS） | winpc | **0.000** | 3 | 同 ID×1 · flash-attn 無し · [baselines/evo1](../docs/baselines/evo1/) |
| Molmo Language hard（参照） | thor | **1.000** | 30 | ×10 · 既存 |

解釈: Stage1 短尺 + 薄い hard だけでは改善見えず。**Stage2 延長は別承認**（薄い 0 だけで決めない）。Evo-1 も同 hard スライスで全滅 → 語彙 OOD はモデル横断の難所（Molmo 例外）。

## 学習ライン（薄い eval = tpc=2, n=14）

| 段階 | winpc | thor | nuc | メモ |
|------|-------|------|-----|------|
| official_aligned @30k | ≈0.21 | 0.214 | **0.357** | Gate3: nuc でも SR>0。薄い数値はマシン間でばらつく |
| +30k expert-only continue | — | 0.286 | — | Camera 等は弱いまま |
| +30k vision unfreeze (lr 2e-5) | **0.571** | **0.571** | **0.571** | 薄い eval では最強に見える。nuc も一致 |
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

| ckpt | 薄い SR | **厚い SR (winpc)** | **厚い SR (thor)** | **厚い SR (nuc)** | 判定 |
|------|-------:|-------------------:|-------------------:|------------------:|------|
| official_aligned@30k | 0.357 (nuc) | — | — | **0.257** | Gate3 厚いで再現。薄い 0.357→厚い 0.257 |
| unfreeze@30k | 0.571 | **0.229** | **0.429** | — | 薄い過大評価。thor では winpc より持ち直し |
| continue unfreeze@30k (winpc) | 0.500 | **0.314** | — | — | winpc 旧親 |
| continue expert-only@30k (thor) | 0.286 | — | **0.286** | — | 厚い≈薄い。Camera 弱 |
| **+15k finetune (lr 1e-5, winpc)** | — | **0.371** | **0.343** (cross) | — | 自機厚いより thor でやや低下 |
| thor unfreeze@30k **クロス** | — | **0.400** | 0.429 (自機) | — | 旧親（mix10k 登場前） |
| **mix10k**（unfreeze→cam mix · winpc） | — | — | **0.514** | — | 厚い同点候補。Cam deep 0.12 |
| **mix continue+10k**（mix10k→+10k） | Cam smoke **0.000** · nuc thin **0.143** | — | **0.514** | **0.371** | **現行親**。Cam deep **0.20**。nuc 厚いは thor より低（マシン差）。薄い 0.143 は過少 |

### nuc continue10k 薄い cross（2026-07-31）

Job `q_20260730T183023…5b83f890` · run `20260731T025659Z_nuc_5c63c8f8_…` · **SR=0.143**（2/14）

| カテゴリ | SR |
|----------|---:|
| Light / Objects | 0.50 |
| Background / Camera / Language / RobotInit / Sensor | **0.00** |

解釈: thor 厚い 0.514 と乖離大。**薄いばらつき + nuc マシン差**として記録のみ。親は変更しない。

### nuc unfreeze@30k 薄い（2026-07-31 · requeue-stale）

Job `q_20260731T025640…aecfb546` · run `20260731T031851Z_nuc_c9d23a1d_…` · **SR=0.571**（8/14）

| カテゴリ | SR |
|----------|---:|
| Light / Objects | 1.00 |
| Background / Language / RobotInit / Sensor | 0.50 |
| Camera | **0.00** |

解釈: winpc/thor 薄い 0.571 と一致。再現 OK。厚い親決めには使わない（unfreeze 厚いは thor 0.429 / winpc 0.229）。

### nuc continue10k 厚い cross（2026-07-31）

Job `q_20260731T033606…7f3ca66a` · run `20260731T033639Z_nuc_6a67ca01_…` · **SR=0.371**（13/35）

| カテゴリ | SR |
|----------|---:|
| Light | 0.80 |
| Background / Language / Objects / Sensor | 0.40 |
| RobotInit | 0.20 |
| Camera | **0.00** |

vs thor 厚い **0.514**: nuc は低いが薄い 0.143 より大幅改善。Camera は厚いでも 0。**親は thor 厚い基準で維持**。

### continue10k 弱点深掘り（thor · 2026-07-31 空き埋め）

| カテゴリ | SR | n | メモ |
|----------|---:|--:|------|
| Sensor | **0.16** | 25 | 1374:0.60 · 1376:0.20 · 他 0。unfreeze 深掘り 0.20 と同程度 |
| Language | **0.32** | 25 | 985:0.80 · 987/988:0.40 · 984/986=0。unfreeze 0.20 より改善 |

run: Sensor `20260731T033613Z_thor_50f7c836_…` · Language `20260731T035331Z_thor_cf28b03a_…`  
解釈: Language は親より良い。Sensor は依然弱い。Gate-RL 未達は継続。

### 親 ckpt 再確定（クロス厚い · 2026-07-29）

| ckpt | 自機厚い | 他機厚い | 判定 |
|------|--------:|--------:|------|
| winpc +15k | 0.371 (winpc) | **0.343** (thor) | 維持候補だが cross で弱い |
| thor unfreeze@30k | 0.429 (thor) | **0.400** (winpc) | **現行親** — マシン差を差し引いても +15k 以上 |

カテゴリ（cross）:

| カテゴリ | +15k on thor | unfreeze on winpc |
|----------|-------------:|------------------:|
| Objects | 0.80 | 0.60 |
| Background | 0.60 | **0.80** |
| Light | 0.60 | 0.40 |
| Language | 0.20 | 0.20 |
| Robot Initial | 0.20 | **0.60** |
| Sensor | 0.00 | 0.20 |
| Camera | **0.00** | **0.00** |

→ 2026-07-29 時点の親は **thor unfreeze@30k**。2026-07-30 mix10k 厚い 0.514 で親候補更新。2026-07-31 **親 = continue10k**（厚い同点・Cam deep 改善）。

### mix10k（2026-07-30 · thor eval）

| 指標 | SR | run |
|------|---:|-----|
| 厚い tpc=5 | **0.514** | `20260730T044841Z_thor_db324def_…` |
| Camera deep 608–612×10 | **0.12** | `20260730T043236Z_thor_36e4bb0a_…` |

厚いカテゴリ（抜粋）: Objects/Background 0.80 · Camera **0.20** · Language/Light/Robot 0.40 · Sensor 0.60  
解釈: unfreeze 厚い 0.40 / Camera deep 0.08 を上回る。cam-only 禁止の mix 方針は有効。

### mix continue+10k（2026-07-30 train · 2026-07-31 親確定）

| 項目 | 値 |
|------|-----|
| job | `q_20260730T070854…a66dc81d` |
| run | `20260730T071018Z_winpc_cbbf5c8b_…` |
| pretrained | mix10k `…6133f628…/010000` |
| steps | +10k · lr 1e-5 · bs=8 |
| ckpt | `010000`（run 内） |
| 薄い smoke | Camera 608–612 ×1 · **SR=0.000**（無視） |
| 厚い (thor) | **0.514** · `20260730T090125Z_thor_2798bc08_…` |
| Cam deep (thor) | **0.20** · `20260730T091211Z_thor_ea7c443f_…` |

厚いカテゴリ (continue10k): Objects 0.80 · Bg/Lang/Light 0.60 · Robot/Sensor 0.40 · Camera 0.20  
vs mix10k: 厚い全体同点。Cam deep **0.20 > 0.12**。Lang/Light↑、Bg/Sensor↓。弱点 Camera が改善したので **親更新**（05）。

### lr↓ 短 FT +5k（2026-07-31 train · 薄いのみ）

| 項目 | 値 |
|------|-----|
| job | `q_20260730T184655…380a43e2` |
| run | `20260730T184742Z_winpc_c7e7c8f2_…` |
| pretrained | continue10k `…cbbf5c8b…/010000` |
| steps | +5k · lr **5e-6** · bs=8 · 同 mix |
| ckpt | `005000`（`last`） |
| 薄い smoke | tpc=2 · n=14 · **SR=0.500** |
| 厚い / Cam deep | 厚い **0.371** · Cam deep **0.14**（親未満） |

薄いカテゴリ: Background **1.00** · Lang/Light/Objects/Robot/Sensor **0.50** · Camera **0.00**  
解釈: continue 系の薄い Cam smoke 0.000 と同型。**親決めに使わない**。

| 指標 | SR | run |
|------|---:|-----|
| 厚い (thor) | **0.371** | `20260730T200910Z_thor_a4d14910_…` |
| Cam deep (thor) | **0.14** | `20260730T202113Z_thor_fded971f_…` |

厚いカテゴリ: Light 0.80 · Objects 0.60 · Bg/Lang 0.40 · Robot/Sensor 0.20 · Camera **0.00**  
Cam deep by task: 608:0.10 · 609:0.20 · 610:0.20 · 611:0.10 · 612:0.10  
vs continue10k: 厚い **0.371 < 0.514** · Cam **0.14 < 0.20** → **親維持・同レシピ延長打ち切り**（05）。

### mix v2 Phase A（2026-07-31 · base120+cam60）

| 項目 | 値 |
|------|-----|
| job | `q_20260730T220954…a908742f` |
| run | `20260730T221003Z_winpc_c9dc1b28_…` |
| pretrained | continue10k `…cbbf5c8b…/010000` |
| dataset | `libero_plus_cam_mix_v2`（base120+cam60 · 180 eps） |
| steps | +5k · lr **1e-5** · bs=8 |
| ckpt | `005000`（`last`） |
| 薄い smoke | tpc=2 · n=14 · **SR=0.571**（Cam/Lang 0 · 無視） |
| 厚い (thor) | **0.400** · `20260730T231841Z_thor_907a8bc1_…` |
| Cam deep (thor) | **0.10** · `20260730T233024Z_thor_5ba94471_…` |

厚いカテゴリ: Light 0.80 · Objects 0.60 · Bg/Lang/Robot 0.40 · Sensor 0.20 · Camera **0.00**  
Cam deep by task: 608:0.30 · 609:0 · 610:0 · 611:0.20 · 612:0  
vs continue10k: 厚い **0.400 < 0.514** · Cam **0.10 < 0.20** → **Phase A 敗北**。親維持。次は **Phase B（cam 増量）**。

### Phase B mix v3（base180+cam120 · continue10k→+5k · thor · 2026-08-01）

| 項目 | 値 |
|------|-----|
| FT | `q_…9a1b9179` · `20260731T104523Z_thor_3fa4d513_…` · ckpt `005000` |
| 薄い | **0.214**（親決め未使用） |
| 厚い | **0.143** · `20260731T170913Z_thor_3c7af49e_…` |
| Cam deep | **0.00** · `20260731T172239Z_thor_908a45cb_…`（608–612×10 全敗） |

厚いカテゴリ: Lang 0.40 · Bg/Light/Sensor 0.20 · Objects/Robot/Camera **0.00**  
vs continue10k: 厚い **0.143 < 0.514** · Cam **0.00 < 0.20** → **Phase B 敗北**。親維持・同軸打ち切り。

### カテゴリ別（厚い）

| カテゴリ | nuc aligned | winpc unfreeze | winpc continue | winpc +15k | thor unfreeze | thor continue(expert) |
|----------|------------:|---------------:|---------------:|-----------:|--------------:|----------------------:|
| Objects Layout | **0.60** | 0.40 | **1.00** | 0.80 | **1.00** | 0.80 |
| Background | 0.40 | **0.60** | 0.20 | **0.80** | **0.80** | 0.60 |
| Sensor Noise | **0.00** | 0.20 | **0.40** | **0.00** ↓ | 0.20 | **0.00** |
| Robot Initial | **0.00** | 0.00 | **0.20** | 0.20 | 0.20 | **0.00** |
| Light | **0.60** | 0.40 | 0.20 | **0.80** | **0.60** | 0.20 |
| Language | **0.00** | 0.00 | 0.20 | **0.00** ↓ | 0.20 | 0.20 |
| **Camera Viewpoints** | **0.20** | **0.00** | **0.00** | **0.00** | **0.00** | 0.20 |

メモ: **親 = thor unfreeze**（cross 確定）。Camera は厚いでほぼ 0。+15k の伸びは Background / Light 中心だが cross では unfreeze に負ける。nuc Gate3 厚い 0.257。

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

### 親 unfreeze Camera deep（thor · 2026-07-29）

Run: `20260729T093144Z_thor_fa549217_…` · 全体 **SR=0.08**（4/50）

| task | SR |
|-----:|---:|
| 608 | 0.20 |
| 609 | 0.10 |
| 610–611 | **0.00** |
| 612 | 0.10 |

continue@30k 深掘り（0.16 · mild 0.30–0.50）より弱い。親復帰は全体厚い根拠。Camera 軸は改善していない。

### 弱点深掘りバッチ（thor · 2026-07-30 完了）

| 対象 | SR | n | メモ |
|------|---:|--:|------|
| 親 unfreeze Camera full | **0.08** | 50 | 既出。hard≈0 |
| +15k mild 608/609 | **0.30** | 20 | 608:0.40 · 609:0.20 |
| 親 Sensor | **0.20** | 25 | 1378=0 · 他 0.20–0.40 |
| 親 Language | **0.20** | 25 | **二極**: 985:0.60 · 987:0.40 · 984/986/988=0 |
| 親 RobotInit | **0.16** | 25 | 全体弱い |
| continue expert Camera | **0.04** | 50 | 親より悪い |
| +15k Camera full | **0.12** | 50 | 3 ckpt 中 Camera 最良。hard ほぼ 0 |

Camera ckpt 比較（deep）: **+15k 0.12 > unfreeze 0.08 > continue 0.04**。  
ただし親決めは厚い全体（unfreeze cross 0.400 ≥ +15k 0.371）を維持。  
**Gate-RL 未達**（最悪カテゴリが深掘りでも ~0.08–0.20）。次軸は **Camera mix 再設計**（cam-only 禁止）。

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

## Phase C 診断（2026-08-01）

仕様: [2026-08-01-phase-c-cam-diagnosis-design.md](../docs/superpowers/specs/2026-08-01-phase-c-cam-diagnosis-design.md)

### View ギャップ

| 種別 | views | 用途 |
|------|-------|------|
| train-safe（DEFAULT_VIEWS） | h∈{5,8,10,12} × v∈{5,10,15}（× scale100）= **12 本** | 再レンダ学習（v1/v2） |
| eval hard | **11_15 · 13_15 · 14_15**（task 610–612） | 評価のみ（学習から意図的除外） |
| eval mild | endpoint 微回転系（608/609） | 評価 |

### continue10k Camera deep

| run | SR | メモ |
|-----|---:|------|
| `20260730T091211Z_thor_ea7c443f_…` | **0.20** | 親決めに使用した値 |
| `20260731T073622Z_thor_7bd32280_…` | **0.16** | 再測定。registry 上 n=50 · Camera のみ。episodes は prune 済で task 別再集計不可 |

失敗モード正本は既存レビュー（上記「動画レビュー所見」）を維持:

- mild: 誤ターゲット / 把持ミス（部分成功あり）
- hard: 視点 OOD → 空間取り違え · 把持前 timeout

Phase B の Cam deep **0.00** は壊れた政策の症状であり、親の失敗モード診断には混ぜない。

### Phase B 失敗の固定文

continue10k から mix v3（base180+cam120 ≈ 60/40）へ +5k · 1e-5 は、Camera 改善の前に **政策全体を破壊**した（thick **0.143** / Cam deep **0.00**）。  
主因候補は (1) cam 比率過大 (2) 短 FT での分布シフト。wrist AV1 修復は二次的（修復後完走でも評価は惨敗）。  
次は「もっと cam」ではなく **cam 比率≤15% · steps≤2.5k · 親バー厳守**（Phase A'）。

### Phase A' 結果（2026-08-01）

| 段階 | thick | Cam deep | 判定 |
|------|------:|---------:|------|
| continue10k（親） | **0.514** | **0.20** | 維持 |
| Phase A' mix v4（base240+hard-near20 · +2.5k） | **0.286** | **0.06** | **敗北** |

- FT: `q_…e5d15dcf` · `…b85fca8b…/002500` · 薄い 0.357（無視）
- thick: `q_…00af5666` · `20260731T203704Z_thor_b86845a9_…`
- Cam deep: `q_…1c66397a` · `20260731T204944Z_thor_553447d0_…`
- バー未達（thick 0.286 < 0.514 · Cam 0.06 < 0.20）→ **親維持 · cam 軸短 FT 打ち切り**

### continue10k Language（Phase D1 · 2026-08-01）

指示文（ベンチマーク）と深掘り:

| task | 指示要約 | thor | nuc |
|------|----------|-----:|----:|
| 984 | darkhued rounded container / flat dish / glazed ceramic | **0** | **0** |
| 985 | black bowl…plate…ramekin（丁寧） | **0.80** | 0.20 |
| 986 | darkcolored rounded container / flat dish for main courses | **0** | **0** |
| 987 | black bowl…plate…ramekin | 0.40 | 0.60 |
| 988 | 丁寧だが物体名は標準 | 0.40 | 0.20 |

**仮説:** 失敗は **言い換え語彙 OOD**（bowl/plate が別表現）。動作そのものより言語。

**hard deep（984/986/988×10 · video）:** SR=**0.10** · `20260731T212845Z_thor_ce07fdf3_…` / `q_…70c96dab`  
- 984: **0/10** · 986: **0/10** · 988: **3/10=0.30** → 語彙 OOD 仮説を補強。

**次（2026-08-02）:** MolmoAct2 Language hard 対照 + 厚い同尺を thor 順投入（親判定外）。ラベル置換少本数 FT は cam なし・別承認。

### 空き埋め（親決め禁止）

| 内容 | SR | run |
|------|---:|-----|
| nuc Language deep vs thor 0.32 | **0.20** | `20260731T172230Z_nuc_9bcfd033_…` |
| nuc Sensor deep vs thor 0.16 | **0.24** | `q_…7bbbffb5` · `20260731T180023Z_nuc_cb27a7ad_…`（n=25 · 親決め禁止） |

## 解釈（短く）

1. **親 = continue10k**（厚い 0.514 · Cam deep **0.20** / 再測定 **0.16**）。mix10k は厚い同点だが Cam 劣後。旧親 unfreeze cross 0.40。
2. Sensor / Language / RobotInit 深掘りも **0.16–0.32**。Language は nuc **0.20** < thor **0.32**。Sensor は nuc **0.24** > thor **0.16**（クロス分散・親決め禁止）。
3. **lr↓5k / mix v2 / Phase B / Phase A' いずれも敗北**。**cam 軸短 FT は Phase D で禁止**。親 = continue10k 凍結。次は非 cam。
4. Gate-RL 未達。GRPO しない。
5. nuc Gate3 aligned 厚い 0.257。continue10k 薄い 0.143 / 厚い **0.371**（thor 0.514 より低・親維持）。

## 主要 Run ID（参照用）

| 内容 | run_id |
|------|--------|
| winpc unfreeze@30k train | `20260727T034050Z_winpc_7cb13dbc_…` |
| winpc continue unfreeze@30k | `20260727T091901Z_winpc_ef97e24e_…` |
| winpc thick unfreeze | `20260727T225455Z_winpc_cb66c529_…` |
| winpc thick continue | `20260727T233503Z_winpc_c56ad1c7_…` |
| winpc camera deep | `20260728T001828Z_winpc_f59aeb6a_…` |
| winpc +15k finetune（厚い 0.371） | `20260728T010727Z_winpc_cb240365_…` |
| nuc Gate3 aligned@30k（薄い 0.357） | `20260728T032038Z_nuc_d9d066c5_…` |
| nuc thick aligned（stale） | `20260728T070752Z_nuc_83a39509_…` |
| nuc thick aligned@30k（**0.257**） | `20260729T014305Z_nuc_25ff3b50_…` |
| winpc camera rerender FT（train_failed） | `20260728T064628Z_winpc_b2a2e871_…` |
| winpc camera rerender FT（cam-only·0.000） | `20260728T082624Z_winpc_8cd84fbf_…` |
| thor unfreeze@30k（**現行親**） | `20260727T084158Z_thor_4e89a1ad_…` |
| thor continue@30k expert-only | `20260727T034002Z_thor_be2cc0ee_…` |
| thor thick unfreeze（0.429） | `20260728T020259Z_thor_076ae49b_…` |
| thor thick continue expert-only（0.286） | `20260728T021430Z_thor_e58b83e0_…` |
| thor aligned@30k | `20260726T203202Z_thor_9ff610fd_…` |
| cross: +15k on thor（**0.343**） | `20260729T023944Z_thor_e24b3a25_…` |
| cross: unfreeze on winpc（**0.400**） | `20260729T024022Z_winpc_1513e490_…` |
| thor camera deep unfreeze（**0.08**） | `20260729T093144Z_thor_fa549217_…` |
| thor +15k mild deep 608/609（**0.30**） | `20260729T174037Z_thor_abf2aca9_…` |
| thor sensor deep unfreeze（**0.20**） | `20260729T174628Z_thor_cf1181aa_…` |
| thor language deep unfreeze（**0.20**） | `20260729T180311Z_thor_9d6e4760_…` |
| thor robot deep unfreeze（**0.16**） | `20260729T181042Z_thor_4c3fec0a_…` |
| thor camera deep continue（**0.04**） | `20260729T181845Z_thor_53a9d293_…` |
| thor camera deep +15k full（**0.12**） | `20260729T183530Z_thor_ba843a64_…` |
| winpc mix10k train | `20260730T023701Z_winpc_6133f628_…` |
| thor thick mix10k（**0.514**） | `20260730T044841Z_thor_db324def_…` |
| thor camera deep mix10k（**0.12**） | `20260730T043236Z_thor_36e4bb0a_…` |
| winpc mix continue+10k train（Cam smoke 0.000） | `20260730T071018Z_winpc_cbbf5c8b_…` |
| thor thick continue10k（**0.514** · **現行親**） | `20260730T090125Z_thor_2798bc08_…` |
| thor camera deep continue10k（**0.20**） | `20260730T091211Z_thor_ea7c443f_…` |
| thor camera deep continue10k 再測定（**0.16**） | `20260731T073622Z_thor_7bd32280_…` |
| winpc lr↓5k train（薄い **0.500**） | `20260730T184742Z_winpc_c7e7c8f2_…` |
| thor thick lr↓5k（**0.371** · 親未満） | `20260730T200910Z_thor_a4d14910_…` |
| thor camera deep lr↓5k（**0.14**） | `20260730T202113Z_thor_fded971f_…` |
| winpc mix v2 train（薄い **0.571**） | `20260730T221003Z_winpc_c9dc1b28_…` |
| thor thick mix v2（**0.400** · Phase A 敗北） | `20260730T231841Z_thor_907a8bc1_…` |
| thor camera deep mix v2（**0.10**） | `20260730T233024Z_thor_5ba94471_…` |
| nuc thin continue10k cross（**0.143**） | `20260731T025659Z_nuc_5c63c8f8_…` |
| nuc thin unfreeze@30k（**0.571**） | `20260731T031851Z_nuc_c9d23a1d_…` |
| nuc thick continue10k（**0.371**） | `20260731T033639Z_nuc_6a67ca01_…` |
| thor sensor deep continue10k（**0.16**） | `20260731T033613Z_thor_50f7c836_…` |
| thor language deep continue10k（**0.32**） | `20260731T035331Z_thor_cf28b03a_…` |
| thor Phase B mix v3 FT（薄い **0.214** · 親決め未使用） | `20260731T104523Z_thor_3fa4d513_…` |
| thor thick mix v3（**0.143** · Phase B 敗北） | `20260731T170913Z_thor_3c7af49e_…` |
| thor camera deep mix v3（**0.00** · 608–612 全敗） | `20260731T172239Z_thor_908a45cb_…` |
| nuc language deep continue10k（**0.20**） | `20260731T172230Z_nuc_9bcfd033_…` |

## QuantVLA サイドカー再現（2026-08-01〜02 · winpc · 研究用・親判定外）

GR00T N1.5 + [QuantVLA](https://quantvla.github.io/) PTQ。正本: [design](../docs/superpowers/specs/2026-08-01-quantvla-repro-design.md) · 表: [libero_classic.md](../docs/baselines/quantvla/libero_classic.md) · [libero_plus.md](../docs/baselines/quantvla/libero_plus.md)。

- 古典 LIBERO（n=1/task）: FP16 Avg **0.875** · Quant **0.850**（Spatial/Object 同点 · Goal Quant↑ · Long Quant↓）。論文 GR00T 表（多 trial）の近傍だが薄いプロトコルのため順位主張はしない。
- LIBERO-plus 薄い（tpc=2 · n=14）: FP16 **0.857** · Quant **0.786**。両条件とも **Camera 0/2**。SmolVLA 主線・親 ckpt には接続しない。

## MolmoAct2 接続スパイク（2026-08-02 · 研究用・親判定外）

正本: [design](../docs/superpowers/specs/2026-08-02-molmoact2-spike-design.md) · 表: [libero_plus.md](../docs/baselines/molmoact2/libero_plus.md)。

- G0 (winpc): PASS · bf16 · peak≈11 GiB。
- G1 (thor): smoke SR=0.0（`max_steps=50` が短すぎ · 同 task は G2 で step 74 成功）。
- G2 (thor · tpc=2 · n=14): SR=**1.000** · run `20260801T223700Z_thor_7a12ac0e_…`。
- Language hard (984/986/988×10): SR=**1.000** · vs SmolVLA **0.10** · `20260801T234708Z_thor_99f67642_…`。
- Thick (tpc=5 · n=35): SR=**1.000** · vs SmolVLA continue10k **0.514** · `20260802T002529Z_thor_dde26442_…`（Camera/全軸 1.0）。
- Ablations（hard×5）: E1 nonsense **0.867** · E2 normalize_off **1.000** · E3 base **FAIL**（state 非互換）· E4 steps=1 **1.000** → **言語必須ではない / LIBERO 契約 FT は必須 / steps 非支配**。H5 言語 FT は見送り。表: [libero_plus.md](../docs/baselines/molmoact2/libero_plus.md)。
- **親 ckpt・提出・主線置換には使わない**（サイドカー）。

## CLAIR / Flow-APO サイドカー（2026-08-02 · 研究用・親判定外）

正本: [design](../docs/superpowers/specs/2026-08-02-clair-apo-sidecar-design.md) · 表: [clair_apo/README.md](../docs/baselines/clair_apo/README.md)。

- 選好ペア主源: **シミュ合成 near-miss**（人間修正は `source=human_revise` 補助のみ）。
- 実装: `parc-clair-pairs` / `train.backend=flow_apo` / AFLoRA / LoRA+ param groups / `parc-merge-ckpts` / `policy.async_inference`。
- Gate: P1 fake 20 pairs pass · P3 Flow-APO smoke pass（winpc · `…6fc79de7_sidecar_flow_apo_smoke`）· P4 merge smoke pass（robot venv）。P2 実 SFT は dry_run YAML のみ。**親 ckpt 選定・提出には使わない**。thor 厚い比較は未実施。

