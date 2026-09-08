#!/bin/bash
#SBATCH --job-name=molmoact2_500eps_endeffector_trace
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=4
#SBATCH --cpus-per-task=288
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --output=/projects/u6ph/jtiensmith.u6ph/logs/%x_%j.out
#SBATCH --error=/projects/u6ph/jtiensmith.u6ph/logs/%x_%j.err

set -euo pipefail

PROJECT_ROOT="${PROJECTDIR:?PROJECTDIR is not set}/${USER:?USER is not set}"

export LEROBOT_ROOT="$PROJECT_ROOT/lerobot_v060"
export MINIFORGE_ROOT="$PROJECT_ROOT/miniforge3"
export CONDA_ENVS_PATH="$PROJECT_ROOT/conda_envs"

# Activate LeRobot v0.6.0
source "$MINIFORGE_ROOT/etc/profile.d/conda.sh"
conda activate lerobot_v060
cd "$LEROBOT_ROOT"

# Hugging Face and LeRobot storage
export HF_HOME="$PROJECT_ROOT/hf_cache"
export HF_HUB_CACHE="$HF_HOME/hub"
export HF_DATASETS_CACHE="$HF_HOME/datasets"
export HF_LEROBOT_HOME="$PROJECT_ROOT/lerobot_data"

OUTPUT_ROOT="$PROJECT_ROOT/outputs"

mkdir -p \
  "$HF_HUB_CACHE" \
  "$HF_DATASETS_CACHE" \
  "$HF_LEROBOT_HOME" \
  "$OUTPUT_ROOT"

# Fresh run or resume
if [[ -n "${RESUME_OUTPUT_DIR:-}" ]]; then
  OUTPUT_DIR="$RESUME_OUTPUT_DIR"
  RUN_ID="$(basename "$OUTPUT_DIR")"
  RESUME_CONFIG="$OUTPUT_DIR/checkpoints/last/pretrained_model/train_config.json"

  if [[ ! -f "$RESUME_CONFIG" ]]; then
    echo "Resume checkpoint not found: $RESUME_CONFIG" >&2
    exit 1
  fi

  START_ARGS=(
    --resume=true
    "--config_path=$RESUME_CONFIG"
  )
  MODE="resume"
else
  RUN_ID="${SLURM_JOB_NAME}_${SLURM_JOB_ID}"
  OUTPUT_DIR="$OUTPUT_ROOT/$RUN_ID"

  if [[ -e "$OUTPUT_DIR" ]]; then
    echo "Fresh output directory already exists: $OUTPUT_DIR" >&2
    exit 1
  fi

  # Generic multi-embodiment checkpoint, not the SO-specific fine-tune
  START_ARGS=(
    --policy.checkpoint_path=allenai/MolmoAct2
  )
  MODE="fresh"
fi

# W&B storage
WANDB_ROOT="$PROJECT_ROOT/wandb_cache/$RUN_ID"

mkdir -p \
  "$WANDB_ROOT/data" \
  "$WANDB_ROOT/cache" \
  "$WANDB_ROOT/artifacts" \
  "$WANDB_ROOT/runs"

export WANDB_DATA_DIR="$WANDB_ROOT/data"
export WANDB_CACHE_DIR="$WANDB_ROOT/cache"
export WANDB_ARTIFACT_DIR="$WANDB_ROOT/artifacts"
export WANDB_DIR="$WANDB_ROOT/runs"
export WANDB_RUN_ID="$RUN_ID"
export WANDB_RESUME=allow

# Per-job temporary storage.
# Use SCRATCHDIR because LOCALDIR has produced permission failures in batch jobs.
ORIGINAL_LOCALDIR="${LOCALDIR:-unset}"

JOB_TMP="${SCRATCHDIR:?SCRATCHDIR is not set}/lerobot_job_tmp/molmoact2_${SLURM_JOB_ID}"
mkdir -p "$JOB_TMP"
chmod 700 "$JOB_TMP"

# Critical: packages that reconstruct paths from LOCALDIR will now also
# resolve to this known-writable directory.
export LOCALDIR="$JOB_TMP"
export TMPDIR="$JOB_TMP"
export TEMP="$JOB_TMP"
export TMP="$JOB_TMP"

