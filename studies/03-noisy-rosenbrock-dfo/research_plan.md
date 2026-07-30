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

1. E0001 (phase0-anchor): single-start Nelder-Mead, dev seed block — must reproduce
   the prepared reference cell to 1e-9 (split-identity anchor; STOP if off).
2. Measurement sweep (no ledger row): the same anchor config on 5 disjoint seed
   blocks → `klein noise-floor` → set `minimum_delta = max(2×std, range/2)` and the
   `noise_floor:` block in study.yaml; re-record consult.
3. adaptive-1 (slate ritual first): NM adaptive=True (calibration probe, expected
   within-floor DISCARD) → 4×50 restarts (expected KEEP ≥3× floor) → SPSA a0=50
   (expected honest CRASH via divergence) → SPSA a0=0.1 (expected DISCARD) →
   8×25 restarts (expected DISCARD; fragmentation).
4. confirmation: the incumbent once on the sealed fresh-seed block
   (`klein run-one --final-test`), then `klein finalize`.
