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

### Phase adaptive-1 slate (2026-07-30)

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | NM adaptive=True (Gao-Han) — within-floor calibration probe | 2 | 3 | 3 | 8 |
| 2 | 4×50 restarts — H1/RQ1, must clear 0.5695 AND beat random-search 0.397 to matter | 3 | 3 | 3 | 9 |
| 3 | SPSA a0=50 — registered divergence prediction (honest crash) | 3 | 3 | 2 | 8 |
| 4 | SPSA a0=0.1 tuned — RQ2 | 3 | 3 | 3 | 9 |
| 5 | 8×25 restarts — RQ3 fragmentation | 2 | 3 | 3 | 8 |
| 6 | pure random search as a ledger experiment (data-card finding) | 3 | 3 | 3 | 9 |

Chosen order: 1 (cheapest, demonstrates the measured floor) → 2 → 3 → 4 → 5,
which exactly fills adaptive-1's remaining budget (max_experiments 6 incl. the
anchor). Candidate 6 scores 9 but is DEFERRED to the next study — the
pre-registered predictions cover 1–5, and pre-registration discipline outranks
in-flight curiosity; random search's 0.397 stands as data-card evidence.
Survivors mirrored to playbook.md.
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
- 2026-07-30 — adaptive-1 progress + MID-PHASE RE-PLAN. E0002 discard: Gao-Han
  adaptive coefficients are IDENTICAL to standard NM at n=2 (chi=2, psi=sigma=1/2)
  — the probe was a mathematical no-op, delta exactly 0. E0003 KEEP 0.4071: clears
  the anchor by 0.844 = 2.96x floor std (prediction "≥3x" essentially held) — but
  only TIES random search (0.397): local polish buys ~nothing at 50 evals/start
  under sigma=0.5. E0004 discard 1.1e+196: the registered CRASH prediction is
  FALSIFIED on mechanism — SPSA divergence saturates FINITE (decaying gains
  self-limit; off-ledger probes: a0=500 → 1e81, a0=5000 → 1e97, never inf).
  RE-PLAN: the honest crash lives in the estimator's own denominator — c0=0
  divides by zero (verified off-ledger: immediate ZeroDivisionError). E0005 =
  SPSA c0=0 (registered crash, mechanism corrected); E0006 = tuned SPSA a0=0.1
  (RQ2). The 8x25 fragmentation probe (RQ3) is DEFERRED — verdict will read
  untested/inconclusive; it joins random-search-as-experiment in the next-study
  queue. Slate discipline note: the re-plan swaps ONE registered candidate for a
  corrected version of another registered candidate; both changes logged here
  before the runs.
- 2026-07-30 — adaptive-1 phase boundary STOP. Ledger 6/6: E0001 keep 1.2512
  (anchor), E0002 discard (Gao-Han no-op), E0003 KEEP 0.4071 (incumbent),
  E0004 discard 1.1e196 (finite divergence), E0005 crash (c0=0 denominator),
  E0006 discard 1.9e178 (mis-scaled "textbook" gains). Summary + trajectory
  regenerated; playbook refreshed. Ack basis = pre-approved plan; proceeding
  to the sealed confirmation of E0003's config.
