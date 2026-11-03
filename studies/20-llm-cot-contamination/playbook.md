# Playbook — 20-llm-cot-contamination

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| anchor run as-is (8 workers, no 429 retry) | E0001 crash | HTTP 429 rate limit killed the run at 599/600 calls; harness fault, not a verdict |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | The direct arm is non-compliant: qwen-flash reasons despite "final number only" (294/300 responses >25 chars), so em_gain is understated | seen in E0001 shard | lead decides prompt/extraction fix, then re-run anchor |
| H2 | A retry/backoff or fewer workers avoids 429 | likely | lead fixes calls.py or max_workers, then re-run anchor |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. twins phase: contamination originals vs twin block A (P3); cot_gain on twin block A (P4)
2. confirmation: sealed dry runs, then sealed twin block C (P5, P6)
3. salted re-query replication of the cot_gain anchor
