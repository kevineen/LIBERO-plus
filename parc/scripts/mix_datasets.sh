#!/usr/bin/env bash
# 親 Matsuo/robot/.venv（lerobot 入り）で dataset mix を実行する。
# parc の薄い .venv には lerobot が無い。
set -euo pipefail
PARC="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -n "${PARC_ROBOT_ROOT:-}" ]]; then
  ROBOT="$(cd "$PARC_ROBOT_ROOT" && pwd)"
else
  ROBOT="$(cd "$PARC/../.." && pwd)"
fi

if [[ ! -x "$ROBOT/.venv/bin/python" ]]; then
  echo "robot venv not found: $ROBOT/.venv" >&2
  echo "hint: set PARC_ROBOT_ROOT to the dir that contains .venv" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$ROBOT/.venv/bin/activate"

if [[ -f "$PARC/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PARC/.env.local"
  set +a
fi

export PYTHONPATH="$PARC/src${PYTHONPATH:+:$PYTHONPATH}"
cd "$PARC"
exec python -m parc.cli mix-datasets "$@"
