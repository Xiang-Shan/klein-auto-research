---
title: "Insights & Framework — A Meta-Synthesis"
type: synthesis
domain: ml
status: ported
source: "ancestor model-survey campaign (private lab), docs/insights_and_framework.md (215-experiment campaign, 2026-04)"
concepts: [framework-priority, model-selection, gbdt-selection, deep-learning-tabular, imbalance-calibration, cross-family-ensemble, monotone-constraints, tabpfn, encoder-family-relativity]
related: [best-practices-auto-insurance.md, gbdt-hyperparameter-guide.md, encoder-comparison.md]
---

# Insights & Framework — A Meta-Synthesis

> Ported from the 2026-04 model-survey campaign (215 experiments, insurance-claims, best val_auc 0.6715). Original lives in the campaign repo.

**Companion to:** `best-practices-auto-insurance.md`, `gbdt-hyperparameter-guide.md`, `encoder-comparison.md`.
**Anchored in:** the 215-experiment model-survey campaign (branch `experiments/model-survey`, ending at commit `6cf1d3c`) on the Kaggle insurance-claims dataset.
**Purpose:** the per-phase docs distilled the **numbers**. This document distills the **patterns of reasoning** — what to do on the next dataset *before* any experiments are run.

---

## 1. Why this document exists

The campaign produced 215 numbers and three deliverable docs. Each per-phase doc answers one of the user's empirical questions (Q1–Q8) with concrete AUC deltas. But the *transferable* part — the framework priorities, the GBDT-choice heuristics, the when-to-deep-learning rules — lives at one level above. Without it, the next dataset starts from scratch and re-discovers the same lessons.

This doc captures three things:
1. The framework priority order across the four optimization axes (model, FE, encoder, HPO) — generalized.
2. A decision rule for choosing among LightGBM / XGBoost / CatBoost.
3. When deep-learning frameworks become the right choice for tabular data — cross-checked against 2024–2025 literature.

It also calls out what changes about these answers when the domain shifts to insurance specifically.

---

## 2. The four priority axes (generalizing the user's Q1)

### 2.1 Empirical priority on this dataset

Phase 5 ran six anchored ablations starting from the best LGBM (`val_auc=0.6701`). Each ablation held the other levers at their best setting and varied only one. The resulting envelope:

| Lever | Worst-version | Best-version | ΔAUC |
|---|---|---|---|
| **Model selection** | LR default = 0.6253 | LGBM tuned = 0.6701 | **+0.045** |
| **HPO** | LGBM default = 0.6570 | LGBM tuned = 0.6701 | **+0.013** |
| **Feature selection** | top-15 features = 0.6649 | all features = 0.6701 | +0.005 |
| **Encoder** | ordinal = 0.6658 | OHE = 0.6701 | +0.004 |
| **Feature engineering** | no ratios = 0.6682 | +3 ratios = 0.6701 | +0.002 |

Order: **Model ≫ HPO > FS ≈ Encoder > FE** (for tree models on weak-signal small data).

The model lever dominates the next-biggest by ~3.4×. That ratio is the headline of this entire campaign.

### 2.2 Why this order, mechanistically

- **Model = upper-bound on the inductive bias.** The wrong family caps you forever. Trees handle multi-level cats + non-linear numerics natively; linear can't unless you spline+interact manually. Once family is fixed, the model has set the ceiling.
- **HPO = unlock the bias you chose.** The defaults in LightGBM (`num_leaves=31`, no row-subsample) were tuned for million-row Kaggle problems and over-fit weak-signal 50k-row data. Tuning down (`num_leaves=15`, `subsample=0.7`, `min_child_samples=20`) unlocked +0.013 AUC. HPO is just realizing the family's potential.
- **FS = reduce variance after bias is fixed.** Trees handle redundant features fine; FS is mostly an explainability lever. The 5-point-loss from going to top-15 says "a few features are doing 99% of the lifting", which matters for interpretation, not optimization.
- **Encoder = noise term once bias is fixed.** For trees, ±0.005. The tree's split-flexibility absorbs encoding choice. (For *linear*, we'll see, this completely flips.)
- **FE = competing with the model's auto-discovery.** GBDT already finds interactions via splits. Hand-built interactions add noise. Invariant ratios (physical meaning, dimensional reduction) are the safe exception.

