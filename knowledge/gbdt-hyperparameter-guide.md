---
title: "GBDT Hyperparameter Guide (insurance-claims, Phase 3)"
type: reference
domain: ml
status: ported
source: "ancestor model-survey campaign (private lab), docs/gbdt_hyperparameter_guide.md (215-experiment campaign, 2026-04)"
concepts: [lightgbm, xgboost, catboost, optuna-importance, monotone-constraints, tree-size, subsample, early-stopping, soft-voting]
related: [best-practices-auto-insurance.md, encoder-comparison.md, insights-and-framework.md]
---

# GBDT Hyperparameter Guide (insurance-claims, Phase 3)

> Ported from the 2026-04 model-survey campaign (215 experiments, insurance-claims, best val_auc 0.6715). Original lives in the campaign repo.

**Question Q3 answer.** Distilled from 60 Phase-3 experiments (XGBoost: 23, LightGBM: 20, CatBoost: 15, plus 2 cross-family ensembles) on the 47k-row, 6.4%-positive insurance-claims dataset.

## TL;DR — what to set on a similar tabular weak-signal binary-classification problem

| Family | Best single-model val_auc | Recipe |
|---|---|---|
| XGBoost | **0.6689** (Exp 114) | `tree_method='hist'`, `max_depth=4`, `min_child_weight=5`, `learning_rate=0.05`, `subsample=0.7`, `colsample_bytree=0.7`, `reg_lambda=1`, `n_estimators=2000` + `early_stopping_rounds=50`, **`ordinal` encoder for cats** |
| LightGBM | **0.6701** (Exp 129) | `num_leaves=15`, `min_child_samples=20`, `learning_rate=0.05`, `subsample=0.7`, `subsample_freq=1`, `colsample_bytree=0.7`, `reg_lambda=1`, `n_estimators=2000` + `early_stopping(50)`, **OHE encoder**, **`monotone_constraints` with `_method='advanced'`** on the 1–2 most monotonic numerics |
| CatBoost | **0.6683** (Exp 145) | `depth=6`, `learning_rate=0.05`, `l2_leaf_reg=3`, `bagging_temperature=1`, `random_strength=1`, `rsm=0.7`, `iterations=2000` + `early_stopping_rounds=50`, **TargetEncoder** (sklearn 1.3+) — beats CatBoost's own native cat handling on this data |
| **Cross-family soft vote** | **0.6715 GLOBAL BEST** (Exp 151) | Average proba of the three winners above. +0.0014 over LGBM-monotone alone. Stacking with LR-meta is *worse* (0.6685) — uniform weights win on this small val. |

## Importance ranking per family (from Optuna 50-trial fast-pass importances)

### XGBoost (Exp 107)

| Param | Importance |
|---|---|
| reg_alpha | 0.640 |
| gamma | 0.081 |
| subsample | 0.078 |
| max_depth | 0.068 |
| min_child_weight | 0.051 |
| reg_lambda | 0.043 |
| learning_rate | 0.032 |
| colsample_bytree | 0.008 |

**Note on reg_alpha dominance:** likely a search-range artefact (range 1e-6..10 logscale). Hand-tuning showed `min_child_weight` and `subsample` as the highest-leverage knobs.

### LightGBM (Exp 125, fast pass)

| Param | Importance |
|---|---|
| num_leaves | 0.669 |
| colsample_bytree | 0.253 |
| subsample | 0.048 |
| learning_rate | 0.019 |
| reg_lambda | 0.006 |
| min_child_samples | 0.004 |
| reg_alpha | 0.001 |

**Verdict:** `num_leaves` is by far the most important LGBM HP — `15` beat `7` (-0.001), `31` (-0.005), `63` (much worse). Colsample (0.5–0.7) is second. Don't waste budget on `learning_rate` if you have early stopping.

### LightGBM honest CV (Exp 126) — different ranking

| Param | Importance |
|---|---|
| learning_rate | 0.485 |
| num_leaves | 0.266 |
| reg_lambda | 0.123 |
| colsample_bytree | 0.073 |
| subsample | 0.034 |
| min_child_samples | 0.019 |

The honest pass values `learning_rate` more (smaller lr → more iterations → more reg-via-shrinkage). Practically: with early stopping, lr is interchangeable with `n_estimators` so its "importance" reflects search overshoot, not true sensitivity.

### CatBoost (Exp 147)

| Param | Importance |
|---|---|
| random_strength | 0.403 |
| learning_rate | 0.243 |
| bagging_temperature | 0.185 |
| l2_leaf_reg | 0.065 |
| depth | 0.053 |
| rsm | 0.051 |

**Verdict:** CatBoost-specific knobs (`random_strength`, `bagging_temperature`) dominate. `depth` is barely important — CatBoost's symmetric trees behave well across 4–8.

## Initial values for a fresh dataset (~50k rows, weak signal, imbalanced)

