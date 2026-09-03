# Research plan — 12-insurance-claims-frequency

## Question

The v1 quickstart (`studies/00-glm-claims-quickstart`, readable at tag `v1.3.0`) ran a
three-rung model ladder on a 58,592-policy motor portfolio under Klein's v1 rules: no
measured noise floor, no sealed partition, no claims lock, no registered predictions
with arithmetic rules. It recorded six keeps. This study re-runs that ladder under the
schema-3 contract and asks what survives the move:

1. do the rungs reproduce, when the port keeps the v1 training rows exactly and grades
   on half of the v1 validation set;
2. does a ledger description that names its non-default kwargs — v1's own advice #5 —
   reproduce as tightly as a committed file;
3. how large is the paired-comparison floor on this portfolio, and how many of v1's six
   keeps clear a bar that is measured rather than assumed;
4. does the insurance profile's calibration-first doctrine reproduce.

This is the insurance-profile exhibit: an actuary reading it should see what a
notarized contract does to a familiar GLM-vs-GBDT comparison, and what it costs.

## Contract

- Kind / modality / profile: `predict` / `tabular` / `insurance`.
- Data: `bundled:insurance-claims` — the Kaggle `litvinenko630/insurance-claims`
  motor portfolio bundled in this repository, 58,592 policies, claim rate 0.063968.
  `prepare.py` reproduces the v1 prepared table (verified byte-identically through the
  regenerated 2k fixture, scouting ledger S6).
- Track: `primary`, mode `frontier`. Metric `val_auc`, higher is better.
- Split: `stratified`, seed 42, `development_size` 0.10, `test_size` 0.10 — chosen by
  index arithmetic (ledger S4), not by taste: it makes the contract's TRAIN partition
  the v1 training partition exactly, and splits the v1 validation partition into a
  development half and a sealed half.
- `minimum_delta`: measured at Phase 0 with the `paired-bootstrap` recipe and the
  `paired-comparison` estimand, because every keep on this track compares two
  candidates predicting the SAME development rows. Never guessed.
- `metric.bound.ideal`: 1.0, the ceiling of an ROC-AUC. Declared at the same Phase 0
  re-record as the floor, because the engine refuses a bound without a floor estimand.
- Per-run maximum 300 s (the insurance profile's medium-tabular class). Every run here
  is expected to take seconds; the cap is a cap.
- Confirmation requires sealed evidence. `klein replicate E0003` is run as
  corroboration and cited as a `rep:` record, but it is deliberately NOT in
  `confirmation.require`: a study should not label its findings exploratory because a
  detached-worktree build failed.

## Validation policy

Adaptive work uses train + development only. The track gets exactly one sealed access,
rehearsed first with `klein run-one --final-test --dry-run` (which spends nothing) and
then spent once. The sealed rows are the half of the v1 validation set that no
development run in this study ever touches.

One consequence is registered here rather than discovered later: with one track and one
sealed access, only the incumbent's LEVEL can be confirmed. Every rung-to-rung GAP in
this study (P3, P5, P6) is development evidence and is **exploratory by construction**.
Findings must not describe a gap as confirmed.

## The anchor tolerance, derived before any run

The three anchor predictions (P1, P2, P4) carry a v1 ledger value as their target and a
tolerance of 0.0225. That number is not a taste:

- the v1 values were measured on 11,718 rows with 750 positives; Hanley–McNeil gives
  SE ≈ 0.011226 at AUC 0.6255;
- this study grades on 5,859 of those same rows with 375 positives; SE ≈ 0.015876;
- the development partition is one half of the v1 validation set, so the standard
  deviation of the DIFFERENCE between the two AUCs is `sqrt(SE_dev² − SE_v1²)`
  ≈ 0.011226;
- 0.0225 is two of those standard deviations, rounded up.

Because the training rows are identical and each recipe is refitted unchanged, the
fitted model in each anchor run is the v1 model. The only thing the transfer changes is
which rows are scored — which is exactly what the tolerance prices. A ±0.001 identity
tolerance, as v1 used, is unattainable under a contract that mandates a sealed third
partition, and the ledger says so (Retirements).

## Experiment ladder

**Phase 0 (metrology, no ledger rows).** Three recipes into three sidecars, all fitting
only the anchor rung on train/development rows:

| Recipe | Estimand | k | What it is for |
|---|---|---|---|
| `seed-sweep` | `fit-noise` | 5 | provenance: how much the FIT moves. Never the bar. |
| `paired-bootstrap` | `paired-comparison` | 200 | **the bar**: how much a DIFFERENCE between two candidates moves on the same rows. |
| `split-lottery` | `marginal-resplit` | 10 | how much one candidate's own score moves when the development draw changes — the right yardstick for reading an anchor residual, reported in findings, never a rule. |

All three are registered with `klein sweep register`. `klein noise-floor --recipe
paired-bootstrap --estimand paired-comparison` prints the contract block;
`minimum_delta = max(2×std, range/2)` and `metric.bound.ideal: 1.0` go in through a
consult re-record with a reason.

**Phase `adaptive-1` (4 experiments).**

| # | Candidate | Reference rung (refit on the same rows) | Tests |
|---|---|---|---|
| E0001 | `glm_ohe_balanced` — the v1 split-identity anchor | none | P1 |
| E0002 | `glm_splines_isotonic` — quantile-knot splines + log1p + 2 interactions + isotonic cv=5 | `glm_ohe_balanced` | P2, P3 |
| E0003 | `hgbt_balanced` — the verbatim v1 tree rung | `glm_splines_isotonic` | P4, P5 |
| E0004 | `glm_ohe_none_isotonic` — the doctrine A/B: `class_weight=None` + isotonic | `glm_ohe_balanced` | P6 |

E0004 is expected to DISCARD on the AUC frontier and to win on calibration. That is the
point of the run, and the disposition is recorded honestly rather than avoided.

**Phase `confirmation` (1 experiment).** `klein run-one --final-test --dry-run` first —
mandatory, and study 09 lost its only seal to a crash that happened before any data was
read — then E0005: the selected candidate, once, on the sealed half, testing P7.

**After the loop.** `klein replicate E0003` for a `rep:` record; `klein predict
adjudicate P8` against the Phase 0 paired-bootstrap sidecar.

## Controls

- **Negative control:** the DATA gate's mechanized four-row clean-room leakage audit
  (`python -m kleinlib.leakage`), whose constant-predictor and label-shuffled rows must
  score at chance. A pipeline that cannot score chance at chance cannot be trusted with
  0.66.
- **Positive control:** E0001, which reproduces a number an independent study already
  recorded on the same training rows. If the port were broken, the anchor is where it
  shows — which is why it runs first and why a miss stops the study rather than being
  absorbed into the ladder.

## Deliverables

`findings.md` (seven sections, §⑤ headed **Business / actuarial value implications**) +
`claims.lock` + `referee_report.md` + `report/index.html` (§6 headed **Model coding
advice**), plus the insurance profile's classification figure set: ROC, PR, reliability,
decile lift, Lorenz/Gini, and the decision trajectory.

No `materiality:` block is registered. Nothing in this study is priced, so findings may
say a registered bar was cleared and may never say "material" or "actionable".
