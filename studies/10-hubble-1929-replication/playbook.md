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
| reproduction | E0005 | `targets_outside_tolerance` 1 | four cells run; 1 of 5 declared targets reproduced (the identity anchor). E0002 K=423.94/454.16 vs 465; E0003 M_t off by 0.0712 on 3 rows; E0004/E0005 documented method gaps | 2026-09-03 |
| estimate | E0006 | `k_kms_per_mpc` 454.158441 | free-intercept OLS on the 24 objects; 95% percentile bootstrap [316.648582, 603.704762], 2000 resamples, seed block A | 2026-09-03 |
| simulate | E0010 | `coverage` 0.938 (analytic) / 0.911 (bootstrap, E0009) | both intervals under-cover at n = 24 on block B; the bootstrap by more | 2026-09-03 |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| reproducing K = 465 from a two-parameter fit | E0002 | nearest fit is 10.84 km/s/Mpc away; 465 came from a four-parameter model |
| a Deming errors-in-variables fit | (declined, adaptive-3 slate #5) | needs the velocity/distance variance ratio, which the paper does not print — the estimate would be a function of an invented number |
| reproducing K = 465 from the four-parameter model | E0004 | 0 of 24 per-object coordinates obtainable from the tables, the article, or any offline catalogue |
| reproducing K = 513 from the nine groups | E0005 | the paper states the criterion but never lists the membership; 0 of 9 groups reconstructible |
| Table 1's printed M_t at half the printed precision | E0003 | the formula is right (21/24 exact round-to-nearest) but the paper truncates 3 rows |
| a "fresh bootstrap block" seal on the 46 rows | (pre-contract) | resampling seen rows creates no information; it launders a look into holdout vocabulary — `scouting_ledger.md` §Retirements |
| a seed-spread floor for the ESTIMATE track's own primary metric | `sweep:mc_resolution` | the point estimate is a closed-form slope over fixed rows — the spread is exactly zero; the floor had to be measured on the key a rule actually reads |
| fetching J2000 coordinates for the 24 objects | (pre-contract) | 24 hand-transcribed positions at an unstated epoch is a fabrication risk, not a replication — P2 carries an `inconclusive_if` instead |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| ~~RQ1~~ | **settled** by E0002: neither fit reaches 465; nearest gap 10.84 | scouted | done (P1 supported) |
| ~~RQ2~~ | **settled** by E0004+E0005: both gaps are missing INPUTS, exactly as the uninformed prior said | uninformed | done (P2, P3 inconclusive by their `inconclusive_if`) |
| ~~RQ3~~ | **settled** by E0006: 454.158441 with a 95% interval of [316.6, 603.7] — width 287.1, far wider than Hubble's ±50 | scouted centre, uninformed width | done |
| RQ4 | percentile bootstrap under-covers at n = 24 | uninformed | **prior held on block B** (0.911 vs nominal 0.95); sealed adjudication of P6 pending on block C |
| RQ5 | the 1929-vs-today gap is a pure distance-scale error | scouted (arithmetically implied) | sealed cell, estimate track (P7) — pending |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

All development cells are run. The confirmation phase spends the three sealed
accesses, one per track, each preceded by its mandatory dry-run:

1. **`reproduction` sealed** — Table 2's implied mean absolute magnitude under this
   study's own K, against Hubble's printed −15.3 ± 0.3 (**P8**).
2. **`estimate` sealed** — the once-only comparison against the external reference
   H₀ = 70: the interval's lower bound (**P4**) and the single-factor rescale
   (**P7**).
3. **`simulate` sealed** — coverage on the fresh seed block C (**P6**).

Carried past the confirmation phase, for findings §⑦ rather than for a cell:
coverage as a function of σ, coverage under a heavy-tailed error law, and the
split-generator design that would let two interval methods share replicates.
