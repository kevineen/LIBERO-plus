# 12. VR Teleop（Quest 3 → LIBERO デモ）

Meta Quest 3 で LIBERO / LIBERO-plus を遠隔操作し、LeRobot v3 デモを収集する。  
設計・進捗の正本: [`feature/vr-teleop/`](../feature/vr-teleop/)

## 構成

```text
Quest (Unity OpenXR)  --WS-->  parc-vr-teleop (PC)
                               ├─ OffScreenRenderEnv / FakeEnv
                               └─ data/datasets/vr_libero_demos  (LeRobot)
```

## PC サーバ

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc

# 1) CLI オプション確認
uv run parc-vr-teleop --help

# 2) フェイク env（Quest / LIBERO 無しでプロトコル確認）
bash scripts/vr_teleop.sh --config configs/vr/fake_smoke.yaml --fake --no-dataset

# 3) フェイク 1 エピソード書き込みスモーク（WS なし）
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv \
  bash scripts/vr_teleop.sh --fake-episode --config configs/vr/fake_smoke.yaml

# 4) Quest 実機待ち受け + LeRobot 書き込み
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv \
  bash scripts/vr_teleop.sh --config configs/vr/quest3_libero_spatial_task0.yaml
```

`--config` で `configs/vr/*.yaml` を読み、必要なら CLI フラグで一部だけ上書きできる。

### 主なオプション

| フラグ | 意味 |
|--------|------|
| `--fake` | ダミー env（画像は色バー） |
| `--fake-episode` | WS なしで 1 ep 書いて終了 |
| `--no-dataset` | ディスク書き込みスキップ |
| `--config` | `configs/vr/*.yaml` を読み込む |
| `--suite` / `--task-id` | LIBERO タスク |
| `--image-size` | 録画解像度（既定 256） |
| `--jpeg-quality` | ストリーム品質 |
| `--no-flip-images` | 学習用 180° flip をオフ |
| `--require-success` | 未成功の Save を拒否（既定は失敗も保存） |
| `--operator-id` / `--device-id` / `--location` | 収集メタ |
| `--calib-override` | カメラ校正上書き JSON |

YAML 追加キー: `require_success`（既定 false）、`init_state_mode: cycle`、`task_ids`、`operator_id` / `device_id` / `location`、`calib_override_path`。

## Quest クライアント

**セットアップ正本（Quest 本体〜Unity〜WSL portproxy）:** [`13_quest3_setup.md`](13_quest3_setup.md)  
Unity 短メモ: [`unity/VrTeleop/README.md`](../unity/VrTeleop/README.md)

要点:

1. Windows で Unity プロジェクトを作成し `Assets/Scripts` をコピー
2. NativeWebSocket + OpenXR (Meta Quest) + Define `NATIVE_WEBSOCKET`
3. `Server Url` = `ws://<WindowsのLAN IP>:8765`（`localhost` 不可。WSL サーバ時は portproxy）
4. A=Record / B=Save / Grip=Discard / Menu=Reset / Trigger=Gripper

## 学習への接続

**方針:** 失敗エピソードは分析用に混在 DS へ残す。学習 baseline は **success-only subset** を使う。

```bash
# 1) 混在 DS → 成功だけ物理 subset
uv run parc-filter-demos \
  --root data/datasets/vr_libero_demos \
  --output data/datasets/vr_libero_demos_success \
  --success-only --overwrite

# 2) success-only で smoke FT
bash scripts/train.sh configs/experiments/smolvla_ft_vr_demos_success_smoke.yaml
./scripts/parc.sh eval -c configs/experiments/subset_eval.yaml
```

混在直読み（デバッグ用）:

```yaml
train:
  backend: lerobot
  dataset_repo_id: local/vr_libero_demos
  dataset_root: data/datasets/vr_libero_demos
```

```bash
bash scripts/train.sh configs/experiments/smolvla_ft_vr_demos_smoke.yaml
```

スキーマは [`07_custom_data_and_algos.md`](07_custom_data_and_algos.md) と同じ（front/wrist/state8/action7/task）。

## 操作フロー

1. PC で `parc-vr-teleop` 起動 → Quest 接続 → `hello` / `task_info`
2. コントローラで EE を動かす（映像パネルで確認）
3. **A (record)** で録画開始
4. **B (save)** でエピソード保存（既定は失敗も保存。`require_success: true` で未成功拒否）
5. Menu で env reset（init_state cycle、または `collection_queue` 消化）

## 品質ゲート

- 既定は **成功/失敗どちらも Save 可**（`success` フラグを必ず記録）。厳格化は `require_success: true` / `--require-success`
- 形式は **LeRobot Dataset v3.0**（`timestamp` は LeRobot が `frame_index/fps` で自動付与。制御時刻はサイドカー）
- `meta/collection_info.json` … カメラ名/解像度/座標系・収集メタ（差し替えは `calib_override_path`）
- `meta/episode_quality.jsonl` … success / task / fps / operator / RTT / category / replay_* 等
- `meta/episode_timestamps.jsonl` … v3 timestamps + control_timestamps（Approximate Time）
- YAML 追加: `max_rtt_ms` / `latency_policy`（`degraded`|`refuse`）/ `approx_time_slop_ms` / `collection_queue`

```bash
uv run parc-verify-demos --root data/datasets/vr_libero_demos
uv run parc-verify-demos --root data/datasets/vr_libero_demos --require-success-only
uv run parc-verify-demos --root data/datasets/vr_libero_demos --coverage --require-coverage-min 2

# 成功だけ物理 subset → 学習
uv run parc-filter-demos --root data/datasets/vr_libero_demos \
  --output data/datasets/vr_libero_demos_success --success-only --overwrite
bash scripts/train.sh configs/experiments/smolvla_ft_vr_demos_success_smoke.yaml

# action リプレイ検証（LeRobot 実 DS）
uv run parc-replay-demos --root data/datasets/vr_libero_demos --episode 0
uv run parc-verify-demos --root data/datasets/vr_libero_demos --require-replay-success
```

収集キュー例: [`configs/vr/collection_queue.example.yaml`](../configs/vr/collection_queue.example.yaml)  
VR YAML で `collection_queue: configs/vr/collection_queue.example.yaml` を指定すると Reset/成功 Save で消化し、Status に `queue_remaining` が出る。

## action_map 調整

`configs/vr/*.yaml` の `action_map` で操作感を変える。Quest 正本の初期値:

| キー | 意味 | `quest3_libero_spatial_task0` |
|------|------|-------------------------------|
| `pos_scale` | 位置差分の倍率 | `0.7` |
| `rot_scale` | 回転差分の倍率 | `1.0` |
| `max_pos` | 1 step の位置クリップ (m) | `0.03` |
| `max_rot` | 1 step の回転クリップ (rad) | `0.35` |

過敏なら `pos_scale` / `max_pos` を下げ、鈍ければ少し上げる。変更後は同じ `--config` で再起動するだけでよい。

## トラブルシュート

| 症状 | 確認 |
|------|------|
| Quest が繋がらない | 同一 LAN・ファイアウォール・PC IP |
| 映像が来ない | `--fake` で色が変わるか。JPEG 品質を下げる |
| 保存されない | `PARC_ROBOT_VENV` と `meta/info.json` を確認。`--no-dataset` になっていないか |
| 動きが過敏/鈍い | `configs/vr/*.yaml` の `action_map` を調整 |
| Unity が WSL で開けない | Windows ホストでビルド |

## Phase 2+

実機・ハンドトラッキング・3D ビュー・パススルーは [`feature/vr-teleop/STATUS.md`](../feature/vr-teleop/STATUS.md) の backlog。
