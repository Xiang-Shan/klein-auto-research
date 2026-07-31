---
type: findings
domain: "insurance"
status: final
concepts: [claim-frequency, poisson-deviance, glm, hgbt, lightgbm, catboost, monotone-constraints, surrogate-distillation, paired-bootstrap, sealed-test, translate-back]
related: [04-fremtpl2-frequency, 03-noisy-rosenbrock-dfo]
---

# Findings — 05-fremtpl2-gap-forensics

> SYNTHESIZE output. Claim IDs are stable (`05-fremtpl2-gap-forensics#C<n>`) and are
> never renumbered. Every delta is stated in the units of the metric
> (`val_poisson_deviance`, lower is better) AND as a multiple of the measured floor
> that governs that comparison. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`.
>
> **The floors this study measured** (cite, never re-derive):
>
> | Floor | Value | Governs |
> |---|---|---|
> | glm fit-seed std (k=5) | **exactly 0** | nothing — `PoissonRegressor` is deterministic; the degenerate value IS a finding |
> | gbdt fit-seed std (k=5) | 0.000210 | HGBT re-fit reproducibility |
> | glm paired-bootstrap SE (B=1000, CRN) | 0.000270 → `minimum_delta` **0.000539** | within-glm-track comparisons |
> | gbdt paired-bootstrap SE (B=1000, CRN) | 0.000287 → `minimum_delta` **0.000573** | within-gbdt-track comparisons |
> | **cross-track** paired-bootstrap SE (dev) | **0.000963** | the headline GLM↔GBDT gap on development |
> | **cross-track** paired-bootstrap SE (sealed) | **0.001028** | the headline gap on the sealed test |
>
> Sources: `sweeps/noise_floor_glm.sidecar.tsv`, `sweeps/noise_floor_gbdt.sidecar.tsv`,
> `sweeps/paired_floor.py`, `study.yaml`. The cross-track SE is an uncertainty band for
> the gap — it is **not** a `minimum_delta` and never gates a keep/discard.

## ① Research-question verdicts

| Claim | RQ | Track | Verdict | Evidence level | Evidence (exp IDs) | Metric delta + uncertainty |
|---|---|---|---|---|---|---|
| **[C1]** | RQ1 — does the GLM→GBDT gap survive as a difference of two SEALED numbers? | glm + gbdt | **supported** | **confirmed** (both tracks' single sealed access spent) | E0011, E0012 (levels); E0003, E0004 (dev incumbents) | Sealed gap = 0.459231 − 0.449667 = **+0.009564 = 9.3× the sealed cross-track paired SE (0.001028)**. Against the pre-registered band: dev incumbent gap 0.453156 − 0.444689 = +0.008467; \|sealed − dev\| = 0.001097 = **1.07× SE**, inside the 2-SE replication band. The anchor-config gap (0.454861 − 0.444689 = +0.010172 = 10.6× the dev cross SE 0.000963) is the reference the study was designed around and it replicates too. |
| **[C2]** | RQ2 — is LightGBM-Poisson within 2× the gbdt floor of sklearn HGBT at matched capacity? | gbdt | **supported (a tie)** | exploratory | E0003, E0005, E0010 | Nominal-matched (200 rounds): 0.444413 vs 0.444689 = **−0.000276 = 0.48× floor 0.000573**. Effective-capacity-matched (M1-b, LGBM `n_estimators=67` against HGBT's early-stopped 67 trees): 0.444431 = **−0.000258 = 0.45× floor**. The tie holds at BOTH capacities, so it is algorithmic, not an early-stopping artefact. Both are discards by the contract — the discard IS the finding. |
| **[C3]** | RQ3 — does CatBoost's ordered-target-statistics + symmetric-tree package beat OHE-HGBT at cardinality ≤ 22? | gbdt | **refuted (no pay — prior held)** | exploratory | E0003, E0006 | 0.446332 vs 0.444689 = **+0.001643 = 2.9× floor 0.000573** — a real deficit, not a tie. Wording per method-card R3: `boosting_type` defaults to `Plain` on CPU, so this tests the **CTR + symmetric-tree package**, not ordered boosting. Replicates `04-fremtpl2-frequency#C3` (native-vs-OHE 0.37× floor) with a different library and the same conclusion. **Attribution caveat: the M2-a isolation lever (`one_hot_max_size=32`) was never run**, so CTR-vs-symmetric-tree capacity remains unresolved (see ②, ⑦). |
| **[C4]** | RQ4 — with column-SCOPED splines, what fraction of the gap does additive shaping close? | glm | **refuted in magnitude** (prior 30–45%) | exploratory (level sealed at E0011) | E0002, E0004; contrast `04-fremtpl2-frequency` E0002 | 0.454861 → 0.453156 = **−0.001705 = 3.2× glm floor 0.000539** — a real, kept frontier improvement, but only **16.8% of the 0.010172 anchor gap**, less than half the 30–45% prior. Decisive sub-finding: study 04's LEAKY shaping (spline basis spilling onto the OHE dummies) closed 0.001788 = **17.6%** — so **fixing the leak changed the closure by −0.8 percentage points, i.e. the leak was never the binding constraint**. Additive shaping tops out near 17% on this data. |
| **[C5]** | RQ5 — how much of the residual gap do the top surrogate-derived interactions recover? | glm | **refuted** (prior: a further 20–30%) | exploratory | E0004, E0007, E0008 + off-ledger surrogate forensics | Top pair alone (VehAge×BonusMalus): 0.453156 → 0.452926 = **−0.000230 = 0.43× glm floor** — sub-floor, DISCARD. Both top pairs: 0.452913 = **−0.000244 = 0.45× floor** — still sub-floor, DISCARD. **Multiplicity ledger: 10 pairs screened, 0 adopted** (M4-c budget honoured with room to spare). The scoped-spline GLM (E0004) is therefore the **practical GLM ceiling**, and the **non-additive residue is 0.008467 = 83.2% of the anchor gap = 8.8× the cross SE** — an irreducible remainder at this basis, not a measurement artefact. |
| **[C6]** | RQ6 — at what training-set size does the gap fall below 2× the paired floor? | glm + gbdt (measurement sweep) | **supported** (prior ~10–15% of train, 40–60k rows) | exploratory (measurement sweep, no ledger row) | `sweeps/data_volume.sidecar.tsv` (7 cells), anchored on E0002/E0003 | Gap by train fraction (anchor configs `glm_ohe` vs `hgbt_ohe`, dev fold never subsampled): **−0.001931 @5% (~20.3k rows — the GLM WINS)**, +0.003446 @10% (~40.7k), +0.003195 @15% (~61.0k), +0.006370 @25%, +0.008471 @50%, +0.009240 @75%, +0.010172 @100% (406,807). The gap crosses zero between **20k and 41k rows** and first clears 2× the cross SE (0.001925) at 10% of train. The prior's ~10–15% band is where the gap becomes *measurable*; the sign flip is one octave below it. |
| **[C7]** | RQ7 — does a monotone BonusMalus constraint cost more than 1× the gbdt floor? | gbdt | **refuted** (prior: filability is nearly free) | exploratory | E0009; control = `04-fremtpl2-frequency` E0004 (hgbt_native 0.445343, tag v1.0.0, identical split/prep) | Constraint component, differenced against a **same-encoding** unconstrained control per method-card R2: 0.447455 − 0.445343 = **+0.002112 = 3.7× gbdt floor 0.000573**. Total cost against the OHE incumbent (constraint + encoding switch): 0.447455 − 0.444689 = **+0.002766 = 4.8× floor**. The constraint also cut effective capacity: `effective_trees` 53 vs the incumbent's 67. Mechanism, resolved by M3-a: BonusMalus is non-decreasing in frequency over **100% of train exposure on the margin**, so `+1` was the correct sign — the cost is therefore *not* a wrong-sign penalty but the price of forbidding **conditional** non-monotonicity, coherent with VehAge×BonusMalus ranking first in the surrogate screen. |

