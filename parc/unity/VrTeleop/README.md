# VrTeleop (Unity OpenXR / Meta Quest 3)

薄い Quest クライアント。PC 上の `parc-vr-teleop` に接続し、コントローラ姿勢を送り、JPEG 映像をパネル表示する。

**初回セットアップの正本:** [`docs/13_quest3_setup.md`](../../docs/13_quest3_setup.md)  
（Quest 開発者モード・Unity・WSL portproxy・E2E チェックリストまで記載）

## 前提

- Unity 2022.3 LTS 以降（Windows ホスト）
- **Meta XR All-in-One SDK** または OpenXR + Meta Quest サポート
- 同一 LAN で PC の `ws://<pc-ip>:8765` に到達できること
- WSL2 上ではビルド不可（Windows の Unity Editor を使う）

## プロジェクト作成手順

1. Unity Hub で 3D (URP 可) プロジェクト `VrTeleop` を作成
2. このフォルダの `Assets/Scripts/` をプロジェクトの `Assets/Scripts/` へコピー
3. Package Manager で次を入れる:
   - `OpenXR Plugin`
   - `XR Interaction Toolkit`（任意）
   - NativeWebSocket 相当: 下記「WebSocket」節
4. Build Settings → Android → Run Device = Quest / Quest 3
5. Player Settings: Minimum API 32、IL2CPP、ARM64
6. XR Plug-in Management → Android → OpenXR  
   - **Interaction Profiles** に **Oculus Touch Controller Profile** を追加（必須）  
   - Features で Meta Quest Support を有効化

## WebSocket

`NativeWebSocket`（[endel/NativeWebSocket](https://github.com/endel/NativeWebSocket)）を推奨。

- `Packages/manifest.json` に git URL を追加するか、`.unitypackage` を入れる
- スクリプトは `using NativeWebSocket;` を想定

代替: `UnityWebSocket` 等でも可。`VrTeleopClient.cs` の `#define` を合わせて調整。

## Windows Editor で先に確認（推奨）

Quest 実機の前に Play Mode で映像を見る。

1. **Scripting Define Symbols** の **Standalone（Windows）** に `NATIVE_WEBSOCKET`（Android だけだと Editor で接続しない）
2. Main Camera から Front/Wrist パネルが見えるようにする
3. `Server Url` = `ws://127.0.0.1:8765`（WSL + portproxy 時）
4. WSL: `bash scripts/vr_teleop.sh --config configs/vr/fake_smoke.yaml --fake --no-dataset`
5. Play → 赤緑パネル + Console `jpeg ok` + プロジェクト直下の `vr_teleop_*.png`

詳細: [`docs/13_quest3_setup.md`](../../docs/13_quest3_setup.md) §5.1

## シーン構成

1. 空の GameObject `VrTeleop` に `VrTeleopClient` + `VrTeleopXrBinder` をアタッチ
2. Inspector:
   - `Server Url` = `ws://192.168.x.x:8765`
   - `Front Panel` / `Wrist Panel` = Quad + Unlit マテリアル（MainTex）
3. **映像パネルは Main Camera の子にしない**（Stereo で左右ずれ・二重像になる）  
   `HudRoot` + `VrTeleopHudFollow`（`head` = Main Camera）の子に Front/Wrist を置く
4. XR Origin を配置し、右手コントローラの Pose を `VrTeleopClient.rightController` に割当
5. ボタン（XR）:
   - PrimaryButton → Record
   - SecondaryButton → Save
   - GripButton → Discard
   - MenuButton → Reset
6. トリガ値 → Gripper

## PC 側

```bash
cd LIBERO-plus/parc
# フェイクで接続確認
bash scripts/vr_teleop.sh --config configs/vr/fake_smoke.yaml --fake --no-dataset

# 本番 LIBERO + LeRobot 書き込み
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv \
  bash scripts/vr_teleop.sh --config configs/vr/quest3_libero_spatial_task0.yaml
```

Quest の `Server Url` は `localhost` ではなく **Windows の LAN IP** にする（WSL サーバ時は portproxy）。  
詳細: [`docs/13_quest3_setup.md`](../../docs/13_quest3_setup.md) · [`docs/12_vr_teleop.md`](../../docs/12_vr_teleop.md)。

## プロトコル

`feature/vr-teleop/protocol.md` を参照。
