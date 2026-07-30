# VR Teleop（Quest 3 → LIBERO デモ収集）

Meta Quest 3 から LIBERO / LIBERO-plus を遠隔操作し、SmolVLA 学習互換の LeRobot データセットを作る機能。

## 現状

| 項目 | 状態 |
|------|------|
| Phase 1 | 実装済み（fake / pytest） |
| データ品質 M1–M4 | **ソフト完了**（filter / RTT / queue / replay / Approx Time） |
| M0 Quest 実機 E2E | **blocked**（Windows + Headset） |
| 詳細 | [STATUS.md](STATUS.md) / [roadmap-data-quality.md](roadmap-data-quality.md) |

## ドキュメント

| ファイル | 内容 |
|----------|------|
| [design.md](design.md) | 設計の正本 |
| [done/phase1-plan.md](done/phase1-plan.md) | 完了済みの Phase 1 実装計画 |
| [next-sprint-plan.md](next-sprint-plan.md) | Sprint C: Quest 実機 1 本 + 運用整備 |
| [roadmap-data-quality.md](roadmap-data-quality.md) | **データ品質・スケーリング改善ロードマップ** |
| [protocol.md](protocol.md) | WebSocket メッセージ仕様 |
| [STATUS.md](STATUS.md) | 進捗・バックログ |

運用手順（ビルド・起動・success-only 学習）: [docs/12_vr_teleop.md](../../docs/12_vr_teleop.md)

## 最短起動（Phase 1）

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
# フェイク env（Quest / LIBERO 無し）
bash scripts/vr_teleop.sh --config configs/vr/fake_smoke.yaml --fake --no-dataset

# Quest 待ち受け + LeRobot 書き込み（robot venv）
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv \
  bash scripts/vr_teleop.sh --config configs/vr/quest3_libero_spatial_task0.yaml

# 品質検証・success-only subset・リプレイ
uv run parc-verify-demos --root data/datasets/vr_libero_demos --coverage
uv run parc-filter-demos --root data/datasets/vr_libero_demos \
  --output data/datasets/vr_libero_demos_success --success-only --overwrite
uv run parc-replay-demos --root data/datasets/vr_libero_demos --episode 0
```

正本設定: `configs/vr/`。詳細手順・smoke FT: [docs/12_vr_teleop.md](../../docs/12_vr_teleop.md)。

## スコープ外（Phase 2+）

- 実機テレオプ
- ハンドトラッキング
- Unity 3D シーン同期
- パススルー人間動作 → ロボット軌道
- LIBERO-plus 物理摂動エンジンの収集時適用（現状はカテゴリラベル＋init/task キュー）
