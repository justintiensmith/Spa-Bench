# Spa-Bench

Spa-Bench is a real-robot benchmark for evaluating scene-grounded semantic and
compositional transfer in vision-language-action (VLA) policies. It uses an
SO-101 robot, two RGB camera views, a 1,200-demonstration fine-tuning corpus,
and matched physical evaluation scenes across five adapted policies from four
VLA families.

This repository is the artifact index for the MSc thesis project. Large robot
datasets and model weights are hosted on Hugging Face; this repository contains
the benchmark manifests, evaluation workbooks, analysis code, preprocessing
tools, model documentation, and links needed to trace the reported results.

> **Status:** research snapshot. The core artifacts are present, but several
> provenance fields and the final thesis/report files are intentionally marked
> `TODO`. See [MISSING_ARTIFACTS.md](MISSING_ARTIFACTS.md).

## Benchmark at a glance

- **Robot:** SO-101, single-arm manipulation.
- **Observations:** six joint positions plus fixed middle and wrist RGB cameras.
- **Fine-tuning data:** 1,200 teleoperated demonstrations across six task
  families.
- **Task families:** State Recognition, Relational Placement, Referential
  Disambiguation, Ordinal Reference Ordering, Counting, and Size Recognition.
- **Primary question:** can a policy execute a concept--argument composition
  withheld during fine-tuning when the constituent concept, objects, and
  manipulation behaviour are individually represented?
- **Complete evaluation design:** 900 physical rollouts per policy: 300 primary
  compositional-transfer trials and 600 diagnostic/control trials. Some public
  rollout datasets are partial; their exact coverage remains to be documented.
- **Evaluated systems:** pi0.5, MolmoAct2, VLA-0, GR00T-N1.7 Frozen LLM, and
  GR00T-N1.7 Full Fine-Tune.

## Evaluated checkpoints

The display names below are canonical within Spa-Bench. Hugging Face repository
IDs are retained so existing links remain valid.

| Spa-Bench name | Evaluated checkpoint |
| --- | --- |
| pi0.5 -- Spa-Bench Epoch 12 | [justintiensmith/pi05_Reasoning_Step_076596](https://huggingface.co/justintiensmith/pi05_Reasoning_Step_076596) |
| MolmoAct2 -- Spa-Bench Epoch 12 | [justintiensmith/molmoact2_Reasoning_Step_076596](https://huggingface.co/justintiensmith/molmoact2_Reasoning_Step_076596) |
| GR00T-N1.7 Frozen LLM -- Spa-Bench Epoch 12 | [justintiensmith/groot_multi_gpu_v4](https://huggingface.co/justintiensmith/groot_multi_gpu_v4) |
| GR00T-N1.7 Full Fine-Tune -- Spa-Bench Epoch 12 | [justintiensmith/groot_multi_gpu_v2](https://huggingface.co/justintiensmith/groot_multi_gpu_v2) |
| VLA-0 -- Spa-Bench Epoch 12 | [mattpidden/vla0-justin-epoch12](https://huggingface.co/mattpidden/vla0-justin-epoch12) |

See [models/README.md](models/README.md) and the model-specific cards for the
recorded configurations, intended use, limitations, and unresolved provenance.

## Public rollout datasets

| Policy | Spa-Bench rollout dataset | Coverage label |
| --- | --- | --- |
| pi0.5 | [Spa_Bench_Full_Pi0.5](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Full_Pi0.5) | Full |
| MolmoAct2 | [Spa_Bench_Full_MolmoAct2](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Full_MolmoAct2) | Full |
| GR00T-N1.7 Frozen LLM | [Spa_Bench_Full_GR00T-N1.7_Frozen_LLM](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Full_GR00T-N1.7_Frozen_LLM) | Full |
| GR00T-N1.7 Full Fine-Tune | [Spa_Bench_Partial_GR00T-N1.7_Full_Fine-Tune](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Partial_GR00T-N1.7_Full_Fine-Tune) | Partial |
| VLA-0 | [Spa_Bench_Partial_VLA-0](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Partial_VLA-0) | Partial |

Training-data variants and revision placeholders are indexed in
[datasets/README.md](datasets/README.md).

## Repository contents

| Path | Contents |
| --- | --- |
| [`benchmark/`](benchmark/) | Prompt manifest, object inventory, validation report, and benchmark construction code |
| [`spreadsheets/`](spreadsheets/) | Working archive of training/evaluation workbooks and tabular exports |
| [`models/`](models/) | Local model cards and links to evaluated checkpoints |
| [`datasets/`](datasets/) | Training and evaluation dataset index |
| [`training/`](training/) | Available launch scripts plus placeholders for missing resolved configurations |
| [`preprocessing/`](preprocessing/) | Dataset derivation and motion-trimming code |
| [`software/`](software/) | Exact LeRobot/VLA-0 integration provenance and patches |
| [`analysis/`](analysis/) | Failure analysis, paired comparisons, confidence intervals, and figure-generation code |
| [`environment/`](environment/) | Recorded software/hardware context and dependency gaps |
| [`documentation/`](documentation/) | Protocol and methods working material |
| [`thesis/`](thesis/) | Placeholders for the final report and presentation |

## Software integration

The LeRobot changes remain in a separate fork to preserve upstream history and
licensing:

- Fork: [justintiensmith/lerobot_rollout_vla0](https://github.com/justintiensmith/lerobot_rollout_vla0)
- Spa-Bench integration commit: `88d519ec5872020cac210aa2d7c6b161cc3a0afe`
- Upstream base: LeRobot v0.6.0, commit
  `30da8e687a6dfc617fcd94afc367ac7071c376ce`

That fork adds an HTTP-backed VLA-0 policy adapter and CSV-backed per-episode
prompt scheduling for `lerobot-rollout`. Patch exports and the status of the
GR00T action filter are documented in
[`software/lerobot_vla0/`](software/lerobot_vla0/).

## Reproducibility

Start with [REPRODUCIBILITY.md](REPRODUCIBILITY.md). The intended artifact flow
is:

1. build and validate the 1,200-row prompt manifest;
2. construct the policy-specific full/two-camera/trimmed training datasets;
3. fine-tune the five policy configurations to the recorded epoch-12 checkpoints;
4. execute CSV-scheduled physical rollouts with fixed evaluation manifests;
5. consolidate binary outcomes and qualitative annotations;
6. regenerate interval estimates, failure summaries, matrices, and figures.

## Citation

A provisional citation file is provided in [CITATION.cff](CITATION.cff). Replace
the thesis title, institution, archival URL, and publication details once final.

## Safety

The released policies can generate unsafe or unpredictable robot motion. Use
physical safeguards, conservative motion limits, an accessible emergency stop,
and direct human supervision. The public artifacts are research outputs, not a
validated control system for unattended deployment.
