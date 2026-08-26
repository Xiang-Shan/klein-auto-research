---
type: findings
domain: "statistics-history"
status: final
concepts:
  [
    fisher-1936,
    linear-discriminant-analysis,
    brier-score,
    split-lottery-floor,
    actionability-threshold,
    positive-control,
    sealed-confirmation,
    protocol-level-estimand,
    provenance-diff,
    duplicate-ruling,
    wrong-pair-comparison,
  ]
related:
  [
    study.yaml,
    program.md,
    scouting_ledger.md,
    data_card.md,
    method_card.md,
    results.tsv,
    aux_metrics.tsv,
    sweeps/split_lottery.sidecar.tsv,
    sweeps/kseed_floor.sidecar.tsv,
  ]
---

# Findings — 07-iris-90years

> SYNTHESIZE output. Claim IDs are stable (`07-iris-90years#C<n>`) and are never
> renumbered. Every delta is stated in the units of the track metric (`val_brier`,
> lower is better) **and** as a multiple of the one measured floor that governs every
> comparison here. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`.
>
> **What this study is.** A prospectively locked, sealed confirmation run after
> documented scouting (`scouting_ledger.md`, committed before the CONSULT gate). The
> 2026-08-24 design panel measured this same dataset and adaptively shaped the metric,
> the candidate set, the floor recipe, the twin ruling and both narratives. The fresh
> split seed 20260828 buys exactly one thing, stated no wider: **this partition — and
> therefore these specific 20 sealed rows — was never scored during scouting.**
>
> **Claims discipline (binding, `study.yaml:claims_discipline`).** Every headline below
> is a **protocol-level decision claim**: under this contract, this dataset, this
> declared split and this δ, challenger X did or did not produce an improvement of at
> least δ over the 1936 anchor. Sanctioned vocabulary only — "no keep earned", "did not
> improve by ≥ δ", "worse by X on the declared split". "Did not clear the floor" is
> never translated into a statement of equality.
>
> **The one floor this study measured** (cite, never re-derive):
>
> | Floor | Value | Governs |
> |---|---|---|
> | k-seed fit-noise sweep (protocol-prescribed, ran first) | **std exactly 0.0** over 5 seeds | nothing — recording 0 IS the finding: LDA is closed form, so a fit-noise floor is degenerate here and a zero floor would let any difference count as a keep (`sweep_kseed_floor.log`, `sweeps/kseed_floor.sidecar.tsv`) |
> | split-lottery floor, k = 20 group-aware re-draws of the 80 non-sealed rows | anchor development Brier mean **0.0187138**, std **0.0163144**, range **0.0499969** | **δ = `minimum_delta` = 0.033** — 2×std, ceiling to 3 dp. klein's protocol default `max(2·std, range/2)` = **0.0326288**, which does **not** exceed the registered value, so the pre-registered escalation rule left the floor where it was: no raise (`sweep_split_lottery.log`, `sweeps/split_lottery.sidecar.tsv`) |
>
> δ is an **actionability threshold** — "the incumbent's own score wobbles this much when
> only the split changes", conditional on these 100 flowers. It is not a confidence
> interval, not a significance test, and not a statement about population sampling.
>
> **Confirmation status.** One track, one seal, spent: `study_state.json`
> `final_holdout_access.primary.count = 1`, at **E0009** (`evaluation_kind:
> final_test`, `incumbent: E0001`). The seal confirms the **incumbent's LEVEL** only.
> The ladder gaps are **exploratory by construction** — the six losing families never
> receive a sealed value, and the contract pre-registered that they would not
> (`study.yaml:phases.confirmation`, `program.md` § Sealed look).
>
> **The ladder, declared split (seed 20260828, development n = 20 at 10/10):**
>
> | Exp | Family | Registered role | `val_brier` | Δ vs anchor | ×δ | Disposition |
> |---|---|---|---|---|---|---|
> | E0001 | `anchor_lda4` | Fisher 1936 LDA, four measurements | **0.026744** | — (frontier) | — | keep |
> | E0002 | — | registered crash rung | NA | — | — | **crash**, exit 1 |
> | E0003 | `logit` | logistic regression, Berkson 1944 / Cox 1958 | 0.059078 | **+0.032334** | 0.98× | discard |
> | E0004 | `knn7` | kNN k=7 distance-weighted, Fix–Hodges 1951 / Cover–Hart 1967 | 0.045403 | **+0.018659** | 0.57× | discard |
> | E0005 | `svm_rbf` | SVM-RBF, Cortes–Vapnik 1995 | 0.056963 | **+0.030219** | 0.92× | discard |
> | E0006 | `hgbt` | HistGradientBoosting sized for n≈60, Friedman 2001 / sklearn 2019 | 0.099975 | **+0.073231** | **2.22×** | discard |
> | E0007 | `lda_petal` | RQ2 ablation — petal measurements only | 0.069452 | **+0.042708** | **1.29×** | discard |
> | E0008 | `lda_sepal` | RQ3 positive control — sepal measurements only | 0.168936 | **+0.142192** | **4.31×** | discard |
> | E0009 | `anchor_lda4` | sealed one-look, 20 sealed rows at base rate 7/13 | **0.055198** | +0.028454 vs development | 0.86× | discard **by design** (sealed evidence never enters the adaptive frontier) |
>
> Source: `results.tsv`, `aux_metrics.tsv`, `runs/E0001..E0009/manifest.json`. Every
> number in this document traces to those files, to `sweeps/*.sidecar.tsv`, to the two
> sweep logs, or to `study.yaml` / the two gate cards — with a single flagged exception
> in ⑥ (an external changelog citation, marked as such).

## ① Research-question verdicts

| Claim | RQ | Track | Verdict | Evidence level | Evidence (exp IDs) | Metric delta + uncertainty |
|---|---|---|---|---|---|---|
| **[C1]** | RQ1 — do any of the four pre-registered post-1936 challengers earn a `keep` against the 1936 anchor, i.e. improve `val_brier` by ≥ δ on the declared split? | primary | **answered NO — no keep earned.** The registered prior is confirmed | **exploratory** (development ladder; no challenger has a sealed value, by contract) | E0003, E0004, E0005, E0006 vs E0001; `results.tsv` | Not one of the four improved by ≥ δ = 0.033. All four were **worse** on the declared split, in ladder order: logit **+0.032334** (0.98×δ), kNN-7 **+0.018659** (0.57×δ), SVM-RBF **+0.030219** (0.92×δ), HGBT **+0.073231** (**2.22×δ**, i.e. worse by more than twice the floor and therefore a degradation the instrument resolves). Uncertainty, from the same 20 lottery draws that produced δ: mean paired Δ vs the anchor is +0.026693 (logit), +0.016746 (kNN-7), +0.017491 (SVM-RBF), +0.030650 (HGBT), and **no family improved by ≥ δ in more than 1 of 20 draws** (see ③.3). Sanctioned reading: **the incumbent stands by default, not by victory** |
| **[C2]** | RQ2 — is petal-only LDA within δ of the four-measurement LDA on `val_brier`? | primary | **answered NO on the declared split. The registered prior is REFUTED — and that falsification is this RQ's honest headline** | **exploratory** | E0007 vs E0001; `sweeps/split_lottery.sidecar.tsv` | **Both pre-registered quantities, reported together per `study.yaml:noise_floor_protocol.verdict_quantity`.** (i) **Declared split — the quantity the ledger judges:** dropping both sepal measurements degrades `val_brier` by **+0.042708 = 1.29×δ**, which is *outside* the floor. The prior said "degradation < δ"; it is not. (ii) **Lottery spread — the quantity the chart shows:** across the 20 group-aware re-draws the mean paired delta is **+0.023445 = 0.71×δ**, with std 0.024051, min −0.037162, max +0.065156, and **13 of 20 draws within ±δ**. The two quantities disagree, the pre-registered rule says the declared-split number decides, and so the verdict is refutation. Stated in the only form the estimand licenses: **petal-only LDA was worse by 1.29×δ on the declared split; across 20 re-draws its degradation sat inside ±δ in 13 of them** |
| **[C3]** | RQ3 — the falsifiable **positive control**: is sepal-only LDA worse than the anchor by at least 2×δ? | primary | **answered YES, resoundingly. The registered prior is confirmed and the instrument is alive** | **exploratory** | E0008 vs E0001; `sweeps/split_lottery.sidecar.tsv` | Degradation **+0.142192 = 4.31×δ**, against a pre-registered bar of ≥ 2×δ = 0.066 — clearing it by a factor of 2.15. Robust across the lottery: mean paired Δ **+0.207387 = 6.28×δ**, min **+0.142192**, and **20 of 20 draws worse than the anchor by more than δ**. The pre-registered failure branch ("if sepal-only does not clear the floor, the instrument cannot resolve differences of this size at n = 100 and every within-floor claim is downgraded") **does not fire.** Corroborating auxiliaries, never a verdict input: `val_auc` falls 1.0 → 0.855 and predicted-probability spread collapses (`min_proba_std` 0.482 → 0.231, `proba_range` 1.000 → 0.818), so this is a real loss of separation, not a calibration artifact |
| **[C4]** | The sealed question: does the incumbent's **level** hold on the 20 sealed rows? | primary | **held — inside the registered ±2δ band** | **confirmed** (the track's single sealed access, spent at E0009) | E0009; `study_state.json`; `runs/E0009/manifest.json` | Sealed `val_brier` **0.055198** against the development **0.026744**: a move of **+0.028454 = 0.86×δ**, well inside the pre-registered ±2δ = ±0.066 band. Read against the **sealed base rate 7/13**, not the development 10/10 — a group split is not stratified and the data card documents this (WARN 4). For scale: a constant predictor at the sealed base rate scores 0.2275 (arithmetic from 7/20; the mechanized constant-chance probe on the development partition scored 0.2525, `data_card.md` leakage row 4), so the sealed level sits at roughly a quarter of chance. Ranking on the sealed rows is at ceiling — `val_auc` 1.0, `val_pr_auc` 1.0 (`aux_metrics.tsv` records 0.9999999999999998, one float64 ULP), `val_f1_at_best` 1.0, `val_lift_top10` 2.857 = 20/7, the maximum attainable at a 35 % base rate. **Scope, exactly:** this confirms the incumbent's LEVEL. It confirms nothing about the six gaps below it |

**Evidence-level note.** Only **[C4]** is `confirmed`; it is the one statement the single
seal was spent on. **[C1]**, **[C2]** and **[C3]** are development comparisons and stay
`exploratory` **by construction**, not by oversight: the contract registered one track and
one seal, and the losing families were never going to receive a sealed value
(`study.yaml:phases.confirmation`; `program.md` § Sealed look).

**Power limitation, pre-registered and adopted rather than discovered.** Population-level
equivalence is not claimable at n = 100 with a 20-row development partition: the
design-phase paired interval analysis produced intervals **wider than the floor band for
all six comparisons** (`scouting_ledger.md` S12, `study.yaml:estimand.not_claimed`, adopted
by the 2026-08-24 decision recorded in `program.md`). The comparison family size is **6**,
and this document states it rather than correcting for it — family honesty here means
declaring the family, because a family-wise multiplier would answer a population estimand
this study does not register.

## ② Predictions to falsify (filled)

The seven levers registered in `study.yaml:predictions_to_falsify`. The `source:` tag on
each is load-bearing — ⑥ scores only the `uninformed` and `derived` rows.

| # | Lever | Predicted delta | Observed delta | Verdict | Evidence |
|---|---|---|---|---|---|
| 1 | the four pre-registered challengers vs the LDA anchor (RQ1) — *(source: scouting-2026-08-24)* | no challenger improves by ≥ δ → four DISCARDs, zero keeps | Four discards, zero keeps. Deltas **+0.032334 / +0.018659 / +0.030219 / +0.073231** (0.98× / 0.57× / 0.92× / 2.22×δ), every one in the *worse* direction | **held** | E0003, E0004, E0005, E0006 vs E0001 |
| 2 | petal-only LDA, sepal measurements dropped (RQ2) — *(source: scouting-2026-08-24)* | degradation **< δ** (inside the floor) | **+0.042708 = 1.29×δ** on the declared split — outside the floor. Lottery mean +0.023445 = 0.71×δ, inside it, in 13/20 draws | **FALSIFIED on the declared split** — the verdict quantity the contract nominated | E0007 vs E0001; `sweeps/split_lottery.sidecar.tsv` |
| 3 | sepal-only LDA, petal measurements dropped (RQ3 control) — *(source: scouting-2026-08-24)* | degradation **≥ 2×δ**; a smaller degradation falsifies the instrument's resolution | **+0.142192 = 4.31×δ** — 2.15× the bar; lottery mean 6.28×δ, 20/20 draws beyond δ | **held** | E0008 vs E0001 |
| 4 | species column handed to the binary evaluator (E0002, registered crash) — *(source: derived — `kleinlib.eval` source, not a data measurement)* | non-zero exit; `kleinlib.eval` raises "binary classification evaluate() requires target labels exactly {0, 1}" → disposition `crash`, primary metric NA | Exit code **1**, disposition **crash**, `metrics: {}`. `runs/E0002/run.log` ends: `ValueError: binary classification evaluate() requires target labels exactly {0, 1}; got [1, 2]` — the registered sentence, verbatim, from `kleinlib/eval.py:337` | **held — with one honest correction to the registered wording** (below) | E0002; `runs/E0002/run.log`, `runs/E0002/manifest.json` |
| 5 | k-seed sweep of the anchor config, seed varied and nothing else (Phase 0) — *(source: derived — closed-form estimator, not a data measurement)* | std **exactly 0.0** across all seeds; the fit-noise floor is degenerate here and is documented, not skipped | 5 seeds, five identical values **0.026744199714**, mean 0.0267441997141, **std 0, range 0**. The log records: "RESULT: DEGENERATE — std is exactly 0, as registered" and refuses to let the zero be pasted into the contract | **held** | `sweeps/kseed_floor.sidecar.tsv`, `sweep_kseed_floor.log` |
| 6 | sealed 20-row confirmation of the incumbent (E0009) — *(source: uninformed — this partition and these sealed rows were never scored)* | sealed `val_brier` within **±2δ** of the development value; the LEVEL is confirmed, not the ladder gap | **+0.028454 = 0.86×δ**, inside ±0.066. Level confirmed; gaps left exploratory, as registered | **held** | E0009 vs E0001 |
| 7 | magnitude of `minimum_delta` under the group-aware split-lottery recipe (Phase 0) — *(source: uninformed — this recipe's scope was never run)* | the measured floor lands in **0.01–0.10** `val_brier` units | **0.033** — inside the registered interval, and near its geometric middle | **held** | `sweep_split_lottery.log`, `sweeps/split_lottery.sidecar.tsv` |

**Score: 6 held, 1 falsified.** The single falsification is lever 2 — the RQ2 prior — and
it is the one prior with a *magnitude* in it. That pattern is worth naming: the priors
predicted **what the loop would decide** (four discards, a degenerate seed floor, a crash
message, a floor of the right order of magnitude, a sealed level that does not move)
correctly in six of six cases, and the one prior that had to be right about **how much**
came out wrong.

**Honest correction to lever 4's registered wording.** `study.yaml:phases` and `program.md`
describe E0002 as handing over "the 3-class species target". The prepared artifact's
`species` column carries sklearn's 3-class *coding scheme* but only **two labels are
present** — value set exactly `{1, 2}`, setosa (0) having been dropped by `prepare.py`
(`data_card.md` profile row; the assertion is in `prepare.py`). The **mechanism** predicted
is exactly the mechanism observed: the evaluator refuses any target that is not exactly
`{0, 1}`, and the traceback prints `got [1, 2]`. The prediction held; the phase text's
"3-class" is a description of the coding scheme, not of the labels in the frame, and this
document says so rather than letting the two readings sit unreconciled.

## ③ Surprises and why

1. **The RQ2 falsification, and the mechanism behind it: a one-split ablation verdict is a
   draw from a distribution wider than the floor that judges it.** **[C5]** *(exploratory;
   evidence: E0007, E0001, `sweeps/split_lottery.sidecar.tsv`)* Petal-only LDA's paired
   delta against the anchor ranges from **−0.037162 to +0.065156** across the 20 group-aware
   re-draws — a span of **0.102318 ≈ 3.1×δ** — with a mean of +0.023445 (0.71×δ). The
   declared split landed at **+0.042708 (1.29×δ)**, in the upper part of that span, and the
   contract's pre-registered verdict quantity is the declared-split number. So a prior that
   was *correct about the central tendency* is recorded as **refuted**, because the protocol
   judges a single draw. **This is not a defect in the protocol; it is the protocol working
   as designed and being expensive about it.** The generalizable statement: when a family's
   paired-delta spread is of the same order as the floor, the split you declared decides the
   verdict, and pre-registering *which* quantity decides is the only thing that stops the
   verdict being chosen after the fact. The study reports both numbers precisely so the
   ledger and the chart agree by construction rather than by narration.

2. **The declared split is draw 1 of the lottery — by seed arithmetic, and we record it
   rather than let it look like a coincidence.** **[C6]** *(exploratory; evidence:
   `sweeps/split_lottery.sidecar.tsv` draw 1 vs `results.tsv` E0001–E0008,
   `kleinlib/data.py:288-297`, `sweeps/split_lottery.py:73-78,132-140`)* All seven of draw
   1's values reproduce the declared-split ladder to the last recorded digit —
   0.026744 / 0.059078 / 0.045403 / 0.056963 / 0.099975 / 0.069452 / 0.168936. The reason is
   mechanical: `kleinlib.data.three_way_split(strategy="group")` splits the sealed partition
   off with `random_state=seed` and then splits development off the remainder with
   `random_state=seed + 1` at `development_size/(1 − test_size) = 0.25`; the lottery's draw
   seeds are `DRAW_SEED_BASE + draw` with base = the declared seed 20260828, so draw 1 uses
   `random_state = 20260829` on the same 80 rows at the same 0.25 — **the identical
   partition**. Two consequences, both recorded rather than smoothed: (i) the declared split
   is a **member** of the k = 20 ensemble whose spread defines δ, a mild self-reference that
   an ensemble of 20 makes small but does not remove; (ii) the anchor's declared-split Brier
   **0.026744 ranks 13th of 20** (mean 0.0187138, median 0.01825), so the study's own
   incumbent was judged on a draw somewhat harder than the ensemble's middle. A follow-up
   should draw the lottery from seeds disjoint from `seed + 1` (⑦.1).

3. **On one draw of twenty, two of the six losers would have earned a keep.** **[C7]**
   *(exploratory; evidence: `sweeps/split_lottery.sidecar.tsv` draw 15)* Draw 15 is the
   second-hardest draw for the anchor (development Brier 0.043057 against a mean of
   0.0187138). On that draw **HGBT beat the anchor by 0.040245 = 1.22×δ** and **petal-only
   LDA beat it by 0.037162 = 1.13×δ** — both clearing the keep bar in the improving
   direction. On the declared split those same two families were the ladder's worst
   challenger (**+2.22×δ**) and the RQ2 falsifier (**+1.29×δ**). Across all 20 draws and all
   six families that is **2 keep-sized improvements out of 120 paired comparisons**, both in
   the same draw. **Mechanism:** with 20 development rows the Brier score is an average over
   20 terms, and a single confidently-wrong row moves it by up to 0.05 — larger than δ. Which
   flowers land in the development partition therefore selects the winner as strongly as
   which method is fitted. This is the study's moral, measured rather than asserted: a
   numerical #1 on one split is not a signable claim. Note the discipline: these are
   **measurement-sweep** values from a sidecar that promotes no winner and writes no ledger
   row (`references/sweep-rules.md` carve-out) — they are evidence about the instrument,
   never about a challenger's standing.

4. **The registered lottery seed scheme crashed all 140 trials on a numeric-domain
   violation, and the crash is committed.** **[C8]** *(exploratory; evidence:
   `sweeps/split_lottery.sidecar.crashed-seed-overflow.tsv`, `sweeps/split_lottery.py:73-78`)*
   `study.yaml:noise_floor_protocol.draw` registered draw seeds `20260828001 .. 20260828020`.
   numpy and sklearn require a seed **< 2³²**, and 20260828001 is roughly 4.7× that bound, so
   every one of the 140 (draw × family) trials failed with
   `ValueError: Seed must be between 0 and 2**32 - 1` — a full sidecar of `status=crash` rows,
   preserved beside the good one instead of being deleted. The fix was **mechanical and
   committed before any floor was stated**: `base + draw` (20260829..20260848) rather than
   `base × 1000 + draw`, documented in the script's own header. Nothing about the floor's
   value was chosen after seeing data. Recorded because it is the kind of pre-registration
   defect that a study which quietly re-ran would never have to disclose: **a registered seed
   scheme is a piece of code and can be wrong in the ordinary way code is wrong.**

5. **The "Fisher's printed coefficients don't match ours" discrepancy was a wrong-pair
   comparison, and the correction is digit-exact.** **[C9]** *(exploratory; evidence:
   `method_card.md` §5 RESOLVED block, `method_check.py` check 3, `events.jsonl` seq 35)*
   The 2026-08-24 scouting recorded cosines of **0.981 / 0.956** between our
   versicolor/virginica direction and "Fisher's printed discriminant" (`scouting_ledger.md`
   S8), and the method card carried that as a discrepancy — with a bounded, numerically
   honest investigation that eliminated the two obvious explanations (total vs within-class
   scatter: cosine 1.000000000000000, guaranteed by Sherman–Morrison since S_B is rank 1
   along μ₁−μ₀; covariance vs sum-of-squares scaling: cosine 1.000000000000000) and showed
   the third was too small by orders of magnitude (1936 desk rounding at two significant
   figures moves the direction by 1 − cos 2.3e-04, ~80× less than the smaller recorded gap).
   That investigation's conclusion — "whatever produces Fisher's printed numbers is a
   *different reported quantity*" — was right. The 2026-08-25 verification against the full
   1936 text identifies it: **Fisher prints no versicolor-versus-virginica discriminant at
   all.** His worked §II compound is *setosa vs versicolor*,
   `X = x₁ + 5.9037x₂ − 7.1299x₃ − 10.1036x₄` (p. 182); the only other printed vector is
   §VI's three-species 4:1:−5 allopolyploidy contrast. Run on **Fisher's own problem**, the
   ten-line from-scratch discriminant returns **(1, 5.90380, −7.12998, −10.10366)** —
   every printed digit, cosine **1.000000**. The 0.981-vs-0.956 spread was an S_W-convention
   artifact **of the wrong-pair comparison**, not a finding about conventions.
   **Lesson, and it is the cheap one to miss:** a reproduction gap is a claim about two
   objects, and the first thing to verify is that they are the same object. Three layers now
   agree — the method (cosine ≥ 1 − 1e-12 across `svd`/`eigen`/`lsqr`), the measurement table
   (150×4 printed Table I vs sklearn: **zero mismatches**, one OCR artifact in the scan
   identified as such), and the printed discriminant itself.

6. **The twin rows are original to the 1936 print.** **[C10]** *(exploratory; evidence:
   `data_card.md` PROVENANCE RESOLVED block, `events.jsonl` seq 36, `reference/PROVENANCE.md`)*
   Hard-pair rows 51 and 92 — full-table rows **102 and 143**, both virginica — carry
   identical measurements **(5.8, 2.7, 5.1, 1.9)** and are the only duplicated row-content in
   the hard pair (asserted in `prepare.py`). The 2026-08-25 check against the full 1936 scan
   finds the same pair printed **twice in Fisher's own Table I** — printed virginica rows
   **2 and 43**, mapping exactly to sklearn rows 102/143 (print order = sklearn order; the
   full table diffs clean). So the duplication is **original to the 1936 publication**, not a
   digitization artifact and not an error introduced by UCI or scikit-learn. **Scope the
   claim exactly as the data card does:** neither Bezdek et al. (1999) nor the UCI page
   mentions this duplication **in the forensic sources we checked** — never "nobody has ever
   noticed". Duplicate record entry versus two genuinely identical flowers remains
   **undecidable** at 0.1 cm resolution, which is why the ruling was to **group, not delete**:
   both rows share `group_id = twins102-143` and always travel into the same partition, so
   the leakage mechanism is removed regardless of which explanation is true, n stays 100, and
   the clean-room audit passes without an override. The counterfactual measured at the data
   gate is why this mattered: under a *stratified* split the twins land in different
   partitions in **16 of 20 seeds** — the leak would have been the normal case.

7. **On the sealed rows the ranking gauges pegged and only the proper score moved.**
   **[C11]** *(confirmed for the incumbent's level; evidence: E0001, E0009, `aux_metrics.tsv`)*
   Sealed `val_auc` 1.0, `val_pr_auc` 1.0, `val_f1_at_best` 1.0, `val_lift_top10` 2.857 —
   which is 20/7, the **maximum attainable** at a 7/13 base rate, exactly as the development
   partition's 2.0 is the maximum at 10/10. Both ranking gauges were at full scale on both
   partitions. Meanwhile `val_brier` moved **0.026744 → 0.055198** and `val_logloss`
   0.072157 → 0.238630. Had this study followed the reflex and scored `val_auc`, the sealed
   look would have read "1.000 → 1.000" and there would have been nothing to confirm and
   nothing to falsify. The metric choice was scouting-informed (`scouting_ledger.md` A1, the
   study's single largest adaptive influence) and is therefore excluded from the prior
   scorecard — but the sealed partition, which scouting never scored, is where the choice
   paid.

8. **Fisher declined our question in print, in 1936.** *(evidence: `method_card.md` §5,
   verbatim from §VI)* "there is some overlap of the distributions of I. virginica and
   I. versicolor, so that a certain diagnosis of these two species could not be based solely
   on these four measurements of a single flower taken on a plant growing wild." The 90-year
   ladder asks a question the source of the data explicitly refused to answer — and the
   answer, ninety years and four method-generations later, is that nothing on the ladder
   improved on the 1936 method by an amount worth acting on.

## ④ Practical advice

1. **[C12]** **Measure the floor that will judge your comparison before you run the first
   challenger — and if your estimator is closed form, measure the right kind of noise.**
   *(evidence: E0001, `sweeps/kseed_floor.sidecar.tsv`, `sweep_split_lottery.log`)* The
   protocol-prescribed k-seed fit-noise sweep returned **std exactly 0** here, because LDA
   has no optimizer, no subsampling and no initialization for a seed to perturb — five seeds,
   five identical values to twelve decimals. Pasting that zero into the contract would have
   made **every** difference a keep. The honest floor for a deterministic estimator is
   **split** noise: 20 group-aware re-draws of the non-sealed rows gave an anchor Brier std
   of 0.0163144 and δ = **0.033**, which is 1.2× the anchor's *own score*. Run the degenerate
   sweep anyway and commit its output — the zero is the finding that tells you which floor
   you actually need.

2. **[C13]** **Pre-register which quantity decides — the declared-split delta or the lottery
   central tendency — and then report both.** *(evidence: E0007, `sweeps/split_lottery.sidecar.tsv`,
   `study.yaml:noise_floor_protocol.verdict_quantity`)* RQ2 is the worked example: 1.29×δ on
   the declared split, 0.71×δ as a lottery mean, and 13 of 20 draws inside ±δ. Both numbers
   are true; they support opposite verdicts; the only thing that keeps the study honest is
   that the contract named the declared-split delta **before** the measurement. If you report
   only the one that agrees with your prior you have not made a measurement, you have made a
   choice — and nobody downstream can tell which.

3. **[C14]** **Put a positive control on the ladder, sized to fail.** *(evidence: E0008,
   4.31×δ; contrast E0003–E0007)* A study whose result is "no keep earned" is
   indistinguishable from a study whose instrument is dead — unless something on the same
   ladder, scored the same way, is *supposed* to break and does. Sepal-only LDA degraded by
   **4.31×δ** against a pre-registered bar of 2×δ, and the failure branch was written down in
   advance ("if the control does not clear the floor, every within-floor claim in this study
   is downgraded and that becomes the headline"). Cost: one run, 0.0098 s of fit-and-score
   time. There is no cheaper insurance in an experimental protocol.

4. **[C15]** **At small n, score a proper score and keep the ranking metrics as auxiliaries.**
   *(evidence: E0001, E0009, `aux_metrics.tsv`; `study.yaml` metric-choice rationale)* On 20
   rows, AUC lives on a 101-point lattice and pegged at 1.000 on both the development and the
   sealed partition, `val_pr_auc` and `val_f1_at_best` pegged with it, and top-decile lift sat
   at its arithmetic ceiling on both (2.0 at 10/10, 2.857 = 20/7 at 7/13). Only `val_brier`
   moved. For pricing work the same asymmetry holds for a different reason — a rate model that
   ranks perfectly and is 2× off in level is unusable — so record ranking, but decide on
   calibration.

5. **[C16]** **Size the modern method for the sample, expect it to lose anyway at n ≈ 60, and
   count what it costs.** *(evidence: E0006, `aux_metrics.tsv`)* HGBT was sized for the
   sample — `min_samples_leaf=5`, `max_leaf_nodes=4`, `early_stopping=False`, chosen after
   the scouting saw it memorize a 60-row training partition unsized (`scouting_ledger.md` A3)
   — and it still finished **worst of the four challengers** at +0.073231 (**2.22×δ**), with
   the ladder's worst `val_logloss` (0.9038) and a best threshold of **0.01**, i.e. badly
   miscalibrated. It also cost **0.126448 s** of fit-and-score against the anchor's
   **0.008361 s** — **15.1× the compute for a materially worse score**. In this regime the
   1936 method's advantage is not cleverness but the absence of ways to be wrong: a closed
   form has no fitting variance to spend.

6. **[C17]** **Run the provenance diff before the first model, and rule undecidable
   duplicates by grouping rather than deletion.** *(evidence: `data_card.md`,
   `reference/PROVENANCE.md`, `prepare.py`)* The UCI copy still ships the documented rows
   35/38 errata — **three cells**, six numbers across the two sources — and both affected rows
   are *setosa*, which `prepare.py` drops, so the errata **provably cannot touch** a single
   row of this study. That sentence is only available because the diff ran *before* the
   anchor, against committed bytes (`reference/uci_iris.data`,
   sha256 `6f608b7…6656c0`) rather than a live fetch. Same discipline on the duplicate: the
   evidence could not decide between duplicate entry and two identical flowers, so the ruling
   removed the **mechanism** (one `group_id`, always co-located) instead of asserting the
   explanation. Deleting a row would have required a claim the evidence does not support.

7. **[C18]** **Keep a registered crash rung on the ladder.** *(evidence: E0002,
   `runs/E0002/run.log`)* One transaction, deliberately handed a target the evaluator must
   refuse, produced `exit 1`, `disposition: crash`, `metrics: {}`, and the exact registered
   sentence `requires target labels exactly {0, 1}; got [1, 2]`. It costs a run and it proves
   the guard is load-bearing rather than decorative — and it is the reason the frame's
   perfect-proxy `species` column could be retained on purpose, documented as a WARN with an
   explicit mitigation (feature columns named literally in `families.py`; no code path passes
   the frame wholesale), instead of being removed and the guard left untested.

8. **[C19]** **Register seed schemes inside the numeric domain of the library that will
   consume them.** *(evidence: `sweeps/split_lottery.sidecar.crashed-seed-overflow.tsv`)*
   `base × 1000 + draw` on a date-shaped seed overflows numpy's 2³² bound and takes down
   **every** trial in the sweep. Prefer `base + draw`, or draw seeds from a
   `SeedSequence`/`spawn` and record them. And when a pre-registered detail has to change,
   change it **before** any statistic is stated, commit the crashed evidence beside the good
   run, and say so in the script header — which is what makes "we fixed a seed" verifiable
   rather than merely asserted.

## ⑤ Business / actuarial value implications

**What this study is worth, translated into decisions rather than metric points.**

1. **The replace-the-incumbent decision has a floor, and most challengers do not reach it.**
   The pricing analogue of this ladder is a rate model in production and four candidate
   replacements. Here the incumbent's own score wobbles by **δ = 0.033** — larger than its
   *entire score* on the declared split (0.026744) — purely from which rows landed in the
   evaluation partition. Any candidate whose measured improvement is smaller than that number
   is not a business case; it is a re-draw. On this ladder **zero of four** cleared it
   ([C1]), and the honest sentence for a rate-review committee is the sanctioned one: **no
   keep earned; the incumbent stands by default, not by victory.**

2. **The floor is cheap enough that there is no excuse for not having one.** The entire
   metrology cost **2.362 s** — 140 lottery trials (2.351 s) plus 5 k-seed trials (0.008 s)
   plus the 140 crashed trials of the overflow attempt (0.003 s). The whole study, all nine
   ledger runs end to end including interpreter startup, cost **6.839 s** of process wall time
   (`runs/E####/manifest.json`, 0.715–0.897 s per run), of which the evaluators' own
   fit-and-score time is **0.191 s** (HGBT's 0.126 s is two thirds of it). Measured total,
   everything included: **≈ 9.2 s**. The `wall_seconds` guardrail of 30 s was never approached
   — the largest single measured fit-and-score was 0.42 % of the cap. On a real portfolio the
   lottery costs *k* refits, and it is the difference between "the challenger is better" and
   "the challenger is better than the noise".

3. **Calibration is the axis that moves; rank is the axis that flatters.** Every ranking
   gauge sat at its ceiling on both partitions ([C11], [C15]) while the proper score moved by
   0.86×δ from development to sealed. A pricing model chosen on Gini or lift alone can be
   swapped for another with an identical rank ordering and a materially different level —
   which is the difference between an adequate rate and an inadequate one at the same
   *relativities*.

4. **One sealed look, spent once, is a governance instrument.** `study_state.json` records
   `final_holdout_access.primary.count = 1`; the manifest records `evaluation_kind:
   final_test` and `incumbent: E0001`; the ledger carries E0009 as a **discard by design**
   so sealed evidence can never re-enter the adaptive frontier. That is the auditable form of
   "we looked once, and we said in advance what looking would mean" — the property a filing
   or a model-validation review is actually asking about when it asks whether a holdout was
   respected.

5. **Provenance work belongs before the model, and it pays in sentences you can sign.**
   Because the diff and the duplicate ruling ran at the data gate, this study can state that
   the known errata **cannot** affect its rows ([C17]) and that its only duplicated
   measurements are **original to the 1936 source** ([C10]) — and the twin ruling removed a
   leakage mechanism that a stratified split would have triggered in 16 of 20 seeds. Data
   lineage discovered after a model is a rework; discovered before, it is a two-line
   limitation and a defensible file.

6. **The uncomfortable transferable result: at n ≈ 60 training rows, a closed-form 1936
   method was not improved upon by ninety years of method development** ([C1], [C16]) — and
   the study can say that *only* because it also proved its instrument could see a real
   degradation when one existed ([C3]). Small-portfolio and thin-segment pricing lives in
   exactly this regime.

## ⑥ Literature tie-back

- **Fisher, R. A. (1936), "The use of multiple measurements in taxonomic problems",
  *Annals of Eugenics* 7(2):179–188 — VERIFIED 2026-08-25** (DOI
  10.1111/j.1469-1809.1936.tb02137.x; open access via Rothamsted, eprint 33079;
  `method_card.md` §6, `events.jsonl` seq 35). Three layers of agreement, each measured:
  the **method** (from-scratch `S_W⁻¹(μ₁−μ₀)` vs sklearn, cosine ≥ 1 − 1e-12 on `svd`,
  `eigen` and `lsqr`; residual for `svd` is 1.11e-16, one ULP), the **measurements** (group
  means to 3 dp; the full 150×4 printed Table I vs sklearn: zero mismatches), and the
  **printed discriminant** — reproduced digit-exact **once compared to the right problem**
  ([C9]). Fisher's §VI sentence about the overlap of virginica and versicolor is the
  study's framing fact: he declined this pair in print.
- **Bezdek, Keller, Krishnapuram, Kuncheva & Pal (1999), "Will the real iris data please
  stand up?", *IEEE Transactions on Fuzzy Systems* 7(3):368–369 — VERIFIED 2026-08-25**
  (`events.jsonl` seq 35). The canonical iris-forensics reference, and the reason the twin
  claim is scoped the way it is: it does not mention the 102/143 duplication, and neither
  does the UCI page — **in the sources we checked** ([C10]).
- **The two errata sources agree with each other and with our diff.** UCI `iris.names`
  (header `Updated Sept 21 by C.Blake - Added discrepency information`, crediting Steve
  Chadwick) names rows 35 and 38; scikit-learn's `load_iris().DESCR` states its copy follows
  Fisher's paper "but not as in the UCI Machine Learning Repository, which has two wrong data
  points"; our cell diff finds **exactly** those two rows, three cells, and nothing else.
  Both are setosa and outside the hard pair (`data_card.md`, `reference/PROVENANCE.md`).
  *Flagged for traceability:* the specific attribution of the fix to **scikit-learn v0.20
  (2018), changelog #11082** comes from the 2026-08-25 citations pass and is **not** recorded
  in any artifact under this study directory — it is reported here as an external citation,
  not as a measurement of ours.
- **Against the "modern methods win on tabular data" trend** (the Grinsztajn-style reading
  that boosted trees remain the default on tabular problems): **it does not transfer to this
  regime**, and the failure is not marginal. HGBT — sized for the sample, not left at
  defaults — finished last of the four challengers at **2.22×δ worse** than a 1936 closed
  form (E0006), with the ladder's worst logloss and a best threshold of 0.01. The mechanism
  the method card predicted in advance ("at n = 100 with a strong near-linear boundary, a
  method with no fitting variance is extremely hard to beat, not because it is clever but
  because everything else has more ways to be wrong") is the mechanism observed. That was
  written as a hypothesis the ladder would test, and the ladder tested it.

### Prior scorecard — and what this study is not allowed to count

The rule was fixed in advance (`scouting_ledger.md` §4, `study.yaml:predictions_to_falsify`):
**§⑥ scores only predictions tagged `uninformed` or `derived`.** The three
research-question priors are all tagged `(source: scouting-2026-08-24 (measured))` and are
**excluded by construction** — this study contributes **zero rows** to the uninformed-prior
tally from its RQs.

| Scored prediction | Source tag | Outcome |
|---|---|---|
| k-seed fit-noise std is **exactly 0** | derived (closed-form estimator) | **HELD** — 5 seeds, std 0, range 0 (`sweeps/kseed_floor.sidecar.tsv`) |
| E0002 crashes with "requires target labels exactly {0, 1}" | derived (`kleinlib.eval` source) | **HELD** — exit 1, message verbatim, `got [1, 2]` (E0002) |
| sealed `val_brier` within ±2δ of the development value | **uninformed** | **HELD** — +0.028454 = 0.86×δ (E0009) |
| the measured floor lands in 0.01–0.10 `val_brier` units | **uninformed** | **HELD** — 0.033 (`sweep_split_lottery.log`) |

**Score on scoreable priors: 4 / 4 held (2 derived, 2 uninformed).** Both `derived` priors
were statements about *code and closed-form mathematics*, which is why they were exact; both
`uninformed` priors were statements about *order of magnitude and direction*, which is the
only kind of unscouted prediction this design could honestly make.

**Disclosed-scouting confirmations — reported, never scored.** RQ1's prior (no keep earned)
and RQ3's prior (control degrades by ≥ 2×δ) came out as expected, and both were informed by
the 2026-08-24 panel probes S3 and S5. They are listed here as confirmations of a disclosed
design input, and they earn no scorecard row. **RQ2 is the exception, and it goes the other
way: the scouting-informed prior was WRONG on the declared split** — predicted degradation
< δ, measured **1.29×δ** (E0007). Having scouted the answer did not stop the prior from
being falsified, which is the most useful thing the ledger discipline produced: a prior
written with answers in context still failed, in public, at the one place it had to commit
to a magnitude.

**Promotion note.** Any line these findings put into `knowledge/` must carry its claim
citation — `(supports 07-iris-90years#C14)` and so on — so the statement stays greppable
back to the evidence that earned it.

## ⑦ What to try next

1. **A split-lottery variant whose draws are disjoint from the declared split, plus a
   stratified-within-group counterfactual.** Two defects meet here. (a) [C6]: the declared
   split *is* draw 1, because `three_way_split` uses `seed + 1` for its inner split and the
   lottery's base is the declared seed — so the ensemble that defines δ contains the split δ
   judges. Re-run with draw seeds drawn from a `SeedSequence` disjoint from `{seed, seed+1}`.
   (b) The adaptive-1 slate deferred candidate 6, the stratified-split counterfactual
   ("what the twins would have done"), to exactly this section. **Predictions to falsify:**
   δ moves by less than 0.005 under disjoint draw seeds (i.e. the self-reference is
   immaterial at k = 20, as [C6] argues but does not prove); and a stratified lottery gives a
   **smaller** anchor std than the group lottery, because co-locating the twins removes an
   easy pair from the development partition in the draws where they would have straddled it
   — which would make the group-aware floor the conservative choice, as intended.

2. **The falsified-RQ2 follow-up: petal-only LDA across k = 100 draws, with the verdict
   quantity pre-registered as the lottery mean.** This is the highest-information item,
   because it converts [C5] from an observation into a design. RQ2's declared-split delta
   (1.29×δ) and lottery mean (0.71×δ) disagree; k = 20 gives the mean a standard error of
   0.024051/√20 ≈ 0.0054, which is not tight enough to settle the question by itself. At
   k = 100 the same standard error falls to ≈ 0.0024. **Predictions to falsify:** the k = 100
   mean paired delta stays within ±0.008 of 0.023445 (0.71×δ), and the fraction of draws
   inside ±δ stays near 13/20 = 65 %. If it does, the sentence "petal-only degradation sits
   inside the floor **on average**, and outside it on the split we declared" is measurable and
   defensible — and RQ2 becomes a study about the verdict quantity rather than about petals.

3. **The ladder as a function of n.** Every claim here is bounded by n = 100 with 20
   development rows, and δ = 0.033 is a consequence of that. Refit the same seven families on
   nested subsamples (train 20 / 40 / 60, group-aware, same sealed rows frozen out) and
   measure δ at each size. **Prediction to falsify:** δ shrinks roughly as 1/√n, and the
   challenger that first clears it is **SVM-RBF, not HGBT** — SVM-RBF has the tightest paired
   spread in the lottery (std 0.012015, less than a third of HGBT's 0.040144) even though its
   declared-split delta was worse than kNN's. If instead HGBT crosses first, the "closed form
   has no fitting variance to spend" mechanism ([C16]) is weaker than the method card claims
   and the trees-win trend re-asserts itself sooner than n = 100 suggests.

4. **Publishing decision — pending, and gated on verification work not yet done.** [C10] (the
   1936-original duplication) and [C9] (the wrong-pair coefficient artifact) are the two
   findings with an audience beyond this repo, and both are currently scoped to "in the
   sources we checked". Before any note is drafted, three checks: read the Bezdek et al.
   (1999) full text rather than its verified bibliographic record; check Anderson (1935) and
   the later iris-forensics literature for any mention of the 102/143 pair; and confirm the
   printed-Table-I mapping against a second scan, since one OCR artifact was already
   identified in the first. If those hold, the honest framing is a short data-provenance note
   — **not** a claim of discovery — and it must carry the same scope qualifier this document
   uses. Until then the finding stays here, in the ledger, with its evidence attached.
