# Research plan — 08-iris-rematch

## Question

Large-budget rematch: under a selection-honest registered protocol, can any of 21 modern challenger families (incl. the 2025 TabPFN v2 foundation model) beat the 1936 LDA anchor on the versicolor-virginica hard pair - at full n or anywhere down the data ladder

## Contract

- Domain: small-n tabular classification (Fisher 1936 iris hard pair, n=100)
- Data: csv:data/prepared/iris_hard_pair.csv
- Track: primary
- Metric: val_brier (lower, minimum delta 0)
- Method depth: full
- Per-run maximum: 120 seconds

## Validation policy

Use train/development for adaptive choices. Access the sealed test partition once per
track through `uv run --locked klein run-one --final-test`; label synthesis
exploratory or confirmed.

## Experiment ladder

1. Reproduce a split-identity anchor.
2. Establish an honest baseline.
3. Test the proposed method and ablations inside phase limits.
4. Run the chosen track candidate once on the sealed final test.
