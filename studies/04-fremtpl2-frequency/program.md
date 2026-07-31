# Program — 04-fremtpl2-frequency

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: On freMTPL2 claim frequency, does gradient boosting beat a well-specified GLM by more than the measured noise floor in Poisson deviance?
- Track: `primary`
- Primary metric: `val_poisson_deviance` (lower is better; minimum meaningful
  delta 0)
- Results are exploratory until the track's one sealed final-test run confirms them.
  A small delta without uncertainty must not be described as real or decisive.

## Data and split

- Source: data_hub:freMTPL2
- Adaptive work uses train + development only. The test partition stays sealed.
- Gate 1 records the prepared-data SHA-256 and split-policy fingerprint.

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/04-fremtpl2-frequency`, and run
   `uv run --locked klein preflight --study .`.
5. Edit `train.py`, then
   `uv run --locked klein run-one --study . --track primary --description ...`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `train.py` to the pre-candidate
base commit.

## Decisions (append-only)

- 2026-07-31 — schema-v2 study scaffolded; gates pending. Ack basis for consult
  and phase boundaries: the user commissioned this exact study as the Stage-2
  soak ("freMTPL2, claim frequency, GLM vs GBDT, full lifecycle") — logged
  friction goes to ~/../SOAK_LOG (outside the repo).
- 2026-07-31 — metric registry has no deviance metrics (soak F1): study runs as
  task_type simulation with the custom scalar metric val_poisson_deviance
  (exposure-weighted mean Poisson deviance, computed in pipeline.py).
- 2026-07-31 — prepare.py: hub table carried 46 derived/leakage/dummy columns
  (incl. Frequency = the target); kept the 12 raw columns. 678,013 rows,
  26,406 claims, 358,360 exposure-years. Null-model dev deviance 0.473037
  (the reference cell). Zero rows needed the literature caps — this Kaggle
  variant ships pre-clipped (provenance nuance on the data card).
- 2026-07-31 — off-ledger train.py smoke polluted aux_metrics.tsv (soak F2);
  sidecar truncated back to header before any ledger run.
## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase adaptive-1 slate (2026-07-31)

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | GLM + shaping (log-density, age/BM splines) — RQ2 | 2 | 3 | 3 | 8 |
| 2 | HGBT poisson baseline (OHE) — RQ1 | 3 | 3 | 3 | 9 |
| 3 | HGBT native categoricals — RQ3 (encoder claim) | 2 | 3 | 3 | 8 |
| 4 | HGBT capacity lever (max_leaf 31→63) | 2 | 3 | 2 | 7 |
| 5 | Interaction-aware GLM (Area×VehGas) | 2 | 2 | 2 | 6 |
| 6 | Tweedie pure-premium track | 3 | 1 (needs severity + new track) | 3 | 7 |

Chosen order: 1 → 2 → 3 → 4 (fills adaptive-1's 4 remaining slots; RQ-coverage
first, capacity probe last). 5 and 6 defer — 6 to a future study with a
severity track. Survivors mirrored to playbook.md.

- 2026-07-31 — Phase-0 noise floor, three views (soak F4): HGBT fit-seed sweep
  k=5 std 0.000210 (suggested 0.00042); marginal dev-fold bootstrap SE 0.005391
  (suggested 0.01078); PAIRED-difference bootstrap (GLM vs HGBT, same rows,
  n_boot=200) SE 0.000893. minimum_delta set to 0.001786 = 2x paired SE — the
  correct floor for a COMPARISON study; the marginal SE overstates comparison
  noise 6x because both models share each bootstrap row's shot noise. Preview
  from the measurement (not a ledger row): HGBT baseline ~0.4449 vs GLM 0.4549,
  paired delta 0.0101 = 11.3 paired SEs. Consult re-recorded.
- 2026-07-31 — E0002 keep 0.453073, delta 0.001788 = 1.001x minimum_delta — a
  keep by 0.000002. CAVEAT (honest implementation note): glm_shaped applies
  SplineTransformer AFTER the OHE preprocessor, so the spline basis covers the
  dummy columns too, not just the numerics as intended; gain may understate
  proper scoped shaping. Follow-up (column-scoped splines) queued for ⑦ —
  adaptive slots are reserved for RQ1/RQ3 per the slate.
