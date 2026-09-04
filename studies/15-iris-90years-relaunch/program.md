# Program — 15-iris-90years-relaunch

## Roster

Who is doing what, and on what. REFEREE cites this table for the independence rung
(`references/referee-protocol.md`); a blank `experimenter` row caps the achievable
rung at "fresh session", because no artifact then says what ran the loop. Fill the
experimenter row at CONSULT and update a row whenever its model, tool or session
changes.

| Role | Who (model · tool · session) | Since |
| --- | --- | --- |
| consultant | Claude Opus 5 · Claude Code `klein-consultant` subagent · session 016HefKjsAszSh9M5FJ8Zw4g | 2026-09-04 |
| experimenter | Claude Sonnet 5 · Claude Code · session 016HefKjsAszSh9M5FJ8Zw4g | 2026-09-04 |
| data-gate auditor | (fill at Gate 1) | |
| referee | (fill at Gate 3 — MUST be a different model AND a fresh session from the experimenter row) | |
| lead | (the human who owns this study) | 2026-09-04 |

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: ninety years after Fisher's 1936 linear discriminant, does any modern
  post-1936 classifier separate iris *versicolor* from *virginica* measurably better
  than Fisher's own LDA on held-out flowers — and do the two petal measurements alone
  carry the signal?
- Tracks and modes:
  - `fisher` — registered, `kind: estimate`. Measures the incumbent's level. No frontier.
  - `modern` — frontier, `kind: predict`. Holds the incumbent; the parade climbs it.
  - `ablation` — registered, `kind: test`. Cells of a pre-registered feature-set map.
- Primary metric on all three: `val_auc` (ROC-AUC, higher is better).
  `tracks.modern.metric.bound.ideal = 1.0` arms the headroom audit.
- `minimum_delta` ships as **0.0 and is not a bar yet.** It is measured at Phase 0 and
  pasted in by a consult re-record. The recipe, estimand, pair and replicate count for
  each track are already fixed in `study.yaml`, before the measurement.
- Results are exploratory until each track's one sealed final-test run confirms them,
  and `confirmation.require: [sealed, replicate]` also wants a replication record.
  A small delta without uncertainty must never be described as real or decisive.

## Data and split

- Source: `sklearn:load_iris`, restricted to versicolor and virginica.
- Stratified, seed 20260904, 0.25 development / 0.25 test → nominally 50 / 25 / 25.
- Development and test are the same size and construction, so they are exchangeable
  and the paired floor measured on one transfers to the other.
- Adaptive work uses train + development only. The test partition stays sealed until
  the confirmation phase, one access per track, each rehearsed with
  `--final-test --dry-run` first.
- Gate 1 records the prepared-data SHA-256 and the split-policy fingerprint; the
  notary then checks the printed `split_fingerprint:` on every run.

## Registered predictions (mirror of `study.yaml:predictions[]`)

| id | track | decided by | one line |
| --- | --- | --- | --- |
| P0 | fisher | E0001, `all_of` on raw counts | identity anchor - 100 / 50 / 50 / 4 and the partitions sum back. **Hard STOP if off.** |
| P1 | fisher | E0001 | Fisher's LDA reaches dev AUC >= 0.90 |
| P2 | fisher | E0001 | it misses at most 3 of 25 development flowers |
| P3 | fisher | E0001 | its 95% bootstrap interval is wider than 0.05 AUC |
| P4 | modern | E0002 | the headroom door is already shut, `h < 1` |
| P5 | modern | E0003 | logistic regression does not beat LDA by one floor |
| P6 | modern | E0004 | 5-NN does not beat LDA by one floor |
| P7 | modern | E0005 | an RBF SVM does not beat LDA by one floor |
| P8 | modern | E0006 | a boosted tree lands at least one floor BELOW LDA |
| P9 | modern | manual, `klein predict adjudicate` on `results.tsv` | zero keeps in the whole parade |
| P10 | modern | sealed run | the sealed score is within two floors of the development score |
| P11 | modern | sealed run | **the sealed gap** - challenger and LDA within one floor on the same sealed rows |
| P12 | ablation | E0007 | petal-only is within one floor of all-four |
| P13 | ablation | E0008 | sepal-only is at least one floor below all-four |
| P14 | ablation | E0009 | the petal verdict is not an LDA artifact |
| P15 | ablation | sealed run | both halves survive the sealed partition |

