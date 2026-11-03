# Program — 22-cnn-data-scaling

## Roster

Who is doing what, and on what. REFEREE cites this table for the independence rung
(`references/referee-protocol.md`); a blank `experimenter` row caps the achievable
rung at "fresh session", because no artifact then says what ran the loop. Fill the
experimenter row at CONSULT and update a row whenever its model, tool or session
changes.

| Role | Who (model · tool · session) | Since |
| --- | --- | --- |
| consultant | lead agent (Claude Code orchestrating session) — drafted the contract | 2026-11-03 |
| instrument builder | general-purpose subagent · Claude Code — wrote prepare.py, lib/protocol.py, the first analyze.py; trained only at smoke budget | 2026-11-03 |
| experimenter | `klein-experimenter` subagent (Sonnet tier) · Claude Code · a fresh subagent context per phase | 2026-11-03 |
| data-gate auditor | `klein-data-auditor` subagent (Sonnet tier) · Claude Code | 2026-11-03 |
| method scholar | `klein-method-scholar` subagent (Opus tier) · Claude Code | 2026-11-03 |
| synthesist | `klein-synthesist` subagent (Opus tier) · Claude Code | 2026-11-03 |
| referee | `klein-referee` subagent (Opus tier) · Claude Code · fresh context that never saw the loop (rung: different model than the experimenter) | 2026-11-03 |
| lead | lead agent, acting on the repository owner's delegation | 2026-11-03 |

**Acknowledgements are delegated.** The repository owner approved the Klein 2.3 plan
that commissions this exhibit, and that approval delegates the CONSULT, DATA, METHOD
and phase acknowledgements of exhibits 20-24 to the lead agent; each is recorded as
`--acknowledged-by lead-agent` with this note, the convention studies 10-15 used.
The referee verdict is never delegated: it is the referee subagent's own.

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: Estimate the data-scaling exponent of a small CNN's test cross-entropy on Fashion-MNIST, and test whether the power law fitted on small training sets predicts the loss at the full training set (a sealed extrapolation).
- Tracks (both registered):
  - `primary` — `val_mlogloss` of one cell = one training-set size N, a 3-seed array
    (`entrypoint.seeds`); each seed draws its own N-item subsample, so data-sampling
    variance is inside the cell. The training protocol is fixed in `lib/protocol.py`
    (outside the mutable surface): a cell only sets N.
  - `exponent` — `scaling_exponent` alpha of L(N) = a N^(-alpha) fitted on log-log axes
    over every pinned development cell, with `fit_r2`; confirmation is a replication.
- Execution: `entrypoint.execution: [local, detached]` — the six cells run as detached
  jobs (`klein run-one --detach` → `klein job exec` → `klein run-one --collect`), the
  exhibit for Klein 2.3's detached transaction; the referee weighs them as attested.
- Predictions P1-P4 are registered in study.yaml with arithmetic rules.

## Data and split

- Source: Fashion-MNIST (Xiao et al. 2017, MIT licence), the four IDX files from
  zalandoresearch/fashion-mnist, each a `url:` pin with sha256 (`data.source` + `data.inputs`).
- Lanes (predefined, by position — no seed): train = official train rows 0-49,999;
  development = official train rows 50,000-59,999; test = the official 10,000 t10k
  images — SEALED, read once by the full-data cell.
- Adaptive work uses train + development only.
- Gate 1 records the prepared-data SHA-256 and split-policy fingerprint.

## Instrument notes and lead decisions (2026-11-03, before DATA)

- Network: a 3-conv CNN with global average pooling (23,946 parameters), chosen over the
  recipe's two-block net (5,130), which pools globally at 14x14. AdamW 1e-3, wd 1e-4,
  batch 128; steps = max(400, ceil(20 epochs x 0.9N / 128)) capped at 12,000; best
  inner-validation (10% of N) checkpoint kept. All in `lib/protocol.py`, outside the surface.
- Subsamples are nested across N within a seed (common random numbers along the curve);
  the seed-resampling bootstrap of alpha therefore errs wide, and with 3 seeds the
  percentile bootstrap understates variance by ~2/3 — `lib/scaling.py` notes both.
- The 400-step minimum trains small cells for many epochs (N=500: ~114); the best-checkpoint
  rule limits overfitting, and the method card must discuss it.
- Decision: `TORCH_THREADS = 1` (robust under contention from sibling studies; ~2x slower
  when the machine is quiet).
- Decision: `max_run_seconds` 1800 -> 5400: it bounds the whole 3-seed array, and the
  sealed N=60,000 array needs about 1,800 s at 1 thread.
- Decision: the sealed DRY run trains only `DRYRUN_STEPS = 60` steps — it rehearses the
  path; a full-budget N=50,000 rehearsal would preview the extrapolation on development
  data.
- Framework fixes reached this study before any run: one confusion table per seed, and
  the array's aux rows written by the notary (seed means + spread).

## Lead decisions after the DATA/METHOD review (2026-11-03, before any cell)

