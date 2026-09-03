# Playbook — 11-exact-verifier-construction

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

Refreshed at the close of phase `adaptive-1` (8 of 8 experiments spent).

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| n_small | — (external) | 22 | the proven maximum 2n at n = 11; no run can beat it, and none did | seeded at the METHOD re-record |
| n_small (best FOUND) | E0003 / E0004 | 21 | ILS on the 11 x 11 grid, development seed block; first reached at evaluation 152 572 and never improved | E0003 |
| n_large | — (external) | 62 | the proven maximum 2n at n = 31 | seeded at the METHOD re-record |
| n_large (best FOUND) | E0007 | 54 | the same ILS on the 31 x 31 grid at 2 000 000 tests; first reached at evaluation 326 744 | E0007 |

Every run is a discard by arithmetic (h = 0 on both tracks, acknowledged before
E0001). "Best found" is not a frontier position; it is the largest verified object
the study holds.

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| beating the frontier on either track | headroom h = 0 on both, acknowledged before E0001 | 2n is a theorem; a keep would have to contradict it |
| buying the n = 11 search more budget | E0003, E0004 | the best object was found at evaluation 152 572 and 1 847 428 further evaluations over 19 014 greedy completions produced nothing better — this is a plateau, not a budget shortfall |
| trusting a searcher's self-report | E0008 | a one-point overclaim was refused at tolerance 0 and recorded as a crash; the inflated number reaches no table |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | ~~the search reaches 2n at n = 11~~ | REFUTED by E0004 at 21 of 22 | — |
| H2 | the same search does not reach 2n at n = 31 | SUPPORTED by E0007 at 54 of 62 | — |
| H3 | the objective is monotone in the budget | confirmed by construction and observed: 20 → 21 → 21 and 50 → 53 → 54 | — |
| H4 | the notary refuses an inflated self-report | SUPPORTED by E0008 | — |
| H5 | the 21-point plateau at n = 11 is a property of this seed, not of the search | untested; the sealed block answers it once | E0009 (already registered as P6) |
| H6 | a different perturbation (remove a whole row's pair rather than 1-3 random points) escapes the plateau | untested | a follow-up study; it changes `lib/`, which this study may not do mid-loop |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

Phase `adaptive-1` is spent. Phase `confirmation` has exactly two lawful cells:

1. E0009 — `n_small`, sealed seed block, largest budget; decides P6
2. E0010 — `n_large`, sealed seed block, largest budget; decides P7

Queued for a FOLLOW-UP study, not for this one (each needs a track declared at
CONSULT or a change to `lib/`, and adding either after seeing results is exactly
what the gates exist to prevent):

3. a third instance between the two (n = 19) to locate where the reach breaks
4. the row-pair perturbation of H6
5. a restart-count sweep at n = 11 to see whether 21 is a basin the ILS cannot leave
