# Playbook — 03-noisy-rosenbrock-dfo

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | E0003 | 0.4071 | 4x50 restarts, budget 200 | adaptive-1 (beats anchor 2.96x floor; TIES random search 0.397) |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| NM adaptive (Gao-Han) at n=2 | E0002 | coefficients identical to standard NM in 2-D — a no-op by mathematics |
| SPSA divergence as a crash source | E0004 (+off-ledger a0=500,5000) | diverges to absurd-but-FINITE values (1e81..1e196); decaying gains self-limit below overflow |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | Restarts beat single-start NM under noise (escape > depth) | very high — random search alone already beats the anchor 3.2× (data card issue 1) | 4×50 restarts vs anchor AND vs 0.397 |
| H2 | SPSA needs more than 200 evals to compete | medium (uninformed) | tuned SPSA a0=0.1 |
| H3 | Restart fragmentation has an optimum near 4 | medium (uninformed) | 8×25 vs 4×50 |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. SPSA c0=0 — corrected crash mechanism (estimator denominator), registered pre-run
2. SPSA a0=0.1 tuned — RQ2
3. DEFERRED next study: random search as ledger experiment; 8×25 fragmentation (RQ3)
