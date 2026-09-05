# 08. リモートアクセスと実験管理 UI

Thor 上の `parc` を **別 PC のブラウザ / Notebook** から使う手順です。

## 構成（拡張ポイント付き）

```text
別PC ブラウザ ──► Next.js (parc/web) ──► ExperimentStore / JobLauncher
                      │                      │
                      │                      ├─ filesystem (default)
                      │                      └─ (将来) wandb / DB / queue
                      ▼
                 experiments/<run_id>/
                 videos/*.mp4|png
```

| 層 | 役割 | 差し替え方 |
|----|------|------------|
| UI | `parc/web` (Next.js App Router) | ページ・コンポーネント追加 |
| API | `/api/v1/*` | ルート追加で後方互換 |
| Store | `lib/adapters/*` | `registerStore(...)` |
| Launcher | `lib/adapters/shell-launcher.ts` | `registerLauncher(...)` |

## 1. 実験管理 Web（Next.js）

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
bash scripts/start_web.sh          # dev :3030
# bash scripts/start_web.sh prod   # build + start
```

別 PC:

```text
http://192.168.11.5:3030
```

推奨（SSH トンネル）:

```bash
ssh -L 3030:127.0.0.1:3030 kevin@192.168.11.5
# ブラウザ: http://127.0.0.1:3030
```

機能:

- **Evals** — upstream `lerobot-eval` ログの一覧・タスク単位ビュー（`/evals`）
- **Board** — 研究カンバン（`/board` · `experiments/board.json`）
- Runs 一覧・フィルタ・タグ
- Run 詳細（カテゴリ別 SR、config、artifacts、**Resume**）
- 動画 / フレームプレビュー（保存されている場合）
- Jobs / Queue パネル（投入・Cancel・Requeue・Recover stale・進捗）
- Docs（`docs/*.md` マニュアル閲覧）— 入口 `/docs` / `/docs/10_ops_ui`
- 階層サイドバー — Evals → run → suite → task、Board 列、Docs 目次

環境変数:

| 変数 | 意味 |
|------|------|
| `PARC_ROOT` | parc ルート（start_web.sh が設定） |
| `PARC_EXPERIMENTS_DIR` | experiments パス（未設定時は `paths.yaml`） |
| `LEROBOT_EVAL_LOGS_DIR` | `lerobot-eval` の `--output_dir` 親（未設定時は `../lerobot/eval_logs`） |
| `PARC_WEB_ALLOW_JOBS` | `1` でジョブ起動許可 |
| `PARC_WEB_LAUNCHER` | `queue`（既定）または `shell` |
| `PARC_WEB_PORT` | 既定 3030 |
| `PARC_WEB_STORE` | アダプタ ID |

```bash
export PARC_WEB_ALLOW_JOBS=1
export PARC_WEB_LAUNCHER=queue
bash scripts/start_web.sh
```

`PARC_WEB_LAUNCHER=queue` のとき、POST は `parc-enqueue` 経由で `experiments/queue/` に書くだけです。  
実際の train/eval は別プロセスの `uv run parc-worker --loop` が消化します（詳細は [09_autoloop_and_rl.md](09_autoloop_and_rl.md)）。

スイープ投入例（API）:

```json
{ "kind": "custom", "params": { "sweep": "configs/sweeps/overnight_ft_smoke.yaml" }, "notes": "overnight" }
```

### API（v1）

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/v1/health` | ヘルス |
| GET | `/api/v1/system` | 設定 YAML 一覧・capabilities |
| GET | `/api/v1/runs` | 実験一覧 `?limit=&tag=` |
| GET | `/api/v1/runs/:id` | 詳細 |
| GET | `/api/v1/runs/:id/artifacts/...` | ファイル配信 |
| GET/POST | `/api/v1/jobs` | ジョブ一覧 / 起動 |
| GET/DELETE | `/api/v1/jobs/:id` | 状態 / キャンセル |
| GET | `/api/v1/evals` | `lerobot-eval` run 一覧（`eval_logs/` 走査） |
| GET | `/api/v1/evals/:runId` | `eval_info.json` + 動画フォルダからタスク詳細 |
| GET | `/api/v1/evals/:runId/videos/...` | mp4 配信（**HTTP Range** 対応・シーク用） |
| GET/POST | `/api/v1/board` | カンバン一覧 / カード作成 |
| PATCH/DELETE | `/api/v1/board/:cardId` | カード更新 / 削除 |

ジョブ POST 例:

```json
{ "kind": "eval", "configPath": "smoke_random.yaml" }
```

`configPath` は `configs/experiments/` 配下のみ許可（パストラバーサル防止）。

## 2. シミュレータ映像のプレビュー

評価 YAML:

```yaml
eval:
  save_frames: true    # PNG シーケンス → Web で表示しやすい
  save_video: true     # mp4（imageio/ffmpeg がある場合）
  frame_stride: 5
  max_save_frames: 40
```

成果物: `experiments/<run_id>/videos/`  
Web の Run 詳細 → Preview で閲覧。

ライブ 3D 操作 UI は未実装。拡張するなら:

1. `JobLauncher` に `stream` kind
2. WebSocket / MJPEG エンドポイントを `/api/v1/streams` に追加
3. UI に `StreamViewer` コンポーネント

## 3. JupyterLab / Notebook（別 PC）

```bash
bash scripts/start_jupyter_remote.sh 8888
```

`--ip=0.0.0.0` で待ち受ける（`jupyter notebook --host 0.0.0.0` は無効）。  
WSL 内にブラウザが無い警告（`Couldn't find a suitable web browser!`）は無視してよい。`--no-browser` 付き。

### 3-1. SSH トンネル（推奨）

winpc の WSL SSH は **Port 2222**（`strategy/04_machine_roles.md`）:

```bash
ssh -L 8888:127.0.0.1:8888 kevin@192.168.1.14 -p 2222
# ブラウザ: http://127.0.0.1:8888/?token=<起動ログのトークン>
```

### 3-2. WSL2 を LAN IP で直接開く

WSL2 は NAT（例: `172.19.x.x`）なので、別 PC から `http://192.168.1.14:8888` へ届けるには **Windows 側 portproxy** が必要。

WSL:

```bash
hostname -I   # 例: 172.19.129.95
bash scripts/start_jupyter_remote.sh 8888
```

Windows PowerShell（管理者）:

```powershell
netsh interface portproxy add v4tov4 listenport=8888 listenaddress=0.0.0.0 connectport=8888 connectaddress=172.19.129.95
New-NetFirewallRule -DisplayName "Jupyter WSL" -Direction Inbound -LocalPort 8888 -Protocol TCP -Action Allow
```

WSL 再起動後は IP が変わるので `connectaddress` を更新する。

### 3-3. トークンなし（一時・LAN 限定）

トークンだけ空にするとログイン画面で **invalid credentials** になる。次のどちらかを使う。

```bash
# A. スクリプト（推奨）
PARC_JUPYTER_NO_AUTH=1 bash scripts/start_jupyter_remote.sh 8888

# B. 手動（Notebook 7 / Jupyter Server 2）
uv run jupyter notebook \
  --no-browser --ip=0.0.0.0 --port=8888 \
  --IdentityProvider.token='' \
  --ServerApp.password='' \
  --ServerApp.allow_unauthenticated_access=True
```

起動ログに `All authentication is disabled` が出れば成功。  
別 PC: `http://192.168.1.14:8888/tree`（古い `?token=` URL や cookie は捨てる）。  
**LAN 内の誰でもコード実行できる**ので、作業後は必ず止める。固定パスワードにするなら `jupyter notebook password` 後に `--IdentityProvider.token=''` のみ。

`0.0.0.0` 直公開は LAN 内でもトークン／パスワード管理を推奨。

## 4. セキュリティ注意

- ジョブ起動は任意コマンド実行に近いので **デフォルト OFF**
- 本番相当の公開は reverse proxy + 認証を推奨
- artifacts API は run ディレクトリ外への `..` を拒否

## 5. アダプタ追加の例

`web/lib/adapters/my-store.ts` を作り:

```ts
import { registerStore } from "@/lib/adapters";
import type { ExperimentStore } from "@/lib/types";

class MyStore implements ExperimentStore { /* ... */ }
registerStore(new MyStore());
```

`index.ts` で import し、`PARC_WEB_STORE=my-store` を設定。

## 関連

- 実験規約: [05_experiments.md](05_experiments.md)
- **複数 PC / Fleet**: [11_multi_machine.md](11_multi_machine.md)（`parc-fleet`・hosts.yaml・GDrive）
- 無人ループ / GRPO: [09_autoloop_and_rl.md](09_autoloop_and_rl.md)
- 評価: [04_eval.md](04_eval.md)
- データ・学習改善: [07_custom_data_and_algos.md](07_custom_data_and_algos.md)
- UI 操作: [10_ops_ui.md](10_ops_ui.md)
- Episode Viewer: [14_viewer.md](14_viewer.md)
