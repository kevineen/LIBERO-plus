# QuantVLA 研究・再現（2026-08-01）

## Why

[QuantVLA](https://quantvla.github.io/)（CVPR 2026 · [arXiv:2602.20309](https://arxiv.org/abs/2602.20309) · [code](https://github.com/AIoT-MLSys-Lab/QuantVLA)）は VLA 向けの **学習不要 PTQ**（W4A8 · ATM · OHB）。論文は π0.5 / GR00T N1.5 を古典 LIBERO で評価し、量子化部で約 70% メモリ削減・SR が FP16 近傍または上回ると主張する。

本プロジェクトは LIBERO-plus + SmolVLA 主線だが、将来の Gr00t / 本選と研究比較のため、**サイドカー再現**を残す。

## Goal

1. GR00T N1.5 について QuantVLA 公開コードを **parc 依存に混ぜず** 起動できる
2. 古典 LIBERO で FP16 vs QuantVLA の SR / VRAM / latency を記録（論文表の傾向再現）
3. 再現後、LIBERO-plus 摂動下の薄い比較を取る

## Non-goals

- SmolVLA / LeRobot への QuantVLA 移植
- `parc` の `pyproject` / `uv` への依存追加
- 親 ckpt・Gate-RL・提出 zip への接続
- π0.5 再現（別ツリーが揃うまで）
- `parc.policies.build_policy` への正式 Gr00t アダプタ（研究クライアントが動けば十分）

## Decisions（固定）

| Item | Decision |
|------|----------|
| Model | GR00T N1.5 only |
| Layout | 独立 clone（例: `~/Matsuo/robot/QuantVLA`）+ conda `groot_test` / `libero_test` |
| Host | 既定は thor だが **/mnt/sda ~98%・home ~94%** のため本再現は **winpc（RTX 4090）** で実施。長時間 EGL は最小化し headless クライアントのみ |
| Eval order | R-Gate1 → R-Gate2 → 古典 suites（R-Gate3）→ plus 薄い（R-Gate4） |
| `~/.libero` | 古典 LIBERO と LIBERO-plus を **混線させない**（切替手順を baselines に固定） |
| Priority | Language / VR 主線より下。空き GPU 時のみ |

## Gates

| Gate | Criterion |
|------|-----------|
| R-Gate1 | FP16 推論サーバ + `libero_spatial` または `libero_10` ヘッドレスが通る |
| R-Gate2 | `./run_quantvla.sh` が同 suite で通る（初回キャリブ ~5–10 min） |
| R-Gate3 | Spatial / Object / Goal / Long 相当で FP16 vs QuantVLA を記録。傾向一致（絶対値±数 pt 許容） |
| R-Gate4 | LIBERO-plus 薄い subset で FP16 vs QuantVLA カテゴリ別 SR |

## Metrics to record

- Success rate（suite / category）
- Peak VRAM（`nvidia-smi`）
- End-to-end latency（可能な範囲）
- Calibration wall time（初回 QuantVLA）

## Artifact paths

| Path | Content |
|------|---------|
| [docs/baselines/quantvla/](../../baselines/quantvla/) | 古典 / plus 比較表 |
| [strategy/02_results_and_findings.md](../../../strategy/02_results_and_findings.md) | 1 段落要約 |
| [strategy/03_next_actions.md](../../../strategy/03_next_actions.md) | バックログ行 |

## Upstream runbook（要約）

```bash
# Terminal 1 — FP16
conda activate groot_test
cd ~/Matsuo/robot/QuantVLA
./run_inference_server.sh libero_10

# Terminal 2 — eval client
conda activate libero_test
cd ~/Matsuo/robot/QuantVLA
./run_libero_eval.sh libero_10 --headless

# QuantVLA W4A8 (+ ATM + OHB)
conda activate groot_test
./run_quantvla.sh libero_10
```

詳細・env vars は upstream README。キャリブキャッシュは 2 回目以降再利用。

## Success

- [x] 古典 LIBERO FP16 / QuantVLA 表が `docs/baselines/quantvla/libero_classic.md` にある
- [x] plus 薄い表が `libero_plus.md` にある
- [x] strategy 02 に解釈 1 段落
- [x] parc SmolVLA パイプラインにコード差分なし（docs/strategy + LIBERO-plus `torch.load` weights_only のみ）
