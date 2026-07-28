# Playbook: ジョブ投入

## 投入前チェックリスト

- [ ] [03_next_actions.md](../03_next_actions.md) の優先と矛盾しない
- [ ] [05_decision_rules.md](../05_decision_rules.md) に抵触しない（薄い eval だけで長い FT / GRPO 禁止）
- [ ] 対象ホストのキューを確認（重い train が既に running なら原則積まない。eval 直列は可）
- [ ] ckpt path が **そのホスト上で実在**する（winpc パスを thor に書かない）
- [ ] YAML を対象ホストへ SCP 済み（fleet enqueue は remote のファイルを読む）
- [ ] ユーザーが投入を依頼・承認している（曖昧なら先に提案だけ）

## YAML 作成ルール

- `configs/experiments/<name>_<machine>.yaml`
- `name` / `tags` に machine を含める
- train は `extra_args` に `--policy.pretrained_path=...` を絶対パスで
- eval-only は `policy.type: checkpoint` + `path:`
- 厚い eval: `tasks_per_category: 5`、深掘り: `task_ids` + `num_trials_per_task`

参考: 既存の `smolvla_thick_eval_*_thor.yaml` / `*_winpc.yaml`

## 投入コマンド

### このマシン（winpc）ローカル

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
set -a && source .env.local && set +a

uv run parc-enqueue \
  -c configs/experiments/<file>.yaml \
  --kind eval \          # または train_eval / train
  --notes "<短い理由>" \
  --notify

# worker が無ければ
uv run parc-worker --loop --poll-sec 30
# または nohup で常駐（既存プロセスを Dual 起動しない）
```

### 他ホスト（推奨: fleet）

```bash
# 1) YAML を先に置く
scp configs/experiments/<file>.yaml \
  kevin@100.99.61.50:/home/kevin/Matsuo/robot/LIBERO-plus/parc/configs/experiments/

# 2) enqueue
uv run parc-fleet enqueue --host thor \
  -c configs/experiments/<file>.yaml \
  --kind eval \
  --notes "<短い理由>" \
  --notify
```

`--host winpc` は Hub から投げるとき。winpc 上ではローカル enqueue でよい。

## 投入後（必須）

```bash
# 対象ホストで
uv run parc-queue status --limit 5
# 20–40s 待って running に遷移するか確認
```

その後:

1. [01_current_status.md](../01_current_status.md) を更新
2. [03_next_actions.md](../03_next_actions.md) の該当項目を進行中に

## kind の目安

| kind | いつ |
|------|------|
| `eval` | 学習なし。厚い eval / camera deep |
| `train_eval` | FT のあと自動で薄い eval まで |
| `train` | 学習のみ（稀） |

## やってはいけない投入

- Gate-RL 未達での GRPO/GSPO
- 薄い SR だけで unfreeze +30k 再延長
- 他マシンの experiments パスをそのまま書いた YAML
- worker 停止中の「投げ得」放置（起動するかユーザーに伝える）
