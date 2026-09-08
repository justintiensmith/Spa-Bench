# Assembly notes

This repository snapshot was assembled on 2026-09-08 from the local LeRobot
working tree at `/Users/justintiensmith/Documents/lerobot`.

## Source state

- Source branch: `codex/vla0-rollout`
- Source HEAD: `88d519ec5872020cac210aa2d7c6b161cc3a0afe`
- Upstream LeRobot base: `30da8e687a6dfc617fcd94afc367ac7071c376ce`
- The source working tree contained additional uncommitted rollout/action-filter
  work. That work is represented only by
  `software/lerobot_vla0/groot_ema_runtime_working.patch` and is not described as
  a committed fork feature.

## Imported artifacts

- Prompt-manifest source and outputs from `benchmarks/vla_prompt_manifest/`.
- Motion-trimming code from `scripts/datasets/trim_idle_prefix_dataset.py`.
- Available MolmoAct2 launch scripts.
- LingBot-VA exploratory scripts, segregated under `preliminary_experiments/`.
- Failure-mode, chart-audit, and paired-effect analysis sources and tables.
- Current paper/methods working sources and selected figures.
- Git-generated patches for the two committed LeRobot/VLA-0 integration commits.
- 62 spreadsheet/CSV files from the historical `outputs/` tree, totalling about
  31 MiB. Excel lock files and copies embedded in generated Hugging Face dataset
  mirrors were excluded.

The spreadsheet archive deliberately retains dated working-directory names so
provenance is not lost before the later curation pass. Its binary snapshot is
recorded in `spreadsheets/MANIFEST.sha256`.

## Naming policy

New documentation uses `Spa-Bench` exclusively. Copied text sources were
mechanically updated from the earlier internal benchmark name. Binary workbook
contents and archived CSV prose were not rewritten during assembly; their
publication cleanup is tracked in `MISSING_ARTIFACTS.md`.

