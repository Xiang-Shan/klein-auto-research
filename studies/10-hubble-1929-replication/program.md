# Program — 10-hubble-1929-replication

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: does Edwin Hubble's 1929 velocity–distance constant reproduce from the two
  tables his paper printed, and what do those 24 objects actually estimate?
- Kind `replicate` · modality `tabular` · profile `generic`. All three tracks are
  `mode: registered`: a run is a **cell**, its disposition is `measured` or `crash`,
  there is no incumbent, no headroom audit and no stop rule.

| Track | kind | Primary metric | Floor | Confirmation |
|---|---|---|---|---|
| `reproduction` | replicate | `targets_outside_tolerance` (lower) | waived: `exactness: exact`, resolution 1 target | `[sealed, replicate]` |
| `estimate` | estimate | `k_kms_per_mpc` (lower) | waived: `exactness: exact`, resolution 1e-6; MC resolution recorded as `fit_noise` | `[sealed, replicate]` |
| `simulate` | simulate | `coverage` (higher) | measured at Phase 0 (`sweep:coverage_floor`) | `[sealed, replicate]` |

Results are exploratory until each track's one sealed access confirms them and a
`reproduced: true` record exists for every development cell a confirmed claim cites.
A small delta without uncertainty is not described as real or decisive.

## Data and split

- Source: `bundled:hubble1929/hubble1929_table1.csv`; Table 2 resolved separately in
  `prepare.py` from `bundled:hubble1929/hubble1929_table2.csv`. Both digests on the
  data card; licence `datasets/hubble1929/DATA_LICENSE` (public domain).
- `split.kind: none` — the partition is the paper's own two tables, not a draw.
  Table 1 (24 rows) is the development block; Table 2 (22 rows) is sealed.
  `lib/hubble.py:load_block()` resolves `KLEIN_EVALUATION_KIND`, refuses the sealed
  block outside a `--final-test` run, honours `KLEIN_SEALED_DRYRUN`, and prints
  `split_fingerprint:`. Because `contract_split` cannot realize partitions for kind
  `none`, no realized fingerprints are registered and `run-one` prints
  `note: partition not verified` on every cell. That is disclosed, not hidden: the two
  block fingerprints are on the data card and a stranger recomputes them from the
  contract plus the bytes.
- The seal is a **prospective analysis lock**, not blindness — see
  `scouting_ledger.md` §0 and `study.yaml:sealed_lock`.

## Workflow

1. `klein gate record consult` (ack delegated — see the decision log below).
2. `prepare.py`, then `data_card.md` with a `Decision: GO`; record the DATA gate.
3. `method_card.md` + `references.yaml`; record the METHOD gate.
4. `klein preflight --study .` on branch `experiments/10-hubble-1929-replication`.
5. Per cell: write `analyze.py` for exactly that measurement, then
   `klein run-one --study . --track <track> --tests P# --description ...`.

Every candidate is committed before execution. On a registered track `run-one` always
restores `analyze.py` afterwards — the candidate commit IS the record of what ran.

## Decisions (append-only)

- **2026-09-03 — scaffolded.** `klein new --schema-version 3 --kind replicate
  --modality tabular --profile generic --split-kind none`, three registered tracks.
- **2026-09-03 — the gate acknowledgements for this exhibit study are DELEGATED to the
  driving agent by the lead.** Every gate is recorded with
  `--acknowledged-by lead-agent`; there is no separate human ack in the loop, and the
  referee reads this line. Phase acknowledgements are recorded the same way.
- **2026-09-03 — Decision: the sealed block is Table 2 and the seal is declared a
  prospective ANALYSIS lock, not blindness.** The driving agent had read all 22 rows
  before the contract existed (`scouting_ledger.md` §0/S6). What `study.yaml:sealed_lock`
  freezes is the statistic, the columns, the source of K and the tolerance; the access
  is spent once. Forced by: the exhibit's own honesty rule, and profile `generic` §7,
  which bans "blind" for this exact confusion.
