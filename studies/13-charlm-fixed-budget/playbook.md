# Playbook — 13-charlm-fixed-budget

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | E0006 | val_loss 1.519319 nats (2.191912 bpc) | the anchor with ONE change: cosine LR decay from 3e-3 to 10% of it over the 2000 steps | 2026-09-03 (phase adaptive-2) |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| 200-step warmup with a CONSTANT learning rate | E0002 | -1.0431 floors: the steps spent below the target rate are never compensated |
| Weight tying at a 65-character vocabulary | E0003 | -11.3693 floors, the largest effect in the study and a cost |
| Dropout 0.1 at a 2000-step budget | E0004 | -4.7255 floors: the binding constraint is optimization, not generalization |
| Width 128 -> 256 at a FIXED step budget | E0005 | -0.4742 floors: inside the floor; capacity is not what binds |
| Warmup on top of cosine decay | E0007 | +0.1035 floors from the incumbent: neither a cost nor a benefit |
| A split-lottery (marginal-resplit) floor | retired before the CONSULT gate (scouting_ledger, Retirements) | the study never re-draws its split, so a re-drawn validation block measures a counterfactual no comparison here runs |
| Sampled validation batches (`eval_iters` style) | retired before the CONSULT gate | it makes the trainer's number and the checker's number disagree for a reason unrelated to the checkpoint |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | ~~Capacity is the binding constraint at 2000 steps~~ | REFUTED by E0005 (-0.4742 floors) | closed |
| H2 | ~~The anchor is already in a stable optimization regime, so warmup buys nothing measurable~~ | PARTLY SUPPORTED: warmup buys nothing (E0007, +0.10 floors from the incumbent) but under a constant LR it actively costs (E0002, -1.04) | closed |
| H3 | ~~The model may already be regularization-limited, so dropout may HELP~~ | REFUTED by E0004 (-4.7255 floors) | closed |
| H4 | ~~Weight tying changes too few parameters to move the loss~~ | REFUTED by E0003 (-11.3693 floors); the parameter COUNT was the wrong thing to reason about | closed |
| H5 | What binds at a fixed step budget is optimization progress per step, so schedule beats capacity and regularization | SUPPORTED so far: the only keep in the study is a pure schedule change (E0006, +3.3326 floors) | a second schedule setting (decay to 0, or a higher peak with decay) — not spent in this study |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

All four registered levers and both exploratory candidates are spent; the phase is
closed and the queue below is what a NEXT study should start from, not this one.

1. A second schedule setting — cosine to 0 rather than to 10%, or a higher peak paid for by the decay: the only lever that has produced a keep, and its setting was never searched
2. Batch 32 -> 64 at the same 2000 steps (from the `adaptive-2` slate, #6) — what does a STEP budget actually hold fixed, steps or tokens?
3. Weight tying WITH a learned logit scale — the E0003 result blames the shared-norm constraint, and that is the cheapest way to test the explanation rather than the effect
4. Width 128 -> 256 at matched FLOPs (fewer steps) rather than matched steps — the `kaplan2020` condition this study deliberately did not run
5. A fixed batch order instead of sampled offsets (from the `adaptive-1` slate, #5) — partly answered by rep:E0001@20260903T121129Z, which held the offset stream fixed and still moved 0.000962 nats

## Measured facts to reuse (phase adaptive-1)

- minimum_delta = 0.0149525 nats (paired floor, k = 10); fit-noise std = 0.00802952 nats (k = 5).
- Anchor level: 1.56915 nats over five seeds; E0001 at a sixth seed = 1.572174.
- Reference levels from the DATA gate: uniform 4.174387, add-one unigram 3.307264 nats.
- Searcher-vs-checker gap so far: 0.00000000 nats on every run.
- A full re-execution at the same seed moves 0.000962 nats; re-scoring a saved
  checkpoint moves 0 (and 0 across devices).
