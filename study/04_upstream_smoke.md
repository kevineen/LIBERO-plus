# 04. Upstream smoke（必須）

**この章が本トラックの必須ハンズオン。** フル学習はしない。  
演習ノート: [notebook/turbovla_evo1_smoke_checklist.ipynb](notebook/turbovla_evo1_smoke_checklist.ipynb)

対応クイズ: [quiz/q04_upstream_smoke.md](../quiz/q04_upstream_smoke.md)

## 目標

次のどちらか（できれば両方）を達成し、notebook に結果を残す。

1. **Evo-1**: policy server 起動確認、可能なら thin client 接続まで
2. **TurboVLA**: HF ckpt 取得 + `evaluate.py` を 1 suite・少数 trial、または GPU 無しなら引数ウォークスルーを記録

## 読むもの

| 優先 | リソース |
|------|----------|
| Must | [Evo-1 README — LIBERO-plus](https://github.com/MINT-SJTU/Evo-1) |
| Must | [TurboVLA README — Evaluation](https://github.com/H-EmbodVis/TurboVLA) |
| Must | [baselines/evo1/libero_plus.md](../parc/docs/baselines/evo1/libero_plus.md) Reproduce 節 |
| Must | 本ノートの checklist notebook |

## Evo-1 smoke（推奨ルート: **winpc** · x86）

> **2026-08-03 チーム実測:** winpc で Language hard thin（984/986/988×1）まで完了。**SR=0.000**（親判定外）。詳細は [baselines/evo1/libero_plus.md](../parc/docs/baselines/evo1/libero_plus.md)。  
> thor は **aarch64** のため Evo-1 policy env は非推奨（clone/weights のみ `/mnt/sda` にあり）。

前提パス（更新時は baselines を優先）:

```text
# winpc（推奨）
CLONE=/mnt/b/parc_sidecars/Evo-1
CKPT=/mnt/b/parc_sidecars/Evo1_LIBERO
# thin client（PARC）
CLIENT=parc/scripts/evo1_parc_thin_client.py

# thor（資産のみ · aarch64）
# CLONE=/mnt/sda/parc_libero_plus/third_party/Evo-1
# CKPT=/mnt/sda/parc_libero_plus/checkpoints/Evo1_LIBERO
```

### Step A — 重み・clone 確認

```bash
ls "$CLONE" "$CKPT"
```

無ければ公式どおり clone + `hf download MINT-SJTU/Evo1_LIBERO --local-dir …`。

### Step B — Policy server

1. `Evo_1/scripts/Evo1_server.py` の `ckpt_dir` を `CKPT` に合わせる（winpc 版は `/mnt/b/parc_sidecars/Evo1_LIBERO`）
2. conda env `Evo1` を activate（flash-attn は任意。未導入でもロード可の実績あり）
3. 起動:

```bash
cd "$CLONE/Evo_1"
python scripts/Evo1_server.py
# ready: ws://0.0.0.0:9000
```

起動ログに bind / ready 相当が出れば **最低限の smoke 成功**。

### Step C —（推奨）PARC thin client

```bash
bash ~/.libero/switch_plus.sh
export MUJOCO_GL=egl
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
../../.venv/bin/python scripts/evo1_parc_thin_client.py \
  --task-ids 984 986 988 --num-episodes 1 --max-steps 280 \
  --server-url ws://127.0.0.1:9000
```

上流フル suite はタスク数が数百になるため、学習用 thin は **タスク ID 制限**を使う。

### よくある失敗

| 症状 | 見ること |
|------|----------|
| import / flash-attn | Evo1 env か、未導入でも動くか（チームは未導入で OK） |
| IndexError on task 984 | classic libero を掴んでいる → `PYTHONPATH` に LIBERO-plus を先に |
| `PosixPath` TypeError | bddl パスを `str()` する（thin client が吸収） |
| 接続拒否 | server ポート 9000 |
| ルートディスク逼迫 | winpc は `/mnt/b`、thor は `/mnt/sda` |

## TurboVLA smoke

### Step A — 取得

```bash
pip install -U huggingface_hub   # 作業 env 内
hf download H-EmbodVis/TurboVLA --local-dir pretrained/TurboVLA
```

### Step B — 評価（GPU あり）

公式に近い形（パスはローカルに合わせる）。**trial 数を小さく**して時間を抑える:

```bash
python experiments/libero/evaluate.py \
  --ckpt_path pretrained/TurboVLA/checkpoints/libero/libero_object.pth \
  --dinov3_path /path/to/dinov3-vitb \
  --bert_path /path/to/bert-base-uncased \
  --stats_path experiments/libero/configs/libero_all4_stats.json \
  --stats_key libero_all4_no_noops \
  --task_suite_name libero_object \
  --num_trials_per_task 1 \
  --chunk_size 12 \
  --num_open_loop_steps 12 \
  --seed 7 \
  --precision bf16 \
  --result_json_path outputs/evaluation/libero_object_smoke.json
```

### Step C — GPU 無しフォールバック（仍は完了可）

notebook に次を記録すれば Phase 4 完了とみなす:

- `evaluate.py --help` 相当で必須引数一覧
- `chunk_size` と `num_open_loop_steps` を一致させる理由
- 使う予定の `stats_key`
- HF にどの ckpt があるか（ディレクトリ一覧のメモ）

## 完了条件

- [ ] checklist notebook の該当欄を埋めた
- [ ] Evo-1 server **または** TurboVLA eval/ウォークスルーの少なくとも一方を完了
- [ ] [q04](../quiz/q04_upstream_smoke.md) を解いた
- [ ] 点数を [rubric](../quiz/rubric.md) で判定し、必要なら下記へ

## つまずいたら

- 易しい補足: [remediation/04/](remediation/04/)
- 復習クイズ: [quiz/bank/04/easy.md](../quiz/bank/04/easy.md)
- 判定: [quiz/rubric.md](../quiz/rubric.md)

## 発展（任意）

- Evo-1 Stage1/2 学習コマンド（README）— PARC 側 Stage1 は **2026-08-03 実行済**（薄い Lang hard SR=0 · 親判定外）。Stage2 は別承認
- TurboVLA `torchrun` 80k
- Evo-1 Language hard ×10 / flash-attn / thick eval — **別承認・GPU 空き待ち**

## 次章

[05_parc_transfer.md](05_parc_transfer.md)
