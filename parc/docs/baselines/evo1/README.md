# Evo-1 baselines（研究サイドカー）

調査メモ: [../../00_research/turbovla_evo1.md](../../00_research/turbovla_evo1.md)  
上流: [MINT-SJTU/Evo-1](https://github.com/MINT-SJTU/Evo-1)

SmolVLA 親・提出には接続しない（MolmoAct2 / QuantVLA と同契約）。

| Gate | Status | Notes |
|------|--------|-------|
| Pub table（upstream LIBERO-plus） | **recorded** | avg **65.69%** · camera **44.86%** · robot **49.42%** |
| Clone on thor | **done** | `/mnt/sda/parc_libero_plus/third_party/Evo-1` |
| HF weights | **done / check** | `/mnt/sda/parc_libero_plus/checkpoints/Evo1_LIBERO` |
| Eval env（libero_plus / Evo1） | **blocked** | conda 無し · micromamba/venv 要 · ルート 99% |
| PARC thin subset（tpc=2） | **pending** | Stage1 FT 完了後に GPU 空きで |
| Language hard（984/986/988×10） | **pending** | Phase D1 対照 |
| Thick（tpc=5） | **deferred** | thin 後 |

表: [`libero_plus.md`](libero_plus.md)

## Dependency note

- Policy env: Evo-1 公式（InternVL3 · flash-attn）— **PARC robot venv とは別** · `/mnt/sda` に作る
- Sim/client: LIBERO-plus + WebSocket（`libero-plus-eval/`）
- Weight: `MINT-SJTU/Evo1_LIBERO`
- PARC 側に `policy.type=evo1` アダプタは **未実装**（当面 upstream harness）
