# Program — 01-dae-claims

> This file is the living lab notebook for this study. Hypotheses, decisions, phase
> plans, and the Predictions-to-falsify table live here and are updated AS THE STUDY
> RUNS. `study.yaml` is the machine-readable contract; this file is the narrative.
> The loop invariants live in the repo `CLAUDE.md` and `.claude/skills/klein/SKILL.md`
> Hard Rules — this file does not restate them, it applies them to THIS study.

## Goal & metric contract

**Goal:** Does a swap-noise denoising autoencoder (DAE) pay on 58k-row weak-signal
insurance claims? Quantify WHEN tabular self-supervised learning (SSL) pays.

**Primary metric:** `val_auc` (higher is better) — the ONE number every experiment
optimizes. Everything else (PR-AUC, brier, wall_seconds, imputation RMSE, anomaly
lift@10, `min_proba_std`, ...) goes to `aux_metrics.tsv`, never into results.tsv.

**Schema:** the shape of `results.tsv` and `aux_metrics.tsv` is defined ONLY in
`kleinlib/schema.py`. This file never restates the column list — see
`kleinlib.schema.RESULTS_COLUMNS`. `new_study.py` wrote the header from
`kleinlib.schema.header_line()` at scaffold time.

**Baselines cited (NOT rerun — from the 215-exp campaign):** raw-LR floor `val_auc 0.6255`
(E1 reproduces it as the split-identity gate); tuned raw single-GBDT `0.6701`
(LightGBM-monotone-advanced, RQ1/RQ2 target); cross-family soft-vote `0.6715` (campaign
global best, a reference line only).

## Data & split contract

- **Source:** data_hub:insurance-claims — prepared by `uv run prepare.py`.
- **Split:** see `study.yaml:data.split` — stratified, seed=42, test_size=0.2, FIXED
  across every experiment. Never resample, reshuffle, or peek at the held-out split.
  Comparability with the campaign baselines depends on the identical split.
- The DATA gate (`data_card.md`) says **go** — see the card. Modeling is unblocked.

## Mutable surface

