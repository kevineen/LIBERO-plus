# 01. 現在の状況（スナップショット）

時点: **2026-07-28 12:20 JST 頃**

## 一言

- 勝ち筋レシピは **official_aligned（expert_width=0.5 / Instruct VLM）**。
- **薄い eval（tpc=2）は過大評価しがち**。厚い eval（tpc=5）で親 ckpt を決める。
- winpc は continue 起点の短 FT 中。thor は厚い eval 2 本を消化中。
- nuc は Gate3 `official_aligned` 30k を再起動済み（WSL GPU パススルー復旧後）。

## マシン別

### winpc（RTX 4090 · `PARC_MACHINE_ID=winpc`）

| 項目 | 状態 |
|------|------|
| worker | 稼働中 |
| 実行中 | `smolvla_ft_continue30k_finetune15k_winpc`（+15k / lr=1e-5）≈40% |
| 起点 ckpt | continue@30k unfreeze 継続  
  `…091901Z_winpc_ef97e24e_…/030000`（厚い eval SR≈0.31 の親） |
| 直近完了 | Camera deep eval（tasks 608–612 ×10）→ **SR=0.16** |
| 待ち | なし（FT 完了後に薄い→厚い eval が必要） |

### thor（空き GPU を厚い eval に使用中）

| 項目 | 状態 |
|------|------|
| worker | 稼働中（`--poll-sec 15`） |
| 実行中 | `smolvla_thick_eval_unfreeze30k_thor`（薄い SR 0.57 の再評価） |
| 待ち | `smolvla_thick_eval_continue30k_thor`（expert-only continue 薄い SR 0.29） |
| 済み（薄い eval） | aligned 0.21 → continue 0.29 → unfreeze **0.57** |

設定 YAML（投入済）:

- `configs/experiments/smolvla_thick_eval_unfreeze30k_thor.yaml`
- `configs/experiments/smolvla_thick_eval_continue30k_thor.yaml`

### nuc（RTX 3090 · WSL2 · `PARC_MACHINE_ID=nuc`）

| 項目 | 状態 |
|------|------|
| 到達 | winpc→nuc（`kevin@100.82.118.86`）は OK。Windows Tailscale は `100.77.194.30`（SSH鍵未整備） |
| worker | 稼働中（`--poll-sec 15`）。`/usr/lib/wsl/lib` を PATH/LD に入れる必要あり |
| 実行中 | `smolvla_ft_official_aligned_nuc` Gate3 30k（job `q_20260727T034627…`）  
  run `20260728T032038Z_nuc_d9d066c5_…` · 開始直後 |
| 待ち | なし（重複 queued は cancel 済み） |
| 直近障害 | stale running（3%@1038、ckpt 無し）+ WSL から GPU 消失 → `wsl --shutdown` で復旧 |
| 方針 | 本 FT 完了まで新規重い学習は積まない。結果を 02 に Gate3 として記録 |
| 通知 | `notify/webhook.py` を winpc と同期済（`PARC · nuc` / `machine=nuc`）。完了時に届く |

## Fleet / UI

- thor Hub の Runs（Fleet ON）から **winpc が見える**ようにした（`hosts.yaml` + Port 2222 + deploy key）。
- Discord 通知は `PARC · <machine>` + `machine=` 行で実行マシンが分かる。

## ディスク・パス（覚書）

| マシン | experiments |
|--------|-------------|
| winpc | `/home/kevin/Matsuo/robot/LIBERO-plus/parc/experiments` |
| thor | `/mnt/sda/parc_libero_plus/experiments`（symlink / paths） |
| nuc | `/home/kevin/Matsuo/LIBERO-plus/parc/experiments`（`robot/` 無し） |

大きな ckpt のマシン間コピーは rclone / scp。Git には載せない。
