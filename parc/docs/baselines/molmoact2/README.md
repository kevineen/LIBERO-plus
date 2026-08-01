# MolmoAct2 baselines

研究サイドカー。SmolVLA 親・提出には接続しない。

| Gate | Status | Notes |
|------|--------|-------|
| G0 HF infer | **PASS** | load≈852s · predict≈18s · peak≈11.0 GiB · actions `(1,10,7)` → `act (7,)` |
| G1 plus smoke | pending | `bash scripts/eval_ckpt.sh configs/experiments/molmoact2_hf_smoke_eval.yaml` |
| G2 thin subset | pending | 同尺カテゴリ表 |

設計: [2026-08-02-molmoact2-spike-design.md](../../superpowers/specs/2026-08-02-molmoact2-spike-design.md)

## Dependency note

- robot venv: **LeRobot 0.5.1** — `molmoact2` policy **なし**
- Eval: HF `allenai/MolmoAct2-LIBERO` via `parc.policies.molmoact2`
- FT（将来）: LeRobot **main** + `uv sync --extra molmoact2` を別 venv
