#!/usr/bin/env bash
# 親 Matsuo/robot の venv で学習を実行する（Jetson Thor 向け）。
set -euo pipefail
PARC="$(cd "$(dirname "$0")/.." && pwd)"
ROBOT="$(cd "$PARC/../.." && pwd)"   # .../Matsuo/robot
LIBERO_PLUS="$(cd "$PARC/.." && pwd)"

if [[ ! -x "$ROBOT/.venv/bin/python" ]]; then
  echo "robot venv not found: $ROBOT/.venv" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$ROBOT/.venv/bin/activate"
# shellcheck disable=SC1091
source "$ROBOT/scripts/thor_cuda_env.sh"

for d in \
  /usr/local/lib/ollama/cuda_v12 \
  /usr/local/cuda-12.6/targets/sbsa-linux/lib \
  /usr/local/cuda-12.9/targets/sbsa-linux/lib
do
  if [[ -d "$d" ]]; then
    export LD_LIBRARY_PATH="$d${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  fi
done

export MUJOCO_GL="${MUJOCO_GL:-egl}"
export HF_HOME="${HF_HOME:-/mnt/sda/huggingface}"
export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_HOME/hub}"
export PYTHONPATH="$PARC/src:$LIBERO_PLUS${PYTHONPATH:+:$PYTHONPATH}"

cd "$PARC"
echo "[parc-train] robot=$ROBOT"
echo "[parc-train] HF_HOME=$HF_HOME"
python -c "import torch; print('cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

CFG="${1:-configs/experiments/smolvla_ft_smoke.yaml}"
if [[ $# -gt 0 ]]; then shift; fi

exec python -m parc.cli train --config "$CFG" "$@"
