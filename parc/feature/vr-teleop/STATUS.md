# STATUS: VR Teleop

**Updated:** 2026-07-30

## Current phase

**Phase 1 — implemented（コード・単体テスト・ドキュメント完了）**  
Quest 実機 E2E と LeRobot 実書き込みは環境依存で backlog。

## Checklist

| Item | Status |
|------|--------|
| feature docs | done |
| protocol + action_map + tests | done（19 passed） |
| fake teleop + recorder | done（`--fake-episode`） |
| JPEG WebSocket server | done（`parc-vr-teleop`） |
| Unity thin client scripts | done（`unity/VrTeleop/`） |
| docs/12 + README update | done |
| Quest hardware E2E | pending（Windows + Headset） |
| LeRobot disk write on robot venv | pending（実機/venv で確認） |

## How to verify now

```bash
cd parc
uv run pytest tests/test_vr_*.py -q
uv run parc-vr-teleop --fake-episode --no-dataset --dataset-root /tmp/vr_smoke
bash scripts/vr_teleop.sh --fake --host 127.0.0.1 --port 8765 --no-dataset
# 別端末で Quest / NativeWebSocket クライアントを接続
```

## Blockers

- Quest E2E: Windows Unity ビルド + 同一 LAN
- LeRobot 永続化: `PARC_ROBOT_VENV`（lerobot 入り）または薄 venv への追加導入

## Backlog (Phase 2+)

- [ ] ハンドトラッキング入力モード
- [ ] Unity 3D シーン同期ビュー
- [ ] 実機 Franka テレオプバックエンド
- [ ] パススルー人間動作 → ロボット軌道変換
- [ ] WebRTC 低遅延映像（必要なら）
- [ ] ActionMapConfig の YAML 化
