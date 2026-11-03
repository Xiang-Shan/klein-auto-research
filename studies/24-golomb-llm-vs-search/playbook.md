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
| llm | E0002 | crash (HTTP 429 at 613 calls) | qwen-flash-2025-07-28, 200x10 proposals | no result |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| LLM run with current max_workers against the provider limit | E0002 | HTTP 429 after 613 calls |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | LLM arm matches more optima than the search (P2) | unknown | needs a successful llm development cell |
| H2 | search reaches P4 = 0/6 on orders 12-13 | high: 0/12 on 8-11 | confirmation cell, after dry run |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. Lead decision: rerun llm development cell with lower max_workers / backoff (needs a new allowance).
2. Confirmation: search arm sealed dry run then final test (P4).
3. Confirmation llm (P5) only after a successful development cell.
