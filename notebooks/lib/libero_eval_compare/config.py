"""Configuration loading for baseline vs fine-tuned evaluation."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
# notebooks/lib/libero_eval_compare -> notebooks
NOTEBOOKS_DIR = PACKAGE_DIR.parent.parent
REPO_ROOT = NOTEBOOKS_DIR.parent
PROFILES_DIR = NOTEBOOKS_DIR / "configs" / "profiles"

SPATIAL_TASK_NAMES: list[str] = [
    "pick up the black bowl from table center and place it on the plate",
    "pick up the black bowl next to the cookie box and place it on the plate",
    "pick up the black bowl next to the plate and place it on the plate",
    "pick up the black bowl next to the ramekin and place it on the plate",
    "pick up the black bowl on the cookie box and place it on the plate",
    "pick up the black bowl on the ramekin and place it on the plate",
    "pick up the black bowl on the stove and place it on the plate",
    "pick up the black bowl on the wooden cabinet and place it on the plate",
    "pick up the black bowl in the top drawer of the wooden cabinet and place it on the plate",
    "pick up the black bowl between the plate and the ramekin and place it on the plate",
]

DEFAULT_CAMERA_MAPPING: dict[str, str] = {
    "agentview_image": "front",
    "robot0_eye_in_hand_image": "wrist",
}


@dataclass
class SuiteConfig:
    """Evaluation settings for one LIBERO suite."""

    task_ids: list[int]
    n_episodes: int = 1


@dataclass
class ModelConfig:
    """Policy directory and display label."""

    path: Path
    label: str


@dataclass
class CompareConfig:
    """Resolved evaluation profile used by runner and compare modules."""

    profile_name: str
    seed: int
    workdir: Path
    repo_root: Path
    lerobot_dir: Path
    libero_plus_dir: Path
    baseline: ModelConfig
    finetuned: ModelConfig
    suites: dict[str, SuiteConfig]
    camera_mapping: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_CAMERA_MAPPING))
    observation_height: int = 256
    observation_width: int = 256
    control_mode: str = "relative"
    policy_device: str = "cuda"
    spatial_task_names: list[str] = field(default_factory=lambda: list(SPATIAL_TASK_NAMES))
    sub_profiles: list[str] = field(default_factory=list)

    @property
    def lerobot_src(self) -> Path:
        return self.lerobot_dir / "src"

    @property
    def comparison_groups(self) -> list[str]:
        if self.sub_profiles:
            return self.sub_profiles
        return [self.profile_name]

    def make_run_dir(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return self.workdir / "eval" / "compare_runs" / f"{timestamp}_{self.profile_name}"

    def group_config(self, group_name: str) -> CompareConfig:
        """Return a single-group config derived from this profile."""
        if not self.sub_profiles:
            return self
        group_profile = load_profile(group_name, PROFILES_DIR)
        return CompareConfig(
            profile_name=group_name,
            seed=self.seed,
            workdir=self.workdir,
            repo_root=self.repo_root,
            lerobot_dir=self.lerobot_dir,
            libero_plus_dir=self.libero_plus_dir,
            baseline=self.baseline,
            finetuned=self.finetuned,
            suites=group_profile.suites,
            camera_mapping=self.camera_mapping,
            observation_height=self.observation_height,
            observation_width=self.observation_width,
            control_mode=self.control_mode,
            policy_device=self.policy_device,
            spatial_task_names=self.spatial_task_names,
        )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _resolve_path(raw: str | Path, repo_root: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _parse_suites(raw: dict[str, Any]) -> dict[str, SuiteConfig]:
    suites: dict[str, SuiteConfig] = {}
    for suite_name, suite_cfg in raw.items():
        suites[suite_name] = SuiteConfig(
            task_ids=[int(task_id) for task_id in suite_cfg["task_ids"]],
            n_episodes=int(suite_cfg.get("n_episodes", 1)),
        )
    return suites


def _build_compare_config(profile_name: str, raw: dict[str, Any]) -> CompareConfig:
    repo_root = REPO_ROOT
    if "repo_root" in raw:
        candidate = _resolve_path(raw["repo_root"], REPO_ROOT)
        if candidate.is_dir():
            repo_root = candidate
    workdir = _resolve_path(raw["workdir"], repo_root)
    models = raw["models"]
    return CompareConfig(
        profile_name=profile_name,
        seed=int(raw.get("seed", 2026)),
        workdir=workdir,
        repo_root=repo_root,
        lerobot_dir=_resolve_path(raw["paths"]["lerobot_dir"], repo_root),
        libero_plus_dir=_resolve_path(raw["paths"]["libero_plus_dir"], repo_root),
        baseline=ModelConfig(
            path=_resolve_path(models["baseline"]["path"], repo_root),
            label=str(models["baseline"].get("label", "Base (no LoRA FT)")),
        ),
        finetuned=ModelConfig(
            path=_resolve_path(models["finetuned"]["path"], repo_root),
            label=str(models["finetuned"].get("label", "Spatial LoRA")),
        ),
        suites=_parse_suites(raw["suites"]),
        camera_mapping=dict(raw.get("camera_mapping", DEFAULT_CAMERA_MAPPING)),
        observation_height=int(raw.get("observation_height", 256)),
        observation_width=int(raw.get("observation_width", 256)),
        control_mode=str(raw.get("control_mode", "relative")),
        policy_device=str(raw.get("policy_device", "cuda")),
        sub_profiles=[str(item) for item in raw.get("sub_profiles", [])],
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_profile(profile_name: str, profiles_dir: Path | None = None) -> CompareConfig:
    """Load and merge a named profile with default.yaml."""
    profiles_root = profiles_dir or PROFILES_DIR
    default_cfg = _load_yaml(profiles_root / "default.yaml")
    profile_path = profiles_root / f"{profile_name}.yaml"
    if not profile_path.is_file():
        available = sorted(p.stem for p in profiles_root.glob("*.yaml") if p.stem != "default")
        raise FileNotFoundError(
            f"Unknown profile '{profile_name}'. Available: {', '.join(available)}"
        )

    profile_cfg = _load_yaml(profile_path)
    sub_profiles = profile_cfg.pop("sub_profiles", [])
    merged = _deep_merge(default_cfg, profile_cfg)

    config = _build_compare_config(profile_name, merged)
    config.sub_profiles = [str(item) for item in sub_profiles]
    return config


def list_profiles(profiles_dir: Path | None = None) -> list[str]:
    """Return profile names excluding default.yaml."""
    profiles_root = profiles_dir or PROFILES_DIR
    return sorted(
        path.stem
        for path in profiles_root.glob("*.yaml")
        if path.stem != "default"
    )
