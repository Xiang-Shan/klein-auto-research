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

- **2026-09-03 — Decision: P9 is REFUTED (E0003), and the sealed registration STANDS.**
  `max_abs_mag_dev` 0.071213 > the registered 0.06, with 3 of 24 objects outside;
  mean deviation 0.022134. What changed as a result, and what deliberately did not:
  * **Diagnosed, not shrugged off.** 21 of the 24 printed `M_t` values equal
    round-to-nearest of `m − 5log₁₀r − 25` to the last digit *exactly*; the three
    exceptions (N.G.C. 5457 at r = 0.45, and 3031 and 4826 at r = 0.90) are
    truncations toward zero instead. The largest deviation, 0.071213, is inside the
    paper's printed precision of 0.1 mag — no object disagrees by a whole printed
    unit. So the FORMULA is right and the paper's rounding is not uniform; the
    registered bar was half the printed precision, which is what "correctly rounded"
    means, and three rows are not.
  * **The sealed cell's registration is NOT changed.** The temptation is to widen
    P9's tolerance to 0.1 and call the column reproduced; that would be adjusting a
    tolerance after seeing the result, which this study does not do. P8 is a
    different statistic — the MEAN over ~21 objects — and a ±0.07 rounding wobble on
    a few rows averages down; the mean deviation here is 0.022, well inside P8's
    ±0.3. The seal is spent as registered.
  * **What findings will say:** Table 1's printed absolute-magnitude column does not
    reproduce to half its own printed precision, because the paper rounds
    inconsistently — a transcription-grade finding about the 1929 paper, not about
    this study's arithmetic.

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


### Phase adaptive-2 slate

Playbook re-read. Phase adaptive-1 established that the bytes are Hubble's
(E0001, 4/4 anchors, max deviation 3.55e-15), so a number computed from them is
now a number about the 1929 paper. This phase spends its cells on the
`reproduction` track: one published target per cell, each with a tolerance
registered before the run.

| # | Candidate (one cell, one transaction) | Nov | Test | Info | Σ |
|---|---|---|---|---|---|
| 1 | **Two-parameter fits** of Table 1 (through the origin, and free-intercept) against K = 465 ± 10; pin the fit table; adjudicates **P1**. | 3 | 3 | 3 | 9 |
| 2 | **Reproduce Table 1's printed `M_t`** from its own `m_t` and `r_mpc` via M = m − 5log₁₀r − 25, 24 objects, tol 0.06 mag; adjudicates **P9**. Also the de-risking rehearsal of the sealed cell's machinery. | 3 | 3 | 3 | 9 |
| 3 | **Four-parameter solar-motion refit** (K, X, Y, Z) against 465 ± 50; adjudicates **P2**, with `inconclusive_if coords_available < 24`. | 3 | 3 | 3 | 9 |
| 4 | **Nine-group solution** against 513 ± 60; adjudicates **P3**, with `inconclusive_if groups_reconstructed < 9`. | 3 | 3 | 3 | 9 |
| 5 | Reproduce Hubble's quoted probable error ±50 from Table 1's own scatter. | 2 | 3 | 2 | 7 |
| 6 | Quantify the four Virgo-cluster rows' shared distance (issue 6 on the data card). | 2 | 3 | 2 | 7 |

**Chosen: all four of #1–#4, in that order**, which is what the phase's
`max_experiments: 6` is for — this is a registered measurement PROGRAM, not a
search, so the cells do not compete and running one does not tell me whether to
run the next. The order is chosen so the two cells that can still surprise the
machinery (#1, #2) run before the two that are expected to document a gap
(#3, #4): if the distance modulus does not reproduce Table 1's printed
magnitudes, the sealed cell's registration is in trouble and I want to know that
early, while the seal is still unspent.

#5 and #6 are not cells of the reproduction track — neither aims at a target
registered in `study.yaml` — so they move to the playbook as candidates for the
estimate phase, where the jackknife cell subsumes #6.

**Pre-scripted, before #3 and #4 run.** Both are expected to end
`inconclusive` by their `inconclusive_if`, and that outcome must not be dressed
up afterwards. What each cell will do: enumerate the inputs the paper's own
method needs, record for each whether it is present in the bundled tables, in
the article text (`references.yaml:hubble1929`, read at the METHOD gate), or
nowhere; pin that enumeration as the cell's table; print the availability count
the `inconclusive_if` reads; and count the target as NOT reproduced in
`targets_outside_tolerance`, so declining to try can never lower the metric.
Under no circumstance does a cell invent coordinates or a grouping.


### Phase adaptive-2 outcome

Four cells, all `measured`, and the phase's headline is that **the paper's own
headline number does not come back out of the paper's own table**, for two
different reasons that a reader should not confuse:

| Cell | Target | `targets_outside_tolerance` | Verdict |
|---|---|---|---|
| E0002 | K = 465 ± 10 from a two-parameter fit | 1 | **P1 supported** — `k_origin` 423.937323, `k_free` 454.158441, nearest gap 10.841559 |
| E0003 | Table 1's printed `M_t`, ±0.06 mag, all 24 | 1 | **P9 refuted** — max deviation 0.071213 on 3 rows (see the Decision above) |
| E0004 | K = 465 ± 50 from the four-parameter model | 1 | **P2 inconclusive** — `coords_available` 0 of 24 |
| E0005 | K = 513 ± 60 from the nine groups | 1 | **P3 inconclusive** — `groups_reconstructed` 0 of 9 |

Two observations worth carrying into synthesis, neither of them a registered
prediction:

- **E0002 reproduced Hubble's UNCERTAINTY almost exactly.** The analytic
  probable error of the free-intercept slope is 50.747428 km/s/Mpc against the
  ±50 the paper quotes. That was slate candidate #5, which I said would ride
  along in the printed keys rather than spend a cell; it did. It is a striking
  agreement given that the fit reproducing it is not the fit Hubble ran, and
  findings will say so rather than claim more.
- **E0005 found where the textbook 500 comes from, and it is neither published
  solution.** The article adopts 500 as an intermediate value after attributing
  the 465-vs-513 difference largely to the four Virgo-cluster nebulae
  (K = 500, A = 277°, D = +36°, V₀ = 280 km/s). P3 was registered on the
  hypothesis that 500 traces to the nine-group 513; the cell could not test that
  by re-solving, but the article text settles the provenance question directly.
  P3 stays `inconclusive` — the registered rule is about re-solving, and prose
  does not adjudicate a prediction.

**Phase adaptive-2 acknowledged** with `klein gate record phase --phase
adaptive-2 --acknowledged-by lead-agent` (ack delegated by the lead).
