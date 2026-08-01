#!/usr/bin/env python3
"""Extract final total success rate from QuantVLA libero eval logs."""
from __future__ import annotations
import re
import sys
from pathlib import Path

pat = re.compile(r"Current total success rate:\s*([0-9.]+)")
vram_pat = re.compile(r"(\d+)\s*MiB")

def last_sr(path: Path) -> str:
    text = path.read_text(errors="ignore")
    ms = pat.findall(text)
    return ms[-1] if ms else "n/a"

def vram(path: Path) -> str:
    if not path.exists():
        return ""
    lines = path.read_text().strip().splitlines()
    if len(lines) < 2:
        return ""
    m = vram_pat.search(lines[1])
    return m.group(1) if m else lines[1]

def main() -> None:
    logdir = Path(__file__).resolve().parent / "logs"
    suites = ["libero_spatial", "libero_object", "libero_goal", "libero_10"]
    print("| Suite | FP16 SR | QuantVLA SR | FP16 VRAM | Quant VRAM |")
    print("|-------|--------:|------------:|----------:|-----------:|")
    fps, qs = [], []
    for s in suites:
        fp = last_sr(logdir / f"eval_{s}_fp16.log")
        qt = last_sr(logdir / f"eval_{s}_quant.log")
        fv = vram(logdir / f"vram_{s}_fp16_start.csv")
        qv = vram(logdir / f"vram_{s}_quant_start.csv")
        print(f"| {s} | {fp} | {qt} | {fv} | {qv} |")
        if fp != "n/a":
            fps.append(float(fp))
        if qt != "n/a":
            qs.append(float(qt))
    if fps:
        print(f"| **Avg** | {sum(fps)/len(fps):.3f} | {sum(qs)/len(qs):.3f if qs else 'n/a'} | | |")

if __name__ == "__main__":
    main()
