# WebSocket Protocol (v1)

Transport: WebSocket. Text frames = JSON. Binary frames = JPEG video.

Default endpoint: `ws://<host>:8765/vr`

## Client → Server (text JSON)

### `control`（〜20 Hz）

```json
{
  "type": "control",
  "t": 0.0,
  "pose": {
    "pos": [0.0, 0.0, 0.0],
    "quat": [0.0, 0.0, 0.0, 1.0]
  },
  "gripper": 0.0,
  "buttons": {
    "record": false,
    "save": false,
    "discard": false,
    "reset": false
  }
}
```

- `pose.pos`: コントローラ位置（メートル、クライアントローカル基準で可。サーバは差分のみ使用）
- `pose.quat`: `(x, y, z, w)`
- `gripper`: `[0, 1]`（0=開, 1=閉）
- `buttons.*`: エッジ検出（サーバが rising edge でイベント化）

### `ping`

```json
{ "type": "ping", "t": 0.0 }
```

## Server → Client (text JSON)

### `hello`

```json
{
  "type": "hello",
  "protocol_version": 1,
  "fps": 20,
  "video": { "front": true, "wrist": true, "jpeg_quality": 70 }
}
```

### `task_info`

```json
{
  "type": "task_info",
  "suite": "libero_spatial",
  "task_id": 0,
  "language": "pick up the black bowl ..."
}
```

### `episode_saved`

```json
{
  "type": "episode_saved",
  "episode_index": 0,
  "num_frames": 120,
  "dataset_root": "data/datasets/vr_libero_demos"
}
```

### `episode_discarded`

```json
{ "type": "episode_discarded", "reason": "user" }
```

### `status`

```json
{
  "type": "status",
  "recording": false,
  "frame_count": 0,
  "message": ""
}
```

### `error`

```json
{ "type": "error", "code": "bad_message", "message": "..." }
```

### `pong`

```json
{ "type": "pong", "t": 0.0 }
```

## Server → Client (binary)

各バイナリフレーム先頭 1 バイトがカメラ ID:

| Byte0 | Camera |
|-------|--------|
| `0x01` | front (agentview) |
| `0x02` | wrist |

残りは JPEG バイト列。

## Button semantics

| Button | Effect |
|--------|--------|
| `record` rising | エピソード録画開始（バッファクリア） |
| `save` rising | 現バッファを LeRobot episode として保存し停止 |
| `discard` rising | バッファ破棄して停止 |
| `reset` rising | env reset（録画中なら discard 相当） |

## Compatibility

`protocol_version` 不一致時はサーバが `error` を送り接続を閉じる。
