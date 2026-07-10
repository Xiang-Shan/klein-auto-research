---
type: findings
domain: insurance
status: complete
concepts: [split-identity, calibration-first-doctrine, compressed-description-trap, isotonic-calibration, git-recovery, value-pattern-check, weak-signal, rank-vs-calibration]
related: [program.md, method_card.md, data_card.md, results.tsv, aux_metrics.tsv, ../../knowledge/method_cards/glm-pricing.md, ../../knowledge/best-practices-auto-insurance.md, ../../knowledge/encoder-comparison.md, report/index.html]
---

# Findings — 00-glm-claims-quickstart

> SYNTHESIZE stage output. QUALITY BAR: every claim cites experiment IDs from
> `results.tsv` / `aux_metrics.tsv`; no claim without evidence. Contradictions with the
> method-card priors are called out explicitly. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`.
>
> Trajectory mined: 6 experiments, all `status=keep`, no discards or crashes in *this*
> study's ledger — but the pivotal discard cluster lives in the **ancestor campaign**
> (its Phase-1 spline block, exps 40–48, all discard/uncommitted), and reproducing it is
> the whole story of E2→E5. See ③.

## ① Research-question verdicts

| RQ | Verdict | Evidence (exp IDs) | Metric delta |
|---|---|---|---|
| **RQ1** — does `prepare.py` + the fixed split reproduce the campaign's anchors exactly? | **CONFIRMED** (wherever the exact recipe is recoverable) | E1, E3 (direct); E5 (after git-recovery); E2 is the instructive lone miss | E1 \|Δ\|=**0.000038** vs 0.6255; E3 \|Δ\|=**0.000003** vs 0.6629; E5 \|Δ\|=**0.001093** vs 0.6528 |
| **RQ2** — does calibration-first (`class_weight=None` + isotonic) beat `class_weight="balanced"` for probability quality on these anchors? | **CONFIRMED** | E4 (direct A/B vs E1), corroborated by E5 | E4 brier **0.240153 → 0.059279** (~4×), logloss **0.672617 → 0.232385** (~2.9×), val_auc **−0.002603** (within ±0.003) |

**RQ1 detail.** Two of three directly-reproducible anchors land essentially bit-exact:
E1 (LR+OHE, `class_weight=balanced`) at 0.625462 is 0.000038 off its 0.6255 GATE target,
and E3 (HGBT, recovered *verbatim* via `git show` of the campaign's committed exps 6/7)
at 0.662897 is 0.000003 off 0.6629. The one anchor that did **not** reproduce on first
attempt — E2 (0.625533 vs 0.6528 target, Δ=**−0.0273**) — was reconstructed from the
campaign's *prose* `results.tsv` descriptions because its source recipe (exps 40–48) is
`discard`-status with no surviving commit. E5 later recovered it to 0.651707 (Δ=−0.0011)
using the git-grounded method that already validated E1/E3. **RQ1 verdict: the framework
port (`kleinlib.data`/`encoders`/`eval` + `prepare.py`) reproduces campaign anchors
exactly whenever the exact recipe is recoverable; E2's shortfall is a fact about
recovering an uncommitted recipe from compressed prose, not a defect in the port** (see ③).

**RQ2 detail.** E4 is a clean single-lever A/B against E1: identical preprocessing, only
`class_weight="balanced"` → `class_weight=None` + `CalibratedClassifierCV(isotonic)`.
Discrimination barely moves (val_auc 0.625462 → 0.622859, −0.002603) while calibration
improves ~4× on Brier (0.240153 → 0.059279) and ~2.9× on log-loss (0.672617 → 0.232385).
E5 independently lands the study's **best Brier of all six runs, 0.058960**, on a
calibrated LR. The doctrine (war story #4; `knowledge/method_cards/glm-pricing.md` §4)
holds on this study's own anchor configs, not merely as an inherited claim.

## ② Predictions to falsify (filled)

Levers copied from `program.md` / `study.yaml:predictions_to_falsify`; observed + verdict
filled from the trajectory.

| Lever | Predicted Δ | Observed Δ (exp IDs) | Verdict |
|---|---|---|---|
| **E1** split-identity anchor: LR+OHE(min_freq=20)+`cw=balanced` | val_auc = 0.6255 ± 0.001 (hard GATE) | 0.625462 (E1); \|Δ\|=0.000038 | **HELD** — essentially bit-exact; GATE PASS |
| **E2** Phase-1 LR: splines+log1p+interactions+isotonic | val_auc = 0.6528 ± 0.003 | 0.625533 (E2); Δ=−0.0273 **→** 0.651707 (E5 redux); Δ=−0.0011 | **FALSIFIED for the prose reconstruction (E2); HELD after git-recovery (E5)** |
| **E3** Phase-0 HGBT: OHE + 7 model-derivative col drops + shrinkage | val_auc = 0.6629 ± 0.003 | 0.662897 (E3); \|Δ\|=0.000003 | **HELD** — bit-exact (recipe recovered verbatim via `git show`) |
| **E4** E1 config with `cw=None` + isotonic (cv=3) | within ±0.003 of E1; reliability near-diagonal; brier/logloss much improved | 0.622859 (E4); Δ=−0.002603 vs E1; brier ~4×, logloss ~2.9× better | **HELD** |
| **Sweep (E6)** HGBT `learning_rate` ∈ {0.03,0.06,0.1,0.15,0.2} | *no pre-registered prediction* — added post-Phase-0 as the WP6 escape-hatch demo | winner lr=0.06 → 0.664322; **+0.001425** vs E3 baseline 0.662897 (`sweeps/hgbt_lr.sidecar.tsv`) | **improved-path taken** (small, honest lift; see ⑤) |

The E2 row is the one falsified prediction in the study, and it is the most valuable one:
it converts "the anchor didn't reproduce" into a precise, mechanistic finding (③) rather
than an open mystery. The sweep (E6) carried no falsifiable prior — it is a *demonstration*
of the sanctioned sweep protocol, not a hypothesis test — so it is logged as an
improved-path result, not a held/falsified verdict.

## ③ Surprises and why

**Surprise 1 — the compressed-description trap (the study's headline finding, and a
*framework* lesson).** E2 assembled the campaign's Phase-1 recipe faithfully at the
*lever* level — same base (LR+OHE), same splines (5 knots, degree 3) on the same three
columns, same `log1p(region_density)`, same two interactions, same isotonic wrapper — and
landed at **0.625533**, a full **−0.0273** below the 0.6528 target and, tellingly, *below
its own splines-only ablation* (0.627959, logged in E2's investigation). Stacking more
"correct" features made it worse. E5 recovered the target to **0.651707** (**+0.026174**
vs E2; **+0.026245** vs the E1 foundation) by fixing **three implementation details that
never appear in any `results.tsv` description**:
1. `knots="quantile"` instead of sklearn's default `"uniform"` — "5 knots" alone doesn't
   say *where*;
2. `include_bias=False` on `SplineTransformer` — the default `True` duplicates the LR
   intercept and quietly degrades the fit;
3. `CalibratedClassifierCV(cv=5)`, not `cv=3` — cv=5 is what the campaign's *own*
   `best_practices` doc §3.3 recommends; E2 and E4 silently used cv=3.

**Why it matters:** a one-line ledger description names the **lever** (splines, 3 columns,
5 knots, deg 3) but not the dozen constructor kwargs that decide whether that lever
delivers +0.025 or +0.0025. Corroboration that E5 is a genuine recovery and not a lucky
number: its aux **brier=0.058960 / logloss=0.229111** match the campaign's reported
exp47 (0.059 / 0.229) almost to the digit, *simultaneously* on the primary metric and two
independent calibration metrics. **The mechanism / framework lesson: a `git show` of a
`keep` commit recovers every choice exactly and for free (as E1 and E3 prove); prose
cannot. Keep-chain commits are the real config record — descriptions compress, and the
compression is lossy exactly on the non-default kwargs that move the number.** Actionable
corollary already logged for future studies (program.md, E5): when a `discard`-status
experiment's recipe will matter later, spend two words in the description on the
non-default kwargs (`splines(quantile knots, no bias)`) — that would have made E2 exact on
the first try.

**Surprise 2 — the pandas string-dtype war story, reproduced LIVE in this environment,
not merely inherited.** Under this machine's pandas 3.0.3, all 19 boolean-ish columns (17
`is_*` Yes/No + `rear_brakes_type` + `transmission_type`) read in with dtype reported as
`str`, **not** `object` (`data_card.md`, value-pattern check). A naive `dtype == "object"`
gate would silently skip **all 19** — the ancestor campaign's ~2-hour war story, live in
2026 pandas. The value-pattern detectors (`kleinlib.data.detect_yes_no_columns`) key on the
actual value set, never the dtype label, which is why E1 reproduced the 58,592×45 prepared
frame bit-for-bit. **Why:** pandas 3.0 made string storage the default; the dtype *label*
changed, so any check that trusts the label (rather than the values) breaks anew.

**Surprise 3 — the study's best-AUC model is *not* its best-calibrated model.** E6 (HGBT,
val_auc **0.664322**, study best) carries brier **0.222681** — **3.8× worse** than E5's
calibrated-LR brier of 0.058960 — because every HGBT run (E3, E6) is `class_weight=balanced`
and *uncalibrated*. Rank and calibration trade off here, and "best model" is
use-dependent (see ⑤). No run tripped the `min_proba_std` collapse guard (E1 0.099, E3/E6
~0.14, the calibrated LRs E2/E4/E5 ~0.02–0.03 — low but healthy, isotonic compressing
toward the 6.4% base rate, not a collapse).

## ④ Practical advice

On your own data, in priority order:

1. **Reproduce from committed keeps, not from prose.** If you must re-run a historical
   result, `git show <commit>:train.py` a `keep` row (E1, E3: bit-exact) before you ever
   reconstruct from a description (E2: −0.0273). If the source is a `discard` with no
   commit, git-recover the nearest committed *base* and re-apply the delta (E5), and treat
   every within-block kwarg as a suspect.
2. **For linear models, the spline defaults are wrong.** Set `SplineTransformer(knots=
   "quantile", include_bias=False)` — sklearn's defaults (`uniform`, `include_bias=True`)
   cost you most of the lift (E2 vs E5, +0.026). "n_knots=5" is not a recipe.
3. **Calibrate, don't reweight.** For a ~6% positive target, default to
   `class_weight=None` + `CalibratedClassifierCV(method="isotonic", cv=5)` (cv=**5**, per
   the campaign best-practices doc, not cv=3). E4 buys a ~4× Brier improvement for a
   −0.0026 AUC cost; `class_weight="balanced"` (E1) wrecks calibration for no ranking gain.
4. **OHE for linear, always; never ordinal.** E1 reproduces 0.6255 with OHE(min_freq=20);
   `glm-pricing.md` records ordinal at 0.4039 — a self-inflicted −0.22 AUC wound on a
   linear model. (For trees the same choice is ±0.005 noise.)
5. **Log the 2–3 non-default kwargs in the ledger description itself.** The commit records
   the code; the description is what a *future reader* reconstructs from. Two extra words
   (`quantile knots, no bias`) is the cheapest insurance in the framework.
6. **Commit-or-revert first, then exactly one `results.tsv` row.** The E2 double-write
   incident (program.md housekeeping note) is a reminder that the aux sidecar is
   append-only with no dedup — don't re-run `train.py` for cosmetic log cleanliness once a
   result is recorded.

## ⑤ Business / actuarial value implications

- **Calibrated premiums without losing rank order.** For pricing, the load-bearing number
  is a *calibrated* P(claim), not a rank — a technical premium is `P(claim) × severity`,
  attached policy-by-policy. E1's `class_weight="balanced"` model (brier 0.240153) is
  systematically biased in probability (balanced reweighting inflates the positive class),
  so premiums built on it would run high; E4/E5 fix this **~4× on Brier at essentially
  zero discrimination cost** (val_auc −0.0026, E4 vs E1). This is exactly where the
  actuarial value sits: the same rank order, now bankable as a probability.
- **The sweep's +0.0014 AUC is real but small — and not free for pricing.** E6's
  `learning_rate=0.06` beats E3 by +0.001425 val_auc, but its decile lift *regressed*
  (lift@10 2.041568 → 2.001537, E3→E6) and it is uncalibrated (brier 0.222681). For a
  filing/pricing use case that needs calibrated probabilities and stable top-decile
  triage, E5 (calibrated LR, brier 0.058960, lift@10 1.788040) is the more defensible
  model despite its lower AUC; E6 is the pick only for a pure ranking/triage use where the
  +0.0014 nudge matters and probabilities will be recalibrated downstream. **Be honest:
  +0.0014 AUC does not move a rate filing.**
- **Transparency / filing.** The LR anchors (E1/E5) give underwriter-readable odds-ratio
  coefficients and are monotone-by-construction — the filable, auditable option. The
  ~0.013 AUC the GLM leaves on the table vs HGBT (E5 0.651707 vs E6 0.664322) is the known
  price of that transparency, not a bug (`method_card.md` regime verdict).
- **Speed is not the constraint here.** The calibrated LRs are the *slowest* runs
  (E4 39.997s, E2 25.4s, E5 22.9s — the isotonic cross-fit dominates) while the HGBTs are
  ~20–40× faster (E3 1.28s, E6 0.90s). At 59k rows none of this matters operationally; the
  note is only that calibration cost, not fit cost, is where LR spends its wall-clock.

## ⑥ Literature / campaign tie-back

- **Reconciling the campaign's "+0.005 splines" with our +0.026 chain.** The campaign's own
  synthesis (`glm-pricing.md` §5 / insights doc §2.3) attributes **"FE (splines): +0.005"**
  to the spline step, while the same doc's §4 elsewhere frames LR FE as **"+0.025 AUC"** and
  the raw exp40 `results.tsv` description says **"+0.025 HUGE"** — three different campaign
  numbers for "what splines buy." Our trajectory dissolves the apparent contradiction: they
  measure different things. Splines *alone* on the three columns are worth ~+0.0025 in our
  hands (E2's splines-only ablation 0.627959 vs E1 0.625462), consistent with the small
  "+0.005" figure; the **full chain** (splines + log1p + 2 interactions + isotonic, with
  the recovered `quantile`/`no-bias`/`cv=5` kwargs) is worth **+0.026245** (E5 0.651707 vs
  E1 0.625462). **So the synthesis doc's "+0.005 splines" understates the full FE+calibration
  chain's +0.026 vs the foundation LR by ~5×** — not because either number is wrong, but
  because a reader who reads "+0.005" as "what the FE is worth" will badly under-budget the
  whole chain. Rows cited: E1 (foundation) 0.625462; E5 (full chain) 0.651707;
  `glm-pricing.md` anchor-trajectory table (LR+OHE 0.6255 → LR+splines+interactions+isotonic
  0.6528).
- **Ceiling positioning matches the literature.** E5's LR ceiling (0.651707) sits ~0.013
  below the HGBT anchor (E6 0.664322), reproducing the campaign/`method_card` claim that a
  GLM "leaves ~0.017 AUC on the table" because it cannot auto-discover interactions — and
  matching the broader tabular consensus (Grinsztajn 2022, cited in
  `knowledge/method_cards/gbdt-tabular.md`) that trees edge out linear models on weak-signal
  tabular. The GLM's value here is filing/calibration, not discrimination.
- **Knowledge-base cell disagreement (flagged, not resolved here).** The two campaign docs
  disagree on the LightGBM-native and LightGBM-target encoder cells:
  `knowledge/encoder-comparison.md` lists LGBM Native **0.6630** / Target **0.6684**, while
  `knowledge/best-practices-auto-insurance.md` lists LGBM Native **0.6598** / Target
  **0.6626**. This study is GLM/HGBT only and does not touch LGBM native-cat handling, so
  the discrepancy is **carried forward as a knowledge-base inconsistency to reconcile in a
  future LGBM study**, not adjudicated here.

## ⑦ What to try next

In priority order, for a follow-up LR/pricing study on this data:

1. **Elastic-net on the spline basis.** The E5 design matrix (quantile-knot splines +
   interactions) is wide; an `ElasticNet`/`saga` L1+L2 penalty could prune redundant basis
   columns and push past the 0.651707 ceiling without hand-selection — directly tests
   whether E5's ceiling is capacity or overfit.
2. **Target-encoding (with smoothing) for LR.** `glm-pricing.md`/`encoder-comparison.md`
   put smoothed target within ~0.002 of OHE and *better* for high-cardinality `region_code`
   (C22, ~41 val rows). Worth an A/B vs E1's OHE specifically on the high-cardinality cols.
3. **Monotone-constrained HGBT.** The campaign's strongest single model was
   LGBM with `monotone_constraints_method="advanced"` (best-practices #2). Porting monotone
   constraints onto the E6 HGBT tests whether the +0.0014 sweep gain compounds with
   actuarially-signed monotonicity — and yields a *filable* tree.
4. **TabPFN v2 zero-shot.** At 58,592 rows this dataset now sits inside TabPFN v2.5's
   ≤50k→scaling envelope (`knowledge/insights-and-framework.md`: Hollmann et al. 2025,
   Nature). A zero-shot pass is a cheap, high-information probe of whether a tabular
   foundation model beats the tuned GBDT (E6) with no tuning at all.
5. **Graduate to studies 01/02.** This quickstart's job (framework onboarding + split
   identity + calibration doctrine) is done; the open methodological questions move to
   `studies/01-dae-claims` (representation learning) and `studies/02-rqls-pv-severity`
   (severity / regression), where the anchors validated here become the baselines.
