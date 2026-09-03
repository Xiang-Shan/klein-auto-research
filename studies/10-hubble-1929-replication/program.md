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


### Phase adaptive-3 slate

Playbook re-read. The reproduction track has said what it can: the paper's
number does not come back out of the paper's table, and two of the four routes to
it are blocked by inputs the paper never printed. That settles what the 1929
result *was*. This phase asks the different question the `estimate` track exists
for — what those 24 objects actually estimate — and it is deliberately kept
separate, because "Hubble's constant" and "the constant Hubble's data supports"
are two quantities and conflating them is the error the whole study is built to
avoid.

| # | Candidate (one cell, one transaction) | Nov | Test | Info | Σ |
|---|---|---|---|---|---|
| 1 | **Bootstrap interval for K** — 2000 case resamples of the 24 pairs, seed block A, percentile 95 %; the estimate the study will report. | 3 | 3 | 3 | 9 |
| 2 | **Inverse vs forward regression** in units of the paired bootstrap SE, common random numbers; adjudicates **P5**. | 3 | 3 | 3 | 9 |
| 3 | **Jackknife influence** — leave-one-out K for each of the 24 objects; names which galaxies carry the constant and settles data-card issue 6 (the four Virgo rows sharing one distance). | 3 | 3 | 2 | 8 |
| 4 | Bootstrap the through-origin estimator instead, to see whether the interval depends on the intercept choice. | 2 | 3 | 2 | 7 |
| 5 | An errors-in-variables (Deming) fit, which needs an assumed error ratio. | 3 | 2 | 2 | 7 |

**Chosen: #1, #2, #3**, in that order — again a program, not a tournament. #1
must run first because #2 and #3 are both read against its interval. #4 is
subsumed: #1 prints the through-origin bootstrap alongside the free-intercept
one at no extra cost, so it does not need a cell. #5 is **declined and recorded
as declined**: a Deming fit needs the ratio of velocity variance to distance
variance, and the paper prints neither, so the "estimate" it produced would be a
function of a number this study invented. That is the same rule that stopped
E0004 from inventing coordinates.

**Pre-scripted.** P5 is the method card's most exposed prior (§4, prior 4). If
the inverse fit does NOT exceed the forward fit by more than one paired SE, the
claim that Hubble's distance errors dominate his error budget loses its cheapest
support, and findings must say the regression-dilution story was not confirmed
here rather than quietly citing `ref:frost2000` as if it had been. The Phase-0
sweep `sweep:mc_resolution` already fixed the resolution of that comparison
(mean 2.36499, std 0.0382297 across master seeds), so a verdict either way is
outside the seed's reach.


### Phase adaptive-3 outcome

Three cells, all `measured`. The estimate track's answer to "what do those 24
objects actually support?" is not one number but a spread that is much wider
than 1929 admitted, and it moves under choices the paper never discussed.

| Cell | What it measured | Result |
|---|---|---|
| E0006 | 95 % percentile bootstrap for K, 2000 resamples, seed block A | `k_free` **454.158441**, interval **[316.648582, 603.704762]**, width 287.056180; bootstrap SE 72.933862 against analytic 75.237105 |
| E0007 | inverse vs forward, paired on common random numbers | `k_forward` 454.158441, `k_inverse` **728.366015**, ratio 1.603771; paired difference 282.639496 ± 115.484712, i.e. **2.447419 SE units** → **P5 supported** |
| E0008 | jackknife influence, and the Virgo group | jackknife SE 80.485894 (bootstrap 72.933862); largest single influence 50.020227, at r = 2.0 Mpc; dropping all four Virgo rows moves K from 454.158441 to **531.347267**, a shift of **77.188826** |

Three things to carry into synthesis:

- **Hubble's 465 lies inside this study's interval** (`target_inside_ci` = 1 at
  E0006). The reproduction track's verdict — that no two-parameter fit *returns*
  465 — and the estimate track's — that 465 is *not excluded* — are different
  statements, and findings must keep them apart. The first is about arithmetic;
  the second is about resolution at n = 24.
- **Which variable is called the response changes K by 60 %.** The inverse fit
  gives 728.4 against the forward 454.2. Hubble's own 465 sits between them.
  With distances this noisy the ordinary fit is a lower bound on the slope, not
  a best estimate; `ref:frost2000`'s dilution is not a footnote here, it is the
  dominant term.
- **Four objects sharing one assigned distance move the constant by more than a
  standard error.** The Virgo group's joint influence, 77.188826, exceeds the
  analytic SE of 75.237105. Hubble himself attributed the 465-vs-513 difference
  "largely to the four Virgo-cluster nebulae" (`ref:hubble1929`, read at the
  METHOD gate); this reproduces that attribution from his own numbers, which is
  the one part of his uncertainty discussion that DOES reproduce.

