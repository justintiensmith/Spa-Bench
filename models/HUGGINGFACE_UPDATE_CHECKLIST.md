# Hugging Face model-card update checklist

The local cards in this directory are drafts for the public model repositories.
Keep the existing repository IDs stable and update their `README.md` files only
after the unresolved fields below are verified.

For every model card:

- use the canonical Spa-Bench display name;
- link the Spa-Bench artifact repository and evaluated rollout dataset;
- state that the checkpoint is the one used for the reported evaluation;
- pin the base-model and training-dataset revisions;
- include the resolved training configuration and checkpoint step;
- describe middle/wrist cameras, six-dimensional state/action, and action horizon;
- distinguish training changes from deployment-time processing;
- summarize intended use, limitations, and physical safety requirements;
- cite the final thesis/publication and upstream model;
- avoid reporting an aggregate score until the final result table is frozen.

Additional checks:

- **pi0.5:** reconcile the historical frame-count/model-card discrepancy.
- **MolmoAct2:** confirm the exact epoch-12 launcher and revision.
- **GR00T Frozen LLM:** remove the inaccurate `vision-only` label and record EMA
  alpha.
- **GR00T Full Fine-Tune:** record EMA alpha, initialization assist, and partial
  rollout coverage.
- **VLA-0:** record the training/service code revision, epoch-12 update count,
  and partial rollout coverage.

