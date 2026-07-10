---
type: method-card
domain: "insurance"
status: final
concepts: [denoising-autoencoder, swap-noise, rankgauss, deep-stack-representation, self-supervised-tabular, when-dl-pays]
related: [../../knowledge/insights-and-framework.md, ../../knowledge/method_cards/gbdt-tabular.md, ../../knowledge/method_cards/glm-pricing.md]
refs_verified: true   # every reference below verified via WebSearch/WebFetch (see §7 notes)
---

# Method card — swap-noise Denoising AutoEncoder (DAE) for tabular claims

> Gate 2 (METHOD). Pedagogy for a FRONTIER method (self-supervised representation
> learning for tabular data), written BEFORE modeling. Protocol:
> `.claude/skills/klein/references/method-gate-protocol.md`. The parts are an authoring
> ARC — read them in order. This is the study's teaching centrepiece; `dae.py` realizes it.

## 1. Intuition (for an actuary / data scientist)

**A denoising autoencoder is nonlinear PCA.** PCA finds a low-dimensional linear subspace
that reconstructs your columns with least squared error; an autoencoder (AE) does the same
job but the encoder and decoder are neural nets, so the "subspace" can bend — it captures
non-linear and interaction structure PCA cannot. You train it *unsupervised*: no
`claim_status` label, just "compress each policy row, then reconstruct it."

**Denoising is the twist that forces it to learn something.** An ordinary AE with hidden
layers as wide as the input can cheat by learning the identity map (copy input to output) —
it reconstructs perfectly and learns nothing useful. So we **corrupt** each input row and
ask the net to reconstruct the *clean* row from the *corrupted* one. Now copying is
useless: to undo the corruption the encoder MUST learn how the columns relate (if
`max_power` is corrupted, infer it from `displacement`, `segment`, `model`). The learned
internal activations become a feature representation that has *joint column structure*
baked in. (Our net is actually **overcomplete** — 256-wide hidden layers over a 94-dim
input — so it is the *denoising*, not a narrow bottleneck, that does the forcing. That is
the whole idea of a DAE.)

**Swap noise is the tabular-native corruption.** In images you corrupt by adding Gaussian
noise, blurring, or masking pixels — all meaningful because neighboring pixels are
correlated in space. A table has no such geometry: adding Gaussian noise to a one-hot
`fuel_type` is nonsense. Michael Jahrer's answer (Porto Seguro, §4) was **swap noise**:
with probability *p*, replace a cell with the value of the *same column drawn from a random
other row*. The corrupted value is always a *plausible* value for that column (it came from
a real policy), just wrong for *this* policy — exactly the kind of corruption whose
undoing teaches inter-column structure. We exclude the 17 `is_*` safety-flag binaries from
corruption (swapping a 0/1 accessory flag is not useful denoising signal) and pass them
through untouched.

**What we hand the downstream model** is the **deep-stack representation**: the
concatenation of all three hidden-layer activations (3 × 256 = **768 dims**). Jahrer's
insight was that stacking the layers beats using only the last one.

## 2. Math core

| Symbol | Meaning |
|---|---|
| $x \in \mathbb{R}^{d}$ | one encoded policy row: RankGauss numerics ⊕ OHE categoricals ⊕ `is_*` passthrough ($d=94$ here) |
| $\tilde{x} \sim q(\cdot\mid x)$ | swap-noise-corrupted copy of $x$ |
| $p$ | swap rate (per-cell corruption probability; Jahrer 0.15) |
| $f_\theta$ | encoder (3 ReLU layers, widths $256,256,256$); $h^{(1)},h^{(2)},h^{(3)}$ its activations |
| $g_\phi$ | linear decoder head reconstructing all $d$ dims |
| $z$ | deep-stack representation $=[\,h^{(1)};h^{(2)};h^{(3)}\,]\in\mathbb{R}^{768}$ |

