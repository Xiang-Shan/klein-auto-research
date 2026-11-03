# Playbook — 24-golomb-llm-vs-search

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| search | E0001 | optima_matched 0/12 (measured) | randomized construction + local search, 2,000 evals | 2026-11-03 |
| llm | E0004 | optima_matched 6/12 (measured; first_batch_matches 1) | qwen-flash-2025-07-28, 200x10 proposals, 2 workers | 2026-11-03 |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| LLM run with current max_workers against the provider limit | E0002 | HTTP 429 after 613 calls |
| LLM rerun with 429 backoff only | E0003 | ConnectionResetError not covered by the backoff (fixed; E0004 completed) |
| P2 (llm >= 9/12) and P3 (first batch >= 6) as stated | E0004 | refuted: 6/12 and 1/12 |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | LLM arm matches more optima than the search | supported on dev: 6/12 vs 0/12 (E0004 vs E0001), though below P2 | sealed orders 12-13 (P5) |
| H3 | Matches are recall of tabulated rulers | mixed: first batch 1/12, but shared prefixes and nested optimal ruler | none in this study; flag for findings |
| H2 | search reaches P4 = 0/6 on orders 12-13 | high: 0/12 on 8-11 | confirmation cell, after dry run |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. Phase boundary: await lead ack; development is complete (E0001, E0004 measured; E0002, E0003 crashes).
2. Confirmation: search arm sealed dry run then final test (P4).
3. Confirmation llm (P5, >= 3/6 on orders 12-13) after its dry run; order-12/13 optima are in the pinned oracle.
