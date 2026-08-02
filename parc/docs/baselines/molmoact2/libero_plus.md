# MolmoAct2 — LIBERO-plus

最終更新: 2026-08-02  
親判定: **しない**（研究サイドカー。主線 SmolVLA / 提出親とは別枠）  
正本設計: [`../../superpowers/specs/2026-08-02-molmoact2-spike-design.md`](../../superpowers/specs/2026-08-02-molmoact2-spike-design.md)

## 共通

| 項目 | 値 |
|------|-----|
| Host | thor |
| Policy | `MolmoAct2HFPolicy` (`policy.type=molmoact2`) |
| Checkpoint | `allenai/MolmoAct2-LIBERO` |
| dtype | bfloat16 · CUDA · seed 0 |

---

## 薄い subset（Gate2 · tpc=2 · n=14）

Config: `molmoact2_hf_subset_eval.yaml`

| Run | SR | mean_steps |
|-----|-----|------------|
| `20260801T223700Z_thor_7a12ac0e_molmoact2_hf_subset_eval` | **1.000** | 82.9 |

全軸 SR=1.0（各 n=2）。

---

## 厚い同尺（tpc=5 · n=35 · SmolVLA continue10k と同尺）

Config: `molmoact2_hf_thick_eval.yaml`

| Run | SR | mean_steps | vs continue10k thick |
|-----|-----|------------|----------------------|
| `20260802T002529Z_thor_dde26442_molmoact2_hf_thick_eval` | **1.000** | 86.9 | 親 SmolVLA **0.514** |

| Category | n | SR | mean_steps |
|----------|---|-----|------------|
| Background Textures | 5 | 1.0 | 80.8 |
| Robot Initial States | 5 | 1.0 | 113.4 |
| Camera Viewpoints | 5 | 1.0 | 78.6 |
| Light Conditions | 5 | 1.0 | 80.8 |
| Language Instructions | 5 | 1.0 | 87.2 |
| Objects Layout | 5 | 1.0 | 81.8 |
| Sensor Noise | 5 | 1.0 | 86.0 |

---

## Language hard deep（Phase D1 対照 · 984/986/988×10）

Config: `molmoact2_hf_language_hard_deep_eval.yaml`

| Run | SR | mean_steps | vs SmolVLA continue10k |
|-----|-----|------------|------------------------|
| `20260801T234708Z_thor_99f67642_molmoact2_hf_language_hard_deep_eval` | **1.000** | 91.6 | SmolVLA hard **0.10** |

| task | Molmo | SmolVLA hard |
|------|------:|-------------:|
| 984 | **10/10** | 0/10 |
| 986 | **10/10** | 0/10 |
| 988 | **10/10** | 3/10 |

→ 語彙 OOD は SmolVLA 側の弱点（Molmo は同指示で全滅せず）。

---

## Gate0 / Gate1（参考）

| Gate | Host | 結果 |
|------|------|------|
| G0 infer smoke | winpc | PASS · peak≈11 GiB |
| G1 smoke | thor · max_steps=50 | SR=0.0（horizon 不足） |

## 解釈（短く）

- 薄い・厚い・Language hard いずれも **SR=1.0**（n_trials=1 または hard×10）。
- Camera / Language hard で SmolVLA 親を大きく上回るが、**親昇格・提出接続はしない**（サイドカー契約）。
- ラベル置換 FT・G3 短 FT は別承認。

## 非目標

- 主線 `smolvla` 置換 · parc `uv` に Molmo 依存追加 · 薄い/厚いだけで採用

---

## Ablations（データセット以外 · 2026-08-02）

正本: [`../../superpowers/specs/2026-08-02-molmoact2-why-stronger-ablations.md`](../../superpowers/specs/2026-08-02-molmoact2-why-stronger-ablations.md)

共通: 984/986/988 ×5 · max_steps=280 · seed=0 · 親判定外。  
対照: Molmo hard **1.000**（×10）· SmolVLA hard **0.10**。

| Exp | Run | SR | 解釈メモ |
|-----|-----|-----|----------|
| E1 nonsense task | `20260802T014851Z_thor_65fa8627_…` | **0.867** | 無関係指示でもほぼ成功（984:5/5 · 986/988:4/5）。**言語は必須でない** → H1 弱体 |
| E2 normalize_off | `20260802T015240Z_thor_bc82ee2f_…` | **1.000** | 正規化オフでも満点 → 前処理は主因ではない |
| E3 base ckpt | FAIL（2試行） | — | `libero` タグ無し → `franka_molmoact` で state **(8,) vs (7,)**。**LIBERO 契約なしでは動かない** → H3=背骨だけでは plus 不可 |
| E4 num_steps=1 | `20260802T022701Z_thor_0d806d84_…` | **1.000** | steps=1 でも満点 → H4 非支持 |

### 総合解釈

1. Molmo の hard/厚い成功は **視覚+状態+LIBERO-FT の動作契約** が主。指示文そのものは E1 でほぼ不要。
2. それでも SmolVLA は **正しい hard 指示で SR=0.10** → SmolVLA 側の語彙 OOD は別問題として残る。
3. **H5（SmolVLA 言語ラベル FT）は「Molmo が言語で勝っているから」ではなく「SmolVLA が言語で落ちるから」** の動機。E1 基準では優先低（視覚/容量差の方が Molmo 優位の説明として近い）。

H5: **今は着手しない**（E1≈1 → プラン解釈どおり言語必須仮説は非支持）。
