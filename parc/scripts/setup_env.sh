#!/usr/bin/env bash
# LIBERO-plus の assets を正しい場所へ配置し、~/.libero/config.yaml を書き換える。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PARC="$(cd "$(dirname "$0")/.." && pwd)"
ASSETS_DST="$ROOT/libero/libero/assets"
NESTED="$ROOT/libero/libero/inspire/hdd/project/embodied-multimodality/public/syfei/libero_new/release/dataset/LIBERO-plus-0/assets"

echo "[parc] LIBERO-plus root: $ROOT"

# 1) 誤って深いパスに展開された assets を正規位置へ
if [[ -d "$NESTED" && ! -e "$ASSETS_DST" ]]; then
  echo "[parc] moving nested assets → $ASSETS_DST"
  mv "$NESTED" "$ASSETS_DST"
elif [[ -d "$NESTED" && -d "$ASSETS_DST" ]]; then
  echo "[parc] both nested and dest assets exist; leaving as-is"
elif [[ -L "$ASSETS_DST" || -d "$ASSETS_DST" ]]; then
  echo "[parc] assets already present: $ASSETS_DST"
else
  echo "[parc] assets missing. Download assets.zip from HF and extract to:"
  echo "       $ASSETS_DST"
  echo "  hf download --repo-type dataset Sylvest/LIBERO-plus assets.zip --local-dir $PARC/data"
fi

# 2) parc パッケージ install（PyYAML 等が必要なので、パス設定より先に）
cd "$PARC"
if command -v uv >/dev/null 2>&1; then
  uv sync
  echo "[parc] uv sync done. Activate with: source $PARC/.venv/bin/activate"
else
  python3 -m pip install -e "$PARC"
fi

# 3) ~/.libero/config.yaml をこのリポジトリに向ける（venv / uv 優先）
if [[ -x "$PARC/.venv/bin/python" ]]; then
  "$PARC/.venv/bin/python" "$PARC/scripts/configure_libero_paths.py"
elif command -v uv >/dev/null 2>&1; then
  (cd "$PARC" && uv run python scripts/configure_libero_paths.py)
else
  python3 "$PARC/scripts/configure_libero_paths.py"
fi

# 4) 親 LIBERO-plus を editable で入れる（parc venv がある場合）
if [[ -x "$PARC/.venv/bin/pip" ]]; then
  "$PARC/.venv/bin/pip" install -e "$ROOT" || true
fi

echo "[parc] setup finished."
echo "  - パス確認: uv run parc-smoke --skip-env"
echo "  - 学習 dry-run: uv run parc-train -c configs/experiments/smolvla_ft.yaml"
echo "  - 評価: ./scripts/parc.sh eval -c configs/experiments/smoke_random.yaml"
echo
echo "[parc] tip: robosuite 1.4 には mujoco==3.1.1 前後が必要なことがあります。"
echo "  uv pip install --python ../.venv/bin/python 'mujoco==3.1.1'"

