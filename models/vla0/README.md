# VLA-0 -- Spa-Bench Epoch 12

- **Model:** [mattpidden/vla0-justin-epoch12](https://huggingface.co/mattpidden/vla0-justin-epoch12)
- **Base checkpoint:** `Qwen/Qwen2.5-VL-3B-Instruct`
- **Client framework:** custom LeRobot 0.6.0 fork
- **Robot:** SO-101, single arm
- **Checkpoint:** epoch 12
- **Policy inputs:** middle RGB, wrist RGB, six absolute joint positions
- **Policy output:** text-encoded/discretized eight-step action chunks
- **Action horizon:** 8
- **Training-data variant:** motion-trimmed episodes
- **Evaluation rollouts:** [Spa_Bench_Partial_VLA-0](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Partial_VLA-0)

## Adaptation and deployment summary

Recorded project metadata describes full fine-tuning of the Qwen backbone
without LoRA or QLoRA, min--max scaling with 1,000 action bins, AdamW with
learning rate `5e-6`, weight decay `0.01`, and cosine annealing.

The VLA-0 checkpoint runs in its own CUDA environment and exposes an HTTP
inference service. The LeRobot client captures observations, supplies the
per-episode prompt, sends requests to the service, controls the robot, and
records rollout datasets. See `software/lerobot_vla0/README.md`.

## Missing before archival

- Immutable model/base-model/training-dataset revisions.
- Original resolved training configuration and exact optimizer-update count.
- Exact software commit used by the inference service.
- Exact coverage of the partial evaluation dataset.