### 2.3 The "priority depends on family" caveat

The same Phase 5 numbers re-pivoted by model family tell a different story:

```
For LR (Phase 1 best 0.6528):
  Encoder:      OHE 0.6255 vs ordinal 0.4039 → ΔAUC = 0.222 (CATASTROPHIC if wrong)
  FE (splines): +0.005 (meaningful — LR has no auto-interaction)
  HPO (C):      ±0.001 (flat curve)
  → Order:      Encoder ≫ FE > HPO

For LGBM (Phase 3 best 0.6701):
  Encoder:      OHE 0.6671 vs ordinal 0.6658 → ΔAUC = 0.004 (noise)
  FE (ratios):  +0.002 (small)
  HPO (TPE):    +0.013 (matters)
  → Order:      HPO > FE > Encoder
```

The framework is **family-relative**. A linear model needs you to do the non-linearity for it (encoder, splines, interactions). A tree model needs you to *not interfere* (no binning, no hand interactions, just give it the columns).

### 2.4 The framework guideline (the recommendation)

```
1. Foundation correctness     — no AUC budget; bug fixes are infinite ROI
2. Family screening           — ~20 quick experiments, sane defaults, all 4 families
3. HPO of top-2 families      — Optuna 50 trials each (fast pass + honest CV)
4. Cross-family ensemble      — uniform soft vote of family winners
5. Calibration + threshold    — post-hoc; for actuarial probability quality
6. Light FE (ratios only)     — skip if model already over-fits
7. Encoder sweep ONLY         — for linear or boundary cases
8. Feature selection LAST     — interpretability artifact, not optimizer
```

Spend 80% of compute on (2)+(3). Treat (4)+(5) as free dessert. The discipline is to **resist the urge to do (6)/(7)/(8) before (2)/(3)** — they feel productive but aren't on the critical path.

---

## 3. Insurance-tabular specifics (industry view)

### 3.1 What insurance datasets share

- **~10⁴–10⁵ rows.** Regulatory + segmentation limits. You rarely have a million policy-years of clean data.
- **5–25% positive class** (claim, fraud, churn). Moderate to severe imbalance, but not extreme.
- **Mixed feature types.** Continuous (vehicle_age, premium), high-cardinality nominal (region_code, model), monotonic priors (recency, frequency, severity).
- **Calibrated probabilities matter.** Actuarial pricing wants P(claim), not just rank. AUC alone is not enough.
- **Regulatory pressure for explainability.** SHAP, monotone constraints, business-rule consistency must hold up in audit.

### 3.2 What this changes vs generic Kaggle

| Generic Kaggle priority | Insurance priority shift |
|---|---|
| Maximize AUC | AUC + Brier + lift@decile + monotone-violation count |
| Stack everything | Stack 2–3 GBDTs + ONE simple model (LR or HGBT) for sanity baseline |
| Heavy feature engineering | Light FE — physical/dimensional ratios only, never hand-interactions |
| Big DL ensembles | DL only if you have >500k policies AND multi-modal data |
| HPO budget = max | HPO budget cropped at 100 trials — diminishing returns past that on weak signal |

### 3.3 Modeling priority for insurance (the doctrine)

