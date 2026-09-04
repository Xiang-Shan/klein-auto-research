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

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase anchor-and-floor slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