Every refuted prediction gets a dated `Decision:` line in this file naming what
changed and which evidence forced it. `klein verify --evidence-use` checks for it.

## Phase ladder

| phase | budget_s | max_exp | contents |
| --- | --- | --- | --- |
| `anchor-and-floor` | 600 | 3 | E0001 anchor + level; four registered sweeps; paste floors; re-record consult |
| `parade` | 900 | 6 | E0002 seeds the frontier and prints `h`; E0003-E0006 the four challengers |
| `ablation-map` | 600 | 4 | E0007 petal, E0008 sepal, E0009 petal with the best modern family |
| `confirmation` | 600 | 4 | three sealed cells, one per track, each dry-run rehearsed first |

At every phase boundary: summarize, STOP for user ack, then
`klein gate record phase --phase <id>`. At every phase start: the slate ritual
(`references/phase-ritual.md`) - 4-6 falsifiable candidates or cells, scored, table
recorded below, survivors mirrored into `playbook.md`.

## Pre-scripted branches (written before the evidence, per the consult protocol)

- **P4 supported - the headroom door is shut before any challenger runs.**
  Run `klein headroom ack` with the recorded reason: *the parade IS this study's
  registered question; four dispositioned discards on a measured bar are the evidence
  the brief asked for, and refusing to run them would answer the question by
  declining to ask it.* Then run the parade. Every candidate is reported with `h`.
- **P4 refuted - the door is ajar.** Run the frontier normally. `h >= 1` means "not
  excluded", never "plausible", and findings must use those words.
- **P8 refuted** (boosting is NOT a full floor worse). Record the `Decision:` line,
  and report in findings §③ that the floor was large enough to absorb a capacity
  cost that was visible in the raw numbers - a statement about the instrument, not
  about boosting.
- **P12 refuted** (petal-only is a floor or more below all-four). The sepal
  measurements carry non-redundant signal; add one cell measuring petal + sepal-width
  before drawing any conclusion about "the petals carry it".
- **P1 or P0 refuted.** Hard STOP. Do not run the parade; audit `prepare.py` and the
  split before anything else, and re-record the DATA gate with the reason.
- **Every parade run discards.** The `stop:` rule fires at four consecutive discards
  on the track; acknowledge with `klein stop ack` so the losing phase ends on the
  record rather than by quiet abandonment.

## Decisions (append-only)

- 2026-09-04 — schema-v3 study scaffolded; gates pending.
- 2026-09-04 — CONSULT. Typed `predict` / `tabular` / `generic`. Chose THREE tracks
  rather than one, because the headline question is a comparison and one sealed access
  per track means a single-track study could confirm the incumbent's level but never
  the gap. Chose `val_auc` over accuracy: on a 25-flower block accuracy resolves only
  to 0.04 (one whole flower), AUC to 0.0064 over 156 ordered pairs; accuracy and the
  raw error count ride along in `extra={...}` because they are what Fisher reported.
  Chose 50/25/25 so development and test are exchangeable and the paired floor
  transfers. Left `minimum_delta` at 0.0 and fixed instead the recipe, estimand, pair
  and replicate count of each floor, so the bar cannot be chosen after seeing the
  answer. Kept `scouting_ledger.md` rather than deleting it - see S1 there.