1. **Foundation.** Audit categorical encodings. Fix Yes/No string-dtype bugs. Build `lib/data.py` with seeded splits and `random_state=42`. *On this study, the `is_*` Yes/No fix was worth ~0.005 AUC and silently mis-encoded 19 columns until Phase 0.*
2. **Family.** Sweep LR / HGBT / LGBM / XGB / CatBoost with sane defaults — about 20 quick experiments. Stop at GBDT if it dominates LR by >0.01 AUC (it usually does on insurance shapes).
3. **HPO.** LGBM 50-trial Optuna fast pass on the GBDT winner. Add `monotone_constraints` with `method='advanced'` for the 1–3 most monotonic numerics — but **verify the empirical sign first**. Actuarial intuition is often backwards (this study: `vehicle_age → -1`, `subscription_length → +1`, opposite of "older=more risk"). Get this wrong and monotone hurts by -0.005.
4. **Calibration.** `CalibratedClassifierCV(method='isotonic', cv=5)` post-hoc. **Imbalance treatments (class_weight, focal, SMOTE) are all dead ends** on insurance-shaped data — they hurt calibration without improving rank.
5. **Cross-family soft vote.** 3-GBDT uniform-weight average. Stacking with a meta-learner under-performs on weak-signal small data because the meta over-fits OOF.
6. **Reporting.** AUC, PR-AUC, log-loss, Brier, lift@10%, Spiegelhalter z, monotone-violation count. Reliability diagrams in the deliverable, not just headline numbers.

---

## 4. GBDT framework selection (the user's Q2)

### 4.1 The empirical headline

On this dataset, the three frameworks are within 0.002 AUC when each is paired with its preferred encoder:

```
LightGBM + OHE + monotone-advanced  : 0.6701   (winning single model)
XGBoost  + ordinal + tuned          : 0.6689
CatBoost + sklearn-target + tuned   : 0.6683
                                      ──────
soft-voted (uniform 1/3)            : 0.6715   (global best)
```

**Framework choice is ±0.002. Encoder pairing is the second-order win.** This means the right question is not "which framework?" but "which framework × encoder × constraint pairing?"

### 4.2 When each framework wins (decision rules)

| Choose ... | When ... |
|---|---|
| **LightGBM** (default) | Weak-signal binary, ~10⁴–10⁵ rows. You want HPO speed, monotone-advanced, and the smallest learning-curve. Winner here. **Caveat**: native cat handling under-performs OHE on small data — don't trust the marketing. |
| **XGBoost** | Many naturally-ordered features (recency, frequency, days-since-X), or you need broadest tooling (SHAP-tree, Treelite, ONNX, Spark integration). Surprise winner with **ordinal encoder**. Slightly slower than LGBM on CPU but the extras can be worth it in production. |
| **CatBoost** | Many high-cardinality nominal cats (city, postcode, vehicle_model), and limited FE budget. Ordered Boosting reduces target-leakage on small data. **Caveat**: 2–3× slower fits; native cat encoding is *slightly worse* than sklearn 1.3+ TargetEncoder on weak signal. |
| **HGBT (sklearn)** | Sanity baseline + speed. Reaches ~0.668–0.670 with default `categorical_features=auto`. Useful when you can't add deps or you need a control. |
| **All three** + uniform soft-vote | Production. Reliable +0.001–0.003 over single best. Always do this last. |

### 4.3 The "encoder × framework" matrix is the actual decision

```
                  LR    XGB    LGBM   CatBoost
OHE+min_freq=20   0.626 0.668  0.670  0.667
Ordinal           0.404 0.669* 0.666  —
Target (sklearn)  0.624 0.669  0.668  0.668*
Native            n/a   0.667  0.663  0.660
Hashing/JS        0.624 —      —      —
```
*= winning encoder for that family (within ±0.001 of next-best).

Two conclusions:
- **Diversity in encoder + framework compounds.** That's why the soft-vote winner uses different encoders per learner: XGB-ordinal + LGBM-OHE-monotone + CatBoost-target. Each base learner sees the cats from a different angle, so their errors are de-correlated.
- **The "native cat handling" advertised by LGBM and CatBoost is a small-data myth.** It's a marketing claim that may hold past 100k rows; on weak-signal 50k rows, OHE / target encoding wins.

### 4.4 Cross-family ensembling rules

