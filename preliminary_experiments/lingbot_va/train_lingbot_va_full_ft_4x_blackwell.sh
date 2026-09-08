#!/bin/bash
set -euo pipefail

# Full-parameter LingBot-VA fine-tuning for 4 x RTX PRO 6000 Blackwell (96 GB).
#
# Run a memory probe before the full job, using a distinct run name:
#   RUN_NAME=lingbot_va_full_ft_smoke \
#   STEPS_OVERRIDE=20 \
#   SAVE_CHECKPOINT=false \
#   PUSH_TO_HUB=false \
#   WANDB_ENABLE=false \
#   ./train_lingbot_va_full_ft_4x_blackwell.sh

RUN_NAME="${RUN_NAME:-lingbot_v1}"

export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3}"
export HF_LEROBOT_HOME="/vol/dissolve/justin/lerobot_data"
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

NUM_GPUS="${NUM_GPUS:-4}"
PER_GPU_BATCH_SIZE="${PER_GPU_BATCH_SIZE:-1}"
GLOBAL_BATCH_SIZE=$((NUM_GPUS * PER_GPU_BATCH_SIZE))

# LingBot-VA's reported post-training recipe is step-based rather than epoch-based.
# Begin with 5K updates and extend only if held-out loss and robot rollouts improve.
TRAIN_STEPS="${STEPS_OVERRIDE:-${TRAIN_STEPS:-5000}}"
SAVE_FREQ="${SAVE_FREQ:-1000}"
EVAL_STEPS="${EVAL_STEPS:-1000}"
MAX_EVAL_SAMPLES="${MAX_EVAL_SAMPLES:-512}"
EVAL_SPLIT="${EVAL_SPLIT:-0.1}"
LOG_FREQ="${LOG_FREQ:-10}"

if (( NUM_GPUS < 1 || PER_GPU_BATCH_SIZE < 1 || TRAIN_STEPS < 1 )); then
  echo "ERROR: NUM_GPUS, PER_GPU_BATCH_SIZE, and TRAIN_STEPS must be positive" >&2
  exit 1
fi

DATASET_REPO="justintiensmith/VLA_Reasoning_Training_Dataset_1200_Trimmed_Start_5_Frame"
DATASET_REVISION="c1231a8f2b282b3f875fc898dced9ebf5574b903"
TOTAL_FRAMES=570386

BASE_MODEL="${BASE_MODEL:-lerobot/lingbot_va_base}"
MODEL_REPO="justintiensmith/${RUN_NAME}"
OUTPUT_DIR="/vol/dissolve/justin/outputs/${RUN_NAME}"

# Dataset action order:
#   shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper
# LingBot-VA channel order:
#   left joints = 14-20; left gripper = 28
ACTION_CHANNEL_IDS='[14,15,16,17,18,28]'
CAMERA_KEYS='["observation.images.middle","observation.images.wrist"]'

LEARNING_RATE="${LEARNING_RATE:-1e-5}"
WARMUP_STEPS="${WARMUP_STEPS:-200}"
TEXT_ENCODER_DEVICE="${TEXT_ENCODER_DEVICE:-cpu}"

SAVE_CHECKPOINT="${SAVE_CHECKPOINT:-true}"
PUSH_TO_HUB="${PUSH_TO_HUB:-true}"
WANDB_ENABLE="${WANDB_ENABLE:-true}"

echo "Training LingBot-VA with full-parameter DDP"
echo "Run: ${RUN_NAME}"
echo "Base model: ${BASE_MODEL}"
echo "Dataset: ${DATASET_REPO}@${DATASET_REVISION}"
echo "Dataset frames: ${TOTAL_FRAMES}"
echo "GPUs: ${NUM_GPUS}"
echo "Batch size per GPU: ${PER_GPU_BATCH_SIZE}"
echo "Global batch size: ${GLOBAL_BATCH_SIZE}"
echo "Optimizer steps: ${TRAIN_STEPS}"
echo "Checkpoint frequency: ${SAVE_FREQ}"
echo "Eval frequency: ${EVAL_STEPS}"
echo "Eval split: ${EVAL_SPLIT}"
echo "Max eval samples: ${MAX_EVAL_SAMPLES}"
echo "Camera order: ${CAMERA_KEYS}"
echo "Action-channel mapping: ${ACTION_CHANNEL_IDS}"
echo "Text encoder device: ${TEXT_ENCODER_DEVICE}"
echo "LoRA: disabled (all transformer parameters are trainable)"

WANDB_ROOT="/vol/dissolve/justin/wandb_cache/${RUN_NAME}"

mkdir -p \
  "${WANDB_ROOT}/data" \
  "${WANDB_ROOT}/cache" \
  "${WANDB_ROOT}/artifacts" \
  "${WANDB_ROOT}/runs"

export WANDB_DATA_DIR="${WANDB_ROOT}/data"
export WANDB_CACHE_DIR="${WANDB_ROOT}/cache"
export WANDB_ARTIFACT_DIR="${WANDB_ROOT}/artifacts"
export WANDB_DIR="${WANDB_ROOT}/runs"