**Evidence-level note.** Only [C1] is `confirmed` — it is the study's estimand and both
tracks' sealed accesses were spent on it (E0011, E0012). [C4]'s *level* is sealed
(E0011 confirms the scoped-spline GLM at 0.459231) but its *closure fraction* is a
development quantity. [C2], [C3], [C5], [C7] are development-fold comparisons and stay
exploratory; [C6] is a measurement sweep and carries no sealed evidence by design.

## ② Predictions to falsify (filled)

Six outcome-level levers from `study.yaml` + eight method-level levers (M1-a…M5-a)
appended at the CONSULT re-record.

| # | Lever | Predicted delta | Observed delta | Verdict | Evidence |
|---|---|---|---|---|---|
| 1 | glm sealed incumbent vs gbdt sealed incumbent (RQ1) | sealed gap within 2 paired SEs of the dev gap | sealed gap +0.009564 = 9.3× sealed SE; \|sealed − dev incumbent gap 0.008467\| = 1.07× SE | **held** | E0011, E0012 |
| 2 | HGBT-OHE → LightGBM poisson, matched capacity (RQ2) | within 2× gbdt floor → DISCARD (tie predicted) | −0.000276 = 0.48× floor → DISCARD | **held** | E0003, E0005 |
| 3 | HGBT-OHE → CatBoost native categoricals (RQ3) | within 2× gbdt floor → DISCARD (ordered TS does not pay at ≤22) | +0.001643 = **2.9× floor** → DISCARD, but as a real deficit, not a tie | **held on disposition, falsified on magnitude** | E0003, E0006 |
| 4 | GLM-OHE anchor → column-scoped splines (RQ4) | closes ≥30% of the 0.010172 gap (KEEP) | closes **16.8%** (−0.001705 = 3.2× glm floor) → KEEP | **held on disposition, falsified on magnitude** | E0002, E0004 |
| 5 | scoped-spline GLM → + top-2 surrogate interactions (RQ5) | closes a further ≥2× glm floor; total closure ≤70% (KEEP) | −0.000230 (1 pair, 0.43× floor) / −0.000244 (2 pairs, 0.45× floor) → both DISCARD | **falsified** | E0004, E0007, E0008 |
| 6 | HGBT → HGBT with monotone BonusMalus (RQ7) | within 1× gbdt floor → DISCARD (constraint is free) | +0.002112 vs same-encoding control = **3.7× floor**; +0.002766 vs OHE incumbent = 4.8× floor | **falsified** | E0009 + `04-fremtpl2-frequency` E0004 |
| 7 | **M1-a** HGBT `early_stopping='auto'` at 406,807 train rows | fitted `n_iter_` < 200 (capacity NOT matched at nominal 200) | `effective_trees` = **67** | **held** | E0003 |
| 8 | **M1-b** LGBM vs HGBT after matching effective tree count | \|Δ\| stays < 2× gbdt floor → the RQ2 tie is algorithmic | LGBM@67 = 0.444431, Δ = −0.000258 = **0.45× floor** | **held** | E0010 (vs E0003) |
| 9 | **M2-a** `catboost_poisson` with `one_hot_max_size=32` (CTRs off) | moves dev deviance < 0.5× gbdt floor → the deficit is symmetric-tree capacity, not categorical handling | **not measured** — no experiment slot was spent on the isolation run; the study redirected to adaptive-3's monotone/capacity questions after E0006 | **untested (inconclusive)** — RQ3's package-level verdict [C3] stands; the CTR-vs-capacity attribution does not | (none; see ⑦ item 2) |
| 10 | **M3-a** empirical BonusMalus → frequency direction, 8 quantile bins on train | non-decreasing over ≥90% of exposure → `+1` is the right sign | non-decreasing over **100% of exposure** (qcut collapsed to 4 usable bins; 68.8% of exposure sits in BM 50–54) | **held** | off-ledger forensics; consumed by E0009 |
| 11 | **M4-a** train-fold surrogate `R²_main` vs the HGBT log-score | > 0.90 → the gap is mostly NOT an interaction gap | **R²_main = 0.6647** | **falsified** — the gap IS substantially non-additive | off-ledger `forensics.surrogate_glm`; corroborated by E0007/E0008 |
| 12 | **M4-b** top-ranked surrogate residual pair | (BonusMalus, DrivAge) ranks first | ranking: **VehAge×BonusMalus 0.1536** > BonusMalus×logDensity 0.0985 > VehAge×DrivAge 0.0789; **DrivAge×BonusMalus ranks 8/10** | **falsified** | off-ledger `forensics.surrogate_glm`; PD cross-check strengths 0.029 / 0.043 / 0.016 |
| 13 | **M4-c** multiplicity budget | 10 pairs screened, ≤2 adopted, none adopted below 1× glm floor, all rejections reported | **10 screened, 0 adopted**; best candidate reached 0.43× floor and was rejected; both rejections filed as ledger rows | **held** (with margin) | E0007, E0008 |
| 14 | **M5-a** 8-bin BonusMalus gap decomposition | top-3 segments carry ≥50% of the gap on ≤25% of exposure | top-3 BonusMalus bins carry **87% of the gap on 89% of exposure** — proportional, not concentrated | **falsified** — the gap is DIFFUSE | off-ledger `forensics.segment_deviance_gap` |

