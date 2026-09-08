# Dataset index

Large datasets are hosted on Hugging Face and are linked rather than copied into
this repository. Add immutable revision hashes before archival publication.

## Fine-tuning datasets

| Dataset | Intended role | Revision |
| --- | --- | --- |
| [justintiensmith/VLA_Benchmark_Prompted_1200](https://huggingface.co/datasets/justintiensmith/VLA_Benchmark_Prompted_1200) | Earlier/full 1,200-episode prompted dataset used by the historical pi0.5 model card | `TODO: map exact revision to evaluated checkpoint` |
| [justintiensmith/VLA_Reasoning_Training_Dataset_1200_2cam](https://huggingface.co/datasets/justintiensmith/VLA_Reasoning_Training_Dataset_1200_2cam) | Two-camera, full-length derivative used by GR00T Full Fine-Tune | `TODO` |
| `justintiensmith/VLA_Reasoning_Training_Dataset_1200_Trimmed_Start_5_Frame` | Motion-trimmed derivative referenced by local training scripts | `TODO: verify public URL and revision` |
| `TODO: full-length MolmoAct2/pi0.5 training repository` | Full-length training input for MolmoAct2 and pi0.5 | `TODO` |
| `TODO: VLA-0 training repository/revision` | Motion-trimmed VLA-0 training input | `TODO` |

The current methods draft describes 1,200 demonstrations and two policy-facing
RGB views. It records 612,733 frames for the full two-camera derivative and
570,386 frames for the motion-trimmed derivative. Historical artifacts also
record a 609,565-frame snapshot. These values must be resolved by immutable
revision, not silently reconciled.

## Spa-Bench evaluation rollouts

| Policy | Dataset | Coverage | Revision |
| --- | --- | --- | --- |
| pi0.5 | [Spa_Bench_Full_Pi0.5](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Full_Pi0.5) | Full | `TODO` |
| MolmoAct2 | [Spa_Bench_Full_MolmoAct2](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Full_MolmoAct2) | Full | `TODO` |
| GR00T-N1.7 Frozen LLM | [Spa_Bench_Full_GR00T-N1.7_Frozen_LLM](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Full_GR00T-N1.7_Frozen_LLM) | Full | `TODO` |
| GR00T-N1.7 Full Fine-Tune | [Spa_Bench_Partial_GR00T-N1.7_Full_Fine-Tune](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Partial_GR00T-N1.7_Full_Fine-Tune) | Partial; document omissions | `TODO` |
| VLA-0 | [Spa_Bench_Partial_VLA-0](https://huggingface.co/datasets/justintiensmith/Spa_Bench_Partial_VLA-0) | Partial; document omissions | `TODO` |

## Preliminary experiments

`TODO`: add the preliminary dataset/model links and state whether each experiment
was exploratory, a pipeline validation, or part of model selection. Keep these
separate from the confirmatory Spa-Bench evaluation.

