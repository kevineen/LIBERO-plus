# Phase C — Camera 診断 + 空き埋め並行（2026-08-01）

## Why

Phase A（重み）・Phase B（cam 増量）はいずれも continue10k 親を下回った。

| 段階 | thick | Cam deep | 判定 |
|------|------:|---------:|------|
| continue10k（親） | **0.514** | **0.20** | 維持 |
| Phase A mix v2 | 0.400 | 0.10 | 敗北 |
| Phase B mix v3 | **0.143** | **0.00** | 敗北・打ち切り |

教訓: **親から cam 比率を大きくした短 FT は forgetting**（全体崩壊 + Camera 全敗）。  
量を足す同軸は禁止。次は診断で「足りない視点」を固定してから、超保守の少本数 mix（Phase A' / 旧案 A）を検討する。

## Goal

1. continue10k の Camera 失敗モードを表に固定する（学習しない）
2. train-safe views vs eval hard のギャップ表を残す
3. 次 FT（少本数 hard-view）の仕様草案を1枚にする（**投入は別承認**）
4. 並行で GPU 空きを親決めにならない eval で埋める

## Non-goals

- 今すぐの新 FT / mix v3 延長 / cam-only / GRPO
- nuc での Camera deep（BSOD 歴）
- 薄い eval だけで親更新

## Workstream C1 — 診断（必須）

### C1.1 既存レビューの再利用

既に [02_results_and_findings.md](../../../strategy/02_results_and_findings.md) にある所見を正本の出発点にする:

- mild (608/609): 誤ターゲット・把持ミス。部分成功あり
- hard (610–612): 視点 OOD → 空間取り違え。把持前に timeout

追加でやること:

| 手順 | 内容 | 成果物 |
|------|------|--------|
| 1 | continue10k Cam deep 最新（`…7bd32280…` SR0.16）を registry から転記（episodes prune 済） | 02 追記 **済** |
| 2 | hard 失敗モードは 2026-07-28 動画レビューを正本として再利用（再視聴は artifact 欠落で保留） | 02 に明記 **済** |
| 3 | Phase B Cam deep 0.00 は診断対象外と注記 | 02 **済** |

### C1.2 View ギャップ表

学習（`DEFAULT_VIEWS` in `scripts/rerender_camera_demos.py`）は **eval exact hard を意図的に除外**:

| 種別 | views (h_v 要約) | 用途 |
|------|------------------|------|
| train-safe（v1/v2） | h∈{5,8,10,12} × v∈{5,10,15}（scale=100）の **12 本**。`11_15`/`13_15`/`14_15` **なし** | 再レンダ学習 |
| eval hard | **11_15 · 13_15 · 14_15**（task 610–612） | 評価のみ |
| eval mild | endpoint 微回転系（608/609） | 評価 |

ギャップ仮説（検証対象）:

> 学習は hard exact を見ない → hard OOD は構造的に弱い。  
> 一方 Phase B は train-safe cam を増やしただけで親を壊した → **「hard を足せば直る」は未証明**。  
> 次 FT は hard 近傍を **ごく少量**だけ入れ、base 比率を高く保つ。

### C1.3 Phase B 失敗の固定文

> continue10k から mix v3（base180+cam120 ≈ 60/40）へ +5k · 1e-5 は、Camera 改善の前に **他カテゴリを含む政策全体を破壊**した（thick 0.143 / Cam 0.00）。  
> 原因候補は (1) cam 比率過大 (2) 短 FT での分布シフト (3) wrist 破損修復の影響は二次的（修復後も完走したが評価は惨敗）。  
> 対策は「もっと cam」ではなく **比率≤15% · ステップ≤2.5k · 親バー厳守**。

### C1.4 次 FT 草案（Phase A' · 投入は承認後）

| Item | Draft |
|------|--------|
| Parent | continue10k `…cbbf5c8b…/010000`（変更しない） |
| Cam | hard 近傍のみ（例: 10/12/15 帯 · **exact 11_15 はリーク議論あり → 近傍優先**） |
| Mix | base **≥240** + cam **≤40**（cam 比率 **≤15%**） |
| FT | +**≤2500** · lr **≤1e-5** · bs=8 · **thor** |
| Eval | thin ignore; thick + Cam deep |
| Parent bar | thick ≥ 0.514 **and** Cam deep ≥ 0.20；どちらか欠けたら即打ち切り |
| Forbidden | cam-only · nuc Cam deep · Phase B 同軸延長 |

※ exact eval view を学習に入れるかは **C1 完了後に別途承認**（評価リーク懸念）。

## Workstream C2 — 空き埋め（並行）

| OK | NG |
|----|-----|
| continue10k Sensor deep クロス（nuc/thor） | Camera deep on nuc |
| Language / Robot の軽いクロス（親決め禁止と明記） | 新 FT · mix 延長 |
| 薄い再現スモーク | 厚い+Cam を「親更新」目的で重複投下 |

空き埋め結果は 02 に記録し、**親 ckpt は動かさない**。

## Success

- [x] C1.1–C1.3 が strategy/02 と本仕様に反映（2026-08-01）
- [x] C1.4 草案がレビュー可能（本仕様内）
- [x] C2 が少なくとも1本完走（Language deep **0.20** · Sensor deep **0.24** · `q_…7bbbffb5`）
- [ ] ユーザーが A' 投入の可否を判断できる

## Out of scope until A' approval

実装・再レンダ・enqueue of Phase A' FT。