- 2026-09-04 — METHOD (Gate 2). Wrote `method_card.md` (five parts, `method_depth:
  full`) and `references.yaml` (18 entries, 18 verified, 0 UNVERIFIED); triad asserted
  theory / papers / practice all true. Taught LDA from scratch — the between/within
  scatter ratio, the pooled-covariance closed form, and why it is the plug-in Bayes rule
  under equal-covariance Gaussians (Welch 1939) — and RAN the from-scratch numpy version
  against `LinearDiscriminantAnalysis(solver="svd")` on this study's 49 TRAINING rows
  (`method_check_lda.py`): cosine similarity of the two discriminant directions
  1.000000000000000, max absolute coefficient difference 7.105e-15, max score difference
  1.776e-14. The development block was not scored and the sealed block was not read — no
  evidence was spent at this gate. Transcribed Fisher's own hard-pair result from the
  1936 original and settled a folklore question: he reported NO misclassification count
  for versicolor vs virginica anywhere in the paper. His §VI compound gives a mean
  separation of 15.31 units against within-species standard deviations of 4.342 and
  4.222 — "less than four times the standard deviation of each species" — and his verdict
  was that "a certain diagnosis of these two species could not be based solely on these
  four measurements of a single flower taken on a plant growing wild". That is
  DESCRIPTIVE context for findings only; it is explicitly NOT P2's bar, which stays the
  consultant's own independent estimate. `study.yaml` was NOT edited: in schema 3
  `predictions:` IS the protocol's `predictions_to_falsify`, the ledger P0-P15 is already
  registered and hashed into the consult gate record, and the card's own additional
  priors are recorded as M1-M6 on the card (descriptive, adjudicated in findings section
  ③, never substitutable for a registered prediction). No verifier declared — this is
  `kind: predict` and nothing is checkpoint-scored. Written without opening any file
  under `studies/07-iris-90years/`, `studies/08-iris-rematch/` or
  `studies/09-iris-first-lesson/`.
- 2026-09-04 — EXPERIMENT, Phase `anchor-and-floor`, E0001 (`fisher`, `measured`,
  commit `bc1beecf8ac0`). The identity anchor + Fisher's 1936 LDA level, on the 49
  training / 25 development rows `data_card.md` froze (`split_fingerprint`
  `41553e71e4ed…`, matches the DATA gate exactly). Printed block: `raw_rows=100
  raw_versicolor=50 raw_virginica=50 raw_features=4 partition_sum_matches=1
  val_accuracy=0.96 val_errors=1 primary_metric(val_auc)=1.000000 ci_low=1.000000
  ci_high=1.000000 n_boot=2000`. **P0 supported, P1 supported (AUC 1.0 >= 0.90), P2
  supported (1 error <= 3).** Verified by hand (not just trusted): all 13 development
  versicolor rows score `predict_proba(virginica) < 0.02`, all 12 virginica rows score
  `> 0.45` — one virginica at 0.4507 is the lone threshold-0.5 miss (hence
  `val_errors=1`) but it still ranks above every versicolor score, so ROC-AUC is exactly
  1.0. This is a genuine property of this particular 49/25 split (confirmed independently
  three more times below), not a leakage bug — the DATA-gate duplicate-row fix already
  removed the one mechanism that could have manufactured it, and a fresh `predict_proba`
  dump was inspected row-by-row before trusting the number.
  **P3 REFUTED** (`ci_width 0 > 0.05` is false: `ci_width=0.0` exactly) — see the dated
  Decision line immediately below for what changed and why.
