# MolmoAct2 接続スパイク（2026-08-02）

## Why

[MolmoAct2](https://allenai.org/blog/molmoact2)（[arXiv:2605.02881](https://arxiv.org/abs/2605.02881)）は古典 LIBERO で平均 ~97% の公式 FT ckpt を公開し、**相対 EE・front/wrist** 契約が parc と整合する。  
現行 robot venv の **LeRobot 0.5.1 には `policy.type=molmoact2` が無い**（docs は LeRobot **main** + `uv sync --extra molmoact2`）。  
研究比較のため、**HF `predict_action` アダプタ**で Gate1 まで通す。

## Goal

1. `policy.type=molmoact2` で `parc-eval` / `eval_ckpt.sh` が 1 タスク smoke まで通る
2. 古典 LIBERO 公式 ckpt（`allenai/MolmoAct2-LIBERO`）のゼロショット地板を LIBERO-**plus** 薄い subset で取る
3. LeRobot main への FT は **別 venv サイドカー**（parc `uv` / 親 SmolVLA venv に混ぜない）

## Non-goals

- SmolVLA 親の置き換え・提出 zip 接続
- parc `pyproject` への MolmoAct2 専用依存追加
- Pi0 / Gr00t 本選計画の変更
- MolmoAct2-Think（depth）— 本 ckpt は depth 無効
- 薄い eval だけで親採用

## Decisions（固定）

| Item | Decision |
|------|----------|
| Eval path | `parc.policies.molmoact2.MolmoAct2HFPolicy`（transformers + `trust_remote_code`） |
| Default ckpt | `allenai/MolmoAct2-LIBERO`（`norm_tag=libero`） |
| Dtype | **bfloat16**（4090 24GB）。公式報告は float32 だが VRAM ~26GB |
| LeRobot FT | 将来: 独立 clone + LeRobot main。いまの robot `.venv` は上げない |
| Host | 初回 DL・smoke は **空き GPU**（winpc 4090 可）。厚い / 深掘りは **thor** 既定 |
| HF cache | 大容量 DL は **Linux 側**（例: `HF_HUB_CACHE=$HOME/.cache/huggingface/hub`）。`/mnt/b` 等の Windows マウントは遅い・不完全 DL になりやすい |
| Priority | Language / VR / D1 より下。空き時のみ |

## Gates

| Gate | Criterion | Status |
|------|-----------|--------|
| G0 | HF sample 画像で `predict_action` が `(T,≥7)` を返す（env 不要） | **PASS** (winpc) |
| G1 | `molmoact2_hf_smoke_eval.yaml` が 1 タスク完走（SR 問わず） | **PASS** (thor · SR=0 · horizon不足) |
| G2 | 薄い plus subset（SmolVLA と同 task_ids）でカテゴリ表 | **PASS** (thor · SR=1.000 · n=14) |
| G3 | （任意）LeRobot main サイドカーで短 FT → 同尺比較 | 未着手 |

## Metrics to record

- Success rate（suite / category）
- Peak VRAM / step latency（warmup 後）
- `flip_images` true/false の掴み差（必要なら）

## Artifact paths

| Path | Content |
|------|---------|
| `src/parc/policies/molmoact2.py` | HF アダプタ |
| `configs/experiments/molmoact2_hf_smoke_eval.yaml` | Gate1 |
| `docs/baselines/molmoact2/` | 結果表 |
| `scripts/molmoact2_infer_smoke.py` | Gate0 |

## Runbook

```bash
cd ~/Matsuo/robot/LIBERO-plus/parc

# G0 — env なし推論
bash scripts/eval_ckpt.sh  # は使わず robot venv で:
#   source ../../.venv/bin/activate   # Matsuo/robot/.venv
export PYTHONPATH=src:..
python scripts/molmoact2_infer_smoke.py

# G1 — LIBERO-plus 1 タスク
bash scripts/eval_ckpt.sh configs/experiments/molmoact2_hf_smoke_eval.yaml
```

## Success（スパイク完了条件）

- [x] 依存調査: LeRobot 0.5.1 に molmoact2 **無し**（pi0/smolvla 等のみ）
- [x] `MolmoAct2HFPolicy` + `build_policy` 接続
- [x] smoke YAML + 本設計メモ
- [x] G0 実走 PASS（bf16 · peak≈11 GiB · action chunk `(1,10,7)`）
- [x] G1 実走 PASS on **thor**（完走 · SR=0.0 · task0 Background · max_steps=50）
- [x] G2 薄い plus カテゴリ表（SR=1.000 · n=14 · 親昇格しない）
- [ ] strategy 02 に 1 段落
