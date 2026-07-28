# 01. 現在の状況（スナップショット）

時点: **2026-07-29 06:45 JST 頃**

## 一言

- **thor 厚い eval 完了**: unfreeze@30k **SR=0.429** / continue@30k(expert-only) **SR=0.286**。キュー空・GPU 空き。
- **nuc**: 再起動後復帰。CUDA OK。厚い Gate3 eval **再投入・running**（`q_20260728T214414…` / run `…bec819ac…`）。
- winpc: cam-only FT は薄い 0.000 で打ち切り。キュー空。親は +15k（厚い 0.371）。

## マシン別

### winpc（RTX 4090 · `PARC_MACHINE_ID=winpc`）

| 項目 | 状態 |
|------|------|
| worker | 稼働想定（キュー空） |
| 実行中 | なし |
| 直近完了 | cam-only rerender · 薄い **SR=0.000** |
| 親 ckpt | `…cb240365…/015000`（+15k · 厚い 0.371） |

### thor（`PARC_MACHINE_ID=thor`）

| 項目 | 状態 |
|------|------|
| 到達 | OK（`kevin@100.99.61.50`） |
| worker | 稼働中（`--poll-sec 15`） |
| 実行中 | なし（キュー空） |
| GPU | 空き（Util 0%） |
| 直近完了（厚い tpc=5） | unfreeze@30k **0.429** · continue@30k expert-only **0.286** |
| 済み（薄い） | aligned 0.214 → continue 0.286 → unfreeze 0.571 |

Run:

- `20260728T020259Z_thor_076ae49b_smolvla_thick_eval_unfreeze30k_thor`
- `20260728T021430Z_thor_e58b83e0_smolvla_thick_eval_continue30k_thor`

### nuc（RTX 3090 · WSL2 · `PARC_MACHINE_ID=nuc`）

| 項目 | 状態 |
|------|------|
| 到達 | OK（`kevin@100.82.118.86`） |
| worker | 稼働中（`--poll-sec 15` · WSL GPU PATH 付き） |
| GPU | RTX 3090 · `torch.cuda=True`（再起動後復帰） |
| 実行中 | 厚い eval `q_20260728T214414717408+0000_a4209d02` · run `20260728T214421Z_nuc_bec819ac_…` |
| 直近完了 | Gate3 aligned@30k 薄い **SR=0.357** |
| メモ | 旧 stale `q_20260728T070732…` は fail 済。`.env.local` に `/usr/lib/wsl/lib` を追記済 |

## Fleet / UI

- Discord ジョブ完了は `PARC · <machine>` + `machine=` を正とする
- GPU 死活: hub で `parc-fleet gpu-check`（変化時のみ webhook）。cron 推奨 → `docs/10_ops_ui.md`

## ディスク・パス（覚書）

| マシン | experiments |
|--------|-------------|
| winpc | `/home/kevin/Matsuo/robot/LIBERO-plus/parc/experiments` |
| thor | `/mnt/sda/parc_libero_plus/experiments` |
| nuc | `/home/kevin/Matsuo/LIBERO-plus/parc/experiments`（`robot/` 無し） |
