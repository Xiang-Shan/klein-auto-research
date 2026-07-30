# Program — 03-noisy-rosenbrock-dfo

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: At a fixed 200-evaluation budget on noisy Rosenbrock (sigma=0.5), do restarts beat plain Nelder-Mead, and does SPSA beat both?
- Track: `primary`
- Primary metric: `mean_final_gap` (lower is better; minimum meaningful
  delta 0.5695 = 2× the measured seed-block std, k=5)
- Results are exploratory until the track's one sealed final-test run confirms them.
  A small delta without uncertainty must not be described as real or decisive.

## Data and split

- Source: synthetic:noisy_rosenbrock_v1 — generated locally, known truth f*=0 at (1,1),
  evaluation noise N(0, 0.5^2), hard budget 200 evaluations per rep, R=40 reps per
  experiment.
- Split kind `none`: comparability = fixed seed blocks (objective.py). Development
  block 42..81; noise-floor measurement blocks 142.., 242.., 342.., 442..; sealed
  final-test block 10042..10081, touched once via `klein run-one --final-test`.
  `prepare.py` proves the blocks disjoint mechanically.
- Gate 1 records the prepared-data SHA-256 (the reference cell) and split-policy
  fingerprint.

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/03-noisy-rosenbrock-dfo`, and run
   `uv run --locked klein preflight --study .`.
5. Edit `train.py`, then
   `uv run --locked klein run-one --study . --track primary --description ...`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `train.py` to the pre-candidate
base commit.

## Decisions (append-only)

- 2026-07-30 — schema-v2 study scaffolded; gates pending.
- 2026-07-30 — CONSULT ack basis: the user approved this exact study design
  (goal, phases, RQs with priors, predictions incl. one engineered crash) in the
  Stage-1 plan; phase-boundary acks are recorded on the same basis and each STOP
  is documented here.
- 2026-07-30 — prepare.py generated the reference cell: anchor config
  (single-start NM, budget 200, dev block) mean_final_gap 1.251208 over 40 reps.
- 2026-07-30 — DATA-gate clean-room audit finding (pre-loop): random search
  (200 uniform samples) scores 0.397 vs the anchor's 1.251 — the no-information
  baseline beats single-start NM 3.2× under noise. Noiseless probe = exact 0.0
  (harness sane; the noise is the story). The bar for "restarts pay" is 0.397.
  RQ1's prior strengthens; the interesting comparison is restarts vs random
  search, not restarts vs the stalled anchor.
## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
- 2026-07-30 — Phase-0 noise floor measured: anchor config across 5 disjoint
  seed blocks → mean 1.725, std 0.2848, range 0.749. minimum_delta set to
  0.5695 (= 2×std). The dev block (1.251) is the LUCKIEST of the five — a
  block-level reminder that single-block deltas below 0.57 are weather, not
  climate. Consult gate re-recorded with the amended contract.
- 2026-07-30 — CONTRACT AMENDMENT (framework lesson, logged as defect A20): the
  phase ladder was edited after scaffold to insert `phase0-anchor`, but phase
  state anchors at scaffold time — the machine ran E0001 under `adaptive-1` and
  a pre-current phase can never be acknowledged retroactively. Folded the anchor
  into `adaptive-1` (max_experiments 6 = anchor + 5 adaptive; budgets summed);
  consult re-recorded. The framework now preflight-fails this drift instead of
  ignoring it.
