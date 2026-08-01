# Phase D1 Language + D3 VR 並行プラン（2026-08-01）

> **For agentic workers:** D1 は thor、D3 は mainpc（winpc）。cam FT は禁止のまま。

**Goal:** Language 弱点を thor で診断→少本数 FT 草案まで進め、同時に mainpc で VR 実機 E2E のソフト確認と Quest 接続準備を進める。

**Architecture:** 二系統独立。D1 は既存 continue10k の Language deep 結果と LIBERO-plus 言い換え文を正本に診断し、**言語ラベル置換の少本数 mix**（cam なし）を草案化。D3 は `parc-vr-teleop` の fake → Quest 実機の順。

**Tech Stack:** SmolVLA / LIBERO-plus · parc-fleet(thor) · parc-vr-teleop · Unity OpenXR (Windows)

---

## D1 — Language（thor）

### 診断結果（固定）

| task | language_k | thor deep (メモ) | nuc deep | 指示の特徴 |
|------|------------|----------------:|---------:|------------|
| 984 | language_1 | **0** | **0/5** | `darkhued rounded container` / `flat dish` / `glazed ceramic dish` — 語彙が遠い |
| 985 | language_2 | **0.80** | 1/5 | `black bowl` / `plate` / `ramekin` を維持した丁寧依頼 |
| 986 | language_3 | **0** | **0/5** | `darkcolored rounded container` / `flat dish for main courses` — 984 同型 |
| 987 | language_4 | 0.40 | **3/5** | `black bowl`…`plate` を維持 |
| 988 | language_5 | 0.40 | 1/5 | 丁寧依頼だが物体名は標準 |

**仮説:** 失敗は動作スキル欠如より **言い換え語彙 OOD**（bowl/plate/ramekin が別表現に置換）。  
**やらない:** cam remender · exact cam hard。

### 次ステップ

- [x] 指示文をベンチマークから取得し 02 / 本プランに固定
- [ ] （任意）thor で Language hard deep（984/986/988×10）+ save_video — 失敗モード動画確認
- [ ] FT 草案（**承認後**）: base≥240 + **言語ラベル置換エピソード ≤40**（同一軌道・言い換え文のみ）· +≤2500 · 1e-5 · thor  
  - 親バー: thick≥0.514 **and** Lang deep≥0.32 · Cam が大きく落ちたら打ち切り
- [ ] FT enqueue はユーザー承認後

### Forbidden

cam mix / Phase A'·B 延長 / GRPO

---

## D3 — VR（mainpc / winpc）

### いまできること（ソフト）

- [ ] `bash scripts/vr_teleop.sh --fake --no-dataset` プロトコル確認
- [ ] `PARC_ROBOT_VENV=... bash scripts/vr_teleop.sh --fake-episode` で 1ep 書き込み
- [ ] `uv run parc-verify-demos --root data/datasets/vr_libero_demos`（fake 後）
- [ ] Windows 側: Unity プロジェクト作成チェックリストを STATUS に転記

### Quest 実機（ユーザー手作業）

手順正本: [docs/13_quest3_setup.md](../../13_quest3_setup.md)

- [ ] Windows Unity + Quest 3 で `ws://<winpc-LAN-IP>:8765` 接続（WSL 時は portproxy）
- [ ] 1 episode Save → verify → STATUS に記録
- [ ] （後）success-only → smoke FT（thor 可）

### Blocker

Quest / Windows Unity 未接続。セットアップ手順は 13 に文書化済み。
