# 03. ファインチューニング

## 方針（ルール前）

| フェーズ | バックエンド | 目的 |
|----------|--------------|------|
| 今 | LeRobot + SmolVLA（軽量） | 学習→ckpt→評価の線を通す |
| 本選 | 配布の Pi0 / Gr00t / 指定 VLA | 本番スコア |

`parc-train` は **YAML → コマンド生成 / 実行** の薄いラッパです。  
重い学習本体は既存フレームワークに任せます。

## 1. コマンドだけ確認（dry-run）

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
uv run parc-train -c configs/experiments/smolvla_ft.yaml
```

`experiments/<run_id>/logs/train_cmd.txt` に実際のコマンドが書かれます。  
デフォルトは `dry_run: true` です。

## 2. 本当に学習する（Jetson Thor）

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc

# 超小規模（200 step）でパイプライン確認
bash scripts/train.sh configs/experiments/smolvla_ft_smoke.yaml

# もう少し長く回す場合は smolvla_ft.yaml をコピーして
#   dry_run: false / steps: 10000
# にしてから:
# bash scripts/train.sh configs/experiments/smolvla_ft_local.yaml
```

`scripts/train.sh` は親 `Matsuo/robot` の venv + `thor_cuda_env.sh` + cu12 ライブラリをセットします。

注意:

- データは `HF_HOME`（既定 `/mnt/sda/huggingface`）にキャッシュされる
- ディスク逼迫時は先に `df -h` を確認
- 親 venv へ `parc` を入れるなら必ず `uv pip install -e parc --no-deps`
## 3. 公式に近い学習コマンド例（手動）

LeRobot ドキュメント相当:

```bash
lerobot-train \
  --policy.type=smolvla \
  --policy.load_vlm_weights=true \
  --dataset.repo_id=lerobot/libero_plus \
  --env.type=libero \
  --env.task=libero_spatial \
  --output_dir=./experiments/manual_smolvla/checkpoints \
  --steps=10000 \
  --batch_size=4 \
  --eval.n_episodes=1 \
  --env_eval_freq=1000
```

注意: インストール済み LeRobot **0.5.1** には `env.type=libero_plus` が無いことがあります。  
その場合は **LIBERO-plus を `import libero` に差し替えたうえで `env.type=libero`** とし、評価は `parc-eval` 側で plus タスクを回します。

## 4. OpenVLA-OFT / OpenPI（後で接続）

本選コードが来たら `src/parc/train/` にモジュールを追加し、  
`train.backend: openpi` などを実装します。雛形の戻り値は既に `not_implemented` で用意済みです。

学習後は `policy.type: checkpoint` と `path:` を評価 YAML に書き、  
`bash scripts/eval_ckpt.sh` で LIBERO-plus 評価へつなぎます。

## 5. オリジナルデータ・学習改善

データ差し替え、ハイパーパラ実験、独自バックエンド接続の手順書:

→ **[07_custom_data_and_algos.md](07_custom_data_and_algos.md)**

関連テンプレ:

- `configs/experiments/smolvla_ft_custom_data.yaml`
- `scripts/examples/convert_demo_to_lerobot.py`

## 6. 他ベンチ（MT50）の学習骨格

`benchmark.backend: metaworld_mt50` を書いた YAML（例: `configs/experiments/mt50_ft_skeleton.yaml`）では、  
`parc-train` は本学習せず `status: not_implemented` と DatasetSpec / skeleton meta を返します。  
評価は `eval.backend: metaworld_mt50` + 別 venv（[01_setup.md](01_setup.md) §5b）。デモ変換は未実装（[07](07_custom_data_and_algos.md) D2）。
