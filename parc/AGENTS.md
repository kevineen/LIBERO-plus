# AGENTS

このディレクトリ（`parc`）で動く AI エージェント向けエントリポイント。

**手順書の正本:** [strategy/AGENT.md](strategy/AGENT.md)

| 読むもの | 用途 |
|----------|------|
| [strategy/AGENT.md](strategy/AGENT.md) | セッション開始・禁止事項・playbook 索引 |
| [strategy/playbooks/](strategy/playbooks/) | 状況確認 / 投入 / DONE 後 / docs 更新 |
| [strategy/01](strategy/01_current_status.md)–[05](strategy/05_decision_rules.md) | 現状・結果・バックログ・判断ルール |
| [strategy/04_machine_roles.md](strategy/04_machine_roles.md) | **ホスト割り振り**（重いジョブ=thor 既定） |
| [docs/](docs/) | セットアップ・API·Fleet 詳細 |
| [catchup/](catchup/) | 人間の新規メンバー向け（エージェントは通常不要） |

**ホスト既定（2026-07-31〜）:** 長時間 GPU / MuJoCo EGL 再レンダ / 厚い・深掘り → **thor**。短 FT → winpc（承認後）。winpc・nuc（WSL）で長時間 EGL 再レンダしない。

Cursor rule: `.cursor/rules/parc-agent.mdc`（alwaysApply）
