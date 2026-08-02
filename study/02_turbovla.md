# 02. TurboVLA

上流: [H-EmbodVis/TurboVLA](https://github.com/H-EmbodVis/TurboVLA)  
論文の売り: **RTX 4090 で ~32 Hz・&lt;1 GB VRAM・0.2B・LIBERO classic 平均 97.7%**（著者公表）

対応クイズ: [quiz/q02_turbovla.md](../quiz/q02_turbovla.md)

## 目標

- V+L→A が何を省略しているか説明できる
- **no-noop データ**と **mixed-suite stats** の意味が分かる
- 評価で `chunk_size` / `num_open_loop_steps` / `stats_key` を揃える理由が言える
- PARC では **全体を親にしない**が、データ衛生アイデアは借りる、と説明できる

## 読むもの

| 優先 | リソース |
|------|----------|
| Must | [TurboVLA README](https://github.com/H-EmbodVis/TurboVLA)（Install / Dataset / Train / Eval） |
| Must | 本章 + [turbovla_evo1.md](../parc/docs/00_research/turbovla_evo1.md) の TurboVLA 行 |
| Should | HF [H-EmbodVis/TurboVLA](https://huggingface.co/H-EmbodVis/TurboVLA)（ckpt + 正規化メタ） |
| Optional | DINOv3 / GroundingDINO / BERT（視覚・相互作用・言語エンコーダ） |

## 要点

### アーキテクチャ（実装に効く粒度）

```text
画像 → DINOv3
言語 → BERT（オンライン；テキスト特徴キャッシュ不要）
両者 → 軽量な双方向 VL 相互作用（GroundingDINO 由来初期化）
     → 連続 action chunk デコーダ
```

LLM を毎ステップ回さないことが、レイテンシと VRAM 削減の主因。

### データ衛生（PARC が借りたい部分）

| 道具 | 役割 |
|------|------|
| `scripts/libero/regenerate_libero_no_noops.py` | デモから no-op（ほぼ静止）ステップを除去した RLDS を作る |
| `scripts/libero/compute_mixed_stats.py` | 4 suite 混ぜた正規化統計 |
| `experiments/libero/configs/libero_all4_stats.json` | 公開された mixed stats |
| `stats_key`（例: `libero_all4_no_noops`） | **どの統計で normalize したか**を明示 |

PARC への翻訳: VR デモの idle trim + **versioned `stats_key`**（roadmap M5）。classic RLDS への全置換はしない。

### LIBERO 評価プロトコル（落とし穴）

公式例の要点:

- suite 名: `libero_spatial` / `libero_object` / `libero_goal` / `libero_10`
- `--chunk_size 12 --num_open_loop_steps 12`（一致させる）
- `--stats_path` + `--stats_key` を学習時と揃える
- precision `bf16` など環境依存フラグあり

**LIBERO-plus は TurboVLA 公式の主戦場ではない。** plus 数字は Evo-1 / PARC 側で見る。

### 環境

- Python 3.10、LIBERO 用と RoboTwin 用は **別 conda/venv 推奨**
- 依存: PyTorch、`pip install -e ".[libero]"`、別途 LIBERO 本体

### 規模感（論文・README の目安）

| 項目 | LIBERO レシピ目安 |
|------|-------------------|
| パラメータ | ~0.2B |
| chunk | 12 |
| 最適化 step | 80k（4 GPU・global batch 256 など） |
| 推論 | ~31 ms / ~0.9 GB（4090・著者公表） |

フル学習は本トラックの **発展（任意）**。必須は Phase 4 の smoke。

## 手を動かすメモ

Phase 4 の準備として、次だけ確認する。

```text
□ README の Dataset ツリー（libero_*_no_noops）を眺めた
□ evaluate.py の必須引数をメモした
□ 「親にしない理由」（LeRobot 非対応・plus なし・スタック別）を 1 文で書いた
```

## 発展（任意・フル学習）

公式 README の `torchrun … experiments/libero/train.py` を参照。4 GPU・長時間。PARC キュー承認なしで流さない。

## 完了条件

- [ ] no-noop / mixed stats / chunk=open-loop を説明できる
- [ ] [q02](../quiz/q02_turbovla.md) を解いた
- [ ] 点数を [rubric](../quiz/rubric.md) で判定し、必要なら下記へ

## つまずいたら

- 易しい補足: [remediation/02/](remediation/02/)
- 復習クイズ: [quiz/bank/02/easy.md](../quiz/bank/02/easy.md)
- 判定: [quiz/rubric.md](../quiz/rubric.md)

## 次章

[03_evo1.md](03_evo1.md)
