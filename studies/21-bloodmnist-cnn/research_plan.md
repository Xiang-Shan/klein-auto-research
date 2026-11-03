# Research plan — 21-bloodmnist-cnn

## Question

From pixel logistic regression to a small CNN: what earns a keep under a measured floor on 8-class blood-cell microscopy images (BloodMNIST, official split), and how far does a CPU-budget CNN get toward the published MedMNIST baselines?

## Contract

- Domain: medical image classification (hematology microscopy)
- Data: MedMNIST v2 BloodMNIST (url pin, official split)
- Track: primary
- Metric: val_macro_f1 (higher, minimum delta 0)
- Method depth: full
- Per-run maximum: 1800 seconds

## Validation policy

Use train/development for adaptive choices. Access the sealed test partition once per
track through `uv run --locked klein run-one --final-test`; label synthesis
exploratory or confirmed.

## Experiment ladder

1. **Anchor (P2).** The recipe's SmallCNN, unchanged, as a 3-seed array.
2. **Baseline (P1).** A linear softmax on pixels — how much needs no convolution at all.
3. **Floor (Phase 0).** An item bootstrap of the anchor's development macro-F1 gives the
   keep bar (marginal-resplit); three further seed blocks give the fit noise (provenance).
   Registered as a measurement sweep; `klein noise-floor` writes the contract block.
4. **Adaptive (P3 and the slate).** One idea per candidate against the floor; the
   registered P3 cell is BN + three blocks + flip/rot90 + 4,000 steps.
5. **Sealed (P4, P5).** The incumbent once on the official test split, after
   `--final-test --dry-run`; then `klein replicate` the incumbent.

## What would change the conclusion

- Near-duplicate images across the official partitions (the DATA gate's audit) would
  make every development number optimistic.
- A keep whose gain sits inside the floor is not a keep; the floor decides, not the
  eye.
