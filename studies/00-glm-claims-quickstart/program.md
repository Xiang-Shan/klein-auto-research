# Program — 00-glm-claims-quickstart

> This file is the living lab notebook for this study. Hypotheses, decisions, phase
> plans, and the Predictions-to-falsify table live here and are updated AS THE STUDY
> RUNS. `study.yaml` is the machine-readable contract; this file is the narrative.
> The loop invariants live in the repo `CLAUDE.md` and `.claude/skills/klein/SKILL.md`
> Hard Rules — this file does not restate them, it applies them to THIS study.

## Goal & metric contract

**Goal:** Reproduce the 215-exp campaign's GLM/HGBT anchors to prove split identity and onboard the framework

**Primary metric:** `val_auc` (higher is better) — the ONE number every
experiment optimizes. Everything else (PR-AUC, brier, wall_seconds, ...) goes to
`aux_metrics.tsv`, never into results.tsv.

**Schema:** the shape of `results.tsv` and `aux_metrics.tsv` is defined ONLY in
`kleinlib/schema.py`. This file never restates the column list — see
`kleinlib.schema.RESULTS_COLUMNS`. `new_study.py` wrote the header from
`kleinlib.schema.header_line()` at scaffold time; the indicative shape is
`experiment<TAB>...` (generated from kleinlib.schema — do not hand-edit).

## Data & split contract

- **Source:** data_hub:insurance-claims — prepared by `uv run prepare.py`.
- **Split:** see `study.yaml:data.split` — FIXED across every experiment. Never
  resample, reshuffle, or peek at the held-out split. Comparability depends on it.
- The DATA gate (`data_card.md`) must say **go** before the first modeling run.

## Mutable surface

- **Mutable:** `train.py` ONLY. The per-experiment diff is 5–15 lines.
- **Fixed:** `prepare.py`, `study.yaml`, `kleinlib/` — changing these is rare and
  deliberate, never part of an experiment diff.
- Sweeps are the ONE exception and live under `sweeps/` — see
  `.claude/skills/klein/references/sweep-rules.md`.

## Phases & budgets

Authoritative copy is `study.yaml:phases`. Mirror here for quick reading; STOP for user
ack at every phase boundary.

| Phase | Description | Min/Max exp | Budget |
|---|---|---|---|
| 0 | anchors — reproduce campaign GLM/HGBT recipes EXACTLY (split-identity gate + calibration doctrine smoke) | 1–4 | 1h |

Single-phase study: this quickstart is entirely Phase 0 (E1-E4). No later phases planned —
if the anchors reproduce, the study's job (onboarding + CI smoke) is done.

## Research questions

Authoritative copy is `study.yaml:research_questions`. One verdict per RQ in
`findings.md`, each citing evidence experiment IDs.

| ID | Question | Prior (honest expectation) |
|---|---|---|
| RQ1 | does prepare.py + the fixed split reproduce the campaign's anchors exactly? | yes if preprocessing matches — the split-identity gate exists precisely to catch a preprocessing diff before it poisons every later comparison |
| RQ2 | does the calibration-first doctrine (cw=None + isotonic beats cw=balanced) hold on these anchor configs? | class_weight=balanced boosts AUC negligibly-to-not-at-all but wrecks brier/logloss vs class_weight=None + isotonic calibration |

## Predictions to falsify

Fill `predicted` NOW (before running); fill `observed` + `verdict` during SYNTHESIZE.
A prediction with no verdict is an unfinished study.

