# 10. UI 操作・運用マニュアル

PARC Lab Web（`:3030`）から実験・キュー・再開・ドキュメントを扱う手順です。

## 画面構成

| ページ | 用途 |
|--------|------|
| **Runs** `/` | 実験一覧・SR・Progress・**Hide paused**・**Delete failed / Delete paused** |
| **Jobs / Queue** `/#jobs` | 投入・取消・再投入・キュー削除・stale 回収・進捗 |
| **Docs** `/docs` | 本マニュアル群の閲覧 |
| Run 詳細 `/runs/<id>` | metrics・config・動画・**Resume** |

## 起動

```bash
cd parc
export PARC_WEB_ALLOW_JOBS=1
export PARC_WEB_LAUNCHER=queue
bash scripts/start_web.sh
# 別ターミナルでワーカー必須
uv run parc-worker --loop --poll-sec 30
```

SSH トンネル例: `ssh -L 3030:127.0.0.1:3030 user@host`

## キュー操作（UI）

1. **Launch** — 設定 YAML を選んで `train` / `eval` をキューへ（即実行ではない）
2. **Cancel** — `queued` のみ取消
3. **Pause** — `running` の学習/評価プロセスを止め GPU を解放。ジョブは `cancelled`、ckpt / run は残る
4. **Requeue** — `failed` / `cancelled` / `succeeded` を同じ設定で再投入
5. **Delete** — `failed` / `cancelled` / `done` をキューから削除（**run ディレクトリは残す**）。行の Delete または **Delete failed (local)**
6. **Resume** — 紐づく run の最新 ckpt から続き（Pause 後の再開はこれ）
7. **Recover stale** — 長時間 `running` のままのジョブを失敗扱いにし、中身を再キュー
8. **進捗** — `phase`（train / eval / done / paused）と紐づく `run_id`・SR をポーリング

CLI 同等:

```bash
uv run parc-queue status
uv run parc-queue cancel <job_id>   # running ならプロセス kill + cancelled（Pause）
uv run parc-queue requeue <job_id>
uv run parc-queue delete --failed   # 失敗ジョブをキューから削除
uv run parc-queue delete <job_id>
uv run parc-queue resume <run_id> --mode auto
uv run parc-queue recover-stale --max-age-sec 3600
```

Pause 後の再開例（mainpc / winpc）:

```bash
uv run parc-queue resume <run_id> --mode train   # 学習続き
# または UI の Resume
```

※ Pause を効かせるには `parc-worker` が新しいコードで動いていること（PID ファイルを書く版）。古いワーカーは再起動してください。

## 途中停止からの再開

| 状況 | やること |
|------|----------|
| ワーカーが落ちた・`running` のまま | UI の **Recover stale** または `parc-queue recover-stale` |
| GPU を空けたい（指定ジョブ） | Jobs の **Pause** または `parc-queue cancel <job_id>` → あとで **Resume** |
| train 済み・eval 未完了 | Run 詳細の **Resume (auto)** → eval ジョブ |
| GRPO/GSPO を ckpt から続けたい | **Resume (train)** → `init_policy_path` 付きで再学習 |
| 失敗ジョブを同じ設定で | **Requeue** |
| 失敗ジョブを一覧から消す | Jobs の **Delete** / **Delete failed**（run は残る） |
| 失敗・Pause 残骸の **run** を消す | Runs の **Delete failed** / **Delete paused** / 行の Delete |
| Pause 済み run を隠す | Runs の **Hide paused**（デフォルト ON） |

※ LeRobot のステップ完全 resume はバックエンド依存です。GRPO は `init_policy_path` で方策を引き継ぎます。

## スコアの見方

- Runs 表の **SR** = `metrics.json` の `success_rate`
- Runs / Jobs の **Progress** = 学習 step（`train 1234/50000`）とバー。Fleet モードでも queue 進捗を合流して表示
- 詳細の **by_category** = 摂動カテゴリ別
- Queue パネルの **Top scores** = 最近ジョブに紐づく SR 上位
- prune は `keep_best`（SR）を優先して残す

CLI:

```bash
uv run parc-queue status   # phase + progress (step/total %)
```

※ いま動いているジョブはワーカー再起動なしで進捗を追うため、初回 ckpt（`save_freq`、long FT は 10k）までは `0/50000` のままになることがあります。次ジョブからは学習ログをストリームしてより細かく更新します。

## 完了通知（Slack / Discord）

