# Playbook — 22-cnn-data-scaling

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary (registered, no incumbent) | cells measured so far: E0001 N=500 | val_mlogloss 0.8296 (sd 0.035) | detached 3-seed array | - |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. cells phase slate: N=500, 1000, 2000, 4000, 8000, 16000 in ascending order (see program.md). Then fit phase (P1, P2, P5).
