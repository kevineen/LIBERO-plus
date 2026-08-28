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

## 3. JupyterLab（別 PC）

```bash
bash scripts/start_jupyter_remote.sh 8888
```

別 PC（推奨）:

```bash
ssh -L 8888:127.0.0.1:8888 kevin@192.168.11.5
```

トークンは起動ログの URL を使う。  
`0.0.0.0` 直公開は LAN 内でもトークン管理必須。

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
