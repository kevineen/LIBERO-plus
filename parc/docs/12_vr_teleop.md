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

# 1) フェイク env（Quest / LIBERO 無しでプロトコル確認）
bash scripts/vr_teleop.sh --fake --host 0.0.0.0 --port 8765 --no-dataset

# 2) フェイク 1 エピソード書き込みスモーク（WS なし）
bash scripts/vr_teleop.sh --fake-episode --no-dataset \
  --dataset-root data/datasets/vr_libero_demos_smoke

# 3) 本番 LIBERO（親 LIBERO-plus/.venv）
USE_LIBERO_VENV=1 bash scripts/vr_teleop.sh --host 0.0.0.0 --port 8765 \
  --suite libero_spatial --task-id 0 \
  --dataset-root data/datasets/vr_libero_demos

# LeRobot 書き込みには robot venv（lerobot 入り）が必要:
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv \
  bash scripts/vr_teleop.sh --fake --host 0.0.0.0 --port 8765 \
  --dataset-root data/datasets/vr_libero_demos
```

CLI 直叩き: `uv run parc-vr-teleop --help`

### 主なオプション

| フラグ | 意味 |
|--------|------|
| `--fake` | ダミー env（画像は色バー） |
| `--fake-episode` | WS なしで 1 ep 書いて終了 |
| `--no-dataset` | ディスク書き込みスキップ |
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
# configs/experiments/ にコピーして使う例
train:
  backend: lerobot
  dataset_repo_id: local/vr_libero_demos
  dataset_root: data/datasets/vr_libero_demos
```

```bash
bash scripts/train.sh configs/experiments/<your_vr_ft>.yaml
```

スキーマは [`07_custom_data_and_algos.md`](07_custom_data_and_algos.md) と同じ（front/wrist/state8/action7/task）。

## 操作フロー

1. PC で `parc-vr-teleop` 起動 → Quest 接続 → `hello` / `task_info`
2. コントローラで EE を動かす（映像パネルで確認）
3. **A (record)** で録画開始
4. タスク完了後 **B (save)** でエピソード保存（失敗なら Grip で discard）
5. Menu で env reset

## トラブルシュート

| 症状 | 確認 |
|------|------|
| Quest が繋がらない | 同一 LAN・ファイアウォール・PC IP |
| 映像が来ない | `--fake` で色が変わるか。JPEG 品質を下げる |
| 保存されない | lerobot が入った venv か。`--no-dataset` になっていないか |
| 動きが過敏/鈍い | `ActionMapConfig`（今後 YAML 化予定）。とりあえずゆっくり動かす |
| Unity が WSL で開けない | Windows ホストでビルド |

## Phase 2+

実機・ハンドトラッキング・3D ビュー・パススルーは [`feature/vr-teleop/STATUS.md`](../feature/vr-teleop/STATUS.md) の backlog。
