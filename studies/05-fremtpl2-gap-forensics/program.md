# Program — 05-fremtpl2-gap-forensics

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: On freMTPL2 claim frequency, WHERE does a gradient-boosted model's Poisson-deviance advantage over a spline-shaped GLM live, how much of it transfers back into GLM-representable structure, and does the gap itself survive two sealed final-test evaluations?
- Tracks: `glm` and `gbdt` — the sealed-gap redesign queued by study 04. Each track
  owns `val_poisson_deviance` (lower) with its own measured minimum_delta and ONE
  sealed final-test access; the headline gap = difference of two sealed numbers.
- minimum_delta 0.001786 is PROVISIONAL (study 04's paired floor) until the anchor-0
  measurement sweeps replace it; the consult gate is re-recorded then.
- Results are exploratory until each track's sealed final-test run confirms them.
  A small delta without uncertainty must not be described as real or decisive.

## Data and split

- Source: data_hub:freMTPL2
- Adaptive work uses train + development only. The test partition stays sealed.
- Gate 1 records the prepared-data SHA-256 and split-policy fingerprint.

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/05-fremtpl2-gap-forensics`, and run
   `uv run --locked klein preflight --study .`.
5. Edit `train.py`, then
   `uv run --locked klein run-one --study . --track glm --description ...`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `train.py` to the pre-candidate
base commit.

## Decisions (append-only)

- 2026-07-31 — schema-v2 study scaffolded; gates pending.
- 2026-07-31 — CONSULT fast-path taken: the brief (an approved cross-session plan,
  itself built on study 04's findings and a repo/protocol scout) answers all six
  consult questions — goal, data (data_hub:freMTPL2, prep frozen to study 04's),
  method familiarity (full method card for LGBM/CatBoost/surrogate-distillation),
  metric + decision use (val_poisson_deviance per track; deliverable feeds a CAS
  seminar 2026-08-28 but stands alone), budget (420 s/run; four phases), deliverable
  form (findings + tutorial + claim-cited checklist). Two-track sealed-gap design
  chosen over single-track to close study 04's protocol caveat. RQ1-RQ7 + six
  predictions-to-falsify recorded in study.yaml. Acknowledged by xiang.
- 2026-07-31 — Anchor comparability decision: prep is study 04's byte-for-byte
  (SHA-256 asserted); the 4,872 duplicate feature profiles straddling train/dev and
  the pre-clipped hub Exposure are recorded as data-card NOTEs and findings
  limitations, NOT "fixed" — changing prep would break the 0.454861/0.444689
  anchors and destroy cross-study comparability.
- 2026-07-31 — Pre-loop evidence (off-loop, sanctioned smoke + library sanity, not
  ledger rows): prepare.py reproduces study 04's corpus exactly (678,013 rows /
  26,406 claims / 358,360.1 exposure-years; null dev deviance 0.473037 matches
  study 04's card; prepared sha256 db82e802…1cf948). KLEIN_SMOKE glm_ohe through
  the v0.4.0 registry path prints val_poisson_deviance 0.454861 — anchor-exact,
  registry ≡ study-04's hand-rolled metric (soak-F1 friction is CLOSED by v0.4.0).
  Constructor sanity on dev fold: hgbt_ohe 0.444689 (anchor-exact, calibration
  1.0149 = archived pricing-eval card), lgbm_poisson 0.444413 (RQ2 tie prior looks
  close — formal verdict at E0003), catboost_poisson 0.446332 via
  prediction_type="Exponent" (raw-score trap handled; calibration 1.0164 sane).
  Fit times 1.1-6.7 s — far inside the 400 s guardrail.
- 2026-07-31 — Value-level audit at prep: IDpol fully unique (hub README's
  "non-unique" claim is wrong for this table); 149,248 duplicate 9-feature
  profiles TOTAL (the 4,872 figure from study 04 is the train/dev STRADDLE count —
  both true, different measures).
- 2026-07-31 — DATA gate recorded (GO-WITH-CAUTIONS, clean-room audit 9/9
  mechanized clean). Standing directives adopted from the card: (a) 26.54% of dev
  rows have a 9-feature twin in train (31,798 straddling groups; twins are
  claim-poor, 1.97% claim-bearing) → REPORT THE GAP, never absolute deviance
  levels; (b) interaction pairs for glm_interactions must be derived from the
  train-fold surrogate ONLY, with the chosen pairs + their surrogate ranking
  recorded in the candidate description (lookahead guard no static check
  catches); (c) rate outliers (ClaimNb/Exposure up to 365) stay — exposure
  weighting handles them, never filter; (d) Exposure lower clip binds 1,060 rows
  at 1/365.25 (prepare's counter counts only outside-(0,1] rows — under-reports
  by design, recorded); (e) Density has a real censoring ceiling: 1.55% of rows
  pinned at exactly 27,000.
- 2026-07-31 — METHOD gate recorded (full card, triad complete, 18/18 refs
  verified). Loop disciplines adopted from card risks R1-R9: (R1) HGBT
  early_stopping="auto" engages >10k rows → nominal max_iter is NOT matched
  capacity; effective_trees now logged to aux on every GBDT row; RQ2's verdict
  must cite effective counts, with M1-b (match effective tree count) as the
  follow-up lever if the tie breaks. (R2) hgbt_monotone confounds
  native-encoding with the constraint → study 04's E0004 hgbt_native 0.445343
  (same split/prep, tag v1.0.0) is the unconstrained control; an in-study native
  control is the designated reserve-slot use if the comparison gets close. (R3)
  CatBoost on CPU defaults boosting_type=Plain → RQ3's claim is about the
  CTR+symmetric-tree package, NOT ordered boosting; M2-a (one_hot_max_size=32)
  is the isolation lever. (R4) never inline a raw CatBoostRegressor in train.py
  (RawFormulaVal trap — wrapper only). (R5) all three models carry ~+2% A/E
  (calibration 1.02) → reported every row, never recalibrated (would break
  anchors). (R6) segment shares: ≥8 quantile bins, exposure share alongside,
  bootstrap before quoting. (R7) surrogate basis is numeric-only → categorical
  interactions invisible; cross-check with two_way_pd_gap; state the blind spot
  explicitly if forensics localises the gap categorically. (R8) R²_main is a
  log-score diagnostic, not a deviance bound. (R9) 26.54% dev twin straddle →
  the GAP is robust, the levels are optimistic — RQ1 wording fixed accordingly.
  Eight additional predictions-to-falsify levers (M1-a…M5-a) are queued to enter
  study.yaml together with the measured floors at the consult re-record (one
  yaml edit, one hash re-bind).
- 2026-07-31 — adaptive-1 (anchors + metrology) COMPLETE. E0002 keep glm anchor
  0.454861 (registry path, anchor-exact); E0003 keep gbdt anchor 0.444689
  (anchor-exact) with the phase's headline discovery: **effective_trees = 67** —
  sklearn early_stopping="auto" truncated the nominal-200 config (method-card R1
  CONFIRMED; M1-a lever resolved). Floors measured (sweeps committed):
  glm fit-seed std EXACTLY 0 (k=5, deterministic — the degenerate floor is the
  finding); gbdt fit-seed std 0.000210 (= study 04's); paired CRN bootstrap
  B=1000: glm-pair SE 0.000270, gbdt-pair SE 0.000287, cross SE 0.000963.
  minimum_delta set: glm 0.000539, gbdt 0.000573 (max rule). Dev gap +0.010172 =
  10.6× cross paired SE. Pre-loop signals for the slate: LGBM−HGBT −0.000276
  (0.96× SE, tie prior alive but capacity-confounded — LGBM built 200 trees vs
  HGBT's 67); CatBoost +0.001643 (2.9× gbdt floor, deficit real-looking);
  scoped-splines closure only 16.8% vs leaky study-04 shaping's 18% — RQ4's
  30-45% prior now DOUBTED, honest-no candidate.
- 2026-07-31 — FRICTION F1 (this study): E0001 printed the anchor-exact metric
  (0.454861) but was dispositioned discard — "guardrail metric 'wall_seconds'
  missing". Cause: `evaluate_regression` writes wall_seconds into aux_metrics.tsv
  but does NOT print it in the canonical/aux block, and the runner's guardrail
  check reads the PRINTED metrics; study 04 avoided this by passing wall_seconds
  explicitly via `extra` (now understood as load-bearing, not decorative). Fix =
  E0002's candidate diff (one line: wall_seconds into extra); adaptive-1
  max_experiments raised 2→3 to un-burn the slot, recorded in the contract
  description; consult re-recorded. Framework-improvement candidate for the
  study's findings §⑦: evaluate_regression should print wall_seconds, or
  preflight should warn when a declared guardrail metric is not among the
  printed keys.
## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