export XDG_CACHE_HOME="$JOB_TMP/xdg_cache"
export TORCHINDUCTOR_CACHE_DIR="$JOB_TMP/torchinductor"
export TRITON_CACHE_DIR="$JOB_TMP/triton"
export CUDA_CACHE_PATH="$JOB_TMP/cuda_cache"
export TORCH_EXTENSIONS_DIR="$JOB_TMP/torch_extensions"
export PYTORCH_KERNEL_CACHE_PATH="$JOB_TMP/pytorch_kernels"

# Prevent packages installed in ~/.local from modifying the conda environment.
export PYTHONNOUSERSITE=1

mkdir -p \
  "$XDG_CACHE_HOME" \
  "$XDG_CACHE_HOME/torch/kernels" \
  "$TORCHINDUCTOR_CACHE_DIR" \
  "$TRITON_CACHE_DIR" \
  "$CUDA_CACHE_PATH" \
  "$TORCH_EXTENSIONS_DIR" \
  "$PYTORCH_KERNEL_CACHE_PATH"

echo "Original LOCALDIR:       $ORIGINAL_LOCALDIR"
echo "Effective LOCALDIR:      $LOCALDIR"
echo "TMPDIR:                  $TMPDIR"
echo "TorchInductor cache:     $TORCHINDUCTOR_CACHE_DIR"

cleanup() {
  if [[ -n "${JOB_TMP:-}" && -d "$JOB_TMP" ]]; then
    rm -rf -- "$JOB_TMP"
  fi
}
trap cleanup EXIT

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PYTHONUNBUFFERED=1

# Dataset/model configuration
DATASET_REPO="mattpidden/500eps-endeffector-trace-dataset"
DATASET_REVISION="1b03652351fcc49bca0d12a0da66b8843e05fe06"
MODEL_REPO="justintiensmith/molmoact2_500eps_endeffector_trace"
MODEL_REVISION="e432d85f6e039edca44afb93c262f3084ab72a9c"

TOTAL_FRAMES=137695
NUM_GPUS=4

# LeRobot interprets batch_size per process/GPU.
BATCH_SIZE_PER_GPU="${BATCH_SIZE_PER_GPU:-24}"
GLOBAL_BATCH_SIZE=$(( NUM_GPUS * BATCH_SIZE_PER_GPU ))

EPOCHS="${EPOCHS:-28}"
STEPS_PER_EPOCH=$(( (TOTAL_FRAMES + GLOBAL_BATCH_SIZE - 1) / GLOBAL_BATCH_SIZE ))
FULL_STEPS=$(( EPOCHS * STEPS_PER_EPOCH ))

# STEPS_OVERRIDE is only for short smoke tests.
# Leave it unset for every job in the full chained run so the
# full-run learning-rate schedule remains consistent.
if [[ -n "${STEPS_OVERRIDE:-}" ]]; then
  STEPS="$STEPS_OVERRIDE"
else
  STEPS="$FULL_STEPS"
fi

CHECKPOINT_EPOCHS="${CHECKPOINT_EPOCHS:-1}"
SAVE_FREQ=$(( CHECKPOINT_EPOCHS * STEPS_PER_EPOCH ))

NUM_WORKERS_PER_GPU="${NUM_WORKERS_PER_GPU:-8}"
LOG_FREQ="${LOG_FREQ:-100}"
WANDB_ENABLE="${WANDB_ENABLE:-true}"
PUSH_TO_HUB="${PUSH_TO_HUB:-true}"
SAVE_CHECKPOINT="${SAVE_CHECKPOINT:-true}"
WANDB_PROJECT="${WANDB_PROJECT:-lerobot}"

TRAIN_EXE="$(command -v lerobot-train)"
ACCELERATE_EXE="$(command -v accelerate)"

echo "Mode:                   $MODE"
echo "Run:                    $RUN_ID"
echo "Output:                 $OUTPUT_DIR"
echo "Dataset revision:       $DATASET_REVISION"
echo "GPUs:                   $NUM_GPUS"
echo "Batch per GPU:          $BATCH_SIZE_PER_GPU"
echo "Global batch:           $GLOBAL_BATCH_SIZE"
echo "Frames:                 $TOTAL_FRAMES"
echo "Steps per epoch:        $STEPS_PER_EPOCH"
echo "Full target steps:      $FULL_STEPS"
echo "This job stops at:      $STEPS"
echo "Checkpoint frequency:   $SAVE_FREQ steps"
echo "Workers:                $NUM_WORKERS_PER_GPU per GPU"

