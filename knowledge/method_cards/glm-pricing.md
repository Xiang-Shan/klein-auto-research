---
title: "GLM / Logistic Regression for Insurance Risk"
type: method-card
domain: insurance
status: seed
concepts: [logistic-regression, link-function, splines, binning-linear, encoder-criticality, isotonic-calibration, threshold-tuning, weak-signal, class-weight]
related: [../best-practices-auto-insurance.md, ../encoder-comparison.md, gbdt-tabular.md]
---

# GLM / Logistic Regression for Insurance Risk

*Seed card. Campaign anchors come from the 2026-04 insurance-claims model survey; see `../best-practices-auto-insurance.md` and `../encoder-comparison.md`. A study's Gate-2 `method_card.md` instantiates this against that study's data.*

## 1. Practitioner intuition (for actuaries)

A logistic regression is **the GLM you already price with** — same machinery as your
Poisson-frequency or Gamma-severity models, just with a Bernoulli response and a logit
link, aimed at P(claim) instead of a count or an amount.

- The **linear predictor** `η = β0 + Σ βj·xj` is a score on the log-odds scale.
- The **link** squashes that unbounded score into a probability.
- Each `βj` is a **log odds-ratio**: holding all else equal, a one-unit move in `xj`
  multiplies the odds of a claim by `e^βj`. An underwriter can read the coefficient table.

Because the score is linear, the model is **monotone and additive by construction** in
every feature. That is its blessing — transparent, filable, monotone without extra
constraints — and its curse: it cannot see a U-shape, an interaction, or a threshold
unless *you* put it in the design matrix.

## 2. Math core

- Model: `y_i ~ Bernoulli(μ_i)`, `logit(μ_i) = η_i = β0 + Σ_j βj·x_ij`, so
  `μ_i = 1 / (1 + e^{-η_i})`.
- Fit by maximizing the Bernoulli log-likelihood (equivalently, minimizing log-loss),
  via IRLS or L-BFGS. An L2 penalty (ridge; sklearn's `C` is inverse strength) shrinks
  `β` toward 0 and stabilizes weak-signal fits.
- **Non-linearity must be engineered into the design matrix** — the model has no auto-
  interaction and no auto-curvature:
  - **splines** (natural cubic / B-spline basis) give a continuous feature a smooth
    non-linear response;
  - **quantile binning** (5–10 bins) is the blunt-instrument version of the same idea;
  - **explicit interaction columns** `x_j·x_k` because the GLM will never find them itself.
- **Calibration ≠ discrimination.** AUC measures ranking; a GLM can rank acceptably yet
  be biased in probability. Post-hoc **isotonic regression** re-maps scores to observed
  frequencies with a monotone step function — the actuarially load-bearing step.

## 3. Minimal implementation sketch

```python
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, SplineTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

pre = ColumnTransformer([
    # OHE is non-negotiable for nominal cats in a linear model (see §4):
    ("cat", OneHotEncoder(min_frequency=20, handle_unknown="infrequent_if_exist"), cat_cols),
    # the model's ONLY path to curvature — splines on the top few numerics:
    ("num", SplineTransformer(n_knots=5, degree=3), spline_cols),
    # (optional) explicit interaction columns, built deterministically in prepare.py
])
glm = Pipeline([("pre", pre),
                ("lr", LogisticRegression(C=1.0, class_weight=None, max_iter=2000))])
# Calibrate probabilities post-hoc (isotonic). NEVER reweight the loss for imbalance:
model = CalibratedClassifierCV(glm, method="isotonic", cv=5).fit(X_tr, y_tr)
```

The diff surface stays thin: the encoder + spline + interaction choices *are* the
experiment; everything else is library.

## 4. When it pays / when it doesn't

**When it pays**
- **Filing and audit.** Coefficients are odds-ratios an underwriter and a regulator can
  read; monotone in each feature by construction.
- **Calibration-first use.** Pricing attaches a number to each policy, not just a rank
  order — the campaign's best Brier came from calibrated models, and calibration is
  "where the actuarial value is" (insights §6.4).
- **A transparent anchor** for the whole study — Study 00 uses exactly this as its
  familiar baseline.

**When it doesn't**
- **Discrimination ceiling.** On insurance-claims the best LR reached **val_auc 0.6528**
  vs tuned LGBM **0.6701** — the GLM leaves ~0.017 AUC on the table because it cannot
  auto-discover interactions.
- **You must hand-build the non-linearity.** Splines + interactions are *mandatory* FE
  for LR (+0.025 AUC in the campaign) — the exact opposite of the "don't interfere" rule
  for trees.

**The encoder is the whole ballgame for a GLM** (campaign, nominal cats):

| Encoder on nominal cats | LR val_auc |
|---|---|
| OHE (min_freq=20) | **0.6255** |
| Ordinal | 0.4039 (catastrophic) |
| Frequency (count) | 0.5179 |

Ordinal encoding tells the linear model that "region 7 > region 3" *as a quantity* — a
~0.22-AUC self-inflicted wound that makes LR essentially unusable. **Never ordinal- or
frequency-encode nominal categories for a linear model.** (For trees this same choice is
±0.005 noise — the criticality is family-specific.)

**Calibration-first doctrine** (campaign-wide): `class_weight=None` + isotonic
calibration + post-hoc threshold tuning. Every imbalance reweighting tried
(`class_weight="balanced"`, SMOTE, ADASYN) moved AUC only marginally and **ruined
calibration** (log-loss 3–10× worse). Reweighting the loss is calibration poison.

**Campaign anchor trajectory** (the GLM story in Study 00):

| Step | val_auc |
|---|---|
| LR + OHE baseline | 0.6255 |
| LR + splines + interactions + isotonic (Phase-1 best) | **0.6528** |

That is ~75% of the way from the LR floor to the HGBT baseline (~0.6629) — bought
entirely with feature engineering + calibration, no change of model family.

## 5. References

- `../best-practices-auto-insurance.md` — Q1 lever order, the imbalance verdict, threshold targets (this campaign).
- `../encoder-comparison.md` — full per-family encoder table (the 0.4039 ordinal result and the high-cardinality treatment).
- `../insights-and-framework.md` §2.3, §6.2–6.4 — the family-relative FE / binning / calibration asymmetries.
- de Jong, P. & Heller, G. Z. (2008). *Generalized Linear Models for Insurance Data.* Cambridge University Press (International Series on Actuarial Science).
- Ohlsson, E. & Johansson, B. (2010). *Non-Life Insurance Pricing with Generalized Linear Models.* Springer (EAA Series).
