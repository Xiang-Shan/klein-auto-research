# Research plan — 24-golomb-llm-vs-search

## Question

At a matched budget of verifier calls, does an LLM proposing Golomb rulers as data match the known optimal lengths (OEIS A003022) as often as a classical randomized search, on development orders n = 8-11 and sealed orders n = 12-13 — and is a match search or recall?

## Contract

- Domain: {{DOMAIN}}
- Data: synthetic:prepare.py
- Track: primary
- Metric: ruler_length (lower, minimum delta 0)
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
