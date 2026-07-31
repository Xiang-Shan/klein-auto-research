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
## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
