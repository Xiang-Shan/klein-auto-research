---
type: method-card
domain: "insurance"
profile: "insurance"
status: complete
concepts: [isotonic-calibration, class-weight-prior-shift, spline-basis, histogram-gradient-boosting, paired-bootstrap, auc-standard-error, brier-decomposition]
related: [study.yaml, research_plan.md, references.yaml, ../../knowledge/domains/insurance/README.md, ../../knowledge/domains/insurance/best-practices-auto-insurance.md, ../../knowledge/method_cards/glm-pricing.md]
refs_verified: true
triad:
  theory: true
  papers: true
  practice: true
---

# Method card — calibrated risk scoring on a weak-signal binary target, and the paired bootstrap that decides whether a rung moved

> Gate 2 (METHOD). Protocol:
> `.claude/skills/klein/references/method-gate-protocol.md`. The five parts are an
> authoring ARC — written in order.
>
> The models in this study (logistic regression, a spline basis, isotonic
> calibration, a histogram gradient-boosted tree) are FAMILIAR — the v1 quickstart
> ran them and `knowledge/method_cards/glm-pricing.md` carries the full pricing
> pedagogy. What is not familiar, and what every decision in this study actually
> turns on, is the pair of measuring instruments underneath them: the **calibration
> map** that separates ranking quality from probability quality, and the **paired
> bootstrap floor** that decides whether a difference between two rungs is a
> measurement at all. Those are what this card teaches.

## 1. Intuition (for a practitioner)

You are an actuary with 58,592 motor policies and a 6.4 % claim rate, and you want a
number per policy you can multiply by an expected severity and put in a rate filing.
Two completely different things can be wrong with such a number, and one metric cannot
see both.

**Ranking.** Does the model put the policies that actually claimed above the ones that
did not? That is what AUC measures, and it is the only thing AUC measures. Pick a
random claimant and a random non-claimant; AUC is the probability the model scores the
claimant higher. An AUC of 0.63 on a portfolio like this is a genuine but weak signal —
and it is *rank* information, which is what a triage list or a relativity ordering needs.

**Level.** When the model says 12 %, do 12 % of those policies claim? That is
calibration, and AUC is blind to it: any strictly increasing relabelling of the scores —
halve them, square them, run them through any monotone curve — leaves AUC exactly
unchanged while destroying or repairing the level completely. A technical premium is
`P(claim) × severity` attached policy by policy; it lives entirely in the level. So a
model can rank beautifully and still be unfilable.

Three tools follow from that split.

**`class_weight="balanced"` is a level-destroyer, and it is popular anyway.** Weighting
the 6.4 % of claim rows up until they carry the same total weight as the 93.6 % that did
not claim tells the model it is living in a 50/50 world. The fitted probabilities come
out at the scale of that imagined world — far too high — while the ordering barely
changes, because reweighting the classes mostly shifts the intercept. That is the
insurance profile's war story 4 in one sentence, and Dal Pozzolo et al. (2015) is its
published form. You get a model that ranks and lies.

**Isotonic calibration is a level-repairer that cannot touch the ranking.** Fit a
staircase — any non-decreasing step function — from the model's raw score to the
observed claim frequency, choosing the staircase that maximises the likelihood of the
labels. Because the staircase never goes down, the order of the scores after the map is
the order before it, so AUC is preserved by construction (up to the noise of the
cross-fitting that keeps the map honest). This is why "calibrate, don't reweight" is
doctrine here and not taste: calibration buys level at no rank cost, reweighting buys
nothing and pays level.

**Splines let a GLM bend without becoming a black box.** A logistic regression forces
each numeric rating factor into a straight line in log-odds. Vehicle age and
subscription length are not straight lines. A B-spline basis replaces one column by a
handful of smooth local humps whose weighted sum can bend — still a GLM, still
inspectable, still filable, now able to say "risk rises to age 6 and flattens". Where
you put the humps is a modelling choice, not a default: the standard practice is knots
at quantiles of the covariate (Perperoglou et al. 2019), so the flexibility lands where
the data actually is. scikit-learn's default is equally spaced knots, which on a skewed
column spends most of its flexibility where there are no policies.

**And the instrument that decides all of it.** Every claim in this study is of the form
"rung B beat rung A by Δ". Δ is a measurement, and a measurement without a resolution is
a rumour. Re-drawing the evaluation rows moves each rung's own AUC by about ±0.016 here —
larger than most of the gaps in the ladder. But the two rungs are scored on the *same*
rows, so their errors move together and largely cancel; the DIFFERENCE is far better
resolved than either level (DeLong et al. 1988). The paired bootstrap measures exactly
that: resample the evaluation rows once per replicate, score BOTH rungs on the same
resample, and look at the spread of the difference. That spread — not the spread of a
single model's score, and not the spread across fit seeds — is what a keep must clear.

