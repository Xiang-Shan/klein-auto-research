# Research plan — 24-golomb-llm-vs-search

## Question

At a matched budget of verifier calls, does an LLM proposing Golomb rulers as data match the known optimal lengths (OEIS A003022) as often as a classical randomized search, on development orders n = 8-11 and sealed orders n = 12-13 — and is a match search or recall?

## Contract

- Domain: combinatorial search (Golomb rulers)
- Data: none — instance.json (orders, budget, OEIS optima, seed blocks)
- Track: primary
- Metric: ruler_length (lower, minimum delta 0)
- Method depth: full
- Per-run maximum: 300 seconds

## Validation policy

Use train/development for adaptive choices. Access the sealed test partition once per
track through `uv run --locked klein run-one --final-test`; label synthesis
exploratory or confirmed.

## Experiment ladder

1. **Development (P1-P3).** One cell per arm on orders 8-11, three trials each, 2,000
   candidate evaluations per trial; the verifier counts matched optima.
2. **Sealed (P4, P5).** Orders 12-13, one run per arm after its dry run.
3. **Replication.** `klein replicate` the search cells (deterministic seeds) and
   `klein replicate --replay` the LLM cells (offline, from the pinned ledger); a salted
   re-query of the LLM development cell is the replication confirmation counts.

## What would change the conclusion

- A matched optimum in the LLM's first batch is a retrieval, not a search result; the
  verifier's `first_batch_matches` keeps the two apart.
- The search arm's numbers are a property of THIS search at THIS budget, not of
  classical search in general; findings must say so.
