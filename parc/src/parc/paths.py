"""パス解決と環境変数の共通処理。"""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path
from typing import Any

import yaml

# parc/ ルート（src/parc/paths.py → parents[2]）
PARC_ROOT = Path(__file__).resolve().parents[2]
LIBERO_PLUS_ROOT = PARC_ROOT.parent

_DOTENV_LOADED = False


def load_dotenv_files(*, override: bool = False) -> list[Path]:
    """``.env`` / ``.env.local`` を読み環境変数へ載せる。

    既定は「未設定のキーだけ埋める」（シェルで export した値が勝つ）。
    ``.env.local`` が ``.env`` より後に読まれるのでローカル上書き向き。
    """
    global _DOTENV_LOADED
    loaded: list[Path] = []
    for name in (".env", ".env.local"):
        path = PARC_ROOT / name
        if not path.is_file():
            continue
        _apply_dotenv_file(path, override=override)
        loaded.append(path)
    _DOTENV_LOADED = True
    return loaded


def _apply_dotenv_file(path: Path, *, override: bool) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {'"', "'"}:
            val = val[1:-1]
        if not override and key in os.environ and os.environ[key] != "":
            continue
        os.environ[key] = val


def ensure_dotenv_loaded() -> None:
    """初回だけ dotenv を読む。"""
    if not _DOTENV_LOADED:
        load_dotenv_files(override=False)


def _load_paths_yaml() -> dict[str, Any]:
    """configs/paths.yaml があれば読む（無ければ空）。

    注意: paths.yaml が無いとき example を読むのは初回セットアップ用。
    本番では必ずローカル paths.yaml を置くか、``.env.local`` で上書きする。
    """
    ensure_dotenv_loaded()
    path = PARC_ROOT / "configs" / "paths.yaml"
    if not path.is_file():
        example = PARC_ROOT / "configs" / "paths.example.yaml"
        if example.is_file():
            with example.open() as f:
                return yaml.safe_load(f) or {}
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}


def get_machine_id() -> str:
    """複数 PC 識別子。PARC_MACHINE_ID → paths.yaml machine_id → hostname 短縮。"""
    ensure_dotenv_loaded()
    env = (os.environ.get("PARC_MACHINE_ID") or "").strip()
    if env:
        return _sanitize_machine_id(env)
    cfg = _load_paths_yaml()
    from_cfg = cfg.get("machine_id")
    if from_cfg not in (None, "null", ""):
        return _sanitize_machine_id(str(from_cfg))
    host = socket.gethostname().split(".")[0]
    return _sanitize_machine_id(host or "host")


def _sanitize_machine_id(raw: str) -> str:
    """run_id に埋め込み可能な短い ID にする。"""
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", raw.strip())[:24]
    return safe or "host"


def get_paths() -> dict[str, Path]:
    """実験・データ・リポジトリ根のパス辞書を返す。"""
    ensure_dotenv_loaded()
    cfg = _load_paths_yaml()

    def resolve(key: str, default: Path, env: str | None = None) -> Path:
        if env and os.environ.get(env):
            return Path(os.environ[env]).expanduser().resolve()
        val = cfg.get(key)
        if val in (None, "null"):
            return default.resolve()
        p = Path(str(val)).expanduser()
        if not p.is_absolute():
            p = (PARC_ROOT / p).resolve()
        return p

    experiments_dir = resolve(
        "experiments_dir", PARC_ROOT / "experiments", "PARC_EXPERIMENTS_DIR"
    )
    data_dir = resolve("data_dir", PARC_ROOT / "data", "PARC_DATA_DIR")
    libero_root = resolve(
        "libero_plus_root", LIBERO_PLUS_ROOT, "PARC_LIBERO_PLUS_ROOT"
    )

    return {
        "parc_root": PARC_ROOT,
        "libero_plus_root": libero_root,
        "experiments_dir": experiments_dir,
        "data_dir": data_dir,
        "datasets_dir": data_dir / "datasets",
        "checkpoints_dir": data_dir / "checkpoints",
        "classification_json": libero_root
        / "libero"
        / "libero"
        / "benchmark"
        / "task_classification.json",
    }


def apply_runtime_env() -> None:
    """MuJoCo / HF / PYTHONPATH などランタイム環境変数をセットする。"""
    import sys

    ensure_dotenv_loaded()
    cfg = _load_paths_yaml()
    mujoco_gl = os.environ.get("MUJOCO_GL") or cfg.get("mujoco_gl") or "egl"
    os.environ.setdefault("MUJOCO_GL", str(mujoco_gl))
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    hf_home = os.environ.get("HF_HOME") or cfg.get("hf_home")
    if hf_home not in (None, "null"):
        os.environ["HF_HOME"] = str(Path(str(hf_home)).expanduser())

    paths = get_paths()
    # editable インストールが効かない環境向けにリポジトリ根を sys.path へ
    root = str(paths["libero_plus_root"])
    if root not in sys.path:
        sys.path.insert(0, root)

    paths["experiments_dir"].mkdir(parents=True, exist_ok=True)
    paths["datasets_dir"].mkdir(parents=True, exist_ok=True)
    paths["checkpoints_dir"].mkdir(parents=True, exist_ok=True)
