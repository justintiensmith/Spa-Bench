# pi0.5 -- Spa-Bench Epoch 12 (Step 76,596)

- **Model:** [justintiensmith/pi05_Reasoning_Step_076596](https://huggingface.co/justintiensmith/pi05_Reasoning_Step_076596)
- **Base checkpoint:** `lerobot/pi05_base`
- **Framework:** LeRobot 0.6.0
- **Robot:** SO-101, single arm
- **Checkpoint:** epoch 12, step 76,596
- **Policy inputs:** middle RGB, wrist RGB, six absolute joint positions
- **Policy output:** six absolute joint-position commands
- **Action horizon:** 50
- **Training-data variant:** full-length episodes
- **Evaluation rollouts:** [Spa_Bench_Full_Pi0.5](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Full_Pi0.5)

## Adaptation summary

The PaliGemma vision-language backbone and action expert were updated jointly.
Recorded project metadata specifies quantile normalization for state/action,
AdamW, peak learning rate `2.5e-5`, weight decay `0.01`, 1,000 warm-up updates,
cosine decay, bfloat16 precision, and a global batch size of 96 across four
accelerators.

## Intended use and limitations

This checkpoint is documented as the pi0.5 policy evaluated in Spa-Bench. It is
not validated outside the recorded SO-101 embodiment, camera views, workspace,
object set, or prompt distribution. Physical deployment requires supervision and
an emergency-stop procedure.

## Missing before archival

- Immutable model and training-dataset revisions.
- Resolved `train_config.json` and exact launch command.
- Reconciliation of the historical 609,565/612,733 frame-count records.
- Confirmation of accelerator model and all package versions from the run log.

