# Design: VR Quest 3 Teleop Dataset Collection

**Approach:** A — `parc` 内蔵テレオプサーバ + 薄い Unity OpenXR クライアント  
**Date:** 2026-07-30  
**Phase 1 scope only**（拡張点は末尾）

## Goals

1. Quest 3 コントローラで LIBERO / LIBERO-plus タスクを操作する
2. **成功/失敗ラベル付き**エピソードを LeRobot Dataset **v3.0**（front / wrist / state8 / action7 / task）で保存する
3. 保存先をそのまま `train.sh` の `dataset_root` に使えるようにする
4. init_state（と任意の `task_ids`）を cycle し、単位コストあたりの多様な軌跡を増やす
5. `meta/collection_info.json` + `episode_quality.jsonl` + `episode_timestamps.jsonl` + `parc-verify-demos` で検証可能にする

## Architecture

```text
Quest3 Unity OpenXR  --WS JSON control-->  parc-vr-teleop (Python)
                     <--WS JPEG video---       |
                                               +-- OffScreenRenderEnv
                                               +-- LeRobotDataset writer
                                               +--> data/datasets/vr_libero_demos
```

### PC server (`parc.vr`)

- LIBERO `OffScreenRenderEnv` を生成・step
- コントローラ相対変位 → 相対 7D action（OSC_POSE 互換）
- agentview / wrist を JPEG 化し Quest へ配信
- 録画は PC 側のみ（学習スキーマと一致させるため）
- Save ゲート: `parc.env.success.is_libero_success`（eval と共有）
- 多様化: init_states cycle + 任意 `task_ids` round-robin
- 品質メタ: `meta/episode_quality.jsonl` / `meta/collection_stats.json`

### Quest client (`parc/unity/VrTeleop`)

- 右手コントローラ 6DoF → pose uplink
- トリガ → gripper
- A/B（または UI）→ record / save / discard / reset
- 受信 JPEG をワールド空間パネルに表示

## Observation / action schema

学習・評価と同一（`docs/07_custom_data_and_algos.md` / `lerobot_ckpt.py`）:

| Key | Shape | Notes |
|-----|-------|-------|
| `observation.images.front` | `(H,W,3)` uint8 | agentview |
| `observation.images.wrist` | `(H,W,3)` uint8 | eye-in-hand |
| `observation.state` | `(8,)` float32 | eef_pos(3)+axisangle(3)+gripper_qpos(2) |
| `action` | `(7,)` float32 | relative EE 6 + gripper |
| `task` | string | language instruction |

デフォルト `fps=20`、`robot_type=panda`。画像 flip は録画時に学習慣習（180°）へ合わせるオプションを持つ。

## Control mapping

絶対ポーズ IK は使わない。フレーム間のコントローラ相対変位をスケール・クリップして 7D にする。

- `dx,dy,dz`: 位置差分 × `pos_scale`、±`max_pos` でクリップ
- `dax,day,daz`: 相対回転を axis-angle × `rot_scale`、±`max_rot` でクリップ
- gripper: トリガ `[0,1]` → `[-1,1]`（開→閉）

最初のフレームは差分ゼロ（または idle）とし、前フレーム pose を保持する。

## Protocol

詳細は [protocol.md](protocol.md)。概略:

- Uplink ~20 Hz: pose + gripper + buttons
- Downlink: front/wrist JPEG binary frames + JSON セッションイベント
- セッション: `hello` / `task_info` / `episode_saved` / `error`

## Components (code)

| Path | Responsibility |
|------|----------------|
| `src/parc/vr/protocol.py` | メッセージ dataclass / encode-decode |
| `src/parc/vr/action_map.py` | pose delta → action7 |
| `src/parc/vr/obs_util.py` | LIBERO obs → images/state |
| `src/parc/vr/recorder.py` | LeRobot episode writer |
| `src/parc/vr/video.py` | RGB → JPEG bytes |
| `src/parc/vr/session.py` | env loop + recording state machine |
| `src/parc/vr/server.py` | WebSocket server |
| `scripts/vr_teleop.sh` | LIBERO venv で起動 |
| `unity/VrTeleop/` | OpenXR 薄クライアント |

## Non-goals (Phase 1)

- Unity 内 3D シーン同期
- ハンドトラッキング
- 実機ロボット
- パススルー人間動作変換
- WebRTC（遅延が問題になったら検討）

## Extension points (Phase 2+)

- `InputMode = controller | hand` を uplink に追加
- `Backend = sim | real` で session の env 差し替え
- 3D ビューは別チャネルでロボット関節・物体 pose を送る
- パススルーは別 recorder（人間骨格 → retarget → action）

## Risks

| Risk | Mitigation |
|------|------------|
| WSL では Unity/Quest ビルド不可 | Windows ホストで Unity、sim は Fleet 機 |
| 映像遅延 | JPEG 品質・解像度を下げる。必要なら WebRTC |
| action スケール不一致 | 設定で scale/clip。スモークで手動調整 |
| lerobot が parc 薄 venv に無い | `vr_teleop.sh` は親 LIBERO-plus / robot venv を使う |
