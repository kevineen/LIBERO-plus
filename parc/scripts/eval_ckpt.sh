#!/usr/bin/env bash
# 親ディレクトリの学習用 venv で checkpoint 評価を実行する。
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

# Nuc 等: sudo なしで展開した ImageMagick（Wand / Sensor Noise 用）
# MAGICK_HOME だけでは PNG coder を見つけられず MissingDelegateError になるため
# CODER / CONFIGURE パスも明示する。
_IM_ROOT="${HOME}/opt/imagemagick"
_IM_USER_LIB="${_IM_ROOT}/usr/lib/x86_64-linux-gnu"
_IM_CODERS="${_IM_USER_LIB}/ImageMagick-6.9.11/modules-Q16/coders"
_IM_CONFIG="${_IM_ROOT}/etc/ImageMagick-6"
if [[ -e "${_IM_USER_LIB}/libMagickWand-6.Q16.so" ]]; then
  export MAGICK_HOME="${_IM_ROOT}/usr"
  export LD_LIBRARY_PATH="${_IM_USER_LIB}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  if [[ -d "${_IM_CODERS}" ]]; then
    export MAGICK_CODER_MODULE_PATH="${_IM_CODERS}"
  fi
  if [[ -d "${_IM_CONFIG}" ]]; then
    export MAGICK_CONFIGURE_PATH="${_IM_CONFIG}"
  fi
fi
unset _IM_ROOT _IM_USER_LIB _IM_CODERS _IM_CONFIG

export MUJOCO_GL="${MUJOCO_GL:-egl}"
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
echo "[parc-eval-ckpt] robot=$ROBOT"
python -c "import torch; print('cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

CFG="${1:-configs/experiments/smolvla_ckpt_smoke_eval.yaml}"
if [[ $# -gt 0 ]]; then shift; fi

# 既定で Discord/Slack 完了通知。抑制: PARC_EVAL_NO_NOTIFY=1 または --no-notify
NOTIFY_ARGS=(--notify)
if [[ "${PARC_EVAL_NO_NOTIFY:-0}" == "1" ]]; then
  NOTIFY_ARGS=()
fi
for _a in "$@"; do
  if [[ "$_a" == "--notify" || "$_a" == "--no-notify" ]]; then
    NOTIFY_ARGS=()
    break
  fi
done
unset _a

exec python -m parc.cli eval --config "$CFG" "${NOTIFY_ARGS[@]}" "$@"
