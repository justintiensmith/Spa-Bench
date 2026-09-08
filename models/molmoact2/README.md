# MolmoAct2 -- Spa-Bench Epoch 12 (Step 76,596)

- **Model:** [justintiensmith/molmoact2_Reasoning_Step_076596](https://huggingface.co/justintiensmith/molmoact2_Reasoning_Step_076596)
- **Base checkpoint:** `allenai/MolmoAct2`
- **Framework:** LeRobot 0.6.0
- **Robot:** SO-101, single arm
- **Checkpoint:** epoch 12, step 76,596
- **Policy inputs:** middle RGB, wrist RGB, six absolute joint positions
- **Policy output:** six absolute joint-position commands
- **Action horizon:** 30
- **Training-data variant:** full-length episodes
- **Evaluation rollouts:** [Spa_Bench_Full_MolmoAct2](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Full_MolmoAct2)

## Adaptation summary

The VLM and continuous-action expert were trained jointly while the token
embedding layer remained frozen. Recorded project metadata specifies min--max
state/action normalization, AdamW with zero weight decay, 200 warm-up updates,
and cosine decay. The recorded learning rates are `1e-5` base, `5e-6` for the
vision transformer/connector, and `5e-5` for the action expert.

## Intended use and limitations

This checkpoint is documented as the MolmoAct2 policy evaluated in Spa-Bench.
It is not validated outside the project embodiment and evaluation protocol.
Physical deployment requires direct supervision and conservative limits.

## Missing before archival

- Immutable model, base-model, and training-dataset revisions.
- Resolved `train_config.json` and confirmation of the exact launcher.
- Confirmation of all hardware/software versions from the run log.

