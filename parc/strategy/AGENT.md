# AGENT playbook — PARC 実験オペ

このファイルは **Cursor / コーディングエージェント向け**の手順書です。  
人間向けの方針メモは同ディレクトリの `01`〜`05`。オペ詳細は `docs/`。

## セッション開始時（必須）

1. 作業ルート: `LIBERO-plus/parc`
2. 先に読む（この順）:
   - [01_current_status.md](01_current_status.md) — いま何が走っているか
   - [03_next_actions.md](03_next_actions.md) — 次にやるべきこと
   - [05_decision_rules.md](05_decision_rules.md) — やってよい / だめ
3. 状況が古そうなら [playbooks/check_status.md](playbooks/check_status.md) で実機確認し、`01` を更新する
4. ジョブ投入・方針変更の前にユーザー確認（明示依頼がなければ勝手に長い train / GRPO を積まない）

## ドキュメント役割

| 場所 | 誰向け | エージェントの扱い |
|------|--------|-------------------|
| `strategy/01`–`05` | 方針・現状 | **更新対象**。事実が変わったら必ず直す |
| `strategy/AGENT.md` + `playbooks/` | エージェント | 手順の正本。コマンドはここからコピー |
| `docs/*.md` | セットアップ・API | 参照。手順変更時のみ触る |
| `catchup/` | 人間の新規メンバー | 参照のみ。オンボーディング案内時に指す |
| `configs/experiments/*.yaml` | 実験定義 | 新規ジョブはここ。ckpt path は絶対パス明示 |
| `.env.local` / `configs/hosts.yaml` | マシン固有 | **git に載せない**。中身の秘密をチャットに貼らない |

## 絶対に守ること

- Python 実行は `uv run …`（`uv run python …` は使わない）
- ジョブ投入は原則キュー経由（`parc-enqueue` / `parc-fleet enqueue`）。ワーカーが無いと消化されない
- **薄い eval だけで長い FT / RL を決めない**（→ `05`）
- **重いジョブ（長時間 GPU / MuJoCo EGL 再レンダ / 厚い・深掘り連続 / 短 FT 含む）の既定ホストは thor**（→ `04_machine_roles.md`）
  - winpc・nuc（WSL）で長時間 EGL 再レンダを起動しない（2026-07-31 BSOD: `dxgmms2` + `vmmem`）
  - 短 FT も原則 **thor**（ユーザー方針 2026-07-31）。winpc は承認後の例外のみ
- 旧 `from_official_*`（width 未整合）や SR0 の `continue_unfreeze50k` 延長を再利用しない
- Resume より **pretrained_path を書いた新規 YAML**
- Discord の実行マシンは表示名 `PARC · <machine>` と本文 `machine=` を見る（Hub 名と混同しない）
- GPU 死活は hub で `uv run parc-fleet gpu-check`（変化時のみ Discord）
- nuc 等の自動再起動は `gpu-check --auto-reboot`（hosts で `auto_reboot: true` + 連続 2 回 `gpu_dead`）。詳細は `docs/10_ops_ui.md`
- winpc への SSH は **Port 2222**（`:22` は Windows OpenSSH）。ホスト割り振りは `04_machine_roles.md`

## 典型タスク → playbook

| 依頼の例 | playbook |
|----------|----------|
| 状況は？ / キュー空？ | [playbooks/check_status.md](playbooks/check_status.md) |
| GPU 死んだ？ / Discord 監視 | `uv run parc-fleet gpu-check`（→ `docs/10_ops_ui.md`） |
| 自動再起動を試す / dry-run | `parc-fleet gpu-check --auto-reboot --dry-run-reboot` |
| ジョブを投げて | [playbooks/enqueue_job.md](playbooks/enqueue_job.md) |
| DONE 通知が来た | [playbooks/after_job_done.md](playbooks/after_job_done.md) |
| strategy を更新して | [playbooks/update_strategy_docs.md](playbooks/update_strategy_docs.md) |
| thor / winpc / nuc に何を？ | `03` + `04` + `05`。重いものは **thor 既定**。投入は確認後 |

## 完了報告の型

ユーザーへの返答は短く:

1. 何をしたか（job_id / config / host）
2. いまの状態（running / queued / SR）
3. strategy のどのファイルを更新したか
4. 次の一手が自動で続くなら一言（なければ「完了待ち」）
