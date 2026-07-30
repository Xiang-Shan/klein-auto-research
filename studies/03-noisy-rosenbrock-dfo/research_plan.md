# Research plan — 03-noisy-rosenbrock-dfo

## Question

At a fixed 200-evaluation budget on noisy Rosenbrock (sigma=0.5), do restarts beat plain Nelder-Mead, and does SPSA beat both?

## Contract

- Domain: optimization
- Data: synthetic:noisy_rosenbrock_v1
- Track: primary
- Metric: mean_final_gap (lower, minimum delta 0)
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
