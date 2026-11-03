# Program — 21-bloodmnist-cnn

## Roster

Who is doing what, and on what. REFEREE cites this table for the independence rung
(`references/referee-protocol.md`); a blank `experimenter` row caps the achievable
rung at "fresh session", because no artifact then says what ran the loop. Fill the
experimenter row at CONSULT and update a row whenever its model, tool or session
changes.

| Role | Who (model · tool · session) | Since |
| --- | --- | --- |
| consultant | lead agent (Claude Code orchestrating session) — drafted the contract | 2026-11-03 |
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

- Goal: From pixel logistic regression to a small CNN: what earns a keep under a measured floor on 8-class blood-cell microscopy images (BloodMNIST, official split), and how far does a CPU-budget CNN get toward the published MedMNIST baselines?
- Track: `primary` (frontier) — `val_macro_f1`, the seed-array mean over seeds 0, 1, 2
  (`entrypoint.seeds`); higher is better; `metric.bound.ideal: 1.0`.
- The keep bar is MEASURED at Phase 0 (an item bootstrap of the anchor's development
  macro-F1 — estimand marginal-resplit) and written into the contract by
  `klein noise-floor`; the seed-block spread is recorded as `fit_noise`, never as the bar.
- Predictions P1-P5 are registered in study.yaml with arithmetic rules.
- Results are exploratory until the one sealed test run and a replication record
  confirm them (`confirmation.require: [sealed, replicate]`).

## Data and split

- Source: MedMNIST v2 `bloodmnist.npz` (28 x 28 RGB, 8 classes), Zenodo record
  10519652, a `url:` pin with sha256. Licence: CC BY 4.0.
- Split: the dataset's OFFICIAL partitions, kept (`kind: predefined`): train 11,959,
  val -> development 1,712, test -> sealed 3,421. Whether they are grouped by patient
  or slide is a DATA-gate question.
- Adaptive work uses train + development only. The test split is read once.
- Gate 1 records the prepared-data SHA-256 and split-policy fingerprint.

## Phases and registered predictions (mirror of study.yaml)

| Phase | Cells | Predictions |
| --- | --- | --- |
| anchor | the recipe SmallCNN (anchor); a linear softmax on pixels; then the floor sweep | P2 — anchor macro-F1 >= 0.85; P1 — linear in [0.50, 0.85] |
| adaptive | one idea per candidate (normalization/depth, augmentation, schedule, width) | P3 — BN + 3 blocks + flip/rot90 + 4,000 steps >= 0.93 |
| confirmation | the incumbent on the sealed test split, after its dry run | P4 — test macro-F1 >= 0.90; P5 — test accuracy < 0.958 |

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/21-bloodmnist-cnn`, and run
   `uv run --locked klein preflight --study .`.
5. Edit `model.py` / `train.py` (one idea), then
   `uv run --locked klein run-one --study . --track primary [--tests P#] --description ...`.
   Each run is a seed array: the notary runs seeds 0, 1, 2 and decides on the mean.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores the surface (`model.py`, `train.py`) to the pre-candidate
base commit.

## Decisions (append-only)

- 2026-11-03 — schema-v3 study scaffolded from recipe `cv-classify`, typed
  predict · image · cv.
- 2026-11-03 — Decision: keep MedMNIST's official split (predefined) rather than
  re-splitting, so the sealed number is comparable with published test numbers.
- 2026-11-03 — Decision: primary metric macro-F1 (the CV profile's rule for imbalanced
  classes); accuracy is printed beside it and P5 reads it, because MedMNIST reports
  accuracy.
- 2026-11-03 — Decision (DATA gate): the official split carries 11 cross-split
  near-duplicates (dHash <= 4 bits); `prepare.py` drops them from development (3) and
  test (8). Scope limit on every claim: the official split is image-level, not grouped
  by patient or slide, so all scores are image-level.
- 2026-11-03 — METHOD: the card confirms MedMNIST v2 Table 3 (BloodMNIST, test):
  ResNet-18 (28) ACC 0.958 (P5 unchanged), auto-sklearn ACC 0.878 on flattened raw
  pixels. Decision: re-record CONSULT to correct RQ1's prior text (it said auto-sklearn
  used feature engineering; it did not) and to make RQ4's probability explicit. No
  prediction, rule, track or phase changed; no run exists yet.
