# Program — 02-rqls-pv-severity

> Living lab notebook. `study.yaml` is the machine-readable contract; this file is the
> narrative — hypotheses, the experiment ladder, decisions, and the Predictions-to-falsify
> table, updated AS THE STUDY RUNS. Loop invariants live in the repo `CLAUDE.md` and
> `.claude/skills/klein/SKILL.md` Hard Rules; this file applies them to THIS study.

## Goal & metric contract

**Goal:** Robust Quantile Least Squares (RQLS) for photovoltaic (PV) loss severity under
contamination and incomplete data (deductible-truncated, limit-censored) — a known-truth
synthetic lab where every estimator is scored against the generator's exact answer.

**Primary metric:** `premium_error_pct` (lower is better) = |fitted premium − truth
premium| / truth premium × 100, computed with `kleinlib.eval.evaluate_scalar` (a
simulation study — no model/X_val pair). Everything else (parameter bias/RMSE, relative
efficiency, VaR95/99 & TVaR99 errors, wall_seconds) goes to `aux_metrics.tsv`, never into
results.tsv.

**Schema:** the shape of `results.tsv` and `aux_metrics.tsv` is defined ONLY in
`kleinlib/schema.py` (`kleinlib.schema.RESULTS_COLUMNS`). This file never restates columns.

## The two refinement rules (verbatim — these govern the whole study)

**(a) Truth-gate rule.** The E1 truth-recovery gate runs on SINGLE-FAMILY samples
(per-peril / single-distribution mode). Under the realistic mixture (E5–E7), "truth" =
generator FUNCTIONALS (VaR/TVaR/mean payout under d,u), not component params — otherwise
the gate is unpassable by construction.

