# VR Teleop（Quest 3 → LIBERO デモ収集）

Meta Quest 3 から LIBERO / LIBERO-plus を遠隔操作し、SmolVLA 学習互換の LeRobot データセットを作る機能。

## 現状

| 項目 | 状態 |
|------|------|
| Phase | 1 実装済み（Quest 実機 E2E は STATUS backlog） |
| 詳細 | [STATUS.md](STATUS.md) |

## ドキュメント

| ファイル | 内容 |
|----------|------|
| [design.md](design.md) | 設計の正本 |
| [plan.md](plan.md) | 実装タスク（チェックボックス） |
| [protocol.md](protocol.md) | WebSocket メッセージ仕様 |
| [STATUS.md](STATUS.md) | 進捗・バックログ |

運用手順（ビルド・起動）: [docs/12_vr_teleop.md](../../docs/12_vr_teleop.md)

## 最短起動（Phase 1）

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
# フェイク入力で録画スモーク（Quest 不要）
bash scripts/vr_teleop.sh --fake --suite libero_spatial --task-id 0

# Quest 待ち受け
bash scripts/vr_teleop.sh --host 0.0.0.0 --port 8765 \
  --suite libero_spatial --task-id 0 \
  --dataset-root data/datasets/vr_libero_demos
```

学習 YAML では `train.dataset_root` に上記パスを指定する。

## スコープ外（Phase 2+）

- 実機テレオプ
- ハンドトラッキング
- Unity 3D シーン同期
- パススルー人間動作 → ロボット軌道
