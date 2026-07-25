#!/usr/bin/env bash
# JupyterLab を LAN 公開（トークン必須）。別 PC からは SSH トンネル推奨。
#
# 推奨（別 PC）:
#   ssh -L 8888:127.0.0.1:8888 kevin@192.168.11.5
#   ブラウザ: http://127.0.0.1:8888/?token=...
#
# 直接公開する場合はファイアウォールとトークン管理に注意。
set -euo pipefail
PARC="$(cd "$(dirname "$0")/.." && pwd)"
ROBOT="$(cd "$PARC/../.." && pwd)"
PORT="${1:-${PARC_JUPYTER_PORT:-8888}}"
IP="${PARC_JUPYTER_IP:-0.0.0.0}"

if [[ -x "$ROBOT/.venv/bin/jupyter-lab" ]]; then
  JUPYTER="$ROBOT/.venv/bin/jupyter-lab"
elif command -v jupyter-lab >/dev/null 2>&1; then
  JUPYTER="$(command -v jupyter-lab)"
else
  echo "jupyter-lab が見つかりません。robot venv に入れてください:" >&2
  echo "  source $ROBOT/.venv/bin/activate && uv pip install jupyterlab" >&2
  exit 1
fi

export PYTHONPATH="$PARC/src:$PARC/..${PYTHONPATH:+:$PYTHONPATH}"
cd "$PARC"

echo "[parc-jupyter] $JUPYTER"
echo "[parc-jupyter] root=$PARC"
echo "[parc-jupyter] http://$IP:$PORT  (prefer SSH tunnel to localhost)"

exec "$JUPYTER" \
  --no-browser \
  --ip="$IP" \
  --port="$PORT" \
  --ServerApp.root_dir="$PARC" \
  --ServerApp.allow_origin='*' \
  --ServerApp.allow_remote_access=True