**(b) Uniform metric contract.** Every experiment's `primary_metric` = **absolute
risk-loaded premium error % vs truth** for that experiment's scenario cell (goal: lower) —
heterogeneous scalars would break the one-metric-per-study contract and the progress
frontier; param bias/RMSE, relative efficiency, VaR/TVaR errors all go to
`aux_metrics.tsv`. (Also the best CAS framing: every experiment answers "how wrong would
your premium be?")

## Contracts (this study)

- **The "data" is code.** `generator.py::PVLossGenerator` is a known-truth PV
  loss-severity lab. `truth_functionals(d,u)` returns the EXACT mean payout, VaR95/99,
  TVaR99, and risk-loaded premium under the product layer via 1-D numeric integration of
  the mixture survival function (verified against a 10⁶-draw Monte-Carlo in tests).
- **The methods under study** live in `estimators.py`: `mle_full` (naive), 
  `mle_truncated_censored` (proper conditional likelihood), `qls` (observable-window
  Quantile Least Squares, OLS/GLS), `mtm` (method of trimmed moments).
- **Premium loading convention (documented once, used everywhere):**
  `premium = E[payout] + 0.10·(TVaR99 − E[payout])` — the expected layer payout plus a
  10% load on the TVaR99 risk margin *above* the mean. Layer payout is
  `Y = (min(X,u) − d)₊` per policy. See `method_card.md` §2 and `generator.py`.
- **Standard product layer:** deductible `d = $5,000`, limit `u = $2,000,000`, priced in
  EVERY experiment (even E1, whose sample is not truncated/censored — the layer defines
  the premium; the sample defines what the estimator sees).
- **Split:** `kind: none`. No train/val split — comparability comes from FIXED seeds and
  Monte-Carlo reps. Each rep offsets from `seed=42`; never reshuffle a reported cell.

## Phases & budgets (authoritative copy: study.yaml)

Acks fire at every phase boundary → the required cadence **after E1, after E4, at end**.

| Phase | Description | Exps | Budget |
|---|---|---|---|
| 0 | generator truth-recovery gate | E1 | 0.3 h |
| 1 | efficiency + robustness | E2–E4 | 1.0 h |
| 2 | realistic cells + decisions | E5–E7 | 1.0 h |

## The 7-experiment ladder

Every cell reports `premium_error_pct` vs that cell's truth (rule b); the aux columns
below go to `aux_metrics.tsv`. The loop ADAPTS — this is the plan, not a batch script.

| Exp | Cell (generator config) | Estimators | Primary metric (results.tsv) | Key aux (aux_metrics.tsv) | Answers |
|---|---|---|---|---|---|
| **E1** | single-family lognormal, ε=0, no trunc/cens, n=2000 × 200 reps | `mle_full` | premium_error_pct | μ̂/σ̂ bias vs 2·MC-SE (the GATE), premium_err sd | truth-gate (rule a) |
| **E2** | single-family lognormal, ε=0 (clean), n=2000 × reps | `mle_full` · `qls` · `mtm` | premium_error_pct (per estimator) | rel. efficiency (QLS/MLE, MTM/MLE), param RMSE | RQ1 |
| **E3** | breakdown sweep ε ∈ {0,1,2,5,10}% (single-family) | `mle_full` · `qls` · `mtm` | premium_error_pct at each ε | premium-error-vs-ε curve, param RMSE-vs-ε | RQ2 |
| **E4** | truncation d=$5k + censoring u=$2M, ε=0 | `mle_full` (naive) · `mle_truncated_censored` · `qls` (window) | premium_error_pct (per estimator) | μ̂/σ̂ bias by estimator, window coverage | RQ3 |
| **E5** | realistic cell: ε=5% + trunc + cens (mixture) | naive `mle_full` · window-`qls` (trimmed) · `mtm` | premium_error_pct | which correction matters most; bias decomposition | RQ2+RQ3 combined |
| **E6** | GPD fire tail ON (ξ=0.4 @ $250k), mixture | tail-blind lognormal fit · tail-aware | premium_error_pct; VaR95/99, TVaR99 error (aux) | TVaR99 under-pricing, tail-share of premium | RQ4 |
| **E7** | premium-error decision table across cells | best estimator per cell | premium_error_pct (decision table) | $ premium by cell, VaR/TVaR, load adequacy | RQ4 / the "money slide" |

Figures (built at SYNTHESIZE/TUTORIAL): breakdown-curve (premium error vs ε), efficiency-cost
bar (E2), window-QQ with trunc/cens shaded (E4), premium-error tornado (E7 money slide),
severity-fan.

## Guardrails (this study)

- **Foreground runs only:** `uv run python studies/02-rqls-pv-severity/train.py 2>&1 | tee run.log`,
  terminal timeout = phase budget in ms. A run over budget is a `crash` (timeout note), reverted.
- **Commit-or-revert FIRST, then exactly ONE results.tsv row.** Never the reverse; never batch.
- **Status honesty:** keep / discard / crash. A crash logs `NA` metric. A missing row is
  worse than a crash row (it breaks the sequential numbering).
- **`train.py` is the ONLY mutable surface** (5–15 line diff per experiment): swap the
  generator cell + estimator(s), bump `EXPERIMENT_ID`. `generator.py` / `estimators.py`
  are library-stable — changes there are rare, deliberate, and never part of an exp diff.
- **Determinism:** every reported cell is seed-pinned; never reshuffle to chase a number.
- **Sweeps** (E3's ε grid): if run as a sweep, use the escape-hatch — every ε trial to a
  sidecar TSV under `sweeps/`, exactly ONE winner row in results.tsv. See
  `.claude/skills/klein/references/sweep-rules.md`.
- **Phase-boundary acks:** summarize and STOP after E1, after E4, at end.
- **Branch:** run on `experiments/02-rqls-pv-severity`, never `main`. Merge at study end.

## Gate status (synthetic lab)

- **DATA gate:** the "dataset" is the known-truth generator; `prepare.py` emits a
  reference cell + its exact truth functionals for the DATA card to profile. Determinism
  and truth-vs-Monte-Carlo agreement are pinned by `tests/test_rqls.py`.
- **METHOD gate:** `method_card.md` (RQLS pedagogy) is authored BEFORE the ladder runs —
  the hard-block lifts only once it exists and the DATA card says go.

## Log (append-only)

- 2026-07-10 — study scaffolded (WP9b). Built `generator.py` (PVLossGenerator + exact
  truth functionals), `estimators.py` (mle_full / mle_truncated_censored / qls / mtm),
  `train.py` (E1 gate), `method_card.md`, and `tests/test_rqls.py` (8 tests green, 1.4 s).
- 2026-07-10 — **E1 truth-recovery gate DRY-RUN: PASS.** Naive `mle_full` on single-family
  lognormal(9.0, 1.1), n=2000 × 200 reps: μ̂ bias +0.00037 (2·SE=0.00353), σ̂ bias
  −0.00043 (2·SE=0.00260) — both within MC tolerance. Mean premium error 4.28 %
  (sd 3.03) is the irreducible n=2000 sampling floor (parameter bias ≈ 0; the ~4 % is pure
  finite-sample propagation through the nonlinear premium map — the reference every
  robustness result in E2–E7 is measured against). Wall-clock 1.3 s. Nothing logged to
  results.tsv (WP9b builds + gate-verifies; WP13 runs the ladder).
- 2026-07-10 — budget probe: one E3-style cell (3 estimators × 100 reps, ε=5%) = 1.6 s
  (16 ms/rep). Preview of the breakdown story: at ε=5%, naive MLE premium error ≈ 139 %
  vs QLS ≈ 21 % / MTM ≈ 20 %. Phase budgets (0.3 h / 1.0 h / 1.0 h) are ample.
- 2026-07-10 — **WP13 Phase 0 — E1 OFFICIAL RUN: PASS** (branch
  `experiments/02-rqls-pv-severity`; `uv sync --extra dev`; `prepare.py` rebuilt the
  gitignored reference cell — realistic-mixture truth premium $62,346.20 matches
  `data_card.md`; preflight 11/11 OK, 0 FAILs; `tests/test_rqls.py` 8/8 green in 1.32 s).
  Naive `mle_full` on single-family lognormal(9.0, 1.1), ε=0, n=2000 × 200 reps,
  seed=42: μ̂ bias +0.00037 (2·SE=0.00353, ok) | σ̂ bias −0.00043 (2·SE=0.00260, ok) —
  both inside tolerance, numerically identical to the WP9b dry-run (deterministic
  seed, no train.py edit needed — E1 config was already correct). Mean premium error
  **4.279 %** (sd 3.03) — reconfirms the n=2000 MC sampling floor (`data_card.md`
  issue #1); this is the reference line every E2–E7 result is measured against, not 0.
  Wall-clock 1.27 s (phase-0 budget 0.3 h — far under). Logged: `results.tsv` row 1
  (keep, commit `762e77d`, metric 4.278819) + `aux_metrics.tsv` (bias/SE/gate flags/
  reps/n_per_rep/wall_seconds) + `results_summary.md`/`progress.svg` regenerated
  (`--goal lower`). Commits: `762e77d` (exp 1 evidence), `eab838d` (results row).
  **Phase 0 boundary — AWAITING ACK for Phase 1 (E2–E4).**
- Next (WP13 Phase 1, on ack): E2 efficiency at ε=0 (MLE vs QLS-OLS vs QLS-GLS vs
  MTM, rel. efficiency in aux) → E3 breakdown sweep ε∈{0,1,2,5,10}% (sweep escape-hatch
  if run as a sweep) → E4 incomplete-data recovery (naive-MLE vs trunc-MLE vs
  window-QLS under d=$5k/u=$2M). Ack cadence: after E4, at end.
- 2026-07-10 — **Phase 0 ACKED** by the orchestrator as user-delegate (user
  pre-approved full-ladder execution). Steers recorded: (1) E3 runs through the sweep
  escape-hatch — every (estimator, ε) cell to `sweeps/e3_breakdown.sidecar.tsv` with
  its rep count in `params_json`, ONE results row whose primary is the pre-registered
  cell; (2) E2 records per-estimator `wall_seconds_*` to aux so the efficiency story
  includes compute cost; (3) E4's aux carries the naive-MLE bias direction AND
  magnitude explicitly (signed `bias_mu`/`bias_sigma`/`prem_bias_pct` for the naive
  fit) — the aux headline even though the primary is window-QLS's error.
- 2026-07-10 — **Phase-1 pre-registration (written BEFORE any Phase-1 run):**
  - **E2** (efficiency at ε=0, RQ1): single-family lognormal(9.0, 1.1), complete data,
    n=2000 × **1000 reps** (seeds 42+r; data_card sanctions 200–1000). Estimators:
    `mle_full` · `qls` OLS · `qls` GLS (both on the default grid p∈[0.05,0.95]×19) ·
    `mtm` (trim=0.10). Primary = **QLS-OLS mean premium error** (mission contract:
    "primary = QLS premium error"). Aux: per-estimator mean/sd premium error, signed
    premium bias, RMSE(μ̂)/RMSE(σ̂), relative efficiency vs MLE as MSE ratios
    (premium-MSE and σ̂-MSE), premium-error ratio vs MLE, per-estimator wall_seconds.
  - **E3** (breakdown sweep, RQ2): 4 estimators × ε∈{0,1,2,5,10}% = 20 cells,
    **500 reps/cell**, n=2000, single-family, contamination only (no trunc/cens).
    QLS OLS+GLS on the robust trimmed grid p∈[0.15,0.85]×19 (method_card §Robustness;
    the config pinned in tests); mtm trim=0.10. Reported (primary) cell
    pre-registered = **trimmed QLS-OLS at ε=10%**. Full grid → sidecar via
    `kleinlib.sweep.SweepRunner` (rep count in every row's params_json) + per-cell
    curve (prem_err / signed bias / rmse_sigma) to aux. Sweep-rules deviations logged:
    rule 5 (pickle winner) is n/a — a simulation study has no model object; the
    "winner" is the reported cell's config, snapshotted into train.py (rule 4) whose
    evaluate call uses `study_dir=None` so a reproduction rerun cannot clobber the
    sweep-written exp-3 aux rows.
  - **E4** (incompleteness at ε=0, RQ3): d=$5k truncation + u=$2M censoring
    (`incomplete=True`), n=2000 drawn × **500 reps** (≈1,320 observed/rep after
    truncation — the honest effective-n design). Estimators: `mle_full` (naive) ·
    `mle_truncated_censored` · window-`qls` (untrimmed default grid — data is clean;
    the window handles incompleteness). Primary = **window-QLS mean premium error**.
    Aux headline: naive-MLE signed bias_mu/bias_sigma/prem_bias_pct (direction +
    magnitude), plus window coverage (mean observed fraction vs exact F(d)) and
    censored counts.
- 2026-07-10 — **E2 (keep, commit `57e503e`, primary 4.458722): RQ1 answered — the
  efficiency cost of robustness at ε=0 is real but small for QLS.** Paired design,
  1000 reps: MLE floor **4.116 %** (the 1000-rep refinement of E1's 4.279 % @ 200
  reps) | QLS-OLS **4.459 %** = **1.083×** MLE (prior band 1.05–1.18× ✓; rel. eff
  premium-MSE 0.846, σ̂-MSE 0.805 — at the lower edge of the 85–95 % prior) |
  QLS-GLS 4.624 % = 1.123× (rel. eff 0.785) | MTM 5.016 % = 1.219× (rel. eff 0.653,
  outside the QLS prior band — trimming 10 % of both tails is the priciest insurance).
  **Surprise worth carrying to findings:** diagonal plug-in GLS is *less* efficient
  than plain OLS on clean data at this 19-point grid — the inverse-variance weights
  (from a first-stage fit) add noise rather than efficiency; the full-Σ⁻¹ ceiling of
  the method card is not reached by the stable diagonal form. Compute cost aux'd per
  steer 2: all four estimators ≈ 6 s / 1000 fits incl. pricing — cost is a non-issue
  at this scale. Wall 24.6 s.
- 2026-07-10 — **E3 (keep, commit `72d9c8b`, primary 49.969892 = pre-registered
  trimmed-QLS-OLS @ ε=10%): RQ2 answered — the breakdown curve is the money picture.**
  Sweep escape-hatch: 20 cells × 500 reps to `sweeps/e3_breakdown.sidecar.tsv` (rep
  counts in params_json per steer 1), curve to aux, ONE results row. Premium error %
  by ε ∈ {0,1,2,5,10}% (MC floor ≈ 4.1–4.3 %):
  MLE 4.21 → 21.28 → 45.47 → **136.59** → **352.19** (diverges; even ε=1 % — one bad
  record in a hundred — already 5× the floor); trimmed QLS-OLS 5.42 → 6.25 → 8.58 →
  **20.32** → 49.97; QLS-GLS ≈ OLS (48.95 at ε=10); MTM slightly worse at high ε
  (57.55). **Both falsification points CONFIRMED at ε=5 %: MLE 136.6 % > 50 %; QLS
  20.3 % / MTM 22.7 % < 25 %.** Direction: ALL estimators biased UP under this
  contamination mix (bias ≈ error: gross over-reports inflate σ̂ → TVaR99 → premium),
  i.e. contamination overcharges policyholders rather than undercharging the book.
  Nuance for findings: trimming bounds influence but does NOT null it — the ε-mix
  (half ×10–100 gross, half ×0.01 typos) shifts mid-sample quantile RANKS
  (Q̂(p) ≈ Q_clean((p−ε/2)/(1−ε))), so robust-estimator bias grows ~linearly in ε
  while MLE grows explosively. train.py snapshot reproduced 49.969892 exactly
  (study_dir=None guard). Sweep wall 62.4 s.
- 2026-07-10 — **E4 (keep, commit `4a36b4e`, primary 4.834350 = window-QLS): RQ3
  answered — recovery CONFIRMED, but the naive->20 % prior is FALSIFIED.** d=$5k
  trunc + u=$2M cens, ε=0, n=2000 drawn × 500 reps (observed ≈1,340/rep; coverage
  67.01 % vs exact 1−F(d)=66.96 % ✓). Naive-MLE bias headline (steer 3): μ̂ bias
  **+0.596** (theory-exact: σ·λ(α)=0.593 at α=(ln d−μ)/σ=−0.439), σ̂ bias **−0.347**
  (truncated-normal variance shrink, also exact) — RMSE ≈ |bias|, i.e. pure
  systematic distortion. **Yet naive premium error is only 5.85 % (signed −5.23 %,
  systematic UNDERpricing), not >20 %:** the μ-up/σ-down biases nearly cancel in
  this layer's premium map — the naive fit approximates the CONDITIONAL law above d,
  and a layer with deductible d only pays above d ("wrong parameters, nearly right
  layer"). The falsification sharpens the doctrine: parameter bias ≠ pricing bias;
  what truncation-ignorance corrupts materially is the *ground-up* law (and any
  functional below d or far in the tail), not necessarily the same-layer premium.
  Recovery: window-QLS **4.834 %** ≈ incomplete-data floor, near-unbiased
  (μ̂ +0.00226, σ̂ −0.00273, premium bias −0.02 %); trunc-MLE **4.680 %** (the
  proper-likelihood reference); QLS/trunc-MLE ratio 1.033 — robustness costs ~3 %
  here. Floor note: 4.68–4.83 % > E1's 4.28 % because truncation cuts effective n
  to ~1,340. Censoring never binds at this cell (n_cens=0.000, S(u)≈3e-7) —
  machinery exercised; it will bite in E6 tail mode. Wall 20.7 s (trunc-MLE
  Nelder-Mead dominates: 13.6 s of it).
- 2026-07-10 — **PHASE 1 COMPLETE (E2–E4, 3/3 keep, 0 crash).** Wall ≈ 108 s of
  compute against a 1.0 h budget. RQ1: efficiency cost real but small (QLS-OLS
  1.083× MLE; GLS no help; MTM priciest). RQ2: both ε=5 % falsification points
  confirmed (MLE 136.6 % vs QLS 20.3 %/MTM 22.7 %); contamination biases premiums
  UP. RQ3: window-QLS recovers to the floor; naive-MLE premium prior falsified
  (param bias huge & theory-exact, premium bias only −5.2 % at this layer).
  **Phase 1 boundary — AWAITING ACK for Phase 2 (E5–E7).**
- 2026-07-10 — **Phase 1 ACKED** by the orchestrator as user-delegate (as before;
  the summarize phase-telemetry count-vs-ID-range display bug is acknowledged as a
  framework cosmetic issue — not worked around here, fixed at finalize). Phase-2
  steers recorded: (1) E6's deliverable = the tail-blind vs tail-aware SPLIT on
  VaR99/TVaR99 errors, explicit in aux and this log; (2) E7's decision table goes
  BOTH to aux and as a filing-memo-style markdown table here (estimator × ε,
  premium error %, direction); (3) figures: tornado = money slide with the 4.28 %
  MC-floor line + overcharging-direction annotation, severity-fan at the realistic
  cell per estimator, breakdown-curve log-scale for MLE's 352 %; (4) this is the
  final experimenter turn — synthesis/tutorial run separately.
- 2026-07-10 — **Phase-2 pre-registration (written BEFORE any Phase-2 run):**
  - **E5** (realistic cell, RQ2+RQ3): full mixture (tail off), ε=5 %, trunc d=$5k +
    cens u=$2M (`incomplete=True, contaminate=True`), n=2000 drawn × **500 reps**
    (seeds 42+r). Truth = generator FUNCTIONALS (refinement rule a; truth premium
    $62,346.20) — component-param bias is meaningless under the mixture. Estimators:
    `mle_full` (naive) · `mle_truncated_censored` · **window-QLS trimmed
    (p∈[0.15,0.85]×19; both corrections on) = PRIMARY** · `mtm` (trim=0.10); plus
    the pre-registered "which correction matters most" 2×2 QLS ablation to aux:
    qls_naive (no window, no trim) · qls_window_only (untrimmed) · qls_trim_only
    (no window). Aux: per-estimator prem_err mean/sd, signed premium/VaR99/TVaR99
    bias, wall_seconds, coverage.
  - **E6** (GPD tail, RQ4): mixture, `tail_mode=True` (fire GPD ξ=0.4, β=$125k
    spliced above t=$250k), ε=0, trunc+cens, n=2000 × **500 reps**. **Design probe
    (logged like the Phase-0 budget probe): truth premium tail-ON $62,454.93 vs OFF
    $62,346.20 = +0.174 % (TVaR99 +0.219 %, VaR99 +0.000 % — the splice sits just
    above ground-up Q(0.99)≈$244k); observable exceedances >$250k ≈ 20/rep
    (hail-dominated); censored ≈ 0.05/rep.** The maximum possible tail effect on
    this CAPPED layer is therefore +0.17 % of premium — the RQ4 prior (">10 %
    underpricing") is expected to be falsified BY THE GENERATOR'S OWN TRUTH at the
    frozen parameters (params stay frozen per data_card issue #2 — changing truth
    mid-study is the war story). The estimation-side question stands: does
    tail-awareness pay, or does POT noise hurt, at n_obs≈1,380? Estimators:
    **tail-blind window-QLS (untrimmed, on (d,u)) = PRIMARY** (pre-registered
    reading of "primary = QLS premium error in tail mode": the study's standard QLS
    deployed tail-unaware); tail-blind trunc-MLE (reference); tail-aware =
    window-QLS body fit on (d, t) + GPD via `scipy.stats.genpareto.fit(floc=0)` on
    observed uncensored exceedances above t, spliced with the generator's own
    `_Spliced` class, priced on (d,u); fallback to tail-blind when n_exc < 5 (rate
    recorded); ξ̂ floored at 1e-6 (clip rate recorded). Aux (steer 1): per-estimator
    signed VaR95/99 + TVaR99 + premium bias with the explicit blind-vs-aware
    contrast, n_exc/ξ̂ stats, truth tail-share diagnostics. The tail-aware helper is
    a local function in train.py (estimators.py stays library-stable per
    guardrails).
  - **E7** (decision table, RQ4/money slide): second sanctioned sweep —
    `sweeps/e7_decision.py`: the consolidated **realistic-lab grid** = mixture
    (tail off) + trunc + cens at every ε∈{0,1,2,5,10}% × 4 estimators (`mle_full`
    naive · `mle_truncated_censored` · window-QLS trimmed · `mtm`) = 20 cells ×
    **500 reps** (seeds 42+r) → sidecar with rep counts; per-cell prem_err + signed
    bias to aux; **primary = window-QLS-trimmed at the realistic ε=5 % cell**
    (identical config+seeds to E5's primary — E7 must reproduce it exactly; a free
    consistency check). Deliverable per steer 2: markdown decision table (estimator
    × ε, premium error %, direction) in this file + aux. train.py snapshotted to
    the reported cell (rule 4); rule 5 n/a (simulation study).
  - **Figures** (after E7, per steer 3): bespoke `figures_extra.py`
    (kleinlib.figures lacks these; dataviz-clean, colorblind-safe, dpi 150,
    MC-floor reference lines): breakdown-curve (E3+E7 sidecars, log-y for MLE's
    352 %), efficiency-cost bar (E2 rel. eff), window-QQ (E4 cell, trunc/cens
    shaded), premium tornado (E7 grid, signed, floor ±4.28 %, overcharging
    annotated — the money slide), severity-fan (E5 realistic cell: truth density
    vs per-estimator fitted fans).
- 2026-07-10 — **E5 (keep, commit `c006944`, primary 18.783886 = window-QLS-trimmed):
  RQ2+RQ3 combined answered — and the pre-registered hypothesis ("trim matters most")
  is OVERTURNED: the WINDOW is the correction that matters; trimming actively hurts.**
  Realistic cell (mixture, ε=5 %, d/u on), 500 reps, truth = functionals ($62,346.20;
  n_obs≈1,391, coverage 69.6 % vs 1−F(d)=69.5 % ✓, n_cens 0.126/rep). Headline:
  **trunc-MLE 7.85 %** (signed +2.10 — best) | window-QLS-trimmed 18.78 % (−18.55,
  UNDERcharge) | MTM 31.94 % (−31.94) | naive-MLE 57.53 % (+57.53, OVERcharge).
  2×2 QLS ablation: window-only **8.90 %** (−5.52) ≫ window+trim 18.78 % ≫ naive-QLS
  23.74 % ≫ trim-only 35.90 %. **Mechanism:** under a misspecified single-lognormal
  fit of a heavy-tailed MIXTURE, the top quantiles carry REAL risk (hail ×8, 8 % of
  claims), not just contamination — trimming p>0.85 deletes that signal and the fit
  underprices the tail (TVaR99 bias: trimmed-QLS −18.5 %, MTM −48.8 %). The (d,u)
  window is the PRINCIPLED trimmer: typos (×0.01) land below d, gross errors
  (×10–100) mostly land above u, so the KNOWN policy terms screen contamination
  without touching real mid-tail signal — that's why the two window-corrected
  untrimmed estimators (trunc-MLE, window-QLS-untrimmed) win. Direction split worth
  the filing memo: naive OVERcharges (+57.5 %), every trimmed/robust variant
  UNDERcharges. mle_tc's TVaR99 is nonetheless +13.6 % (misspecification pushes the
  fitted tail past the mixture's) — premium is partly saved by offset within the
  loading formula. Wall 34.6 s.
- 2026-07-10 — **E6 (keep, commit `e57c799`, primary 25.813827 = tail-blind
  window-QLS): RQ4 answered — the prior falls TWICE, and the steer-1 split is
  explicit.** Cell: mixture, tail_mode ON (fire GPD ξ=0.4, β=$125k above t=$250k),
  ε=0, trunc+cens, 500 reps (n_exc≈19.2/rep, POT fallback 0/500, n_cens 0.130/rep).
  **(a) Truth-side falsification:** the $2M limit CAPS the layer — the entire GPD
  tail is worth **+0.174 %** of premium (TVaR99 +0.219 %, VaR99 +0.000 %), two
  orders of magnitude below the ">10 % underpricing" prior. A policy limit is
  itself tail protection; tail shape beyond the cap cannot move a capped TVaR.
  **(b) Estimation-side falsification — tail-awareness HURTS here (steer-1 split,
  aware−blind |bias| in pp): premium +1.86, VaR99 +4.38, TVaR99 +2.85** (positive =
  aware worse). Mechanism: the exceedances above t are mostly HAIL lognormal mass
  (not fire GPD) → POT fits ξ̂ = 0.217 (true 0.4; sd 0.264; 35.6 % of fits clipped
  at the ξ≈0 floor) — a LIGHTER tail than the lognormal it replaces; and
  restricting the body fit to (d,t) deletes the beyond-t hail signal from the body
  (VaR99 bias −30.07 % aware vs −25.69 % blind) — E5's "don't delete real tail
  mass" lesson recurring at the threshold. **(c) Emergent finding:** at ε=0, ALL
  single-lognormal estimators underprice this mixture layer by ~23–26 % (blind QLS
  −25.77 %, trunc-MLE −23.39 %) — pure MISSPECIFICATION bias (hail); E5's smaller
  errors were contamination(+σ̂) partially cancelling misspecification(−tail). The
  dominant "tail risk" in this lab is the un-modelled hail component, not the GPD
  splice. E7's ε=0 column pins the tail-off misspecification floor. Wall 32.4 s.
- 2026-07-10 — **E7 (keep, commit `bfdef87`, primary 18.783886 = window-QLS-trimmed
  @ ε=5 %, EXACTLY reproducing E5's primary — consistency check passed): the
  decision table.** Second sanctioned sweep, 20 cells × 500 reps on the realistic
  lab (mixture, tail off, trunc d=$5k + cens u=$2M; truth premium $62,346.20;
  sidecar `sweeps/e7_decision.sidecar.tsv`). **The filing-memo table (steer 2):
  signed premium bias % vs truth (negative = UNDERcharge, positive = OVERcharge);
  |bias| ≈ mean |error| except near zero. 500 MC reps per cell; single-family MC
  floor for reference: 4.28 %.**

  | Estimator (single-lognormal fit) | ε=0 % | ε=1 % | ε=2 % | ε=5 % | ε=10 % |
  |---|---|---|---|---|---|
  | naive MLE (no corrections) | −33.9 | −20.0 | **−3.5** | +57.5 | **+188.9** |
  | truncated/censored MLE | −23.3 | −17.6 | −12.3 | **+2.1** | +15.9 |
  | window-QLS, trimmed [0.15,0.85] | −31.5 | −29.2 | −26.9 | −18.6 | **−0.6** |
  | MTM (trim 0.10) | −42.3 | −40.5 | −38.6 | −31.9 | −16.2 |

  Best-|error| per cell: mle_tc (ε=0: 23.3 %; ε=1: 17.7 %; ε=5: 7.9 %), naive-MLE
  (ε=2: 8.2 % — cancellation luck), window-QLS-trimmed (ε=10: 9.8 %). **How to read
  it (the two-error mechanic):** at ε=0 EVERY single-family estimator underprices
  by 23–42 % — that is pure MIXTURE-MISSPECIFICATION bias (the un-modelled hail
  tail), not estimation noise (mle_tc's −23.3 at tail-off ε=0 matches E6's tail-on
  −23.4; the GPD tail itself is worth +0.17 %). Contamination pushes premiums UP,
  so as ε rises the two errors CANCEL: naive-MLE crosses zero near ε≈2 %
  ("stopped-clock pricing" — right for the wrong reason, then catastrophically
  wrong: +188.9 % at ε=10); trunc-MLE sweet-spots at ε=5 (+2.1 %); trimmed
  window-QLS — the most contamination-immune — improves monotonically and is
  near-exact at ε=10 (−0.6 %) BY cancellation, not by fit quality. MTM always the
  worst underpricer. **Memo caveat: no cell on this grid reaches the 4.28 % MC
  floor by SKILL — every low-|error| cell is two wrongs cancelling. The structural
  fix is modeling the mixture (per-peril fits), not choosing among single-family
  estimators.** Wall 138.5 s; all 20 cells ok.
- 2026-07-10 — **PHASE 2 COMPLETE — LADDER COMPLETE (E1–E7, 7/7 keep, 0 crash, 0
  discard).** Figures shipped per steer 3 (`figures_extra.py` → `figures/`:
  breakdown_curve, efficiency_cost, window_qq, premium_tornado, severity_fan;
  dataviz-validated palette, worst adjacent CVD ΔE 47.2; MC-floor references;
  tornado annotates the overcharging direction with naive-MLE's +188.9 % flagged
  off-scale). True compute telemetry (aux wall_seconds; the summarize phase table
  has the acknowledged count-vs-ID display bug): phase 0 ≈ 1.3 s of 0.3 h; phase 1
  ≈ 108 s of 1.0 h; phase 2 ≈ 206 s of 1.0 h — total ≈ 5.3 min against 2.3 h.
  **RQ verdicts (experimenter's cut — synthesis stage will formalize):
  RQ1 CONFIRMED** (QLS-OLS 1.083× MLE premium error at ε=0, rel. eff 0.85/0.80;
  GLS surprise: no gain). **RQ2 CONFIRMED** (ε=5 %: MLE 136.6 % > 50 % vs QLS
  20.3 %/MTM 22.7 % < 25 %; MLE reaches 352 % at ε=10 on the single family).
  **RQ3 SPLIT** (window-QLS/trunc-MLE recover to the floor as predicted — but the
  naive->20 % half is falsified: param bias huge and theory-exact, premium bias
  only −5.2 % on the same layer). **RQ4 FALSIFIED, twice, instructively** (the
  $2M cap bounds the whole GPD tail to +0.174 % of premium; POT tail-awareness
  makes estimation WORSE at n≈1,380 — ξ̂ 0.22 vs 0.4; the REAL tail risk is the
  un-modelled hail mixture component: −23 to −42 % misspecification underpricing
  at ε=0, the study's biggest practical lesson, plus the E5 discovery that
  trimming deletes real hail signal — window ≫ trim). This closes the
  EXPERIMENT stage; SYNTHESIZE and TUTORIAL run separately per the ack.
