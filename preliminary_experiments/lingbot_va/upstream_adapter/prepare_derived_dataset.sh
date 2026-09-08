#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export HF_LEROBOT_HOME="${HF_LEROBOT_HOME:-/vol/dissolve/justin/lerobot_data}"
export HF_HOME="${HF_HOME:-/vol/dissolve/justin/hf_cache}"
export HF_HUB_CACHE="${HF_HUB_CACHE:-${HF_HOME}/hub}"
export HF_DATASETS_CACHE="${HF_DATASETS_CACHE:-${HF_HOME}/datasets}"

CONDA_BASE="${CONDA_BASE:-/vol/dissolve/justin/miniforge3}"
LEROBOT_CONDA_ENV="${LEROBOT_CONDA_ENV:-lerobot_v060}"
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate "${LEROBOT_CONDA_ENV}"

SOURCE_REPO_ID="${SOURCE_REPO_ID:-justintiensmith/VLA_Reasoning_Training_Dataset_1200_Trimmed_Start_5_Frame}"
SOURCE_REVISION="${SOURCE_REVISION:-c1231a8f2b282b3f875fc898dced9ebf5574b903}"
DERIVED_DATASET="${DERIVED_DATASET:-/vol/dissolve/justin/lerobot_data_derived/lingbot_va_reasoning_15fps_256}"
MODEL_PATH="${MODEL_PATH:-robbyant/lingbot-va-base}"
VALIDATION_FRACTION="${VALIDATION_FRACTION:-0.05}"
MAX_SEGMENT_SECONDS="${MAX_SEGMENT_SECONDS:-0}"

ARGS=(
  --source-repo-id "${SOURCE_REPO_ID}"
  --source-revision "${SOURCE_REVISION}"
  --output-root "${DERIVED_DATASET}"
  --model-path "${MODEL_PATH}"
  --camera-keys observation.images.middle observation.images.wrist
  --target-fps 15
  --height 256
  --width 256
  --validation-fraction "${VALIDATION_FRACTION}"
  --max-segment-seconds "${MAX_SEGMENT_SECONDS}"
  --device cuda:0
  --text-encoder-device cuda:0
  --dtype bfloat16
  --video-backend pyav
)

if [[ -n "${SOURCE_ROOT:-}" ]]; then
  ARGS+=(--source-root "${SOURCE_ROOT}")
fi
if [[ -n "${MAX_EPISODES:-}" ]]; then
  ARGS+=(--max-episodes "${MAX_EPISODES}")
fi
if [[ "${PLAN_ONLY:-0}" == "1" ]]; then
  ARGS+=(--plan-only)
fi

python "${SCRIPT_DIR}/prepare_segment_dataset.py" "${ARGS[@]}"
