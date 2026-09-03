# Playbook — 13-charlm-fixed-budget

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | E0001 | val_loss 1.572174 nats (2.268167 bpc) | anchor recipe: 4L/4H/128-wide/128-context char transformer, AdamW lr 3e-3 constant, batch 32, 2000 steps, no warmup, no dropout, untied head, seed 20260903 | 2026-09-03 (phase adaptive-1) |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| A split-lottery (marginal-resplit) floor | retired before the CONSULT gate (scouting_ledger, Retirements) | the study never re-draws its split, so a re-drawn validation block measures a counterfactual no comparison here runs |
| Sampled validation batches (`eval_iters` style) | retired before the CONSULT gate | it makes the trainer's number and the checker's number disagree for a reason unrelated to the checkpoint |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | Capacity is the binding constraint at 2000 steps, so width is the only single edit that clears the floor | plausible, uninformed | E0005 (width 256) |
| H2 | The anchor is already in a stable optimization regime, so warmup buys nothing measurable | plausible, uninformed; the blocks are Pre-LN and Xiong et al. 2020 say warmup exists to fix a Post-LN problem | E0002 (warmup) |
| H3 | 2000 steps × 4096 tokens is ~9 epochs over 892k characters, so the model may already be regularization-limited and dropout may HELP rather than hurt — the opposite of the registered P4 | live and against the registered prior | E0004 (dropout 0.1) |
| H4 | Weight tying at vocab 65 changes 8,320 of 824k parameters, far too few to move a loss | plausible, uninformed | E0003 (tying) |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. E0002 warmup (adjudicates P2) — `adaptive-2`, registered
2. E0003 weight tying (adjudicates P3) — `adaptive-2`, registered
3. E0004 dropout 0.1 (adjudicates P4) — `adaptive-2`, registered; H3 says it may go the other way
4. E0005 width 128 -> 256 (adjudicates P5) — `adaptive-2`, registered
5. Cosine LR decay to 10% of peak (from the `adaptive-2` slate, #5) — an untouched lever, no registered prediction
6. Batch 32 -> 64 at the same 2000 steps (from the `adaptive-2` slate, #6) — what does a STEP budget actually hold fixed?
7. A fixed batch order instead of sampled offsets (from the `adaptive-1` slate, #5) — partly answered by rep:E0001@20260903T121129Z, which held the offset stream fixed and still moved 0.000962 nats
8. The anchor at 200 steps, to price the marginal value of the budget (from the `adaptive-1` slate, #4, unchosen)

## Measured facts to reuse (phase adaptive-1)

- minimum_delta = 0.0149525 nats (paired floor, k = 10); fit-noise std = 0.00802952 nats (k = 5).
- Anchor level: 1.56915 nats over five seeds; E0001 at a sixth seed = 1.572174.
- Reference levels from the DATA gate: uniform 4.174387, add-one unigram 3.307264 nats.
- Searcher-vs-checker gap so far: 0.00000000 nats on every run.
- A full re-execution at the same seed moves 0.000962 nats; re-scoring a saved
  checkpoint moves 0 (and 0 across devices).
