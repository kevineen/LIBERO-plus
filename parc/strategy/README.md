# PARC Strategy（実験方針メモ）

操作マニュアル（`docs/`）とは別に、**いま何が分かっていて次に何をするか**を置く場所です。  
日付付きスナップショットと、判断ルールを短く保ちます。

## エージェント向け（手順書）

| ファイル | 内容 |
|----------|------|
| [AGENT.md](AGENT.md) | **エージェント用 playbook の正本**（開始時必読） |
| [playbooks/](playbooks/) | 状況確認 / 投入 / DONE 後 / strategy 更新 |
| [../AGENTS.md](../AGENTS.md) | `parc` ルートのエントリ |

Cursor: `.cursor/rules/parc-agent.mdc` が alwaysApply で上記を指す。

## 方針メモ（人間・エージェント共用）

| ファイル | 内容 |
|----------|------|
| [01_current_status.md](01_current_status.md) | 各マシンのキュー・走行中ジョブ（時点スナップショット） |
| [02_results_and_findings.md](02_results_and_findings.md) | 結果表・解釈・勝ち筋 / 負け筋 |
| [03_next_actions.md](03_next_actions.md) | 今後やるべきこと（優先順バックログ・将来/本選リスト） |
| [04_machine_roles.md](04_machine_roles.md) | winpc / thor / nuc の役割・速度目安・現在/将来の割り振り表 |
| [05_decision_rules.md](05_decision_rules.md) | Gate・eval 信頼度・RL 投入の判断ルール |

最終更新: **2026-07-30**（JST · mix10k 評価確定 · continue10k 投入）

関連オペ docs: [10_ops_ui.md](../docs/10_ops_ui.md) · [11_multi_machine.md](../docs/11_multi_machine.md) · [09_autoloop_and_rl.md](../docs/09_autoloop_and_rl.md)  
新規メンバー: [catchup/](../catchup/)
