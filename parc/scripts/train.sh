#!/usr/bin/env bash
# 親ディレクトリの学習用 venv で学習を実行する。
# - Thor: Matsuo/robot/.venv（既定: PARC/../..）
# - Nuc 等: PARC_ROBOT_ROOT で上書き可。無い場合は PARC/../..
set -euo pipefail
PARC="$(cd "$(dirname "$0")/.." && pwd)"
LIBERO_PLUS="$(cd "$PARC/.." && pwd)"
if [[ -n "${PARC_ROBOT_ROOT:-}" ]]; then
  ROBOT="$(cd "$PARC_ROBOT_ROOT" && pwd)"
else
  ROBOT="$(cd "$PARC/../.." && pwd)"
fi

if [[ ! -x "$ROBOT/.venv/bin/python" ]]; then
  echo "robot venv not found: $ROBOT/.venv" >&2
  echo "hint: create it or set PARC_ROBOT_ROOT to the dir that contains .venv" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$ROBOT/.venv/bin/activate"
if [[ -f "$ROBOT/scripts/thor_cuda_env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROBOT/scripts/thor_cuda_env.sh"
fi

for d in \
  /usr/lib/wsl/lib \
  /usr/local/lib/ollama/cuda_v12 \
  /usr/local/cuda-12.6/targets/sbsa-linux/lib \
  /usr/local/cuda-12.9/targets/sbsa-linux/lib \
  /usr/local/cuda-12.9/targets/x86_64-linux/lib
do
  if [[ -d "$d" ]]; then
    export LD_LIBRARY_PATH="$d${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  fi
done

export MUJOCO_GL="${MUJOCO_GL:-egl}"
# マシン固有: 未設定ならホーム配下（Nuc）/ 従来 Thor パス
if [[ -z "${HF_HOME:-}" ]]; then
  if [[ -d /mnt/sda/huggingface ]]; then
    export HF_HOME=/mnt/sda/huggingface
  else
    export HF_HOME="${HOME}/.cache/huggingface"
  fi
fi
export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_HOME/hub}"
export PYTHONPATH="$PARC/src:$LIBERO_PLUS${PYTHONPATH:+:$PYTHONPATH}"

cd "$PARC"
echo "[parc-train] robot=$ROBOT"
echo "[parc-train] HF_HOME=$HF_HOME"
python -c "import torch; print('cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

CFG="${1:-configs/experiments/smolvla_ft_smoke.yaml}"
if [[ $# -gt 0 ]]; then shift; fi

exec python -m parc.cli train --config "$CFG" "$@"