**Score: 6 fully held (1, 2, 7, 8, 10, 13), 2 held-on-disposition-but-falsified-on-magnitude
(3, 4), 5 outright falsified (5, 6, 11, 12, 14), 1 untested (9).** The study's priors were
right about *what the loop would decide* far more often than about *how much* — every
magnitude prior that was stakeable came out wrong.

## ③ Surprises and why

1. **The GBDT was running at one third of its nominal capacity — and nobody would have
   known.** `HistGradientBoostingRegressor(max_iter=200)` fitted **67** trees (E0003,
   `effective_trees` in `aux_metrics.tsv`), because `early_stopping="auto"` switches on
   above 10,000 samples and holds out `validation_fraction=0.1` of the train fold.
   LightGBM at `n_estimators=200` built all 200 (E0005). *Every* "matched-capacity library
   comparison" published with those two default configs is comparing 67 trees to 200.
   **Why it didn't matter here:** M1-b (E0010) truncated LGBM to 67 and the delta *shrank*
   (0.48× → 0.45× floor). Both libraries have already saturated this signal well before 67
   trees, so the confound was real but inert. That is luck, not design — the confound was
   only visible because method-card risk R1 forced `effective_trees` into the aux ledger on
   every GBDT row.

2. **The interaction the literature would bet on ranks eighth.** BonusMalus×DrivAge is the
   canonical French-MTPL confound (young drivers enter at the base level 100), and M4-b
   staked the prior on it. The train-fold surrogate ranks it **8 of 10** by residual
   correlation, behind VehAge×BonusMalus (0.1536) and BonusMalus×logDensity (0.0985); the
   independent partial-dependence instrument agrees on the top *set* (strengths 0.029 /
   0.043 / 0.016) while disagreeing mildly on order. **Mechanism:** the DrivAge–BonusMalus
   relationship is largely *marginal* confounding, which additive main effects already
   absorb; what the tree adds is **vehicle-age conditioning of the experience-rating
   signal** — an old car with a bad BM record is not the linear sum of "old car" and "bad
   record". Caveat (method-card R7): the surrogate basis is numeric-only, so a
   Region×DrivAge-style categorical interaction is structurally invisible to this ranking.

