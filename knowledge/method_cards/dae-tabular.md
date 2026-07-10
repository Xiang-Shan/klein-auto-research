---
title: "Swap-Noise Denoising Autoencoders for Tabular Data"
type: method-card
domain: ml / insurance
status: validated
source: studies/01-dae-claims
concepts: [denoising-autoencoder, swap-noise, rankgauss, deep-stack-representation, self-supervised-tabular, dae-imputer, recon-error-anomaly, inductive-fairness, when-dl-pays]
related: [gbdt-tabular.md, glm-pricing.md, ../insights-and-framework.md]
---

# Swap-Noise Denoising Autoencoders for Tabular Data

*Validated card distilled from `studies/01-dae-claims` (8-experiment ladder, 58,592-row
weak-signal auto-insurance claims; full trail in that study's `method_card.md`,
`findings.md`, `results.tsv`). The method: Jahrer's Porto Seguro 2017 recipe, tested
under an honest inductive contract.*

## 1. Practitioner intuition

**A denoising autoencoder is nonlinear PCA.** An encoder+decoder net is trained —
*unsupervised, no target label* — to compress each row and reconstruct it. Because the
nets can bend, the learned "subspace" captures non-linear, interacting column structure
PCA cannot.

**Denoising is what forces learning.** A wide (overcomplete) AE can cheat via the
identity map. So corrupt the input row and demand reconstruction of the CLEAN row: now
the only way to win is to infer each corrupted cell *from the other columns* — i.e.
model the joint distribution.

**Swap noise is the tabular-native corruption** (Jahrer, Porto Seguro): with
probability *p* per cell, replace it with the same column's value from a random other
row — always a *plausible* value, just wrong for this row. Apply it at the
**original-column level, then re-encode**, so a swapped categorical stays one valid
one-hot. Exclude near-informationless binaries (e.g. 0/1 accessory flags) from
corruption; pass them through.

**Hand downstream the deep stack**: the concatenation of all hidden activations
(3×256 → 768 dims in the study), not just the last layer.

## 2. Math core

- Corruption: `x̃[i,j] = x[r,j] w.p. p (j eligible), else x[i,j]`, donor `r ~ Unif{1..n}`.
- Encoder `h¹=σ(W₁x̃+b₁)`, `hᵏ=σ(Wₖhᵏ⁻¹+bₖ)`; linear decoder head `x̂ = W_o h³ + b_o`.
- Objective: `min E‖g(f(x̃)) − x‖²` — MSE of the CLEAN row from the CORRUPTED input.
- Feature: `z = [h¹; h²; h³]`, frozen; decoder discarded (kept only for imputation /
  anomaly reuse).
- **RankGauss** (per-numeric quantile map to a normal) keeps the MSE scale-balanced so
  no wide-range column dominates the loss.

## 3. Minimal implementation sketch

```text
encode ONCE, fit on the TRAIN fold only (the fairness rule; log n_fit_rows_ as canary):
  numerics -> median-impute + QuantileTransformer(output_distribution="normal")  # RankGauss
  binaries -> passthrough (excluded from swap noise)
  cats     -> mode-impute + OneHotEncoder(min_frequency=20), dense

net:  Linear(d,256)->ReLU x3 ; head Linear(256,d) ;  AdamW(1e-3, wd=1e-5), batch 256
loop: FRESH swap noise each epoch at ORIGINAL-column level -> re-encode ->
      MSE(net(corrupt), clean); early-stop on a FIXED corrupted held-out recon loss
out:  concat(h1,h2,h3) as CPU numpy -> LGBM / linear probe
```

Ops guards (both bit this study): MPS index-shuffle batching, never a
DataLoader/TensorDataset (silent prediction collapse); **two-stage process isolation
for torch + LightGBM on macOS arm64** — both bundle a `libomp`, whichever engages
OpenMP second SIGSEGVs below Python (war story #5: torch-only child fits + caches,
lightgbm-first parent heads; `set -o pipefail`, `PYTHONUNBUFFERED=1`).

