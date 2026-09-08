# Missing and unresolved artifacts

This file is deliberately explicit so that a placeholder cannot be mistaken for
a verified experimental detail.

## Required before thesis archival

- [ ] Add the final MSc thesis source and PDF under `thesis/report/`.
- [ ] Add the final presentation source and exported PDF under `thesis/slides/`.
- [ ] Replace the provisional citation metadata in `CITATION.cff`.
- [ ] Select and add licences for original code, documentation, spreadsheets,
      and figures. Preserve Apache-2.0 notices on LeRobot-derived patches.
- [ ] Add an archival repository URL and, if available, DOI.
- [ ] Add immutable Hugging Face revision hashes for every model and dataset.
- [ ] Explain the exact episode/task coverage of the two public datasets labelled
      `Partial` and verify that every dataset card reports its coverage.
- [ ] Add links for preliminary-experiment datasets and checkpoints.

## Training provenance

- [ ] Add the resolved epoch-12 `train_config.json` for each evaluated model.
- [ ] Add the exact launch command/job script for pi0.5.
- [ ] Confirm that the MolmoAct2 launcher in `training/molmoact2/` is the command
      used for the reported checkpoint; otherwise replace it.
- [ ] Add or reconstruct the GR00T Frozen LLM and Full Fine-Tune launch commands.
- [ ] Add the VLA-0 training configuration and exact optimizer-update count at
      epoch 12.
- [ ] Resolve the historical full-dataset frame-count discrepancy (609,565 vs
      612,733) by mapping every model to an immutable dataset revision.
- [ ] Add links or exported summaries for the relevant experiment-tracking runs.

## Deployment and evaluation provenance

- [ ] Record the EMA coefficient used for both GR00T evaluations.
- [ ] Commit the EMA action-filter implementation to the LeRobot fork and replace
      the working patch with a commit/revision link.
- [ ] Record the approximate joint or end-effector displacement used to move the
      GR00T Full Fine-Tune policy beyond its static initial state.
- [ ] Add the exact robot calibration identifiers and safe, non-personal hardware
      configuration used during evaluation.
- [ ] Add camera-layout and object-inventory photographs where redistribution is
      permitted.
- [ ] Document which person scored each rollout, whether scoring was blinded,
      and how ambiguous trials were adjudicated.

## Spreadsheet publication pass

- [ ] Identify one canonical final workbook for each task and one consolidated
      results workbook.
- [ ] Move superseded workbooks into an explicitly labelled archive.
- [ ] Standardize all visible naming to `Spa-Bench`.
- [ ] Replace `vision-only` with `GR00T-N1.7 Frozen LLM` where appropriate.
- [ ] Standardize `pi0.5`, `MolmoAct2`, `GR00T-N1.7`, and `VLA-0` labels.
- [ ] Remove local absolute paths, hidden personal notes, external workbook links,
      lock files, and unintended document metadata.
- [ ] Export critical sheets to CSV so changes are reviewable in Git.
- [ ] Rebuild `spreadsheets/MANIFEST.sha256` after the publication pass.

