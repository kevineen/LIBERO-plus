# GPU 死活 → 自動再起動 + 記録（hub 拡張）

日付: 2026-07-30  
ステータス: **仕様レビュー待ち**（実装前）

## Goal

WSL2 等で `nvidia-smi` / NVML が死んだホストを、hub の既存 `parc-fleet gpu-check` から **検知 → 記録 →（許可機のみ）再起動 → 復帰後 worker 自動起動**まで自動化する。誤爆と再起動ループを防ぐ。

## 背景（既知の障害モード）

- 症状: `Failed to initialize NVML: N/A` / `gpu_dead`（SSH は生存）
- 典型ホスト: **nuc（WSL2 + RTX 3090）**
- 復旧: Windows ホスト再起動（`shutdown.exe /r`）が有効。WSL 単体 reboot では足りないことが多い
- 既存: `parc.fleet.gpu_watch` はプローブ + Discord エッジ通知のみ（再起動なし）
- 根本原因（TDR / ドライバ / WSL 既知不具合等）はログ不足で未特定 → **死ぬ前の証拠を残す**のが副目的

## 採用アプローチ

**A. hub 拡張**（既存 `gpu-check` cron に足す）

- hosts.yaml でホストごとに許可
- Discord / 状態ファイル / fleet 運用と一貫
- hub 停止中は動かない（許容。必要なら後でローカル watchdog を追加）

## 非目標

- `unreachable`（SSH 不通）での自動再起動（ネットワーク揺らぎで誤爆しやすい）
- thor / winpc への既定自動再起動（明示許可がない限りしない）
- GPU 故障のハードウェア診断・ドライバ自動更新
- 学習ジョブの自動 resume（worker 起動まで。queued は worker が拾う）

## 設定（hosts.yaml）

```yaml
hosts:
  nuc:
    ssh: kevin@100.82.118.86
    parc_dir: /home/kevin/Matsuo/LIBERO-plus/parc
    web_port: 3030
    local_web_port: 3031
    # --- GPU auto-recover（本仕様で追加）---
    auto_reboot: true
    reboot_method: windows_shutdown   # windows_shutdown | linux_reboot
    # 任意オーバーライド（省略時は下記デフォルト）
    # gpu_dead_streak_needed: 2
    # reboot_cooldown_hours: 1
```

`hosts.example.yaml` にもコメント付きで同キーを記載する。

### デフォルト定数

| 項目 | 値 | 理由 |
|------|-----|------|
| 連続 `gpu_dead` 必要回数 | **2** | 単発 NVML グリッチ対策（5 分 cron なら約 10 分） |
| 再起動クールダウン | **1 時間に最大 1 回** | ループ暴走防止 |
| 再起動対象 status | **`gpu_dead` のみ** | `unreachable` は通知のみ |
| 復帰待ち | 最大約 10 分（ポーリング） | Windows 起動 + Tailscale + WSL |
| worker 起動 | 復帰かつ GPU OK 後に自動 | queued ジョブ再開 |

## 安全スイッチ

自動再起動は **明示 ON のときだけ**実行する（誤って cron に載せただけでは動かない）。

優先順:

1. CLI: `parc-fleet gpu-check --auto-reboot`
2. または env: `PARC_GPU_AUTO_REBOOT=1`

どちらも無い場合: 現行どおり検知・通知・状態更新のみ（記録イベントは `action=none` でも書いてよい）。

`--dry-run-reboot`: 再起動コマンドを実行せず、記録と通知だけ（テスト用）。

## 処理フロー

```text
gpu-check (cron)
  ├─ 各ホスト probe（既存）
  ├─ Discord エッジ通知（既存）
  ├─ 状態更新: status, detail, gpu_dead_streak, last_reboot_at
  ├─ イベント追記: gpu_watch_events.jsonl
  └─ if auto-reboot enabled AND host.auto_reboot
       AND status==gpu_dead AND streak>=2
       AND cooldown OK:
         ├─ preflight 証拠収集（可能なら）
         ├─ SSH reboot コマンド
         ├─ イベント: reboot_requested / reboot_sent / reboot_failed
         ├─ Discord: REBOOT 通知
         └─ （同一 cron またはフォロージョブ）recovery poll:
              ├─ SSH 復帰 → GPU OK
              ├─ parc-worker --loop 起動（未起動なら）
              └─ イベント: recovered / worker_started / recover_timeout
```

### streak / cooldown 規則

