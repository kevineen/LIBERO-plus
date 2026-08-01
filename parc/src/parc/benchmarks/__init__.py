"""汎用ベンチマーク枠（レジストリ＋アダプタ）。"""

from __future__ import annotations

from parc.benchmarks.base import BenchmarkBackend, DatasetSpec
from parc.benchmarks.registry import get_benchmark, list_benchmarks, register_benchmark

__all__ = [
    "BenchmarkBackend",
    "DatasetSpec",
    "get_benchmark",
    "list_benchmarks",
    "register_benchmark",
]
