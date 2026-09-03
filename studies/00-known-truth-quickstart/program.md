# Program — 00-known-truth-quickstart

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: On a synthetic table whose Bayes-optimal AUC is computable from the declared
  generating process, how close to that known ideal does a short ladder of tabular
  models get, and does the headroom law correctly call the point at which further
  development is arithmetically pointless?
- Kind / modality / profile: `predict` / `tabular` / `generic`. Schema 3.
- Track: `primary`, mode `frontier`.
- Primary metric: `val_auc` (higher is better). `minimum_delta` is measured at
  Phase 0 with a named estimand and pasted into the contract; it is never guessed.
- `metric.bound.ideal` is the development partition's Bayes AUC — the best score any
  model could reach on those rows — declared only after the DATA gate has hashed the
  generator that computes it.
- Results are exploratory until the track's one sealed final-test run confirms them.
  A small delta without uncertainty must not be described as real or decisive.

## Data and split

- Source: `synthetic:prepare.py`. The generator seed is read from
  `data.split.seed`; no seed and no partition rule is written as a literal anywhere
  in a script (war story 8).
- 20 000 rows, 8 standard-normal features. Six enter the true log-odds; `x7` and
  `x8` enter nothing. One two-way interaction (`x1·x2`) and one quadratic (`x3²`)
  are the two things a linear-in-raw-features model cannot express.
- `data/prepared/truth.json` carries the per-row true log-odds and, per contract
  partition, the Bayes AUC and Bayes Brier those log-odds imply.
- Adaptive work uses train + development only. The test partition stays sealed.
- Gate 1 records the prepared-data SHA-256 and the realized partition fingerprints.

## Research questions

- **RQ1** — how much of the distance between a linear-in-raw-features baseline and
  the known Bayes ceiling does each rung of a short ladder close, in units of the
  measured floor? Prior: the anchor stops several floors short; the true interaction
  closes part of it; a boosted tree closes most of the rest without being told which
  terms are true `(source: scouted — scouting_ledger.md S2)`.
- **RQ2** — does the headroom law call the end of this ladder correctly: does
  `h = (ideal − incumbent) / minimum_delta` fall below 1 before a challenger with
  real capacity is spent, and does the run spent anyway come back within the floor?
  Prior: yes, the door closes before the fourth candidate `(source: uninformed —
  the floor is measured at Phase 0, after the scouting ledger closes)`.

## Registered predictions

Every rule is a threshold in units of the MEASURED floor, so every numeral in the
prediction block is an integer count of floors, fixed before the floor was known.
`gap_in_floors` is the run's own headroom against the declared ideal;
`delta_in_floors` is its paired lift over the named reference rung, refitted on the
same rows inside the same run so the comparison lives in one printed block.

| P# | Statement | Rule | Decided by |
|---|---|---|---|
| P1 | the raw-feature logistic model cannot reach the ceiling: more than one floor of distance is left | `gap_in_floors > 1` | E0001 `--tests P1` |
| P2 | handing it the DGP's true interaction beats it by at least one floor on the same rows | `delta_in_floors >= 1` | E0002 `--tests P2` |
| P3 | a boosted tree, told none of the true terms, beats the hand-specified interaction rung by at least one floor | `delta_in_floors >= 1` | E0003 `--tests P3` |
| P4 | buying capacity on top of the boosted rung is within noise (< 1 floor from its own reference) | `abs(delta_in_floors) < 1` | E0004 `--tests P4` |
| P5 | the sealed run lands within two floors of the sealed partition's ceiling | `abs(gap_in_floors) <= 2` | E0005 `--tests P5` |

## Phase plan

| Phase | What happens | Budget | Max experiments |
|---|---|---|---|
| (Phase 0, no ledger rows) | two floor recipes into two sidecars; `klein noise-floor` prints the contract block; consult re-record pastes it | — | — |
| `adaptive-1` | E0001 anchor → E0002 interaction → E0003 boosted → E0004 over-capacity | 3600 s | 4 |
| `confirmation` | sealed dry-run, then E0005 once on the held-out partition | 900 s | 1 |

