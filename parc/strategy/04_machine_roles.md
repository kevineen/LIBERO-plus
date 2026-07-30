# 04. マシン役割と運用メモ

## 役割分担（現方針）

| マシン | 役割 | 得意な使い方 |
|--------|------|----------------|
| **winpc** | 主実験（4090） | 学習延長・Camera 深掘り・方針決定用の厚い eval |
| **thor** | 再現・並列・大バッチ | 同レシピ再現、厚い eval の並列、空き時間の予約ジョブ |
| **nuc** | Gate3 再現・予備 | aligned 系の再確認。SSH が不安定なら無理に積まない |

キューは **マシンごと**。`parc-fleet enqueue --host <alias>` で予約できる（worker が空いたら FIFO）。

## 速度目安（2026-07 実測 · eval）

| マシン | 厚い eval（tpc=5 · ~35 ep） | メモ |
|--------|---------------------------:|------|
| **thor** | 約 **12–25 分** | 深掘り・厚いの主ホスト |
| **nuc** | 約 **50 分** | thor の roughly 2–4×遅い。再現・予備 |
| **winpc** | 厚いは可だが **FT 優先** | 4090。方針決定の厚いも可 |

方針変更ジョブ（新 FT / mix）は **結果を見てから**。空き埋めの軽い eval だけ先行可。

## ジョブ割り振り表（現在 · SmolVLA）

| 種別 | winpc | thor | nuc |
|------|-------|------|-----|
| 親 ckpt 上の **深い eval**（Camera/Sensor 等） | △ 方針用のみ | **◎ 主** | ○ クロス再現 |
| **厚い eval**（親決め） | ○ | **◎** | ○ Gate3 / クロス |
| **短い FT**（lr↓ · mix） | **◎** | △ 空き時のみ | × 原則しない |
| 長い FT / unfreeze 延長 | **◎**（承認後） | × | × |
| 失敗しやすいスモーク | △ | ○ | **◎**（主機を汚さない） |
| cam-only 単体 FT | × 打ち切り済 | × | × |

いま（2026-07-30）: continue+10k 完了。次は thor で厚い+Cam deep。nuc は TDR 復旧直後のため重いジョブは控える。

## 将来割り振り表（Pi0 / Gr00t · 配布後）

詳細手順は [03_next_actions.md](03_next_actions.md) の「将来・本選リスト」。ここではホストだけ固定する。

| 段階 | 内容 | ホスト | 並行 |
|------|------|--------|------|
| Gate1 | 1 タスクスモーク / I/O | **nuc**（または thor 1 台） | 逐次 |
| B0 | ゼロショット薄い→厚い | **Pi0 → thor** · **Gr00t → nuc** | **並行可** |
| B0 敗者 | 打ち切り | — | — |
| B1 | 軽い FT（5k–15k） | **winpc**（または本選 GPU） | 1 本ずつ |
| B1 eval | 薄い→厚い | **thor** に戻す | 勝者優先 |
| B2 | 弱点短 FT / mix | winpc train → thor deep | 結果後 |
| 提出梱包 | `pack_submission` | winpc | — |

縛り:

1. B1 を結果前に両モデルへ投げ得しない  
2. Pi0/Gr00t は同条件 YAML（seed / tpc / task_ids）  
3. Cosmo3-Nano は主線に載せない（合成データ副線のみ）  
4. B-spline Policy は **副指標（滑らかさ・時間）専用**。SR/Camera 主線やホスト割り振りの対象外（→ [03](03_next_actions.md)）

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
    auto_reboot: true                 # hub の gpu-check --auto-reboot 時のみ
    reboot_method: windows_shutdown   # WSL2 GPU 死 → Windows 再起動
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
自動再起動（任意）: hub で `PARC_GPU_AUTO_REBOOT=1` または CLI `--auto-reboot`（hosts の `auto_reboot: true` のみ）

## よく使うコマンド

```bash
# 状態
uv run parc-queue status
uv run parc-fleet hosts
uv run parc-fleet runs --limit 30
uv run parc-fleet gpu-check --no-notify   # nuc/thor GPU 死活
# uv run parc-fleet gpu-check             # 変化時に Discord（cron 推奨）
# uv run parc-fleet gpu-check --auto-reboot   # nuc 自動再起動（hub cron）
# uv run parc-fleet gpu-check --auto-reboot --dry-run-reboot --host nuc --no-notify

# 投入
uv run parc-fleet enqueue --host thor -c configs/experiments/....yaml --kind eval --notify
uv run parc-fleet enqueue --host winpc -c configs/experiments/....yaml --kind train_eval --notify

# ワーカー（各マシンで常駐）
uv run parc-worker --loop --poll-sec 30
```

詳細: [docs/11_multi_machine.md](../docs/11_multi_machine.md) · [docs/10_ops_ui.md](../docs/10_ops_ui.md)（GPU 監視・完了通知）
