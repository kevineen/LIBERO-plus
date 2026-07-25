#!/usr/bin/env bash
# Google Drive 用 rclone remote「gdrive」をヘッドレスで作る。
#
# 用途: Thor など「ブラウザ無し Linux」向け。
# WSL や手元 PC では docs/11_multi_machine.md の「authorize → トークン貼付」
# または「rclone.conf コピー」の方が確実（WSL の 127.0.0.1 は Windows と別）。
#
# Thor 例:
#   # 手元 PC（他用途の 53682 トンネルが無い状態で）
#   ssh -L 53682:127.0.0.1:53682 kevin@<thor-host>
#
#   # Thor（このスクリプト）
#   bash scripts/setup_gdrive_rclone.sh
#   → 表示された http://127.0.0.1:53682/auth?... を手元ブラウザで開く
#
# 複数 PC: 同じ Drive を共有してよい。動いているマシンの rclone.conf を
# コピーするか、各マシンで個別に authorize する。
#
set -euo pipefail

REMOTE="${PARC_RCLONE_REMOTE:-gdrive}"
CONF="${RCLONE_CONFIG:-$HOME/.config/rclone/rclone.conf}"

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone がありません。先に: curl https://rclone.org/install.sh | sudo bash" >&2
  exit 1
fi

mkdir -p "$(dirname "$CONF")"

if rclone listremotes 2>/dev/null | grep -qx "${REMOTE}:"; then
  echo "remote '${REMOTE}' は既にあります。"
  echo "接続テスト: rclone lsd ${REMOTE}:"
  rclone lsd "${REMOTE}:" | head -20
  exit 0
fi

echo "==> remote '${REMOTE}' を作成します（Google Drive）"
echo "    手元 PC で SSH トンネルを張ってから Enter:"
echo "    ssh -L 53682:127.0.0.1:53682 <user>@<this-host>"
read -r -p "トンネル準備OKなら Enter... " _

# 空の drive remote を作り、config reconnect で OAuth
rclone config create "$REMOTE" drive \
  config_is_local=false \
  scope=drive \
  >/dev/null

echo "==> ブラウザ認証を開始します（URL を手元で開いてください）"
rclone config reconnect "$REMOTE:" --auto-confirm

echo "==> 疎通確認"
rclone mkdir "${REMOTE}:PARC/ckpts" 2>/dev/null || true
rclone lsd "${REMOTE}:PARC" || rclone lsd "${REMOTE}:"

echo "OK. paths.yaml の sync.enabled: true を確認し:"
echo "  uv run parc-sync status"
echo "  uv run parc-sync upload <run_id> --dry-run"
