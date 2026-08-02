# Evo-1 baselines（研究サイドカー）

調査メモ: [../../00_research/turbovla_evo1.md](../../00_research/turbovla_evo1.md)  
上流: [MINT-SJTU/Evo-1](https://github.com/MINT-SJTU/Evo-1)

SmolVLA 親・提出には接続しない（MolmoAct2 / QuantVLA と同契約）。

| Gate | Status | Notes |
|------|--------|-------|
| Pub table | **recorded** | avg **65.69%** · camera **44.86%** · robot **49.42%** |
| Clone + weights (winpc) | **done** | `/mnt/b/parc_sidecars/` |
| conda `Evo1` | **done** | flash-attn 未導入でもロード可 |
| Language hard thin | **done** | **SR=0.000**（984/986/988×1）· vs SmolVLA 0.10 / Molmo 1.0 |
| Camera thin / ×10 hard | **optional** | |
| Thick | **deferred** | |

表: [`libero_plus.md`](libero_plus.md)

## Dependency note

- Policy: winpc conda `Evo1` · WS `:9000`（thor aarch64 は非推奨）
- Client: `parc/scripts/evo1_parc_thin_client.py` + LIBERO-plus PYTHONPATH
- Weight: `MINT-SJTU/Evo1_LIBERO`
