# Research plan — 04-fremtpl2-frequency

## Question

On freMTPL2 claim frequency, does gradient boosting beat a well-specified GLM by more than the measured noise floor in Poisson deviance?

## Contract

- Domain: insurance
- Data: data_hub:freMTPL2
- Track: primary
- Metric: val_poisson_deviance (lower, minimum delta 0)
- Method depth: full
- Per-run maximum: 300 seconds

## Validation policy

Use train/development for adaptive choices. Access the sealed test partition once per
track through `uv run --locked klein run-one --final-test`; label synthesis
exploratory or confirmed.

## Experiment ladder

1. E0001: GLM baseline (OHE) — the anchor asserts the null-model dev deviance
   matches prepare.py's reference cell to 1e-9 first, every development run.
2. Noise-floor measurement sweep (no ledger row): HGBT baseline config across
   k=5 random_states -> `klein noise-floor` -> set minimum_delta; ALSO record a
   dev-fold bootstrap SE for the deterministic-GLM view of the floor (real-data
   gap in the protocol — soak friction) and take the larger.
3. adaptive-1 (slate first): GLM + shaping (RQ2) -> HGBT poisson baseline (RQ1)
   -> HGBT native categoricals vs OHE (RQ3) -> one HGBT capacity lever probe.
4. confirmation: incumbent once on the sealed test fold; `klein finalize`.
