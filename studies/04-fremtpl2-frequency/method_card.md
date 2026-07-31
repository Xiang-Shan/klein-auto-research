---
type: method-card
domain: "insurance"
status: final
concepts: [poisson-glm, hgbt, exposure-weights, deviance]
related: [../../knowledge/method_cards/glm-pricing.md, ../../knowledge/method_cards/gbdt-tabular.md]
refs_verified: true    # both verified 2026-07-31 (publisher/SSRN indexes)
triad:
  theory: true         # §2: the weighted-frequency equivalence + deviance definition
  papers: true         # refs_verified: true
  practice: true       # §3: pipeline.py realizes it with named kleinlib helpers
---

# Method card — Poisson frequency: GLM vs gradient boosting

> Gate 2 (METHOD), depth **brief**: both methods are the audience's daily tools
> and both have seed knowledge cards; this card records only the study-specific
> math and the falsifiable priors. Deep treatments: `knowledge/method_cards/glm-pricing.md`
> and `knowledge/method_cards/gbdt-tabular.md`.

## 1. Intuition

Claim frequency is a rate: claims per exposure-year. Both models predict that
rate; the honest comparison metric is the same Poisson deviance both training
losses minimize — not RMSE, which a 96%-zeros count target renders meaningless.

## 2. Math core

| Symbol | Meaning |
|---|---|
| n_i, e_i | claim count and exposure of policy i |
| y_i = n_i/e_i | observed frequency |
| μ(x_i) | modeled frequency |

$$ \text{offset-free equivalence:}\quad \arg\min_\mu \sum_i e_i\, d(y_i, \mu(x_i)) \;=\; \arg\max_\mu \sum_i \log \text{Pois}(n_i \mid e_i\,\mu(x_i)) $$

$$ d(y,\mu) = 2\left(y\log\tfrac{y}{\mu} - y + \mu\right) \quad\text{(unit Poisson deviance; } y\log y := 0 \text{ at } y=0\text{)} $$

Fitting on frequency with `sample_weight = exposure` is exactly the classical
offset formulation — the trick both `PoissonRegressor` and
`HistGradientBoostingRegressor(loss="poisson")` support natively. The metric is
the exposure-weighted mean of d over the development fold.

## 3. Minimal implementation plan

Realized in `pipeline.py`: `kleinlib.data.three_way_split` (fixed 60/20/20),
`kleinlib.encoders.build_preprocessor(kind="ohe")` and `kind="native"` for the
RQ3 arm, `sklearn.metrics.mean_poisson_deviance` with exposure weights,
predictions clipped at 1e-6 (deviance needs μ > 0).

## 4. When it pays / when it doesn't — falsifiable priors

| Regime | Prior |
|---|---|
| Raw features, 678k rows | GBDT wins by several × floor (RQ1) — nonlinearities in DrivAge/BonusMalus/Density that a linear score misses |
| GLM given shaping (log-density, splines) | closes a large part, not all, of the gap (RQ2) |
| Native categoricals vs OHE at ≤22 levels | ≈ tie, within 2× floor (RQ3) |

## 5. References (verified)

1. Noll, A., Salzmann, R., Wüthrich, M.V. (2020). "Case Study: French Motor
   Third-Party Liability Claims." SSRN 3164764. ✅ verified 2026-07-31 — the
   canonical freMTPL2 GLM-vs-boosting/nets case study.
2. Wüthrich, M.V., Merz, M. (2022). *Statistical Foundations of Actuarial
   Learning and its Applications.* Springer (open access). ✅ verified
   2026-07-31 — deviance/exposure-weight treatment, Ch. 2, 5–7.
