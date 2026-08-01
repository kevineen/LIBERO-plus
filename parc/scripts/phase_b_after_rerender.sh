#!/usr/bin/env bash
# Phase B: wait for cam_views_staging_v2 (120) → LeRobot → mix v3 → enqueue FT.
# Idempotent-ish: skips steps when outputs already exist (unless FORCE=1).
set -euo pipefail
PARC="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PARC"

STAGING="$PARC/data/datasets/cam_views_staging_v2"
CAM_OUT="$PARC/data/datasets/libero_cam_views_v2"
MIX_OUT="$PARC/data/datasets/libero_plus_cam_mix_v3"
BASE_ROOT="/mnt/b/hf/hub/lerobot/hub/datasets--lerobot--libero_plus/snapshots/f3f49f426d75030177b18778374005bc12ccd588"
CKPT="$PARC/experiments/20260730T071018Z_winpc_cbbf5c8b_smolvla_ft_libero_cam_mix_continue10k_wi/train_output/checkpoints/010000/pretrained_model"
FT_YAML="configs/experiments/smolvla_ft_libero_cam_mix_v3_from_continue10k_winpc.yaml"
LOG="$PARC/experiments/queue/phase_b_pipeline.log"
FORCE="${FORCE:-0}"

mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

echo "=== Phase B pipeline start $(date -Is) FORCE=$FORCE ==="

if [[ ! -d "$CKPT" ]]; then
  echo "ERROR: parent ckpt missing: $CKPT" >&2
  exit 1
fi

# 1) Wait for 120 npz + manifest (or process end with enough files)
echo "[1] waiting for staging ≥120 npz + manifest…"
for i in $(seq 1 200); do
  n=$(ls "$STAGING"/*.npz 2>/dev/null | wc -l)
  alive=$(pgrep -f 'rerender_camera_demos.py' >/dev/null && echo yes || echo no)
  echo "$(date +%H:%M:%S) npz=$n alive=$alive"
  if [[ -f "$STAGING/manifest.json" && "$n" -ge 120 ]]; then
    echo "staging ready"
    break
  fi
  if [[ "$alive" = "no" ]]; then
    if [[ "$n" -ge 120 ]]; then
      echo "process ended with $n npz; waiting briefly for manifest…"
      sleep 45
      [[ -f "$STAGING/manifest.json" ]] || echo "WARN: no manifest.json (continuing with $n npz)"
      break
    fi
    echo "ERROR: rerender ended with only $n npz" >&2
    exit 1
  fi
  sleep 180
done
n=$(ls "$STAGING"/*.npz 2>/dev/null | wc -l)
if [[ "$n" -lt 120 ]]; then
  echo "ERROR: only $n npz (need 120)" >&2
  exit 1
fi

# 2) staging → LeRobot
if [[ -d "$CAM_OUT/meta" && "$FORCE" != "1" ]]; then
  echo "[2] skip staging_to_lerobot (exists): $CAM_OUT"
else
  echo "[2] staging_to_lerobot → $CAM_OUT"
  set -a && source "$PARC/.env.local" && set +a
  uv run scripts/staging_to_lerobot.py \
    --staging "$STAGING" \
    --out "$CAM_OUT" \
    --repo-id local/libero_cam_views_v2 \
    --overwrite
fi

# 3) mix v3 = base180 + cam120
if [[ -f "$MIX_OUT/mix_manifest.json" && "$FORCE" != "1" ]]; then
  echo "[3] skip mix (exists): $MIX_OUT"
else
  echo "[3] mix_datasets → $MIX_OUT (base180+cam120)"
  bash scripts/mix_datasets.sh \
    --base-root "$BASE_ROOT" \
    --cam-root data/datasets/libero_cam_views_v2 \
    --cam-repo-id local/libero_cam_views_v2 \
    --base-episodes 180 \
    --cam-episodes 120 \
    --out data/datasets/libero_plus_cam_mix_v3 \
    --out-repo-id local/libero_plus_cam_mix_v3 \
    --overwrite
fi

# 4) enqueue FT if not already queued/running
set -a && source "$PARC/.env.local" && set +a
busy=$(uv run parc-queue status --limit 50 --json 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); c=d.get('counts',d) if isinstance(d,dict) else {}; print(int(c.get('queued',0))+int(c.get('running',0))+int(c.get('claimed',0)))" \
  || echo 0)
if [[ "$busy" != "0" ]]; then
  echo "[4] queue already has $busy queued/running job(s); not enqueueing again"
  uv run parc-queue status --limit 8
  exit 0
fi

echo "[4] enqueue Phase B FT"
uv run parc-enqueue \
  -c "$FT_YAML" \
  --kind train_eval \
  --notes "Phase B cam×120 mix v3 base180+cam120; continue10k→+5k lr1e-5; then thor thick+Cam" \
  --notify

uv run parc-queue status --limit 5
echo "=== Phase B pipeline done $(date -Is) ==="
