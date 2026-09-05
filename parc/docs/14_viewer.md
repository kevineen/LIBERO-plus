# 14. Episode Viewer（Web / スマホ / VR でデモ確認）

収録済みデモ（LIBERO HDF5 / VR テレオプの LeRobot）を、**ブラウザ・スマホ・
Quest 3 のどこからでも 3D で確認**できるビューア。MuJoCo シーンを忠実に
3D 再現し、自由視点・ズーム・拡大縮小・再生コントロールが可能。
VR（WebXR）では立体視 + コントローラー操作で再生・エピソード選択ができる。

```text
[HDF5 / LeRobot デモ]
   parc-export-viewer（GLB メッシュ + tracks.bin ポーズ + カメラ mp4）
        ↓
parc/data/viewer_packs/<dataset>/<task>/<ep>/  + index.json
        ↓
parc-web :3030  /api/v1/viewer/*  →  /viewer ページ（React Three Fiber + WebXR）
        ↓
PC ブラウザ（マウス視点操作・キーボード再生）
スマホ（タッチ視点操作・ピンチズーム・ボタン再生）
Quest 3 ブラウザ（WebXR 没入 VR・コントローラー UI）
```

## 1. 使い方

### 1-1. scene pack の生成

```bash
# LIBERO 同梱 HDF5 デモ（libero_spatial など）
./scripts/parc.sh export-viewer --hdf5 data/datasets/libero_spatial/<task>_demo.hdf5 --demos 0 1

# VR テレオプ収集の LeRobot データセット
./scripts/parc.sh export-viewer --lerobot data/datasets/vr_libero_demos

# 既存 packs の index.json 再生成のみ
./scripts/parc.sh export-viewer --reindex
```

- `--out`（既定 `data/viewer_packs`）: pack 出力ルート
- `--demos` / `--episodes`: 対象 demo 番号・episode_index（省略時は全件）
- `--max-frames N`: 長いエピソードのフレーム間引き
- `--no-videos`: カメラ mp4 を出力しない（3D のみ）
- `--force`: 既存 pack の上書き

pack 1 エピソードの中身:

| ファイル | 内容 |
|---|---|
| `scene.glb` | MuJoCo 可視 geom のメッシュ（body 階層、z-up→y-up 焼き込み済み） |
| `tracks.bin` | float32 `[frames][bodies][7]`（pos xyz + quat wxyz、MuJoCo world 座標） |
| `front.mp4` / `wrist.mp4` | 保存観測からのカメラ映像（180° 回転補正済み） |
| `meta.json` | fps・フレーム数・body↔GLTF node 対応・品質情報 |

HDF5 は `states` からの決定的リプレイ、LeRobot は action 再生でポーズ抽出。

### 1-2. ビューアを開く

```bash
bash scripts/start_web.sh        # 既定 :3030（別 PC からは http://<LAN IP>:3030）
```

- PC: `http://localhost:3030/viewer`
- スマホ: 同一 LAN から `http://<PCのIP>:3030/viewer`（QR で渡すと楽）

### 1-3. 操作

| デバイス | 操作 |
|---|---|
| PC | ドラッグ=視点回転 / ホイール=ズーム / `Space`=再生停止 / `←→`=フレーム送り / `↑↓`=エピソード切替 |
| スマホ | 1 本指ドラッグ=視点回転 / ピンチ=ズーム / ボタンとタイムラインで再生 |
| Quest 3 (VR) | `Enter VR` ボタンで没入。**A**=再生/停止、**B**=速度切替、**X/Y**=エピソードメニュー、**右スティック上下**=シーン拡大/縮小、**左スティック**=移動。コントローラーレイで UI パネル・タイムラインを直接クリック |

エピソード一覧は検索・データセット絞り込み・成否フィルタ対応。
VR テレオプ収集分は `episode_quality.jsonl` の success / replay_success を
バッジ表示する。

## 2. Quest 3 から見る（WebXR）

WebXR の没入モードは **secure context（HTTPS または localhost）** が必須。
LAN の `http://192.168.x.x` では Enter VR が無効になるため、開発時は
USB 経由の port forwarding を使う:

```bash
# PC 側で一度だけ（adb は Android Studio または platform-tools 入り）
adb reverse tcp:3030 tcp:3030
```

Quest 3 のブラウザで `http://localhost:3030/viewer` を開く → localhost は
secure context 扱いなので `Enter VR` が有効になる。

LAN HTTPS（mkcert 等）での常設運用は将来課題。Quest ブラウザはインターネット
接続を前提（drei Text のデフォルトフォント取得）。

## 3. 仕組み・拡張

- **エクスポータ**: `src/parc/viewer_export/`（`scene_pack.py` / `build_index.py` /
  `glb.py` 最小 GLB ライタ）。外部依存追加なし（mujoco / h5py / imageio のみ）。
- **API**: `web/app/api/v1/viewer/index`（index.json）と
  `web/app/api/v1/viewer/file`（Range 対応ストリーム、パスは
  `viewer_packs/` 配下に制限）。
- **フロント**: `web/components/viewer/`（store=zustand、Scene3D=GLB+トラック適用、
  PlaybackBar / EpisodeList / CameraPanels=DOM UI、VrLayer=VR 内 UI）。
- テクスチャ付き geom は RGBA 単色で出力（現状の簡略化）。床/テーブルの
  テクスチャ反映は将来拡張。
- ライブ（テレオプ中）監視は将来拡張: pack 形式は静的配信前提だが、
  tracks を WebSocket で流す形式へ自然に拡張できる設計。

## 4. 関連

- VR テレオプ本編: [12_vr_teleop.md](12_vr_teleop.md) / [13_quest3_setup.md](13_quest3_setup.md)
- Web コンソール: [10_ops_ui.md](10_ops_ui.md)
