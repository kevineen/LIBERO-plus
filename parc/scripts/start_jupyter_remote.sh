#!/usr/bin/env bash
# JupyterLab / Notebook を LAN 公開。別 PC からは SSH トンネル推奨。
#
# 推奨（別 PC → winpc WSL は Port 2222）:
#   ssh -L 8888:127.0.0.1:8888 kevin@192.168.1.14 -p 2222
#   ブラウザ: http://127.0.0.1:8888/?token=...
#
# トークンなし（LAN 内一時利用のみ。作業後は止める）:
#   PARC_JUPYTER_NO_AUTH=1 bash scripts/start_jupyter_remote.sh
#
# WSL2 を別 PC から直接開く場合は Windows portproxy + ファイアウォールが必要
# （手順: docs/08_remote_and_ui.md）。
#
# 注意: `jupyter notebook --host 0.0.0.0` は無効。必ず `--ip=` を使う。
set -euo pipefail
PARC="$(cd "$(dirname "$0")/.." && pwd)"
ROBOT="$(cd "$PARC/../.." && pwd)"
PORT="${1:-${PARC_JUPYTER_PORT:-8888}}"
IP="${PARC_JUPYTER_IP:-0.0.0.0}"
NO_AUTH="${PARC_JUPYTER_NO_AUTH:-0}"

if [[ -x "$ROBOT/.venv/bin/jupyter-lab" ]]; then
  JUPYTER="$ROBOT/.venv/bin/jupyter-lab"
elif command -v jupyter-lab >/dev/null 2>&1; then
  JUPYTER="$(command -v jupyter-lab)"
elif [[ -x "$ROBOT/.venv/bin/jupyter-notebook" ]]; then
  JUPYTER="$ROBOT/.venv/bin/jupyter-notebook"
elif command -v jupyter-notebook >/dev/null 2>&1; then
  JUPYTER="$(command -v jupyter-notebook)"
else
  echo "jupyter-lab / jupyter-notebook が見つかりません。robot venv に入れてください:" >&2
  echo "  source $ROBOT/.venv/bin/activate && uv pip install jupyterlab" >&2
  exit 1
fi

export PYTHONPATH="$PARC/src:$PARC/..${PYTHONPATH:+:$PYTHONPATH}"
cd "$PARC"

echo "[parc-jupyter] $JUPYTER"
echo "[parc-jupyter] root=$PARC"
echo "[parc-jupyter] http://$IP:$PORT  (prefer SSH tunnel to localhost)"

ARGS=(
  --no-browser
  --ip="$IP"
  --port="$PORT"
  --ServerApp.root_dir="$PARC"
  --ServerApp.allow_origin='*'
  --ServerApp.allow_remote_access=True
)

# Jupyter Server 2 / Notebook 7: token だけ空にするとログイン画面が出て
# invalid credentials になる。認証無効化には IdentityProvider + allow_unauthenticated が必要。
if [[ "$NO_AUTH" == "1" || "$NO_AUTH" == "true" || "$NO_AUTH" == "yes" ]]; then
  echo "[parc-jupyter] WARNING: authentication disabled (PARC_JUPYTER_NO_AUTH=1)"
  ARGS+=(
    --IdentityProvider.token=''
    --ServerApp.password=''
    --ServerApp.allow_unauthenticated_access=True
  )
fi

exec "$JUPYTER" "${ARGS[@]}"
