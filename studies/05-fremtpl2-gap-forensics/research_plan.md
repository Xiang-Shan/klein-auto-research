# Research plan — 05-fremtpl2-gap-forensics

## Question

On freMTPL2 claim frequency, WHERE does a gradient-boosted model's Poisson-deviance
advantage over a spline-shaped GLM live, how much of it transfers back into
GLM-representable structure, and does the gap itself survive two sealed final-test
evaluations?

Framing guard: every research question is a WHERE / HOW-MUCH / WHEN question. None is
"which model wins" — the deliverable is a mechanism and a condition (a
dataset-characteristics → method-choice checklist), not a leaderboard row.

## Lineage

Direct sequel to `04-fremtpl2-frequency` (archived at tag v1.0.0), which established
the gap (GLM-OHE 0.454861 → HGBT 0.444689, Δ 0.010172 = 11.4 paired-bootstrap SEs)
but left it exploratory-by-construction (one sealed access on a single track) and
explicitly queued a two-track sealed-gap redesign. This study executes that redesign
and adds the forensics/translate-back layer study 04 did not attempt.

## Contract

- Domain: insurance
- Data: data_hub:freMTPL2, prep IDENTICAL to study 04 (12-column allowlist,
  ClaimNb ≤ 4, Exposure ∈ [1/365.25, 1], random 60/20/20 seed 42, y = rate with
  exposure weights). Prepared-file SHA-256 asserted equal to study 04's.
- Tracks: `glm` and `gbdt`, each owning `val_poisson_deviance` (lower) with its own
  measured minimum_delta and one sealed final-test access.
- The 0.001786 minimum_delta at scaffold is PROVISIONAL (study 04's paired floor);
  anchor-0 re-measures fit-seed and paired-bootstrap floors for THIS study and the
  consult gate is re-recorded with the measured values.
- Method depth: full (LightGBM/CatBoost/surrogate-distillation card).
- Per-run maximum: 420 s; per-track guardrail wall_seconds ≤ 400.

## Validation policy

Adaptive choices use train/development only. Each track spends its ONE sealed
final-test access in the confirmation phase; both sealed runs export holdout
predictions (`kleinlib.eval.save_holdout_predictions`, dims DrivAge, BonusMalus,
VehGas, Region). After both accesses are spent, an off-ledger join computes the
sealed gap and its paired-difference bootstrap SE — legitimate because each access
already happened, one per track, sanctioned. Translate-back structure (interactions)
is derived from a TRAIN-fold surrogate only, evaluated on development, confirmed on
the sealed test; the number of screened vs adopted candidates is reported
(multiplicity honesty).

## Experiment ladder

Phase anchor-0 (identity, STOP on any miss):
1. E0001 [glm] GLM-OHE anchor reproduces study-04's 0.454861 to 1e-9 through the
   v0.4.0 `evaluate_regression` registry path (any mismatch = split/weight/clip
   drift — STOP).
2. E0002 [gbdt] HGBT-OHE anchor (seed 0, lr 0.1, 200 iters, 31 leaves) reproduces
   0.444689 to 1e-9.
Then three measurement sweeps (sidecar-only, no ledger rows): gbdt fit-seed k=5;
glm fit-seed k=5 (expect ≈0 — deterministic solver; recording that IS a finding);
paired-difference bootstrap (n=1000, common random numbers) within-track and
cross-track. Set per-track minimum_delta = max(2×std_fit, 2×SE_paired); re-record
consult.

Phase adaptive-1 (slate ritual first):
3. E0003 [gbdt] LightGBM poisson at matched capacity within 2× floor of HGBT (tie
   predicted — DISCARD is the expected disposition and the finding).
4. E0004 [gbdt] CatBoost native categoricals + ordered boosting vs OHE-HGBT at
   Region(22)/VehBrand(11) cardinality.
5. E0005 [glm] Column-SCOPED splines (DrivAge, BonusMalus, log1p Density only)
   close ≥30% of the gap (fixes study-04 E0002's spline-on-dummies leak).
6. E0006 [glm] + top train-fold-surrogate interaction.
7. E0007 [glm] + second interaction + binned BonusMalus = the practical GLM ceiling.
Off-ledger between phases: segment-level deviance-gap decomposition
(`forensics.segment_deviance_gap`) and the data-volume measurement sweep (RQ6).

Phase adaptive-2 (post-forensics redirect):
8. E0008 [gbdt] monotone BonusMalus constraint costs <1× floor.
9-10. E0009/E0010 reserve slots steered by the refreshed slate (e.g. Region target
   encoding on the glm track; capacity check on the gbdt track).

Phase confirmation:
11. E0011 [glm] sealed final test of the glm incumbent (+ prediction export).
12. E0012 [gbdt] sealed final test of the gbdt incumbent (+ prediction export).

## Deliverables

findings.md (7 sections, claim IDs) · report/index.html · checklist.md
(dataset-characteristics → method-choice, every row claim-cited) · gap-waterfall,
double-lift (pricing-eval), decision-trajectory, data-volume figures — these feed a
CAS seminar deck (2026-08-28) but the study stands alone.

## Honest-no outcomes (pre-registered as valid findings)

- Sealed gap does not replicate → "the gap we all quote did not survive a sealed
  test" (checklist row: seal a partition before believing a published gap).
- LGBM ≠ HGBT by >2× floor → implementations are not interchangeable.
- Scoped splines + interactions close <20% → the gap is genuinely non-additive;
  quantified price of interpretability.
- Monotone constraint costs >1× floor → filability is not free.
