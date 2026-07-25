#!/usr/bin/env bash
# 誤展開された assets を正規パスへ移動（setup_env.sh から呼ばれる処理の単体版）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
python3 - <<'PY'
from pathlib import Path
root = Path(r"""$ROOT""")
# bash 展開したいので別実装
PY
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DST="$ROOT/libero/libero/assets"
SRC="$ROOT/libero/libero/inspire/hdd/project/embodied-multimodality/public/syfei/libero_new/release/dataset/LIBERO-plus-0/assets"
if [[ -d "$SRC" && ! -e "$DST" ]]; then
  mkdir -p "$(dirname "$DST")"
  mv "$SRC" "$DST"
  echo "moved → $DST"
elif [[ -e "$DST" ]]; then
  echo "already exists: $DST"
else
  echo "source not found: $SRC"
  exit 1
fi
