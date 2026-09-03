# Playbook — 13-charlm-fixed-budget

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | (none yet) | — | anchor recipe: 4L/4H/128-wide/128-context char transformer, AdamW lr 3e-3 constant, batch 32, 2000 steps, no warmup, no dropout, untied head | — |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| (nothing yet — Phase 0 has not run) | | |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | Capacity is the binding constraint at 2000 steps, so width is the only single edit that clears the floor | plausible, uninformed | E0005 (width 256) |
| H2 | The anchor is already in a stable optimization regime, so warmup buys nothing measurable | plausible, uninformed | E0002 (warmup) |
| H3 | 2000 steps × 4096 tokens is ~9 epochs over 892k characters, so the model may already be regularization-limited and dropout may HELP rather than hurt — the opposite of the registered P4 | live and against the registered prior | E0004 (dropout 0.1) |
| H4 | Weight tying at vocab 65 changes 8,320 of 824k parameters, far too few to move a loss | plausible, uninformed | E0003 (tying) |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. (fill at the phase-start slate ritual)
