---
title: "Encoder Comparison (insurance-claims, Phases 1-3)"
type: reference
domain: ml
status: ported
source: "ancestor model-survey campaign (private lab), docs/encoder_comparison.md (215-experiment campaign, 2026-04)"
concepts: [one-hot-encoding, ordinal-encoding, target-encoding, native-cat, high-cardinality, encoder-by-family, hashing, encoder-diversity]
related: [best-practices-auto-insurance.md, gbdt-hyperparameter-guide.md, insights-and-framework.md]
---

# Encoder Comparison (insurance-claims, Phases 1-3)

> Ported from the 2026-04 model-survey campaign (215 experiments, insurance-claims, best val_auc 0.6715). Original lives in the campaign repo.

**Questions Q6, Q7, Q8 partial answer.** Distilled from 152 experiments. The full Q8 ablation (model fixed × encoders varied vs encoder fixed × models varied) is in Phase 5.

## Per-family encoder rankings (val_auc)

| Encoder | LR (Phase 1) | XGBoost | LightGBM | CatBoost |
|---|---|---|---|---|
| **OHE (min_freq=20)** | 0.6255 (best LR base) | 0.6678 | **0.6671** | 0.6669 |
| **OHE (no min_freq)** | 0.6259 | — | — | — |
| **Ordinal** | 0.4039 (catastrophic) | **0.6689** (best XGB) | 0.6658 | — |
| **Target (sklearn 1.3+)** | 0.6235 (slight loss) | 0.6685 | 0.6684 | **0.6683** (best CB) |
| **Native (`category` dtype)** | n/a | 0.6670 | 0.6630 (surprise loss) | 0.6604 |
| **Frequency (count)** | 0.5179 (~random) | — | — | — |
| **Hashing (64 dim)** | 0.6259 | — | — | — |
| **JamesStein (cat-encoders)** | 0.6233 | — | — | — |

## Key findings

### Q6 — Best encoder by model family

- **Linear models (LR/SGD/LinearSVC)**: OHE wins, **never** use ordinal or frequency** (they treat nominal categories as ordered/quantitative — catastrophic loss of 0.022–0.108 AUC). Hashing matches OHE in dimension-constrained settings. Target/JamesStein come within 0.002 of OHE.
- **XGBoost**: **Ordinal** is the surprise winner (0.6689). OHE is close (0.6678). Native cat handling actually loses by 0.002. Trees split fine on integer codes; the OHE explosion (94 features post-encoding) hurts marginal split quality.
- **LightGBM**: **OHE** beats native cat (0.6671 vs 0.6630). LGBM's "native cat advantage" doesn't materialize on this small (~6k positives) dataset — its proprietary cat split algorithm overfits. OHE > target > ordinal > native.
- **CatBoost**: **TargetEncoder** beats native cat (0.6683 vs 0.6669). The same "native cat advantage doesn't materialize" finding generalizes. Sklearn's TargetEncoder uses a 5-fold cross-fit smoothed mean which is more robust than CatBoost's built-in target stat for this row count.

### Q7 — High-cardinality treatment

The dataset has `region_code` (22 levels), `model` (11 levels), `engine_type` (11 levels). These are the columns where encoder choice matters most:

- **High-cardinality + linear model**: target encoding is mandatory. Ordinal is broken (treats codes as ordered numbers). Frequency loses information by collapsing distinct categories with the same count.
- **High-cardinality + tree model**: target ≈ OHE ≈ ordinal within ±0.002 — the tree's split flexibility absorbs encoding choice. Native handling is the riskiest because it embeds the encoding inside the model and removes user control.
- **Hashing**: matches OHE on this row count (n_features=64 sufficient for 5 cats × ≤22 levels). Useful when categorical inflation is a memory concern, not for AUC lift.

### Q8 — Encoder ROI vs model ROI (preliminary; Phase 5 has the formal ablation)

| Lever | Range | AUC range |
|---|---|---|
| Model family (LR vs HGBT) | best of each | 0.6528 vs 0.6701 = +0.017 |
| Encoder choice within LR | OHE→Ordinal | 0.6255 vs 0.4039 = -0.222 |
| Encoder choice within XGB | OHE→Ordinal | 0.6678 vs 0.6689 = +0.001 |
| Encoder choice within LGBM | OHE→native | 0.6671 vs 0.6630 = -0.004 |
| Encoder choice within CatBoost | OHE→target | 0.6669 vs 0.6683 = +0.001 |

**Verdict (preliminary):** for trees, model choice (+0.017) >> encoder choice (±0.005). For linear models, encoder choice is the *biggest single lever* (a wrong encoder makes LR essentially unusable on nominal cats). The formal ablation (model × encoder grid) lives in Phase 5.

## Recommendations

1. **Linear models**: default to OHE. Test target/JamesStein with smoothing for high-cardinality. Never ordinal or frequency.
2. **XGBoost**: try ordinal first (cheapest, often best). Fall back to target if ordinal fails. OHE is a safe default.
3. **LightGBM**: OHE first. Skip native cat handling on small datasets (<10k positives) — it overfits.
4. **CatBoost**: target encoder beats native handling. Skip CatBoost's built-in target stat on small datasets.
5. **Cross-family ensembles**: use *different encoders per family* — that's what the soft-vote winner (Exp 151, 0.6715) does (XGB-ordinal + LGBM-OHE-monotone + CatBoost-target). Diversity in encoding compounds with diversity in boosting framework.

## Specific to this dataset's high-cardinality cols

- `region_code` C22 has only ~41 val rows in our split. Don't treat its target-encoding stat as gospel — the smoothing is doing real work. JamesStein and target-with-smoothing are better than vanilla target encoding here.
- `model` (C11) and `engine_type` (C11) are mid-cardinality. All sensible encoders converge.
- `segment` (6 levels) and `fuel_type` (3 levels) are low-cardinality. OHE is uniformly best — no hash-collision risk.
