# MolmoAct2 baselines

研究サイドカー。SmolVLA 親・提出には接続しない。

| Gate | Status | Notes |
|------|--------|-------|
| G0 HF infer | **PASS** | load≈852s · predict≈18s · peak≈11.0 GiB · actions `(1,10,7)` → `act (7,)` |
| G1 plus smoke | **PASS (thor)** | SR=**0.0** · n=1 · task0 Background · 50 steps（horizon 不足）· run `20260801T221744Z_thor_a925fc4d_molmoact2_hf_smoke_eval` |
| G2 thin subset | **PASS (thor)** | SR=**1.000** · n=14 · 全軸 1.0 · run `20260801T223700Z_thor_7a12ac0e_molmoact2_hf_subset_eval` |
| Language hard | **PASS (thor)** | SR=**1.000** · n=30 · vs SmolVLA 0.10 · `20260801T234708Z_thor_99f67642_…` |
| Thick (tpc=5) | **PASS (thor)** | SR=**1.000** · n=35 · vs SmolVLA 0.514 · `20260802T002529Z_thor_dde26442_…` |

表: [`libero_plus.md`](libero_plus.md) · 設計: [2026-08-02-molmoact2-spike-design.md](../../superpowers/specs/2026-08-02-molmoact2-spike-design.md)

## Ablations（データセット以外の仮説切り分け）

正本: [2026-08-02-molmoact2-why-stronger-ablations.md](../../superpowers/specs/2026-08-02-molmoact2-why-stronger-ablations.md)

| Exp | Status | Notes |
|-----|--------|-------|
| E1 nonsense task | **DONE** | SR=**0.867** · `20260802T014851Z_thor_65fa8627_…` · 言語非必須 |
| E2 normalize_language=false | **DONE** | SR=**1.000** · `20260802T015240Z_thor_bc82ee2f_…` |
| E3 base ckpt (no LIBERO FT) | **FAIL** | norm/state 非互換 · LIBERO 契約必須 |
| E4 num_steps=1 | **DONE** | SR=**1.000** · `20260802T022701Z_thor_0d806d84_…` |

H5 SmolVLA 言語 FT: **見送り**（E1≈1）。詳細は [`libero_plus.md`](libero_plus.md)。
## Dependency note

- robot venv: **LeRobot 0.5.1** — `molmoact2` policy **なし**
- Eval: HF `allenai/MolmoAct2-LIBERO` via `parc.policies.molmoact2`
- FT（将来）: LeRobot **main** + `uv sync --extra molmoact2` を別 venv
