# STATUS: VR Teleop

**Updated:** 2026-08-01

## Current phase

**Phase D3 並行（mainpc）:** M0 Quest 実機 E2E を mainpc（Windows + WSL）で再開。  
ソフト M1–M4 は完了。cam 軸 FT とは独立。

## Checklist

| Item | Status |
|------|--------|
| feature docs | done |
| protocol + action_map + tests | done |
| fake teleop + recorder | done（`--fake-episode`） |
| JPEG WebSocket server | done（`parc-vr-teleop`） |
| Unity thin client scripts | done（`unity/VrTeleop/`） |
| docs/12 + README update | done |
| success save gate / diversity / quality / verify / filter / RTT / queue / replay / Approx Time | done |
| Quest hardware E2E | **in progress on mainpc**（Windows Unity + Headset） |
| LeRobot disk write on robot venv | pending（実機で確認） |

## mainpc で今やること（手作業）

**手順の正本:** [docs/13_quest3_setup.md](../../docs/13_quest3_setup.md)

1. Quest 開発者モード → Unity プロジェクト → APK（§2–5）
2. WSL portproxy + FW（§6）→ `--fake` で接続確認（§7–8）
3. 本番 1 ep Save → `uv run parc-verify-demos --root data/datasets/vr_libero_demos` → 本ファイルに結果追記

## Sprint C acceptance

- [ ] Quest 実機で 1 episode saved
- [ ] `meta/info.json` を確認
- [ ] `smolvla_ft_vr_demos_smoke.yaml` が起動
- [x] 操作感 / Save 拒否 / quality+verify（ソフト）

## Sprint C result

- Quest E2E: **mainpc で再開中**
- Host: winpc（`PARC_MACHINE_ID=winpc`）
- Next blocker: Quest 接続と Windows↔WSL `:8765` 到達