## 2. Math core

| Symbol | Meaning |
|---|---|
| $y_i \in \{0,1\}$ | claim indicator for policy $i$ |
| $s_i$ | the model's raw score for policy $i$ (a probability or any monotone transform of one) |
| $\hat p_i$ | the calibrated probability for policy $i$ |
| $n_1, n_0$ | number of positives and negatives in the evaluation partition |
| $A$ | ROC-AUC on that partition |
| $w_c$ | the fit weight given to class $c$ |
| $\pi, \pi'$ | the positive-class prior in the population and in the (re)weighted training sample |
| $\Delta$ | the difference in AUC between two rungs on the SAME rows |
| $\sigma_\Delta$ | the bootstrap standard deviation of $\Delta$ |
| $d$ | `minimum_delta`, the contract's keep bar |
| $B$ | number of bootstrap replicates |

**(1) AUC is a ranking probability, and it has a closed-form variance.**

$$ A \;=\; \Pr\!\left(s_i > s_j \mid y_i = 1,\, y_j = 0\right), \qquad
\widehat{\operatorname{Var}}(A) \;=\; \frac{A(1-A) + (n_1-1)(Q_1 - A^2) + (n_0-1)(Q_2 - A^2)}{n_1 n_0} $$

with $Q_1 = A/(2-A)$ and $Q_2 = 2A^2/(1+A)$ (Hanley & McNeil 1982). At $A = 0.6255$,
$n_1 = 375$, $n_0 = 5484$ this gives SE $\approx 0.0159$ — the number that fixed this
study's anchor tolerance before any model was fitted.

**(2) A monotone map cannot change AUC.** If $g$ is non-decreasing then
$s_i > s_j \Rightarrow g(s_i) \ge g(s_j)$, so every concordant pair stays concordant and

$$ A\big(g(s), y\big) \;=\; A(s, y) \quad \text{whenever } g \text{ is strictly increasing.} $$

Isotonic regression's $g$ is non-decreasing but not strictly so — it has flat steps —
which converts some concordant pairs into ties, each worth $\tfrac12$ instead of $1$.
That, plus the cross-fitting, is the entire mechanism by which calibration can move AUC
at all, and it is why the expected move is small and negative.

**(3) Isotonic calibration is a constrained maximum-likelihood problem.** Sort by score
and solve

$$ \min_{g_1 \le g_2 \le \cdots \le g_n} \sum_{i=1}^{n} \left(y_{(i)} - g_i\right)^2 $$

whose exact solution is the pool-adjacent-violators algorithm (Ayer et al. 1955): walk
left to right, and whenever the running fit would decrease, merge the offending block
and replace it with its mean. Zadrozny & Elkan (2002) brought it to classifier scores.

**(4) Reweighting a class is a prior shift.** Weighting class $c$ by $w_c$ trains on an
implied prior $\pi' = \pi w_1 / (\pi w_1 + (1-\pi) w_0)$. For a logit model this
displaces the intercept by

$$ \log\frac{\pi'/(1-\pi')}{\pi/(1-\pi)} \;=\; \log\frac{w_1}{w_0}, $$

leaving the slopes — hence the ranking — almost untouched. `class_weight="balanced"`
sets $w_c \propto 1/n_c$, i.e. $\pi' = \tfrac12$ against a true $\pi = 0.064$: the
probabilities come out roughly an order of magnitude too high, the ranking survives, and
the Brier score collapses (Dal Pozzolo et al. 2015).

**(5) The paired bootstrap floor.** With one index draw per replicate applied to BOTH
rungs (common random numbers),

$$ \Delta^{(b)} = A_B\big(\mathcal{I}^{(b)}\big) - A_A\big(\mathcal{I}^{(b)}\big),
\qquad
\sigma_\Delta = \operatorname{sd}\big(\Delta^{(1)}, \dots, \Delta^{(B)}\big),
\qquad
d = \max\!\left(2\sigma_\Delta, \tfrac{1}{2}\operatorname{range}\right). $$

Two draws instead of one would inflate $\sigma_\Delta$ by roughly $\sqrt{2}$ and quietly
raise the keep bar; `kleinlib.metrology.paired_bootstrap` takes exactly one draw per
replicate and exposes no seam to do otherwise. Brier (1950) supplies the second, level-
sensitive score the doctrine test is decided on:
$\mathrm{BS} = \frac1n\sum_i (\hat p_i - y_i)^2$, strictly proper, so it is minimised
only by the true probability.

