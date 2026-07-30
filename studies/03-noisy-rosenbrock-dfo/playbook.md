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
| SPSA at "textbook" a0=0.1 on Rosenbrock | E0006 | still diverges (1.9e178): Spall 1998's own rule sizes a0 from first-step magnitude — gradients ~1e3-1e4 demand a0~2e-5 |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | CONFIRMED (dev): E0003 0.4071 clears the floor bar vs anchor; polish adds ~nothing over random search | — | sealed confirmation next |
| H2 | SUPERSEDED: SPSA at this budget doesn't merely lose, it diverges unless a0 is landscape-scaled (~2e-5) | high (E0006 + Spall 1998 rule) | next study: a0=2e-5, gradient-normalized SPSA |
| H3 | UNTESTED (deferred with random-search-as-experiment) | medium | 8×25 vs 4×50 next study |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. Sealed final test of the incumbent (E0003 config) on the fresh block — the only remaining move
2. NEXT STUDY queue: random search as ledger experiment; 8×25 fragmentation (RQ3); SPSA a0≈2e-5 landscape-scaled
