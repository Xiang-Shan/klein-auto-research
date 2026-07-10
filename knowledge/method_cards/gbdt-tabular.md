---
title: "Gradient-Boosted Decision Trees for Tabular Data"
type: method-card
domain: ml
status: seed
concepts: [lightgbm, xgboost, catboost, encoder-pairing, monotone-constraints, soft-voting, regularization-defaults, hyperparameter-importance, imbalance-calibration]
related: [../gbdt-hyperparameter-guide.md, ../encoder-comparison.md, ../insights-and-framework.md, glm-pricing.md]
---

# Gradient-Boosted Decision Trees for Tabular Data

*Seed card distilled from the 2026-04 insurance-claims campaign: `../gbdt-hyperparameter-guide.md` (Phase-3 recipes + Optuna importances), `../encoder-comparison.md` (encoder × framework), and `../insights-and-framework.md` (lever order, ensembling, imbalance).*

## 1. Practitioner intuition

On tabular weak-signal data (~10⁴–10⁵ rows, mixed continuous + categorical),
**GBDTs are the default winner** — model choice is the single dominant lever (+0.045 AUC
over an LR floor on the campaign, ~3.4× the next-biggest lever). They handle multi-level
categoricals and non-linear/threshold numeric effects natively, and they discover
interactions through split sequences, so almost no design-matrix engineering is needed.

The three production frameworks — **LightGBM, XGBoost, CatBoost** — land within ~0.002
AUC of each other when each is paired with its preferred encoder. So the real question is
not "which framework?" but **"which framework × encoder × constraint pairing?"** — and
then "soft-vote all three."

Mental model vs a GLM (see `glm-pricing.md`): a GLM needs *you* to supply the
non-linearity; a GBDT needs you to **not interfere** — no binning, no hand interactions,
just hand it the columns.

## 2. Math core

- Additive stagewise model `F_M(x) = Σ_{m=1..M} ν · h_m(x)`, each `h_m` a small
  regression tree, `ν` the learning rate (shrinkage).
- At each stage the new tree fits the **negative gradient** (pseudo-residuals) of the loss
  (log-loss for binary classification): boosting is gradient descent in function space.
- On weak signal, **regularization is the whole game**: shrinkage `ν` + small trees
  (`num_leaves` / `max_depth` / `depth`) + row/column subsampling (~0.7) + L2 leaf penalty
  + a minimum-samples-per-leaf floor.
- **Monotone constraints** restrict the split search so `∂F/∂x_j` keeps a fixed sign — a
  per-feature shape prior. Useful for filing, but only if the sign is *empirically*
  correct (§4).

## 3. Minimal implementation sketch — LightGBM recipe + soft vote

```python
from lightgbm import LGBMClassifier, early_stopping
lgbm = LGBMClassifier(
    n_estimators=2000, learning_rate=0.05,
    num_leaves=15,            # smaller than the default 31 — defaults overfit weak signal
    min_child_samples=20,
    subsample=0.7, subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0,
    monotone_constraints=mvec, monotone_constraints_method="advanced",
    random_state=42, n_jobs=-1, verbose=-1,
)
lgbm.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], callbacks=[early_stopping(50)])

# Close with a UNIFORM cross-family soft vote (campaign global best, 0.6715):
proba = (xgb.predict_proba(X)[:, 1]
         + lgb.predict_proba(X)[:, 1]
         + cb.predict_proba(X)[:, 1]) / 3
```

## 4. When it pays / when it doesn't

**When it pays**
- Tabular weak-signal binary or regression, ~10⁴–10⁵ rows, mixed types. Model choice is
  the dominant lever; native interactions + non-linearity with near-zero FE.

**When it doesn't** (reach for something else — see `../insights-and-framework.md` §5)
- **>500k rows** (DL scaling laws kick in), **multi-modal** (text/image/telematics),
  **very high cardinality** (>1000 levels → entity embeddings beat target encoding), or
  **<50k rows** where **TabPFN v2** zero-shot can beat a tuned GBDT (Grinsztajn 2022;
  Hollmann 2025).

**Encoder pairing — the second-order win once the family is fixed:**

| Framework | Preferred encoder | val_auc |
|---|---|---|
| LightGBM | OHE (+ monotone-advanced) | 0.6671 / **0.6701** |
| XGBoost | ordinal | 0.6689 |
| CatBoost | sklearn `TargetEncoder` (beats native) | 0.6683 |
| **soft-vote** (uniform 1/3) | mixed encoders per learner | **0.6715 (global best)** |

"Native categorical handling" advertised by LGBM/CatBoost is a **small-data myth** here —
OHE / sklearn-target beat it. Use *different* encoders per learner so their errors
de-correlate.

**Regularize the defaults (warning).** LightGBM/XGBoost stock defaults (`num_leaves=31`,
no subsample) were tuned for million-row Kaggle problems and **overfit** weak-signal
50k-row data. Tuning *down* (`num_leaves=15`, `subsample=0.7`, `min_child_samples=20`)
bought +0.013 AUC — this is why HPO is the #2 lever after model choice.

**HP importance per family** (Optuna 50-trial fast pass):
- **LightGBM:** `num_leaves` dominates (15 > 7 > 31 > 63), then `colsample_bytree`;
  `learning_rate` is ~irrelevant with early stopping.
- **XGBoost:** tree size (`max_depth=4`) + `min_child_weight` + `subsample`; smaller trees win.
- **CatBoost:** `random_strength` + `bagging_temperature` dominate; `depth` barely matters
  (symmetric trees behave across 4–8).

**Monotone constraints — verify the empirical sign.** LightGBM `monotone-advanced` gave
the best single-model lift (+0.003) but **only** when the direction matched the data
(`vehicle_age = -1`, `subscription_length = +1` — *reversed* from naive actuarial
"older = riskier" intuition). Wrong sign hurts −0.005. XGB/CatBoost monotone hurt here.

**Imbalance reweighting = calibration poison.** `scale_pos_weight` (XGB), `is_unbalance`
(LGBM), `auto_class_weights="Balanced"` (CatBoost), focal loss, SMOTE, ADASYN — all gave
neutral-to-negative AUC and inflated log-loss 3–10× across *every* family. Keep the
natural distribution; calibrate isotonic post-hoc; threshold-tune the operating point.

**Cross-family soft vote is free dessert.** Uniform 1/3 weights beat Optuna-tuned weights
(0.6715 vs 0.6679 — tuned weights overfit the small val set); a meta-learner stack
underperforms soft voting when val positives < ~10k. Only add a learner if its OOF-pred
correlation with the others is < 0.95 (adding an FT-Transformer hurt by 0.001).

## 5. References

- `../gbdt-hyperparameter-guide.md` — per-family recipes, Optuna importances, failure modes (Phase 3).
- `../encoder-comparison.md` — the full encoder × framework matrix.
- `../insights-and-framework.md` §2, §4, §6 — lever order, framework-selection rules, imbalance/ensemble verdicts.
- Grinsztajn, L., Oyallon, E. & Varoquaux, G. (2022). *Why do tree-based models still outperform deep learning on tabular data?* NeurIPS 2022 Datasets & Benchmarks. [arXiv:2207.08815](https://arxiv.org/abs/2207.08815).
