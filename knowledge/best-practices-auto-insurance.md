---
title: "Best Practices for Auto-Insurance Tabular Classification"
type: synthesis
domain: insurance
status: ported
source: "ancestor model-survey campaign (private lab), docs/best_practices_auto_insurance.md (215-experiment campaign, 2026-04)"
concepts: [gbdt-trio, soft-voting, isotonic-calibration, imbalance-treatment, monotone-constraints, encoder-by-family, feature-engineering, optuna-hpo, threshold-tuning, weak-signal]
related: [insights-and-framework.md, gbdt-hyperparameter-guide.md, encoder-comparison.md]
---

# Best Practices for Auto-Insurance Tabular Classification

> Ported from the 2026-04 model-survey campaign (215 experiments, insurance-claims, best val_auc 0.6715). Original lives in the campaign repo.

**Distilled from 215 experiments on the Kaggle insurance-claims dataset (litvinenko630, ~58k rows, 6.4% positive class, 14.6:1 imbalance).**
This is the answer to **Q2** in the user's research questions and the consolidation of all 5 phases.

---

## TL;DR — the recommended procedure

1. **Fix data first** (Phase 0). Audit string-encoded booleans, weird columns, and known-bad encodings. Skipping this contaminates every downstream metric. On this dataset, `is_*` Yes/No cols were string dtype — fixing it cost 2h and saved every later comparison.
2. **Build a `lib/` package**: `data.py`, `eval.py`, `encoders.py`. Make `train.py` a thin per-experiment surface (≤80 lines). Without this, experiments don't compose.
3. **Sweep four model families with sane defaults** (~20–30 quick experiments). Identify which family has headroom for *this* dataset. On insurance-claims: GLMs cap at ~0.65, sklearn breadth caps at ~0.67, GBDT trio reaches 0.67–0.6715, deep tabular caps at 0.67. **GBDT wins**.
4. **HPO the best 2–3 families** with Optuna. 50 trials per family (fast pass + honest 3-fold CV pass). On insurance-claims, this got LGBM from 0.628 → 0.6701.
5. **Cross-family ensemble** at the end. Soft voting of XGB + LGBM + CatBoost winners with uniform 1/3 weights = best-honest model. +0.001–0.003 over single best is reliable.
6. **Calibration + threshold tuning** for actuarial use. `CalibratedClassifierCV(method='isotonic')` if the target is calibrated probabilities; otherwise threshold-tune for max F1 or fixed precision.

The full procedure that produced our best model (val_auc=0.6715, soft vote of 3 GBDTs):

```python
# Fixed: sklearn 1.3+, lightgbm 4.x, xgboost 2.x, catboost 1.2.5+
# Train each base learner with the recipe in gbdt-hyperparameter-guide.md, on the full train set.
# At inference: average the predict_proba outputs.
ensemble_proba = (xgb.predict_proba(X) + lgb.predict_proba(X) + cb.predict_proba(X)) / 3
```

---

## Q1 — Priority order of optimization levers

**Empirical answer (from Phase 5 ablations on best-LGBM anchor val_auc=0.6701):**

| Lever | ΔAUC vs anchor | Anchored ablation |
|---|---|---|
| Model selection | **−0.0448** | LR default (0.6253) → LGBM tuned (0.6701) |
| HPO | **−0.0131** | LGBM defaults (0.6570) → LGBM tuned (0.6701) |
| Feature selection | −0.0052 | LGBM top-15 features (0.6649) → all features (0.6701) |
| Encoder choice | −0.0043 | LGBM + ordinal (0.6658) → LGBM + OHE (0.6701) |
| Feature engineering | −0.0019 | LGBM no ratios (0.6682) → LGBM + 3 ratios (0.6701) |

**Verdict:** Model selection dominates by ~3.4× over the next lever (HPO). The doctrine "model breadth before depth" is empirically vindicated on this dataset.

**Caveat for GLMs:** the priority order *differs* for linear models. For LR, encoder choice is the single biggest lever (OHE 0.6255 vs ordinal 0.4039 = ΔAUC=−0.222 — a wrong encoder makes LR essentially unusable on nominal cats). For trees, encoder choice is small.

---

## Q2 — Best-practice procedure (this document)

See the TL;DR above. Concrete commands:

```bash
# Phase 0 (foundation)
uv add "scikit-learn>=1.4" "imbalanced-learn>=0.12" "category-encoders>=2.6" "optuna>=3.5" "statsmodels>=0.14"
# Phase 3 (GBDT trio)
uv add "lightgbm>=4.3" "xgboost>=2.0" "catboost>=1.2.5"
# Phase 4 (deep tabular, optional and non-decisive on small datasets)
uv add "torch>=2.3" "pytorch-tabnet>=4.1" "rtdl-revisiting-models" "shap>=0.45"
```

