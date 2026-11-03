# Playbook — 22-cnn-data-scaling

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary (registered, no incumbent) | cells so far E0001 N=500 (0.830), E0002 N=1000 (0.949), E0003 N=2000 (0.841) | flat/noisy start | detached 3-seed arrays | - |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. cells phase slate: N=500, 1000, 2000, 4000, 8000, 16000 in ascending order (see program.md). Then fit phase (P1, P2, P5).

## Observations

- E0002: N=1000 loss > N=500 loss; best_step at the 400-step floor for both. Small cells appear step-limited (floor of 400 steps = fewer epochs at larger N). Watch whether N>=2000 (steps grow with N only above ~N=2,844) restores monotonicity.
- E0003: N=2000 loss 0.841; first three cells flat/noisy, all on the 400-step floor with best_step 350-400. Test: N=4000 is the first cell with steps (563) above the floor.