| Lever | Predicted Δ | Observed Δ (exp IDs) | Verdict |
|---|---|---|---|
| E1 split-identity anchor: LR+OHE(min_freq=20)+cw=balanced | val_auc = 0.6255 +/- 0.001 (GATE) | 0.625462 (exp 1); \|Δ\|=0.000038 | HELD (essentially exact) |
| E2 campaign winning Phase-1 LR: splines+log1p+interactions+isotonic | val_auc = 0.6528 +/- 0.003 | 0.625533 (exp 2); Δ=-0.0273 | FALSIFIED for this reconstruction — see log for the 7-variant investigation; historical recipe not recoverable (discard, no commit) |
| E3 campaign Phase-0 HGBT: OHE+7 col drops+shrinkage | val_auc = 0.6629 +/- 0.003 | 0.662897 (exp 3); \|Δ\|=0.000003 | HELD (essentially exact) |
| E4 E1 config with cw=None+isotonic instead of cw=balanced | val_auc within +/- 0.003 of E1; brier/logloss much improved | 0.622859 (exp 4); Δ=-0.002603 vs E1; brier 0.2402→0.0593 (~4x), logloss 0.6726→0.2324 (~3x) | HELD |

## Guardrails (this study)

- **Foreground runs only:** `uv run train.py 2>&1 | tee run.log`, terminal timeout =
  phase budget in ms. A run over budget is a `crash` (timeout note), reverted.
- **Commit-or-revert FIRST, then ONE results.tsv row.** Never the reverse; never batch.
- **Status honesty:** keep / discard / crash. A crash is logged with `NA` metric, not
  retried into oblivion. A missing row is worse than a crash row.
- **Sweeps:** only via the escape-hatch — every trial to a sidecar TSV, ONE winner row.
- **Phase-boundary acks:** summarize and STOP at each phase boundary.
- **Branch:** run on `experiments/00-glm-claims-quickstart`, never `main`. Merge at study end.

## Log (append-only)

Narrate decisions here as the study runs — why each direction, what a cluster of
discards taught you, where you changed course. This is what SYNTHESIZE mines.

- 2026-07-10 — study scaffolded. Next: CONSULT confirm → DATA gate → METHOD gate.
- 2026-07-10 — **CONSULT: fast-path taken.** The task brief answered all six interview
  axes up front (goal, data source+size known from data_hub catalog, method familiarity
  = familiar/anchor-only, metric+direction, budget ~1h/4 experiments, deliverables =
  standard findings.md+tutorial). No open axis required asking the user; study.yaml,
  program.md, research_plan.md drafted directly from the brief per the fast-path rule
  in `references/consult-protocol.md`. Logged here per Hard Rule 3 (a fast-path skip
  must be logged with a reason, never silent).
- 2026-07-10 — This is the FAMILIAR-model anchor study (per SKILL.md routing): LR and
  sklearn HistGradientBoostingClassifier are well-understood, not frontier/unfamiliar
  methods. method_card.md is therefore a short study-local card pointing to
  `../../knowledge/method_cards/glm-pricing.md` for the full pedagogy, per the METHOD
  gate protocol's allowance for familiar methods (the protocol's mandatory lit-scan
  applies to frontier/unfamiliar methods; GLM logistic regression is neither).