- **Uniform 1/3 weights beat Optuna-tuned weights on small val.** Optuna over-fits to the val set's idiosyncrasies. We saw 0.6679 (Optuna) vs 0.6715 (uniform).
- **LR meta-learner under-performs soft vote when OOF train fold has <5k positives.** Stacking is for big data; soft voting is for small data.
- **Calibrate base learners with isotonic *before* averaging** if downstream needs probabilities. Otherwise a mis-calibrated learner skews the average.
- **Don't blindly add diversity.** Adding a 4th deep-learning learner (FTT) to the soft vote *hurt* by 0.001 here. The decision rule: only add a learner if its pairwise correlation with the existing learners' OOF preds is < 0.95.

---

## 5. Deep learning for tabular: when does it pay? (the user's Q3)

### 5.1 Why DL didn't pay here (Phase 4 evidence)

- Best TabNet 0.6633 (25 configs); best FTT 0.6695 (15 configs). Both below the GBDT trio (0.6701) and the soft-vote (0.6715).
- The MPS DataLoader bug cost 3 experiments (Exp 178–180) to silent gradient collapse. DL has more failure modes than trees on small data.
- TabNet's celebrated attention-mask "interpretability" added zero ranking power on weak signal.

This matches Grinsztajn et al. 2022, who benchmarked 45 tabular datasets and concluded *tree-based models remain state-of-the-art on medium-sized data (~10K samples) even ignoring their speed advantage*. The reasons they identify (rotation-invariance issues in NNs, sensitivity to uninformative features, lack of axis-aligned partition bias) match what we saw.

### 5.2 The five regimes where DL becomes competitive

1. **Large data (>500k rows).** DL scaling laws kick in; trees plateau. Grinsztajn's benchmark shows the gap closing past ~50k–500k rows depending on signal strength. If you have a million policy-years of high-signal claims data, the regime flips.
2. **Multi-modal joint** (tabular + text + images + time-series). DL embeds them in one space; trees can't share representations across modalities. If your insurance pipeline ingests claim notes (text), vehicle photos (images), or telematics streams (sequences), DL is the only architecture that can fuse them end-to-end.
3. **Multi-task / pretraining.** Share an encoder across related tasks (claim probability + claim severity + churn + lapse). Trees retrain per task. With shared deep representations, transfer + multi-task learning become natural.
4. **Very high cardinality** (>1000 levels per col, e.g., zipcode-block, vehicle-VIN-prefix, agent-id). Entity embeddings (`nn.Embedding`) beat target encoding past ~1k levels because target encoding has too few examples per level to estimate cleanly.
5. **Tabular foundation models** (TabPFN, TabM). On *small* tabular (<10k rows), TabPFN v2 (Hollmann et al. 2025, Nature) beats a tuned GBDT in 2.8 seconds because it's pre-trained on 130M synthetic priors and does in-context learning. **This is the big regime shift since 2024** — and the line between "small tabular" and "TabPFN-eligible" is moving up fast (TabPFN v2.5 supports 50k rows; "Scaling Mode" tests 10M).

### 5.3 The five DL-tabular architectures, ranked by 2026 evidence

| Architecture | When it shines | Caveats |
|---|---|---|
| **TabPFN v2** (foundation) | <50k rows, classification or regression, no GPU required | Inference-heavy; needs internet to fetch weights; v2.5 supports up to 50k rows; Mac-friendly via CPU |
| **TabM** (param-efficient ensemble, ICLR 2025) | 10k–500k rows, mixed cats/nums, you have a GPU | Beats FT-Transformer / SAINT / TabR on Gorishniy's 46-dataset benchmark; MLP-based so simpler than transformers; ~2% average improvement over plain MLP ensembles |
| **FT-Transformer** (rtdl) | When you'd otherwise reach for TabNet; medium data | Needs careful dropout HPO (zero-dropout won here); MPS data-loader gotcha; transformer attention is overkill at 50k rows |
| **TabNet** | Interpretable feature masks needed; large data | Underperformed FTT in this study and in Grinsztajn 2022; the attention-mask interpretability is its main selling point |
| **CatBoost as "deep-ish" baseline** | Always fit one as the floor for "GBDT can do" | Already covered in Section 4 |

