# QuantVLA — LIBERO-plus thin subset (GR00T N1.5)

- Date: 2026-08-02
- Host: winpc (RTX 4090)
- Protocol: `tasks_per_category=2` on plus `libero_spatial` (n=14), `num_trials_per_task=1`
- Task ids (0-based): [plus_thin_task_ids.txt](plus_thin_task_ids.txt)
- Model: `youliangtan/gr00t-n1.5-libero-spatial-posttrain` (same spatial ckpt as classic Spatial)
- Switch: `~/.libero/switch_plus.sh` during eval; restored classic after
- Logs: `logs/eval_plus_spatial_{fp16,quant}.log`

## Results

| Mode | Overall SR | n | VRAM start → end (MiB) |
|------|-----------:|--:|------------------------|
| FP16 | **0.857** (12/14) | 14 | 8054 → 8521 |
| QuantVLA W4A8 | **0.786** (11/14) | 14 | 15825 → 18209 |

### By category

| Category | FP16 | QuantVLA |
|----------|-----:|---------:|
| Background Textures | 1.00 (2/2) | 1.00 (2/2) |
| Camera Viewpoints | **0.00** (0/2) | **0.00** (0/2) |
| Language Instructions | 1.00 (2/2) | 1.00 (2/2) |
| Light Conditions | 1.00 (2/2) | 1.00 (2/2) |
| Objects Layout | 1.00 (2/2) | 1.00 (2/2) |
| Robot Initial States | 1.00 (2/2) | 0.50 (1/2) |
| Sensor Noise | 1.00 (2/2) | 1.00 (2/2) |

Interpretation:

- Both modes fail **Camera** on this thin slice (same failure mode as SmolVLA parent narrative)
- Quant slightly lower overall (−1 episode on RobotInit); not a claim of robustness under plus perturbations
- Quant VRAM higher here (pack/calib residency) — integer-kernel memory savings not demonstrated in this fake-quant path

## Reproduce

```bash
bash /home/kevin/Matsuo/robot/QuantVLA/scripts/run_plus_thin_batch.sh
# or:
bash /home/kevin/Matsuo/robot/QuantVLA/scripts/run_plus_thin_eval.sh fp16
bash /home/kevin/Matsuo/robot/QuantVLA/scripts/run_plus_thin_eval.sh quant
```
