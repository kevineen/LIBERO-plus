"""実験ディレクトリのディスク予算。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from parc.paths import _load_paths_yaml, get_paths


@dataclass
class DiskBudget:
    """ディスク寿命管理の閾値。"""

    max_bytes: int
    keep_best: int = 5
    keep_last: int = 3
    protected_tags: list[str] = field(default_factory=lambda: ["protected", "baseline"])
    experiments_dir: Path | None = None

    @property
    def max_bytes_gb(self) -> float:
        return self.max_bytes / (1024**3)


def get_disk_budget(override: dict[str, Any] | None = None) -> DiskBudget:
    """paths.yaml の disk 節（と任意 override）から予算を構築する。"""
    cfg = _load_paths_yaml()
    disk = dict(cfg.get("disk") or {})
    if override:
        disk.update({k: v for k, v in override.items() if v is not None})

    max_gb = float(disk.get("max_bytes_gb", 80))
    exp_dir = get_paths()["experiments_dir"]
    if disk.get("experiments_dir"):
        exp_dir = Path(str(disk["experiments_dir"])).expanduser().resolve()

    return DiskBudget(
        max_bytes=int(max_gb * (1024**3)),
        keep_best=int(disk.get("keep_best", 5)),
        keep_last=int(disk.get("keep_last", 3)),
        protected_tags=[str(t) for t in (disk.get("protected_tags") or ["protected", "baseline"])],
        experiments_dir=exp_dir,
    )


def usage_bytes(root: Path) -> int:
    """ディレクトリ配下の合計バイト数（シンボリックは追わない）。"""
    if not root.exists():
        return 0
    total = 0
    for p in root.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def check_budget(budget: DiskBudget | None = None) -> dict[str, Any]:
    """予算内かどうかを返す。ok=False なら新規 train を拒否する材料。"""
    b = budget or get_disk_budget()
    root = b.experiments_dir or get_paths()["experiments_dir"]
    used = usage_bytes(root)
    return {
        "ok": used < b.max_bytes,
        "used_bytes": used,
        "max_bytes": b.max_bytes,
        "used_gb": round(used / (1024**3), 3),
        "max_gb": round(b.max_bytes / (1024**3), 3),
        "experiments_dir": str(root),
    }