## 3. Minimal from-scratch implementation plan

**PAVA, the whole of isotonic regression, in ten lines** — this is what
`CalibratedClassifierCV(method="isotonic")` runs per fold:

```python
def pava(y, w=None):
    """Least-squares monotone fit to y. Blocks: (sum, weight)."""
    w = [1.0] * len(y) if w is None else list(w)
    blocks = []                                    # (weighted sum, weight)
    for value, weight in zip(y, w):
        blocks.append([value * weight, weight])
        while len(blocks) > 1 and (                # a violation of monotonicity …
            blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]
        ):
            s, wt = blocks.pop()                   # … is fixed by pooling
            blocks[-1][0] += s
            blocks[-1][1] += wt
    return [s / wt for s, wt in blocks for _ in range(int(wt))]
```

The staircase must be fitted on rows the base model did NOT fit, or it learns the base
model's training-set overfit and reports it as calibration.
`CalibratedClassifierCV(cv=5)` does that cross-fitting for us and averages the five
maps; `cv=5` rather than `cv=3` is the third of the three non-default kwargs the v1
study identified as load-bearing.

**The paired bootstrap, in ten lines** — one draw, both rungs:

```python
rng = np.random.default_rng(seed)
n = len(y_eval)
deltas = []
for _ in range(B):
    idx = rng.integers(0, n, n)                    # ONE draw per replicate …
    if y_eval.iloc[idx].nunique() < 2:             # a degenerate resample is skipped
        continue
    a = roc_auc_score(y_eval.iloc[idx], p_A[idx])  # … applied to BOTH rungs
    b = roc_auc_score(y_eval.iloc[idx], p_B[idx])
    deltas.append(b - a)
sigma = np.std(deltas, ddof=1)
```

**What the study actually runs.** The rungs are assembled from stock scikit-learn
inside `train.py`, leaning on these helpers so that no experiment can change them:

| Helper | Job |
|---|---|
| `kleinlib.data.load_partition(kind)` | the rows, from the contract alone; prints the `split_fingerprint:` the notary checks |
| `kleinlib.encoders.build_preprocessor(..., kind="ohe", min_frequency=20)` | median-impute + standardise numerics, one-hot the categoricals with rare levels pooled |
| `kleinlib.eval.evaluate(...)` | the canonical printed block: AUC, PR-AUC, log-loss, **Brier**, lift@10 %, best threshold, plus any `extra=` keys |
| `kleinlib.metrology.paired_bootstrap` / `seed_sweep` / `split_lottery` | the three Phase 0 floor recipes |
| `kleinlib.sweep.SweepRunner` | one row per floor replicate into a resumable sidecar TSV |

The four rungs, each a `Pipeline(preprocessor, estimator)`:

| Rung | Estimator |
|---|---|
| `glm_ohe_balanced` | `LogisticRegression(max_iter=2000, solver="saga", class_weight="balanced")` |
| `glm_splines_isotonic` | the same, wrapped in `CalibratedClassifierCV(method="isotonic", cv=5)`, over a design matrix extended with `SplineTransformer(n_knots=5, degree=3, knots="quantile", include_bias=False)` on three numeric columns, `log1p(region_density)`, and two interactions |
| `hgbt_balanced` | `HistGradientBoostingClassifier(learning_rate=0.05, max_iter=500, max_leaf_nodes=31, class_weight="balanced", early_stopping=True, validation_fraction=0.1, n_iter_no_change=20)`, with seven near-deterministic functions of `model` dropped |
| `glm_ohe_none_isotonic` | `LogisticRegression(..., class_weight=None)` inside `CalibratedClassifierCV(method="isotonic", cv=5)` |

Each run also refits its declared REFERENCE rung on the same rows in the same process,
so `delta_in_floors` and `brier_delta_vs_reference` are paired quantities in a single
printed block rather than a subtraction across two log files.

## 4. When it pays / when it doesn't

