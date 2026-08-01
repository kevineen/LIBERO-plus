"""Flow-APO / AFLoRA / merge の単体テスト。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from parc.data.clair_nearmiss import build_fake_clair_pairs
from parc.train.aflora import AFLoRACallback, AFLoRAConfig, build_loraplus_param_groups
from parc.train.merge_ckpts import linear_merge_state_dicts, merge_checkpoints


torch = pytest.importorskip("torch")


def test_apo_loss_finite() -> None:
    from parc.train.flow_apo import apo_loss_from_energies

    e_w = torch.tensor([0.1, 0.2])
    e_l = torch.tensor([0.5, 0.6])
    e_ref_w = torch.tensor([0.15, 0.25])
    e_ref_l = torch.tensor([0.45, 0.55])
    loss = apo_loss_from_energies(e_w, e_l, e_ref_w, e_ref_l, beta=0.1, anchor_coef=0.05)
    assert torch.isfinite(loss).all()


def test_flow_apo_smoke_training(tmp_path: Path) -> None:
    from parc.train.flow_apo import run_flow_apo_training

    pairs = tmp_path / "pairs"
    build_fake_clair_pairs(pairs, n_pairs=8, n_steps=24, seed=0)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "logs").mkdir()
    cfg = {
        "seed": 0,
        "train": {
            "backend": "flow_apo",
            "pairs_root": str(pairs),
            "steps": 6,
            "batch_size": 2,
            "chunk_size": 8,
            "lr": 1e-3,
            "device": "cpu",
            "dry_run": False,
            "aflora_freeze_after": 3,
            "aflora_eval_every": 2,
        },
    }
    result = run_flow_apo_training(cfg, run_dir)
    assert result["status"] == "finished"
    assert result["parent_ckpt_eligible"] is False
    assert Path(result["ckpt"]).is_file()


def test_aflora_freezes_low_grad() -> None:
    model = torch.nn.Sequential(
        torch.nn.Linear(4, 4),
    )
    # 擬似 LoRA 名
    model.lora_A = torch.nn.Linear(4, 2, bias=False)
    model.lora_B = torch.nn.Linear(2, 4, bias=False)
    for p in model.parameters():
        p.requires_grad_(True)
    x = torch.randn(2, 4)
    y = model[0](x) + model.lora_B(model.lora_A(x))
    y.sum().backward()
    cb = AFLoRACallback(
        model,
        AFLoRAConfig(freeze_after_step=1, eval_every=1, freeze_frac=0.5),
    )
    # 複数 step して凍結が走る
    for _ in range(3):
        model.zero_grad(set_to_none=True)
        y2 = model[0](x) + model.lora_B(model.lora_A(x))
        y2.sum().backward()
        # lora_A の grad を小さくする
        if model.lora_A.weight.grad is not None:
            model.lora_A.weight.grad.mul_(1e-6)
        cb.on_step_end()
    assert len(cb.state.frozen) >= 1


def test_loraplus_param_groups() -> None:
    class M(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.lora_A = torch.nn.Linear(3, 2, bias=False)
            self.lora_B = torch.nn.Linear(2, 3, bias=False)

    m = M()
    groups = build_loraplus_param_groups(m, lr=1e-4, lr_ratio_b=4.0)
    names = {g["name"] for g in groups}
    assert "lora_A" in names
    assert "lora_B" in names
    b = next(g for g in groups if g["name"] == "lora_B")
    assert b["lr"] == pytest.approx(4e-4)


def test_linear_merge_and_cli(tmp_path: Path) -> None:
    a = {"w": torch.ones(3), "i": torch.tensor([1, 2])}
    b = {"w": torch.zeros(3), "i": torch.tensor([9, 9])}
    merged, stats = linear_merge_state_dicts(a, b, alpha=0.5)
    assert torch.allclose(merged["w"], torch.tensor([0.5, 0.5, 0.5]))
    assert stats["n_float_tensors"] == 1

    pa = tmp_path / "a.pt"
    pb = tmp_path / "b.pt"
    torch.save(a, pa)
    torch.save(b, pb)
    out = tmp_path / "merged_dir"
    meta = merge_checkpoints(pa, pb, out, alpha=0.25)
    assert meta["n_merged_keys"] >= 1
    assert (out / "merged.pt").is_file()
