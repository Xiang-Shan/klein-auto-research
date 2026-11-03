# Playbook — 20-llm-cot-contamination

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| cot_gain | E0002 | em_gain 0.01 (CI -0.01..0.03); em_direct 0.95, em_cot 0.96 | gsm8k public 300, registered prompts, qwen-flash-2025-07-28, 2 workers | anchor |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| anchor run as-is (8 workers, no 429 retry) | E0001 crash | HTTP 429 rate limit killed the run at 599/600 calls; fixed by 2 workers, E0002 completed |
| P1 prior (direct EM <= 0.85) | E0002 | refuted: em_direct 0.95 |
| P2 (CoT gain >= 0.10 on public sample) | E0002 | refuted: gain 0.01; direct arm already reasons (4/300 bare replies, median 112 tokens) |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | Direct arm non-compliant (4/300 bare), so em_gain measures CoT vs terse-CoT, not CoT vs no reasoning | confirmed E0002 | report only; prompt stays as registered |
| H2 | Near-ceiling accuracy on twins too, so P4 (gain >= 0.10) likely fails the same way; P3 gap may be small | 0.7 | twins phase cells |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. twins phase: contamination originals vs twin block A (P3); cot_gain on twin block A (P4)
2. confirmation: sealed dry runs, then sealed twin block C (P5, P6)
3. salted re-query replication of the cot_gain anchor
