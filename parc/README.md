# PARC / LIBERO-plus 実験ワークスペース

PARC2026（評価環境 = LIBERO / LIBERO-Plus）向けに、**ルール発表前でも**  
ローカルで「セットアップ → 学習レシピ → 評価 → 実験管理」を回せるプロジェクトです。

公式ルール・提出フォーマットが届いたら、`docs/06_competition.md` と `parc.policies` を差し替える想定です。

## 最短 Quickstart

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
bash scripts/setup_env.sh
bash scripts/fix_assets.sh

uv run parc-smoke --skip-env
uv run parc-list

# 評価（親 LIBERO-plus .venv）
./scripts/parc.sh eval -c configs/experiments/smoke_random.yaml
./scripts/parc.sh eval -c configs/experiments/subset_eval.yaml

# SmolVLA 実学習（親 Matsuo/robot venv + CUDA）
bash scripts/train.sh configs/experiments/smolvla_ft_smoke.yaml

# 公開 + cam 再レンダの物理 mix（MultiDataset 無効のため事前マージ）
# bash scripts/mix_datasets.sh --base-root <libero_plus_snapshot> --dry-run
# bash scripts/train.sh configs/experiments/smolvla_ft_libero_cam_mix_from_unfreeze_winpc.yaml

# 学習済み checkpoint 評価（同じく robot venv）
bash scripts/eval_ckpt.sh configs/experiments/smolvla_ckpt_smoke_eval.yaml

# 実験管理 Web / Jupyter（別 PC から閲覧）
bash scripts/start_web.sh
# bash scripts/start_jupyter_remote.sh
# 手順: docs/08_remote_and_ui.md

# 複数 PC Fleet（hosts.yaml 必須）
# uv run parc-fleet hosts
# uv run parc-fleet runs
# uv run parc-fleet gpu-check              # hub→Discord GPU 死活
# uv run parc-fleet gpu-check --auto-reboot  # nuc 等 auto_reboot 機の自動再起動
# 手順: docs/11_multi_machine.md / docs/10_ops_ui.md
```

ベースライン結果:
- ランダム評価: [`docs/baselines/random_subset_eval.md`](docs/baselines/random_subset_eval.md)
- SmolVLA 200step: [`docs/baselines/smolvla_ft_smoke.md`](docs/baselines/smolvla_ft_smoke.md)
- SmolVLA ckpt 評価: [`docs/baselines/smolvla_ckpt_smoke_eval.md`](docs/baselines/smolvla_ckpt_smoke_eval.md)

> **重要:** ランダム評価は `./scripts/parc.sh`（親 `LIBERO-plus/.venv`）、学習・ckpt 評価は `train.sh` / `eval_ckpt.sh`。  
> `lerobot/libero_plus` 初回は十数 GB。親 venv へ parc を入れるときは `--no-deps`。
## ディレクトリ構成

```text
parc/
  docs/                 手順書
  configs/experiments/  実験 YAML
  src/parc/             実験管理・評価・学習ラッパ
  scripts/              セットアップ / web / jupyter
  web/                  Next.js 実験コンソール
  experiments/          ラン成果（gitignore）
  data/                 データ・チェックポイント
```

## ドキュメント一覧

| 文書 | 内容 |
|------|------|
| [catchup/](catchup/) | **新規メンバー向けキャッチアップ**（概念・初回実行・[モデル/データ対応度](catchup/05_adaptability.md)） |
| [docs/00_overview.md](docs/00_overview.md) | 全体像と用語 |
| [docs/01_setup.md](docs/01_setup.md) | 環境構築・assets・libero パス |
| [docs/02_data.md](docs/02_data.md) | 学習データ |
| [docs/03_train.md](docs/03_train.md) | ファインチューニング |
| [docs/04_eval.md](docs/04_eval.md) | ローカル評価 |
| [docs/05_experiments.md](docs/05_experiments.md) | 実験管理 |
| [docs/06_competition.md](docs/06_competition.md) | PARC2026 準備チェックリスト |
| [docs/07_custom_data_and_algos.md](docs/07_custom_data_and_algos.md) | 独自データ追加・学習改善 |
| [docs/08_remote_and_ui.md](docs/08_remote_and_ui.md) | リモート Web / Jupyter / プレビュー |
| [docs/09_autoloop_and_rl.md](docs/09_autoloop_and_rl.md) | 無人キュー・スイープ・prune・GRPO/GSPO |
| [docs/10_ops_ui.md](docs/10_ops_ui.md) | Web UI 操作・再開・進捗 |
| [docs/11_multi_machine.md](docs/11_multi_machine.md) | 複数 PC・Fleet 横断・GDrive |
| [docs/12_vr_teleop.md](docs/12_vr_teleop.md) | Quest 3 VR テレオプ・デモ収集 |
| [feature/vr-teleop/](feature/vr-teleop/) | VR 機能の設計・計画・STATUS |

## 無人実験ループ（一晩回す）

```bash
uv run parc-enqueue --sweep configs/sweeps/overnight_ft_smoke.yaml
uv run parc-worker --loop --poll-sec 30
uv run parc-prune --dry-run
uv run parc-list --sweep-id overnight_ft_smoke
```

詳細は [docs/09_autoloop_and_rl.md](docs/09_autoloop_and_rl.md)。

## いまできること / まだできないこと

| できる | まだ（ルール・配布待ち） |
|--------|--------------------------|
| LIBERO-plus でローカル評価ループ | 公式提出 zip 形式 |
| 摂動カテゴリ別成功率集計 | 重み付き最終スコアの再現 |
| 実験 run の作成・一覧・metrics 保存 | Pi0 / Gr00t 公式学習コード接続 |
| LeRobot SmolVLA FT + checkpoint 評価 | 本番 I/O 完全一致の保証 |
| キュー / スイープ / ディスク prune | ライブ 3D シミュ操作 UI |
| GRPO/GSPO スモーク（状態ガウス方策） | SmolVLA 本体 log-prob の本格 RL |
| Web 実験管理・リモート Jupyter |  |
| Fleet 横断（runs/queue・ホスト指定投入） | 自動ロードバランス（`--host auto`） |
| GPU 死活監視 + 許可機の自動再起動 | ハブ経由の remote artifact 配信 |
| データセット物理 mix（`parc-mix-datasets`） | MultiLeRobotDataset（現行 LeRobot 無効） |
| Google Drive ckpt sync（rclone） | |
| VR teleop サーバ + Unity 薄クライアント（Quest 3） | Quest 実機 E2E・ハンド/実機/3D ビュー（Phase 2） |
| VR 品質ゲート（success フィルタ・RTT・キュー・replay・Approx Time） | Unity 周期 ping・物理 OOD 摂動エンジン |
| `parc-filter-demos` / `parc-replay-demos` / `parc-verify-demos --coverage` | |

親ディレクトリの upstream README はベンチマーク本体用です。コンペ作業は **この `parc/` をルート** にしてください。
