#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3}"
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"

NUM_GPUS=4
PER_GPU_BATCH_SIZE=1
GRADIENT_ACCUMULATION_STEPS=8
GLOBAL_BATCH_SIZE=$((NUM_GPUS * PER_GPU_BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS))
EPOCHS="${EPOCHS:-12}"

RUN_NAME="${RUN_NAME:-lingbot_va_so101_native_fsdp_v1}"
DERIVED_DATASET="${DERIVED_DATASET:-/vol/dissolve/justin/lerobot_data_derived/lingbot_va_reasoning_15fps_256}"
UPSTREAM_DIR="${UPSTREAM_DIR:-/vol/dissolve/justin/src/lingbot-va}"
BASE_MODEL_DIR="${BASE_MODEL_DIR:-/vol/dissolve/justin/models/lingbot-va-base-flex}"
OUTPUT_DIR="${OUTPUT_DIR:-/vol/dissolve/justin/outputs/${RUN_NAME}}"
MASTER_PORT="${MASTER_PORT:-29501}"

CONDA_BASE="${CONDA_BASE:-/vol/dissolve/justin/miniforge3}"
UPSTREAM_CONDA_ENV="${UPSTREAM_CONDA_ENV:-lingbot_va_upstream}"
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate "${UPSTREAM_CONDA_ENV}"

if [[ ! -f "${DERIVED_DATASET}/READY.json" ]]; then
  echo "ERROR: Derived cache is incomplete: ${DERIVED_DATASET}/READY.json is missing." >&2
  exit 1
fi
if [[ ! -f "${BASE_MODEL_DIR}/transformer/config.json" ]]; then
  echo "ERROR: BASE_MODEL_DIR is not a local LingBot-VA model: ${BASE_MODEL_DIR}" >&2
  exit 1
fi
if [[ "$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["attn_mode"])' "${BASE_MODEL_DIR}/transformer/config.json")" != "flex" ]]; then
  echo "ERROR: ${BASE_MODEL_DIR}/transformer/config.json must have attn_mode=flex." >&2
  echo "Create a non-destructive view with make_flex_training_model_view.py." >&2
  exit 1
fi

python "${SCRIPT_DIR}/install_upstream_adapter.py" --upstream-dir "${UPSTREAM_DIR}"

read -r TRAIN_SEGMENTS VALIDATION_SEGMENTS < <(
  python - "${DERIVED_DATASET}/manifest.jsonl" <<'PY'
import json
import sys

counts = {"train": 0, "validation": 0}
with open(sys.argv[1], encoding="utf-8") as stream:
    for line in stream:
        if line.strip():
            split = json.loads(line).get("split", "train")
            counts[split] = counts.get(split, 0) + 1
print(counts.get("train", 0), counts.get("validation", 0))
PY
)

if (( TRAIN_SEGMENTS <= 0 )); then
  echo "ERROR: The derived manifest has no training segments." >&2
  exit 1
fi
STEPS_PER_EPOCH=$(((TRAIN_SEGMENTS + GLOBAL_BATCH_SIZE - 1) / GLOBAL_BATCH_SIZE))
FULL_TRAINING_STEPS=$((EPOCHS * STEPS_PER_EPOCH))

if [[ "${THROUGHPUT_PROBE:-0}" == "1" ]]; then
  NUM_STEPS="${PROBE_STEPS:-50}"
  SAVE_INTERVAL="${PROBE_SAVE_INTERVAL:-25}"
  RUN_NAME="${RUN_NAME}_probe${NUM_STEPS}"
  OUTPUT_DIR="${OUTPUT_DIR}_probe${NUM_STEPS}"
else
  NUM_STEPS="${NUM_STEPS_OVERRIDE:-${FULL_TRAINING_STEPS}}"
  SAVE_INTERVAL="${SAVE_INTERVAL_OVERRIDE:-${STEPS_PER_EPOCH}}"
fi

export LINGBOT_DATASET_PATH="${DERIVED_DATASET}"
export LINGBOT_BASE_MODEL_PATH="${BASE_MODEL_DIR}"
export LINGBOT_NUM_STEPS="${NUM_STEPS}"
export LINGBOT_SAVE_INTERVAL="${SAVE_INTERVAL}"
export LINGBOT_EVAL_INTERVAL="${EVAL_INTERVAL:-${SAVE_INTERVAL}}"
export LINGBOT_EVAL_BATCHES="${EVAL_BATCHES:-16}"
export LINGBOT_LOAD_WORKERS="${LOAD_WORKERS:-4}"
export LINGBOT_ENABLE_WANDB="${WANDB_ENABLE:-0}"
export LINGBOT_RUN_NAME="${RUN_NAME}"
export WANDB_PROJECT="${WANDB_PROJECT:-VLA_Reasoning}"

if [[ "${LINGBOT_ENABLE_WANDB}" == "1" && -z "${WANDB_API_KEY:-}" ]]; then
  echo "ERROR: WANDB_ENABLE=1 requires WANDB_API_KEY." >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"
cp "${DERIVED_DATASET}/dataset_info.json" "${OUTPUT_DIR}/dataset_info.json"
cp "${DERIVED_DATASET}/READY.json" "${OUTPUT_DIR}/derived_dataset_READY.json"

echo "Training LingBot-VA with native upstream FSDP"
echo "Upstream: ${UPSTREAM_DIR}"
echo "Derived dataset: ${DERIVED_DATASET}"
echo "Segments: ${TRAIN_SEGMENTS} train, ${VALIDATION_SEGMENTS} validation"
echo "GPUs: ${NUM_GPUS}; batch/GPU: ${PER_GPU_BATCH_SIZE}; accumulation: ${GRADIENT_ACCUMULATION_STEPS}"
echo "Effective global batch: ${GLOBAL_BATCH_SIZE}"
echo "Steps/segment epoch: ${STEPS_PER_EPOCH}"
echo "Requested epochs: ${EPOCHS}; full-run steps: ${FULL_TRAINING_STEPS}"
echo "This run: ${NUM_STEPS} steps; save/eval every ${SAVE_INTERVAL} steps"
echo "Output: ${OUTPUT_DIR}"

cd "${UPSTREAM_DIR}"
python -m torch.distributed.run \
  --nproc_per_node="${NUM_GPUS}" \
  --master_port="${MASTER_PORT}" \
  --local-ranks-filter=0 \
  --tee=3 \
  -m wan_va.train \
  --config-name=so101_reasoning_train \
  --save-root="${OUTPUT_DIR}"
