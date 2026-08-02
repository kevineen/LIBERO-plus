# 01. VLA 経路と推論時契約

## 目標

次を区別して説明できること。

1. **V → L → A**（LLM 中心）と **V + L → A**（直接融合）
2. **action chunk** と **open-loop steps** の関係
3. **policy プロセス ≠ sim / robot プロセス**（WebSocket や別 Python）

対応クイズ: [quiz/q01_vla_pathways.md](../quiz/q01_vla_pathways.md)

## 読むもの

| 優先 | リソース |
|------|----------|
| Must | 本章 |
| Must | [TurboVLA README Abstract / Overview](https://github.com/H-EmbodVis/TurboVLA)（V+L→A の主張） |
| Should | [Evo-1 README](https://github.com/MINT-SJTU/Evo-1) の Evaluation（WS server / client） |
| Optional | OpenVLA / π₀ 系のブログや docs（V→L→A の典型） |

## 要点

### 経路の対比

```text
V → L → A   視覚を LLM 表現空間へ射影し、言語モデル経由で行動へ
V + L → A   視覚エンコーダと言語エンコーダを独立に持ち、軽量な相互作用のあと行動デコーダへ
```

| | V→L→A | V+L→A（TurboVLA の主張） |
|--|-------|-------------------------|
| 中心 | 大規模 LM | コンパクトな融合 + action head |
| コスト | 呼び出しごとに LM 計算が重い | 推論レイテンシ・VRAM を抑えやすい |
| 例 | OpenVLA 系、多くの LLM-VLA | TurboVLA |

Evo-1 は InternVL3-1B（軽量 VLM）+ action expert。LLM 巨大モデル中心ではないが、**VLM 表現を活かしつつ意味整合を保つ**設計（二段階 FT）がポイント。PARC 主線の SmolVLA も「軽量 VLM + action」族に近い。

### Action chunk と open-loop

- 政策はしばしば **未来 H ステップ分のアクション列（chunk）** を一度に出す
- 実行側は chunk を **再推論なしで連続適用**することがある（open-loop）
- TurboVLA LIBERO 評価では **`chunk_size == num_open_loop_steps`**（例: 12）が推奨プロトコル

不一致だと「学習時のホライズン」と「評価時の実行契約」がずれ、成功率が比較不能になる。

### プロセス分離

```text
[Policy server]  ←WebSocket / RPC→  [Sim or Robot client]
   GPU 重い推論                         MuJoCo / 実機 I/O
```

- Evo-1: 公式に `Evo1_server.py` ↔ client（MetaWorld / LIBERO / libero-plus-eval）
- TurboVLA RoboTwin: 別 Python 環境で policy と sim を分離可能
- PARC: thor で policy、winpc/nuc で MuJoCo、Fleet 連携と思想が近い

分離の利点: 依存スタック衝突を避ける、ホスト役割を分けられる、再現手順が明確。

## 手を動かすメモ

コードを動かさず、次を紙またはノートに書く。

1. 自分の言葉で V→L→A と V+L→A を各 2 文
2. 「chunk=8, open-loop=16」だと何がまずいかを 1 文
3. policy と sim を同一プロセスに詰めたときのリスクを 1 つ

## 完了条件

- [ ] 上記 3 点を説明できる
- [ ] [q01](../quiz/q01_vla_pathways.md) を解いた
- [ ] 点数を [rubric](../quiz/rubric.md) で判定し、必要なら下記へ

## つまずいたら

- 易しい補足: [remediation/01/](remediation/01/)
- 復習クイズ: [quiz/bank/01/easy.md](../quiz/bank/01/easy.md)
- 判定: [quiz/rubric.md](../quiz/rubric.md)
- ログ: [quiz/progress/TEMPLATE.md](../quiz/progress/TEMPLATE.md)

## 次章

[02_turbovla.md](02_turbovla.md)