---

## Q3 — GBDT hyperparameters and initial values

See `gbdt-hyperparameter-guide.md` for the long-form answer.

**Quick recipe per family (all confirmed by Phase 3 + Phase 5 ablations):**

```python
# LightGBM (winning family on this dataset)
LGBMClassifier(
    n_estimators=2000, learning_rate=0.05, num_leaves=15, min_child_samples=20,
    subsample=0.7, subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0,
    monotone_constraints=mvec, monotone_constraints_method="advanced",
    random_state=42, n_jobs=-1, verbose=-1,
)  # + early_stopping(50) on a fixed val split

# XGBoost
XGBClassifier(
    n_estimators=2000, learning_rate=0.05, max_depth=4, min_child_weight=5,
    reg_lambda=1.0, subsample=0.7, colsample_bytree=0.7,
    tree_method="hist", eval_metric="logloss", early_stopping_rounds=50,
    random_state=42, n_jobs=-1,
)

# CatBoost
CatBoostClassifier(
    iterations=2000, learning_rate=0.05, depth=6, l2_leaf_reg=3.0,
    bagging_temperature=1.0, random_strength=1.0, rsm=0.7,
    early_stopping_rounds=50, eval_metric="Logloss",
    random_seed=42, thread_count=-1, verbose=0,
)
```

---

## Q4 — Do we need feature engineering?

**Empirical answer:** *Some*, not much.

| Feature regime | val_auc |
|---|---|
| LGBM raw (no ratios) | 0.6682 |
| LGBM + 3 Phase-0 ratios (`power_to_weight`, `torque_per_litre`, `safety_features_count`) | **0.6701** |
| LGBM + ratios + 3 hand-built interactions (vage×sublen, torque×power, disp/weight) | 0.6660 |

**Verdict:** The 3 invariant ratio features in `prepare.py` (Phase 0) lift +0.0019 AUC over no-FE — small but free. **Adding more interactions actively hurts** on this small dataset, because they introduce overfitting on 50k rows × 6.4% positives. GBDT's auto-interaction via splits already discovers most useful interactions.

**Rule:** add 2–4 invariant, domain-motivated ratio features. Don't add hand-crafted interactions if a tree model already has access to the constituent features.

---

## Q5 — Should we bin numerical features?

**Empirical answer:** **No — don't bin for GBDT.**

| Treatment | val_auc |
|---|---|
| LGBM continuous numerics (best) | 0.6701 |
| LGBM + KBinsDiscretizer(n_bins=10, strategy=quantile) | 0.6675 |
| LGBM + KBinsDiscretizer(n_bins=50) | 0.6642 |

**Why:** GBDT splits already discretize internally — pre-binning throws away information about where to put split points and can mis-place them at quantile boundaries that don't match the gradient signal.

**Caveat:** for *linear* models (LR/SGD), binning numerics into 5–10 quantiles can help capture non-linearity. We tested this in Phase 1 (KBinsDiscretizer + LR) and it gave +0.001 AUC over raw — small but positive. For trees: don't bin.

---

## Q6/Q7/Q8 — Categorical encoder by family

See `encoder-comparison.md` for the long-form answer.

**Verdict per family (val_auc on best-tuned model):**

| Encoder | LR | XGBoost | LightGBM | CatBoost |
|---|---|---|---|---|
| OHE (min_freq=20) | **0.6255** | 0.6678 | **0.6671** (no mono) / 0.6701 (mono) | 0.6669 |
| Ordinal | 0.4039 (catastrophic) | **0.6689** | 0.6658 | — |
| Target (sklearn 1.3+) | 0.6235 | 0.6685 | 0.6626 | **0.6683** |
| Native (`category` dtype) | n/a | 0.6670 | 0.6598 | 0.6604 |
| Frequency (count) | 0.5179 | — | — | — |
| Hashing (64 dim) | 0.6259 | — | — | — |

**Key findings:**
- **Linear models**: OHE always wins. **Never use ordinal or frequency** for nominal cats — catastrophic 0.10–0.22 AUC loss.
- **XGBoost**: ordinal beats OHE by 0.001 (surprise). Native cat support is a tie at best.
- **LightGBM**: OHE beats native cat by 0.007. Native is a "small-dataset myth" on ~50k rows.
- **CatBoost**: TargetEncoder beats native cat by 0.002. Sklearn's smoothed target is more robust than CatBoost's built-in.
- **High-cardinality treatment** (`region_code` C22): for linear, target-with-smoothing or JamesStein. For trees, all encoders converge within ±0.003. Hashing matches OHE if `n_features=64`.

**Q8 (encoder importance):** for trees, **model choice (+0.045)** ≫ **encoder choice (±0.005)**. For LR, encoder choice IS the model choice — it's catastrophic if wrong.

