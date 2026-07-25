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
huggingface-cli download Sylvest/LIBERO-plus assets.zip --local-dir data
unzip data/assets.zip -d ../libero/libero/
# 中身が assets/ になるよう配置を確認
```

必要なサブディレクトリ例: `textures/`, `scenes/`, `new_objects/` など。

## 2. libero のパス設定

`~/.libero/config.yaml` が **site-packages の別 LIBERO** を向いていると、plus の BDDL / assets が使えません。

```bash
python3 scripts/configure_libero_paths.py
# または
bash scripts/setup_env.sh
```

確認:

```bash
python3 -c "from libero.libero import get_libero_path; print(get_libero_path('assets'))"
```

`.../LIBERO-plus/libero/libero/assets` になっていれば OK。

## 3. parc パッケージ

```bash
cd parc
uv sync
source .venv/bin/activate   # 任意
uv pip install -e ..        # 親 LIBERO-plus を editable で
```

親の `Matsuo/robot` で既に torch / lerobot がある場合、**学習は親 venv**、  
**評価・実験管理は parc venv**、でも構いません（`docs/03_train.md` 参照）。

Jetson で torch を使うときは親側の:

```bash
source ~/Matsuo/robot/scripts/thor_cuda_env.sh
```

を忘れずに。

## 4. ヘッドレス描画

```bash
export MUJOCO_GL=egl
```

`configs/paths.example.yaml` を `configs/paths.yaml` にコピーしても設定できます。  
`paths.yaml` はマシン固有のため git 管理外です。複数 PC で分ける手順は [11_multi_machine.md](11_multi_machine.md)。

```bash
cp configs/paths.example.yaml configs/paths.yaml
export PARC_MACHINE_ID=thor   # 任意（未設定時は hostname）
```

## 5. スモーク

```bash
uv run parc-smoke --skip-env   # import / パス
./scripts/parc.sh eval -c configs/experiments/smoke_random.yaml
```

シミュレータが立ち上がり、`experiments/<run_id>/metrics.json` ができればセットアップ完了です。

### よくある失敗

| 症状 | 対処 |
|------|------|
| `No module named 'libero'` | `python3 scripts/configure_libero_paths.py` と `libero/__init__.py` があること、`PYTHONPATH=LIBERO-plus` |
| `torch.load` / `weights_only` | `parc-eval` 内でローカル init は `weights_only=False` 済み |
| `mj_fullM(): incompatible` | robosuite 1.4 と MuJoCo 3.x の API 差。`parc.env.mujoco_compat` が自動パッチ（旧: `mujoco==3.1.1` ピン） |
| NumPy が突然 2.x に | 親 `.venv` へ `pip install -e parc` するとき必ず `--no-deps` |
