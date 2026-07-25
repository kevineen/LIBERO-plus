# 11. 複数 PC での実験分離

コード・実験 YAML は git で共有し、**大容量データと実験成果物は各 PC ローカル**に置きます。  
同じ NFS に複数 `parc-worker` を当てて同時書き込みしないでください。

## 方針

| 共有（git） | 共有しない（ローカル） |
|-------------|------------------------|
| `parc/src/`, `scripts/`, `docs/`, `web/` ソース | `experiments/**`, ckpt, videos |
| `configs/experiments/*.yaml`, `configs/sweeps/*.yaml` | `HF_HOME` / datasets / hub |
| `configs/paths.example.yaml` | **`configs/paths.yaml`** |
| `configs/claims/*.claim.yaml`（任意） | `.venv/`, `node_modules/` |

```text
git clone → paths.yaml をローカル作成 → HF データ取得 → enqueue → worker
```

## 1. 初回セットアップ（他 PC）

```bash
git clone <LIBERO-plus-remote>
cd LIBERO-plus/parc
cp configs/paths.example.yaml configs/paths.yaml
# experiments_dir / data_dir / hf_home をこの PC のパスに編集

export PARC_MACHINE_ID=pc2   # 例: thor / laptop / pc2
# または paths.yaml に machine_id: pc2

# 依存（robot venv + parc）は docs/01_setup.md に従う
uv sync
bash scripts/setup_env.sh
```

Web:

```bash
export PARC_WEB_ALLOW_JOBS=1
bash scripts/start_web.sh
# 別端末
uv run parc-worker --loop --poll-sec 30
```

## 2. run_id と machine

新規 run は次の形式です。

```text
{utc}_{machine}_{uuid8}_{safe_name}
例: 20260725T173000Z_thor_a1b2c3d4_long_ft_unfreeze_v1_t000
```

- `PARC_MACHINE_ID`（優先）→ `paths.yaml` の `machine_id` → `hostname` 短縮形
- `RunMeta.machine_id` とタグ `machine:<id>` が registry に入る
- `parc-list` / Web Runs 表に Machine 列あり

旧 run（machine 無し）はそのまま読めます。

## 3. 実験が被らない運用

1. **1 PC = 1 `experiments_dir` = 1 worker**（キューはローカル専用）
2. 同じ仮説を複数 PC で回すときは sweep 名に接尾辞:
   - `long_ft_unfreeze_v1__thor`
   - `long_ft_unfreeze_v1__pc2`
3. 任意で [`configs/claims/`](../configs/claims/README.md) に担当宣言
4. seed / trial をずらす場合は YAML か enqueue overrides で明示

## 4. データと ckpt

### 学習データ

各 PC で `HF_HOME` 配下に取得（repo_id は YAML に書くだけ）。手順は [02_data.md](02_data.md)。

### チェックポイントの受け渡し

重いので git に入れない。次のいずれか:

**A. Google Drive（rclone）— 推奨**

```bash
# 各 PC（初回）— rclone 導入済みなら setup スクリプト
# 手元 PC: ssh -L 53682:127.0.0.1:53682 kevin@thor
bash scripts/setup_gdrive_rclone.sh

# paths.yaml（この Thor では sync.enabled: true / machine_id: thor 済み）
# 手動確認
uv run parc-sync status
uv run parc-sync upload <run_id> --dry-run
uv run parc-sync upload <run_id> --force
```

配置: `gdrive:PARC/ckpts/<machine>/<run_id>/<step>/pretrained_model/`  
ジョブ `done` 後にワーカーが自動アップロードを試行します（失敗しても学習は継続）。

**B. rsync / USB**

```bash
rsync -avP \
  experiments/<run_id>/train_output/checkpoints/010000/pretrained_model/ \
  otherpc:/data/parc_ckpts/<run_id>_010000/
```

受信側は `--policy.pretrained_path=` をそのマシンのパスに差し替え。

### ディスク

各 PC で `disk.max_bytes_gb` / `parc-prune` を独立運用（[09_autoloop_and_rl.md](09_autoloop_and_rl.md)）。

## 5. 片方の PC から両方を操作する

できます。**キューは各 PC ローカルのまま**、操作だけ SSH で飛ばします（共有書き込みはしない）。

### CLI（投入・再開・キャンセル・状態）

```bash
cp configs/hosts.example.yaml configs/hosts.yaml   # 編集して git 外に

uv run parc-remote --list-hosts
uv run parc-remote thor queue status
uv run parc-remote pc2 enqueue -c configs/experiments/smoke_random.yaml --notify
uv run parc-remote thor queue resume <run_id> --mode train
uv run parc-remote thor queue cancel <job_id>
uv run parc-remote thor queue requeue <job_id>
```

`running` の強制停止は、対象 PC で `parc-worker` / `lerobot-train` を kill する必要があります（`cancel` はキュー状態を cancelled にする）。

### Web UI（両画面）

```bash
uv run parc-remote thor --tunnel
# → ssh -N -L 3030:127.0.0.1:3030 ...
uv run parc-remote pc2 --tunnel
# hosts.yaml の local_web_port: 3031 なら
# → http://127.0.0.1:3030 と :3031 で両マシンの UI
```

各ホストで `bash scripts/start_web.sh` と `parc-worker --loop` が動いていることが前提です。

## 6. やってはいけないこと

- 複数 PC から同じ `experiments_dir` / `queue.jsonl` を同時書き込み
- `paths.yaml` / `hosts.yaml` や `*.safetensors` を commit
- Gate2（SR>0）前に両 PC で無計画に GRPO を開始

## 関連

- [01_setup.md](01_setup.md) — 環境
- [05_experiments.md](05_experiments.md) — run 規約
- [08_remote_and_ui.md](08_remote_and_ui.md) — 1 ホストへのリモート UI
- [10_ops_ui.md](10_ops_ui.md) — キュー操作
