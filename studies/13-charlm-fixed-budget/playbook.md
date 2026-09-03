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
| A split-lottery (marginal-resplit) floor | retired before the CONSULT gate (scouting_ledger, Retirements) | the study never re-draws its split, so a re-drawn validation block measures a counterfactual no comparison here runs |
| Sampled validation batches (`eval_iters` style) | retired before the CONSULT gate | it makes the trainer's number and the checker's number disagree for a reason unrelated to the checkpoint |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | Capacity is the binding constraint at 2000 steps, so width is the only single edit that clears the floor | plausible, uninformed | E0005 (width 256) |
| H2 | The anchor is already in a stable optimization regime, so warmup buys nothing measurable | plausible, uninformed | E0002 (warmup) |
| H3 | 2000 steps × 4096 tokens is ~9 epochs over 892k characters, so the model may already be regularization-limited and dropout may HELP rather than hurt — the opposite of the registered P4 | live and against the registered prior | E0004 (dropout 0.1) |
| H4 | Weight tying at vocab 65 changes 8,320 of 824k parameters, far too few to move a loss | plausible, uninformed | E0003 (tying) |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. E0002 warmup (adjudicates P2) — `adaptive-2`, registered
2. E0003 weight tying (adjudicates P3) — `adaptive-2`, registered
3. E0004 dropout 0.1 (adjudicates P4) — `adaptive-2`, registered; H3 says it may go the other way
4. E0005 width 128 -> 256 (adjudicates P5) — `adaptive-2`, registered
5. A fixed batch order instead of sampled offsets: does the offset stream contribute to the floor? (from the `adaptive-1` slate, #5, unchosen)
6. The anchor at 200 steps, to price the marginal value of the budget (from the `adaptive-1` slate, #4, unchosen)