Incoming Webhook URL を渡すと、指定ジョブの完了・失敗を通知できます。  
通知本文には **SR / episodes / by_category / 所要時間 / train 設定** が入ります。

```bash
# どちらか一方（秘密は環境変数推奨）
export PARC_NOTIFY_WEBHOOK_URL='https://hooks.slack.com/services/...'
# または Discord: https://discord.com/api/webhooks/...

uv run parc-queue notify-test

# 新規投入時
uv run parc-enqueue -c configs/experiments/grpo_smoke.yaml --notify
uv run parc-enqueue --sweep configs/sweeps/overnight_ft_v1.yaml --notify

# すでにキューにあるジョブへ後付け
uv run parc-queue notify-on <job_id>
uv run parc-queue notify-on --all-active

# 完了済みジョブのサマリを今すぐ送る / 中身だけ確認
uv run parc-queue notify-send <job_id> --preview
uv run parc-queue notify-send <job_id>
```

`configs/paths.yaml` の `notify.notify_all: true` にすると全ジョブ通知（`--notify` 不要）。

### GPU 死活監視（Fleet hub → Discord）

ハブ PC から `hosts.yaml` の各機へ SSH で `nvidia-smi` を叩き、**OK↔NG の変化時だけ** webhook 通知します（ジョブ完了通知とは別）。

```bash
# 疎通確認（通知なし）
uv run parc-fleet gpu-check --no-notify

# 本番（状態変化時のみ Discord）
uv run parc-fleet gpu-check

# 特定ホスト / 自マシンも含める / 強制通知
uv run parc-fleet gpu-check --host nuc --host thor
uv run parc-fleet gpu-check --include-local
uv run parc-fleet gpu-check --force

# 同じ障害が続くとき N 時間ごとに再通知（または PARC_GPU_WATCH_REMIND_HOURS）
uv run parc-fleet gpu-check --remind-hours 6
```

cron 例（5 分おき・ハブの parc ディレクトリで）:

```cron
*/5 * * * * cd /path/to/LIBERO-plus/parc && /home/kevin/.local/bin/uv run parc-fleet gpu-check >/tmp/parc-gpu-check.log 2>&1
```

状態は `experiments/.parc_gpu_watch.json` に保存。表示名は `PARC · <障害ホスト>`。

## 掴み精度改善（long FT ゲート）

overnight 短学習で SR=0 のときは:

```bash
# 観測向きの目視（robot venv + PYTHONPATH）
# 詳細は docs/07「観測アラインメント」
bash -lc 'source ../.venv/bin/activate && source ../scripts/thor_cuda_env.sh && \
  export PYTHONPATH=src:.. HF_HOME=/mnt/sda/huggingface && \
  python scripts/dump_obs_align.py'

# 本学習スイープ（50k / 100k, t003@10k resume）
uv run parc-enqueue --sweep configs/sweeps/long_ft_v1.yaml --notify

# Gate 判定
uv run scripts/check_ft_gates.py

# Gate2 未達なら vision unfreeze 対照
uv run parc-enqueue --sweep configs/sweeps/long_ft_unfreeze_v1.yaml --notify
```

Gate2（SR>0）達成前は GRPO/GSPO を開始しない。

## Fleet（複数 PC 横断）

ハブの Web では **Fleet** チェックで全ホストの Runs / Queue を横断表示できます。  
Jobs の **Target host** で投入先（local / nuc / thor …）を選べます。

前提: `configs/hosts.yaml` と SSH 鍵（BatchMode）。詳細は [11_multi_machine.md](11_multi_machine.md)。

```bash
uv run parc-fleet hosts
uv run parc-fleet runs --limit 50
uv run parc-fleet enqueue --host nuc -c configs/experiments/smoke_random.yaml --kind eval
uv run parc-fleet gpu-check   # GPU 死活 → Discord（上記セクション参照）
```

リモート run の動画・詳細はハブから配信しません。対象ホストの Web（SSH トンネル）を開いてください。

## セキュリティ

- ジョブ操作は `PARC_WEB_ALLOW_JOBS=1` のときのみ
- Docs API は `docs/*.md` の allowlist のみ配信
- 公開するなら reverse proxy + 認証を推奨

## 関連 CLI / ドキュメント

- [09_autoloop_and_rl.md](09_autoloop_and_rl.md) — 無人ループ・GRPO
- [05_experiments.md](05_experiments.md) — run 規約
- [08_remote_and_ui.md](08_remote_and_ui.md) — リモート接続
- [11_multi_machine.md](11_multi_machine.md) — Fleet / hosts / GDrive