3. **The leak fix changed nothing.** Study 04's shaped GLM leaked the spline basis onto the
   OHE dummies and closed 17.6% of the gap; this study's column-scoped splines — the clean
   version, the whole reason RQ4 existed — closed **16.8%** (E0004). The follow-up study was
   designed on the hypothesis that the leak was suppressing the measurement. It was not.
   **Mechanism:** splining a dummy is a no-op in expressiveness (a 0/1 column's cubic basis
   spans the same two-point space), so the "leak" added parameters and a hair of overfit,
   never signal. The honest reading: **additive shaping of this feature set tops out near
   17% of the gap, and no amount of basis hygiene moves that number.**

4. **A filable monotone constraint costs 3.7× the floor even though the constraint is
   empirically true.** M3-a checked the marginal shape first and found BonusMalus
   non-decreasing in frequency over **100%** of train exposure — the `+1` sign is not merely
   defensible, it is right. Yet enforcing it cost +0.002112 against the same-encoding control
   (E0009), a quarter of the entire GLM→GBDT gap. **Mechanism:** sklearn's monotone
   constraint is enforced *pointwise in every conditioning context*, not on the marginal. The
   model wants BonusMalus to bend differently for old vehicles than for new ones — precisely
   the VehAge×BonusMalus interaction that ranked first in surprise 2 — and the constraint
   forbids exactly that. **Marginal monotonicity does not imply conditional monotonicity, and
   it is the conditional version the library enforces.** Two forensics instruments (a
   surrogate ranking and a constraint cost) landed on the same structure by different routes.

5. **At 20,000 rows the GLM is not the compromise — it is the better model.** The RQ6 sweep's
   5% cell shows the gap at **−0.001931**: the GLM-OHE anchor *beats* HGBT
   (`sweeps/data_volume.sidecar.tsv`). **Mechanism:** the gap is overwhelmingly non-additive
   structure (83.2%, [C5]) and interactions need data density to estimate; below the
   crossover the tree's variance in estimating them exceeds the GLM's bias from ignoring
   them. **Honesty note:** at 2.0× the full-data cross SE this reversal sits right at the
   2-SE line, and the SE at 5% of the data is larger than the SE it is being judged against —
   so read the *crossover* as established and the *magnitude of the GLM's win* as at the edge
   of measurability.

6. **The +2% A/E "bias" was a fold, not a model.** Every development row reports
   `calibration_ratio` ≈ 1.014–1.022 (over-prediction), and method-card R5 froze it as a known
   bias to be reported and never recalibrated. On the sealed test both models flip to
   **under**-prediction: 0.9962 (E0011) and 0.9905 (E0012). **Mechanism:** the data card's
   partition frequencies are train 0.073900 / dev 0.072375 / test 0.074350 exposure-weighted
   claims per year. A model calibrated to train over-predicts dev by 0.073900/0.072375 = 1.021
   and under-predicts test by 0.073900/0.074350 = 0.994 — matching the observed 1.0216 and
   0.9962 almost exactly. The A/E number was measuring **split sampling variation**, not model
   calibration. Both tracks move together, so the gap is untouched — the sharpest available
   demonstration of why [C9] ("report the gap, not the level") is the operative discipline.

