# TurboVLA / Evo-1 クイズ

自己採点用です。章を読んだあと **gate**（`qXX_*.md`）を解き、[`answers/`](answers/) で確認してください。  
点数帯に応じた次アクションは [`rubric.md`](rubric.md) が正本です。

## 対応表（gate）

| クイズ | 対象章 | 解答 | 補足 / 復習 |
|--------|--------|------|-------------|
| [q01_vla_pathways.md](q01_vla_pathways.md) | [study/01](../study/01_vla_pathways.md) | [a01](answers/a01_vla_pathways.md) | [remediation/01](../study/remediation/01/) · [bank/01](bank/01/) |
| [q02_turbovla.md](q02_turbovla.md) | [study/02](../study/02_turbovla.md) | [a02](answers/a02_turbovla.md) | [remediation/02](../study/remediation/02/) · [bank/02](bank/02/) |
| [q03_evo1.md](q03_evo1.md) | [study/03](../study/03_evo1.md) | [a03](answers/a03_evo1.md) | [remediation/03](../study/remediation/03/) · [bank/03](bank/03/) |
| [q04_upstream_smoke.md](q04_upstream_smoke.md) | [study/04](../study/04_upstream_smoke.md) | [a04](answers/a04_upstream_smoke.md) | [remediation/04](../study/remediation/04/) · [bank/04](bank/04/) |
| [q05_parc_transfer.md](q05_parc_transfer.md) | [study/05](../study/05_parc_transfer.md) | [a05](answers/a05_parc_transfer.md) | [remediation/05](../study/remediation/05/) · [bank/05](bank/05/) |

Phase 0（[00_prerequisites](../study/00_prerequisites.md)）に専用 gate はない。

## レイヤ

```text
gate (必須)  →  rubric で判定  →  remediation（易しい説明）  →  bank/easy（復習）
                              ↘  定着なら bank/hard（任意）
```

| レイヤ | パス | いつ使う |
|--------|------|----------|
| gate | `q01`〜`q05` | 各 Phase の本番チェック |
| remediation | [`study/remediation/`](../study/remediation/) | 用語が分からないとき |
| bank easy/hard | [`bank/`](bank/) | 誤答タグの再測・発展 |
| progress | [`progress/TEMPLATE.md`](progress/TEMPLATE.md) | スコアと wrong_tags の記録 |

## 採点（要約）

詳細は [`rubric.md`](rubric.md)。

| MC% | 判定 |
|-----|------|
| ≥ 85% + 短答OK | 定着 → 次 Phase |
| 70–84% | 合格・弱点 → remediation + bank easy |
| 40–69% | 要復習 |
| &lt; 40% | 前提へ戻る |

## 運用

1. 解答は **解いてから** 開く
2. スコアを [`progress/`](progress/) に残す（個人ファイルは gitignore）
3. 新しい補足・問題は **gate を肥大化させず** remediation / bank に追加（手順は rubric）
4. 完了したら [study/README.md](../study/README.md) のチェックリストを更新する

入口: [study/README.md](../study/README.md)
