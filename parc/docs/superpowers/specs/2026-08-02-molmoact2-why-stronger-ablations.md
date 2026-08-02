# MolmoAct2 優位の仮説切り分け（2026-08-02）

## Why

厚い / Language hard で MolmoAct2 ≫ SmolVLA continue10k。  
「LIBERO を学習したから」以外の要因を安い Ablation で切り分ける。

## Hypotheses

| ID | Claim |
|----|--------|
| H1 | 言語・意味理解（Molmo2-ER 背骨 / 事前学習）が差の主因 |
| H2 | 視覚・視点ロバスト（優先低・厚い Camera 既に 1.0） |
| H3 | LIBERO-FT なしでも背骨だけで強い／弱いは未検証 |
| H4 | flow-matching `num_steps` が支配的か |
| H5 | SmolVLA は語彙 OOD だけ弱い → 言語ラベル置換 FT（第2段） |

## Experiments（thor · 親判定外）

共通: `task_ids=[984,986,988]` · `n_trials=5` · `max_steps=280` · seed=0。

| Exp | Config | Probe |
|-----|--------|-------|
| E1 | `molmoact2_hf_ablate_e1_nonsense_task.yaml` | `task_override` で無関係指示 |
| E2 | `molmoact2_hf_ablate_e2_normalize_off.yaml` | `normalize_language=false` |
| E3 | `molmoact2_hf_ablate_e3_base_ckpt.yaml` | `allenai/MolmoAct2`（非 LIBERO FT） |
| E4 | `molmoact2_hf_ablate_e4_num_steps_1.yaml` | `num_steps=1` |

対照: Molmo hard SR=1.0（×10）· SmolVLA hard SR=0.10。

## Interpretation

- E1 SR≪1 → H1 支持 → H5 を次チケット
- E1 SR≈1 → 言語非必須 → 視覚系へ
- E3 SR≪1 + E1 言語必須 → 背骨言語力 + LIBERO 動作 FT の組み合わせ

### 実測（2026-08-02 · thor）

| Exp | SR | 判定 |
|-----|-----|------|
| E1 | **0.867** | ≈1 → **H1 非支持**（言語非必須） |
| E2 | **1.000** | 正規化非支配 |
| E3 | **FAIL** | base に `libero` 無し / `franka_molmoact` で state (8,)≠(7,) → **LIBERO 契約 FT 必須** |
| E4 | **1.000** | steps 非支配 |

**H5: 見送り**（E1 基準）。SmolVLA 語彙 OOD は別動機で残るが、Molmo 優位の主因説明としては視覚+LIBERO-FT 側が近い。

## Non-goals

親置換 · cam FT · G3 本格 FT · 厚い再走
