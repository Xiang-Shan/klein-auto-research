# Research plan — 20-llm-cot-contamination

## Question

Does chain-of-thought prompting raise a hosted small model's exact-match on GSM8K, and does the gain survive on procedurally generated fresh twins of the same problems (a contamination probe)?

## Contract

- Domain: LLM evaluation (grade-school math reasoning)
- Data: GSM8K test (bundled, MIT) + exact-solver-validated fresh twins
- Track: primary
- Metric: exact_match (higher, minimum delta 0)
- Method depth: full
- Per-run maximum: 3600 seconds

## Validation policy

Use train/development for adaptive choices. Access the sealed test partition once per
track through `uv run --locked klein run-one --final-test`; label synthesis
exploratory or confirmed.

## Experiment ladder

1. **Anchor (P1, P2).** CoT vs direct on the 300-item public sample, paired.
2. **Contamination (P3).** CoT on the 50 originals vs their 200 development twins,
   template-paired.
3. **Gain on unseen items (P4).** CoT vs direct on the development twins.
4. **Sealed (P5, P6).** Twin block C, one run per track, each after its dry run.
5. **Replication.** `klein replicate --replay` (offline, from the pinned ledger) and one
   salted re-query of the anchor (`klein replicate`), which is what confirmation counts.

## What would change the conclusion

- A twin that is not faithful to its original (different structure, harder numbers) would
  read as contamination; the solver check and the auditor's template review guard it, and
  findings must say how many templates were skipped and why.
- With 50 templates, a 5-point gap is near the detection limit; the interval decides, and
  findings report it rather than the point estimate alone.
