# GR00T-N1.7 Full Fine-Tune -- Spa-Bench Epoch 12

- **Model:** [justintiensmith/groot_multi_gpu_v2](https://huggingface.co/justintiensmith/groot_multi_gpu_v2)
- **Base checkpoint:** `nvidia/GR00T-N1.7-3B`
- **Framework:** LeRobot 0.6.0
- **Robot:** SO-101, single arm
- **Checkpoint:** epoch 12, step 76,596
- **Policy inputs:** middle RGB, wrist RGB, six absolute joint positions
- **Policy output:** six absolute joint-position commands
- **Action horizon:** 16
- **Training-data variant:** full-length, two-camera derivative
- **Evaluation rollouts:** [Spa_Bench_Partial_GR00T-N1.7_Full_Fine-Tune](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Partial_GR00T-N1.7_Full_Fine-Tune)

## Adaptation summary

The language model, visual encoder, multimodal projector, VLLN module, and
diffusion action model were updated. Recorded project metadata specifies AdamW,
learning rate `1e-5`, weight decay `1e-5`, a 5% warm-up, and cosine decay.

The Spa-Bench rollout pipeline applied the same GR00T exponential moving-average
action filter used for the Frozen LLM condition. The current methods draft also
records a small manual upward initialization displacement before autonomous
execution for this model only.

## Missing before archival

- Immutable model/base-model/training-dataset revisions.
- Resolved training configuration and exact launch command.
- Exact EMA coefficient.
- Magnitude and procedure for the initialization displacement.
- Exact coverage of the partial evaluation dataset.

