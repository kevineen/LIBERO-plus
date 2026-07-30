# VR Teleop Next Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quest 実機で 1 本の LIBERO デモを `data/datasets/vr_libero_demos/` に保存し、そのデータで VR 用 smoke FT を起動できるようにする。

**Architecture:** 既存の `parc-vr-teleop` を土台に、操作感パラメータを `ActionMapConfig` から YAML へ出し、Quest 実機で使う起動設定を `configs/vr/` に固定する。実機 E2E は `feature/vr-teleop/STATUS.md` に記録し、学習接続は `configs/experiments/smolvla_ft_vr_demos_smoke.yaml` と検証コマンドで再現可能にする。

**Tech Stack:** Python 3.10+, `pyyaml`, `numpy`, `websockets`, LIBERO `OffScreenRenderEnv`, LeRobot dataset v3, Unity OpenXR / NativeWebSocket

---

## File Structure

| Path | Responsibility |
|------|----------------|
| `src/parc/vr/config.py` | VR セッション設定 YAML のロードと型定義 |
| `src/parc/vr/action_map.py` | `ActionMapConfig` の dict/YAML 変換追加 |
| `src/parc/vr/cli_main.py` | `--config` 読み込み、CLI と YAML のマージ |
| `src/parc/vr/session.py` | 保存後メタ情報、実機 E2E で必要な状態通知の整備 |
| `src/parc/vr/recorder.py` | 保存後の dataset 検証で読むメタ補助 |
| `configs/vr/quest3_libero_spatial_task0.yaml` | Quest 実機向けの正本設定 |
| `configs/vr/fake_smoke.yaml` | フェイク動作確認用設定 |
| `configs/experiments/smolvla_ft_vr_demos_smoke.yaml` | 実機保存データを使う smoke FT |
| `tests/test_vr_config.py` | YAML 読み込みと CLI マージのテスト |
| `tests/test_vr_obs_and_session.py` | 保存後通知と状態更新の回帰テスト |
| `docs/12_vr_teleop.md` | 実機 1 本から smoke FT までの正式手順 |
| `feature/vr-teleop/STATUS.md` | 実機確認結果、詰まり、次の改善 |

---

### Task 1: YAML ベースの VR セッション設定を追加する

**Files:**
- Create: `parc/src/parc/vr/config.py`
- Modify: `parc/src/parc/vr/action_map.py`
- Modify: `parc/src/parc/vr/cli_main.py`
- Create: `parc/tests/test_vr_config.py`

- [ ] **Step 1: `ActionMapConfig` の YAML 入出力を先にテストで定義する**

```python
from pathlib import Path

from parc.vr.config import load_vr_config


def test_load_vr_config_reads_action_map(tmp_path: Path) -> None:
    cfg = tmp_path / "quest.yaml"
    cfg.write_text(
        \"\"\"
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
\"\"\".strip()
    )

    loaded = load_vr_config(cfg)

    assert loaded["suite"] == "libero_spatial"
    assert loaded["action_map"]["pos_scale"] == 0.7
    assert loaded["action_map"]["max_rot"] == 0.35
```

- [ ] **Step 2: 失敗を確認する**

Run: `cd /home/kevin/Matsuo/robot/LIBERO-plus/parc && uv run pytest tests/test_vr_config.py::test_load_vr_config_reads_action_map -v`

Expected: `ModuleNotFoundError: No module named 'parc.vr.config'` または `ImportError`

- [ ] **Step 3: `config.py` と `ActionMapConfig` の変換メソッドを最小実装する**

```python
# src/parc/vr/config.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_vr_config(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError("VR config must be a mapping")
    return raw
```

```python
# src/parc/vr/action_map.py
@dataclass
class ActionMapConfig:
    pos_scale: float = 1.0
    rot_scale: float = 1.0
    max_pos: float = 0.05
    max_rot: float = 0.5

    @classmethod
    def from_mapping(cls, raw: dict[str, float] | None) -> "ActionMapConfig":
        data = raw or {}
        return cls(
            pos_scale=float(data.get("pos_scale", 1.0)),
            rot_scale=float(data.get("rot_scale", 1.0)),
            max_pos=float(data.get("max_pos", 0.05)),
            max_rot=float(data.get("max_rot", 0.5)),
        )
```

- [ ] **Step 4: `cli_main.py` に `--config` を追加し、CLI 値で上書きする**