**Phase adaptive-3 acknowledged** with `klein gate record phase --phase
adaptive-3 --acknowledged-by lead-agent` (ack delegated by the lead).


### Phase adaptive-4 slate

Playbook re-read. The estimate track has produced an interval — [316.6, 603.7]
— that the study is about to lean on: P4's sealed comparison against the modern
H₀ reads its lower bound, and findings will quote its width against Hubble's
±50. Before any of that, the interval itself has to be audited. That is what
this phase is for, and it is the reason the study carries a `simulate` track at
all: **an interval nobody has checked is a decoration.**

| # | Candidate (one cell, one transaction) | Nov | Test | Info | Σ |
|---|---|---|---|---|---|
| 1 | **Coverage of the percentile bootstrap** under the declared DGP at Table 1's own 24 design points, seed block B — the interval E0006 actually reports. | 3 | 3 | 3 | 9 |
| 2 | **Coverage of the analytic (normal-theory) interval** on the same seed block — the comparison that says whether any under-coverage is the bootstrap's fault or the sample size's. | 3 | 3 | 3 | 9 |
| 3 | Coverage as a function of σ, sweeping the scatter up and down. | 2 | 2 | 2 | 6 |
| 4 | Coverage under a heavy-tailed error law instead of Gaussian. | 3 | 2 | 2 | 7 |
| 5 | Recovery of the DGP's K at large n, as a sanity check on the estimator. | 1 | 3 | 1 | 5 |

**Chosen: #1 and #2**, in that order. #1 is the cell the study needs; #2 costs
one more transaction and turns a bare number into a diagnosis — if both intervals
under-cover by the same amount the culprit is n = 24, and if only the bootstrap
does, the culprit is the method (`ref:diciccio1996`). #3 and #4 are good
questions about a DIFFERENT DGP than the one the DATA gate declared and hashed;
changing the declared truth mid-study to explore is how a simulation lane starts
answering questions nobody registered, so they go to findings §⑦ as next steps.
#5 scores 1 on information: the estimator is a closed-form OLS slope and its
consistency is not in doubt.

**The sealed access is NOT spent here.** For kind `simulate`, "sealed" means a
fresh seed block never used in development (`inquiry-model.md`), so both cells
run on block B and **P6 is adjudicated in the confirmation phase on block C**.
This phase produces no verdict on P6, by design.

**Disclosure, repeated from the Phase-0 decision log.** `sweep:coverage_floor`
already measured coverage on five floor blocks (mean 0.9268), so P6's verdict is
foreseeable. That is the unavoidable cost of measuring the resolution of a
quantity a prediction reads, it was disclosed when it happened, and findings §②
carries it. The refutation branch — downgrade every interval in the findings to
descriptive — stays live until block C is read.


**Amendment to this slate, written after E0009 and BEFORE E0010 runs.** The
slate first said candidate #2 would run "on the same replicates" as #1. It
cannot, and pretending otherwise would have been a false claim about the
comparison. `coverage_experiment` draws its synthetic datasets from one
generator, and the bootstrap method consumes draws from it for resampling, so
`method="bootstrap"` and `method="analytic"` at the same seed diverge after the
first replicate. Two ways out were considered:

1. split the generator in two (data, resampling) so both methods see identical
   datasets — the common-random-numbers construction the method card praises for
   the paired bootstrap. Correct, but it changes the numbers E0009 already
   notarized, so it would mean a second bootstrap-coverage cell on block B and
   two coverage numbers for one block in the ledger;
2. run #2 independently on the same seed block and say so.

**Chosen: 2.** The diagnosis this cell exists for — is the shortfall shared by
both intervals, or specific to the bootstrap? — does not need paired replicates:
each estimate carries a binomial Monte-Carlo error of about
sqrt(0.92 x 0.08 / 1000) ≈ 0.0086, which is far smaller than any shortfall worth
diagnosing. Option 1 is recorded in findings §⑦ as the sharper design for a
study that needs to resolve a small difference between two interval methods.


### Phase adaptive-4 outcome

Two cells, both `measured`, and together they are a diagnosis rather than a
number.

| Cell | Interval | Coverage on block B | Shortfall from 0.95 | Mean width |
|---|---|---|---|---|
| E0009 | percentile bootstrap (500 resamples) | **0.911** | 0.039 | 288.833955 |
| E0010 | analytic normal-theory | **0.938** | 0.012 | 291.871773 |

