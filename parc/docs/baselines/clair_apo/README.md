# CLAIR / Flow-APO サイドカー（研究用・親判定外）

正本: [2026-08-02-clair-apo-sidecar-design.md](../../superpowers/specs/2026-08-02-clair-apo-sidecar-design.md)

SmolVLA 主線・親 ckpt には接続しない。

## Gate 記録

| Gate | 状態 | メモ |
|------|------|------|
| P1 pairs smoke（fake≥20） | **pass** | 20 pairs · mean action L2≈0.073 · schema ok |
| P2 QST+LoRA+ SFT smoke | YAML 済 · 実測待ち | `sidecar_smolvla_ft_clair_sft_smoke.yaml`（robot venv · dry_run 既定） |
| P3 Flow-APO smoke | **pass** | `sidecar_flow_apo_smoke` loss≈0.693 · finite · parent_ckpt_eligible=false |
| P4 merge + async 配線 | **pass**（merge smoke） | 同一 energy ckpt を α=0.5 でマージ成功 · async フラグ配線済 |

## クイックコマンド

```bash
cd parc
uv run parc-clair-pairs --fake --n-pairs 20 --output data/datasets/clair_libero_pairs_smoke
# Flow-APO / merge は torch が要るため親 robot venv
bash scripts/train.sh configs/experiments/sidecar_flow_apo_smoke.yaml
PYTHONPATH=src:.. ../../.venv/bin/python -m parc.train.merge_ckpts \
  --a <a.pt> --b <b.pt> --alpha 0.5 --output /tmp/clair_merge
```

## 結果（実測）

- 2026-08-02: P1/P3/P4 smoke pass。P2 は YAML のみ。thor 厚い比較は空き時（親非接続）。