- DATA: the 64-bit dHash audit flagged 56% of held-out images (none byte-identical): a
  tooling false positive on 28x28 silhouettes. Framework fix: `--pixel-rmse` (exact
  pixel-nearest reference, RMS grey levels) and the sealed partition audited against
  train + development (the sealed fit pool). `prepare.py` removes genuine copies at
  <= 4 grey levels RMS: 8 development (vs train) and 5 test (vs train + kept development).
  The sealed fit pool is therefore 59,992 (`lib/protocol.py: N_FULL`), and P3's wording
  says so; the rule and threshold are unchanged.
- METHOD: three sharper predictions from the method card's analysis (theory and synthetic
  checks only, no data) are registered before any cell: P5 (alpha in [0.15, 0.32]),
  P6 (signed extrapolation error in [0.03, 0.25]), P7 (the full-pool cell's best
  checkpoint at or after step 6,329 of 8,437: compute-limited).
- METHOD: `lib/scaling.py`'s claim that the seed bootstrap "errs wide" is withdrawn — the
  synthetic checks show it can be too narrow for the nested-subsample component; the
  printed interval is descriptive, never a calibrated 95% interval. `lib/protocol.py`'s
  receptive-field and thread-count notes corrected (18x18 per conv3 unit; 1 thread).

## Phases and registered predictions (mirror of study.yaml)

| Phase | Cells | Predictions |
| --- | --- | --- |
| cells | primary · N = 500, 1k, 2k, 4k, 8k, 16k (detached, 3 seeds each) | — (measurements) |
| fit | exponent · the power-law fit | P1 — alpha in [0.10, 0.60]; P2 — fit_r2 >= 0.98; P5 — alpha in [0.15, 0.32] |
| confirmation | primary · the full pool (59,992) on the sealed test, after its dry run | P3 — abs rel. error <= 0.20; P4 — rel. error > 0; P6 — rel. error in [0.03, 0.25]; P7 — best_step >= 6,329 |

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/22-cnn-data-scaling`, and run
   `uv run --locked klein preflight --study .`.
5. Set `CELL["n_train"]` in `analyze.py`, then
   `uv run --locked klein run-one --study . --track primary --detach --description ...`,
   `uv run --locked klein job exec runs/E####/job.json`, and
   `uv run --locked klein run-one --study . --collect E####`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `analyze.py` to the pre-candidate
base commit.

## Decisions (append-only)

- 2026-11-03 — schema-v3 study scaffolded from recipe `dl-scaling`, typed
  estimate · image · ml-research.
- 2026-11-03 — Decision: six sizes at doubling spacing (500 … 16,000) — 1.5 decades for
  the fit, and a 3.75x extrapolation to the full 60,000 for the sealed test.
- 2026-11-03 — Decision: the training protocol scales steps with N (20 epochs, at least
  400 steps) and keeps the best inner-validation checkpoint, so small cells are not
  over-trained into a loss that measures overfitting rather than data.
- 2026-11-03 — Decision: the sealed cell's relative error is computed per seed against
  the PINNED fit (tables/scaling_fit.tsv) and the notary averages it; the fit is frozen
  before the sealed access.

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase cells slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | Cell N=500 (detached, 3 seeds): highest loss, anchors the fit's left end; expect best_step well below 400 steps cap (overfit-limited) | 3 | 3 | 3 | 9 |
| 2 | Cell N=1000: first doubling; expect loss drops by ~2^-alpha (0.75-0.90x) | 2 | 3 | 3 | 8 |
| 3 | Cell N=2000: expect monotone decline; checks the curve is not already flattening | 2 | 3 | 3 | 8 |
| 4 | Cell N=4000: mid-curve; seed spread should shrink | 2 | 3 | 3 | 8 |
| 5 | Cell N=8000: expect best_step near the end of its budget (compute-limited onset) | 2 | 3 | 3 | 8 |
| 6 | Cell N=16000: longest cell, anchors the extrapolation base; wall time under load is the risk | 2 | 2 | 3 | 7 |

Order chosen: ascending N (cheapest first, fail-fast on the detached path). All six are
required by the fit phase, so none is dropped. No cell adjudicates a prediction.

### Cell journal
- 2026-11-03 — E0001 N 500 mean 0.8296 sd(ddof1) 0.0349 seeds [0.853675, 0.789615, 0.845652] best_step [400, 400, 350] wall 110.965 detached False 4 cpu x86_64 measured; hardware: 4-cpu x86_64 Linux VM, no GPU, torch 2.13 cpu path; local-executor worktree, attested (observed_by_notary false).
- 2026-11-03 — E0002 N 1000 mean 0.9492 sd(ddof1) 0.0626 seeds [1.002682, 0.964452, 0.880389] best_step [350, 400, 400] wall 119.643 detached False 4 cpu x86_64 measured; hardware: 4-cpu x86_64 Linux VM, no GPU, torch 2.13 cpu path; local-executor worktree, attested (observed_by_notary false).
  - Observation (E0002): N=1000 mean loss 0.949 is HIGHER than N=500's 0.830 (non-monotone). Both cells use the 400-step floor (114 vs 57 epochs) and best_step sits at the 350-400 end of the budget, i.e. the small cells are compute-limited, not data-limited. Recorded as measured; no retry. Bears on the fit (P2) and the method card's 400-step-minimum caveat.
