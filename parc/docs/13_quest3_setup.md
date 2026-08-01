# 13. Quest 3 セットアップ（PARC VR Teleop）

Meta Quest 3 を **Windows PC + WSL2（mainpc）** 上の `parc-vr-teleop` に接続し、LIBERO デモを撮るまでの手順書。  
プロトコル・学習接続の概要は [12_vr_teleop.md](12_vr_teleop.md)。Unity スクリプトの短いメモは [unity/VrTeleop/README.md](../unity/VrTeleop/README.md)。

```text
Quest 3 (Unity APK)
    │  WebSocket  ws://<到達可能なIP>:8765
    ▼
Windows ホスト  ←── portproxy / ファイアウォール ──►  WSL2
                                                      parc-vr-teleop
                                                      LIBERO / LeRobot
```

**重要:** Unity のビルドと Quest へのインストールは **Windows 上**で行う（WSL では不可）。  
サーバ（`parc-vr-teleop`）は **WSL2** で動かす。

---

## 0. 所要時間の目安

| 段階 | 内容 | 目安 |
|------|------|------|
| A | Quest 本体の開発者設定 | 15–30 分 |
| B | Windows + Unity + Android ビルド環境 | 30–90 分（初回） |
| C | VrTeleop プロジェクト作成・ビルド | 30–60 分 |
| D | WSL サーバ + ネットワーク疎通 | 15–30 分 |
| E | フェイク接続 → 本番 1 ep | 15–30 分 |

---

## 1. 用意するもの

### ハードウェア

- Meta Quest 3（コントローラー左右）
- 充電済み・同一 Wi‑Fi（できれば 5GHz）に接続した Windows PC（mainpc）
- USB‑C ケーブル（開発者モード有効化・APK インストール用。無線デプロイでも可）

### ソフトウェア（Windows）

