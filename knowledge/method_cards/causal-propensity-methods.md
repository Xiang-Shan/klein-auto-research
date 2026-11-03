---
title: "Propensity-Score Methods for Observational Effect Estimates"
type: method-card
domain: science
profile: [data-science, generic]
status: seed
concepts: [estimand, att, propensity-score, matching, inverse-probability-weighting, doubly-robust, overlap, experimental-benchmark]
related: [README.md]
triad:
  theory: true
  papers: true
  practice: false
---

# Propensity-Score Methods for Observational Effect Estimates

*Seed card (Klein 2.3) for the `ds-causal` recipe — `estimate` or `replicate` studies of
an effect from observational data, ideally beside an experimental benchmark.*

## 1. Practitioner intuition

To learn what a job-training programme did for the people who took it, compare them
with people who did not — but the comparison group differs (age, schooling, prior
earnings), and those differences, not the programme, may drive the gap. Regression
adjusts for them by assuming a functional form; the **propensity score** — the
probability of treatment given covariates — instead summarises everything that decided
who was treated into one number, so treated and untreated units with the same score can
be compared as if randomised (under no unmeasured confounding and overlap).

The classic test bed is LaLonde's: a randomised experiment (the NSW programme) gives the
true effect; replacing its control group with survey respondents (PSID, CPS) and asking
non-experimental estimators to recover it shows how wrong they can be — and, in
Dehejia & Wahba's re-analysis, how much better they do when the comparison is restricted
to units that overlap with the treated.

## 2. Math core

| Symbol | Meaning |
|---|---|
| `T ∈ {0,1}`, `Y`, `X` | treatment, outcome (e.g. 1978 earnings), covariates |
| `e(x) = P(T=1 | X=x)` | propensity score |
| `ATT = E[Y(1) - Y(0) | T=1]` | the effect on the treated |

1. Experimental benchmark: `ATT_exp = mean(Y | T=1) - mean(Y | T=0)` in the randomised sample.
2. Matching: for each treated unit, the control(s) with the nearest `e(x)` (caliper, with replacement).
3. IPW (ATT weights): controls weighted by `e(x) / (1 - e(x))`, treated by 1.
4. Doubly robust (AIPW): an outcome model `μ0(x)` plus weighted residuals — consistent if
   either the propensity or the outcome model is right.

## 3. Minimal from-scratch implementation

```python
from sklearn.linear_model import LogisticRegression
e = LogisticRegression(max_iter=1000).fit(X, T).predict_proba(X)[:, 1]
keep = (e > 0.01) & (e < 0.99)                         # overlap trimming, stated
w = np.where(T == 1, 1.0, e / (1 - e))
att_ipw = Y[T == 1].mean() - np.average(Y[T == 0], weights=w[T == 0])
```

Intervals by bootstrapping the whole pipeline (re-fit the propensity model each draw);
every specification is a registered cell, and the experimental benchmark is the sealed
comparison.

## 4. When it pays / when it doesn't

| Regime | Expectation |
|---|---|
| rich pre-treatment covariates incl. lagged outcomes | propensity methods can approach the experimental answer |
| poor overlap (controls unlike the treated) | estimates are driven by a few heavily weighted units; trim and say so |
| unmeasured confounding | no estimator fixes it; sensitivity analysis is the honest output |
| naive difference in means on observational controls | can miss by the effect's whole size, even its sign |

Registrable priors: the experimental benchmark reproduces within a stated tolerance;
the naive observational difference lies outside the benchmark's interval; at least one
propensity estimator's interval contains the benchmark; estimates move by more than
their own interval across specifications (specification dependence).

## 5. References (verify at instantiation)

- LaLonde (1986). Evaluating the econometric evaluations of training programs with experimental data. *American Economic Review* 76(4). https://www.jstor.org/stable/1806062
- Rosenbaum & Rubin (1983). The central role of the propensity score in observational studies for causal effects. *Biometrika* 70(1). doi:10.1093/biomet/70.1.41
- Dehejia & Wahba (1999). Causal effects in nonexperimental studies. *JASA* 94(448). doi:10.1080/01621459.1999.10473858
- Dehejia & Wahba (2002). Propensity score-matching methods for nonexperimental causal studies. *Review of Economics and Statistics* 84(1). doi:10.1162/003465302317331982
- Bang & Robins (2005). Doubly robust estimation in missing data and causal inference models. *Biometrics* 61(4). doi:10.1111/j.1541-0420.2005.00377.x