| Regime | Data size | Signal | Verdict |
|---|---|---|---|
| Isotonic calibration on an imbalanced target | ≥ ~5k rows, ≥ ~300 positives | any | **pays** — Brier and log-loss improve by multiples at a rank cost near zero. Below a few hundred positives the staircase overfits and Platt scaling is safer. |
| `class_weight="balanced"` for a *filed* probability | any | any | **does not pay** — it shifts the prior and inflates the level for no ranking gain. It remains defensible when only the ordering is used and the level is recalibrated downstream. |
| Quantile-knot splines in a GLM | ≥ ~10k rows | weak but real, non-linear in a few numerics | **pays** — a few extra columns per factor, still inspectable, still filable. On a linear relationship they buy nothing and cost variance. |
| Histogram gradient boosting | ~10k–1M rows, mixed types | weak, with interactions | **pays on rank** (Grinsztajn et al. 2022 — trees remain the thing to beat at this size) and **not on level** (Niculescu-Mizil & Caruana 2005 — boosted scores are systematically distorted). Rank it, then calibrate it. |
| A paired floor rather than a marginal one | any | any | **pays** whenever the question is a comparison: it is the smaller, correct instrument. Using a marginal floor for a paired question sets the bar several times too high and hides real effects. |
| Chasing a fourth decimal of AUC on 6 % prevalence | 58k rows, 3.7k positives | weak | **does not pay** — a difference under the measured floor is not a measurement, whatever the ledger of a study without a floor recorded. |

**Falsifiable priors this card commits to** (mirrored to `study.yaml:predictions[]`):

1. Refitting each v1 rung on the identical training rows reproduces its recorded AUC
   within 0.0225 on the development half — P1, P2, P4. *The card can be wrong: an
   unrecoverable kwarg would show up here as a miss.*
2. The spline + isotonic chain beats the raw GLM anchor by at least one measured floor
   on the same rows — P3.
3. The boosted tree beats the calibrated GLM by at least one measured floor — P5. *This
   is the one the card is least sure of: the v1 gap between these two rungs was
   0.011190, and a floor of that order would make the comparison inconclusive rather
   than a win. That is exactly what the floor exists to reveal.*
4. `class_weight=None` + isotonic lowers Brier against the balanced rung while costing
   less than one floor of AUC — P6. *§2's equations (2) and (4) say the rank cost is
   near zero and the level gain is large; if Brier does not improve, equation (4) is
   wrong about this portfolio.*
5. The sealed score lands within two floors of the development incumbent — P7.
6. The v1 sweep's +0.001425 lift is smaller than the measured floor — P8. *If it is
   not, this card's claim that a fourth decimal cannot be measured here is wrong.*

## 5. Verified references

Every row checked against the publisher, arXiv or proceedings page on 2026-09-03 by the
orchestrating agent via WebSearch; full records, including the reason each is cited, in
`references.yaml`.

| Reference | Where | Verified? |
|---|---|---|
| Hanley & McNeil 1982, The meaning and use of the area under a ROC curve | Radiology 143(1), 29-36 · doi:10.1148/radiology.143.1.7063747 | ✅ |
| DeLong, DeLong & Clarke-Pearson 1988, Comparing the areas under two or more correlated ROC curves | Biometrics 44(3), 837-845 · doi:10.2307/2531595 | ✅ |
| Efron 1979, Bootstrap methods: another look at the jackknife | Annals of Statistics 7(1), 1-26 · doi:10.1214/aos/1176344552 | ✅ |
| Ayer, Brunk, Ewing, Reid & Silverman 1955, An empirical distribution function for sampling with incomplete information | Annals of Mathematical Statistics 26(4), 641-647 · doi:10.1214/aoms/1177728423 | ✅ |
| Zadrozny & Elkan 2002, Transforming classifier scores into accurate multiclass probability estimates | KDD 2002, 694-699 · doi:10.1145/775047.775151 | ✅ |
| Niculescu-Mizil & Caruana 2005, Predicting good probabilities with supervised learning | ICML 2005, 625-632 · doi:10.1145/1102351.1102430 | ✅ |
| Dal Pozzolo, Caelen, Johnson & Bontempi 2015, Calibrating probability with undersampling for unbalanced classification | IEEE SSCI 2015, 159-166 · doi:10.1109/SSCI.2015.33 | ✅ |
| Brier 1950, Verification of forecasts expressed in terms of probability | Monthly Weather Review 78(1), 1-3 · doi:10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2 | ✅ |
| Perperoglou, Sauerbrei, Abrahamowicz & Schmid 2019, A review of spline function procedures in R | BMC Med Res Methodol 19(1), 46 · doi:10.1186/s12874-019-0666-3 | ✅ |
| Grinsztajn, Oyallon & Varoquaux 2022, Why do tree-based models still outperform deep learning on tabular data? | NeurIPS 2022 Datasets & Benchmarks · arXiv:2207.08815 | ✅ |

No reference on this card is unverified. The methods are established rather than
frontier, so no lit-scan of a 2023+ literature was required; the doctrine anchor
(Grinsztajn 2022) is the profile's own and is cited where it does work, in §4.