- 2026-09-04 — Decision: P3 refuted. Because the development sample is perfectly
  rank-separated (E0001, above), the percentile bootstrap cannot exhibit any resampling
  variability — every one of the 2000 resamples is drawn WITH REPLACEMENT from the same
  25 already-cleanly-separated rows, so every resample is itself perfectly separated too
  (a mathematical certainty once the parent sample has a clean gap between the two
  classes' score ranges, not a coding artifact). RQ3's prior (a floor of 0.02-0.10 AUC)
  is refuted in the opposite direction from what was expected: not "the floor is too
  coarse to see," but "this specific 25-row block has no gap for the bootstrap to
  resample across." Findings must report this precisely — the percentile bootstrap's
  own known blind spot on a perfectly-separated sample, not evidence that 25 flowers
  "pin down" the true population separation.
- 2026-09-04 — EXPERIMENT, Phase `anchor-and-floor`, the four registered Phase-0 sweeps
  (`kleinlib.sweep.SweepRunner`, each registered with `klein sweep register`; scripts
  and sidecars committed under `sweeps/`). All four measured `noise_floor:`/`fit_noise:`
  blocks pasted into `study.yaml` verbatim from `klein noise-floor`'s printed block; the
  consult gate was re-recorded immediately after (see the gate-record line below) and
  `klein preflight`'s three `noise floor:` lines all read `[OK]`.
  - `sweep:fit_noise_svm_rbf` and `sweep:fit_noise_hgbt` (seed-sweep, k=5 each, seeds
    `[1,2,3,4,5]`, `svm_rbf`/`hgbt` refit on the SAME 49/25 development split, varying
    only the model's own `random_state`): **both recipes score AUC 1.0 on every seed**
    (`svm_rbf` bit-identically 1.0; `hgbt` `0.9999999999999999` on all five, a
    floating-point artifact of the same perfect ranking) — `std=0, range=0` for both.
    The two sub-sweeps are IDENTICAL to measurement precision, so only one
    (`fit_noise_svm_rbf`) is pasted as `tracks.modern.metric.fit_noise:`; the other stays
    on record as `sweep:fit_noise_hgbt`. Provenance only, never a bar, per protocol.
  - `sweep:floor_modern` (paired-bootstrap, 1000 replicates, common random numbers, pair
    `(lda_all4, hgbt)` on the 25 development rows, `study.yaml`'s pre-declared pair):
    **delta AUC(hgbt) − AUC(lda_all4) is exactly 0 on every one of 1000 resamples**
    (`std=0, range=0`, mean `≈0`, a handful of `-0.0` floating-point signs) — `hgbt`
    matches `lda_all4`'s perfect development separation on essentially every resample,
    consistent with the `fit_noise` result above. `suggested_minimum_delta =
    max(2×0, 0/2) = 0`. Pasted as `tracks.modern.metric.minimum_delta: 0` +
    `noise_floor:` (measured, not a placeholder).
  - `sweep:floor_ablation` (paired-bootstrap, 1000 replicates, pair `(lda_all4,
    lda_sepal)`, same 25 rows): **real, resolvable spread** — mean `−0.190092`, std
    `0.0952175`, range `0.5625`. `suggested_minimum_delta = max(2×0.0952175, 0.5625/2) =
    max(0.190435, 0.28125) = 0.28125`. Pasted as `tracks.ablation.metric.minimum_delta:
    0.28125` + `noise_floor:`.
  - `sweep:floor_fisher` (split-lottery, k=5, seeds `[201,202,203,204,205]`, marginal
    resplit strictly inside the 74 non-sealed rows only — `train=49 + development=25`,
    confirmed printed by the script itself; the 25 sealed rows were never read):
    **`lda_all4`'s own development AUC is 1.0 on every one of the 5 redraws** — `std=0,
    range=0`. `suggested_minimum_delta = 0`. Pasted as `tracks.fisher.metric
    .minimum_delta: 0` + `noise_floor:`.
  **Decision — the degenerate floor on `modern`, flagged for the orchestrator before
  Phase `parade`.** The measured `minimum_delta` for BOTH `fisher` (0) and `modern` (0)
  is literally zero — this specific 74-row non-sealed pool, and this specific 25-row
  development block, are separable enough by `lda_all4` (and, per `fit_noise`, by
  `hgbt`/`svm_rbf` too) that no resampling instrument tried at Phase 0 exhibits ANY
  spread. `kleinlib.decision.track_headroom` returns `h=None` (not a number, not
  infinite) whenever `minimum_delta <= 0` — so **the headroom law is now permanently
  disarmed for the `modern` track**, regardless of what E0002 measures as the incumbent:
  P4's rule (`gap_in_floors < 1`) can never be adjudicated because
  `gap_in_floors`/`delta_in_floors` are only printed by `lib.iris.frontier_extra` when
  `minimum_delta > 0` (a defensive guard that also prevents a `0/0` division — no crash
  risk, confirmed by inspecting `frontier_extra`'s guard and `track_headroom`'s own
  `minimum_delta <= 0 → None` short-circuit). Concretely: **P4, P5, P6, P7, P8, P10 and
  P11 will all read INCONCLUSIVE for as long as `tracks.modern.metric.minimum_delta`
  stays 0** — each one's own `inconclusive_if` clause already names exactly this
  condition ("minimum_delta is still 0, so train.py prints no gap_in_floors line"),
  written before Phase 0 without anticipating that a MEASURED floor, not just an
  unmeasured placeholder, could land on that same value. This was NOT patched
  unilaterally here: the pair `(lda_all4, hgbt)` and the paired-bootstrap recipe were
  fixed in `study.yaml` before any measurement specifically so neither could be chosen
  after seeing an answer, and `lib/iris.py`'s zero-guard already matches every other
  Klein study's own convention for reading `minimum_delta` (`study 00`'s train.py uses
  the identical `... or 0.0` idiom). The `ablation` track is UNAFFECTED (floor
  0.28125, real spread, P12-P15 fully decidable). **Handed to the orchestrator as an
  explicit phase-boundary decision point**, not resolved here.
- 2026-09-04 — CONSULT re-recorded (`klein gate record consult`) after pasting all four
  measured floors, per the pre-scripted Phase-0 plan. `--note "minimum_delta set from
  the measured noise floor (fit_noise/floor_modern/floor_ablation/floor_fisher, Phase
  0)"`. `klein preflight` afterward: all three `noise floor:` lines `[OK]`, working
  tree clean, gate artifact hashes match.
- 2026-09-04 — Headroom audit attempted (`klein preflight`) after the consult
  re-record. **Not yet computable**: `modern` track reads "no incumbent yet (or no
  measured minimum_delta) — audited at first keep" — `kleinlib.decision._incumbent`
  only counts a `keep` on the SAME track, and zero `modern`-track runs exist yet
  (E0001 ran on `fisher`, a registered track whose disposition is `measured`, never
  `keep`, so it does not seed `modern`'s incumbent). `klein headroom ack` was
  therefore NOT run — there is nothing armed to acknowledge. Per the finding above,
  once E0002 DOES seed the `modern` incumbent, `h` will still read `None`
  (not a number) because `minimum_delta` is measured at exactly 0 — the pre-scripted
  P4 branch ("if h < 1, ack; if h >= 1, proceed") cannot fire either way until this is
  resolved. **This is the first item Phase `parade` must address, on the record,
  before spending E0002.**

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase anchor-and-floor slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | E0001 (`fisher`, cell): identity anchor (P0) + `lda_all4` dev-AUC level with a 2000-rep bootstrap CI (P1-P3) | 3 | 3 | 3 | 9 |
| 2 | `sweep:floor_fisher` — split-lottery k=5, marginal-resplit inside the 74 non-sealed rows, sets `tracks.fisher.metric.minimum_delta` | 3 | 3 | 3 | 9 |
| 3 | `sweep:floor_modern` — paired-bootstrap 1000 reps, pair `(lda_all4, hgbt)`, sets `tracks.modern.metric.minimum_delta` | 3 | 3 | 3 | 9 |
| 4 | `sweep:floor_ablation` — paired-bootstrap 1000 reps, pair `(lda_all4, lda_sepal)`, sets `tracks.ablation.metric.minimum_delta` | 3 | 3 | 3 | 9 |
| 5 | `sweep:fit_noise_{svm_rbf,hgbt}` — seed-sweep k=5 each, provenance only, never a bar | 2 | 3 | 2 | 7 |

Chosen: all five, in this exact order — `research_plan.md`'s Phase 0 plan already fixed
the sequence, the recipe, the estimand, the pair and the replicate count of every floor
BEFORE any measurement (the whole point of the ritual here is executing that
pre-committed plan on the record, not choosing among alternatives after seeing a
number). No candidate is deferred; nothing survives to "next-best" this phase — the
next slate is Phase `parade`'s, and its first item is now forced by this phase's own
finding (see the Decisions log: `modern`'s measured floor is 0, disarming the headroom
law — Phase `parade` must open by addressing that, not by running E0002 blind to it).
