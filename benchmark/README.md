# Spa-Bench definition

Spa-Bench contains six language-conditioned manipulation task families:

1. State Recognition
2. Relational Placement
3. Referential Disambiguation
4. Ordinal Reference Ordering
5. Counting
6. Size Recognition

The fine-tuning corpus contains 200 demonstrations from each family. The
controlled missing-cell design withholds selected concept--argument bindings
while preserving the component concept, object identity, and relevant physical
behaviour elsewhere in training.

The prompt manifest, object inventory, validation output, and construction code
are under `prompt_manifest/`. Detailed evaluation allocation and protocol text
are under `documentation/`.

