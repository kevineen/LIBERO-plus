# 00. 前提（Prerequisites）

## 目標

このトラックに入る前に、次を **自分の言葉で説明できる** こと。

- Vision-Language-Action（VLA）が何をするモデルか
- LIBERO / LIBERO-plus の違い（classic 4-suite vs 7 摂動）
- LeRobot データ形式が「学習の共通通貨」であること
- PARC ではいま **SmolVLA** が親であり、TurboVLA / Evo-1 はサイドカー理解であること

## 読むもの

| 優先 | リソース | 読み方 |
|------|----------|--------|
| Must | [parc/catchup/01_concepts.md](../parc/catchup/01_concepts.md) | 用語の全体像 |
| Must | [parc/catchup/02_study_urls.md](../parc/catchup/02_study_urls.md) の Must 行 | URL を開くだけで可 |
| Should | [LIBERO-plus 論文](https://arxiv.org/pdf/2510.13626) | abstract・図・7 摂動表 |
| Should | [LeRobot docs](https://huggingface.co/docs/lerobot) | Dataset / policy の入口 |
| Optional | [`notebook/第2回`〜`第4回`](notebook/) | FK/IK・シミュレーション感覚 |

PARC 本線をまだ触っていない場合は、この章のあと（または並行）に [catchup/03_first_run.md](../parc/catchup/03_first_run.md) を推奨。

## 要点

### VLA（一言）

観測画像（Vision）と指示文（Language）から、ロボットの連続アクション（Action）を出す模倣学習ベースの政策。

### LIBERO vs LIBERO-plus

| | LIBERO classic | LIBERO-plus |
|--|----------------|-------------|
| スイート | spatial / object / goal / 10 | 同じタスク骨格 + **7 種の摂動** |
| 本トラックでの位置 | TurboVLA 論文の主戦場 | Evo-1 公式 eval・PARC 本戦場 |

7 摂動の名前だけ覚える: background, camera, language, layout, light, noise, robot。

### データ形式の地図

```text
TurboVLA 学習:  TFDS / RLDS（*_no_noops）
Evo-1 学習:     LeRobot v2.1
PARC / VR:      LeRobot（VR は v3 方向）
```

「全部 RLDS に寄せる」は PARC ではやらない（調査メモの「借りない」参照）。

### 親とサイドカー

- **親**: 提出・主線の判断に使う政策（現状 SmolVLA continue 系）
- **サイドカー**: 評価・手法・データ衛生の参考。数字を取っても親判定ゲートとは別契約

詳細: [turbovla_evo1.md](../parc/docs/00_research/turbovla_evo1.md)

## 手を動かすメモ

この章に GPU 必須作業はない。次を確認するだけでよい。

```bash
# リポジトリルートから
ls study/ parc/catchup/ parc/docs/00_research/turbovla_evo1.md
```

## 完了条件

- [ ] VLA・LIBERO-plus・LeRobot・「親≠サイドカー」を口頭で説明できる
- [ ] catchup 01 を読んだ（または同等の知識がある）

## 次章

[01_vla_pathways.md](01_vla_pathways.md) — 経路の違いと推論時契約
