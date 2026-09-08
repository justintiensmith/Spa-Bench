# GR00T-N1.7 Frozen LLM -- Spa-Bench Epoch 12

- **Model:** [justintiensmith/groot_multi_gpu_v4](https://huggingface.co/justintiensmith/groot_multi_gpu_v4)
- **Base checkpoint:** `nvidia/GR00T-N1.7-3B`
- **Framework:** LeRobot 0.6.0
- **Robot:** SO-101, single arm
- **Checkpoint:** epoch 12; current methods record step 71,304
- **Policy inputs:** middle RGB, wrist RGB, six absolute joint positions
- **Policy output:** six absolute joint-position commands
- **Action horizon:** 16
- **Training-data variant:** motion-trimmed episodes
- **Evaluation rollouts:** [Spa_Bench_Full_GR00T-N1.7_Frozen_LLM](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Full_GR00T-N1.7_Frozen_LLM)

## Adaptation summary

The language-model backbone was frozen. The visual encoder, multimodal
projector, VLLN module, and diffusion action model were updated. Recorded
project metadata specifies AdamW, learning rate `1e-4`, weight decay `1e-5`, a
5% warm-up, and cosine decay.

Raw action targets were filtered during Spa-Bench deployment using a
deterministic exponential moving average. The filter state began from the
observed joint state and reset between rollouts; the gripper was excluded.

## Terminology

Older workbooks may call this configuration `vision-only`. Spa-Bench uses
`Frozen LLM` because modules beyond the visual encoder were updated.

## Missing before archival

- Immutable model/base-model/training-dataset revisions.
- Resolved training configuration and launch command.
- Verification of the epoch-12 optimizer-update count.
- Exact deployment EMA coefficient.

