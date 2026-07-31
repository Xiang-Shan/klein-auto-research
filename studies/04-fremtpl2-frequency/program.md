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

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