echo "Testing cache configuration with: $(command -v python)"

python - <<'PY'
import os
from pathlib import Path

expected = Path(os.environ["TORCHINDUCTOR_CACHE_DIR"])
print("Python LOCALDIR:", os.environ.get("LOCALDIR"))
print("Python TMPDIR:", os.environ.get("TMPDIR"))
print("Python TORCHINDUCTOR_CACHE_DIR:", expected)

expected.mkdir(parents=True, exist_ok=True)
probe = expected / "write_test"
probe.write_text("ok")
probe.unlink()

# Reproduce the import path that previously crashed Accelerate.
import torch._dynamo.package
from torch._inductor.runtime.cache_dir_utils import cache_dir

resolved = Path(cache_dir())
print("PyTorch resolved cache:", resolved)

assert resolved == expected, (resolved, expected)
print("Torch cache preflight: OK")
PY

nvidia-smi --list-gpus

# The sbatch script is already running on the allocated compute node.
# Accelerate launches the four local GPU workers.
"$ACCELERATE_EXE" launch \
  --multi_gpu \
  --num_machines=1 \
  --num_processes="$NUM_GPUS" \
  --mixed_precision=bf16 \
  --dynamo_backend=no \
  "$TRAIN_EXE" \
  "${START_ARGS[@]}" \
  --dataset.repo_id="$DATASET_REPO" \
  --dataset.revision="$DATASET_REVISION" \
  --dataset.video_backend=pyav \
  --dataset.image_transforms.enable=false \
  --dataset.eval_split=0.0 \
  --policy.type=molmoact2 \
  --policy.checkpoint_revision="$MODEL_REVISION" \
  --policy.normalization_mapping='{"ACTION":"MIN_MAX","STATE":"MIN_MAX","VISUAL":"IDENTITY"}' \
  --policy.input_features='{"observation.images.middle":{"type":"VISUAL","shape":[3,480,640]},"observation.images.wrist":{"type":"VISUAL","shape":[3,480,640]},"observation.state":{"type":"STATE","shape":[6]}}' \
  --policy.image_keys='["observation.images.middle","observation.images.wrist"]' \
  --policy.setup_type="single so100/so101 robotic arm in molmoact2" \
  --policy.control_mode="absolute joint pose" \
  --policy.device=cuda \
  --policy.action_mode=continuous \
  --policy.inference_action_mode=continuous \
  --policy.chunk_size=30 \
  --policy.n_action_steps=30 \
  --policy.model_dtype=bfloat16 \
  --policy.num_flow_timesteps=8 \
  --policy.gradient_checkpointing=true \
  --policy.freeze_embedding=true \
  --policy.normalize_gripper=true \
  --policy.normalize_language=true \
  --policy.train_action_expert_only=false \
  --policy.enable_lora_vlm=false \
  --policy.enable_lora_action_expert=false \
  --policy.enable_knowledge_insulation=false \
  --policy.optimizer_lr=1e-5 \
  --policy.optimizer_vit_lr=5e-6 \
  --policy.optimizer_connector_lr=5e-6 \
  --policy.optimizer_action_expert_lr=5e-5 \
  --policy.optimizer_grad_clip_norm=1.0 \
  --policy.scheduler_warmup_steps=200 \
  --policy.scheduler_decay_steps="$FULL_STEPS" \
  --policy.scheduler_decay_lr=1e-6 \
  --output_dir="$OUTPUT_DIR" \
  --job_name="$RUN_ID" \
  --seed=1000 \
  --steps="$STEPS" \
  --batch_size="$BATCH_SIZE_PER_GPU" \
  --num_workers="$NUM_WORKERS_PER_GPU" \
  --log_freq="$LOG_FREQ" \
  --env_eval_freq=0 \
  --eval_steps=0 \
  --save_checkpoint="$SAVE_CHECKPOINT" \
  --save_freq="$SAVE_FREQ" \
  --save_checkpoint_to_hub=false \
  --wandb.enable="$WANDB_ENABLE" \
  --wandb.project="$WANDB_PROJECT" \
  --wandb.disable_artifact=true \
  --policy.repo_id="$MODEL_REPO" \
  --policy.push_to_hub="$PUSH_TO_HUB"
