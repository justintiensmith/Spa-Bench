# Reproducibility guide

Spa-Bench separates small, version-controlled research artifacts from large
datasets and model weights hosted on Hugging Face.

## 1. Benchmark manifest

The canonical source files are under `benchmark/prompt_manifest/`:

```bash
python benchmark/prompt_manifest/build_prompt_manifest.py \
  --pdf /path/to/source_design_document.pdf
```

The builder expects the six source dataset snapshots in the Hugging Face cache.
The pinned source revisions currently encoded by that script must be reviewed
before archival release.

Expected outputs include the 1,200-row CSV/JSONL manifest, object inventory, and
validation report.

## 2. Dataset construction

The merge builder constructs a LeRobot v3 dataset while retaining episode-level
provenance:

```bash
python benchmark/prompt_manifest/build_merged_dataset.py --help
```

Policy-specific camera selection and motion trimming are described under
`preprocessing/`. Large generated datasets must not be committed to Git.

## 3. Model fine-tuning

The five evaluated configurations are indexed in `models/` and `training/`.
Only some original launchers are currently available. Do not treat a documented
configuration as exactly reproduced until its model card contains:

- an immutable training-dataset revision;
- the resolved training configuration;
- the exact base-model revision;
- the seed, process count, per-device and global batch sizes;
- the checkpoint step and epoch;
- software and hardware versions.

## 4. Physical rollout

The VLA-0 client and CSV prompt scheduler live in a separate LeRobot fork. See
`software/lerobot_vla0/README.md` for the exact revision.

For every evaluation session, preserve:

- the input CSV and selected row range;
- policy and dataset revisions;
- robot/camera configuration;
- rollout duration and frame rate;
- any deployment-time filtering or initialization assist;
- the resulting dataset repository and revision.

## 5. Analysis

Analysis sources are grouped by purpose under `analysis/`. Several scripts were
copied from a working directory and may still require path arguments in place of
historical absolute paths. These are tracked in `MISSING_ARTIFACTS.md`.

Primary outcomes are binary physical task success. Qualitative reasoning and
failure annotations are secondary analyses and should not be substituted for
the primary score.

## 6. Verification checklist

- Recompute manifest row counts and leakage checks.
- Verify all workbook-derived counts against exported CSV tables.
- Regenerate Wilson confidence intervals and paired bootstrap intervals.
- Confirm that figure source values match the final manuscript.
- Verify SHA-256 checksums for all archived workbooks.
- Run a secret and personal-metadata scan before making the repository public.