## Workflow

1. `klein gate record consult` (the scouting ledger is committed first, so the gate
   hashes it).
2. `prepare.py`, the profile, the clean-room leakage audit, `data_card.md` = GO;
   `klein gate record data`.
3. `method_card.md` + `references.yaml`; `klein gate record method`.
4. Phase 0 floors; paste the measured block; consult re-record with a reason;
   `klein preflight`.
5. The loop: edit `train.py` (two constants), `klein run-one --tests P#`.

Every candidate is committed before execution. Discards and crashes remain
resolvable commits; the evidence transaction then restores `train.py` to the
pre-candidate base commit.

## Decisions (append-only)

- 2026-09-03 — schema-3 study scaffolded (`predict` / `tabular` / `generic`); gates
  pending.
- 2026-09-03 — `study.yaml:target` is the target COLUMN, so it reads `y`; the
  "synthetic" part of the study's identity lives in `data.source`
  (`synthetic:prepare.py`), which is what `contract_split` and the DATA gate read.
- 2026-09-03 — the user's gate acknowledgements are DELEGATED to this agent for the
  Klein 2.0 exhibit studies. Every gate below is therefore recorded with
  `--acknowledged-by lead-agent`, on the lead's standing instruction, and the same
  applies to the phase acknowledgements. Nothing else about the gates changes: the
  artifacts still have to exist, be placeholder-free, and hash.
- 2026-09-03 — the smoke check of `train.py` ran before the consult gate was
  recorded and is disclosed as entry S4 of `scouting_ledger.md` rather than left
  silent. It wrote nothing and could not have set a rule: no floor existed yet.
- 2026-09-03 — Phase 0 measured TWO floors and they disagree by everything.
  `seed-sweep` (k = 5) refit the anchor on the same rows under five fit seeds and
  moved it not at all: std 0, range 0. That is recorded under `fit_noise` as
  provenance and is NOT the bar — a study that had pasted it into
  `minimum_delta` would carry a keep bar of zero and would keep every candidate
  that moved the fourth decimal. The bar comes from `split-lottery`
  (k = 10, estimand `marginal-resplit`, redrawing train/development inside the
  train+development pool only, never touching the sealed rows):
  std 0.00372606, range 0.012855, `minimum_delta` 0.00745212 = max(2*std, range/2).
- 2026-09-03 — Decision: `tracks.primary.metric.bound.ideal` is set to 0.884116,
  the development partition's Bayes AUC from `data/prepared/truth.json`. This is
  a contract change AFTER the DATA gate, and it is lawful only through a gate
  re-record with a reason, which is what happens next: the DATA gate had to hash
  the generator before the number it computes could be quoted in the contract. No
  run exists yet, so no result could have informed it. `on_infeasible: ack` is
  chosen over `block` deliberately — this study wants to walk through the closed
  door on the record, not be stopped by it.

- 2026-09-03 — E0001 KEEPS at val_auc 0.806201 and anchors the track. Its printed
  `gap_in_floors` is 10.4555: a single hyperplane over the raw features sits more
  than ten measured floors below the known ceiling of 0.884116. P1 SUPPORTED by
  the notary on the printed block.
- 2026-09-03 — E0002 KEEPS at val_auc 0.835785. Handing the linear model the DGP's
  true `x1*x2` term bought `delta_in_floors` 3.9699 over the same rung refitted on
  the same rows, and cut the distance to the ceiling from 10.4555 to 6.4856
  floors. P2 SUPPORTED. Decision: the remaining distance is the quadratic the
  linear model still cannot express, so the next rung changes model class rather
  than adding another hand-specified term.