| ソフト | 用途 |
|--------|------|
| [Meta Quest アプリ](https://www.meta.com/quest/setup/)（旧 Oculus） | ヘッドセット管理・開発者モード |
| [Unity Hub](https://unity.com/download) + **Unity 2022.3 LTS** | クライアントビルド |
| Android Build Support（Unity インストール時に追加） | Quest 向け APK |
| [SideQuest](https://sidequestvr.com/)（任意） | APK インストールが楽 |

### アカウント

- Meta アカウント
- 開発者モード用に [Meta Developer](https://developer.oculus.com/) で Organization 作成（個人でも可）

---

## 2. Quest 3 本体の設定

### 2.1 開発者モード

1. スマホの **Meta Quest アプリ** でヘッドセットを登録
2. メニュー → **ヘッドセット設定** → **開発者モード** をオン  
   （初回は Meta Developer で Organization 作成が必要）
3. Quest を再起動
4. Quest 内: **設定 → システム → 情報** で数回タップし「開発者」メニューが出ることを確認（機種により UI 差あり）

### 2.2 開発者向けオプション（推奨）

Quest 内 **設定 → システム → 開発者**:

- **USB デバッグ** オン（ケーブル接続時）
- **不明な提供元** のインストールを許可（SideQuest / 自前 APK 用）

### 2.3 ネットワーク

- Quest と Windows PC を **同じ LAN / 同じ Wi‑Fi** にする
- ゲスト Wi‑Fi やクライアント分離（AP isolation）は避ける（端末同士が通信できない）

---

## 3. Windows 側: Unity 環境

### 3.1 Unity インストール

1. Unity Hub → **Installs → Install Editor → 2022.3 LTS**
2. モジュールに必ず入れる:
   - **Android Build Support**
   - **Android SDK & NDK Tools**
   - **OpenJDK**
3. （推奨）**Windows Build Support** も入れて Editor 上の簡易確認に使う

### 3.2 新規プロジェクト

1. Hub → **New project** → **3D (URP)** または **3D Core**  
   名前例: `VrTeleop`
2. 作成場所は Windows パス（例: `C:\Users\<you>\Unity\VrTeleop`）。  
   **WSL の `/home/...` を直接プロジェクトルートにしない**

### 3.3 PARC スクリプトをコピー

リポジトリ（WSL から見える Windows パス例）:

```text
\\wsl$\Ubuntu\home\kevin\Matsuo\robot\LIBERO-plus\parc\unity\VrTeleop\Assets\Scripts\
```

またはエクスプローラーで WSL フォルダを開き、次を Unity プロジェクトへコピー:

| コピー元 | コピー先 |
|----------|----------|
| `parc/unity/VrTeleop/Assets/Scripts/VrTeleopClient.cs` | `<UnityProject>/Assets/Scripts/` |
| `parc/unity/VrTeleop/Assets/Scripts/VrTeleopXrBinder.cs` | `<UnityProject>/Assets/Scripts/` |

`Packages/manifest.example.json` は依存の参考。次節で Package Manager / git URL から入れる。

---

## 4. Unity パッケージと Quest 向け Player 設定

### 4.1 パッケージ

**Window → Package Manager** で追加:

| パッケージ | 必須 |
|------------|------|
| **OpenXR Plugin** (`com.unity.xr.openxr`) | 必須 |
| **XR Plugin Management** | 必須（OpenXR と一緒に入ることが多い） |
| XR Interaction Toolkit | 任意（本クライアントは `VrTeleopXrBinder` だけで可） |

**NativeWebSocket**（必須）— [endel/NativeWebSocket](https://github.com/endel/NativeWebSocket)

`Packages/manifest.json` の `dependencies` に例:

```json
"com.endel.nativewebsocket": "https://github.com/endel/NativeWebSocket.git#upm"
```

（タグはリポジトリの最新 UPM 案内に合わせる。入らなければ `.unitypackage` / ソース直接配置でも可。）

### 4.2 Scripting Define

**Edit → Project Settings → Player → Other Settings → Scripting Define Symbols**（Android）に追加:

```text
NATIVE_WEBSOCKET
```

これがないと `VrTeleopClient` は接続せず警告だけ出す。

### 4.3 XR Plug-in Management

1. **Edit → Project Settings → XR Plug-in Management**
2. タブ **Android** で **OpenXR** にチェック
3. 左側（または OpenXR 行の歯車）→ **OpenXR** 設定を開く
4. **Interaction Profiles** で **+** を押し、少なくとも1つ追加する（警告解消に必須）:

| 追加するプロファイル | 用途 |
|----------------------|------|
| **Oculus Touch Controller Profile** | Quest 2/3 タッチコントローラー（**まずこれ**） |
| Meta Quest Touch Plus Controller Profile | Quest 3 向け（一覧にあれば追加してよい） |
| Eye Gaze / Hand 等 | 本クライアントでは不要 |

5. 同じ OpenXR 画面の **OpenXR Feature Groups** / **Features** で次を有効化（名前はバージョンで多少違う）:
   - **Meta Quest Support**（または Oculus Quest Support）
   - 必要なら **Meta Quest Feature** / **XR Meta OpenXR** 系

6. **Android** タブ側でも Interaction Profiles が空でないことを確認（PC タブだけ埋めて Android が空、というミスが多い）

警告文 `"At least one interaction profile must be added..."` は、**Features ではなく Interaction Profiles リストが空**のときに出る。コントローラープロファイルを足せば消える。

### 4.4 Android Player Settings

**Edit → Project Settings → Player**（Android）:

| 項目 | 推奨値 |
|------|--------|
| Minimum API Level | **Android 12L (API 32)** 以上 |
| Scripting Backend | **IL2CPP** |
| Target Architectures | **ARM64** のみ（ARMv7 オフ） |
| Internet Access | **Require**（WebSocket 用） |
| Write Permission | External は任意 |

**File → Build Settings**:

- Platform: **Android** → Switch Platform
- Run Device: 接続中の Quest 3（USB **または Wi‑Fi ADB**）または「Export / Build APK」

### 4.1 Wi‑Fi で APK を送る（USB なし運用）

**初回だけ USB が必要**（無線 ADB を有効化するため）。その後は同じ Wi‑Fi 上ならケーブル無しで Build And Run / `adb install` できる。

**方法 A（推奨）: Meta Quest Developer Hub**

1. [MQDH](https://developers.meta.com/horizon/documentation/unity/ts-mqdh-basic-usage/) を Windows に入れる
2. USB で Quest を接続 → ヘッドセット内で「USB デバッグを許可」
3. MQDH → **Device Manager** → **ADB over Wi‑Fi** を ON
4. USB を抜く
5. Unity **Build Settings → Run Device** に Quest が出ていれば **Build And Run**

**方法 B: コマンドライン**

```powershell
# USB 接続中に（Unity 付属 adb でも可）
adb devices
adb shell ip route
# 表示の src の後ろが Quest の IP（例 192.168.1.23）
adb tcpip 5555
adb connect <QuestのIP>:5555
adb devices
# 例: 192.168.1.23:5555   device  と出れば OK → USB を抜いてよい
```

以降のインストール例:

```powershell
adb install -r E:\Unity\VrTeleop\Builds\VrTeleop.apk
```

注意:

- PC と Quest は **同じ Wi‑Fi**（ゲスト分離オフ）
- Quest / PC 再起動後は `adb connect` または MQDH の Wi‑Fi ADB をやり直しが必要なことが多い
- 無線は USB より遅い。大きい APK は時間がかかる

---

## 5. シーン構成（最小）

1. 空のシーンを保存（例: `Assets/Scenes/VrTeleop.unity`）
2. Hierarchy:
   - 空 GameObject `VrTeleop`
     - `VrTeleopClient`
     - `VrTeleopXrBinder`（`client` に同じオブジェクトの Client を割り当て）
   - 空 GameObject `RightControllerAnchor`（Transform のみ）→ Client の **Right Controller** に割当
   - **`HudRoot`（`VrTeleopHudFollow`）** — `head` = Main Camera。**Camera の子にしない**
     - Quad ×2（`FrontPanel` / `WristPanel`）を **HudRoot の子** にする
     - Material: Unlit、MainTex を Client の **Front Panel / Wrist Panel** Renderer に割当
3. Inspector `VrTeleopClient`:
   - **Server Url** — 後述の到達可能 URL（仮で `ws://127.0.0.1:8765` のままビルドしない）
   - **Send Hz** = `20`
4. Build Settings にこのシーンだけを入れてビルド

> **重要（Stereo）:** Front/Wrist パネルを **Main Camera の子** にすると、VR で左右ずれ・二重像・「両パネルに両方の映像」に見えます。  
> 必ず `VrTeleopHudFollow` 配下（Camera の外）に置き、頭追従はスクリプトに任せてください。  
> Play 時に `[VrTeleop] … が Camera「Main Camera」の子です` が出たら配置ミスです。

### 5.1 Windows Editor で先に映像確認（Quest 不要）

APK を焼く前に **Play Mode** でパネル映像を確認できる。

1. **Scripting Define** を Android だけでなく **Standalone**（Windows）にも付ける  
   `Edit → Project Settings → Player → Other Settings → Scripting Define Symbols`  
   - タブ **Windows / Standalone** に `NATIVE_WEBSOCKET`  
   - （Android 側にも同じ定義があること）
2. シーンは §5 のまま。Game ビューで `FrontPanel` / `WristPanel` が見える位置に Main Camera を置く
3. Inspector `Server Url`:
   - portproxy 済みなら **`ws://127.0.0.1:8765`**（Windows → WSL）
   - 不通なら Windows LAN IP（`ws://192.168.x.x:8765`）
4. WSL でサーバ起動（まず fake）:

```bash
bash scripts/vr_teleop.sh --config configs/vr/fake_smoke.yaml --fake --no-dataset
```

5. Unity で **Play** → Console に `[VrTeleop] connected` と `jpeg ok`  
   - fake: パネルが赤／緑に変わる  
   - プロジェクト直下に `vr_teleop_front.png` / `vr_teleop_wrist.png` が保存される（Editor）
6. 問題なければ本番:

```bash
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv \
  bash scripts/vr_teleop.sh --config configs/vr/quest3_libero_spatial_task0.yaml
```

Unity 無しでサーバ映像だけ見る場合（WSL）:

```bash
uv run scripts/vr_ws_capture.py --url ws://127.0.0.1:8765 --out /tmp/vr_cap
# /tmp/vr_cap/*.png を確認
```

### コントローラ割り当て（`VrTeleopXrBinder` 既定）

| Quest | 機能 |
|-------|------|
| **右手 A**（primary） | Record 開始/トグル |
| **右手 B**（secondary） | Save |
| **右手 Grip** | Discard |
| **左手 Menu（≡）** または **左手 Y** | Reset（右手に Menu は無い） |
| **右手 Trigger** | Gripper（0–1） |

`VrTeleop` オブジェクトに **`VrTeleopXrBinder`** が付いていること。Console に `[VrTeleopXr] RightHand tracking OK` が出れば入力は生きている。  
`RightHand XR device not found` なら OpenXR Interaction Profiles（Oculus Touch）と Active Input Handling=Both を確認して APK 再ビルド。

Editor では矢印キーで EE、`R`/`S`/`G`/`T` でボタン試験可。

---

## 6. ネットワーク: WSL2 でサーバを動かす場合（mainpc 必須）

Quest は **WSL の仮想 IP に直接届かない**ことが多い。次のどちらかにする。

### 方法 A（推奨）: Windows で portproxy

1. **管理者の PowerShell** で Windows の LAN IP と WSL IP を確認:

```powershell
ipconfig
wsl hostname -I
```

2. ポート転送（例: Windows `0.0.0.0:8765` → WSL `<WSL_IP>:8765`）:

```powershell
netsh interface portproxy add v4tov4 `
  listenaddress=0.0.0.0 listenport=8765 `
  connectaddress=<WSL_IP> connectport=8765
```

WSL 再起動で WSL IP が変わることがある。そのときは `portproxy` を消し再設定:

```powershell
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=8765
netsh interface portproxy show all
```

3. Windows ファイアウォールで **TCP 8765** を許可（受信）。

4. Quest の **Server Url** =

```text
ws://<WindowsのLAN_IP>:8765
```

例: `ws://192.168.11.5:8765`  
**`localhost` / `127.0.0.1` は Quest から見ると Quest 自身なので不可。**

### 方法 B: サーバを Windows ネイティブで動かす

WSL を経由しない場合は portproxy 不要。ただし現状の LIBERO / robot venv は WSL 前提のため、**通常は方法 A**。

### 疎通チェック

**注意:** `Test-NetConnection 127.0.0.1 -Port 8765` が True なのは「Windows ループバックに何かいる」ことだけ示す。  
Quest には別途 **Windows の LAN IP** と、WSL サーバの **`host: 0.0.0.0`** + portproxy が必要。

1. YAML の `host` が `0.0.0.0` か確認（`fake_smoke.yaml` / `quest3_*.yaml`）
2. サーバ再起動後、ログが `listening on 0.0.0.0:8765` であること（`127.0.0.1` だけなら NG）
3. portproxy 設定済みなら:

```powershell
# Windows の LAN IP を確認（例 192.168.x.x）
ipconfig
Test-NetConnection -ComputerName <WindowsのLAN_IP> -Port 8765
```

4. Quest の Server Url = `ws://<WindowsのLAN_IP>:8765`

届かなければ Wi‑Fi 分離・FW・portproxy・`host: 127.0.0.1` 固定を疑う。

---

## 7. PC サーバ起動（WSL）

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc

# (1) まずフェイク — Quest 接続・映像パネル確認用（データ無し）
bash scripts/vr_teleop.sh --config configs/vr/fake_smoke.yaml --fake --no-dataset

# (2) 本番 — LIBERO + LeRobot 書き込み
PARC_ROBOT_VENV=/home/kevin/Matsuo/robot/.venv \
  bash scripts/vr_teleop.sh --config configs/vr/quest3_libero_spatial_task0.yaml
```

設定正本: `configs/vr/quest3_libero_spatial_task0.yaml`（`host: 0.0.0.0` / `port: 8765`）。

ログに待ち受けと接続が出たら OK。Quest 側で APK を起動し、接続メッセージを確認。

---

## 8. 初回 E2E チェックリスト

- [ ] Quest 開発者モード ON
- [ ] Unity で APK ビルド成功・Quest にインストール
- [ ] `NATIVE_WEBSOCKET` 定義済み
- [ ] WSL で `--fake --no-dataset` 起動中
- [ ] portproxy + FW 済み
- [ ] Server Url = `ws://<Windows LAN IP>:8765`
- [ ] Quest で映像パネルが更新される（フェイクは色バー）
- [ ] A で record、B で save がサーバログに見える
- [ ] 本番 config に切替 → 1 ep 保存
- [ ] 検証:

```bash
uv run parc-verify-demos --root data/datasets/vr_libero_demos
ls data/datasets/vr_libero_demos/meta/info.json
```

結果は [feature/vr-teleop/STATUS.md](../feature/vr-teleop/STATUS.md) に追記する。

---

## 9. 操作フロー（本番）

1. WSL で `quest3_libero_spatial_task0.yaml` 起動
2. Quest で VrTeleop 起動 → 接続
3. 右手で EE を動かし、front/wrist 映像を確認
4. **A** Record → タスク実行 → **B** Save  
   （既定は失敗も保存。成功のみにするなら YAML で `require_success: true`）
5. **Menu** で Reset（次の init_state）
6. 不要なら **Grip** Discard

詳細・品質ゲート: [12_vr_teleop.md](12_vr_teleop.md)。

---

## 10. トラブルシュート

| 症状 | 確認 |
|------|------|
| OpenXR: interaction profile must be added | **Project Settings → XR → OpenXR → Interaction Profiles** に **Oculus Touch Controller Profile** を追加（Android タブ側）。Features だけでは消えない |
| Unity が WSL パスで壊れる | プロジェクトを `C:\...` に置く |
| ビルドが ARMv7 / API 不足 | ARM64 のみ・Min API 32・IL2CPP |
| 接続直後に落ちる / OnError | `NATIVE_WEBSOCKET`・Internet Access Require・Server Url |
| 繋がらない | 同一 Wi‑Fi・AP 分離・FW・**portproxy**・Windows LAN IP |
| 映像が黒い | **接続直後の fake は昔 t=0 が黒**だった（修正済）。`rightController` 未割当だと control が送られず更新されない。URP なら `_BaseMap`（スクリプトは両方セット）。パネル Renderer 割当も確認 |
| 本番がテレビノイズ | fake 赤緑 OK なら Unity は正常。**旧 JPEG 破損**→現行は RGB24 raw（要最新 `VrTeleopClient`）。サーバ再起動 |
| 映像なし・PNG 無し・`rgb ok` が出ない | **Unity が古い DLL のまま**。Console に `client build: rgb-0x11` が無ければ未再コンパイル。`Assets → Reimport All` かスクリプトを Unity 内で再保存。APK も再ビルド必須 |
| APK ビルドが class layout incompatible | Editor と Player のアセンブリ不整合。Play を止め → Reimport → 再ビルド |
| 黒チラつき | 旧クライアントは毎フレーム `Renderer.material` 再生成していた（修正済）。最新スクリプトへ更新して再ビルド |
| VR で左右ずれ・両パネルに両方の映像 | **パネルが Main Camera の子**。`HudRoot`+`VrTeleopHudFollow` 配下へ移す。Console に Camera 子警告が出るか確認 |
| たまにカクつく／一瞬おかしい | 古いクライアントは溜まった全フレームを Apply していた。`2026-08-01g`（latest-frame）へ更新。`Send Hz` は 20 推奨 |
| 最初は良いが時間後に別映像がチラつく | `LoadRawTextureData(managed[])` + GC / RGB24。`2026-08-01i`（RGBA32 + HideAndDontSave）へ更新 |
| Editor で RightHand not found が連発 | コントローラ未接続時は正常。矢印キーで操作。警告は 01i で1回だけ |
| Console 触ると映像が乱れる | Editor テキスト入力中のキー拾いを無視（01i） |
| コントローラ無反応・ボタン無効 | `VrTeleopXrBinder` 未アタッチ、または XR device 未検出。Reset は**左手 Menu/Y**。Console の `[VrTeleopXr]` ログを確認 |
| `closed ServerError` | LIBERO 初期化中の **WS ping timeout (1011)**。現行は keepalive 無効化済み。サーバ再起動。接続後数十秒は `loading env` 待ち |
| 保存されない | `PARC_ROBOT_VENV`・`--no-dataset` になっていないか・ディスク容量 |
| 操作が過敏/鈍い | YAML の `action_map`（[12](12_vr_teleop.md)） |
| WSL IP が変わって突然不通 | `portproxy` の connectaddress を更新 |
| Quest が「不明なアプリ」拒否 | 開発者モード・不明な提供元 |

---

## 11. 関連ファイル

| パス | 内容 |
|------|------|
| [12_vr_teleop.md](12_vr_teleop.md) | サーバ CLI・学習・品質ゲート |
| [unity/VrTeleop/README.md](../unity/VrTeleop/README.md) | Unity 短メモ |
| [feature/vr-teleop/STATUS.md](../feature/vr-teleop/STATUS.md) | E2E 進捗 |
| `configs/vr/quest3_libero_spatial_task0.yaml` | Quest 本番サーバ設定 |
| `configs/vr/fake_smoke.yaml` | 接続スモーク |
| `feature/vr-teleop/protocol.md` | WebSocket メッセージ |
