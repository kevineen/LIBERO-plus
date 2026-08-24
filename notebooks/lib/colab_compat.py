"""Local vs Colab environment helpers.

Course submission notebooks must stay self-contained (do not import this
module from submit/). Use this only from experiments/ notebooks or local
scripts, then copy the equivalent cells into the Colab notebook by hand.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_colab() -> bool:
    """Return True when running inside Google Colab."""
    if "google.colab" in sys.modules:
        return True
    return "COLAB_RELEASE_TAG" in os.environ


def setup_mujoco_egl() -> None:
    """Use EGL so MuJoCo can render without a display (Colab / headless GPU)."""
    os.environ.setdefault("MUJOCO_GL", "egl")


def resolve_workdir(repo_root: Path | None = None) -> Path:
    """Return the working directory used for models, eval, and caches.

    Colab uses /content/workdir. Locally this is <repo>/workdir.
    Optionally mounts Google Drive when Colab is detected.
    """
    if is_colab():
        try:
            from google.colab import drive  # type: ignore
        except ImportError:
            drive = None
        if drive is not None:
            drive.mount("/content/drive", force_remount=False)
        workdir = Path("/content/workdir")
    else:
        root = repo_root or Path(__file__).resolve().parents[2]
        workdir = root / "workdir"
    workdir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(workdir / "hf_cache"))
    os.environ.setdefault("HF_LEROBOT_HOME", str(workdir / "lerobot_cache"))
    return workdir


def notebooks_lib_on_path() -> Path:
    """Insert notebooks/lib on sys.path and return that directory."""
    lib_dir = Path(__file__).resolve().parent
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir))
    return lib_dir
