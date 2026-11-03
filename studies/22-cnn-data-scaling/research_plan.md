# Research plan — 22-cnn-data-scaling

## Question

Estimate the data-scaling exponent of a small CNN's test cross-entropy on Fashion-MNIST, and test whether the power law fitted on small training sets predicts the loss at the full training set (a sealed extrapolation).

## Contract

- Domain: deep-learning scaling (image classification)
- Data: Fashion-MNIST (url pins), predefined lanes by position
- Track: primary
- Metric: val_mlogloss (lower, minimum delta 0)
- Method depth: full
- Per-run maximum: 1800 seconds

## Validation policy

Use train/development for adaptive choices. Access the sealed test partition once per
track through `uv run --locked klein run-one --final-test`; label synthesis
exploratory or confirmed.

## Experiment ladder

1. **Cells.** Six registered sizes, detached, each a 3-seed array on development.
2. **Fit (P1, P2).** alpha and R^2 over the six seed means; the fit table is pinned.
3. **Sealed extrapolation (P3, P4).** Train on all 60,000, score the official test set
   once, compare with the pinned law's prediction.
4. **Replication.** `klein replicate` one collected cell locally (an observed record of an
   attested run) and the fit.

## What would change the conclusion

- Development rows come from the official TRAIN file and the sealed rows from t10k; a
  distribution difference between them would show up as extrapolation error that is not
  about scaling. The data card compares them.
- A fit over 1.5 decades cannot distinguish a power law from a power law plus a small
  irreducible term; the sealed point is what can.
