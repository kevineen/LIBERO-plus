# 01. 環境セットアップ

## 前提

- Linux + GPU（この環境は Jetson / Tegra）
- `uv` が入っていること
- 親リポジトリ: `LIBERO-plus/`（この `parc/` の一つ上）

## 1. assets を正しい場所へ

公式は `assets.zip` を `LIBERO-plus/libero/libero/assets/` に展開します。

過去に深いパスへ展開されている場合:

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
bash scripts/fix_assets.sh
```

未ダウンロードの場合（例）:

```bash
mkdir -p data
# ※ Sylvest/LIBERO-plus は dataset リポジトリ。--repo-type dataset が必須
hf download --repo-type dataset Sylvest/LIBERO-plus assets.zip --local-dir data
unzip data/assets.zip -d ../libero/libero/
# 深いパスに展開された場合は setup_env.sh / fix_assets.sh が正規位置へ移す
```

必要なサブディレクトリ例: `textures/`, `scenes/`, `new_objects/` など。  
最終的に `LIBERO-plus/libero/libero/assets/` があれば OK。

## 2. libero のパス設定 + parc パッケージ

`~/.libero/config.yaml` が **site-packages の別 LIBERO** を向いていると、plus の BDDL / assets が使えません。

推奨（依存インストール → パス設定の順）:

```bash
cd parc
bash scripts/setup_env.sh
# 内部で uv sync のあと .venv の Python で configure_libero_paths.py を実行する
```

手動で分ける場合:

```bash
uv sync
uv run python scripts/configure_libero_paths.py
# または
.venv/bin/python scripts/configure_libero_paths.py
```

システムの `python3` で `configure_libero_paths.py` を直接叩くと `No module named 'yaml'` になり得ます（PyYAML は parc venv 側）。

確認:

```bash
uv run python -c "from libero.libero import get_libero_path; print(get_libero_path('assets'))"
```

`.../LIBERO-plus/libero/libero/assets` になっていれば OK。

## 3. 評価用の親 `.venv`（`parc.sh`）

`./scripts/parc.sh` は **`LIBERO-plus/.venv`**（親）の Python を使います。無い場合:

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus
uv venv .venv
# 評価に必要な最低限（例）
uv pip install --python .venv/bin/python -e parc --no-deps
uv pip install --python .venv/bin/python \
  'numpy>=1.22,<2' pyyaml rich tqdm pillow imageio imageio-ffmpeg \
  'robosuite==1.4.0' bddl easydict cloudpickle 'gym==0.25.2' \
  opencv-python matplotlib 'hydra-core==1.2.0' \
  wand scikit-image termcolor h5py
uv pip install --python .venv/bin/python -e .
# GPU torch（例: CUDA 12.8）
uv pip install --python .venv/bin/python torch --index-url https://download.pytorch.org/whl/cu128
```

`hf` が無いときは `/path/to/miniconda3/bin/hf` や `huggingface-cli` を使う。

## 4. ヘッドレス描画

```bash
export MUJOCO_GL=egl
```

`configs/paths.example.yaml` を `configs/paths.yaml` にコピーしても設定できます。  
または **`cp .env.example .env.local`** で保存先だけ上書き（推奨・PC ごと）。  

優先順位: シェル export > `.env.local` > `.env` > `paths.yaml`。  
詳細は [11_multi_machine.md](11_multi_machine.md)。

```bash
cp .env.example .env.local
# PARC_MACHINE_ID / PARC_EXPERIMENTS_DIR / HF_HOME を編集
```

## 5. スモーク

```bash
uv run parc-smoke --skip-env   # import / パス
./scripts/parc.sh eval -c configs/experiments/smoke_random.yaml
```

シミュレータが立ち上がり、`experiments/<run_id>/metrics.json` ができればセットアップ完了です。

## 5b. Meta-World MT50（研究用・optional）

PARC 本戦の評価対象は **LIBERO / LIBERO-Plus** のままです。MT50 は汎用ベンチ枠の第2バックエンドで、**別 venv 推奨**です（親 `.venv` の `gym==0.25.2` / robosuite と Gymnasium が衝突しやすいため）。

```bash
# 例: MT50 専用 venv
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
uv venv .venv-metaworld
uv pip install --python .venv-metaworld/bin/python -e ".[metaworld]" --no-deps
uv pip install --python .venv-metaworld/bin/python \
  'numpy>=1.22,<2' pyyaml rich tqdm pillow imageio imageio-ffmpeg \
  'metaworld>=3.0' 'gymnasium>=1.0' 'mujoco>=3.1'
# libero は import 経路用に editable（MT50 評価だけなら必須ではないが parc パッケージには含まれる）
uv pip install --python .venv-metaworld/bin/python -e ../ --no-deps

export MUJOCO_GL=egl
.venv-metaworld/bin/parc-eval -c configs/experiments/mt50_smoke_random.yaml
```

または `uv sync --extra metaworld`（既存 LIBERO venv への混在は非推奨）。

学習は骨格のみ: `configs/experiments/mt50_ft_skeleton.yaml`（`parc-train` は `not_implemented` + DatasetSpec を返す）。手順の詳細は [07_custom_data_and_algos.md](07_custom_data_and_algos.md) の「ベンチ追加手順」。

### よくある失敗

| 症状 | 対処 |
|------|------|
| `No module named 'yaml'` | `uv sync` 後に `uv run python scripts/configure_libero_paths.py`（または `bash scripts/setup_env.sh`） |
| HF `404` / Repository Not Found（assets） | `--repo-type dataset` を付ける（model 扱いだと 404） |
| `hf: command not found` | miniconda の `hf` / `huggingface-cli` を使うか `uv pip install huggingface_hub` |
| `No virtual environment ... ../.venv` | 親 `LIBERO-plus` で `uv venv .venv` を先に作成 |
| `No module named parc.cli`（parc.sh） | 親 `.venv` へ `uv pip install -e parc --no-deps` |
| `No module named 'torch'/'wand'/'skimage'` | 親 `.venv` に不足パッケージを追加（上記 §3） |
| `PermissionError: /data` | `.env.local` の `PARC_EXPERIMENTS_DIR` 等を、その PC に存在するパスへ変更 |
| `No module named 'libero'` | `configure_libero_paths.py` と `libero/__init__.py` があること、`PYTHONPATH=LIBERO-plus` |
| `torch.load` / `weights_only` | `parc-eval` 内でローカル init は `weights_only=False` 済み |
| `mj_fullM(): incompatible` | robosuite 1.4 と MuJoCo 3.x の API 差。`parc.env.mujoco_compat` が自動パッチ（旧: `mujoco==3.1.1` ピン） |
| NumPy が突然 2.x に | 親 `.venv` へ `pip install -e parc` するとき必ず `--no-deps` |
| WSL で rclone `127.0.0.1` 空レス | Windows で `rclone authorize` → WSL に token 貼付。または既存 remote（例: `matsuo-gdrive`）を使う |
| MT50 で `ImportError: metaworld` | `parc[metaworld]` を **別 venv** に入れる（§5b）。LIBERO 親 venv へ無理に混在しない |
| MT50 評価で gym / gymnasium 衝突 | LIBERO（`gym==0.25.2`）と Meta-World（Gymnasium）を同一 venv に入れない |