## 4. When it pays / when it doesn't

**Observed (study 01, 58k-row weak-signal insurance claims — the validated row):**

| Arm | val_auc | Verdict |
|---|---|---|
| Frozen DAE(768-d) → LGBM (inductive, swap 0.15) | **0.6683** | E3: below tuned raw-GBDT 0.6701 AND below the plain MLP — headline **doesn't pay** |
| Plain supervised MLP, same 94-d encoding | **0.6706** | E2: ≈ ties tuned GBDT 0.6701 — the bar every SSL detour must beat |
| DAE + raw concat → LGBM | 0.6607 | E6: **regresses** −0.0076 vs reps-only (redundant dims dilute the split budget; best_iter 107→55) |
| Linear probe on frozen reps | 0.6580 | E4: +0.0326 over raw-LR 0.6255 — the DAE DID linearize signal (~72% of the LR→GBDT gap); real but not useful on top of supervised learning |
| **DAE as MCAR imputer** vs median/mode | +0.0013–0.0015 downstream | E7: **pays at the cell level** — numeric RMSE **1.02 vs 3.42 (3.4×)**, cat accuracy **90.1% vs 33.4%**; rank barely moves |
| Recon-error as claim ranker | 0.4805 (lift@10 0.934) | E8: **no** — mildly inverted; feature-space rarity ≠ claim risk |

Swap rate is a **real lever, not flat**: 0.10 → −0.0063, 0.25 → −0.0041 vs 0.15 (E5
sweep) — Jahrer's 0.15 replicated as a local optimum even 25× below his data scale.
Sweep it; never default it.

**When it pays** (regime table, Grinsztajn 2022 + `../insights-and-framework.md` §5):
large unlabeled pools / >500k rows (Jahrer's transductive ~1.5M-row regime),
label-scarce semi-supervised settings (the VIME/SCARF habitat), multi-modal fusion —
and, at ANY scale, **imputation-for-values** in data-quality workflows.

**When it doesn't**: headline AUC on ~50k single-modal, fully-labeled, weak-signal
tabular — a plain supervised MLP on the same RankGauss+OHE encoding captures everything
the DAE offers, at ⅓ the wall-clock (E2 12.5s vs E3 37.2s). Under <50k rows prefer a
tabular foundation model (TabPFN v2) as the first DL move. Never report a transductive
(train+test-features) DAE as a headline — label it a Kaggle-style aside.

**Order of operations (the doctrine this study adds):** run the supervised-DL floor
BEFORE any SSL detour. If a plain MLP already ties your tuned GBDT, frozen-rep
pipelines have nothing left to add.

## 5. References

All verified during the study's METHOD gate (`studies/01-dae-claims/method_card.md` §7);
note the VIME arXiv-id correction recorded there (cited via NeurIPS proceedings, not
arXiv).

- Jahrer, M. (2017). *1st place solution — Porto Seguro's Safe Driver Prediction.*
  Kaggle discussion #44629. Swap noise 0.15, RankGauss, deep-stack, 6-model blend —
  NOT peer-reviewed; details from the forum write-up.
- Yoon, Zhang, Jordon & van der Schaar (2020). *VIME.* NeurIPS 2020 —
  proceedings.neurips.cc/paper/2020/hash/7d97667a3e056acab9aaf653807b4a03.
- Bahri, Jiang, Tay & Metzler (2022). *SCARF.* ICLR 2022 — arXiv:2106.15147.
- Grinsztajn, Oyallon & Varoquaux (2022). *Why do tree-based models still outperform
  deep learning on tabular data?* NeurIPS 2022 D&B — arXiv:2207.08815.
- Hollmann et al. (2025). *Accurate predictions on small data with a tabular foundation
  model* (TabPFN v2). Nature — doi:10.1038/s41586-024-08328-6.
- `studies/01-dae-claims/{findings.md, results.tsv, aux_metrics.tsv}` — the empirical
  row above, experiment-by-experiment.
