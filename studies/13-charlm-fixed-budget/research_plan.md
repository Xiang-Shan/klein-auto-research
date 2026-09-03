# Research plan — 13-charlm-fixed-budget

## Question

Under a fixed 2000-step training budget on a character-level corpus, which single-change training-recipe edits to a small char transformer improve held-out validation loss by more than the measured run-to-run floor, when every checkpoint is scored by a verifier the training script cannot touch?

## Contract

- Domain: language modeling
- Data: bundled:tinyshakespeare/tinyshakespeare.txt.gz
- Track: primary
- Metric: val_loss (lower, minimum delta 0)
- Method depth: full
- Per-run maximum: 900 seconds

## Validation policy

Use train/development for adaptive choices. Access the sealed test partition once per
track through `uv run --locked klein run-one --final-test`; label synthesis
exploratory or confirmed.

## Experiment ladder

1. Reproduce a split-identity anchor.
2. Establish an honest baseline.
3. Test the proposed method and ablations inside phase limits.
4. Run the chosen track candidate once on the sealed final test.
