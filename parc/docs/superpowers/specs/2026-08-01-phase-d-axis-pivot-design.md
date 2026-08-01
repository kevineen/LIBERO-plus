# Phase D — cam 軸打ち切り + 軸転換（2026-08-01）

## Why

continue10k 親に対する **cam 再レンダ短 FT は全敗**:

| 実験 | thick | Cam deep |
|------|------:|---------:|
| continue10k（親） | **0.514** | **0.20** |
| lr↓5k | 0.371 | 0.14 |
| mix v2 | 0.400 | 0.10 |
| Phase B（cam 多） | 0.143 | 0.00 |
| Phase A'（cam≤15% hard-near） | **0.286** | **0.06** |

教訓: 比率・近傍を絞っても、continue10k からの cam mix 短 FT は **全体を忘れる**。同軸延長は禁止。

ユーザー選択（2026-08-01）: **方針1 — 軸転換**。

## Goal

1. 親 = continue10k を **凍結**（厚い 0.514 · Cam deep 0.20）
2. **cam 軸の学習投入を禁止**（再レンダ mix FT / cam-only / exact hard リーク実験も含む）
3. 次の改善軸を非 cam に限定し、1 本ずつ承認ゲートで進める
4. GPU 空きは親決めにならない eval / インフラ準備のみ

## Non-goals

- Phase A'/B 延長 · mix v3/v4 再 FT
- exact eval hard（11/13/14_15）を学習に入れる最終 cam 実験
- GRPO / Gate-RL（未達のまま）
- nuc での Camera deep（BSOD 歴）
- 薄い eval だけで親更新

## Decisions（固定）

| Item | Decision |
|------|----------|
| Parent | continue10k `…cbbf5c8b…/010000` — **変更しない**（新 FT がバーを超えない限り） |
| Camera | 現状天井として記録。Cam deep は親の参照値のみ維持 |
| cam FT | **禁止**（strategy/05 に明記） |
| Host | 重いジョブ = thor |

## Workstreams（優先はユーザーが選ぶ）

### D1 — Language 軸（**進行中 · thor**）

- 既存: thor Lang deep **0.32**（二極）· nuc クロス 0.20
- 診断: 984/986 は語彙 OOD（darkhued/container 言い換え）で全滅。985/987 は black bowl 表現で生存
- running: Language hard deep `q_…70c96dab`
- 次: 失敗動画確認 → **言語ラベル置換** 少本数 FT 草案（cam なし · 承認後）
- 親バー: thick ≥ 0.514 **and** Lang deep ≥ 0.32（Cam 悪化も見たら打ち切り）

### D2 — Sensor 軸（候補）

- 既存: thor Sensor deep **0.16** · nuc 0.24
- 次: ノイズ種別の失敗固定 → データ/aug 草案（短 FT は診断後）
- 親バー: thick ≥ 0.514 **and** Sensor deep ≥ 0.16

### D3 — VR / データ収集（**進行中 · mainpc**）

- Quest 実機デモ → success-only smoke
- 手順: [STATUS.md](../../../feature/vr-teleop/STATUS.md) · [plan](../plans/2026-08-01-phase-d1-language-d3-vr.md)

### D4 — 待機・準備（候補）

- Pi0 / Gr00t 配布待ちの評価パイプライン確認
- ディスク整理（thor `/mnt/sda` ~99%）· 文書整備

## Forbidden（本フェーズ）

- continue10k からの `libero_cam_views_*` / mix v2–v4 系 FT
- cam-only · Phase B/A' 同軸
- 「色 jitter = Camera 対策」

## Success

- [ ] strategy `01`/`03`/`05` に cam FT 禁止と親凍結が反映
- [ ] ユーザーが D1–D4 のどれを最初に走らせるか決定
- [ ] 選んだ軸の診断 or 準備が1ステップ完了（FT は別承認）

## Out of scope until sub-track approval

具体 YAML・enqueue・新データ生成。
