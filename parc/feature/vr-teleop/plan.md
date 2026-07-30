# Implementation Plan: VR Teleop Phase 1

> Agentic workers: track progress with checkboxes. Update [STATUS.md](STATUS.md) when a section completes.

**Goal:** Quest 3 コントローラで LIBERO を操作し、LeRobot v3 デモを `data/datasets/vr_libero_demos` に保存できる。

**Architecture:** Approach A（`parc.vr` サーバ + Unity 薄クライアント）。詳細は [design.md](design.md)。

**Tech Stack:** Python 3.10+, websockets, Pillow/numpy, LIBERO OffScreenRenderEnv, LeRobot dataset v3, Unity OpenXR

---

### Task 1: Feature docs

**Files:**
- Create: `feature/vr-teleop/README.md`, `design.md`, `plan.md`, `STATUS.md`, `protocol.md`

- [x] **Step 1:** feature フォルダ一式を作成する

---

### Task 2: Protocol + action map (TDD)

**Files:**
- Create: `src/parc/vr/protocol.py`, `src/parc/vr/action_map.py`, `src/parc/vr/__init__.py`
- Test: `tests/test_vr_protocol.py`, `tests/test_vr_action_map.py`

- [x] **Step 1:** 失敗するテストを書く
- [x] **Step 2:** protocol encode/decode を実装して通す
- [x] **Step 3:** pose delta → action7 を実装して通す

---

### Task 3: Obs util + recorder + fake session

**Files:**
- Create: `src/parc/vr/obs_util.py`, `src/parc/vr/recorder.py`, `src/parc/vr/session.py`, `src/parc/vr/video.py`
- Create: `src/parc/vr/cli_main.py`（CLI 本体）
- Modify: `src/parc/cli.py`, `pyproject.toml`
- Create: `scripts/vr_teleop.sh`
- Test: `tests/test_vr_obs_and_session.py`

- [x] **Step 1:** obs → front/wrist/state8 の単体テスト
- [x] **Step 2:** メモリ上のフレームバッファ recorder（lerobot 無しでも検証可能）
- [x] **Step 3:** `--fake` でダミー入力ループ +（利用可能なら）LeRobot 書き込み
- [x] **Step 4:** `parc-vr-teleop` / `vr_teleop.sh` エントリ

---

### Task 4: WebSocket server + JPEG downlink

**Files:**
- Create: `src/parc/vr/server.py`
- Modify: `src/parc/vr/session.py`
- Test: `tests/test_vr_obs_and_session.py`（JPEG）

- [x] **Step 1:** RGB → JPEG エンコードテスト
- [x] **Step 2:** WS サーバ（control uplink / video downlink / session events）
- [x] **Step 3:** `--fake` 無しで接続待ち

---

### Task 5: Unity OpenXR client

**Files:**
- Create: `unity/VrTeleop/README.md`
- Create: `unity/VrTeleop/Assets/Scripts/*.cs`

- [x] **Step 1:** WebSocket クライアント + pose 送信
- [x] **Step 2:** JPEG パネル表示
- [x] **Step 3:** record / save / discard UI バインド
- [x] **Step 4:** README に Meta Quest ビルド手順

---

### Task 6: Docs + STATUS

**Files:**
- Create: `docs/12_vr_teleop.md`
- Modify: `README.md`（できること表）
- Modify: `feature/vr-teleop/STATUS.md`, `plan.md` checkboxes

- [x] **Step 1:** 運用ドキュメント
- [x] **Step 2:** STATUS を Phase 1 実装完了に更新（Quest E2E は環境依存で backlog 可）
