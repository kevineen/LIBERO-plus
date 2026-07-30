# Playbook: 状況確認

作業ディレクトリ: `LIBERO-plus/parc`  
ローカル（このマシン）では必ず `.env.local` を読んでから CLI を叩く。

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
set -a && source .env.local && set +a
```

## 1. ローカルキュー

```bash
uv run parc-queue status --limit 10
pgrep -af 'parc-worker --loop' | grep -v snap || echo 'NO_WORKER'
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader | head -1
```

## 2. Fleet 横断

```bash
uv run parc-fleet hosts
uv run parc-fleet runs --limit 20
uv run parc-fleet gpu-check --no-notify   # nuc/thor GPU 死活
# hub で自動再起動を有効にしている場合（判定のみ）:
# uv run parc-fleet gpu-check --auto-reboot --dry-run-reboot --host nuc --no-notify
# または remote
uv run parc-remote thor queue status --limit 8
```

thor 直 SSH（Tailscale）:

```bash
ssh -o BatchMode=yes kevin@100.99.61.50 \
  'export PATH="$HOME/.local/bin:$PATH"; cd /home/kevin/Matsuo/robot/LIBERO-plus/parc; uv run parc-queue status --limit 8'
```

## 3. 特定 run の metrics

```bash
# winpc 例
python3 -c "import json; m=json.load(open('experiments/<run_id>/metrics.json')); print(m.get('success_rate'), m.get('by_category'))"
```

thor の experiments は多くが `/mnt/sda/parc_libero_plus/experiments/`。

## 4. 確認後

`01_current_status.md` の日付と表が実態と違えば更新する（→ [update_strategy_docs.md](update_strategy_docs.md)）。

## 判定メモ

| 見え方 | 意味 |
|--------|------|
| queued>0 かつ worker 無し | 投入済みだが消化されない → worker 起動が必要 |
| running なのに GPU 0% | eval ロード中か CPU 前処理。数分待って再確認 |
| Fleet に winpc が無い | Hub 側 `hosts.yaml` 未登録。`04_machine_roles.md` |
| Discord が「thor」なのに winpc の話 | 旧通知。`machine=` 行と run_id 内の machine を見る |
| `gpu_dead` / NVML N/A（SSH は生きてる） | WSL2 GPU パススルー死。nuc は `auto_reboot` で Windows 再起動可（`docs/10_ops_ui.md`） |
| イベントログを見る | `experiments/gpu_watch_events.jsonl`（hub） |
