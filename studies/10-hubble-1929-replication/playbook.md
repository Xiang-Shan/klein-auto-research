# Playbook — 10-hubble-1929-replication

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

Registered tracks have no incumbent — a cell measures, it does not climb. This table
therefore records the LATEST measurement of each track's summary scalar, not a winner.

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| reproduction | E0001 | `targets_outside_tolerance` 0 | identity anchor: 4/4 published anchors reproduced, max abs deviation 3.55e-15 | 2026-09-03 |
| estimate | — | — | floors measured (`sweep:mc_resolution`); no cell yet | — |
| simulate | — | — | floor measured (`sweep:coverage_floor`, minimum_delta 0.0060663); no cell yet | — |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| a "fresh bootstrap block" seal on the 46 rows | (pre-contract) | resampling seen rows creates no information; it launders a look into holdout vocabulary — `scouting_ledger.md` §Retirements |
| a seed-spread floor for the ESTIMATE track's own primary metric | `sweep:mc_resolution` | the point estimate is a closed-form slope over fixed rows — the spread is exactly zero; the floor had to be measured on the key a rule actually reads |
| fetching J2000 coordinates for the 24 objects | (pre-contract) | 24 hand-transcribed positions at an unstated epoch is a fabrication risk, not a replication — P2 carries an `inconclusive_if` instead |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| RQ1 | no two-parameter fit returns 465 | scouted: the fits land at ~424 and ~454 | E0002 (P1) |
| RQ2 | the paper's headline is unreproducible for lack of printed INPUTS, not method | uninformed | E0004 (P2), E0005 (P3) |
| RQ3 | the 24 objects estimate K ≈ 450 with a wide interval | scouted centre, uninformed width | E0006 |
| RQ4 | percentile bootstrap under-covers at n = 24 | uninformed | E0009, E0010, sealed E0013 (P6) |
| RQ5 | the 1929-vs-today gap is a pure distance-scale error | scouted (arithmetically implied) | sealed E0012 (P7) |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. **Two-parameter fits of Table 1 against 465 ± 10** (P1) — phase adaptive-2, Σ 9.
2. **Reproduce Table 1's printed `M_t` from `m_t` and `r_mpc`** (P9) — phase
   adaptive-2, Σ 9; also the de-risking rehearsal for the sealed cell's machinery.
3. **Bootstrap interval for K** on the 24 objects, seed block A — phase adaptive-3, Σ 8.
4. **Coverage of the percentile interval under the declared DGP**, seed block B —
   phase adaptive-4, Σ 8.
5. Four-parameter solar-motion refit (P2) and the nine-group solution (P3) — phase
   adaptive-2; both expected to end as documented method gaps, which is the finding.
