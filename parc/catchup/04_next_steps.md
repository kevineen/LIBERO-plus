# 04. 次にやること

キャッチアップのゴール（FT → ckpt 評価 → `parc-list`）を終えた人向けです。

## 1. 既存ドキュメントマップ

| 読みたいこと | 文書 |
|--------------|------|
| 全体像・ディスク注意 | [docs/00_overview.md](../docs/00_overview.md) |
| 環境・assets | [docs/01_setup.md](../docs/01_setup.md) |
| データセット | [docs/02_data.md](../docs/02_data.md) |
| 学習を長く回す | [docs/03_train.md](../docs/03_train.md) |
| 評価の絞り方 | [docs/04_eval.md](../docs/04_eval.md) |
| 実験管理 | [docs/05_experiments.md](../docs/05_experiments.md) |
| コンペ準備 | [docs/06_competition.md](../docs/06_competition.md) |
| 独自データ・改善アイデア | [docs/07_custom_data_and_algos.md](../docs/07_custom_data_and_algos.md) |
| Quest 3 VR デモ収集 | [docs/12_vr_teleop.md](../docs/12_vr_teleop.md) / [feature/vr-teleop/](../feature/vr-teleop/) |
| VR データ品質ロードマップ | [feature/vr-teleop/roadmap-data-quality.md](../feature/vr-teleop/roadmap-data-quality.md) |
| リモート Web / Jupyter | [docs/08_remote_and_ui.md](../docs/08_remote_and_ui.md) |
| 無人キュー・RL スモーク | [docs/09_autoloop_and_rl.md](../docs/09_autoloop_and_rl.md) |
| Web UI 操作 | [docs/10_ops_ui.md](../docs/10_ops_ui.md) |
| 複数 PC / Fleet | [docs/11_multi_machine.md](../docs/11_multi_machine.md) |

ベースライン結果は [`docs/baselines/`](../docs/baselines/)。

## 2. チームの「いま」を追う（strategy）

操作マニュアルとは別に、現状と判断ルールは `strategy/` にあります。

| ファイル | 内容 |
|----------|------|
| [strategy/README.md](../strategy/README.md) | 索引 |
| [strategy/01_current_status.md](../strategy/01_current_status.md) | 各マシンの状況スナップショット |
| [strategy/02_results_and_findings.md](../strategy/02_results_and_findings.md) | 結果と解釈 |
| [strategy/03_next_actions.md](../strategy/03_next_actions.md) | 優先バックログ |
| [strategy/04_machine_roles.md](../strategy/04_machine_roles.md) | マシン役割 |
| [strategy/05_decision_rules.md](../strategy/05_decision_rules.md) | 判断ルール（薄い eval だけで決めない等） |

エージェントと協働する場合は [AGENTS.md](../AGENTS.md) / [strategy/AGENT.md](../strategy/AGENT.md)。

## 3. おすすめの次アクション（人間メンバー）

優先度は `strategy/03_next_actions.md` が正ですが、キャッチアップ直後の定番は次です。

1. **smoke より長い FT** — YAML をコピーして `steps` を増やし、同じ eval プロトコルで比較する  
2. **カテゴリ別の弱点を見る** — subset / classification 付き評価で Camera / Robot 等を見る  
3. **改善仮説を 1 つだけ試す** — データ mix・学習レシピ・観測など（[docs/07](../docs/07_custom_data_and_algos.md)）  
4. （任意）**VR デモ** — Quest が使えるなら [docs/12](../docs/12_vr_teleop.md)。学習は必ず success-only（`parc-filter-demos`）  
5. （任意）**運用** — キュー / Web / Fleet は必要になったら docs/09–11

## 4. やってはいけないこと（短く）

- `.env.local` / webhook / 鍵を git やログに出さない  
- 薄い評価だけで親 checkpoint・長い FT・RL の是非を決めない（[strategy/05](../strategy/05_decision_rules.md)）  
- 他人のマシンに長いジョブを確認なしで積まない  
- 公式提出 zip を推測で捏造しない（テンプレ配布待ち）

## 5. 困ったとき

1. まず該当の `docs/0x_*.md`  
2. `strategy/01`–`03` でチーム現状を確認  
3. チャットで「どの Step / どのコマンド / エラー全文」を共有  

キャッチアップ入口に戻る: [README.md](README.md)
