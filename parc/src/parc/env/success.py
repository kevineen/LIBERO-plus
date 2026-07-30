"""LIBERO / LIBERO-plus の成功判定（eval と VR teleop で共有）。"""

from __future__ import annotations

from typing import Any, Mapping


def is_libero_success(
    reward: float,
    done: bool,
    info: Mapping[str, Any] | None = None,
    env: Any = None,
) -> bool:
    """done / reward / info.success / env.check_success のいずれかが真なら成功。

    LIBERO 実装差を吸収するため、評価ランナーと同じ OR ロジックを使う。
    """
    info = info or {}
    if bool(done) or float(reward) > 0.5 or bool(info.get("success", False)):
        return True
    check = getattr(env, "check_success", None)
    if callable(check) and bool(check()):
        return True
    return False