## ④ Practical advice

1. **[C8]** **Run the translate-back program as a *screen with a budget*, not as a search.**
   Distil the black box on the **train fold only** into an interpretable surrogate, rank
   candidate structure by residual explanation, then adopt on development **only above the
   measured floor** — and publish `screened / adopted` either way. Here that was
   **10 screened, 0 adopted** (E0007 at 0.43× floor, E0008 at 0.45× floor), and the honest
   zero is a stronger result than any of the ten "improvements" a floor-free search would
   have reported (evidence: E0004, E0007, E0008; M4-c).

2. **[C9]** **Report the GAP, never the levels.** 26.54% of development rows and 26.37% of
   sealed-test rows have a feature-identical twin in the train fold (`data_card.md` issue 1;
   31,798 straddling groups), and the three partitions differ in exposure-weighted frequency
   by ±1.3%. Both effects hit both tracks identically, so the GLM↔GBDT difference is robust
   while every absolute deviance and every A/E ratio is fold-specific — as ③.6 shows, the dev
   fold's "+2% over-prediction" reversed sign on the sealed fold with no model change
   whatsoever (evidence: E0011, E0012 vs E0002–E0004; `data_card.md` issue 1).

3. **[C10]** **Log EFFECTIVE capacity on every boosted row before you claim a library
   difference — or a library tie.** `max_iter` / `n_estimators` / `iterations` are nominal;
   `n_iter_`, `booster_.num_trees()`, `tree_count_` are what you actually fitted. HGBT
   early-stops above 10,000 samples by default and delivered **67** of a nominal 200 trees
   (E0003), the monotone variant delivered **53** (E0009), while LightGBM and CatBoost
   delivered all 200 (E0005, E0006). Match on the effective number and re-run before writing
   the verdict (evidence: E0003, E0005, E0009, E0010).

4. **[C11]** **Measure the paired floor that governs YOUR comparison before believing any gap —
   there is more than one floor and they differ by a factor of five or more.** This study
   measured four: a GLM fit-seed std of **exactly 0** (deterministic solver — quoting a seed
   floor for a GLM is meaningless), a GBDT fit-seed std of 0.000210, within-track
   paired-bootstrap SEs of 0.000270/0.000287, and a **cross-track** paired SE of 0.000963 —
   4.6× the GBDT seed floor and the only one of the four that legitimately bands the headline
   gap. Use common random numbers and bootstrap the *difference*, not the two levels
   (evidence: `sweeps/noise_floor_*.sidecar.tsv`, `sweeps/paired_floor.py`, E0002, E0003).

5. **[C12]** **Size-gate the model class before you spend a week on it.** Refit both candidates on
   nested subsamples of your own train fold and plot the gap against n: it costs seven fits
   (14 s of compute here) and it tells you whether the boosted model is worth its governance
   overhead at all. On freMTPL2 the crossover is **20–41k rows** and the gap does not clear
   2× the cross SE until ~40k — below that a filed additive GLM is not a concession, it is the
   better model (evidence: `sweeps/data_volume.sidecar.tsv`, [C6]).

6. **[C13]** **Price a shape constraint against a control that differs ONLY by the constraint, and
   check the MARGINAL shape first so you know what you are pricing.** `hgbt_monotone` also
   switches the encoder to native-categorical; differencing it against the OHE incumbent
   measures constraint + encoding (+0.002766 = 4.8× floor), while the same-encoding control
   isolates the constraint (+0.002112 = 3.7× floor). And confirm the empirical direction before
   interpreting: BonusMalus is monotone over 100% of train exposure marginally (M3-a), so this
   cost is the price of forbidding *conditional* non-monotonicity, not a wrong-sign penalty — a
   completely different conversation with a regulator (evidence: E0009,
   `04-fremtpl2-frequency` E0004, M3-a).

7. **[C14]** **Start the next study from `checklist.md`, not from this file.** The transferable
   product of this study is the seven-row **dataset-characteristics → method-choice checklist**
   shipped alongside these findings; each row names the measurable property of *your* data, the
   method choice it implies, and the claim ID that earned it. Read the checklist to decide;
   read findings.md to audit the decision (evidence: all of [C1]–[C7]).

## ⑤ Business / actuarial value implications