- 2026-11-03 — METHOD flags for the floor sweep: macro-F1 is not a per-image mean, so
  its item bootstrap resamples images and recomputes macro-F1 (not `item_bootstrap` on
  per-image correctness); augmentation draws from its own RNG so batch order matches the
  anchor at the same seed; per-seed confusion tables are now pinned separately
  (framework fix d2a4f08).
- 2026-11-03 — Decision: `prepare.py` stores the source's uint8 pixels; the training
  loader scales them (the payload stays byte-faithful to the source).

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase anchor slate

| # | Candidate (cell, one transaction) | Novelty | Testable | Info | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | E0001 anchor: recipe SmallCNN as committed (width 32, 1,500 steps), 3-seed array; adjudicates P2 (>= 0.85) | 3 | 3 | 3 | 9 |
| 2 | E0002 pixel-linear softmax (Flatten + Linear), same loop/optimizer/steps; adjudicates P1 (in [0.50, 0.85]); expected discard against E0001 | 3 | 3 | 3 | 9 |
| 3 | Floor (a): item bootstrap of the anchor's dev macro-F1 (multinomial re-draw of the confusion table, 1,000 draws per seed table), estimand marginal-resplit = the keep bar | 3 | 3 | 3 | 9 |
| 4 | Floor (b): anchor on three more seed blocks {10,11,12} {20,21,22} {30,31,32}, spread of block means, estimand fit-noise (provenance, never the bar); tests K2 | 2 | 2 | 3 | 7 |

