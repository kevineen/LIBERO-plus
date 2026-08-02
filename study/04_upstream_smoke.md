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

## Evo-1 smoke（推奨ルート: thor 既存資産）

前提パス（環境により更新されている場合は baselines を優先）:

```text
CLONE=/mnt/sda/parc_libero_plus/third_party/Evo-1
CKPT=/mnt/sda/parc_libero_plus/checkpoints/Evo1_LIBERO
```

### Step A — 重み・clone 確認

```bash
ls "$CLONE" "$CKPT"
```

無ければ公式どおり clone + `hf download MINT-SJTU/Evo1_LIBERO --local-dir …`。

### Step B — Policy server

1. `Evo_1/scripts/Evo1_server.py` の checkpoint パスを `CKPT` に合わせる
2. Evo1 用 env を activate（flash-attn 済み想定）
3. 起動:

```bash
cd "$CLONE/Evo_1"
python scripts/Evo1_server.py
```

起動ログに bind / ready 相当が出れば **最低限の smoke 成功**。

### Step C —（任意・推奨）thin client

```bash
export LIBERO_CONFIG_PATH="$HOME/.libero-plus"
cd "$CLONE/libero-plus-eval"
# env: libero_plus 等（baselines 参照）
bash test_libero_plus.sh libero_spatial
```

薄くするなら client 側でタスク数を制限（PARC 同尺: `tasks_per_category=2` 相当）。GPU 競合時は server のみでも Phase 4 可（notebook に理由を書く）。

### よくある失敗

| 症状 | 見ること |
|------|----------|
| import / flash-attn | Evo1 env か、MAX_JOBS 付きで入れたか |
| 接続拒否 | server ポートと client ポート |
| 画像サイズ | 448×448 等、README の前処理 |
| ルートディスク逼迫 | `/mnt/sda` 配下に env・重みを置く |

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

- Evo-1 Stage1/2 学習コマンド（README）
- TurboVLA `torchrun` 80k
- Language hard（984/986/988×10）や thick eval — **別承認・GPU 空き待ち**

## 次章

[05_parc_transfer.md](05_parc_transfer.md)