- 2026-09-03 — E0003 KEEPS at val_auc 0.871390 and takes the frontier. A boosted
  tree told NONE of the true terms beat the hand-specified interaction rung by
  `delta_in_floors` 4.7779, leaving `gap_in_floors` 1.7077. P3 SUPPORTED.
- 2026-09-03 — headroom read before spending the fourth candidate:
  h = (0.87139 - 0.884116) / 0.00745212 = 1.708. The door is AJAR, not open. The
  study proceeds and records in advance that `h >= 1` means only "not
  arithmetically excluded": the attainable ceiling may sit well short of the ideal
  one, and study 08 stood at h = 1.015 and produced zero keeps in twenty-one
  attempts. No `klein headroom ack` is required at h > 1, and none is filed.
- 2026-09-03 — Decision: **P4 REFUTED** by E0004. The over-capacity boosted tree
  (500 trees, 127 leaves, `min_samples_leaf` 1, no L2, no early stopping) did not
  land within noise of its own reference — it lost `delta_in_floors` -1.7903, a
  degradation nearly twice the floor, and DISCARDS at val_auc 0.858049 against the
  incumbent 0.87139. The prediction said "within noise"; the measurement says
  "measurably worse", so the prediction is refuted rather than supported, and the
  study records that the honest reading of a refuted "no-effect" prediction is a
  real effect in the wrong direction. Its `val_logloss` 1.024102 against E0003's
  0.355165 says why: unregularized depth on 12 000 rows destroys the probabilities
  long before it destroys the ranking. Consequence: capacity is now a ruled-out
  direction on this table, the ladder stops here, and the confirmation phase
  spends the one sealed access on E0003's configuration.
- 2026-09-03 — Decision: RQ2's prior is WRONG so far. It said the headroom would
  close (h < 1) before the fourth candidate; it stood at 1.708 instead, so the law
  did not stop the study and the discard had to be paid for in full. That prior was
  `(source: uninformed)` and is recorded as a miss, not quietly rewritten.
- 2026-09-03 — Phase `adaptive-1` closes with its four experiments spent: three
  keeps (E0001, E0002, E0003) and one discard (E0004); P1, P2, P3 supported and P4
  refuted, all four adjudicated by the notary on printed blocks. Playbook
  refreshed; the acknowledgement is the lead's delegated one.

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase adaptive-1 slate

Scored after the Phase 0 floor landed at `minimum_delta` 0.00745212, so
testability is judged against a bar that exists.

| # | Candidate (one hypothesis, one transaction) | Nov | Test | Info | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | `logreg_raw`: the raw-feature identity anchor; prints the first `gap_in_floors` and decides P1 | 1 | 3 | 3 | 7 |
| 2 | `logreg_interaction`: hand the linear model the DGP's true `x1*x2`; decides P2 | 3 | 3 | 3 | 9 |
| 3 | `hgbt_default`: a boosted tree told none of the true terms; decides P3 | 3 | 3 | 3 | 9 |
| 4 | `hgbt_overcapacity`: 5x the trees, 127 leaves, no shrinkage discipline, no early stopping; decides P4 | 2 | 3 | 3 | 8 |
| 5 | `logreg_quadratic`: hand it `x3^2` as well — reaches the ceiling by construction | 2 | 3 | 1 | 6 |
| 6 | `logreg_raw` without `x7`, `x8`: does dropping known-noise columns move anything? | 2 | 1 | 2 | 5 |

Chosen, in order: 1 (a frontier needs an incumbent before anything can be
compared to it), then 2, 3, 4 — the ladder in the order the method card argues
it. #5 scores 1 on information because the DGP already dictates its answer: a
model handed every true term must reach the ceiling, so the run would teach
nothing the generator has not already said. #6 scores 1 on testability because a
logistic regression on 12 000 rows barely notices two noise columns; the
predicted move is well under `minimum_delta`, so one run cannot decide it. Both
go to the playbook queue rather than the ledger.