**Default DL move (2026):**
- If rows < 50k: **try TabPFN v2 first.** Zero-shot inference. If it doesn't beat your GBDT, fall back to ensembling GBDT + TabPFN.
- If rows in 50k–500k: **try TabM.** Cleaner than FTT, beats it in benchmarks.
- If rows > 500k or multi-modal: **start with TabM or FTT**, then ensemble with GBDT.

### 5.4 How to use DL well on tabular (rules of thumb)

- **Always ensemble DL with GBDT.** They have different inductive biases — DL learns smooth manifolds, trees learn axis-aligned partitions. A soft vote often beats either alone.
- **Long training schedule.** 100–200 epochs, cosine LR, dropout grid. DL on tabular needs ~3× the training budget of trees because trees converge fast.
- **Sanity-check DL.** Add an assertion: `assert proba.std() > 0.01` after the first val batch. Phase 4 found that `DataLoader + TensorDataset + MPS` silently collapses to constant predictions — manual index shuffling fixed it. The early-warning assertion would have caught it in 30 seconds instead of 3 experiments.
- **Embeddings, not OHE.** `nn.Embedding` for cats is the deep-tabular advantage when cardinality > 50. OHE-into-MLP discards the structure that embeddings preserve.
- **Skip imbalance treatments.** focal loss / class weights hurt deep tabular *more* than trees on insurance-shaped data. Train on the natural distribution; calibrate post-hoc.

### 5.5 The 2026 outlook — when this advice will go stale

TabPFN-v2.5 already extends to 50k rows. TabPFN "Scaling Mode" (Nov 2025) tests up to 10M rows. If those scaling curves hold, the "trees win at 10k" line will move to "trees win at 1M" — and then to nothing — within 2–3 years.

The *durable* advice is the framework (Section 2.4), not the framework-of-the-year. Anything that says "X is the best for tabular" should be re-checked annually.

---

## 6. Other framework-level findings worth keeping

### 6.1 Imbalance treatment — universal "don't"

Across LR / RF / HGBT / XGB / LGBM / CatBoost / TabNet / FTT, *none* of {`class_weight=balanced`, `scale_pos_weight`, `is_unbalance`, `auto_class_weights='Balanced'`, focal loss, SMOTE, ADASYN} won on this dataset. They give marginal AUC change but ruin calibration (logloss 3–10× worse).

**The rule: treat imbalance with calibration + threshold tuning, not loss reweighting.** This contradicts a lot of conventional Kaggle advice but matches the recent calibration-aware literature.

### 6.2 Feature engineering — the asymmetry

| Family | What FE does |
|---|---|
| **GBDT** | 3 invariant ratios = +0.002. Hand interactions = -0.004 (overfit). Physical/dimensional reduction is the only safe FE. |
| **LR** | Splines + interactions = +0.025. FE is the model's only path to non-linearity — it's mandatory. |
| **DL** | Typically no FE; the architecture replaces it. Caveat: still beneficial to log-transform skewed magnitudes. |

The FE budget should follow the family. The same FE that's mandatory for LR is harmful for GBDT.

### 6.3 Numerical binning — the asymmetry, repeated

| Family | What binning does |
|---|---|
| **GBDT** | Don't bin. Trees discretize internally, better than KBinsDiscretizer. Pre-binning throws away gradient information about *where* the optimal split sits. (KBins=10 hurt by 0.003; KBins=50 by 0.006.) |
| **LR** | Bin into 5–10 quantiles to capture non-linearity, OR splines on the top-3 non-linear features. (+0.001 to +0.005.) |
| **DL** | Don't bin (continuous embedding via `nn.Linear` works). |

