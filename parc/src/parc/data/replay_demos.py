"""保存 action を env で再生し、episode_quality に replay_* を追記する。"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from parc.data.verify_demos import load_quality_rows
from parc.env.success import is_libero_success
from parc.paths import PARC_ROOT
from parc.vr.recorder import QUALITY_JSONL_NAME


@dataclass
class ReplayResult:
    """1 エピソードのリプレイ結果。"""

    episode_index: int
    replay_success: bool
    replay_steps: int
    suite: str
    task_id: int
    init_state_index: int


def _resolve_root(path: str | Path) -> Path:
    """相対パスを parc ルート基準で解決する。"""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (PARC_ROOT / p).resolve()
    return p


def write_quality_rows(root: Path, rows: list[dict[str, Any]]) -> None:
    """quality jsonl を丸ごと書き戻す。"""
    path = root / "meta" / QUALITY_JSONL_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_episode_actions_from_lerobot(
    root: Path,
    episode_index: int,
    *,
    repo_id: str = "local/vr_libero_demos",
) -> list[np.ndarray]:
    """LeRobot dataset から指定エピソードの action 列を読む。"""
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    ds = LeRobotDataset(repo_id, root=root)
    # v3: episode 境界は meta.episodes
    ep_meta = ds.meta.episodes[episode_index]
    start = int(ep_meta["dataset_from_index"])
    end = int(ep_meta["dataset_to_index"])
    actions: list[np.ndarray] = []
    for i in range(start, end):
        item = ds[i]
        act = item["action"]
        actions.append(np.asarray(act, dtype=np.float64).reshape(-1))
    return actions


def replay_actions_on_env(
    env: Any,
    actions: Sequence[np.ndarray],
    *,
    init_states: Sequence[Any] | None = None,
    init_state_index: int = 0,
) -> ReplayResult:
    """actions を順に step し success を返す（結果の episode メタは呼び出し側で埋める）。"""
    env.reset()
    if init_states:
        i = int(init_state_index) % len(init_states)
        set_fn = getattr(env, "set_init_state", None)
        if callable(set_fn):
            set_fn(init_states[i])

    success = False
    steps = 0
    for action in actions:
        obs, reward, done, info = env.step(np.asarray(action, dtype=np.float64).tolist())
        steps += 1
        if is_libero_success(reward, done, info, env):
            success = True
        _ = obs
    return ReplayResult(
        episode_index=-1,
        replay_success=success,
        replay_steps=steps,
        suite="",
        task_id=-1,
        init_state_index=init_state_index,
    )


def update_quality_with_replay(
    rows: list[dict[str, Any]],
    episode_index: int,
    *,
    replay_success: bool,
    replay_steps: int,
) -> list[dict[str, Any]]:
    """指定 episode の quality 行に replay_* を追記したコピーを返す。"""
    out: list[dict[str, Any]] = []
    found = False
    for row in rows:
        r = dict(row)
        if r.get("episode_index") == episode_index:
            r["replay_success"] = bool(replay_success)
            r["replay_steps"] = int(replay_steps)
            found = True
        out.append(r)
    if not found:
        raise KeyError(f"episode_index={episode_index} not in quality jsonl")
    return out


def replay_demo_episode(
    root: Path | str,
    episode_index: int,
    *,
    repo_id: str = "local/vr_libero_demos",
    fake: bool = False,
    actions: Sequence[np.ndarray] | None = None,
    write: bool = True,
) -> ReplayResult:
    """1 エピソードを再生して quality に追記する。"""
    root_path = _resolve_root(root)
    rows = load_quality_rows(root_path)
    row = next((r for r in rows if r.get("episode_index") == episode_index), None)
    if row is None:
        raise KeyError(f"episode_index={episode_index} not found")

    suite = str(row.get("suite", "libero_spatial"))
    task_id = int(row.get("task_id", 0))
    init_idx = int(row.get("init_state_index", 0))

    if actions is None:
        if fake:
            raise ValueError("fake replay requires explicit actions=")
        actions = load_episode_actions_from_lerobot(
            root_path, episode_index, repo_id=repo_id
        )

    from parc.vr.env_factory import make_teleop_env

    bundle = make_teleop_env(suite, task_id, fake=fake)
    try:
        result = replay_actions_on_env(
            bundle.env,
            actions,
            init_states=list(bundle.init_states),
            init_state_index=init_idx,
        )
    finally:
        close = getattr(bundle.env, "close", None)
        if callable(close):
            close()

    result.episode_index = episode_index
    result.suite = suite
    result.task_id = task_id
    result.init_state_index = init_idx

    if write:
        updated = update_quality_with_replay(
            rows,
            episode_index,
            replay_success=result.replay_success,
            replay_steps=result.replay_steps,
        )
        write_quality_rows(root_path, updated)
    return result


def build_parser() -> argparse.ArgumentParser:
    """CLI パーサ。"""
    p = argparse.ArgumentParser(
        prog="parc-replay-demos",
        description="Replay saved demo actions in LIBERO env and annotate quality jsonl",
    )
    p.add_argument("--root", required=True, help="LeRobot dataset root")
    p.add_argument("--episode", type=int, required=True, help="episode_index")
    p.add_argument("--repo-id", default="local/vr_libero_demos")
    p.add_argument("--fake", action="store_true", help="FakeLiberoEnv で再生")
    p.add_argument(
        "--actions-json",
        default="",
        help="[[a0..], ...] 形式の action 列（--fake テスト用）",
    )
    p.add_argument("--dry-run", action="store_true", help="quality を書かない")
    return p


def main(argv: list[str] | None = None) -> None:
    """エントリポイント。"""
    from rich.console import Console

    console = Console()
    args = build_parser().parse_args(argv)
    actions = None
    if args.actions_json:
        raw = json.loads(Path(args.actions_json).read_text(encoding="utf-8"))
        actions = [np.asarray(a, dtype=np.float64) for a in raw]
    try:
        result = replay_demo_episode(
            args.root,
            args.episode,
            repo_id=args.repo_id,
            fake=args.fake,
            actions=actions,
            write=not args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]replay failed[/red]: {exc}")
        raise SystemExit(1) from exc
    console.print(
        f"[green]replay ok[/green] ep={result.episode_index} "
        f"success={result.replay_success} steps={result.replay_steps} "
        f"({asdict(result)})"
    )
