#!/bin/bash
set -euo pipefail

RUN_NAME="${RUN_NAME:-lingbot_va_multi_gpu_v1}"

export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3}"
export HF_LEROBOT_HOME="/vol/dissolve/justin/lerobot_data"
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

NUM_GPUS="${NUM_GPUS:-4}"
# LingBot-VA is a 5B video model. Start at one clip per GPU, then increase only
# after a smoke test shows sufficient VRAM headroom.
PER_GPU_BATCH_SIZE="${PER_GPU_BATCH_SIZE:-1}"
GLOBAL_BATCH_SIZE=$((NUM_GPUS * PER_GPU_BATCH_SIZE))

EPOCHS="${EPOCHS:-12}"
TOTAL_FRAMES=570386

if (( NUM_GPUS < 1 || PER_GPU_BATCH_SIZE < 1 || EPOCHS < 1 )); then
  echo "ERROR: NUM_GPUS, PER_GPU_BATCH_SIZE, and EPOCHS must all be positive" >&2
  exit 1
fi

# LeRobot's batch_size is per process/GPU. One distributed optimizer step sees
# NUM_GPUS * PER_GPU_BATCH_SIZE samples.
STEPS_PER_EPOCH=$(((TOTAL_FRAMES + GLOBAL_BATCH_SIZE - 1) / GLOBAL_BATCH_SIZE))
FULL_STEPS=$((EPOCHS * STEPS_PER_EPOCH))

# Optional for a short launch test. Use a separate run name so its output does
# not collide with the full run, for example:
# RUN_NAME=lingbot_va_smoke STEPS_OVERRIDE=20 ./this_script.sh
STEPS="${STEPS_OVERRIDE:-$FULL_STEPS}"

# Save after each complete pass over the dataset. LeRobot also saves at STEPS,
# so a smoke test still writes a final checkpoint.
SAVE_FREQ="${STEPS_PER_EPOCH}"

DATASET_REPO="justintiensmith/VLA_Reasoning_Training_Dataset_1200_Trimmed_Start_5_Frame"
DATASET_REVISION="c1231a8f2b282b3f875fc898dced9ebf5574b903"

BASE_MODEL="${BASE_MODEL:-lerobot/lingbot_va_base}"
MODEL_REPO="justintiensmith/${RUN_NAME}"
OUTPUT_DIR="/vol/dissolve/justin/outputs/${RUN_NAME}"

# The dataset stores five absolute arm-joint positions followed by the gripper.
# LingBot-VA's fixed 30-channel schema assigns left-arm joints to 14-20 and the
# left gripper to 28, so these six dataset columns map to the channels below.
ACTION_CHANNEL_IDS='[14,15,16,17,18,28]'
CAMERA_KEYS='["observation.images.middle","observation.images.wrist"]'

# LoRA is required on typical 24-32 GB GPUs. LingBot-VA has no policy-specific
# default PEFT targets in this checkout, so target every linear layer explicitly.
# Fully train the small action input/output projections because the selected
# joint channels were not used by the released LingBot-VA checkpoints.
LORA_R="${LORA_R:-16}"
LORA_ALPHA="${LORA_ALPHA:-16}"
LEARNING_RATE="${LEARNING_RATE:-1e-5}"
TEXT_ENCODER_DEVICE="${TEXT_ENCODER_DEVICE:-cpu}"

echo "Training LingBot-VA with DDP + LoRA"
echo "Base model: ${BASE_MODEL}"
echo "Dataset: ${DATASET_REPO}@${DATASET_REVISION}"
echo "Frames: ${TOTAL_FRAMES}"
echo "GPUs: ${NUM_GPUS}"
echo "Batch size per GPU: ${PER_GPU_BATCH_SIZE}"
echo "Global batch size: ${GLOBAL_BATCH_SIZE}"
echo "Epochs: ${EPOCHS}"
echo "Steps per epoch: ${STEPS_PER_EPOCH}"
echo "Full target steps: ${FULL_STEPS}"
echo "This launch stops at: ${STEPS}"
echo "Save frequency: ${SAVE_FREQ}"
echo "Camera order: ${CAMERA_KEYS}"
echo "Action-channel mapping: ${ACTION_CHANNEL_IDS}"
echo "Text encoder device: ${TEXT_ENCODER_DEVICE}"

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

# The PID prevents two launches with the same run name sharing a temp directory.
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

if ! python -c 'import diffusers, peft, transformers; from lerobot.policies.lingbot_va.configuration_lingbot_va import LingBotVAConfig; from torch.nn.attention.flex_attention import flex_attention' >/dev/null 2>&1; then
  echo 'ERROR: LingBot-VA training dependencies are missing.' >&2
  echo 'Install this LeRobot checkout with: pip install -e ".[training,lingbot_va,peft]"' >&2
  exit 1
fi

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
  --dataset.eval_split=0.0 \
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
  --policy.repo_id="${MODEL_REPO}" \
  --policy.push_to_hub=true \
  --peft.method_type=LORA \
  --peft.target_modules=all-linear \
  --peft.full_training_modules='["action_embedder","action_proj_out"]' \
  --peft.r="${LORA_R}" \
  --peft.lora_alpha="${LORA_ALPHA}" \
  --seed=42 \
  --batch_size="${PER_GPU_BATCH_SIZE}" \
  --steps="${STEPS}" \
  --num_workers=4 \
  --prefetch_factor=2 \
  --persistent_workers=true \
  --save_checkpoint=true \
  --save_freq="${SAVE_FREQ}" \
  --save_checkpoint_to_hub=false \
  --use_policy_training_preset=true \
  --env_eval_freq=0 \
  --eval_steps=0 \
  --log_freq=10 \
  --output_dir="${OUTPUT_DIR}" \
  --job_name="${RUN_NAME}" \
  --wandb.enable=true \
  --wandb.project=VLA_Reasoning \
  --wandb.mode=online \
  --wandb.disable_artifact=true