**(1) Swap-noise corruption** — per column $j$, independently per row $i$, with donor row
$r$ drawn uniformly; `is_*` columns exempt ($\mathcal{E}$ = eligible columns):

$$\tilde{x}_{ij}=\begin{cases}x_{r j}, & \text{w.p. } p \text{ and } j\in\mathcal{E}\\ x_{ij}, & \text{otherwise}\end{cases}\qquad r\sim\text{Unif}\{1,\dots,n\}$$

**(2) Encoder** (ReLU $\sigma$): $\;h^{(1)}=\sigma(W_1\tilde{x}+b_1),\;\; h^{(k)}=\sigma(W_k h^{(k-1)}+b_k),\; k=2,3.$

**(3) Decoder** (reconstruct ALL encoded dims from the last hidden layer):
$\;\hat{x}=W_o\,h^{(3)}+b_o.$

**(4) Objective** — mean-squared reconstruction of the CLEAN row from the corrupted input:

$$\min_{\theta,\phi}\;\; \mathbb{E}_{x}\,\mathbb{E}_{\tilde{x}\sim q(\cdot\mid x)}\;\bigl\lVert\, g_\phi\!\bigl(f_\theta(\tilde{x})\bigr)-x\,\bigr\rVert_2^2$$

**(5) Downstream feature**: freeze $\theta$, discard $g_\phi$, use $z=[h^{(1)};h^{(2)};h^{(3)}]$.

**Why noise prevents the identity solution.** If $p=0$ then $\tilde{x}=x$ and, because the
hidden layers are wide enough, $g_\phi\!\circ f_\theta=\mathrm{Id}$ achieves zero loss while
learning nothing. With $p>0$, the target $x$ differs from the input $\tilde{x}$ on the
corrupted cells, so a copy incurs loss exactly there; minimizing the expected loss forces
$f_\theta$ to predict each cell from the *others* — i.e. to model the joint distribution of
the columns. RankGauss (each numeric column mapped to a Gaussian by rank) keeps the MSE
scale-balanced across heterogeneous numerics so no single wide-range column dominates the
loss.

## 3. Minimal from-scratch implementation plan

The smallest honest version (what `dae.py` realizes; kleinlib helpers named):

```text
# encode ONCE (fit on TRAIN fold only — the fairness rule)
transformer = ColumnTransformer(
    num  -> SimpleImputer(median) + QuantileTransformer(output_distribution="normal")  # RankGauss
    is_* -> passthrough                                                                # excluded from noise
    cat  -> SimpleImputer(most_frequent) + OneHotEncoder(min_frequency=20)             # dense
).fit(X_train)                                # → d = 94 encoded dims
Z_clean = transformer.transform(X_train)

net: Linear(d,256)->ReLU ->Linear(256,256)->ReLU ->Linear(256,256)->ReLU ; head Linear(256,d)
opt  = AdamW(lr=1e-3, weight_decay=1e-5)

for epoch in range(100):                      # early-stop patience 10 on held-out recon loss
    Xc = swap_noise(X_train, eligible=num+cat, rate=p)   # ORIGINAL-column corruption, fresh each epoch
    Z_corrupt = transformer.transform(Xc)                # re-encode → valid one-hots / RankGauss
    for batch in kleinlib.torch_loop.iterate_minibatches(n, 256, shuffle=True):   # MPS-safe, NEVER DataLoader
        loss = MSE( net(Z_corrupt[batch]) , Z_clean[batch] ) ; loss.backward() ; opt.step()

rep = concat(h1,h2,h3)  for X                 # 768-dim deep-stack, returned as CPU numpy
```

Helpers it leans on: `kleinlib.torch_loop.iterate_minibatches` (MPS-safe index-shuffle
batching — the DataLoader collapse war story), `kleinlib.torch_device.pick_device`
(MPS→CPU), `kleinlib.eval.evaluate` (downstream classifier eval + `min_proba_std` guard).
The swap-noise granularity is **original-column-level then re-encode** — a categorical swap
stays a valid single one-hot and a numeric swap gets RankGauss'd consistently (documented
in `dae.py`; provably identical to copying the donor's encoded slice because both encoders
are per-column deterministic maps).

