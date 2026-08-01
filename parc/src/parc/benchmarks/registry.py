"""ベンチマークレジストリ（parc 側。libero.benchmark とは別）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Type

if TYPE_CHECKING:
    from parc.benchmarks.base import BenchmarkBackend

_BENCHMARK_MAPPING: dict[str, Type[BenchmarkBackend]] = {}


def register_benchmark(target_class: Type[BenchmarkBackend]) -> Type[BenchmarkBackend]:
    """``BenchmarkBackend`` サブクラスを名前で登録する（大文字小文字無視）。"""
    key = str(getattr(target_class, "name", "") or target_class.__name__).lower()
    if not key:
        raise ValueError(f"BenchmarkBackend.name が空です: {target_class!r}")
    _BENCHMARK_MAPPING[key] = target_class
    return target_class


def get_benchmark(name: str) -> Type[BenchmarkBackend]:
    """登録済みバックエンドクラスを返す。"""
    # 遅延 import で組み込みアダプタを登録
    from parc.benchmarks import libero as _libero  # noqa: F401
    from parc.benchmarks import metaworld_mt50 as _mt50  # noqa: F401

    key = name.lower().strip()
    if key not in _BENCHMARK_MAPPING:
        known = ", ".join(sorted(_BENCHMARK_MAPPING)) or "(none)"
        raise KeyError(f"Unknown benchmark backend: {name!r}. Known: {known}")
    return _BENCHMARK_MAPPING[key]


def list_benchmarks() -> list[str]:
    """登録名一覧（アダプタをロードしたうえで）。"""
    get_benchmark("libero")  # 登録副作用
    return sorted(_BENCHMARK_MAPPING.keys())