```python
p.add_argument("--config", default="", help="configs/vr/*.yaml")
```

```python
raw_cfg = load_vr_config(args.config) if args.config else {}
suite = str(raw_cfg.get("suite", args.suite))
task_id = int(raw_cfg.get("task_id", args.task_id))
dataset_root = _resolve_root(raw_cfg.get("dataset_root", args.dataset_root))
action_map = ActionMapConfig.from_mapping(raw_cfg.get("action_map"))
```

- [ ] **Step 5: テストを通す**

Run: `cd /home/kevin/Matsuo/robot/LIBERO-plus/parc && uv run pytest tests/test_vr_config.py -q`

Expected: `1 passed` 以上

- [ ] **Step 6: コミット**

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus
git add parc/src/parc/vr/config.py parc/src/parc/vr/action_map.py parc/src/parc/vr/cli_main.py parc/tests/test_vr_config.py
git commit -m "feat: add yaml config for vr teleop sessions"
```

---

### Task 2: Quest 実機向けの正本設定ファイルを追加する

**Files:**
- Create: `parc/configs/vr/quest3_libero_spatial_task0.yaml`
- Create: `parc/configs/vr/fake_smoke.yaml`
- Modify: `parc/docs/12_vr_teleop.md`

- [ ] **Step 1: 実機とフェイク用の設定ファイルを作る**

```yaml
# parc/configs/vr/quest3_libero_spatial_task0.yaml
host: 0.0.0.0
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
```

```yaml
# parc/configs/vr/fake_smoke.yaml
host: 127.0.0.1
port: 8765
suite: libero_spatial
task_id: 0
dataset_root: /tmp/vr_smoke
repo_id: local/vr_libero_demos
fps: 20
jpeg_quality: 70
camera_height: 64
camera_width: 64
image_size: 64
flip_images: true
action_map:
  pos_scale: 1.0
  rot_scale: 1.0
  max_pos: 0.05
  max_rot: 0.5
```

- [ ] **Step 2: 新しい起動コマンドを docs に書く**

```bash
bash scripts/vr_teleop.sh --config configs/vr/fake_smoke.yaml --fake --no-dataset
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv \
  bash scripts/vr_teleop.sh --config configs/vr/quest3_libero_spatial_task0.yaml
```

- [ ] **Step 3: CLI ヘルプと設定ファイルの存在を確認する**

Run: `cd /home/kevin/Matsuo/robot/LIBERO-plus/parc && uv run parc-vr-teleop --help`

Expected: `--config` が表示される

- [ ] **Step 4: コミット**

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus
git add parc/configs/vr/quest3_libero_spatial_task0.yaml parc/configs/vr/fake_smoke.yaml parc/docs/12_vr_teleop.md
git commit -m "docs: add canonical vr teleop session configs"
```

---

### Task 3: LeRobot 永続化の本番確認を自動チェックできるようにする

**Files:**
- Modify: `parc/src/parc/vr/recorder.py`
- Modify: `parc/src/parc/vr/session.py`
- Modify: `parc/tests/test_vr_obs_and_session.py`
- Create: `parc/tests/test_vr_recorder_meta.py`

- [ ] **Step 1: 保存後に最低限の dataset メタが確認できるテストを書く**

```python
from pathlib import Path

from parc.vr.session import run_fake_episode


def test_fake_episode_writes_meta_when_dataset_enabled(tmp_path: Path) -> None:
    try:
        import lerobot  # noqa: F401
    except ImportError:
        return

    written = run_fake_episode(
        dataset_root=tmp_path,
        num_frames=4,
        create_dataset=True,
        image_size=(32, 32),
    )

    assert written == 1
    assert (tmp_path / "meta" / "info.json").is_file()
```

- [ ] **Step 2: 保存成功時に `meta/info.json` と episode 数を返す補助を実装する**

```python
# src/parc/vr/recorder.py
def dataset_summary(self) -> dict[str, object]:
    return {
        "root": str(self.root),
        "meta_exists": (self.root / "meta" / "info.json").is_file(),
        "episode_count": self._episode_count,
    }
```

```python
# src/parc/vr/session.py
summary = self.recorder.dataset_summary()
self.emit_status(
    f"saved meta={summary['meta_exists']} episodes={summary['episode_count']}"
)
```

- [ ] **Step 3: テストを通す**