## 4. The Porto Seguro story (why this method, and why 58k rows is a different regime)

The single most resonant precedent is **Michael Jahrer's 1st-place solution to Porto
Seguro's Safe Driver Prediction (Kaggle, 2017)** — which is *also auto-insurance claim
prediction*. Verified facts from his solution writeup (§7):

- He won with a blend of **6 models (1 LightGBM + 5 neural nets)**, and **every neural net
  was trained on denoising-autoencoder hidden activations**, not the raw features — "the DAE
  did a great job learning a better representation of the numeric data."
- He invented **swap noise** for exactly the reason in §1: tabular data has no
  flip/rotate/crop augmentation, so he corrupts by sampling a cell from another row; his
  rate was **0.15** (15% of cells replaced).
- The DAE was trained on **train + test features combined** (unlabeled) — roughly
  **~1.5M rows** (≈595k train + ≈892k test) — i.e. a **transductive** fit that quietly uses
  the test-set distribution. Per his writeup he used **large (~1500-unit) hidden layers** and
  the **deep-stack** (concatenated hidden) features, with **RankGauss** input normalization.

**Why our data is a different regime — and why the honest verdict is likely "no headline
lift."** Three differences matter, all pushing *against* the DAE here:

| Axis | Jahrer / Porto Seguro | This study (01-dae-claims) |
|---|---|---|
| Rows feeding the DAE | ~1.5M (train+test, **transductive**) | ~47k (train fold only, **inductive** — the fairness rule) |
| Regime | large-data, representation learning pays | 58k weak-signal — squarely where **trees still win** (Grinsztajn) |
| Fairness | transductive (sees test distribution) | headline is inductive; transductive only a labeled "Kaggle-style" aside |

Representation learning's edge grows with unlabeled scale; at ~25× fewer rows and with an
honest inductive constraint, a tuned GBDT (campaign best 0.6701) is the bar to beat and we
predict the frozen DAE reps will *not* clear it. That measured "no" is the study's headline
value: it tells an actuary the DAE is not worth it *on data like this* — while leaving room
for the imputer/anomaly second acts (RQ4) that may pay independently.

## 5. Frontier context & when-it-pays

Two peer-reviewed anchors put swap-noise DAEs in the tabular-SSL landscape:

- **VIME** (Yoon et al., NeurIPS 2020) generalized the idea: corrupt tabular rows with a
  mask, then train on *two* pretext tasks — reconstruct the values AND predict the mask —
  plus a consistency-regularized semi-supervised head. Our DAE is the reconstruction half.
- **SCARF** (Bahri et al., ICLR 2022; arXiv:2106.15147) uses the *same* random-feature
  corruption but with a **contrastive** objective (InfoNCE) instead of reconstruction, and
  showed gains across 69 OpenML tabular datasets — evidence the corruption idea is real, but
  concentrated where SSL has room (label scarcity, larger data).

**When it pays / when it doesn't** (regime table, grounded in Grinsztajn 2022 +
`knowledge/insights-and-framework.md §5`):

