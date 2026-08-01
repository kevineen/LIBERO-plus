"""チェックポイントの線形マージ（研究サイドカー · Phase 4）。

sim / 摂動カテゴリ別 ckpt 同士の平均。実機 ckpt が無い間のスモーク用。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from parc.paths import PARC_ROOT


def _resolve(path: str | Path) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (PARC_ROOT / p).resolve()
    return p


def _load_state_dict(path: Path) -> dict[str, Any]:
    """``.pt`` / ``.pth`` / ``.safetensors`` / ディレクトリを読む。"""
    path = _resolve(path)
    if path.is_dir():
        # LeRobot pretrained_model を想定
        for name in ("model.safetensors", "pytorch_model.bin", "flow_apo_energy.pt", "grpo_policy.pt"):
            cand = path / name
            if cand.is_file():
                path = cand
                break
        else:
            pts = list(path.glob("*.pt")) + list(path.glob("*.safetensors"))
            if not pts:
                raise FileNotFoundError(f"no weights under {path}")
            path = pts[0]
    if path.suffix == ".safetensors":
        from safetensors.torch import load_file  # type: ignore

        return dict(load_file(str(path)))
    import torch

    obj = torch.load(str(path), map_location="cpu", weights_only=False)
    if isinstance(obj, dict):
        if "model" in obj and hasattr(obj["model"], "keys"):
            return dict(obj["model"])
        if "state_dict" in obj:
            return dict(obj["state_dict"])
        # plain state_dict
        if all(hasattr(v, "shape") for v in obj.values()):
            return obj
    raise ValueError(f"unsupported checkpoint format: {path}")


def linear_merge_state_dicts(
    a: dict[str, Any],
    b: dict[str, Any],
    *,
    alpha: float = 0.5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """θ = (1-α) a + α b。共通キーのみ。

    Returns:
        (merged, stats)
    """
    import torch

    alpha = float(alpha)
    keys = sorted(set(a) & set(b))
    skipped_a = sorted(set(a) - set(b))
    skipped_b = sorted(set(b) - set(a))
    merged: dict[str, Any] = {}
    n_float = 0
    for k in keys:
        va, vb = a[k], b[k]
        if hasattr(va, "dtype") and hasattr(vb, "dtype") and va.shape == vb.shape:
            if va.is_floating_point() and vb.is_floating_point():
                merged[k] = (1.0 - alpha) * va.float() + alpha * vb.float()
                # 元 dtype に戻す
                merged[k] = merged[k].to(dtype=va.dtype)
                n_float += 1
            else:
                merged[k] = va
        else:
            merged[k] = va
    stats = {
        "n_merged_keys": len(merged),
        "n_float_tensors": n_float,
        "n_skipped_a_only": len(skipped_a),
        "n_skipped_b_only": len(skipped_b),
        "alpha": alpha,
    }
    return merged, stats


def merge_checkpoints(
    path_a: Path | str,
    path_b: Path | str,
    output: Path | str,
    *,
    alpha: float = 0.5,
) -> dict[str, Any]:
    """2 ckpt を線形マージして保存する。"""
    try:
        import torch
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "torch が必要です。親 Matsuo/robot .venv で実行してください:\n"
            "  PYTHONPATH=src:.. ../../.venv/bin/python -m parc.train.merge_ckpts ..."
        ) from exc

    a = _load_state_dict(Path(path_a))
    b = _load_state_dict(Path(path_b))
    merged, stats = linear_merge_state_dicts(a, b, alpha=alpha)
    out = _resolve(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == "" or out.is_dir() or not out.suffix:
        out.mkdir(parents=True, exist_ok=True)
        weight_path = out / "merged.pt"
        meta_path = out / "merge_meta.json"
    else:
        weight_path = out
        meta_path = out.with_suffix(".merge_meta.json")
    torch.save(merged, weight_path)
    meta = {
        "a": str(_resolve(path_a)),
        "b": str(_resolve(path_b)),
        "output": str(weight_path),
        **stats,
        "sidecar": True,
        "parent_ckpt_eligible": False,
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="parc-merge-ckpts",
        description="2 つの ckpt を線形マージする（CLAIR/APO サイドカー Phase4）。",
    )
    p.add_argument("--a", required=True, help="ckpt A（path or pretrained_model dir）")
    p.add_argument("--b", required=True, help="ckpt B")
    p.add_argument("--output", required=True, help="出力 .pt またはディレクトリ")
    p.add_argument("--alpha", type=float, default=0.5, help="θ=(1-α)A + αB")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    meta = merge_checkpoints(args.a, args.b, args.output, alpha=float(args.alpha))
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
