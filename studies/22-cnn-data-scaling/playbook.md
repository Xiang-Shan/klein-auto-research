# Playbook — 22-cnn-data-scaling

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary (registered, no incumbent) | all six cells measured E0001-E0006: N=500 0.830, 1000 0.949, 2000 0.841, 4000 0.757, 8000 0.652, 16000 0.564 | monotone from N=1000; N=500 anomalously low | detached 3-seed arrays | cells phase complete |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. Cells phase DONE (6/6). Next: fit phase (exponent track; P1, P2, P5) after the phase ack. Caveat to carry: N=500 below N=1000 and best_step at end of budget everywhere.

## Observations

- E0002: N=1000 loss > N=500 loss; best_step at the 400-step floor for both. Small cells appear step-limited (floor of 400 steps = fewer epochs at larger N). Watch whether N>=2000 (steps grow with N only above ~N=2,844) restores monotonicity.
- E0003: N=2000 loss 0.841; first three cells flat/noisy, all on the 400-step floor with best_step 350-400. Test: N=4000 is the first cell with steps (563) above the floor.
- E0004: N=4000 loss 0.757, best_step 550-563 of 563 (end of budget). Every cell so far is compute-limited (best checkpoint at the end); remaining question is whether N=8000/16000 continue down.
- E0005: N=8000 loss 0.652 (sd 0.007), best_step 1100/1125. Wall 288 s; N=16000 expected ~600 s.
- E0006: N=16000 loss 0.564 (sd 0.008), best_step 2128-2240/2250, wall 566 s. Ratio 8000->16000: 0.864 (local exponent ~0.21).
