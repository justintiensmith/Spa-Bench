# Spa-Bench prompt manifest

This directory contains a derived, episode-level prompt assignment for the six
immutable 200-episode source datasets used by the Spa-Bench.

The source repositories are never edited by the build script. Each manifest row
retains the source repository, pinned revision, episode index, original task
string, and episode length.

## Build

Run from the LeRobot repository root:

```bash
python benchmarks/vla_prompt_manifest/build_prompt_manifest.py \
  --pdf "/path/to/Spa-Bench V8 (2).pdf"
```

The build requires `pypdf` and `pyarrow`. Source metadata must already be
present in the local Hugging Face cache at the pinned revisions recorded in the
script.

## Outputs

- `prompt_manifest_v1.csv`: spreadsheet-friendly 1,200-row manifest.
- `prompt_manifest_v1.jsonl`: the same records in JSON Lines format.
- `validation_report_v1.json`: structural, balance, leakage, and provenance
  checks.
- `object_inventory_v1.json`: the user-verified canonical object inventory.

The manifest uses the standard spelling `propellers` while referring to the
user-verified with/without-propellers airplane objects.

## Prompt policy

- **Size:** green-block-as-largest and juggling-ball-as-smallest are held out.
  Those trajectories receive object-identity prompts. The Pepsi can is
  canonically identified as a crushed Pepsi can.
- **State:** the `closed + upside-down` conjunction is held out. Its
  trajectories receive a unique single-attribute prompt when possible.
- **Relational placement:** physical left/right demonstrations are labeled with
  undirected `next to` language. Front/behind remain seen.
- **Referential disambiguation:** `furthest` is held out. Those trajectories
  receive target-identity prompts.
- **Ordering:** `first from right` and `third from left` are absent from
  training. Existing layouts are truthfully relabeled with another ordinal
  description where possible, otherwise with object identity.
- **Counting:** final counts 1 and 3 are held out. Those trajectories receive
  object-and-direction prompts; final counts 0 and 2 receive goal-count prompts.

Three controlled templates are balanced within each prompt cell. All 1,200
episodes are assigned to the training split. Episode index modulo 10 is retained
only as optional bookkeeping if a future experiment needs reproducible folds.

The assigned prompts are task-local holdouts. Direction and ordinal words may
appear in other task families, intentionally testing cross-task transfer rather
than claiming that pretrained models have never encountered those words.

## Merged training dataset

`build_merged_dataset.py` creates a separate LeRobot v3.0 dataset without
editing any source repository. It downloads the six pinned revisions, preserves
all five video streams, rewrites global episode/frame indices, and makes each
episode's assigned prompt its LeRobot task string.

```bash
python benchmarks/vla_prompt_manifest/build_merged_dataset.py
```

The default output is:

```text
~/.cache/huggingface/lerobot/justintiensmith/VLA_Benchmark_Prompted_1200
```

It can be loaded locally with the repo ID
`justintiensmith/VLA_Benchmark_Prompted_1200`. Keep
`--dataset.eval_split=0.0` to train on all 1,200 episodes. A custom location can
be supplied with `--output-root`; pass that same path to training as
`--dataset.root`.

The merge builder requires `huggingface_hub`, `numpy`, `pandas`, and `pyarrow`.
Use `--offline` to rebuild strictly from already-cached source snapshots.