- **2026-09-03 — Decision: a "fresh bootstrap block" seal is REJECTED before any run.**
  Resampling the same 46 rows an analyst has already seen creates no new information;
  calling the resample a holdout would launder a look into confirmation vocabulary.
  Recorded in `scouting_ledger.md` §Retirements and taught in `method_card.md` §4.
- **2026-09-03 — Decision: Table 2's `r_mpc`, `vs_kms` and `M_t` are forbidden to every
  cell.** `r_mpc` there was computed *from* velocity with Hubble's adopted K ≈ 500
  (dataset README; spot-checked at design time, S7), so it cannot be evidence about K;
  `vs_kms` is tied to it by an exact identity; `M_t` is the printed answer. Mechanized
  as leakage row 1 at the DATA gate.
- **2026-09-03 — Decision: catalogue coordinates for the solar-motion refit will NOT be
  fetched.** Twenty-four hand-transcribed sky positions at an epoch the paper does not
  state is a fabrication risk, not a replication. P2 is registered with an
  `inconclusive_if` on input availability and the missing inputs become the finding.
- **2026-09-03 — Decision: three sealed accesses, one per track, not one for the
  study.** `references/inquiry-model.md` defines "sealed" per KIND, and this study
  carries three kinds: `replicate` seals the original's reported value (Table 2),
  `estimate` seals a once-only comparison against an external reference (H₀ = 70),
  `simulate` seals a fresh seed block. The launch brief sketched a single sealed cell;
  where a brief and a protocol disagree, the protocol wins.
- **2026-09-03 — Decision: `exactness: exact` on the `reproduction` and `estimate`
  tracks; a measured floor only on `simulate`.** Every cell of the first two is a
  closed-form computation over a fixed printed table, so a k-seed spread would measure
  floating-point dust, which `klein preflight` already recognises as a waiver. The part
  of the estimate track that *does* move with a seed — the bootstrap-derived printed
  keys P4 and P5 read — gets its own Phase-0 measurement, recorded as `fit_noise`
  (provenance) and never as a bar.

