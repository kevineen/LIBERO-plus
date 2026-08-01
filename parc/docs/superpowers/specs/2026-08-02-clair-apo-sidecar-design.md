# CLAIR / APO ロボティクス適用（研究サイドカー · 2026-08-02）

## Why

TACL 2025 の CLAIR（高コントラスト選好ペア）と APO（アンカー付き選好最適化）を、SmolVLA + LIBERO-plus の **pick 近傍失敗** に移植する。  
LLM の revision ペアの代わりに、**成功軌道への微小摂動で得た near-miss** を主源とする。

## Goal

1. シミュ合成 near-miss から `(preferred, rejected)` ペアデータセットを作る（`parc-clair-pairs`）
2. QST（4bit+adapter）+ LoRA+ の sidecar SFT レシピを用意する
3. `train.backend=flow_apo` で Flow-Matching 向け Anchored Preference を回す（AFLoRA 併用）
4. ckpt 線形マージ + 非同期推論の配線を用意する

## Non-goals

- SmolVLA **親 ckpt** の置き換え・提出 zip 接続
- Phase D（Language / VR）主線のブロッカー化
- Quest 人間 CLAIR を Phase1 必須にすること（補助のみ）
- Gate-RL 未達のまま GRPO 本格化
- token log-prob 待ち（SmolVLA は Flow-Matching のため **Flow-APO**）

## Decisions（固定）

| Item | Decision |
|------|----------|
| 位置づけ | 研究サイドカー（`tags: [sidecar, clair_apo]`） |
| ペア主源 | シミュ合成 near-miss（接触近傍失敗のみ採用） |
| 人間修正 | `source=human_revise` で任意追記のみ |
| コントラスト既定 | 物理指標（VLM/GPT-4V はオフライン任意） |
| QST | VLM 4bit + action expert bf16（QLoRA 級） |
| LoRA+ | A/B 非対称 LR（既定 LR_B = 4× LR_A） |
| APO | action-chunk Flow energy + π_ref アンカー |
| 正則化 | 短 steps・初期チャンク更新制約・スクイージング監視 |
| Host | 長ジョブ = thor / smoke = winpc 可 |

## Gates

| Gate | Criterion |
|------|-----------|
| P1 | spatial 系 smoke で ≥20 ペア、schema OK、action L2 帯内 |
| P2 | 200step SFT が OOM なく完走、薄い subset が親床以上 |
| P3 | Flow-APO loss 有限、SFT 比で非悪化 or pick 近傍改善 |
| P4 | merge 前後で薄い subset が壊れない |

## Artifact paths

| Path | Content |
|------|---------|
| `src/parc/data/clair_nearmiss.py` | near-miss 合成・pairs schema |
| `src/parc/train/flow_apo.py` | Flow-APO backend |
| `src/parc/train/aflora.py` | AFLoRA 動的凍結 |
| `src/parc/train/merge_ckpts.py` | 線形マージ CLI |
| `configs/experiments/sidecar_smolvla_*.yaml` | sidecar 学習/評価 |
| `docs/baselines/clair_apo/` | Gate 記録 |

## Runbook

```bash
cd ~/Matsuo/robot/LIBERO-plus/parc

# P1 — fake near-miss pairs
uv run parc-clair-pairs --fake --n-pairs 20 \
  --output data/datasets/clair_libero_pairs_smoke

# P2 — SFT smoke（robot venv + CUDA）
bash scripts/train.sh configs/experiments/sidecar_smolvla_ft_clair_sft_smoke.yaml

# P3 — Flow-APO smoke
bash scripts/train.sh configs/experiments/sidecar_flow_apo_smoke.yaml

# P4 — merge
uv run parc-merge-ckpts --a <ckpt_a> --b <ckpt_b> --alpha 0.5 --output <out>
```

## Success（実装完了条件）

- [x] 設計正本 + strategy 非接続宣言
- [x] `parc-clair-pairs` + 単体テスト
- [x] sidecar SFT / Flow-APO YAML + backend
- [x] AFLoRA + merge CLI + async 配線
- [x] P1/P3/P4 smoke（winpc）
- [ ] thor 実測の厚い比較（空き時・親判定外）