- 2026-07-10 — **E1 (exp 1, keep, commit 7c3a25b): val_auc=0.625462.** Split-identity
  GATE PASSED: |0.625462 - 0.6255| = 0.000038, well inside the 0.001 tolerance — in
  fact this is essentially a bit-exact reproduction of the campaign's own
  val_auc=0.625462 for the identical recipe (LR, OHE min_freq=20, class_weight=
  balanced, seed42/0.2/stratified split). This confirms `kleinlib.data`/`encoders`/
  `eval` are a faithful port and `prepare.py` replicates the campaign's prepare.py
  output exactly (same row count 58,592, same 45 prepared columns). aux: brier=0.2402,
  logloss=0.6726 — poor calibration, as expected from `class_weight=balanced` (matches
  the campaign's own exp1/exp13/exp32 observations) and sets up E4's doctrine test.
  RQ1 evidence collected (verdict deferred to SYNTHESIZE, pending E2/E3 too).
- 2026-07-10 — **E2 (exp 2, keep, commit ae552d5): val_auc=0.625533 — target 0.6528
  MISSED by -0.027 (outside both the ±0.003 tolerance and the "wildly off >0.01"
  caution).** Documenting the reconstruction investigation honestly, since this
  deviation is large:
  - **Why this had to be reconstructed, not `git show`'d:** the campaign's Phase-1
    spline block (exps 39-48) is entirely `discard`-status in `results.tsv` (commit
    field blank for all of them) — per the same commit-or-revert discipline this
    framework itself enforces, a discarded experiment's `train.py` is reverted and
    never committed. There is no surviving code for exp 40/43/46/47 anywhere in the
    campaign's git history (verified: `git log --oneline -- program.md` and
    `docs/*.md` history show no code, only the terse `results.tsv` descriptions and
    one later synthesis doc).
  - **Recipe recovered from descriptions:** exp40 "SPLINES(5knots,deg3) on
    subscription_length/vehicle_age/customer_age" (0.650186, "+0.025 HUGE" vs the
    0.6255 anchor); exp41 "+log1p" (no marginal gain alone); exp43 "+interactions
    (density*vage, sublen*vage)" (0.651409); exp46/47 "+CALIBRATE(sigmoid/isotonic)"
    (0.651492 / 0.652847, brier 0.059 logloss 0.229).
  - **7 reconstruction variants tried, none closed the gap:** (1) the recipe as
    literally assembled (splines+log1p(density)+2 interactions+isotonic) →
    0.625533; (2) splines-only n_knots=5 (matching exp40's stated config exactly,
    no FE/calibration) → 0.627959, i.e. +0.0025 over baseline, NOT +0.025; (3)
    n_knots swept 5/10/20/50 → ceiling 0.640754 at 50 knots (a resolution far
    beyond "5knots" and still 0.012 short of 0.6502); (4) LR regularization C swept
    0.1-1000 → flat ~0.627-0.628, rules out an L2-shrinkage explanation; (5)
    combined splines+log1p+interactions with/without dropping the 7 model-derivative
    columns → 0.626479 either way; (6) splines(3 cols)+categoricals only, ALL other
    numerics dropped → 0.510 (much worse — rules out a feature-selection/decluttering
    explanation); (7) splines alone / categoricals alone (no combination) → 0.592 /
    0.497. **Conclusion:** the marginal, information-theoretic ceiling of nonlinear
    transforms on just these 3 continuous columns (even generously over-resolved at
    50 knots) is empirically ~0.64, not 0.65+ — the historical "+0.025 HUGE" jump for
    exp40 could not be reproduced from the documented recipe alone.
  - **Independent cross-check supporting this reconstruction, not the historical
    number:** the campaign's OWN later synthesis, `docs/insights_and_framework.md`
    §2.3, states the LR family's "FE (splines): +0.005" contribution toward the
    0.6528 figure — an order of magnitude smaller than the "+0.025" framing in the
    `results.tsv` free-text description, and much closer to what this reconstruction
    finds. The two campaign artifacts disagree with each other; this study's
    empirical ceiling test sides with the synthesis doc's smaller number.
  - **Decision: logged as `keep` per the task instruction ("target 0.6528±0.003 →
    keep... log observed delta honestly either way"), NOT a full study STOP.** The
    hard "STOP EVERYTHING" language in this study's brief is scoped explicitly to
    E1's split-identity GATE (which passed almost exactly) — E2's tolerance language
    is softer by design, anticipating exactly this kind of irrecoverable-recipe
    scenario for a `discard`-status historical experiment. Calibration mechanics
    otherwise check out well (brier=0.059307/logloss=0.232177 vs the campaign's
    reported 0.059/0.229 — very close), isolating the shortfall to the
    discriminative FE lift specifically, not the calibration wrapper.
  - RQ1 verdict (deferred to `findings.md`): partially open — E1 says yes
    (near-exact), E2 is the one anchor that does NOT reproduce; this is itself a
    finding about the LIMITS of reproducing a non-committed historical experiment
    from prose, not evidence against the framework/kleinlib port (which E1 and, as
    tested next, E3 both validate).
- 2026-07-10 — **E3 (exp 3, keep, commit b1389ca): val_auc=0.662897.** Target
  0.6629±0.003 essentially exact: |0.662897-0.6629|=0.000003 — a bit-for-bit match
  to the campaign's own exp7 value. Recipe recovered VERBATIM via `git show` of two
  committed (keep-status) campaign commits (exp6 0fc6c00 + exp7 e801cec), unlike
  E2's reconstruction. This is the SECOND independent confirmation (after E1) that
  `kleinlib.data`/`encoders`/`eval` faithfully port the campaign's `lib/` — two for
  two on every anchor where the historical code actually survived in git history.
  RQ1 verdict now firmly supported: the framework reproduces campaign anchors
  exactly whenever the exact recipe is recoverable (E1, E3); E2's shortfall traces
  to the historical recipe itself being unrecoverable (discard, no commit), not to
  any defect in the port.
- 2026-07-10 — **E4 (exp 4, keep, commit 2e046bb): val_auc=0.622859.** RQ2 doctrine
  smoke test, textbook result: E1's exact preprocessing with `class_weight=None`
  + isotonic (`CalibratedClassifierCV`, cv=3) instead of `class_weight="balanced"`.
  val_auc delta vs E1 = -0.002603 (within the predicted ±0.003 band) while
  val_brier improved ~4x (0.240153 → 0.059279) and val_logloss improved ~3x
  (0.672617 → 0.232385). RQ2 verdict: **HELD** — the calibration-first doctrine
  (war story #4 / `knowledge/method_cards/glm-pricing.md`) reproduces cleanly on
  this study's own anchor configs, not just as an inherited claim from the
  campaign. Saved `models/latest_val_preds.npz`; ran
  `.claude/skills/klein/scripts/make_figures.py` — reliability diagram confirms
  near-diagonal calibration in the low-probability region (base rate 6.4%),
  metric trajectory shows all 4 anchors as `keep` with E3's HGBT spike visible.
- 2026-07-10 — **Phase 0 / study complete: all 4 planned experiments run.** Ran
  `summarize_results.py` for the aux panels + phase telemetry (see
  `results_summary.md`). Final per-experiment table: E1=0.625462 (GATE PASS,
  near-exact), E2=0.625533 (target missed, reconstruction limit — see above),
  E3=0.662897 (near-exact), E4=0.622859 (doctrine CONFIRMED). Natural stop point
  per `stop_rule` — all min/max_experiments (1-4) for Phase 0 satisfied.
- 2026-07-10 — **Housekeeping fix:** re-running E2's `train.py` a second time (to
  capture a clean `run.log` after the reconstruction debugging session) caused
  `kleinlib.eval.evaluate`'s unconditional append to double-write exp2's block in
  `aux_metrics.tsv` (identical values, `wall_seconds` differing by run-to-run
  noise). `results.tsv` was never affected (its one row per experiment is written
  by a single explicit `printf`, not by `evaluate()`). Removed the redundant
  second block by hand so the sidecar carries exactly one clean set of rows per
  experiment; `results_summary.md`/`progress.svg` regenerated identically (the
  duplicate had already been silently deduplicated by `summarize_results.py`'s
  last-write-wins dict keying, so this was a ledger-hygiene fix, not a numbers
  fix). Lesson for future studies: avoid re-running `train.py` purely for
  cosmetic log cleanliness once a result is already recorded — the sidecar is
  append-only and has no dedup.
- 2026-07-10 — **E5 "E2-redux" (exp 5, keep, commit 1fb8ca6): val_auc=0.651707 —
  target 0.6528 essentially HIT** (|0.651707-0.6528|=0.001093, well inside ±0.003;
  +0.0262 over exp 2's 0.625533). This is a redo of E2's reconstruction, this time
  following the git-recovery protocol properly instead of assembling the recipe from
  results.tsv prose alone:
  - **The recovered base.** In the campaign repo, every LR-family experiment from
    exp9 through exp48 — including the entire Phase-1 spline block, exps 40-48 — is
    `discard` with no surviving commit. The LAST LR-family `keep` row before that
    block is **campaign exp1** (`commit 5a70203`, "foundation baseline
    LogReg+OHE+balanced"), confirmed via `git show 5a70203:train.py`: OHE(min_freq=20)
    + median-impute/StandardScaler numerics + `LogisticRegression(max_iter=2000,
    solver=saga, class_weight=balanced, random_state=42)` — structurally identical to
    this study's own E1. That IS the true accumulated base; there is no undiscovered
    intermediate commit hiding in Blocks A-F (encoder ranking, regularization,
    imbalance treatments) — none of them beat exp1's baseline enough to get kept and
    committed either, so the campaign's Phase-1 exploration ran entirely on an
    uncommitted, hand-iterated `train.py` from exp9 to exp48.
  - **The delta chain, applied on top of that base:** exp40 splines
    (`SplineTransformer(n_knots=5, degree=3)` on subscription_length/vehicle_age/
    customer_age) → exp41 `+log1p(region_density)` → exp43 `+2 interactions`
    (`log1p(region_density)*vehicle_age`, `subscription_length*vehicle_age`) → exp47
    `+isotonic calibration` (skipping exp46's intermediate sigmoid step, since exp47
    supersedes it and IS the 0.652847 target row).
  - **What actually closed the gap — three specifics the compressed descriptions
    never mention:** exp 2 implemented this exact same conceptual chain (same base,
    same levers, same column names) and landed at 0.625533 — *below* its own
    splines-only ablation (0.627959, see E2's log) once log1p+interactions+isotonic
    were stacked on. E5 fixes three implementation-level details left at sklearn's
    defaults in E2, none of which are recoverable from "SPLINES(5knots,deg3)" as a
    phrase:
    1. `knots="quantile"` instead of sklearn's default `"uniform"` — adaptive knot
       placement matching where the data actually lives (standard GAM practice, but
       not sklearn's default, and "5 knots" alone doesn't say which).
    2. `include_bias=False` on the spline transformer — a partition-of-unity spline
       basis with `include_bias=True` (sklearn's default) duplicates the LR's own
       intercept; redundant, and quietly degrades the fit.
    3. `CalibratedClassifierCV(cv=5)`, not `cv=3` — matches the campaign's OWN
       documented recommendation (`docs/best_practices_auto_insurance.md` §3.3 pt.4:
       *"CalibratedClassifierCV(method='isotonic', cv=5)"*); both E2 and E4 used
       `cv=3`, an undocumented deviation nobody had flagged until this pass.
    Corroborating evidence this is a genuine recovery, not a lucky number: aux
    brier=0.058960 / logloss=0.229111 vs the campaign's own reported 0.059/0.229 for
    exp47 — matching almost to the digit, on BOTH the primary metric and two
    independent calibration metrics simultaneously.
  - **The compressed-description lesson (why this matters beyond one number).** A
    one-line results.tsv description like *"LR+SPLINES(5knots,deg3) on
    subscription_length/vehicle_age/customer_age: 0.6502 — HUGE +0.025"* names the
    LEVER (splines, 3 columns, 5 knots, degree 3) but not the dozen implementation
    choices that determine whether that lever actually delivers +0.025 or only
    +0.0025 — knot placement strategy, bias handling, solver, and (three levers
    later) the calibration wrapper's fold count. `git show`-ing a `keep` commit
    (E1, E3 in this study) recovers those choices exactly, for free. `git recover the
    base, then re-apply the described delta` (this experiment's protocol) is
    STRICTLY BETTER than reconstructing purely from prose (E2's approach) because it
    at least anchors the starting point exactly — but it still leaves every
    within-block implementation detail to informed reconstruction. The task
    instruction to "read the exact description texts for details" was necessary but
    not sufficient; closing the gap took recognizing which sklearn defaults were
    plausible candidates for silent divergence and cross-checking one of them
    (calibration cv) against a SEPARATE campaign artifact (the best_practices doc)
    that happened to state it explicitly. **Actionable rule for future studies:**
    when a `discard`-status experiment's description will matter later, log the 2-3
    non-default constructor kwargs explicitly in the description text itself (e.g.
    "splines(quantile knots, no bias)") — the two extra words would have made E2
    exact on the first try instead of needing this redo.
  - RQ1 verdict update: E5 converts the one open anchor (E2's failed reconstruction)
    into a near-exact reproduction, using the same git-grounded method that already
    validated E1 and E3. Of the five experiments run so far, only E2 itself remains a
    genuine miss — and it is now understood WHY (prose-only reconstruction of an
    uncommitted, multi-step delta chain) rather than left as an open mystery.
- 2026-07-10 — **E6 "sweep demo" (exp 6, keep, commit 3f3822f): val_auc=0.664322 —
  new study best.** First real use of the newly-landed `kleinlib.sweep.SweepRunner`
  (WP6), run exactly per `.claude/skills/klein/references/sweep-rules.md`:
  - **Sweep:** `sweeps/hgbt_lr.py` swept ONE axis, `learning_rate` in {0.03, 0.06,
    0.1, 0.15, 0.2}, on top of exp 3's exact preprocessing/drops (OHE min_freq=20,
    the same 7 dropped model-derivative columns, class_weight=balanced,
    max_leaf_nodes=31, early_stopping) — nothing else varied, the split loaded once
    and reused for all 5 trials. All 5 trials `status=ok`, appended to
    `sweeps/hgbt_lr.sidecar.tsv` in order:

    | trial | learning_rate | val_auc | wall_seconds |
    |---|---|---|---|
    | 1 | 0.03 | 0.662705 | 1.2 |
    | 2 | **0.06** | **0.664322** | 0.7 |
    | 3 | 0.10 | 0.660501 | 0.6 |
    | 4 | 0.15 | 0.661399 | 0.5 |
    | 5 | 0.20 | 0.654928 | 0.5 |

    Non-monotonic in `learning_rate` — 0.06 beats both its neighbors (0.03 and
    0.10) — consistent with exp 3's own `learning_rate=0.05` sitting near a local
    optimum for this `max_iter=500`/`early_stopping=True` combination; the sweep
    just nudges it slightly higher.
  - **Winner vs baseline:** `learning_rate=0.06` -> val_auc=0.664322 vs exp 3's
    baseline 0.662897: `improved_over(0.662897)` = **True** (delta=+0.001425). Sweep
    rule 7's "no improving trial" branch does NOT apply here — this took the
    **improved path** (rules 4-6): winner snapshotted into `train.py` (no sweep
    machinery — a plain 5-line diff from exp 3's committed recipe, just
    `learning_rate` and the experiment id), `train.py` rerun once foreground and
    reproduced 0.664322 exactly (bit-for-bit match with the sweep's own trial 2,
    confirming the snapshot is faithful), which pickled a new study-best model
    (`models/best_6_0.6643.pkl`, manifest updated) via `kleinlib.eval.evaluate`'s
    normal `maybe_save_best` side effect. Committed train.py+sweep script+sidecar,
    then the one `results.tsv` row pointing at the sidecar, per the rules — the
    sidecar carries the full 5-trial record so nothing about the search is lost even
    though only the winner earns a ledger row.
  - **Escape-hatch validated end-to-end:** this is the first sweep run against the
    real `kleinlib.sweep.SweepRunner` (rather than the sidecar-by-hand fallback
    `klein-sweeper.md` allowed before the module existed) — every trial landed in
    the sidecar in arrival order, the runner touched neither `results.tsv` nor git
    nor `models/`, and the improved-path bookkeeping (snapshot -> rerun -> commit ->
    one row) matched the protocol exactly. New study best across all 6 experiments:
    E6 (HGBT, tuned learning_rate) at 0.664322, ahead of E3's HGBT anchor
    (0.662897) and far ahead of the LR family's ceiling (E5, 0.651707).
