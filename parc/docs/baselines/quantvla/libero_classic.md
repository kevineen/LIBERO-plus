# QuantVLA — classical LIBERO (GR00T N1.5)

- Date: 2026-08-01
- Host: **winpc** (RTX 4090) — thor disk was ~98%; see [design](../../superpowers/specs/2026-08-01-quantvla-repro-design.md)
- Code: `/home/kevin/Matsuo/robot/QuantVLA` ([upstream](https://github.com/AIoT-MLSys-Lab/QuantVLA))
- Protocol: `num_trials_per_task=1` (fast trend; paper uses more trials — high variance expected)
- Denoising steps: 8 · Quant: W4A8 + ATM + OHB (`run_quantvla.sh`)
- Logs: [logs/](logs/)

## Results

Paper GR00T reference (more trials): FP16 Avg **86.5%** · QuantVLA (LLM+DiT) **88.0%** ([project](https://quantvla.github.io/)).

| Suite | FP16 SR | QuantVLA SR | FP16 VRAM start (MiB) | Quant VRAM start (MiB) |
|-------|--------:|------------:|----------------------:|-----------------------:|
| libero_spatial (Spatial) | **1.00** | **1.00** | 11881 | 11673 |
| libero_object (Object) | **0.90** | **0.90** | 8204 | 11687 |
| libero_goal (Goal) | **0.60** | **0.80** | 13426 | 11678 |
| libero_10 (Long) | **1.00** | **0.70** | 8233 | 11677 |
| **Avg** | **0.875** | **0.850** | | |

Interpretation (n=1/task):

- Spatial / Object: FP16 ≈ QuantVLA
- Goal: QuantVLA **better** (+20 pt)
- Long: QuantVLA **worse** (−30 pt) — likely trial noise and/or quantization sensitivity on long horizon; re-run with `num_trials_per_task≥5` before strong claims
- Avg within a few points of paper floor; **not** a claim that QuantVLA beats FP16 under this thin protocol
- VRAM: Quant path ~11.7 GB steady; FP16 varied 8–13 GB (suite / load state). Fake-quant W4A8 may not show full integer-kernel savings

## Smoke (R-Gate1)

- `libero_spatial` task 0 × 1 trial FP16: Success=True (`logs/eval_libero_spatial_fp16_smoke.log`)

## Reproduce

```bash
bash /home/kevin/Matsuo/robot/QuantVLA/scripts/resume_classic_batch.sh
# or per suite:
bash /home/kevin/Matsuo/robot/QuantVLA/scripts/run_classic_eval.sh fp16 libero_spatial --num-trials-per-task 1
bash /home/kevin/Matsuo/robot/QuantVLA/scripts/run_classic_eval.sh quant libero_spatial --num-trials-per-task 1
```

`~/.libero/switch_classic.sh` before eval; `datasets` dir may be empty (warning only).