| Regime | Data size | Signal / structure | Verdict for a DAE |
|---|---|---|---|
| This study | ~58k rows | weak signal, low-cardinality, single-modal | **Doesn't pay for the headline** — trees win; DAE reps ~0.66-0.67 ≤ tuned GBDT 0.6701 |
| Large tabular | >500k rows | DL scaling laws engage | Starts to pay — representation learning + transductive unlabeled data (Jahrer's regime) |
| Multi-modal | any | tabular + text/image/telematics | Pays — a DAE/NN fuses modalities trees cannot share |
| High cardinality | any | >1000 levels/col | Pays — learned embeddings beat target encoding |
| Small tabular | <50k rows | — | Prefer a **tabular foundation model** (TabPFN v2, Hollmann 2025) over a hand-trained DAE |
| **Second acts** (any regime) | any | missingness / outliers present | The SAME DAE can **impute** (reconstruct missing cells) and **flag anomalies** (reconstruction error) — independent value even when the headline says "no" |

## 6. Falsifiable priors this study tests

Mirrored verbatim in `study.yaml:predictions_to_falsify`; `findings.md` records observed +
held/falsified. Each names a lever, a direction, and a magnitude (protocol §"good prior").

| RQ | Lever | Predicted | Falsifiable? |
|---|---|---|---|
| — | E1 anchor LR+OHE+cw=balanced | `val_auc = 0.6255 ± 0.001` | **GATE — STOP the study if missed** |
| RQ1 | E3 frozen DAE(768-d) → LGBM | `val_auc ~0.66-0.67, Δ ≤ 0 vs 0.6701` (no beat) | Yes — the headline claim |
| RQ2 | E6 DAE+raw → LGBM | `Δ ≤ +0.001 vs 0.6701` (likely discard) | Yes — additive-value bar |
| RQ3 | E4 linear probe on DAE reps | `val_auc ~0.63-0.66, Δ > 0 vs raw-LR 0.6255` | Yes — "did SSL linearize the signal?" |
| RQ4 | E7 DAE-imputer vs median (MCAR 10/30%) | downstream `Δ ≥ 0`, growing with missing rate | Yes — independent second act |
| RQ4 | E8 recon-error anomaly | `lift@10% > 1.0` | Yes — independent second act |
| — | E5 swap-rate sweep {.10,.15,.25} | `|Δ| ≤ 0.002` across rates | Yes — noise-sensitivity |

## 7. Verified references

Each verified via WebSearch/WebFetch (venue, year, and — where applicable — arXiv id).
Verification note: a *wrong* arXiv id (2006.06775) was caught and rejected for VIME during
this gate, so VIME is cited by its authoritative NeurIPS proceedings page, not an arXiv id.

| Reference | Where | Verified? |
|---|---|---|
| Yoon, Zhang, Jordon & van der Schaar (2020). *VIME: Extending the Success of Self- and Semi-supervised Learning to Tabular Domain.* | NeurIPS 2020 — proceedings.neurips.cc/paper/2020/hash/7d97667a3e056acab9aaf653807b4a03 | ✅ (venue + authors confirmed; no arXiv id cited — see note) |
| Bahri, Jiang, Tay & Metzler (2022). *SCARF: Self-Supervised Contrastive Learning using Random Feature Corruption.* | ICLR 2022 — arXiv:2106.15147 | ✅ (arXiv id + ICLR 2022 confirmed) |
| Jahrer, M. (2017). *1st place solution — Porto Seguro's Safe Driver Prediction* (denoising autoencoder + swap noise + representation learning). | Kaggle competition writeup, discussion #44629 | ✅ existence + DAE/swap-noise-0.15/6-model-blend confirmed via multiple secondary sources (kaggler.com; fast.ai forums; *The Kaggle Workbook*). ⚠️ NOT peer-reviewed; the exact hidden width (~1500) and RankGauss detail are from that forum writeup, presented as such. |
| Grinsztajn, Oyallon & Varoquaux (2022). *Why do tree-based models still outperform deep learning on tabular data?* | NeurIPS 2022 Datasets & Benchmarks — arXiv:2207.08815 | ✅ (arXiv id + venue confirmed; also in `knowledge/insights-and-framework.md`) |
| Hollmann et al. (2025). *Accurate predictions on small data with a tabular foundation model* (TabPFN v2). | Nature — doi:10.1038/s41586-024-08328-6 | ✅ (in `knowledge/insights-and-framework.md §5`, verified there) |

- Frontier method → the lit-scan above is MANDATORY and complete before this card ships.
- `refs_verified: true` set: every row verified (with the Jahrer forum-writeup caveat
  flagged explicitly rather than hidden).
