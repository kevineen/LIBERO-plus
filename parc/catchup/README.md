# PARC / LIBERO-plus キャッチアップガイド

新規メンバー・ロボティクス初心者向けの入口です。  
**ゴール:** 概念を理解したうえで、ローカルで **SmolVLA ファインチューニング → checkpoint 評価 → `parc-list`** まで自力で回せるようになること。

作業ルートは常にこのディレクトリの親である **`parc/`** です。

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
```

## 学習ロードマップ

| 順番 | 章 | 目安時間 | やること |
|------|-----|----------|----------|
| 1 | [01_concepts.md](01_concepts.md) | 1–2 時間 | 用語と全体像を掴む |
| 2 | [02_study_urls.md](02_study_urls.md) | 半日〜 | Must URL を読む（論文は abstract + 図だけでも可） |
| 3 | [03_first_run.md](03_first_run.md) | 半日〜1 日 | setup → smoke → FT → eval → list |
| 4 | [04_next_steps.md](04_next_steps.md) | 必要時 | 既存 docs / strategy / 運用への橋渡し |

## 完了チェックリスト

- [ ] VLA・LIBERO-plus・PARC の用語が説明できる（01）
- [ ] Must の学習 URL を一通り開いた（02）
- [ ] `setup_env.sh` と `parc-smoke` が通る（03）
- [ ] ランダム評価で `experiments/<run_id>/` ができる（03）
- [ ] SmolVLA smoke FT（200 step）が終わる（03）
- [ ] ckpt 評価を回し、`uv run parc-list` で自 run が見える（03）

## ドキュメントの役割分担

| 場所 | 役割 |
|------|------|
| **この `catchup/`** | 初心者向けの「なぜ・何の順・最短パス」 |
| [`docs/`](../docs/) | セットアップ・学習・評価・Fleet・VR の操作マニュアル |
| [`feature/`](../feature/) | 機能単位の設計・計画・STATUS（例: [vr-teleop](../feature/vr-teleop/)） |
| [`strategy/`](../strategy/) | いま何が分かっていて次に何をするか（方針メモ） |
| [`README.md`](../README.md) | 最短 Quickstart |

## すぐ知りたいとき

- コンペ概要 → [docs/06_competition.md](../docs/06_competition.md)
- 用語・ワークフロー → [docs/00_overview.md](../docs/00_overview.md)
- 環境構築の詳細 → [docs/01_setup.md](../docs/01_setup.md)