**The price of interpretability on this book is now a number with an error bar on it.**
A filed additive GLM — even a properly spline-shaped one, with the study-04 basis leak
fixed — leaves **83.2% of the modeling gap on the table** at 678,013 rows (residue
0.008467 = 8.8× the cross-track paired SE; E0004 vs E0003). The recoverable portion is
16.8% via additive shaping (E0004) and, measurably, **nothing further** from the two
strongest interaction candidates the black box itself nominated (E0007, E0008, at 0.43×
and 0.45× floor). "Rebuild the GLM better" is not a route to closing this gap; the
remaining advantage is non-additive structure a linear score cannot represent
(`R²_main` = 0.6647).

**But the price is a function of portfolio size, and below ~40k rows it is zero or
negative.** The RQ6 curve ([C6]) makes model choice a *sizing* decision rather than a
methodological preference: at ~20k exposures the GLM anchor **beats** the boosted model
(−0.001931), and the gap does not clear 2× the cross SE until ~40k rows. For a small book,
a new line of business, a thin segment carved out for separate rating, or a territory with
sparse history, the boosted model buys nothing measurable and costs the whole governance,
documentation, and monitoring apparatus. **Do not buy a GBDT programme for a portfolio that
cannot feed it.**

**Filing constraints are not free, and they are expensive in exactly the way that matters.**
Enforcing the regulator-friendly monotone BonusMalus shape cost **3.7× the floor** — about a
quarter of the entire GLM→GBDT gap — against a same-encoding control (E0009). Because
BonusMalus is marginally monotone over 100% of exposure (M3-a), the cost is not the model
being dragged toward a wrong shape; it is the model being forbidden from letting the
experience-rating slope vary by vehicle age. That is a concrete, quantifiable trade the
pricing committee can actually decide: *this much predictive accuracy for this much shape
guarantee*. Quantified against the GLM-OHE anchor: the unconstrained incumbent captures the
full 0.010172 gap, the monotone variant captures 0.454861 − 0.447455 = 0.007406 = **72.8%** —
so filing the shape guarantee gives up **27% of the boosted edge** (E0002, E0003, E0009).

**Where the gap does NOT live is as useful as where it does.** The M5 decomposition is
**diffuse** — the top-3 BonusMalus bins carry 87% of the gap on 89% of exposure, i.e. the
gap is essentially proportional to exposure. There is no bad segment to carve out, no thin
high-frequency pocket where a specialist model earns its keep. Any capture of this gap is a
**book-wide** re-rate, not a targeted intervention — which raises the implementation cost and
the filing burden relative to the "just fix the bad segment" story the concentration prior
(M5-a) would have supported.

**On calibration and capital:** both sealed models land within 1% of unity on A/E (0.9962
GLM, 0.9905 GBDT; E0011, E0012) with **no recalibration applied**, so the deviance comparison
is between two adequately-calibrated models rather than a rank-vs-calibration trade. Neither
model needs an off-balance correction before use. The ±2% swing between folds (③.6) is
portfolio-sampling noise and should not be booked as a model loading.

**Operational cost is not the deciding variable.** Wall-clock per fit: GLM 1.1–1.5 s,
HGBT 2.9 s, LightGBM 2.2–3.2 s, CatBoost 7.1 s (`aux_metrics.tsv`) — all three orders of
magnitude inside the 400 s guardrail. Library choice here is an operations decision
(deployment target, native-categorical support, team familiarity), not an accuracy
decision ([C2]).

## ⑥ Literature tie-back

- **Noll, Salzmann & Wüthrich (SSRN 3164764), *Case Study: French Motor Third-Party Liability
  Claims*.** Direction reproduced: boosting beats the GLM on freMTPL2, with interactions as
  the mechanism. This study adds two things the case-study literature does not carry — an
  **error bar on the gap** (cross-track paired-bootstrap SE 0.000963 dev / 0.001028 sealed) and
  the gap as a **difference of two sealed test numbers** ([C1]). Absolute deviances differ from
  the published case study because this hub variant is pre-clipped (`data_card.md`).
- **Lorentzen & Mayer (SSRN 3595944), *Peeking into the Black Box*.** The closest published
  precedent for this study's forensics layer, on the same dataset: they do the interpretability
  forensics without a sealed confirmation; study 04 did the seal on one track only. Doing
  both — deriving translate-back structure on train, adopting on development under a *reported*
  multiplicity budget, confirming as two sealed numbers — is the protocol contribution here,
  and it is the reason the "0 of 10 adopted" result is publishable rather than embarrassing.