**Cross-family ensembling:** use *different* encoders per family — the Phase 3 winner used XGB-ordinal + LGBM-OHE-monotone + CatBoost-target. Encoder diversity compounds with framework diversity.

---

## Imbalance treatment

**Universally bad on this dataset:** `class_weight='balanced'` (LR), `scale_pos_weight` (XGB), `is_unbalance` (LGBM), `auto_class_weights='Balanced'` (CatBoost), focal loss, SMOTE, ADASYN. All give marginal AUC change but ruin calibration (logloss 3–10× worse).

**The right treatment:** `class_weight=None` (i.e. don't treat). Train the model on the natural distribution. Calibrate post-hoc with `CalibratedClassifierCV(method='isotonic')` if you need probabilities. Threshold-tune post-hoc if you need labels.

**Threshold targets** for an actuarial use case (best soft-vote 3-fam on this dataset):
- Max-F1 threshold ≈ 0.08, F1 ≈ 0.18 (low because the dataset has weak signal)
- Lift@10% ≈ 1.6 (modest — picking top decile gets 1.6× the base rate of true positives)

---

## When NOT to bother with deep tabular

For datasets with <100k rows and weak signal (PR-AUC < 0.15), deep tabular models (TabNet, FTTransformer) cap at single-GBDT performance and never beat the GBDT trio ensemble. Phase 4 (43 deep tabular experiments) confirmed this:
- Best TabNet: 0.6633 (gamma=1.0). Tuned 25-config sweep.
- Best FTTransformer: 0.6695 (n_blocks=3, d_block=96, all-zero dropout). Tuned 15-config sweep.
- Both below the cross-family soft vote (0.6715).

**Cost:** TabNet ~30–250s/fit, FTTransformer ~60–250s/fit on M4Max MPS. LGBM cost: ~2s/fit on CPU. **Skip deep tabular** for datasets in this regime.

If forced to use deep tabular, **FTTransformer with all-zero dropouts beats TabNet on weak-signal small data** by ~0.006 AUC.

---

## Multi-session execution notes

- **Resume protocol:** read `MEMORY.md` index → read `results.tsv` and `tail -50 run.log` → `git status` + `git log --oneline -20` → identify current phase from row count.
- **Phase boundaries** are natural breakpoints. Save state via git + memory entries.
- **Memory entries** capture cross-session insights; `docs/` capture long-form numbers; `results.tsv` is the audit trail.
- **Hardware acceleration**: CPU `n_jobs=-1` for sklearn/GBDT (no MPS support in their wheels); MPS for Phase 4 PyTorch only. CUDA-only frameworks (XGB/LGBM/CatBoost GPU) fall back to CPU on macOS.
- **Phase wall-clock** (M4Max, 14-core CPU): Phase 0 = 2h, Phase 1 = 8h, Phase 2 = 10h, Phase 3 = 24h, Phase 4 = 12h (with MPS), Phase 5 = 4h. Total ≈ 60h across multiple sessions.

---

## Final ranked findings

1. **GBDT trio dominates** for tabular weak-signal binary classification on ~50k rows.
2. **LightGBM with `monotone_constraints_method='advanced'`** is the strongest single model when you can verify the empirical sign of monotonic priors.
3. **Cross-family soft voting** (uniform 1/3 weights of XGB + LGBM + CatBoost winners) reliably beats any single GBDT by +0.001–0.003.
4. **Stacking with a meta-learner < soft voting** when the val set has <5k positives (the meta over-fits OOF predictions).
5. **Imbalance treatments are dead ends** across all model families. Use `class_weight=None`, calibrate post-hoc, threshold-tune for the operating point.
6. **Encoder choice matters mostly for linear models**; for trees it's a ±0.005 tweak.
7. **Deep tabular doesn't pay** below ~100k rows.
8. **3 invariant ratio features** in `prepare.py` give +0.002 AUC; hand-built interactions on top hurt.
9. **Feature selection (top-15 by LGBM importance)** loses 0.005 AUC vs all features. Save it for explainability, not optimization.
10. **HPO matters but is dwarfed by model choice** (+0.013 vs +0.045 ΔAUC). Get the family right first; tune second.

---

## Files

- `gbdt-hyperparameter-guide.md` — Q3 long-form (per-family Optuna importance, copy-paste recipe)
- `encoder-comparison.md` — Q6/Q7/Q8 long-form (cross-family encoder ranking)
- `best-practices-auto-insurance.md` — this document (Q2 procedure synthesis)
- `results.tsv` — 215 experiments, the audit trail (campaign repo)
- `MEMORY.md` (in `.claude/projects/.../memory/`) — index of cross-session memories