**Both under-cover, and the bootstrap under-covers more.** Each estimate carries
a binomial Monte-Carlo error of about sqrt(0.92 × 0.08 / 1000) ≈ 0.0086, so the
0.027 gap between them is roughly 2.2 standard errors of the difference — small,
but pointing the same way `ref:diciccio1996` predicts: the plain percentile
interval is only first-order accurate and at n = 24 that costs real coverage,
over and above what the sample size costs by itself. The estimator is
essentially unbiased on both (bias −2.117216 and +1.268232 against k_true = 450),
so this is an interval problem, not an estimation problem.

**An honest note about the Phase-0 floor.** `sweep:coverage_floor` measured
coverage on five floor blocks as 0.9268 ± 0.003033, and gave
`minimum_delta` = 0.0060663. Block B's bootstrap coverage is 0.911 — outside the
floor's whole observed range. The floor is not wrong; it is *optimistic*, because
a k = 5 spread of a binomial proportion can easily come in below the binomial
standard error itself (0.0086 here). The floor recipe's `max(2 × std, range/2)`
guard exists for exactly this, and it still under-shot. Findings will say so: a
five-block floor on a Monte-Carlo proportion is a lower bound on that
proportion's true variability, and a study that needs the difference between two
coverages should size the floor against the binomial SE, not only against the
observed spread.

**Phase adaptive-4 acknowledged** with `klein gate record phase --phase
adaptive-4 --acknowledged-by lead-agent` (ack delegated by the lead).


### Confirmation phase — and what the mandatory dry-run caught

**2026-09-03 — the sealed dry-run earned its keep on the first try.**
`klein run-one --track reproduction --final-test --dry-run` exited 1 with

    RuntimeError: forbidden columns reached the sealed cell:
                  ['r_mpc', 'vs_kms', 'M_t']
    sealed dry-run FAILED: the entrypoint exited 1; the seal is intact

and the study's one reproduction seal was still unspent. The defect was in this
study's own library, not in the engine: `load_block` dropped
`TABLE2_FORBIDDEN_COLUMNS` only when the block it SERVED was Table 2. Under a
dry run it serves Table 1, whose rows carry `r_mpc`, `vs_kms` and `M_t` in the
prepared union — so the rehearsal handed the sealed cell a frame of a different
SHAPE than the real run would, and the cell's own leak guard fired.

Fixed by dropping on the block REQUESTED rather than the block served: a
rehearsal that exercises a different code path is not a rehearsal. Both guards
were needed to catch it — the library's exclusion and the cell's independent
assertion that the exclusion happened — which is the argument for keeping a
check at the door *and* a check at the consumer.

This is the war story the study was told about (`references/war-stories.md`:
"a study's only sealed access was spent by a crash before any data was read"),
happening in the study that was warned. The rehearsal cost nothing and the seal
survived.

**A second, smaller trap the rehearsal exposed.** A passing dry-run WRITES the
sealed cell's artifact — with development data in it, under the sealed cell's
filename (`tables/sealed_table2_magnitudes.tsv`, 19 rehearsal rows). It is
untracked and the sealed run would overwrite it, but leaving it in the tree
risks a rehearsal by-product being hashed as evidence if anything about the
ordering changed. It was deleted before the real run, so the bytes the notary
hashes are the sealed run's own. Recorded because a reader building a sealed
cell of their own will hit it: *a rehearsal that spends nothing can still leave
something behind.*

**2026-09-03 — the sealed dry-run earned its keep a SECOND time, on a different
track.** `klein run-one --track estimate --final-test --dry-run` completed
cleanly but printed

    k_origin_rescaled: 2567.469343268568
    max_abs_gap_70:    2680.4959109684214

where the registration expects both fits near 70. The cell had applied P7's
single factor the wrong way round: `r / f` instead of `r * f`. Hubble's distances
were too SMALL, so correcting the ladder MULTIPLIES them, which divides the slope
— v = K r = (K/f)(f r). Dividing the distances instead sends the fits to ~2570.

Note what the rehearsal did NOT do: it did not fail. Exit code 0, a well-formed
printed block, a pinned table. Had this been the real run, P7 would have been
recorded `refuted` on `max_abs_gap_70` = 2680.5 > 15, the estimate track's one
access would have been spent, and the study would have published a refutation of
a prediction it had never actually tested. **A sealed run can be wrong without
crashing, and reading the rehearsal's numbers — not just its exit code — is what
catches that.**

Fixed to `r * f`; the corrected rehearsal gives `k_origin_rescaled` 70.0 exactly
(by construction of f) and `k_free_rescaled` 74.990073, which is the value
`scouting_ledger.md` already recorded as arithmetically implied by the scouted
anchors. The registered rule and tolerance are unchanged: the cell now
implements the registration it always carried, and "rescaling by f" was only
ever readable as the multiplication that sends `k_origin` to 70 — the other
reading makes the prediction absurd.
