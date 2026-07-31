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

1. Reproduce a split-identity anchor.
2. Establish an honest baseline.
3. Test the proposed method and ablations inside phase limits.
4. Run the chosen track candidate once on the sealed final test.
