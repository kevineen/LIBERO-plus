#!/usr/bin/env bash
# LIBERO-plus 付属 .venv（robosuite/mujoco 入り）で parc コマンドを実行する。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PARC="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "LIBERO-plus .venv がありません: $PY" >&2
  exit 1
fi
export MUJOCO_GL="${MUJOCO_GL:-egl}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$PARC"
exec "$PY" -m parc.cli "$@"
