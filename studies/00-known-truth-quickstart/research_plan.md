# Research plan — 00-known-truth-quickstart

## Question

On a synthetic table whose Bayes-optimal AUC is computable from the declared
generating process, how close to that known ideal does a short ladder of tabular
models get, and does the headroom law correctly call the point at which further
development is arithmetically pointless?

This is the onboarding study: the shortest complete walk of the Klein lifecycle,
chosen so that the one thing a real study can never show — the ceiling — is
visible on every run.

## Contract

- Kind / modality / profile: `predict` / `tabular` / `generic`.
- Domain: synthetic. Data: `synthetic:prepare.py` — 20 000 rows, 8 features
  (6 informative, 2 pure noise), a logistic label with one two-way interaction
  and one quadratic term; the generator seed is the contract's split seed.
- Track: `primary`, mode `frontier`. Metric `val_auc`, higher is better.
- `minimum_delta`: measured at Phase 0, never guessed. `metric.bound.ideal`: the
  development partition's Bayes AUC, declared after the DATA gate has hashed the
  generator (a consult re-record with a reason, on the event trail).
- Split: stratified 60 / 20 / 20 from `study.yaml` alone; per-run maximum 60 s.
- Confirmation requires sealed evidence.

## Validation policy

Adaptive work uses train + development only. The track gets exactly one sealed
access, rehearsed first with `klein run-one --final-test --dry-run` (which spends
nothing) and then spent once. The sealed number is confirmation evidence, never
another frontier candidate.

## Experiment ladder

**Phase 0 (metrology, no ledger rows).** Two floor recipes into two sidecars:
`seed-sweep` (k = 5) → `fit_noise`, recorded as provenance and never as a bar;
`split-lottery` (k = 10, estimand `marginal-resplit`) → `minimum_delta`. Both are
registered with `klein sweep register` so findings can cite them.

**Phase `adaptive-1` (4 experiments).**

| # | Candidate | Reference rung | Tests |
|---|---|---|---|
| E0001 | `logreg_raw` — the identity anchor | none | P1 |
| E0002 | `logreg_interaction` — the DGP's true `x1·x2` handed to the linear model | `logreg_raw` | P2 |
| E0003 | `hgbt_default` — a boosted tree told none of the true terms | `logreg_interaction` | P3 |
| E0004 | `hgbt_overcapacity` — 5x the trees, 127 leaves, no shrinkage discipline | `hgbt_default` | P4 |

After each keep, the headroom `h = (ideal − incumbent) / minimum_delta` is
re-read at preflight. If it falls below 1 the frontier is arithmetically closed
and the study must either stop or record a run-anyway branch with
`klein headroom ack` before spending E0004 — which is the lesson this study
exists to show, live.

**Phase `confirmation` (1 experiment).** `klein run-one --final-test --dry-run`,
then E0005: the selected candidate, once, on the sealed partition, testing P5.

## Deliverables

`findings.md` (seven sections) + `claims.lock` + `referee_report.md` +
`report/index.html`, plus the three figures the profile's §4 asks of a
classification study with a known truth: the decision trajectory against the
ceiling, predicted-vs-true probability calibration, and the headroom bar.