- **Mutable:** `train.py` ONLY. The per-experiment diff is 5–15 lines.
- **Study lib (rare, deliberate — NOT the per-experiment diff):** `dae.py` holds the
  `SwapNoiseDAE` (the study's centerpiece). `train.py` stays thin: it wires `dae.py` +
  `kleinlib` together for one experiment. Editing `dae.py` is a library change, logged.
- **Fixed:** `prepare.py`, `study.yaml`, `kleinlib/`. Sweeps are the ONE exception and
  live under `sweeps/` — see `.claude/skills/klein/references/sweep-rules.md`.

## Phases & budgets

Authoritative copy is `study.yaml:phases`. Mirror here for quick reading; STOP for user
ack at every phase boundary.

| Phase | Description | Min/Max exp | Budget | Ack boundary |
|---|---|---|---|---|
| 0 | split-identity anchor — reproduce the campaign LR anchor EXACTLY (0.6255 STOP gate) | 1–1 | 0.5h | **ACK after E1** |
| 1 | DAE representation ladder — E2 supervised MLP floor, E3 frozen DAE→LGBM, E4 linear probe, E5 swap-rate sweep | 3–5 | 1.5h | **ACK after E5** |
| 2 | additive value + other jobs — E6 DAE+raw→LGBM (keep iff >0.6701), E7 DAE-imputer vs median, E8 recon-error anomaly | 2–3 | 1.0h | **ACK at end (after E8)** |

Total ~3h wall-clock (deep/torch on MPS). User-ack pauses: **after E1, after E5, at end.**

## The 8-experiment ladder

The loop ADAPTS — this is the planned spine, not a batch script. Each row is one
`train.py` edit (E5 is the one sanctioned sweep). "Keep rule" is the honest bar each
experiment must clear to earn a `keep`.

| Exp | Phase | What | Config | Keep rule / gate |
|---|---|---|---|---|
| E1 | 0 | Split-identity anchor | LR + OHE(min_frequency=20) + `class_weight=balanced`, fixed 42/0.2/stratified split | **GATE: `|val_auc − 0.6255| ≤ 0.001` or STOP the study** (preprocessing/split drift) |
| E2 | 1 | Supervised MLP raw floor | 3×256 ReLU MLP on OHE+RankGauss encoding, trained SUPERVISED (no SSL), `min_proba_std` guard on | keep if it beats raw-LR 0.6255 (establishes "representation power alone", pre-SSL) |
| E3 | 1 | Frozen DAE → LGBM (RQ1 headline) | `SwapNoiseDAE(swap_rate=0.15)` fit on TRAIN fold only (inductive), freeze, take 768-d deep-stack reps → LGBM default | keep if it beats E2; **RQ1 verdict = does it reach 0.6701?** |
| E4 | 1 | Linear probe (RQ3) | LogisticRegression on the SAME frozen 768-d DAE reps | keep if it beats raw-LR 0.6255 (did SSL linearize the signal?) |
| E5 | 1 | Swap-rate sweep (sweep-rules.md) | `swap_rate ∈ {0.10, 0.15, 0.25}` → DAE→LGBM, every trial to `sweeps/swaprate.sidecar.tsv`, ONE winner row | keep the winner iff it beats E3; else `discard` (null result still logged) |
| E6 | 2 | DAE + raw → LGBM (RQ2) | concat(768-d DAE reps, raw prepared features) → LGBM | **keep IFF val_auc > 0.6701**, else `discard` — the honest additive-value bar |
| E7 | 2 | DAE-imputer vs median (RQ4a) | inject MCAR at {10%, 30%}, impute via DAE `reconstruct()` vs median, refit LGBM, compare downstream val_auc | keep if DAE-impute ≥ median at either rate; report gain-vs-missing-rate to aux |
| E8 | 2 | Recon-error anomaly (RQ4b) | rank val rows by DAE reconstruction error; lift@10% of positives among top-error rows | keep if lift@10% > 1.0 (independent, calibration-free ranking signal) |

Metric contract note: E7/E8's native signals (imputation RMSE, anomaly lift@10) are
NOT the primary metric — `val_auc` stays the one ledger metric (E7 logs the downstream
LGBM val_auc; E8 logs val_auc of the anomaly score as a 1-D ranker). The rich E7/E8
numbers go to `aux_metrics.tsv`.

## Research questions

Authoritative copy is `study.yaml:research_questions`. One verdict per RQ in
`findings.md`, each citing evidence experiment IDs.

| ID | Question | Prior (honest expectation) |
|---|---|---|
| RQ1 | Frozen DAE reps + LGBM vs raw-GBDT 0.6701? | **no** — DAE reps ~0.66-0.67, at/below tuned GBDT; SSL pays at scale/multimodal/high-card, none present here |
| RQ2 | DAE+raw lift over 0.6701? | **≤ +0.001** — trees already have the axis-aligned signal; keep only if it clears 0.6701 |
| RQ3 | Linear probe on DAE reps vs raw-LR 0.6255? | **yes, modestly** (~0.63-0.66) — SSL pre-bakes non-linearity a linear model can use, still < GBDT |
| RQ4 | Imputer + anomaly = independent value? | **plausible, independent** — imputation gain grows with missing rate; recon-error lift@10% > 1.0 |

## Predictions to falsify

Fill `predicted` NOW (before running); fill `observed` + `verdict` during SYNTHESIZE.
A prediction with no verdict is an unfinished study. (Authoritative:
`study.yaml:predictions_to_falsify`.)

| Lever | Predicted Δ | Observed Δ (exp IDs) | Verdict |
|---|---|---|---|
| E1 anchor: LR+OHE(min_freq=20)+cw=balanced | val_auc = 0.6255 ± 0.001 (GATE) | | |
| E2 supervised MLP raw floor | val_auc ~0.63-0.65; > raw-LR 0.6255, < GBDT 0.6701 | | |
| E3 frozen DAE(768-d)→LGBM (RQ1) | val_auc ~0.66-0.67; Δ ≤ 0 vs 0.6701 (no beat) | | |
| E4 linear probe on DAE reps (RQ3) | val_auc ~0.63-0.66; Δ > 0 vs 0.6255 | | |
| E5 swap-rate sweep {.10,.15,.25} | \|Δ\| ≤ 0.002 across rates; best ≈ 0.15 | | |
| E6 DAE+raw→LGBM (RQ2) | Δ ≤ +0.001 vs 0.6701 (likely discard) | | |
| E7 DAE-imputer vs median, MCAR {10,30}% (RQ4a) | downstream Δ ≥ 0, growing with missing rate | | |
| E8 recon-error anomaly (RQ4b) | lift@10% > 1.0 | | |

## Guardrails (this study)

- **FAIRNESS RULE (headline honesty — the refinement that makes this comparable to the
  campaign).** The headline DAE (E3/E4/E5/E6) is trained on **TRAIN-fold features ONLY**
  (`SwapNoiseDAE(fit_mode="inductive")`, the default) — it never sees a single val row
  during representation learning, so its reps are honestly comparable to the campaign's
  inductive baselines. The Jahrer-style **transductive** variant (DAE fit on train+val
  features, `fit_mode="transductive"`) is reported ONLY as a clearly-labeled
  **"Kaggle-style" aside** — it is how Porto Seguro was won (DAE on train+test), but it
  quietly uses the val distribution and is NOT the headline. Never let the transductive
  number masquerade as the headline.
- **MPS-safety rules (the collapse war story).** (1) Torch training/inference uses
  `kleinlib.torch_loop` index-shuffle batching — **NEVER a `DataLoader`/`TensorDataset`
  on MPS** (silent prediction collapse). (2) Device via `kleinlib.torch_device.pick_device`
  (MPS→CPU fallback). (3) ALL representations cross back to **CPU numpy** before touching
  sklearn/LightGBM. (4) seed 42 everywhere: `torch.manual_seed` + `torch.mps.manual_seed`
  + numpy. (5) Any classifier eval goes through `kleinlib.eval.evaluate`, whose
  `min_proba_std` guard RAISES on collapsed predictions after the first val batch — a
  collapsed DAE→classifier crashes LOUD, never lies quiet.
- **Foreground runs only:** `uv run train.py 2>&1 | tee run.log`, terminal timeout =
  phase budget in ms. A run over budget is a `crash` (timeout note), reverted.
- **Commit-or-revert FIRST, then ONE results.tsv row.** Never the reverse; never batch.
- **Status honesty:** keep / discard / crash. A crash is logged with `NA` metric, not
  retried into oblivion. A missing row is worse than a crash row.
- **Sweeps:** E5 only, via the escape-hatch — every trial to `sweeps/swaprate.sidecar.tsv`,
  ONE winner row, winner snapshotted into train.py, winner pickled.
- **Phase-boundary acks:** summarize and STOP after E1, after E5, and at end.
- **Branch:** the OFFICIAL ladder (WP12) runs on `experiments/01-dae-claims`, never
  `main`; merge at study end.

## Ops war stories (this study) — PROMOTION CANDIDATE for knowledge/war-stories

> Flagged per the Phase-2 ack for the SYNTHESIZE stage to promote into the repo
> knowledge base (findings §3 material). This is the prominent summary; the full
> diagnostic trail lives in the Log (2026-07-10 E3 entries). The experimenter does
> not touch `knowledge/` — promotion is the synthesist's move.

**torch + LightGBM cannot share a process on macOS arm64 (SIGSEGV exit 139, no
traceback).** Both wheels bundle their own `libomp`; whichever framework engages
OpenMP heavily SECOND segfaults the process. Import order only moves the victim
(lightgbm-first survives toy loads, then the full-scale torch stage dies). The armed
`min_proba_std` guard cannot catch it — the failure is below Python. THE fix:
**two-stage process isolation inside one train.py / sweep script** — a torch-only
child subprocess fits the DAE and dumps `.pkl` caches (never imports lightgbm); the
parent imports lightgbm FIRST, loads the caches, and runs the GBDT head (torch bound
passively by kleinlib but never operated). Sanctioned by SKILL.md's "wrap a launcher
INSIDE one train.py" note. Ops corollaries: (1) `set -o pipefail` on every tee'd run —
tee otherwise masks the real exit code; (2) `PYTHONUNBUFFERED=1` — block-buffered
stdout dies with the process, leaving an empty run.log; (3) a bit-exact rerun
(E3 = sweep trial 2 = 0.668271) is the cheap proof isolation preserved determinism.

## Log (append-only)

Narrate decisions here as the study runs — why each direction, what a cluster of
discards taught you, where you changed course. This is what SYNTHESIZE mines.

- 2026-07-10 — study scaffolded via `new_study.py`. Next: CONSULT confirm → DATA gate →
  METHOD gate → the E1 STOP gate.
- 2026-07-10 — **CONSULT: fast-path taken.** The task brief answered all six interview
  axes up front (goal = quantify when tabular SSL pays; data = data_hub:insurance-claims,
  58,592 rows, known from the campaign; method familiarity = FRONTIER/unfamiliar → full
  method card + lit-scan required; metric = val_auc higher, decision = "should an actuary
  reach for a DAE on data like this?"; budget ~3h / 8 experiments across 3 phases;
  deliverables = standard findings.md + tutorial). study.yaml, program.md,
  research_plan.md drafted directly from the brief per the fast-path rule in
  `references/consult-protocol.md`. Logged here per Hard Rule 3.
- 2026-07-10 — This is a **FRONTIER-method study** (self-supervised learning for tabular):
  the METHOD gate's mandatory lit-scan applies. `method_card.md` written with a verified
  lit-scan (VIME, SCARF, Jahrer's Porto Seguro DAE, Grinsztajn) BEFORE any modeling.
- 2026-07-10 — **DATA gate: GO.** Same trusted data_hub dataset as study 00 (58,592 rows,
  6.40% positive). data_card.md adds the DAE-specific column routing (which columns enter
  the DAE, `is_*` binaries passthrough-excluded from swap noise, RankGauss numerics,
  OHE(min_frequency=20) cats → reported input encoded dim). No BLOCKER; calibration
  doctrine noted for the downstream classifiers.
- 2026-07-10 — **WP9a build (this pass): E1 verified by DRY-RUN only.** train.py left at
  the E1 anchor config; `dae.py` + tests complete. The official 8-experiment ladder
  (E1-E8 logged rows, findings, tutorial) runs later on the `experiments/01-dae-claims`
  branch (WP12). results.tsv is header-only until then — no rows logged in this pass.
- 2026-07-10 — **WP12 Phase 0: E1 official run — GATE PASS.** `val_auc=0.625462`,
  `|0.625462-0.6255|=0.000038 <= 0.001`. train.py needed no edit (already the correct
  E1 config from WP9a); commit `c48a57b` carries the run artifacts (aux_metrics.tsv,
  models/manifest.tsv), results row committed at `8f342e0`. Exactly matches study 00's
  own E1 anchor (0.625462) — confirms both studies share `prepare.py` byte-for-byte and
  the split/preprocessing are correctly wired before any DAE work. Next: Phase 1
  (E2-E5) awaiting user ack.
- 2026-07-10 — **Phase 0 boundary ACK received** (orchestrator acting as user-delegate;
  the user pre-approved full-ladder execution — phase-boundary acks are recorded this
  way for the rest of the study). Proceeding with Phase 1 (E2-E5). Coordinator notes
  adopted: (1) E3 persists its fitted DAE + frozen reps under `models/*.cache.pkl`
  (gitignored payloads; exact paths documented at E3) so Phase 2 E6-E8 reuse them
  without refitting; (2) every torch fit stays behind the `min_proba_std` guard, CPU
  fallback after <=2 MPS anomalies; (3) budget pressure handled by early-stopping
  patience, never epoch cuts. Env smoke check: all 4 `tests/test_dae.py` pass
  (pandas 3.0.3, torch 2.13.0, MPS available).
- 2026-07-10 — **E2 (keep, 0.670616): the supervised-MLP floor is NOT a floor — it ties
  the tuned GBDT.** Predicted 0.63-0.65; observed 0.670616 (+0.045 over raw-LR, -0.0005
  vs soft-vote territory... just +0.0005 over single-GBDT 0.6701). 12s fit on MPS, 26
  epochs, guard clean, brier 0.0587 (cw=None doctrine holds for NNs too). Consequence:
  E3's pre-registered keep bar ("beats E2") is now 0.670616 — the DAE must beat a
  GBDT-strength supervised NN, a much harder ask than the prediction assumed. This
  mirrors the ancestor campaign's Phase-4 lesson (FTT-zero-dropout ~ single GBDT).
- 2026-07-10 — **THE WAR STORY (not the one we pre-registered): torch + LightGBM cannot
  share a process on macOS arm64.** E3's first run died at `LGBMClassifier.fit` with
  SIGSEGV (exit 139), NO traceback, and an empty run.log (stdout block-buffered into a
  pipe was lost at the kill). The pre-armed `min_proba_std` guard never fired — the
  failure was below Python. Diagnostic trail: (A) torch-free process, LGBM on the cached
  reps -> OK (val_auc 0.668271, 1.5s); (B) tiny torch-MPS op then LGBM fit, same
  process -> exit 139; (C) lightgbm imported FIRST, tiny torch -> OK; full-scale rerun
  with lgbm-first -> exit 139 INSIDE the torch stage (faulthandler died mid-header).
  Conclusion: both bundle a libomp and whichever engages OpenMP heavily SECOND
  segfaults — import order only shifts the victim. FIX: two-stage process isolation
  inside one train.py (the pattern SKILL.md's Limitations note sanctions): stage "dae"
  = torch-only child subprocess (fit DAE, dump caches, never imports lightgbm); stage
  "head" = parent, lightgbm imported first, torch never operated. Each stage maps onto
  a proven-good diagnostic. Ops lessons: always `set -o pipefail` (tee masks exit
  codes), always `PYTHONUNBUFFERED=1` (or a crash eats the log). E5's sweep and every
  Phase-2 experiment mixing torch+LGBM MUST reuse this two-stage pattern.
- 2026-07-10 — **E3 (discard, 0.668271): RQ1 headline answer is NO — frozen inductive
  DAE reps + LGBM do not reach the tuned raw-GBDT 0.6701, and do not beat the E2 MLP
  0.670616.** Observed dead-center in the predicted 0.66-0.67 band; Δ=-0.0018 vs 0.6701,
  Δ=-0.0023 vs E2. DAE: swap 0.15, 100 epochs (hit max; recon still improving),
  es_mse 0.023, 33s on MPS, fairness canary n_fit_rows=46873 ✓. LGBM recipe best_iter
  107. train.py reverted per commit-or-revert; the E3 two-stage config is preserved
  verbatim in the E5 sweep machinery (same recipe) and this log. **Cache paths for
  Phase 2 reuse (coordinator note): `models/dae_e3_swap015.cache.pkl` (fitted
  SwapNoiseDAE, net parked on CPU — E7 reconstruct/E8 recon-error) and
  `models/reps_e3_swap015.cache.pkl` (dict: rep_tr/rep_va 768-d float32, swap_rate,
  input_dim, n_fit_rows, dae_fit_seconds, history — E4/E6 consume; pure numpy, loadable
  torch-free).** Both gitignored payloads, deterministic (seed 42): a rerun of the
  cached pipeline reproduced 0.668271 bit-exact.
- 2026-07-10 — **E4 (keep, 0.658019): RQ3 answer YES — the linear probe beats the raw-LR
  floor by +0.0326.** Predicted 0.63-0.66; observed 0.6580 (upper half of band). The DAE
  demonstrably learned usable joint structure: a plain LR on its frozen reps closes ~72%
  of the raw-LR (0.6255) -> tuned-GBDT (0.6701) gap. Emerging Phase-1 ordering: raw-LR
  0.6255 < probe 0.6580 < DAE->LGBM 0.6683 < GBDT-bar 0.6701 ~ MLP 0.6706 — the reps
  carry real signal, but nothing DAE-based has beaten plain supervised learning. Next:
  E5 swap-rate sweep {0.10, 0.15, 0.25}, baseline = E3 0.668271.
- 2026-07-10 — **E5 (discard, 0.668271): swap-rate sweep is a null result for the metric
  but falsifies its own prediction.** 3 trials via SweepRunner (two-stage per trial —
  libomp isolation), sidecar `sweeps/swaprate.sidecar.tsv`. Winner rate=0.15 reproduces
  E3 BIT-EXACT (0.668271 — the determinism check passed; the runner's `improved=True`
  is a float-vs-6dp-literal artifact, honestly read as no-improvement -> rule-7 discard;
  no snapshot, no pickle, train.py untouched at E4's config). SCIENCE: the pre-registered
  "|Δ| ≤ 0.002 across rates" is FALSIFIED — 0.10 costs -0.0063 and 0.25 costs -0.0041,
  so swap-rate is a real lever at 58k rows and Jahrer's 0.15 is a genuine local optimum
  here too. Recon es_mse rises with rate (0.0154 / 0.0230 / 0.0358) — more corruption =
  harder pretext task; 0.10's EASIER task learns weaker reps (least denoising pressure),
  0.25 over-corrupts. Per-rate values also in aux (experiment 5 rows). Trial caches
  kept: `models/{dae,reps}_e5_swap{0.10,0.15,0.25}.cache.pkl`. E3's caches remain the
  canonical Phase-2 rep source (winner == E3 config).
- 2026-07-10 — **Phase 1 boundary ACK received** (orchestrator as user-delegate, as
  before). Phase 2 (E6-E8) proceeds as proposed, with steers: E2's MLP gets full
  prominence in the when-it-pays figure; the libomp war story is promoted to its own
  ops section above (flagged for knowledge/ promotion by the synthesist); the
  noise-sensitivity figure includes per-rate es_mse from aux; final turn ends with
  ledger + aux highlights + honest RQ1-4 read (synthesis/tutorial run separately).
- 2026-07-10 — **E7 primary-metric operationalization (pre-registered BEFORE the run).**
  The ledger metric stays a true `val_auc` (trajectory comparability): **the downstream
  val_auc of the DAE-imputed arm at 30% MCAR** — the harder, headline missingness rate.
  "Downstream frozen-E3-LGBM" = the E3 LGBM head refit deterministically from the clean
  cached rep_tr (E3's model was not pickled — discard rows never are; bit-exact refit
  proven twice). All four arm AUCs (dae/median x 10/30), the clean-reps reference, the
  per-arm deltas, and imputation-quality diagnostics (RankGauss-space numeric RMSE,
  categorical accuracy at masked cells) go to aux. MCAR injection: eligible columns
  only (21 numerics + 6 cats — mirrors the swap-noise doctrine; `is_*` excluded),
  per-rate seeds default_rng(4210/4230). Keep rule (pre-registered): DAE-impute >=
  median-impute on downstream val_auc at EITHER rate.
- 2026-07-10 — **E6 (discard, 0.660653): RQ2 answer NO — and concat is WORSE than reps
  alone.** concat(94-d canonical raw encoding via the cached E3 transformer, 768-d
  frozen reps) = 862 dims -> same LGBM recipe: 0.660653, far under the 0.6701 keep bar
  AND 0.0076 under E3's reps-only 0.668271. best_iter fell 107 -> 55: the redundant raw
  dims dilute the split budget (colsample 0.7 over 862 mixed features) and the model
  overfits earlier. Sharper-than-predicted null: the prior said "<= +0.001 lift"; the
  observation is a REGRESSION. Trees don't want the DAE's re-expression of information
  they already have. train.py reverted (sits at E4's kept config).
- 2026-07-10 — **E7 (keep, 0.632213): RQ4a answer YES — but the win lives at the cell
  level, not the AUC level.** DAE-impute beats median/mode on downstream val_auc at
  BOTH rates (+0.0015 @10%, +0.0013 @30% — keep bar met), and at the cell level it is
  not close: numeric RMSE 1.02 vs 3.42 (RankGauss space, 3.4x better), categorical
  accuracy 90.1% vs 33.4% (the DAE exploits exactly the model-derivative redundancy the
  data card flagged as NOTE 2). Two honest nuances: (1) the predicted "gain grows with
  missing rate" is FALSIFIED — the delta is flat (0.0015 -> 0.0013); (2) the dominant
  effect is information loss itself (clean 0.6683 -> 0.6321 at 30% MCAR), which no
  imputer recovers — the LGBM head is largely robust to WHICH imputer filled the cells.
  Actuarial read: reach for the DAE-imputer when you need the VALUES (downstream
  reports, ratemaking features, audit), not when you only need the classifier's rank.
  Cache: `models/e7_imputer.cache.pkl` (per-rate arm reps + diagnostics).
- 2026-07-10 — **E8 (discard, 0.480548): RQ4b answer NO — recon-error is not a claim
  ranker here; the prior (lift@10 > 1.0) is FALSIFIED.** lift@10 = 0.9341 (also
  lift@5 = 0.9081, lift@20 = 0.9203), ranker val_auc 0.4805: the signal is slightly
  INVERTED — rows the DAE reconstructs worst (unusual model-spec combinations) are
  marginally LESS claim-prone, not more. Why (post-hoc): claims on this book are driven
  by weak exposure/usage signal (subscription_length, age, density), not by "weird
  vehicle configurations" — outlier-ness in the feature joint is orthogonal-to-slightly-
  negative for claim risk. An honest second-act null: the SAME DAE that imputes 3.4x
  better than median (E7) is useless as an unsupervised claim-flagger (E8). Phase 2
  experiment count: 3/3 (E6-E8). Next: figures + final summarize + final report.
- 2026-07-10 — **EXPERIMENT stage complete: 8/8 ladder run, 4 keep / 4 discard / 0
  crash, total wall ~0.02h of 3h budget.** Final artifacts: results.tsv (8 rows),
  aux_metrics.tsv, results_summary.md + progress.svg, and the pre-registered figure
  set (figures/plot_{when_it_pays,noise_sensitivity,imputer_gain,anomaly_lift,
  metric_trajectory}.png via figures_extra.py — every number parsed from the committed
  ledgers; E2 given prominence per the Phase-2 steer). Study best remains E2
  (0.670616, models/best_2_0.6706.pkl). Headline read for SYNTHESIZE: (RQ1) NO —
  frozen DAE reps + LGBM 0.6683 < 0.6701 GBDT < wait-for-it E2 MLP 0.6706; (RQ2) NO —
  concat regresses; (RQ3) YES — probe +0.033 over raw-LR; (RQ4a) YES-at-cell-level
  (3.4x RMSE, 90% vs 33% cat-acc), marginal on rank; (RQ4b) NO — lift@10 0.93,
  inverted. Meta-surprise: on 58k weak-signal rows, a plain supervised MLP on
  RankGauss+OHE equals the tuned GBDT — the DAE's unsupervised detour never catches
  the supervised baselines it was meant to feed. Handoff: SYNTHESIZE (findings.md,
  fills Predictions-to-falsify verdicts + promotes the libomp ops story), then
  TUTORIAL (report/index.html).
