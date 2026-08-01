# 01. 現在の状況（スナップショット）

時点: **2026-08-01 06:25 JST 頃**

## 一言

- **親 = continue10k 凍結**。cam FT 禁止（Phase D）。
- **並行:** D1 Language on **thor**（hard deep running）· D3 VR on **mainpc**（Quest 準備）。
- 計画: [2026-08-01-phase-d1-language-d3-vr.md](../docs/superpowers/plans/2026-08-01-phase-d1-language-d3-vr.md)

## マシン別

### winpc（mainpc）

| 項目 | 状態 |
|------|------|
| 役割 | **D3 VR**（Unity/Quest は Windows 側） |
| ソフト | `parc-vr-teleop` CLI OK · fake-episode は robot venv で要確認 |
| 次 | Windows Unity プロジェクト + Quest で `ws://<LAN-IP>:8765` |
| 親 ckpt | continue10k `…cbbf5c8b…/010000` |

### thor

| 項目 | 状態 |
|------|------|
| running | D1 Language hard deep · `q_…70c96dab`（984/986/988×10） |
| 診断 | 語彙 OOD（darkhued/container 言い換えが全滅） |
| 次 | 動画確認 → 言語ラベル置換 FT 草案（承認後） |

### nuc

| 項目 | 状態 |
|------|------|
| GPU | OK · idle |
| 直近 | Lang 0.20 · Sensor 0.24（親決め禁止） |
