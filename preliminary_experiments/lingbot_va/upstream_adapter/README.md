# Native LingBot-VA post-training for the SO-101 reasoning dataset

This bundle implements the upstream segment-level post-training recipe while keeping the source
LeRobot dataset unchanged. It is pinned to LingBot-VA commit
`7c6ffa9bfc4b83582cafc860fab4c82cc7deeeeb` so the adapter does not silently drift with upstream.

## What the derived dataset contains

`prepare_segment_dataset.py` reads the v3.0 source dataset and writes a separate cache with:

- `episodes.jsonl`: one or more `action_config` ranges per source episode;
- `manifest.jsonl`: segment paths, prompts, exact source provenance, and train/validation split;
- `segments/*.pt`: 256×256 Wan VAE latents plus normalized, aligned action tensors;
- `text_embeddings/*.pt`: one UMT5 embedding per unique task prompt;
- `empty_emb.pt`: the classifier-free-guidance empty prompt;
- `dataset_info.json` and `READY.json`: recipe/provenance and completion markers.

The camera order is `middle`, then `wrist`. Their VAE latents are concatenated left-to-right on the
latent width axis. Source actions are mapped to model channels `[0, 1, 2, 3, 4, 28]` and normalized
using source-dataset 1st/99th percentiles. The original Hub repo and local source cache are never
written by the converter.

At the default 5% episode-level validation holdout, 1,200 one-segment episodes give 1,140 training
segments. Global batch 32 therefore gives 36 optimizer steps per segment epoch and 432 steps for 12
epochs. Checkpoints and validation losses occur at steps 36, 72, ..., 432; the checkpoints nearest
200, 300, 400, and 500 are 216, 288, 396, and the final 432. With no holdout, the corresponding math
is 38 steps/epoch and 456 total steps.

## 1. Download the unchanged base model and create the flex-attention view

Run this once in any environment that provides the `hf` CLI:

```bash
hf download robbyant/lingbot-va-base \
  --local-dir /vol/dissolve/justin/models/lingbot-va-base

python scripts/lingbot_va_upstream/make_flex_training_model_view.py \
  --source /vol/dissolve/justin/models/lingbot-va-base \
  --output /vol/dissolve/justin/models/lingbot-va-base-flex
```

The `-flex` directory symlinks the large immutable weights and owns only a training-specific
`transformer/config.json`. This preserves the downloaded model with its inference attention mode.

## 2. Plan, then preprocess the derived dataset

The converter runs in the existing LeRobot environment because that environment understands the
source v3.0 layout. First verify the segment and optimizer-step counts without loading Wan models:

```bash
PLAN_ONLY=1 \
MODEL_PATH=/vol/dissolve/justin/models/lingbot-va-base \
bash scripts/lingbot_va_upstream/prepare_derived_dataset.sh
```

Then run the resumable preprocessing job on one GPU:

```bash
MODEL_PATH=/vol/dissolve/justin/models/lingbot-va-base \
bash scripts/lingbot_va_upstream/prepare_derived_dataset.sh \
  2>&1 | tee lingbot_preprocess.log
```

UMT5 and the Wan VAE are loaded sequentially on GPU 0, never together; this is appropriate for the
96 GB cards and substantially faster than CPU prompt encoding. Override the Python argument only if
the preprocessing GPU is unusually constrained.

Re-running the same command skips complete prompt and segment files. Writes are atomic, so an
interrupted partial file is not mistaken for a finished segment. To use every segment for training
and reproduce the approximately 456-step calculation, set `VALIDATION_FRACTION=0`; checkpoint
evaluation will then need real-robot rollouts or a separately held-out dataset.

Useful overrides are `DERIVED_DATASET`, `SOURCE_ROOT`, `MAX_EPISODES`, and
`MAX_SEGMENT_SECONDS`. Leaving `MAX_SEGMENT_SECONDS=0` creates one segment per episode and trims at
most seven 30-FPS source frames from the tail so every segment aligns exactly to the 8-action unit.

## 3. Prepare the pinned upstream checkout and environment

```bash
bash scripts/lingbot_va_upstream/bootstrap_upstream.sh
bash scripts/lingbot_va_upstream/create_upstream_env.sh
```

The upstream environment is deliberately separate from `lerobot_v060`: upstream pins Python 3.10,
PyTorch 2.9, Diffusers 0.36, and Transformers 4.55. The adapter removes its runtime dependency on
legacy `lerobot==0.3.3` and makes FlashAttention optional because training uses PyTorch
FlexAttention. `PYTORCH_INDEX_URL` defaults to the CUDA 12.8 wheel channel for Blackwell and can be
overridden if the host uses a different supported PyTorch build.

## 4. Run the 50-step throughput probe

```bash
WANDB_ENABLE=1 \
WANDB_API_KEY=... \
WANDB_TEAM_NAME=... \
bash scripts/lingbot_va_upstream/run_throughput_probe.sh \
  2>&1 | tee lingbot_probe50.log
```

The probe uses all four GPUs, batch 1/GPU, accumulation 8, and writes to a `_probe50` output
directory. It saves/evaluates at steps 25 and 50. The progress bar reports optimizer-step rate, so
the measured full-run estimate is approximately `probe wall time × full steps / 50`. Preprocessing
time is separate and each manifest record also records its VAE preprocessing duration.

W&B is optional; omit the three W&B variables to run offline. Do not start the full run until the
probe loss is finite, all four GPUs are busy, and step time is stable after compilation/warm-up.

## 5. Run 12 segment-level epochs

```bash
WANDB_ENABLE=1 \
WANDB_API_KEY=... \
WANDB_TEAM_NAME=... \
bash scripts/lingbot_va_upstream/train_fsdp_4gpu.sh \
  2>&1 | tee lingbot_native_fsdp_12epochs.log
```

The launcher verifies that the cache is ready, that the model config says `attn_mode=flex`, and that
the upstream checkout is at the pinned commit. It then computes steps from `manifest.jsonl`, launches
upstream FSDP with four processes, saves every segment epoch, and computes distributed validation
video/action loss at the same interval. `dataset_info.json` is copied into the output for checkpoint
normalization and camera/action provenance.

Important overrides:

- `EPOCHS=12` changes the number of segment-level passes.
- `NUM_STEPS_OVERRIDE` changes optimizer steps directly.
- `SAVE_INTERVAL_OVERRIDE` and `EVAL_INTERVAL` change checkpoint/evaluation cadence.
- `EVAL_BATCHES=16` is the maximum number of validation segments evaluated per GPU.
- `LOAD_WORKERS=4`, `MASTER_PORT`, `RUN_NAME`, and `OUTPUT_DIR` control runtime details.

Upstream checkpoints contain transformer weights but not optimizer state. A failed process should be
restarted as a new run from a chosen transformer checkpoint; it is not an exact optimizer-state
resume. Keep the epoch checkpoints until real SO-101 rollouts identify the best one—offline
flow-matching loss is useful for screening, but closed-loop task success is the deciding metric.
