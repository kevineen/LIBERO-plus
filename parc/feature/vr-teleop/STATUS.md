# STATUS: VR Teleop

**Updated:** 2026-07-31

## Current phase

**Data quality M1–M4（ソフト）完了。** Phase 1 + 品質ゲートは実装済み。  
**M0 Quest 実機 E2E は環境依存で継続 blocked**（手順の正本は [next-sprint-plan.md](next-sprint-plan.md)）。

## Checklist

| Item | Status |
|------|--------|
| feature docs | done |
| protocol + action_map + tests | done |
| fake teleop + recorder | done（`--fake-episode`） |
| JPEG WebSocket server | done（`parc-vr-teleop`） |
| Unity thin client scripts | done（`unity/VrTeleop/`） |
| docs/12 + README update | done |
| **success save gate** (`require_success`) | done（既定は失敗も保存） |
| **init_state / task_ids diversity** | done |
| **episode_quality.jsonl + collection_stats** | done |
| **collection_info + calib override** | done |
| **LeRobot Dataset v3.0 準拠書き込み** | done（timestamp 自動付与・finalize） |
| **parc-verify-demos** | done（`--coverage` / `--require-replay-success`） |
| **parc-filter-demos** success-only | done |
| **RTT / latency gate** | done（`max_rtt_ms` / `latency_policy`） |
| **collection_queue + category** | done |
| **parc-replay-demos** | done |
| **Approximate Time stale drop** | done（`approx_time_slop_ms`） |
| Quest hardware E2E | pending（Windows + Headset） |
| LeRobot disk write on robot venv | pending（実機/venv で確認） |

## Sprint C acceptance

- [ ] Quest 実機で 1 episode saved
- [ ] `meta/info.json` を確認
- [ ] `smolvla_ft_vr_demos_smoke.yaml` が起動
- [x] 操作感パラメータを YAML で調整
- [x] 未成功 Save 拒否（単体テスト）
- [x] quality jsonl + verify CLI（単体テスト）

## Sprint C result

- Quest E2E result: blocked
- Host machine: local WSL（Quest / Windows 側は未接続）
- Dataset root checked: `data/datasets/vr_libero_demos`（設定・コード上で整備、実機保存は未確認）
- Smoke FT run_id: not run
- Quality gates: fake / pytest で検証済み（M1–M4 含む）
- Next blocker: Quest 実機接続と `PARC_ROBOT_VENV` 付き保存確認が未実施

## How to verify now

```bash
cd parc
uv run pytest tests/test_vr_*.py tests/test_filter_demos.py tests/test_replay_demos.py -q
bash scripts/vr_teleop.sh --config configs/vr/fake_smoke.yaml --fake --no-dataset
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv \
  bash scripts/vr_teleop.sh --fake-episode --config configs/vr/fake_smoke.yaml
# 品質メタ検証（保存後）
# uv run parc-verify-demos --root data/datasets/vr_libero_demos --coverage
# success-only 学習 subset
# uv run parc-filter-demos --root data/datasets/vr_libero_demos \
#   --output data/datasets/vr_libero_demos_success --success-only --overwrite
# Quest: PARC_ROBOT_VENV=... bash scripts/vr_teleop.sh --config configs/vr/quest3_libero_spatial_task0.yaml
```

## Blockers

- Quest E2E: Windows Unity ビルド + 同一 LAN
- LeRobot 永続化: `PARC_ROBOT_VENV`（lerobot 入り）または薄 venv への追加導入

## Backlog (Phase 2+)

データ品質・スケーリングの優先計画は **[roadmap-data-quality.md](roadmap-data-quality.md)** を正本とする。

### ロードマップ（要約）

- [ ] **M0** Quest 実機 E2E（#1）— **blocked**（Windows + Unity + Headset 未接続）
- [x] **M1** 学習時 success-only フィルタ（#3）
- [x] **M2** RTT / 遅延ゲート（#2）
- [x] **M3** 摂動・カテゴリ多様化キュー（#4）
- [x] **M4** 物理リプレイ検証 + Approximate Time 同期器（#5 #6）

### その他

- [ ] ハンドトラッキング入力モード
- [ ] Unity 3D シーン同期ビュー
- [ ] 実機 Franka テレオプバックエンド
- [ ] パススルー人間動作 → ロボット軌道変換
- [ ] WebRTC 低遅延映像（必要なら）
- [ ] Unity クライアントからの周期 `ping`（RTT 実測）
