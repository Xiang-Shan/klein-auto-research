# Playbook — 11-exact-verifier-construction

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| n_small | — (external) | 22 | the proven maximum 2n at n = 11; no run can beat it | seeded at the METHOD re-record |
| n_large | — (external) | 62 | the proven maximum 2n at n = 31; no run can beat it | seeded at the METHOD re-record |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| beating the frontier on either track | headroom h = 0 on both tracks, acknowledged before E0001 | 2n is a theorem, so a `keep` would have to contradict it; every run here is a discard by arithmetic and the study says so in advance |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | the search reaches 2n at n = 11 within 2 000 000 addability tests | uninformed | E0004 |
| H2 | the same search at the same budget does not reach 2n at n = 31 | uninformed | E0007 |
| H3 | the objective is monotone in the budget because the budget ladder is a prefix of one RNG stream | by construction | compare E0002/E0003/E0004 |
| H4 | the notary refuses an inflated self-report rather than recording it | uninformed | E0008 |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. E0001 — the verifier controls, and the identity anchor (decides P3)
2. E0002–E0004 — the `n_small` budget ladder (E0004 decides P1)
3. E0005–E0007 — the `n_large` budget ladder (E0007 decides P2)
4. E0008 — the deliberate searcher/checker disagreement (evidence for P5)