- `ok` または `unreachable` に遷移したら `gpu_dead_streak = 0`
- `gpu_dead` が続くたびに streak++（同一 check 内で二重加算しない）
- `last_reboot_at` から 1 時間未満なら再起動スキップ（イベント `reboot_skipped_cooldown`）

### 再起動コマンド

| `reboot_method` | コマンド（SSH 先で実行） |
|-----------------|-------------------------|
| `windows_shutdown` | `/mnt/c/Windows/System32/shutdown.exe /r /t 5 /f /c "PARC GPU auto-reboot"` |
| `linux_reboot` | `sudo -n /sbin/reboot`（パスワード無し sudo 必須。失敗は記録） |

### 復帰後 worker 起動

- リモート `parc_dir` で:
  - WSL PATH: `/usr/lib/wsl/lib` を付与（既存 GPU probe と同様）
  - `PARC_MACHINE_ID=<alias>`（hosts から推定、または既存 .env.local）
  - `nohup uv run parc-worker --loop --poll-sec 15 >> experiments/queue/worker.log 2>&1 &`
- 既に worker が生きていれば起動スキップ（イベント `worker_already_running`）

## 記録

### 1. 状態ファイル（既存拡張）

`experiments/.parc_gpu_watch.json` のホストエントリに追加:

- `gpu_dead_streak: int`
- `last_reboot_at: iso | null`
- `last_reboot_result: str | null`

### 2. 追記ログ（新規）

`experiments/gpu_watch_events.jsonl`（1 行 1 イベント、git 外想定）

必須フィールド例:

```json
{
  "ts": "2026-07-30T05:00:00+00:00",
  "hub": "winpc",
  "host": "nuc",
  "event": "reboot_sent",
  "status": "gpu_dead",
  "detail": "Failed to initialize NVML: N/A",
  "streak": 2,
  "action": "windows_shutdown",
  "ok": true,
  "extra": {}
}
```

### 3. 再起動前の証拠（best-effort）

SSH が生きて `gpu_dead` のとき、短い診断を `extra` または別ファイル `experiments/gpu_watch_dumps/<host>_<ts>.txt` に保存:

- `nvidia-smi` 生出力
- `uname -a` / WSL か否か
- （取得できれば）`dmesg` 末尾の nvidia/nvrm 行

取得失敗しても再起動は続行（証拠は副次）。

## CLI / 運用

```bash
# 監視のみ（現行互換）
uv run parc-fleet gpu-check

# 自動再起動 ON（cron 推奨）
uv run parc-fleet gpu-check --auto-reboot

# テスト
uv run parc-fleet gpu-check --auto-reboot --dry-run-reboot --host nuc --force
```

cron 例（hub）:

```cron
*/5 * * * * cd /path/to/parc && uv run parc-fleet gpu-check --auto-reboot >>/tmp/parc-gpu-check.log 2>&1
```

Discord: 既存 webhook。イベント例:

- `GPU ALERT`（既存）
- `GPU REBOOT`（送信時）
- `GPU RECOVERED + worker started`（復帰時）

## 実装タッチポイント（予定）

- `src/parc/fleet/gpu_watch.py` — streak / cooldown / reboot / recover / jsonl
- `src/parc/remote/hosts.py` — `auto_reboot` 等を load
- `src/parc/cli.py` — `--auto-reboot` / `--dry-run-reboot`
- `configs/hosts.example.yaml` / `docs/10_ops_ui.md` — ドキュメント
- 初期運用: `hosts.yaml` の **nuc のみ** `auto_reboot: true`

## 成功条件

1. nuc を `auto_reboot: true` にした状態で、連続 2 回の `gpu_dead`（または dry-run）が記録に残る
2. dry-run で実再起動なしにフローを検証できる
3. 実再起動後、SSH+GPU OK かつ worker が自動起動し、queued ジョブが拾われる
4. 1 時間以内の 2 回目再起動はスキップされ、イベントに残る
5. thor（許可なし）は通知のみで再起動されない

## リスクと緩和

| リスク | 緩和 |
|--------|------|
| 誤再起動 | 許可フラグ + streak2 + cooldown + `--auto-reboot` 明示 |
| 再起動後 SSH が戻らない | timeout イベント + Discord。手動介入 |
| worker 二重起動 | pgrep してから起動 |
| sudo reboot 失敗（Linux） | 失敗を記録・通知。windows_shutdown を nuc 既定に |
| hub ダウン | 監視停止（既知制限）。後続でローカル B を検討可 |

## 将来（本仕様外）

- ホスト上の補助 watchdog（hub 非依存）
- Windows イベントログの定期収集
- `unreachable` の別ポリシー（より長い streak + 別クールダウン）
