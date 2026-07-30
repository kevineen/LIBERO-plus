# 03. 初めての実行（ゴール到達手順）

この章を最後までやると、**学習 → checkpoint 評価 → 実験一覧**まで到達します。  
詰まったら詳細マニュアルへ: [docs/01_setup.md](../docs/01_setup.md) / [docs/03_train.md](../docs/03_train.md) / [docs/04_eval.md](../docs/04_eval.md)。

作業ディレクトリ:

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
```

> **注意**
> - 大きいデータ（`lerobot/libero_plus`）は十数 GB。`df -h` で空きを確認してから学習へ。
> - 機密（`.env.local` / webhook / 鍵）はコミット・チャットに出さない。
> - 長い学習や他マシンのキュー投入は、チームルールに従い確認してから。

---

## Step 0. 前提チェック

- [ ] Linux + GPU が使えるマシンにいる（またはチームが案内したホスト）
- [ ] `uv` が入っている（`uv --version`）
- [ ] このリポジトリを clone 済み

---

## Step 1. 環境セットアップ

```bash
bash scripts/setup_env.sh
bash scripts/fix_assets.sh
```

assets が未取得の場合は [docs/01_setup.md](../docs/01_setup.md) の Hugging Face 取得手順を参照。

疎通:

```bash
uv run parc-smoke --skip-env
uv run parc-list
```

`parc-list` は既存 run が無くてもエラーにならなければ OK です。

---

## Step 2. ランダム評価（パイプライン確認）

シミュレータと評価保存の線を通します（学習はまだ）。

```bash
export MUJOCO_GL=egl
./scripts/parc.sh eval -c configs/experiments/smoke_random.yaml
```

カテゴリ別の小さな subset:

```bash
./scripts/parc.sh eval -c configs/experiments/subset_eval.yaml
```

成功の目安:

- `experiments/<run_id>/` ができる
- `metrics.json` がある（ランダムなので成功率はほぼ 0 でよい）

参考ベースライン: [docs/baselines/random_subset_eval.md](../docs/baselines/random_subset_eval.md)

---

## Step 3. SmolVLA スモーク学習（200 step）

**ここから親 robot venv + CUDA** を使う `train.sh` です（`parc.sh` ではない）。

```bash
bash scripts/train.sh configs/experiments/smolvla_ft_smoke.yaml
```

初回はデータセット取得で時間がかかります。  
終わると `experiments/<run_id>/train_output/checkpoints/...` に重みが残ります。

参考: [docs/baselines/smolvla_ft_smoke.md](../docs/baselines/smolvla_ft_smoke.md)  
詳細: [docs/03_train.md](../docs/03_train.md) / [docs/02_data.md](../docs/02_data.md)

dry-run だけ先に見たい場合:

```bash
uv run parc-train -c configs/experiments/smolvla_ft.yaml
```

（デフォルトは dry-run のことが多い。実際に回すのは `train.sh` + smoke YAML が安全）

---

## Step 4. checkpoint 評価

```bash
bash scripts/eval_ckpt.sh configs/experiments/smolvla_ckpt_smoke_eval.yaml
```

YAML 内の checkpoint パスが、自分の FT run を指しているか確認してください。  
違う場合はコピーしてパスを直した YAML を使うか、既存 docs の手順に従ってください。

参考: [docs/baselines/smolvla_ckpt_smoke_eval.md](../docs/baselines/smolvla_ckpt_smoke_eval.md)

---

## Step 5. 実験一覧で確認（ゴール）

```bash
uv run parc-list
```

自分の FT run / eval run が見えれば、**キャッチアップのゴール達成**です。

必要なら:

```bash
uv run parc-list --help
```

Web UI がある環境では [docs/08_remote_and_ui.md](../docs/08_remote_and_ui.md) / [docs/10_ops_ui.md](../docs/10_ops_ui.md) も参照。

---

## （任意）Step 6. VR デモ収集の線を触る

Quest が無くてもフェイクでプロトコル確認できます。

```bash
bash scripts/vr_teleop.sh --config configs/vr/fake_smoke.yaml --fake --no-dataset
uv run pytest tests/test_vr_*.py tests/test_filter_demos.py tests/test_replay_demos.py -q
```

本番収集・success-only 学習・リプレイ検証は [docs/12_vr_teleop.md](../docs/12_vr_teleop.md)。  
進捗は [feature/vr-teleop/STATUS.md](../feature/vr-teleop/STATUS.md)（Quest 実機 E2E はまだ blocked）。

---

## よくあるつまずき

| 症状 | 確認すること |
|------|----------------|
| assets / BDDL が見つからない | `fix_assets.sh`、`~/.libero/config.yaml` が plus を向いているか（docs/01） |
| `No module named 'yaml'` | システムの python ではなく `uv run` / venv 経由か |
| 評価が重い・終わらない | task を絞っているか（smoke / subset YAML を使う） |
| ディスク不足 | `df -h`、`configs/paths.yaml`、`HF_HOME`（docs/00・02） |
| 学習が CUDA エラー | `train.sh` 経由か、正しいマシン（GPU あり）か |

---

## 完了チェック

- [ ] smoke / ランダム評価で `experiments/` に成果が出た
- [ ] SmolVLA smoke FT が finished
- [ ] ckpt 評価を実行した
- [ ] `uv run parc-list` で自 run を確認した

次: [04_next_steps.md](04_next_steps.md)
