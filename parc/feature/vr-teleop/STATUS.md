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

## Sprint C acceptance

- [ ] Quest 実機で 1 episode saved
- [ ] `meta/info.json` を確認
- [ ] `smolvla_ft_vr_demos_smoke.yaml` が起動
- [x] 操作感パラメータを YAML で調整

## Sprint C result

- Quest E2E result: blocked
- Host machine: local WSL（Quest / Windows 側は未接続）
- Dataset root checked: `data/datasets/vr_libero_demos`（設定・コード上で整備、実機保存は未確認）
- Smoke FT run_id: not run
- Next blocker: Quest 実機接続と `PARC_ROBOT_VENV` 付き保存確認が未実施

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