Run: `cd /home/kevin/Matsuo/robot/LIBERO-plus/parc && uv run pytest tests/test_vr_obs_and_session.py tests/test_vr_recorder_meta.py -q`

Expected: `passed`。`lerobot` が無い環境では meta テストは skip 相当

- [ ] **Step 4: robot venv でフェイク保存を実行してメタを確認する**

Run:

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv \
  bash scripts/vr_teleop.sh --fake-episode --config configs/vr/fake_smoke.yaml
ls data/datasets/vr_libero_demos/meta
```

Expected: `info.json` などのメタファイルが見える

- [ ] **Step 5: コミット**

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus
git add parc/src/parc/vr/recorder.py parc/src/parc/vr/session.py parc/tests/test_vr_obs_and_session.py parc/tests/test_vr_recorder_meta.py
git commit -m "feat: verify vr dataset persistence metadata"
```

---

### Task 4: 実機 1 本から smoke FT までの運用導線を固める

**Files:**
- Modify: `parc/configs/experiments/smolvla_ft_vr_demos_smoke.yaml`
- Modify: `parc/docs/12_vr_teleop.md`
- Modify: `parc/feature/vr-teleop/STATUS.md`

- [ ] **Step 1: VR 用 smoke FT の前提をコメントではなく手順として明記する**

```yaml
name: smolvla_ft_vr_demos_smoke
seed: 0
tags: [smolvla, ft, vr, smoke]

train:
  backend: lerobot
  policy_type: smolvla
  dataset_repo_id: local/vr_libero_demos
  dataset_root: data/datasets/vr_libero_demos
  steps: 200
  batch_size: 4
  num_workers: 2
```

`docs/12_vr_teleop.md` には次の 3 行をそのまま置く:

```bash
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv bash scripts/vr_teleop.sh --config configs/vr/quest3_libero_spatial_task0.yaml
bash scripts/train.sh configs/experiments/smolvla_ft_vr_demos_smoke.yaml
./scripts/parc.sh eval -c configs/experiments/subset_eval.yaml
```

- [ ] **Step 2: `STATUS.md` に実機 1 本確認欄を追加する**

```md
## Sprint C acceptance

- [ ] Quest 実機で 1 episode saved
- [ ] `meta/info.json` を確認
- [ ] `smolvla_ft_vr_demos_smoke.yaml` が起動
- [ ] 操作感パラメータを YAML で調整
```

- [ ] **Step 3: 実機未接続でも文書だけは完成させる**

Run: `cd /home/kevin/Matsuo/robot/LIBERO-plus/parc && uv run pytest tests/test_vr_*.py -q`

Expected: 全 VR テストが PASS

- [ ] **Step 4: コミット**

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus
git add parc/configs/experiments/smolvla_ft_vr_demos_smoke.yaml parc/docs/12_vr_teleop.md parc/feature/vr-teleop/STATUS.md
git commit -m "docs: define vr e2e and smoke training flow"
```

---

### Task 5: スプリント結果を feature に記録し、次の Phase 2 へ橋渡しする

**Files:**
- Modify: `parc/feature/vr-teleop/README.md`
- Modify: `parc/feature/vr-teleop/STATUS.md`
- Modify: `parc/strategy/03_next_actions.md`

- [ ] **Step 1: 実行結果を `STATUS.md` に具体的に記録する**

```md
- Quest E2E result: success / blocked
- Host machine: <winpc or local>
- Dataset root checked: <path>
- Smoke FT run_id: <run_id or not run>
- Next blocker: <one line>
```

- [ ] **Step 2: `README.md` に次スプリント計画へのリンクを残す**

```md
| [next-sprint-plan.md](next-sprint-plan.md) | 次スプリント（実機1本 + 最低限の運用整備）の実装計画 |
```

- [ ] **Step 3: `strategy/03_next_actions.md` の VR 行を完了/継続に更新する**

```md
- [x] Quest 実機でデモ 1 本 → `data/datasets/vr_libero_demos` → smoke FT
```

または未完なら:

```md
- [ ] Quest 実機でデモ 1 本 → `data/datasets/vr_libero_demos` → smoke FT
  - blocked: Windows/Quest/robot venv のどこで止まったかを 1 行で書く
```

- [ ] **Step 4: コミット**

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus
git add parc/feature/vr-teleop/README.md parc/feature/vr-teleop/STATUS.md parc/strategy/03_next_actions.md
git commit -m "docs: record vr next sprint outcomes"
```
