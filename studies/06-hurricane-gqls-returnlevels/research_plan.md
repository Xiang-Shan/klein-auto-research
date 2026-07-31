# Research plan — 06-hurricane-gqls-returnlevels

## Question

On the 30 most-damaging US hurricanes (Pielke-Landsea 1998, normalized 1995 USD), does a from-scratch gQLS reproduce Adjieteh (2024) Table 6.9 within the published reporting resolution; does its robustness advantage over MLE survive the thesis's 10x contamination and leave-top-k-out stress; and does that advantage carry into per-event return levels - the thesis's own declared future work?

## Contract

- Domain: insurance
- Data: data_hub:hurricane_top30_pl1998
- Track: reproduction
- Metric: mean_abs_param_deviation (lower, minimum delta 0)
- Method depth: full
- Per-run maximum: 180 seconds

## Validation policy

Use train/development for adaptive choices. Access the sealed test partition once per
track through `uv run --locked klein run-one --final-test`; label synthesis
exploratory or confirmed.

## Experiment ladder

1. Reproduce a split-identity anchor.
2. Establish an honest baseline.
3. Test the proposed method and ablations inside phase limits.
4. Run the chosen track candidate once on the sealed final test.
