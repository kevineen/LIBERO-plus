"""VR teleop YAML 設定の単体テスト。"""

from __future__ import annotations

from pathlib import Path

from parc.vr.cli_main import build_parser, resolve_runtime_args
from parc.vr.config import load_vr_config


def test_load_vr_config_reads_action_map(tmp_path: Path) -> None:
    cfg = tmp_path / "quest.yaml"
    cfg.write_text(
        """
host: 0.0.0.0
port: 8765
suite: libero_spatial
task_id: 0
dataset_root: data/datasets/vr_libero_demos
fps: 20
jpeg_quality: 70
image_size: 256
action_map:
  pos_scale: 0.7
  rot_scale: 1.2
  max_pos: 0.03
  max_rot: 0.35
""".strip(),
        encoding="utf-8",
    )

    loaded = load_vr_config(cfg)

    assert loaded["suite"] == "libero_spatial"
    assert loaded["action_map"]["pos_scale"] == 0.7
    assert loaded["action_map"]["max_rot"] == 0.35


def test_resolve_runtime_args_prefers_yaml_and_cli_flags(tmp_path: Path) -> None:
    cfg = tmp_path / "quest.yaml"
    cfg.write_text(
        """
host: 127.0.0.1
port: 8765
suite: libero_spatial
task_id: 0
dataset_root: data/datasets/vr_libero_demos
repo_id: local/vr_libero_demos
fps: 20
jpeg_quality: 65
camera_height: 128
camera_width: 128
image_size: 256
flip_images: true
action_map:
  pos_scale: 0.7
  rot_scale: 1.0
  max_pos: 0.03
  max_rot: 0.35
""".strip(),
        encoding="utf-8",
    )

    parser = build_parser()
    args = parser.parse_args(
        [
            "--config",
            str(cfg),
            "--host",
            "0.0.0.0",
            "--task-id",
            "4",
            "--jpeg-quality",
            "80",
            "--no-flip-images",
        ]
    )

    runtime = resolve_runtime_args(args)

    assert runtime["host"] == "0.0.0.0"
    assert runtime["task_id"] == 4
    assert runtime["jpeg_quality"] == 80
    assert runtime["flip_images"] is False
    assert runtime["action_map"].pos_scale == 0.7
