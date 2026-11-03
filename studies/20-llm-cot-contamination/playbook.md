# Playbook — 20-llm-cot-contamination

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| contamination (sealed) | E0006 | em_gap 0.01 (CI -0.040..0.065); orig 0.98, twins 0.97 | sealed twin block C | confirmation |
| cot_gain (sealed) | E0005 | em_gain 0.000 (CI -0.055..0.045); 0.97 vs 0.97 | sealed twin block C | confirmation |
| contamination | E0003 | em_gap 0.02 (CI -0.015..0.060); orig 0.98, twins 0.96 | CoT, 50 templates vs 200 dev twins | twins |
| cot_gain (twins) | E0004 | em_gain -0.025 (CI -0.065..0.005); direct 0.985, cot 0.96 | twin_dev, 200 items, 50 clusters | twins |
| cot_gain | E0002 | em_gain 0.01 (CI -0.01..0.03); em_direct 0.95, em_cot 0.96 | gsm8k public 300, registered prompts, qwen-flash-2025-07-28, 2 workers | anchor |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| anchor run as-is (8 workers, no 429 retry) | E0001 crash | HTTP 429 rate limit killed the run at 599/600 calls; fixed by 2 workers, E0002 completed |
| P5 (sealed gain >= 0.10) | E0005 | refuted: gain 0.000 |
| P4 (CoT gain >= 0.10 on twins) | E0004 | refuted: gain -0.025; ceiling, direct arm reasons |
| P1 prior (direct EM <= 0.85) | E0002 | refuted: em_direct 0.95 |
| P2 (CoT gain >= 0.10 on public sample) | E0002 | refuted: gain 0.01; direct arm already reasons (4/300 bare replies, median 112 tokens) |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | Direct arm non-compliant (4/300 bare), so em_gain measures CoT vs terse-CoT, not CoT vs no reasoning | confirmed E0002 | report only; prompt stays as registered |
| H2 | P3 supported (gap 0.02) but CI upper 0.06 > 0.05; sealed P6 may land either side | 0.5 | sealed contamination cell |
| H3 | CoT gain is ~0 for qwen-flash because the direct arm reasons; a truly bare-number arm would show a gain | 0.6 | out of scope (prompt registered); next study |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. (done) twins phase E0003, E0004
2. (done) confirmation: E0005, E0006, replications of E0002, E0003
3. SYNTHESIZE: findings.md, claims.lock (E0003 replication within 0.005 of tolerance)