Pattern: any operation that *fixes* a discretization choice handicaps a tree (which would have chosen a better one) or helps a linear model (which couldn't have chosen any).

### 6.4 Calibration is where the actuarial value is

Best soft-vote AUC = 0.6715. Best Brier = 0.0586. Best lift@10% = 1.6.

The model isn't a great *ranker* — AUC 0.67 is barely above what a single feature like `region_density` could give. But it's a *well-calibrated* ranker — Brier drift is small, and isotonic post-cal removes residual sigmoid bias. For premium pricing, calibration matters more than rank discrimination because you're not just sorting policies — you're attaching a price to each.

**Always report Brier + Spiegelhalter z + reliability diagram alongside AUC for insurance.**

### 6.5 Stacking < soft voting on small validation sets

LR meta over OOF on 14k positives split 3-fold → 0.6685.
Uniform soft vote → 0.6715.

The meta-learner over-fits OOF idiosyncrasies when val_pos is small. **Rule of thumb: use stacking only when val_pos > 10k.** Below that, uniform soft voting wins.

---

## 7. Generalization beyond insurance

The framework (Section 2.4) generalizes to any tabular weak-signal binary classification. Insurance specifics (Section 3) generalize to credit scoring, churn prediction, fraud detection, medical-risk prediction. The DL section (Section 5) generalizes to any tabular setting.

**What does *not* generalize:**
- Specific HPs (`num_leaves=15` is dataset-tuned; restart Optuna on a new dataset).
- Specific encoder winners (XGB liked ordinal here; on a dataset with mostly low-cardinality cats, OHE may beat ordinal).
- Monotone-constraint signs (verify empirically per dataset; intuition is unreliable).
- The exact model-vs-HPO ratio (3.4× here; depends on how badly defaults fit your row count and signal strength).

**What does generalize:**
- The *order* of priorities (model > HPO > FS > encoder > FE for trees).
- The *family-relative caveat* (encoder catastrophic if linear; HPO matters most if tree).
- The *imbalance verdict* (don't reweight; calibrate post-hoc).
- The *binning verdict* (don't bin for trees, do bin for linear).
- The *cross-family soft-vote rule* (uniform 1/3 weights, +0.001–0.003 free).

---

## 8. Citations

- **Grinsztajn, L., Oyallon, E., & Varoquaux, G. (2022).** *Why do tree-based models still outperform deep learning on tabular data?* NeurIPS 2022 Datasets and Benchmarks. [arXiv:2207.08815](https://arxiv.org/abs/2207.08815). The canonical "trees still win" benchmark — 45 datasets, rigorous methodology, identifies rotation-invariance and uninformative-feature issues as DL weaknesses on tabular.
- **Hollmann, N., et al. (2025).** *Accurate predictions on small data with a tabular foundation model.* Nature. [doi:10.1038/s41586-024-08328-6](https://www.nature.com/articles/s41586-024-08328-6). TabPFN v2 — pre-trained on 130M synthetic tabular datasets, beats tuned GBDT in 2.8s on <10k rows. The model that's redrawing the small-tabular regime.
- **Gorishniy, Y., Kotelnikov, A., et al. (2024).** *TabM: Advancing Tabular Deep Learning with Parameter-Efficient Ensembling.* ICLR 2025. [arXiv:2410.24210](https://arxiv.org/abs/2410.24210). New SOTA tabular DL via efficient MLP-ensemble; beats FT-Transformer, SAINT, TabR on Gorishniy's 46-dataset benchmark.

---

## 9. Cross-references

- **Empirical numbers per question:** `best-practices-auto-insurance.md` (Q2)
- **Per-family GBDT recipes + Optuna importance:** `gbdt-hyperparameter-guide.md` (Q3)
- **Encoder × family table:** `encoder-comparison.md` (Q6/Q7/Q8)
- **Audit trail (215 experiments):** the ancestor campaign's `results.tsv` (its private
  lab; the distilled numbers all appear in the three companion docs above)

The chain *abstract → essay → numbers* should work end-to-end: a reader starts at this
doc's abstract and reaches concrete experiment numbers in the companion docs.