- **Wüthrich & Merz (2023, *Statistical Foundations of Actuarial Learning*, Ch. 2/5) and
  Denuit, Hainaut & Trufin (2019).** The offset ≡ exposure-weight equivalence used throughout
  (`y = ClaimNb/Exposure`, `sample_weight = Exposure`) is their standard treatment; it held
  across `PoissonRegressor`, HGBT, LightGBM and CatBoost without per-library offset plumbing
  (E0002–E0006).
- **Grinsztajn, Oyallon & Varoquaux (2022), *Why do tree-based models still outperform deep
  learning on typical tabular data?*** Standing doctrine unchallenged — the tree wins here too.
  The refinement this study contributes is **conditional**: the doctrine is a large-sample
  statement. At ~20k rows on this data the additive GLM wins ([C6]), consistent with their own
  emphasis on tabular targets being irregular and interaction-heavy — such functions are only
  *learnable* when there are enough rows to learn them.
- **Prokhorenkova et al. (2018), CatBoost; Ke et al. (2017), LightGBM.** Both libraries'
  headline advantages are cardinality- and scale-conditional, and neither condition is met
  here: at ≤22 levels with roughly 9,000 train rows per Region level, ordered target statistics
  have nothing to de-bias, and the CTR + symmetric-tree package lands **2.9× floor worse** than
  plain OHE-HGBT ([C3]). LightGBM's leaf-wise growth and `poisson_max_delta_step=0.7`
  regulariser produce no measurable difference from HGBT's depth-wise histogram trees at either
  capacity ([C2]).
- **Priors' scorecard.** `knowledge/`-sourced priors: RQ2 (`gbdt-tabular.md`) **held** exactly;
  RQ3 (`gbdt-tabular.md` / study-04 C3) **held on disposition** but understated the magnitude —
  the deficit is 2.9× floor, not a tie, so the card should say "OHE is at least as good, and
  specifically CatBoost's CTR+symmetric package is *worse* at ≤22 levels"; RQ7
  (`glm-pricing.md`, "filability is nearly free") **REFUTED** at 3.7× floor and needs a caveat
  at promotion: *a constraint that is true on the margin can still be expensive when the
  model's edge is interaction-borne*. RQ4's prior came from study 04's own caveat and was
  **refuted** — the caveat over-promised. `uninformed` priors: RQ5 **refuted** (no further
  recovery, versus a predicted 20–30%), RQ6 **held** (~10–15% of train). Net: knowledge-sourced
  priors went 1 fully held / 1 partially / 2 refuted while uninformed priors went 1 held /
  1 refuted — informed priors did **not** outperform uninformed ones here, and both card
  refutations are cases where a *large-sample, main-effects* intuition was generalised into a
  regime where the binding structure was interactions.
- **Study 04 lineage.** `04-fremtpl2-frequency#C1` (the gap, level-confirmed but
  gap-exploratory) is upgraded to a sealed-gap claim by [C1]; `#C2` (shaping closes 18%,
  refuted in magnitude) is **reproduced under the clean scoped basis** at 16.8% ([C4]); `#C3`
  (native ≈ OHE at ≤22 levels) is extended to a third library ([C3]). The §⑥ protocol caveat
  study 04 filed — "the gap cannot be sealed-confirmed under one-access-per-track" — is
  **closed**. E0012 also reproduced study 04's sealed HGBT number (0.449667) bit-identically
  across a study boundary.

### Limitations

1. **Feature-profile twins straddle the split (the dominant caveat).** 26.54% of development
   rows and 26.37% of sealed-test rows have a feature-identical twin in train (`data_card.md`
   issue 1; 31,798 straddling groups). Prep was frozen byte-for-byte to study 04 to preserve
   the 0.454861/0.444689 anchors, so this was recorded and not fixed. **Consequence: every
   absolute deviance level in this document is optimistic relative to a fresh portfolio; the
   GAP is not, because both tracks consume identical contamination.** Twin rows are also
   claim-poor (1.97% claim-bearing among dev twins vs 3.68% overall), which bounds the
   memorization upside.
2. **The surrogate screen is numeric-only (method-card R7).** `forensics.surrogate_glm` ranks
   numeric×numeric products in a cubic basis. Region×DrivAge, VehBrand×VehAge and pure
   threshold interactions are **structurally invisible** to the M4-b ranking and to the
   E0007/E0008 adoption test. The "0 of 10 adopted" result therefore bounds what
   *numeric-product* translate-back can recover, not what *any* GLM-representable structure
   could — a categorical interaction probe is the first thing ⑦ item 2 buys.
3. **One split, one seed.** All results come from a single random 60/20/20 split at seed 42.
   The paired bootstraps quantify comparison noise *within* that split; they say nothing about
   split-to-split variation. No time column exists in the prepared artifact (`data_card.md`
   issue 9), so [C1] is an **in-period** statement about this portfolio, not a
   forward-in-time generalization claim.