- 2026-11-03 — E0003 N 2000 mean 0.8408 sd(ddof1) 0.0261 seeds [0.846524, 0.863479, 0.812273] best_step [400, 400, 400] wall 111.227 detached False 4 cpu x86_64 measured; hardware: 4-cpu x86_64 Linux VM, no GPU, torch 2.13 cpu path; local-executor worktree, attested (observed_by_notary false).
  - Observation (E0003): N=2000 mean 0.841; the curve is flat-to-noisy so far (0.830, 0.949, 0.841) with all best_steps at the 350-400 floor. Steps only exceed the 400 floor from N=4000 (563 steps), so the first three cells share an identical step budget.
- 2026-11-03 — E0004 N 4000 mean 0.7570 sd(ddof1) 0.0254 seeds [0.727778, 0.773272, 0.769948] best_step [550, 563, 550] wall 154.047 detached False 4 cpu x86_64 measured; hardware: 4-cpu x86_64 Linux VM, no GPU, torch 2.13 cpu path; local-executor worktree, attested (observed_by_notary false).
  - Observation (E0004): N=4000 mean 0.757, the first cell above the 400-step floor (563 steps) and the first clear drop; best_step 550-563 is again at the end of the budget (compute-limited at every cell so far).
- 2026-11-03 — E0005 N 8000 mean 0.6523 sd(ddof1) 0.0072 seeds [0.650137, 0.646519, 0.660363] best_step [1100, 1100, 1100] wall 288.066 detached False 4 cpu x86_64 measured; hardware: 4-cpu x86_64 Linux VM, no GPU, torch 2.13 cpu path; local-executor worktree, attested (observed_by_notary false).
  - Observation (E0005): N=8000 mean 0.652 (sd 0.007), best_step 1100 of 1125 in all seeds: still compute-limited at the end of the budget. Wall time ~2x the N=4000 cell.
- 2026-11-03 — E0006 N 16000 mean 0.5637 sd(ddof1) 0.0077 seeds [0.572035, 0.556876, 0.562141] best_step [2240, 2240, 2128] wall 566.404 detached False 4 cpu x86_64 measured; hardware: 4-cpu x86_64 Linux VM, no GPU, torch 2.13 cpu path; local-executor worktree, attested (observed_by_notary false).
  - Observation (E0006): N=16000 mean 0.564 (sd 0.008), best_step 2128-2240 of 2250. All six cells measured; phase boundary reached (no phase gate recorded by the experimenter). Pattern: loss falls monotonically from N=1000, but N=500 < N=1000 (the 400-step floor gives N=500 114 epochs vs 57), and every cell's best checkpoint is at the end of its budget, so the curve measures a compute-limited protocol; the fit phase should read alpha with that caveat (P7 is the same question at the full pool).

### Phase fit slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | Exponent cell: OLS log-log fit over all six pinned cells as registered (adjudicates P1 alpha in [0.10,0.60], P2 fit_r2>=0.98, P5 alpha in [0.15,0.32]) | 3 | 3 | 3 | 9 |
| 2 | Refit dropping N=500 (post-hoc robustness; NOT registered, would not be pinned as the fit) | 2 | 2 | 2 | 6 |
| 3 | Refit over N>=4000 only (compute-limited regime check) | 2 | 2 | 2 | 6 |

Chosen: #1 only; all six cells enter as registered. Expectation from the journal: the non-monotone N=500/1000 pair makes P2 (fit_r2 >= 0.98) at real risk.

### Fit result (E0007, exponent track, six cells as registered)

alpha = 0.1304 (bootstrap interval 0.1181 to 0.1411, descriptive only, ci_clamped 0), fit_r2 = 0.7955, a = 2.1258, predicted loss at N_FULL (59,992) = 0.5066. P1 supported; P2 refuted; P5 refuted.

- 2026-11-03 — Decision: P2 refuted (fit_r2 0.796 < 0.98). Cause visible in the cell journal: N=500 (0.830) lies below N=1000 (0.949), and the N<=2000 cells share the 400-step floor, so the small end is flat/non-monotone; a pure power law over all six cells does not describe the curve. Not repaired by dropping N=500 (registered as six cells); any robustness refit is a post-hoc exploratory note, not the pinned fit.
- 2026-11-03 — Decision: P5 refuted (alpha 0.130 < 0.15). The effective exponent is flatter than predicted, consistent with the flat small-N end and compute-limited cells pulling the slope down. P1 (wide band) supported. The pinned law (a=2.126, alpha=0.130) is frozen for the sealed extrapolation as registered; the flat small-N end means it likely predicts a loss at N_FULL (0.507) that is higher than a steeper large-N law would, so P4's sign (measured above prediction) is now doubtful.
