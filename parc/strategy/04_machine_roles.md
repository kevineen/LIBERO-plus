# 04. マシン役割と運用メモ

## 役割分担（現方針）

| マシン | 役割 | 得意な使い方 |
|--------|------|----------------|
| **winpc** | 主実験（4090） | 学習延長・Camera 深掘り・方針決定用の厚い eval |
| **thor** | 再現・並列・大バッチ | 同レシピ再現、厚い eval の並列、空き時間の予約ジョブ |
| **nuc** | Gate3 再現・予備 | aligned 系の再確認。SSH が不安定なら無理に積まない |

キューは **マシンごと**。`parc-fleet enqueue --host <alias>` で予約できる（worker が空いたら FIFO）。

## Fleet 表示

Hub（多くは thor Web `:3030`）で Runs の **Fleet** を ON にすると `hosts.yaml` のホストを横断表示する。

### thor の `configs/hosts.yaml`（要点）

```yaml
hosts:
  winpc:
    ssh: winpc   # ~/.ssh/config の Host 名
    parc_dir: /home/kevin/Matsuo/robot/LIBERO-plus/parc
    web_port: 3030
    local_web_port: 3032
  nuc:
    ssh: kevin@100.82.118.86
    parc_dir: /home/kevin/Matsuo/LIBERO-plus/parc
    web_port: 3030
    local_web_port: 3031
```

### winpc SSH（重要）

- Tailscale 名: `llm` / IP: `100.107.132.76`
- `:22` = Windows OpenSSH（WSL ではない）
- `:2222` = Windows portproxy → WSL sshd（`172.19.x.x:22`）
- thor 側: `~/.ssh/config` の `Host winpc`（Port 2222）+ `IdentityFile ~/.ssh/id_ed25519_parc_winpc`
- winpc WSL: `~/.ssh/authorized_keys` に deploy 公開鍵

トンネル例:

```bash
ssh -N -L 3032:127.0.0.1:3030 winpc
# http://127.0.0.1:3032
```

## 環境変数（各マシン `.env.local`）

必須に近いもの: `PARC_MACHINE_ID` / `PARC_EXPERIMENTS_DIR` / `PARC_WEB_ALLOW_JOBS=1` / `PARC_WEB_LAUNCHER=queue`  
通知: `PARC_NOTIFY_WEBHOOK_URL`（ジョブ完了時 `PARC · <machine>`）  
GPU 監視（任意）: `PARC_GPU_WATCH_REMIND_HOURS`（同じ障害の再通知間隔。未設定=再通知なし）

## よく使うコマンド

```bash
# 状態
uv run parc-queue status
uv run parc-fleet hosts
uv run parc-fleet runs --limit 30
uv run parc-fleet gpu-check --no-notify   # nuc/thor GPU 死活
# uv run parc-fleet gpu-check             # 変化時に Discord（cron 推奨）

# 投入
uv run parc-fleet enqueue --host thor -c configs/experiments/....yaml --kind eval --notify
uv run parc-fleet enqueue --host winpc -c configs/experiments/....yaml --kind train_eval --notify

# ワーカー（各マシンで常駐）
uv run parc-worker --loop --poll-sec 30
```

詳細: [docs/11_multi_machine.md](../docs/11_multi_machine.md) · [docs/10_ops_ui.md](../docs/10_ops_ui.md)（GPU 監視・完了通知）