- **2026-09-03 — Decision (contract re-record #1): `data.source` carries a tag, not prose.**
  The launch brief asked for
  `bundled:hubble1929/hubble1929_table1.csv (Table 2 via a second resolve ... )`.
  `data.source` is machine-resolvable (`references/data-sources.md`): with the
  parenthetical attached, `klein doctor --study` reported
  `[WARN] data source: ... no file 'hubble1929_table1.csv (Table 2 via ...)'`.
  Where a brief and a protocol disagree, the protocol wins. `data.source` is now the
  bare tag and the second bundled member is declared beside it as
  `data.source_table2`, so BOTH files are named in the hashed contract and
  `prepare.py` resolves both from the contract rather than hardcoding a path. Both
  digests go on the data card, as the brief intended. Made before any evidence
  exists; the CONSULT gate is re-recorded with this reason.

- **2026-09-03 — Decision (contract re-record #2): phase ids follow the shipped
  convention `adaptive-N` / `confirmation`.** The descriptive ids drafted at CONSULT
  (`p0-anchor`, `p1-reproduction`, …) made `klein preflight` fail
  `[FAIL] phase ladder: state current_phase 'adaptive-1' is not in the contract's
  phases` — `klein new` writes `current_phase` from the SCAFFOLD's first phase, and
  the guard against retroactively rewriting a phase ladder then fires. The guard is
  correct and studies 03 and 05–09 all use `adaptive-N`; the rename was the
  deviation, so the contract now matches the convention and the descriptions carry
  the meaning. Made before any evidence exists; the CONSULT gate is re-recorded.

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

- **2026-09-03 — Decision (contract re-record #3): both Phase-0 floors are MEASURED and
  pasted in.** `sweep:mc_resolution` gives the estimate track's `fit_noise` — the
  spread of P5's deciding key `inverse_minus_forward_se_units` across five master
  seeds: mean 2.36499, std 0.0382297, range 0.098856. P5's bar is 1, so the seed
  cannot reach the verdict; the block is recorded as `fit_noise`, never as a bar,
  because the track's own primary metric is deterministic (`exactness: exact`).
  `sweep:coverage_floor` gives the simulate track's `minimum_delta` = 0.0060663 =
  max(2×0.00303315, 0.007/2), measured over five simulation seed blocks disjoint
  from A, B and C. Both blocks pasted verbatim from `klein noise-floor`; the CONSULT
  gate is re-recorded with the reason the protocol prescribes.
- **2026-09-03 — DISCLOSURE: the coverage floor foreshadows P6.** Measuring the
  resolution of a quantity a prediction reads necessarily reveals roughly where that
  quantity sits, and the floor blocks put coverage at 0.9268, above P6's bar of 0.90.
  The floor seeds are disjoint from the sealed block C, P6 is still adjudicated there
  as registered, and the pre-scripted refutation branch (downgrade every interval to
  descriptive) stays live — but findings §② will carry this line, not bury it. The
  alternative, measuring the floor on a quantity the predictions do not read, would
  have produced a floor that judges nothing.
- **2026-09-03 — Phase adaptive-1 complete.** One cell (E0001, `measured`,
  `targets_outside_tolerance` 0, P0 supported with max deviation 3.55e-15) and two
  registered measurement sweeps. Acknowledged with `klein gate record phase --phase
  adaptive-1 --acknowledged-by lead-agent` (ack delegated by the lead).

### Phase adaptive-1 slate

Playbook re-read first (nothing ruled out yet beyond the two pre-contract
retirements). On a registered track a candidate is a CELL: which measurement, on
which block, adjudicating which `P#`, at what cost.

| # | Candidate (one cell, one transaction) | Nov | Test | Info | Σ |
|---|---|---|---|---|---|
| 1 | **Identity anchor**: recompute Table 1's `sum(r_mpc)`, `sum(v_kms)` and both row counts against the published anchors; pin the table; adjudicates **P0**. A mismatch is a hard STOP. | 3 | 3 | 3 | 9 |
| 2 | Two-parameter fits of Table 1 against 465 ± 10; adjudicates **P1**. | 3 | 3 | 3 | 9 |
| 3 | Reproduce Table 1's printed `M_t` from `m_t` and `r_mpc`; adjudicates **P9**. | 3 | 3 | 3 | 9 |
| 4 | Bootstrap interval for K on the 24 objects (block A, B = 2000). | 3 | 3 | 2 | 8 |
| 5 | Coverage of the percentile interval under the declared DGP, block B. | 3 | 2 | 3 | 8 |

**Chosen: #1**, and it is not a close call despite the three-way tie on score.
Candidates 2–5 all compute a number *from the bytes*; if the bytes are not
Hubble's, every one of them is a confidently wrong measurement of the wrong
table. The anchor is the only candidate whose failure invalidates the others, so
it runs first and hard-STOPs on mismatch — the `replicate` kind's own rule
(`references/replication-protocol.md`). Candidates 2 and 3 move to phase
adaptive-2, 4 to adaptive-3, 5 to adaptive-4; all four are mirrored into the
playbook.

Two **measurement sweeps** also belong to this phase and consume no experiment
budget (`references/sweep-rules.md`, the measurement carve-out): `mc_resolution`
(the Monte-Carlo spread of the bootstrap-derived printed keys across independent
master seeds, recorded as `fit_noise` on the estimate track — provenance, never a
bar) and `coverage_floor` (five simulation seed blocks, none of them A, B or C,
giving the `simulate` track's measured `minimum_delta`). Both are registered with
`klein sweep register` so findings can cite them as `sweep:<name>`.