# Isolate compilation and temporary files for this launch.
JOB_TMP="/vol/dissolve/justin/tmp/${RUN_NAME}_$$"
mkdir -p "${JOB_TMP}"

export TMPDIR="${JOB_TMP}"
export TEMP="${JOB_TMP}"
export TMP="${JOB_TMP}"
export TORCHINDUCTOR_CACHE_DIR="${JOB_TMP}/torchinductor"
export TRITON_CACHE_DIR="${JOB_TMP}/triton"
mkdir -p "${TORCHINDUCTOR_CACHE_DIR}" "${TRITON_CACHE_DIR}"

cleanup() {
  if [[ -n "${JOB_TMP:-}" && -d "${JOB_TMP}" ]]; then
    rm -rf -- "${JOB_TMP}"
  fi
}
trap cleanup EXIT

export PATH="/vol/dissolve/justin/miniforge3/bin:${PATH}"
source /vol/dissolve/justin/miniforge3/etc/profile.d/conda.sh
conda activate lerobot_v060

export HF_HOME="/vol/dissolve/justin/hf_cache"
export HF_HUB_CACHE="${HF_HOME}/hub"
export HF_DATASETS_CACHE="${HF_HOME}/datasets"
export TRANSFORMERS_CACHE="${HF_HOME}/hub"

if [[ ! -r "${HF_HOME}/token" ]]; then
  echo "ERROR: Hugging Face token file is not readable: ${HF_HOME}/token" >&2
  exit 1
fi
export HF_TOKEN="$(<"${HF_HOME}/token")"

TRAIN_ENTRYPOINT="$(command -v lerobot-train)"

if ! command -v accelerate >/dev/null 2>&1; then
  echo "ERROR: accelerate is not installed in the active environment" >&2
  exit 1
fi

if ! python -c 'import diffusers, transformers; from lerobot.policies.lingbot_va.configuration_lingbot_va import LingBotVAConfig; from torch.nn.attention.flex_attention import flex_attention' >/dev/null 2>&1; then
  echo 'ERROR: LingBot-VA training dependencies are missing.' >&2
  echo 'Install this LeRobot checkout with: pip install -e ".[training,lingbot_va]"' >&2
  exit 1
fi

echo "Detected GPUs:"
nvidia-smi \
  --query-gpu=index,name,memory.total,driver_version \
  --format=csv,noheader

accelerate launch \
  --multi_gpu \
  --num_processes="${NUM_GPUS}" \
  --num_machines=1 \
  --mixed_precision=bf16 \
  --dynamo_backend=no \
  "${TRAIN_ENTRYPOINT}" \
  --dataset.repo_id="${DATASET_REPO}" \
  --dataset.revision="${DATASET_REVISION}" \
  --dataset.video_backend=pyav \
  --dataset.image_transforms.enable=false \
  --dataset.eval_split="${EVAL_SPLIT}" \
  --policy.path="${BASE_MODEL}" \
  --policy.device=cuda \
  --policy.dtype=bfloat16 \
  --policy.attn_mode=flex \
  --policy.input_features=null \
  --policy.output_features=null \
  --policy.obs_cam_keys="${CAMERA_KEYS}" \
  --policy.camera_layout=width_concat \
  --policy.image_hflip=false \
  --policy.height=128 \
  --policy.width=128 \
  --policy.action_per_frame=4 \
  --policy.frame_chunk_size=4 \
  --policy.used_action_channel_ids="${ACTION_CHANNEL_IDS}" \
  --policy.normalization_mapping='{"VISUAL":"IDENTITY","STATE":"IDENTITY","ACTION":"QUANTILES"}' \
  --policy.text_encoder_device="${TEXT_ENCODER_DEVICE}" \
  --policy.optimizer_lr="${LEARNING_RATE}" \
  --policy.scheduler_warmup_steps="${WARMUP_STEPS}" \
  --policy.repo_id="${MODEL_REPO}" \
  --policy.push_to_hub="${PUSH_TO_HUB}" \
  --seed=42 \
  --batch_size="${PER_GPU_BATCH_SIZE}" \
  --steps="${TRAIN_STEPS}" \
  --num_workers=4 \
  --prefetch_factor=2 \
  --persistent_workers=true \
  --save_checkpoint="${SAVE_CHECKPOINT}" \
  --save_freq="${SAVE_FREQ}" \
  --save_checkpoint_to_hub=false \
  --use_policy_training_preset=true \
  --env_eval_freq=0 \
  --eval_steps="${EVAL_STEPS}" \
  --max_eval_samples="${MAX_EVAL_SAMPLES}" \
  --log_freq="${LOG_FREQ}" \
  --output_dir="${OUTPUT_DIR}" \
  --job_name="${RUN_NAME}" \
  --wandb.enable="${WANDB_ENABLE}" \
  --wandb.project=VLA_Reasoning \
  --wandb.mode=online \
  --wandb.disable_artifact=true