```python
# XGBoost
xgb = XGBClassifier(
    n_estimators=2000,
    learning_rate=0.05,
    max_depth=4,
    min_child_weight=5,
    subsample=0.7,
    colsample_bytree=0.7,
    reg_lambda=1.0,
    tree_method="hist",
    eval_metric="logloss",
    early_stopping_rounds=50,
    random_state=42,
    n_jobs=-1,
)
# Encoder: prefer ordinal > target > native > OHE for XGB

# LightGBM
lgbm = LGBMClassifier(
    n_estimators=2000,
    learning_rate=0.05,
    num_leaves=15,           # smaller than the default 31
    min_child_samples=20,
    subsample=0.7,
    subsample_freq=1,        # required for subsample to take effect
    colsample_bytree=0.7,
    reg_lambda=1.0,
    random_state=42,
    n_jobs=-1,
    verbose=-1,
)
# Encoder: OHE > target > ordinal > native (surprise: native_cat hurt by 0.004)

# CatBoost
cb = CatBoostClassifier(
    iterations=2000,
    learning_rate=0.05,
    depth=6,
    l2_leaf_reg=3.0,
    bagging_temperature=1.0,
    random_strength=1.0,
    rsm=0.7,
    early_stopping_rounds=50,
    eval_metric="Logloss",
    random_seed=42,
    thread_count=-1,
    verbose=0,
)
# Encoder: target > OHE ≈ native (TargetEncoder beat CatBoost's own native by 0.002)
```

## Knobs that *don't* matter on this dataset (with early stopping)

- `learning_rate` (anything in 0.02–0.2 converges to within ±0.001)
- `reg_lambda` for XGB and LGBM (flat curve)
- `gamma`, `reg_alpha` for XGB (second-order)
- `boosting_type` for CatBoost: Plain > Ordered (-0.003)

## Knobs that DO matter

- **Tree size**: `max_depth` for XGB, `num_leaves` for LGBM, `depth` for CatBoost. **Smaller wins** on weak-signal data — XGB d=4 > d=15 (-0.013), LGBM nleaves=15 > nleaves=63 (-0.005), CatBoost d=6 > d=8 (-0.002).
- **Regularization sample size**: `min_child_weight` (XGB), `min_child_samples` (LGBM). 5–20 is the sweet spot.
- **Subsample/colsample stochasticity**: 0.7 wins for both row + column sampling. 1.0 (no subsample) is reliably worse; 0.5 is too aggressive.
- **`monotone_constraints`** with `method='advanced'` for LGBM only — gave +0.003 (best single-model lift in Phase 3) when the constraint direction matched the empirical slope (vehicle_age=-1, subscription_length=+1; reversed from naive actuarial intuition!). XGB/CatBoost monotone *hurt* on this dataset.

## Failure modes worth flagging

- **`class_weight`-equivalents kill calibration**: `scale_pos_weight=14.6` (XGB), `is_unbalance=True` (LGBM), `auto_class_weights="Balanced"` (CatBoost) all gave neutral-to-negative AUC and inflated logloss 3–10×. Same pattern as Phase 1 LR `class_weight=balanced`. Keep imbalance untreated; tune threshold post-hoc.
- **DART boosting hurts in both XGB and LGBM**: -0.001 to -0.005, slower, and miscalibrated (LGBM DART logloss=0.65 vs gbdt 0.23). Skip unless you specifically want random feature dropout.
- **GOSS (LGBM)** dropped 0.018 — gradient-sampling discards too much signal on weak-signal data.
- **Stacking with LR-meta < soft voting** on this dataset (0.6685 vs 0.6715). The 3-fold OOF stack train set has only ~14k positives split across 3 folds — meta-learner over-fits the OOF predictions. Soft voting with uniform 1/3 weights is better.
- **Combo experiments rarely stack additively**: LGBM monotone (0.6701) + target encoder (0.6684) → combo 0.6666 (-0.003). LGBM Optuna-HPs + monotone → 0.6664 (-0.004). Pick one win and stop, or carefully verify each combination.

## Generalization advice

For a new tabular weak-signal binary classification dataset:

1. Start with the LightGBM recipe above. It's the most likely single-family winner.
2. If your dataset has strong monotonic priors (recency, frequency, magnitude), try `monotone_constraints` with `method='advanced'`. **Check empirical sign first — actuarial intuition often gets the direction wrong.**
3. Run a 50-trial Optuna fast-pass on each family. Don't bother with honest CV — the rank-order it produces is similar to the fast pass and costs 5–10× more wall-clock.
4. **Always close with cross-family soft voting** of the 3 GBDT winners. +0.001–0.003 over single-family best is reliable.
5. Stacking with a meta-learner only beats soft voting when you have ≥10× more data than we have here.

## Wall-clock budget (M4Max, 14-core CPU)

| Phase | Wall-clock |
|---|---|
| 23 XGB experiments | ~6 minutes total (most experiments <0.5s; one Optuna 50tr=35s; honest CV 100tr=236s) |
| 20 LGBM experiments | ~17 minutes (Optuna honest CV took 867s alone) |
| 15 CatBoost experiments | ~5 minutes (faster wheel; default thread_count saturates 14 cores) |
| 2 cross-family ensembles | ~10 seconds |

CatBoost is fastest per experiment in this row count. LGBM is fastest absolute on early-stopping cases.