Chosen: 1, 2, 3, 4 in order (the phase is fixed by the contract; the floor needs the anchor's pinned tables). Rationale: the ladder P2 then P1 then the measured bar is the phase plan itself.


## Phase anchor — run log and decisions

- 2026-11-03 — E0001 (anchor, recipe SmallCNN, width 32, 1,500 steps, seeds 0/1/2; `--allow-rerun`
  because the anchor is the committed surface): val_macro_f1 seed-mean 0.7189 (std 0.0255; seeds
  0.7331 / 0.7342 / 0.6895), val_accuracy 0.7794 (std 0.0079). Disposition `keep` (first run; the
  incumbent). Per-class recall (seed mean): 0: 0.26, 1: 0.94, 2: 0.76, 3: 0.71, 4: 0.50, 5: 0.57,
  6: 0.95, 7: 0.98. Class 0 is mostly called class 3 (immature granulocytes); the 3 / 4 / 5
  group is the weak spot. Development has 1,709 images (3 near-duplicates dropped at the DATA gate).
  Loss at step 1500 is still ~0.5-1.0 and noisy: the anchor is under-trained at constant lr 3e-3,
  not capacity-limited alone.
- 2026-11-03 — Decision: P2 refuted (anchor 0.7189 < 0.85; the method card's central guess was 0.87,
  plausible range 0.80-0.92, so this is below its range). Reading: 1,500 constant-lr AdamW steps
  (8 epochs) leave the two-block, 8-px-receptive-field network far from the 0.85 line, and the
  seed spread (0.69-0.73) is itself large. RQ2's prior ("macro-F1 at or above 0.85") is not
  supported at the anchor. No change to the contract; P2 stays refuted and the adaptive phase
  tests which lever moves it.
- 2026-11-03 — E0002 (pixel-linear softmax, Flatten + Linear(2352, 8), same loop/steps/optimizer/
  seeds): val_macro_f1 seed-mean 0.6903 (std 0.0364; seeds 0.7134 / 0.7092 / 0.6483),
  val_accuracy 0.7353 (std 0.0268). Disposition `discard` (0.6903 < incumbent 0.7189 + delta; the
  expected outcome). P1 supported (0.6903 in [0.50, 0.85]); the card's central guess was 0.72,
  within range. The linear model and the CNN are 0.029 macro-F1 apart at the SAME ~19k parameters,
  smaller than the keep bar measured below (0.0438). Linear per-class recall: class 3 is the
  weak spot there (0.29), class 0 is strong (0.77): the two models fail on different classes.
  The wall time was 3 s per seed against 250-500 s for the CNN (CPU shared; load average ~10).
- 2026-11-03 — Floor (a), registered as `sweep:item_bootstrap`: 1,000 multinomial re-draws of the
  seed-mean E0001 confusion table (n = 1,709), macro-F1 recomputed on every draw (not
  `item_bootstrap` on per-image correctness). Per-seed-table cross-check sds 0.0121 / 0.0114 /
  0.0117; sidecar sd 0.01197, range 0.0877, so `minimum_delta` = max(2 sd, range/2) =
  0.0438435 (range/2 binds, as the card's section 2 predicted). The seed-mean table keeps the
  sd of one seed's table (seeds' predictions are highly correlated), so this is not shrunk by
  sqrt(3); bootstrapping the pinned tables conditions on the three fitted models.
- 2026-11-03 — K1 (floor in [0.015, 0.040]) is FALSIFIED: the bar is 0.0438. K3 (accuracy minus
  macro-F1 in [0, 0.03]) is FALSIFIED: the gap at the anchor is 0.0605. K4 (class 3 lowest or
  second-lowest recall) is FALSIFIED: classes 0 (0.26), 4 (0.50) and 5 (0.57) all sit below
  class 3 (0.71). These are card priors (not registered P#), recorded here for SYNTHESIZE.
  Headroom at the anchor: h = (1 - 0.7189) / 0.0438 = 6.4.
- 2026-11-03 — Floor (b), registered as `sweep:fit_noise`: the anchor configuration (train.py's
  own RECIPE and SmallCNN, run in-process; the harness reproduces E0001's seeds 0/1/2 to the
  sixth decimal) on seed blocks {10,11,12} {20,21,22} {30,31,32}. Block-mean macro-F1 0.6719,
  0.5886, 0.6688: mean 0.6431, std 0.0472, range 0.0833. Per-seed values range from 0.490 (seed
  21) to 0.734. Recorded as `fit_noise` (provenance, never the bar). Across all twelve seeds run
  at the anchor config: mean 0.662, per-seed std 0.075. E0001's block (0.7189) is the highest of
  the four blocks (four-block mean 0.6620, std 0.0541): the incumbent is a favourable draw.
- 2026-11-03 — K2 (fit/item ratio < 1.0) is FALSIFIED: fit-noise std 0.0472 over item-bootstrap
  std 0.0120 is 3.9. Unlike the card's expectation the seed-array spread is the bigger noise, and
  the anchor is unstable at this schedule (constant lr 3e-3, 8 epochs). Consequence: the
  keep bar 0.0438 is set by item noise (the contract's estimand), but a candidate's 3-seed mean
  also carries fit noise of about 0.047; the bar sits at about 0.93 fit-noise sds. A keep needs
  0.7627 (incumbent 0.7189 + 0.0438). Because the incumbent is a favourable draw, a null change
  is unlikely to keep (it would need roughly +2 block sds over the four-block mean), while a
  real improvement that also stabilises training clears the bar easily. Read every adaptive
  keep and discard against both floors; a candidate within 0.047 of the incumbent is not
  distinguishable by one seed array.
- 2026-11-03 — Contract: `minimum_delta` 0.0438435 (estimand marginal-resplit, recipe
  item-bootstrap, k 1000) and the `fit_noise` block are in `study.yaml`; CONSULT re-recorded
  (lead-agent, reason: minimum_delta set from the measured noise floor). Preflight: 22 checks,
  0 failed; headroom h = 6.41.

### Phase adaptive slate (drafted at the anchor close; the formal ritual repeats at the phase start)

Evidence in hand: the anchor is unstable and under-trained (loss still ~0.5-1.0 at step 1500,
per-seed macro-F1 0.49-0.73), and fit noise (0.047) is about the size of the keep bar (0.044).
Levers that stabilise optimisation should therefore pay first. Predicted effects are in
macro-F1 against the incumbent 0.7189; the keep bar is +0.0438.

| # | Candidate (one lever, one seed array) | Nov | Test | Info | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | BatchNorm after each conv, anchor depth/steps otherwise (normalization): +0.08, stabilises seeds | 3 | 3 | 3 | 9 |
| 2 | D4 flip / rot90 augmentation on the training batch (own RNG, batch order unchanged), anchor model: +0.04 | 3 | 3 | 3 | 9 |
| 3 | Third conv block (conv-pool-conv-pool-conv, receptive field 8 -> 18 px), no BN: +0.05 | 3 | 3 | 3 | 9 |
| 4 | Longer schedule only: 4,000 steps, anchor model (RQ3's prior says it helps less than the floor) | 2 | 3 | 3 | 8 |
| 5 | Width 64 (capacity only): +0.02, expected not to clear the bar | 2 | 3 | 2 | 7 |
| 6 | P3 as its own registered cell: three blocks + BN + D4 + 4,000 steps (tests P3 >= 0.93); a bundle of four levers | 2 | 3 | 3 | 8 |

Chosen to start: 1 (BatchNorm) because the anchor's seed instability is the dominant measured
noise; then 2 and 3, so the P3 bundle can be decomposed before it runs. 4-6 are the queue.

- 2026-11-03 — Decision (lead, at the anchor/adaptive boundary): `max_run_seconds` and the
  `wall_seconds` guardrail 1800 -> 5400. Both bound a whole 3-seed array; under CPU
  contention from the sibling exhibits a seed took 250-500 s, so a 1,800 s cap would turn
  slow machines into crashes. No prediction, rule, metric or floor changed; consult
  re-recorded with this reason.
- 2026-11-03 — Note (lead): the fit noise across seed blocks (std 0.047) is as large as the
  keep bar (minimum_delta 0.0438, item bootstrap). The bar answers "would this score hold
  on a re-drawn set of development images"; it does not absorb seed luck, and E0001's
  seeds were the best of four blocks. A keep in the adaptive phase is therefore read
  together with its own seed spread, and findings must say so.
- 2026-11-03 — Framework fix applied before the adaptive phase (fcadacf): the notary now
  writes a seed array's aux rows as the seed means; E0001/E0002 were filed before it, so
  their aux_metrics.tsv rows hold the LAST seed's values — their per-seed values are in
  runs/E000N/seeds.tsv.

### Phase adaptive slate

Formalized at the phase start (the draft above stands; scores unchanged). Order of execution,
one lever per seed-array candidate, P3 last as its own registered bundle:

| # | Candidate | Nov | Test | Info | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | BatchNorm after each conv (normalization), anchor otherwise | 3 | 3 | 3 | 9 |
| 2 | D4 flip / rot90 augmentation, own RNG | 3 | 3 | 3 | 9 |
| 3 | Third conv-pool-conv-pool-conv block (depth) | 3 | 3 | 3 | 9 |
| 4 | 4,000 steps only (schedule) | 2 | 3 | 3 | 8 |
| 5 | Width 64 (capacity) | 2 | 3 | 2 | 7 |
| 6 | P3 bundle: 3 blocks + BN + D4 + 4,000 steps, `--tests P3` | 2 | 3 | 3 | 8 |

Chosen first: 1. Frontier rule: a keep becomes the base for the next candidate; a discard does not.

## Phase adaptive — run log

- 2026-11-03 — E0003 (BatchNorm2d after each conv, anchor otherwise): `discard`, val_macro_f1
  seed-mean 0.3005 (seeds 0.2159 / 0.3541 / 0.3317; std 0.0725), accuracy 0.3669 (seeds 0.246 /
  0.485 / 0.369). Margin vs incumbent 0.7189: -0.4184, far outside seed spread. Training loss
  at step 1500 was 0.23-0.34 (anchor 0.5-1.0), so training worked. Off-loop diagnostic
  (seed 0, same recipe, in-process; not evidence): dev accuracy with batch statistics 0.83 /
  0.89 / 0.92 at steps 250 / 750 / 1500, but 0.44 / 0.65 / 0.25 in eval mode with the running
  averages. So the failure is the evaluation-time running statistics (momentum 0.1 lagging
  weights that still move at constant lr 3e-3), not the idea: BN made the network far better
  fit, and the candidate as written measured a broken inference path. Bug-in-implementation,
  not a bad idea; NOT recorded as "ruled out". Next: the same lever with the running
  statistics recomputed on the training set (no_grad, cumulative average, train data only; no
  development statistics are used) before `eval()`.
