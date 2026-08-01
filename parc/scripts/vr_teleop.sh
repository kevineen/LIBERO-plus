#!/usr/bin/env bash
# VR teleop サーバ起動。
# - 既定: parc の uv 環境（--fake / プロトコル検証向け）
# - LIBERO 実環境: USE_LIBERO_VENV=1 で親 LIBERO-plus/.venv を使う
# - LeRobot 書き込み: robot venv に lerobot がある場合は PARC_ROBOT_VENV を指定可
set -euo pipefail
PARC="$(cd "$(dirname "$0")/.." && pwd)"
LIBERO_PLUS="$(cd "$PARC/.." && pwd)"
ROBOT_ROOT="$(cd "$PARC/../.." && pwd)"

cd "$PARC"

# WSL ヘッドレス描画。未設定だと MuJoCo がゴミ画素を返しテレビノイズになることがある
export MUJOCO_GL="${MUJOCO_GL:-egl}"

if [[ "${USE_LIBERO_VENV:-0}" == "1" ]]; then
  # shellcheck disable=SC1091
  source "$LIBERO_PLUS/.venv/bin/activate"
  export PYTHONPATH="${PARC}/src:${LIBERO_PLUS}:${PYTHONPATH:-}"
  exec python -m parc.cli vr-teleop "$@"
fi

if [[ -n "${PARC_ROBOT_VENV:-}" && -f "${PARC_ROBOT_VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${PARC_ROBOT_VENV}/bin/activate"
  export PYTHONPATH="${PARC}/src:${LIBERO_PLUS}:${PYTHONPATH:-}"
  exec python -m parc.cli vr-teleop "$@"
fi

# デフォルト: parc uv（フェイク／プロトコル）。実 sim は USE_LIBERO_VENV=1
exec uv run parc-vr-teleop "$@"
