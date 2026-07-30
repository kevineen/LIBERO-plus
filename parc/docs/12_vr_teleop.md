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

## Quest クライアント

手順は [`unity/VrTeleop/README.md`](../unity/VrTeleop/README.md)。

要点:

1. Windows で Unity プロジェクトを作成し `Assets/Scripts` をコピー
2. NativeWebSocket + OpenXR (Meta Quest)
3. `Server Url` = `ws://<PCのLAN IP>:8765`（`localhost` 不可）
4. A=Record / B=Save / Grip=Discard / Menu=Reset / Trigger=Gripper

## 学習への接続

```yaml
train:
  backend: lerobot
  dataset_repo_id: local/vr_libero_demos
  dataset_root: data/datasets/vr_libero_demos
```

```bash
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv bash scripts/vr_teleop.sh --config configs/vr/quest3_libero_spatial_task0.yaml
bash scripts/train.sh configs/experiments/smolvla_ft_vr_demos_smoke.yaml
./scripts/parc.sh eval -c configs/experiments/subset_eval.yaml
```

スキーマは [`07_custom_data_and_algos.md`](07_custom_data_and_algos.md) と同じ（front/wrist/state8/action7/task）。

## 操作フロー

1. PC で `parc-vr-teleop` 起動 → Quest 接続 → `hello` / `task_info`
2. コントローラで EE を動かす（映像パネルで確認）
3. **A (record)** で録画開始
4. タスク完了後 **B (save)** でエピソード保存（失敗なら Grip で discard）
5. Menu で env reset

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
