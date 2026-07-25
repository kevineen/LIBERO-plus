#!/usr/bin/env bash
# PARC Lab Web（Next.js）を起動する。
# 別 PC からは http://<このマシンIP>:3030 へ（可能なら SSH トンネル推奨）。
set -euo pipefail
PARC="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$PARC/web"
PORT="${PARC_WEB_PORT:-3030}"
HOST="${PARC_WEB_HOST:-0.0.0.0}"

if [[ ! -d "$WEB/node_modules" ]]; then
  echo "[parc-web] yarn install..."
  (cd "$WEB" && yarn install)
fi

export PARC_ROOT="$PARC"

# .env / .env.local を読み込む（未設定キーのみ）
_load_env_file() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" == export\ * ]] && line="${line#export }"
    [[ "$line" != *=* ]] && continue
    local key="${line%%=*}"
    local val="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    val="${val#"${val%%[![:space:]]*}"}"
    val="${val%"${val##*[![:space:]]}"}"
    if [[ "${val}" == \"*\" && "${val}" == *\" ]]; then
      val="${val:1:${#val}-2}"
    elif [[ "${val}" == \'*\' && "${val}" == *\' ]]; then
      val="${val:1:${#val}-2}"
    fi
    if [[ -z "${!key+x}" || -z "${!key}" ]]; then
      export "$key=$val"
    fi
  done < "$f"
}
_load_env_file "$PARC/.env"
_load_env_file "$PARC/.env.local"

# experiments_dir: env → paths.yaml → デフォルト
if [[ -z "${PARC_EXPERIMENTS_DIR:-}" ]]; then
  PARC_EXPERIMENTS_DIR=""
  if command -v python3 >/dev/null 2>&1; then
    PARC_EXPERIMENTS_DIR="$(
      cd "$PARC" && python3 - <<'PY' 2>/dev/null
from pathlib import Path
import yaml
p = Path("configs/paths.yaml")
if p.is_file():
    d = yaml.safe_load(p.read_text()) or {}
    print(d.get("experiments_dir") or "")
PY
    )" || PARC_EXPERIMENTS_DIR=""
  fi
  if [[ -z "$PARC_EXPERIMENTS_DIR" ]]; then
    PARC_EXPERIMENTS_DIR="$PARC/experiments"
  fi
fi
export PARC_EXPERIMENTS_DIR
# 無人ループ向け既定ランチャーは queue（即 shell が欲しければ PARC_WEB_LAUNCHER=shell）
export PARC_WEB_LAUNCHER="${PARC_WEB_LAUNCHER:-queue}"
# ジョブ起動を許可する場合のみ:
#   export PARC_WEB_ALLOW_JOBS=1
export PARC_WEB_ALLOW_JOBS="${PARC_WEB_ALLOW_JOBS:-0}"

cd "$WEB"
echo "[parc-web] PARC_ROOT=$PARC_ROOT"
echo "[parc-web] experiments=$PARC_EXPERIMENTS_DIR"
echo "[parc-web] jobsAllowed=$PARC_WEB_ALLOW_JOBS"
echo "[parc-web] listen http://$HOST:$PORT"

MODE="${1:-dev}"
if [[ "$MODE" == "start" || "$MODE" == "prod" ]]; then
  yarn build
  exec yarn start --hostname "$HOST" --port "$PORT"
fi

exec yarn dev --hostname "$HOST" --port "$PORT"
