# Catchup ドキュメント設計

**日付:** 2026-07-30  
**場所:** `LIBERO-plus/parc/catchup/`  
**承認済み方針:** アプローチ B（段階別マルチファイル）

## 目的

新規参入メンバー・ロボティクス初心者が、概念理解から **SmolVLA FT → ckpt 評価 → `parc-list`** まで自力で到達できるようにする。

## 対象読者

- ロボティクス初心者（VLA / LIBERO / 模倣学習の基礎から必要）
- PARC2026 / LIBERO-plus 実験ワークスペース（`parc/`）の作業者

## 非目標

- Fleet / キュー運用の完全マスター（`04_next_steps.md` で任意案内のみ）
- 公式提出 zip 形式の確定手順（ルール未公開のため）
- `.env.local` / webhook / 鍵などの機密情報の記載
- 既存 `docs/` のコマンド詳細の全面複製

## 構成

| ファイル | 責任 |
|----------|------|
| `catchup/README.md` | 入口・ロードマップ・完了チェックリスト・章リンク |
| `catchup/01_concepts.md` | 用語・概念（模倣学習・VLA・LIBERO / plus・PARC） |
| `catchup/02_study_urls.md` | 勉強用 URL（優先度 Must / Should / Optional） |
| `catchup/03_first_run.md` | setup → smoke → ランダム評価 → FT → ckpt 評価 → list |
| `catchup/04_next_steps.md` | `docs/` / `strategy/` への案内、運用の次の一歩 |

## 内容方針

1. **日本語**で書く。コマンドはコピペ可能な形にする。
2. 手順の詳細は既存 docs へリンクする（`docs/01_setup.md` 等）。catchup は「なぜ・何の順・最短パス」に集中する。
3. ゴール到達の最短コマンド列は `parc/README.md` Quickstart と整合させる。
4. スクリプト使い分けを明示する:
   - ランダム評価: `./scripts/parc.sh`（親 LIBERO-plus `.venv`）
   - 学習・ckpt 評価: `train.sh` / `eval_ckpt.sh`（親 robot venv + CUDA）
5. `parc/README.md` のドキュメント一覧に catchup への一行を追加する。

## 学習 URL（`02_study_urls.md` に載せる候補）

### Must（先に読む）

- PARC 公式: https://weblab.t.u-tokyo.ac.jp/physical-ai-competition/
- LIBERO-plus Paper: https://arxiv.org/pdf/2510.13626
- LIBERO-plus Website: https://sylvestf.github.io/LIBERO-plus
- LIBERO 原論文 / リポジトリ: https://github.com/Lifelong-Robot-Learning/LIBERO
- Hugging Face LeRobot: https://huggingface.co/docs/lerobot

### Should

- OpenVLA: https://github.com/openvla/openvla
- SmolVLA / LeRobot 学習ドキュメント（HF LeRobot docs 内）
- LIBERO-plus assets / datasets（Sylvest HF）
- 説明会資料 Drive（`docs/06_competition.md` 記載の URL）

### Optional

- π₀ (openpi): https://github.com/Physical-Intelligence/openpi
- MuJoCo 入門: https://mujoco.org/
- 模倣学習サーベイ / Behavior Cloning 基礎資料

## 成功条件

- 初心者が README のチェックリストを上から辿れる
- `03_first_run.md` を完了すると `parc-list` で自 run が見える
- 既存 docs と矛盾しない（パス・スクリプト名・venv 使い分けが一致）

## 変更ファイル一覧

- 新規: `catchup/README.md`, `01_concepts.md`, `02_study_urls.md`, `03_first_run.md`, `04_next_steps.md`
- 更新: `parc/README.md`（ドキュメント一覧に catchup を追加）
