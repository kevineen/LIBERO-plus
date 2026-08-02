# TurboVLA / Evo-1 学習トラック

**ゴール:** 概念を理解したうえで、上流の **smoke（ckpt 推論 or thin eval）** まで通し、PARC に何を借り・何を借りないかを説明できること。

このトラックは **PARC 親（SmolVLA）の差し替え手順ではありません**。サイドカー理解用です。調査メモの正本は [`parc/docs/00_research/turbovla_evo1.md`](../parc/docs/00_research/turbovla_evo1.md)。

PARC 本線の入門は [`parc/catchup/`](../parc/catchup/) を先に（または並行して）使ってください。

## 全体ロードマップ

```text
Phase 0 前提 → 1 経路概念 → 2 TurboVLA → 3 Evo-1 → 4 Upstream smoke → 5 PARC 落とし込み
```

| 順番 | 章 | 目安 | やること | クイズ |
|------|-----|------|----------|--------|
| 0 | [00_prerequisites.md](00_prerequisites.md) | 1–2 時間 | VLA / LIBERO / LeRobot / catchup の前提を揃える | — |
| 1 | [01_vla_pathways.md](01_vla_pathways.md) | 1–2 時間 | V→L→A vs V+L→A、chunk、プロセス分離 | [quiz/q01](../quiz/q01_vla_pathways.md) |
| 2 | [02_turbovla.md](02_turbovla.md) | 2–3 時間 | TurboVLA の設計・データ衛生・評価プロトコル | [quiz/q02](../quiz/q02_turbovla.md) |
| 3 | [03_evo1.md](03_evo1.md) | 2–3 時間 | Evo-1 の二段階 FT・WS・LIBERO-plus | [quiz/q03](../quiz/q03_evo1.md) |
| 4 | [04_upstream_smoke.md](04_upstream_smoke.md) + [notebook](notebook/turbovla_evo1_smoke_checklist.ipynb) | 半日〜1 日 | **必須 smoke**（または GPU 無し時の手順ウォークスルー記録） | [quiz/q04](../quiz/q04_upstream_smoke.md) |
| 5 | [05_parc_transfer.md](05_parc_transfer.md) | 1–2 時間 | P0/P1 の借り方と「やらないこと」 | [quiz/q05](../quiz/q05_parc_transfer.md) |

目安合計: **2–4 日**（Phase 4 の GPU 待ちを含む）。

## 完了チェックリスト

- [ ] Phase 0: catchup 相当の用語（VLA・LIBERO-plus・LeRobot）を説明できる
- [ ] Phase 1: V→L→A / V+L→A、action chunk と open-loop steps、policy≠sim を説明できる（q01）
- [ ] Phase 2: no-noop・mixed stats・`chunk_size == num_open_loop_steps`・&lt;1GB 意図を説明できる（q02）
- [ ] Phase 3: Stage1/2 FT・pad-to-24D・plus 7 軸・WS server/client を説明できる（q03）
- [ ] Phase 4: smoke を実行した、または notebook に手順ウォークスルーを記録した（q04）
- [ ] Phase 5: PARC の P0/P1 と「親にしない理由」を研究メモと対応付けて説明できる（q05）

フル FT / thick eval は **発展（任意）**。必須完了条件に含めない。

## 既存資料との関係

| 場所 | 役割 |
|------|------|
| **この `study/`** | TurboVLA / Evo-1 専用トラック |
| [`remediation/`](remediation/) | つまずき用の易しい補足（本線は長くしない） |
| [`quiz/`](../quiz/) | gate クイズ・bank・rubric・progress |
| [`notebook/第N回*`](notebook/) | Physical AI 基礎講座（運動学など）。本トラックの任意前提 |
| [`notebook/turbovla_evo1_smoke_checklist.ipynb`](notebook/turbovla_evo1_smoke_checklist.ipynb) | Phase 4 smoke 記録（追跡対象） |
| [`parc/catchup/`](../parc/catchup/) | PARC 本線（SmolVLA FT → eval）の最短パス |
| [`parc/docs/00_research/turbovla_evo1.md`](../parc/docs/00_research/turbovla_evo1.md) | チーム向け調査メモ（借りる優先度） |
| [`parc/docs/baselines/evo1/`](../parc/docs/baselines/evo1/) | Evo-1 ベースライン記録枠 |

## 上流リポジトリ

- [H-EmbodVis/TurboVLA](https://github.com/H-EmbodVis/TurboVLA)
- [MINT-SJTU/Evo-1](https://github.com/MINT-SJTU/Evo-1)

## クイズの使い方

各章の末尾で対応 **gate** クイズを解く → 答えは [`quiz/answers/`](../quiz/answers/)（先に見ない）。  
点数は [`quiz/rubric.md`](../quiz/rubric.md) で判定し、弱点は補足・復習クイズへ。

| 役割 | 場所 |
|------|------|
| 本線章 | このディレクトリの `00`〜`05` |
| 易しい補足 | [`remediation/`](remediation/) |
| gate クイズ | [`quiz/q01`〜`q05`](../quiz/) |
| 復習 / 発展バンク | [`quiz/bank/`](../quiz/bank/) |
| 自己採点ログ | [`quiz/progress/TEMPLATE.md`](../quiz/progress/TEMPLATE.md) |

詳細: [`quiz/README.md`](../quiz/README.md)

次: [00_prerequisites.md](00_prerequisites.md)