4. **Hub-prepped data.** The `data_hub:freMTPL2` variant arrives pre-clipped (`ClaimNb ≤ 4` is
   a no-op here: 0 rows exceeded it) and `prepare.py`'s exposure lower clip silently binds
   1,060 rows at 1/365.25 while the hygiene counter reports 0 (`data_card.md` issues 4–5).
   Absolute values are therefore not directly comparable to published freMTPL2 numbers from
   other preparations. `Density` also has a real censoring ceiling (1.55% of rows pinned at
   exactly 27,000).
5. **Off-ledger forensics carry no uncertainty.** `R²_main` = 0.6647, the pair rankings, the PD
   strengths and the M5 shares are **same-fold descriptive instruments** computed outside the
   run ledger (method-card R6/R8). They are cited as directional evidence and every conclusion
   they support is independently confirmed by a ledger row (E0007/E0008 for the interaction
   story, E0009 for the monotonicity story) — no verdict in ① rests on a forensics number
   alone.
6. **M2-a untested.** The CatBoost deficit's attribution — categorical handling versus
   symmetric-tree capacity — was never isolated (② row 9). [C3] is a package-level claim only.
7. **The RQ6 curve is not perfectly monotone.** The 15% cell (+0.003195) sits below the 10%
   cell (+0.003446) by 0.000251 = 0.26× the cross SE — sub-floor, i.e. noise. Descriptions of
   the curve as "monotonically increasing" should read "increasing apart from one sub-floor
   inversion between 10% and 15%".

## ⑦ What to try next

1. **Tensor-product spline / GAM interactions on the glm track — the real test of RQ5.**
   E0007/E0008 tested *raw standardized products*, the crudest possible interaction basis, and
   found 0.43–0.45× floor. The surrogate says the structure exists (`R²_main` 0.6647) and names
   where it is (VehAge×BonusMalus). Fit a tensor-product spline basis (or a bivariate smooth)
   on that one pair inside the scoped-spline GLM and see whether a *flexible* interaction
   recovers what a product could not. Highest-information follow-up: it decides whether "83%
   non-additive" means "GLM-unrepresentable" or merely "not representable by products".
   Prediction to falsify: closes 2–5× the glm floor — enough to keep, far short of the residue.
2. **Categorical interaction probe — close the R7 blind spot, and spend the slot M2-a never
   got.** Extend the screen to categorical×numeric and categorical×categorical structure
   (Region × DrivAge, VehBrand × VehAge) using `forensics.two_way_pd_gap` on the fitted HGBT
   rather than the numeric-only surrogate, and re-run the segment decomposition over Region and
   VehBrand levels instead of BonusMalus bins. In the same phase, run `catboost_poisson` with
   `one_hot_max_size=32` so [C3]'s CTR-vs-capacity attribution stops being open.
3. **A two-track CI anchor test.** Both anchors reproduced to 1e-9 across a study boundary and
   E0012 reproduced study 04's sealed number bit-identically. Promote the pair (0.454861 /
   0.444689 on the frozen prep SHA-256 `db82e802…1cf948`) into a repo-level regression test so
   any future change to `pipeline.py`, `kleinlib.eval`, or the environment that moves either
   anchor fails CI loudly. Determinism this exact is an asset; nothing currently guards it.
4. **Framework fixes (both cost a real experiment slot in this study).**
   **F1** — `evaluate_regression` writes `wall_seconds` to `aux_metrics.tsv` but does not PRINT
   it, and the runner's guardrail check reads the printed block; E0001 was dispositioned discard
   with an anchor-exact metric because of it. Fix: print `wall_seconds` in the canonical block,
   **or** have `klein preflight` fail when a declared guardrail metric is not among the keys the
   run will print.
   **F2** — `klein new` scaffolds a single track and `initial_state` derives
   `final_holdout_access` keys from the tracks *at scaffold time*; adding a second track by
   editing `study.yaml` (the only way to build a two-track study today) leaves that map stale,
   and E0012 was refused with "sealed final-test state is missing for track 'gbdt'". Fix: have
   `load_state` top up per-track maps from the current contract, **or** let `klein new` accept
   repeated `--track`.
5. **Severity / pure-premium extension.** Frequency is one of two factors in the premium. The
   same two-track sealed-gap protocol on a Gamma severity track and a Tweedie pure-premium track
   would say whether the 83% non-additive residue is a frequency phenomenon or a property of
   this book — and whether the 20–41k crossover moves when the response gets noisier.
