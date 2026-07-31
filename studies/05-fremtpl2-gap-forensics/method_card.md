---
type: method-card
domain: "insurance"
status: final
concepts:
  - poisson-boosting-across-libraries
  - offset-weight-equivalence
  - ordered-target-statistics
  - monotone-constraints
  - surrogate-glm-distillation
  - interaction-screening
  - segment-deviance-decomposition
  - multiplicity-discipline
related:
  - ../../knowledge/method_cards/gbdt-tabular.md       # build ON, do not duplicate
  - ../../knowledge/method_cards/glm-pricing.md        # build ON, do not duplicate
  - "git show v1.0.0:studies/04-fremtpl2-frequency/method_card.md"  # archived predecessor (read-only)
refs_verified: true    # every row in §5 verified 2026-07-31 via WebFetch/WebSearch
triad:                 # Theory + Papers + Practice — self-asserted, gate-checked
  theory: true         # §2: notation table + five display equations (E1-E5), each derived or cited
  papers: true         # refs_verified: true — 18/18 rows verified, 0 UNVERIFIED
  practice: true       # §3: pipeline.py constructors + forensics.py, exercised pre-loop —
                       # hgbt_ohe 0.444689 (study-04 anchor-exact), lgbm_poisson 0.444413,
                       # catboost_poisson 0.446332 via prediction_type="Exponent",
                       # calibration_ratio ~= 1.02 on all three
---

# Method card — Poisson boosting across libraries, ordered target statistics, monotone constraints, surrogate-GLM distillation, and segment deviance decomposition

> Gate 2 (METHOD), depth **FULL**. Protocol:
> `.claude/skills/klein/references/method-gate-protocol.md`. The five parts are an
> authoring ARC — written in order.
>
> **Scope.** This card covers only what is NEW to study 05. It is *not* a
> GLM-vs-GBDT rehash: the families themselves are treated in
> `knowledge/method_cards/glm-pricing.md` and
> `knowledge/method_cards/gbdt-tabular.md`, and the study-04 Poisson-deviance /
> exposure-weight setup is in the archived predecessor card
> (`git show v1.0.0:studies/04-fremtpl2-frequency/method_card.md`). Read those
> first; this card starts where they stop.
>
> Five new methods, tracked as **M1–M5** through every part:
>
> | | Method | Serves |
> |---|---|---|
> | **M1** | Poisson boosting across libraries (HGBT / LightGBM / CatBoost) | RQ2, RQ3 |
> | **M2** | CatBoost ordered target statistics | RQ3 |
> | **M3** | Monotone constraints in histogram GBDT | RQ7 |
> | **M4** | **Surrogate-GLM distillation for gap forensics** (the methodological core) | RQ4, RQ5 |
> | **M5** | Segment-level deviance decomposition | RQ1, RQ5, RQ6 |

**Data regime this card is written against** (measured, `data/prepared/fremtpl2_frequency.csv`):
678,013 rows → 406,807 train / 135,603 dev / 135,603 sealed test (random, seed 42).
26,406 claims over 358,360 exposure-years = **0.0737 claims per exposure-year**
weighted. Five numerics (VehPower, VehAge, DrivAge, BonusMalus, Density), four
categoricals — Region 22 levels (min 1,326 rows, median 15,065, max 160,601),
VehBrand 11 (min 4,047, median 28,548), Area 6, VehGas 2.

---

## 1. Intuition (for a practitioner)

### M1 — Poisson boosting across libraries: one blueprint, three carpenters

All three libraries minimise the **same** Poisson deviance and all of them work on
a **log scale** internally. The loss is the blueprint. What differs is how each
carpenter cuts the wood:

- **sklearn `HistGradientBoostingRegressor`** and **LightGBM** both bin every
  numeric feature into ≤255 buckets and then grow **leaf-wise (best-first)** trees
  — always split the leaf that reduces the loss most, up to `max_leaf_nodes` /
  `num_leaves`. Same family, near-identical shape.
- **CatBoost** grows **symmetric (oblivious)** trees: every node at a given depth
  uses the *same* split. Depth 6 gives 64 leaves nominally, but far fewer *distinct*
  decisions than 31 freely-placed leaves. It is a structurally more constrained,
  more regularised learner — you should expect it to behave differently even with
  the loss held fixed.
- **Prediction space differs.** HGBT and LightGBM `predict()` return the *rate*
  (they exponentiate internally). CatBoost `predict()` returns the raw log-score
  unless you ask for `prediction_type="Exponent"`. Forget that and every prediction
  is a log — negative for rates below 1, which the Poisson deviance rejects
  outright. `pipeline.py:CatBoostPoisson.predict` already handles it; the
  pre-loop sanity run (0.446332, `calibration_ratio` ≈ 1.02) is the proof it is
  wired right.

**The exposure question underneath all of it.** A policy on the books for three
months and one on for a full year cannot be compared claim-count to claim-count.
There are two textbook fixes:

1. Model the **count** and hand the model a fixed known term — "this row had 0.25
   years at risk" — an **offset** `log e_i`.
2. Model the **rate** `n_i/e_i` and tell the fitter "this row is worth 0.25 as
   much" — a **weight**.

For a log-link Poisson these are the *same estimator*: same score equations, same
fitted coefficients, same fitted trees (§2, E1). This matters practically because
**weights are universally supported** (`sample_weight` in sklearn, LightGBM and
CatBoost) while offsets/`init_score`/`baseline` are supported inconsistently and
are easy to get wrong. That is why the whole study fits rates with exposure
weights — one parameterisation, three libraries, no per-library offset plumbing.

### M2 — CatBoost ordered target statistics: the running mean that cannot peek

Target encoding says: *replace "Region R82" with the average claim rate of R82*.
The trouble is that the row you are encoding **contributed to that average**. Its
own label leaks into its own feature — the same sin as scoring a model on its
training set, just hidden inside a preprocessing step. With few rows per level the
leak is enormous: at the limit of one row per level, the "encoding" *is* the label.

CatBoost's fix is a trick any time-series modeller already knows: pretend the rows
arrived in a random order and compute each row's statistic using **only the rows
that arrived before it** — a prefix mean, smoothed toward a prior. Row *i* never
sees `y_i`. Because the earliest rows in a permutation have almost no support (and
therefore huge variance), CatBoost averages several independent random
permutations. That is *ordered target statistics*; the closely related *ordered
boosting* applies the same "use only the past" idea to the gradient estimates
themselves.

**Where the value comes from tells you where it goes away.** The greedy-TS bias
scales roughly like 1/n_level. On this dataset the *median* Region level has
≈9,000 training rows (≈350 claims at 0.0390 claims/row). The smallest Region level
does have thin support — ≈795 train rows, ≈31 claims — but it is 0.2% of the book,
so even a fully leaked encoding there cannot move an exposure-weighted aggregate
deviance by anything close to a noise floor. There is essentially nothing to leak
where the exposure actually is. The RQ3 prior — echoing study 04's
0.37×-floor native-vs-OHE tie and the ancestor campaign's "native categorical
handling is a small-data myth" verdict in `gbdt-tabular.md` — is that the fix has
nothing to fix here.

### M3 — Monotone constraints: a shape prior enforced inside split finding

Telling a GBDT "frequency may never *decrease* as BonusMalus rises" is the tree
equivalent of telling a spline it may bend but never go downhill. It is not a
post-hoc filter — enforcement happens **inside split finding**. Each node inherits
a `[lower, upper]` value band from its ancestor path; candidate leaf values are
clipped into that band, and the children's bands are tightened so no leaf on the
high-x side can ever sit below a leaf on the low-x side. The guarantee that comes
out is exactly what a filing needs: `x₁ ≤ x₁′ ⟹ F(x₁, x₂) ≤ F(x₁′, x₂)` for *all*
values of the other features.

**Why anyone would want to pay for this.** A regulator or an underwriter will not
accept "a driver with a *worse* bonus-malus record gets a *cheaper* price". A
reversal in a thinly-populated cell reads as a pricing bug even when it is a real
(selection-driven) data pattern. So the constraint is sometimes not optional. The
research question is therefore never "does it help accuracy" — it is **what does
filability cost**, in units of the measured noise floor.

**The cost is a search-space restriction**, and it can only ever be ≥ 0 on the
training loss. On development it may be ~0 (when the data is monotone anyway) or
even negative-cost (the constraint acting as a variance reducer). `gbdt-tabular.md`
carries the standing warning from the ancestor campaign: **verify the empirical
sign first** — the campaign found the actuarially "obvious" directions *reversed*,
and a wrong-sign constraint cost −0.005 AUC.

### M4 — Surrogate-GLM distillation: distillation's machinery used as an instrument

Knowledge distillation (Hinton, Vinyals & Dean 2015; the compression ancestor is
Craven & Shavlik's TREPAN, which extracts a decision tree *from a trained network*)
trains a small **student** on the **teacher's outputs** rather than on the labels.
The reason it works is that the teacher's output is a denser, lower-variance signal
than a raw label — a smooth surface instead of a 0/1.

Here we are **not compressing anything to deploy**. We are using the same machinery
as a **measurement instrument**, and the difference matters for how you read the
output:

> The GBDT's log-prediction surface is a smooth function of the rating factors.
> Fit a **GLM-shaped surrogate** — main effects only, in a basis the real GLM could
> actually use — to that surface. Whatever the surrogate **cannot** reproduce, its
> residual, is by construction the part of the teacher's structure that is **not
> representable as GLM main effects**. Correlate that residual against candidate
> two-way products and the largest correlations name *which interactions the GBDT
> found*.

Then — and this is the whole point — you do not guess. You **promote the top
candidates into the real GLM as design-matrix columns and measure the effect on
development deviance**. The instrument and the intervention are the same object: the
product column that scored highest *is* the column you add. A screening hit is
therefore immediately falsifiable by a refit.

Three properties make this honest rather than a fishing expedition:

1. **The screen never touches evaluation labels.** The surrogate's target is the
   teacher's *train-fold predictions*, not `y`. Derivation lives entirely inside
   the train fold; development is spent only on the adopt/reject decision; the
   sealed test confirms.
2. **The multiplicity is small, fixed in advance, and reported.** Five numerics →
   C(5,2) = **10 candidate pairs screened**, at most **2 adopted**. Both counts go
   into `findings.md` §③. A screen you report is a screen; a screen you hide is
   p-hacking.
3. **`R²_main` is itself a headline number.** The fraction of the teacher's
   log-rate surface a main-effects basis can reproduce answers RQ5's real question
   — *is the gap an interaction gap at all?* — before a single interaction is
   adopted.

### M5 — Segment deviance decomposition: a P&L by line of business

The weighted Poisson deviance is a **sum of per-row contributions**. Any partition
of the evaluation rows into disjoint segments therefore partitions the total
**exactly** — no cross terms, no residual, nothing to approximate (§2, E5). So the
headline "GBDT beats GLM by 0.010172" splits additively into "how much came from
drivers under 25", "how much from BonusMalus ≥ 100", "how much from Region R11".

That identity is what converts a leaderboard row into a **WHERE answer**: *72% of
the gap sits in three segments covering 11% of exposure* is a completely different
business story from *the gap is spread evenly across the book* — even though both
produce the same 0.010172. It is nearly free (one groupby), it is exact, and it is
the honest framing for a study whose stated goal is "WHERE does the advantage
live".

---

## 2. Math core

| Symbol | Meaning |
|---|---|
| `n_i` | claim count of policy *i* (`ClaimNb`, capped at 4 by prep) |
| `e_i` | exposure of policy *i* in years at risk, `e_i ∈ [1/365.25, 1]` |
| `y_i = n_i / e_i` | observed claim **frequency** (a rate) — the modelling target |
| `w_i = e_i` | the fitting **and** evaluation weight (E1 is why they coincide) |
| `x_i` | rating-factor vector of policy *i* |
| `μ_θ(x)` | modelled frequency (rate); `λ_θ(x) = e · μ_θ(x)` is the modelled count |
| `d(y, μ)` | unit Poisson deviance |
| `D(m) = Σ_i w_i d(y_i, μ_m(x_i))` | total weighted deviance of model *m* on a fold |
| `Δ = D(GLM) − D(GBDT)` | the **gap** (positive ⇒ GBDT better); dev value 0.010172 |
| `S_1 … S_K` | a disjoint partition of the evaluation rows, `∪_k S_k` = all rows |
| `F(x) = log μ̂_GBDT(x)` | the teacher's log-score (CatBoost's `RawFormulaVal`) |
| `g(x; θ)` | main-effects surrogate predictor of `F` |
| `r_i = F(x_i) − g(x_i; θ̂)` | surrogate residual — the non-additive remainder |
| `z_a` | weight-standardised column *a*; `z_ab = std(z_a ⊙ z_b)` the product column |
| `σ` | a random permutation of the training rows (ordered TS) |
| `a, p` | ordered-TS prior weight and prior value |
| `ν`, `M` | learning rate (shrinkage) and number of boosting iterations |

### E1 — Offset ≡ exposure-weighted-rate (why all three libraries can be driven the same way)

$$
\arg\max_{\theta}\;\sum_i \log \mathrm{Pois}\!\big(n_i \mid e_i\,\mu_\theta(x_i)\big)
\;\;=\;\;
\arg\min_{\theta}\;\sum_i e_i\, d\!\big(y_i,\ \mu_\theta(x_i)\big),
\qquad
d(y,\mu) = 2\Big(y\log\tfrac{y}{\mu} - y + \mu\Big),\ \ 0\log 0 := 0 .
$$

*Derivation (the load-bearing step, so it does not rest on a citation).*
`log Pois(n | eμ) = n log(eμ) − eμ − log n!`. Substitute `n = e·y` and drop terms
free of θ: `e(y log μ − μ)`. And `e·d(y,μ)/2 = e(y log y − y log μ − y + μ)`, whose
θ-dependent part is `−e(y log μ − μ)`. Hence maximising the count likelihood **with
offset `log e`** and minimising the **`e`-weighted rate deviance** differ only by
θ-free terms. With a log link `log μ = η_θ(x)` both give the identical score
equation

$$\sum_i \big(n_i - e_i\,\mu_\theta(x_i)\big)\,\nabla_\theta \eta_\theta(x_i) \;=\; 0 .$$

**Caveats worth stating.** (i) The equality is for the *point estimate / fitted
function*; dispersion-based standard errors differ unless φ is handled
consistently — irrelevant here (the metric is deviance, not a Wald test), but it is
the reason the two forms are not interchangeable in a filing memo. (ii) For a GBDT
the equality holds at the level of the loss and its gradients, hence at every
split-gain and leaf-value computation, so "weighted rate" and "offset counts"
produce the same trees under the same seed.

### E2 — Ordered target statistic (what CatBoost substitutes for a category)

For a categorical feature *j*, value `c`, under permutation σ:

$$
\hat{x}^{(j)}_i \;=\;
\frac{\displaystyle\sum_{k\,:\,\sigma(k)<\sigma(i)} \mathbb{1}\big[x^{(j)}_k = x^{(j)}_i\big]\, y_k \;+\; a\,p}
     {\displaystyle\sum_{k\,:\,\sigma(k)<\sigma(i)} \mathbb{1}\big[x^{(j)}_k = x^{(j)}_i\big] \;+\; a}
$$

The **greedy** TS is the σ-free version whose sums run over *all* rows including
*i* — so `y_i` appears on the right-hand side of its own encoding. Prokhorenkova
et al. 2018 formalise this as *target leakage* / *prediction shift* and show the
ordered variant restores the property that a row's encoding is independent of its
own label, at the cost of variance for rows early in σ (hence *s* independent
permutations). The same "use only the prefix" construction applied to gradients is
**ordered boosting**.

**Two configuration facts that decide whether any of this is even active** (both
verified against the CatBoost docs, §5):

- `one_hot_max_size` defaults to **2** on CPU. Region (22), VehBrand (11) and
  Area (6) therefore get **CTRs (ordered target statistics)**; only VehGas (2) is
  one-hot encoded. Ordered TS **is** engaged for the features RQ3 is about.
- `boosting_type` defaults to **`Plain` on CPU**. Ordered *boosting* is therefore
  **off** in the study's configuration. RQ3 tests ordered **target statistics**;
  it does *not* test ordered boosting. Say so in `findings.md` or the claim
  over-reaches.

### E3 — Monotone constraint as a split-finding restriction

For feature *j* with constraint `c_j = +1`, every node carries a band `[ℓ, u]`
inherited from its ancestors, and the split search admits a split on *j* only if
the resulting leaf values satisfy

$$
v_{\text{left}} \le v_{\text{right}},
\qquad v_{\text{left}}, v_{\text{right}} \in [\ell, u],
$$

with the children's bands tightened so the ordering can never be undone deeper in
the tree. Additive stagewise composition preserves the property, so the ensemble
`F_M = Σ_m ν h_m` inherits it. The scikit-learn user guide states the resulting
guarantee exactly as

$$ x_1 \le x_1' \;\Longrightarrow\; F(x_1, x_2) \le F(x_1', x_2) . $$

Encoding: `+1` increase, `0` unconstrained, `-1` decrease, one entry per **input**
feature. Categorical features cannot be constrained (categories are unordered) —
`hgbt_monotone` therefore puts `0` on every categorical position and `+1` on
BonusMalus only. **Verified against the pinned scikit-learn 1.9.0 source**: `fit`
calls `_check_monotonic_cst` and then *remaps* the constraint vector to the
internal layout (categoricals are moved to the front by `_preprocess_X`) — passing
`monotonic_cst` alongside `categorical_features` with zeros on the categoricals
does **not** raise; the caller keeps original column order. Since the constrained
column is standardised by a positive affine map, the constraint direction is
unchanged by preprocessing.

### E4 — Surrogate distillation and the interaction score

Weighted least squares of a main-effects basis against the **teacher's train-fold
log-predictions**:

$$
\hat{\theta} \;=\; \arg\min_{\theta} \sum_{i \in \mathrm{TRAIN}} w_i
\Big(\underbrace{\log \hat{\mu}_{\mathrm{GBDT}}(x_i)}_{F(x_i)} - g(x_i;\theta)\Big)^{\!2},
\qquad
r_i \;=\; F(x_i) - g(x_i;\hat{\theta}),
$$

$$
R^2_{\text{main}} = 1 - \frac{\sum_i w_i r_i^2}{\sum_i w_i\,(F_i - \bar{F}_w)^2},
\qquad
\mathrm{score}(a,b) \;=\;
\frac{\big|\sum_i w_i\, z^{ab}_i\, r_i \big/ \sum_i w_i\big|}
     {\sqrt{\sum_i w_i r_i^2 \big/ \sum_i w_i}} \;\in[0,1].
$$

`score(a,b)` is the **weighted correlation between the standardised product column
and the residual**. Rank the 10 pairs; adopt the top-K into the real GLM.

*What `R²_main` does and does not mean.* It is measured on the **log-score
surface**, not on deviance. High `R²_main` with a stubborn deviance gap would mean
the gap lives in the **basis/knots** (curvature the scoped splines do not span),
not in interactions — a different, equally reportable RQ5 answer. It is a
diagnostic, not a bound on recoverable deviance. Read it that way in `findings.md`.

*Cross-check instrument.* `forensics.two_way_pd_gap` computes, on the log scale,
`PD₂(a,b) − [PD₁(a) + PD₁(b)]` on a quantile grid; the standard deviation of that
centred residual surface is the pair's non-additivity in **log-rate units**, and is
model-agnostic (any object with `.predict`). A pair is adopted only if the
surrogate score and the PD signature agree.

### E5 — Segment decomposition of the deviance gap (an identity, not an approximation)

$$
D(m) \;=\; \sum_i w_i\, d\big(y_i, \mu_m(x_i)\big)
\;=\; \sum_{k=1}^{K} \underbrace{\sum_{i \in S_k} w_i\, d\big(y_i, \mu_m(x_i)\big)}_{D_k(m)}
$$

$$
\Delta \;=\; D(\mathrm{GLM}) - D(\mathrm{GBDT})
\;=\; \sum_{k=1}^{K} \big[D_k(\mathrm{GLM}) - D_k(\mathrm{GBDT})\big]
\;=\; \sum_{k=1}^{K} \Delta_k,
\qquad
\text{gap share}_k = \frac{\Delta_k}{\Delta},\quad \sum_k \text{gap share}_k = 1 .
$$

Exact for **any** disjoint partition `{S_k}` of the evaluation rows — that is the
entire content of the method, and it is why a segment table is an *attribution*
rather than an approximation. Note that individual `Δ_k` may be **negative**
(segments where the GLM is *better*); the shares still sum to 1, and a share > 1
alongside a negative share elsewhere is a real, reportable structure, not a bug.
The reported metric is a *mean* (`D/Σw`), so a segment's mean deviance must always
be shown next to its **exposure share** or a 1%-exposure segment will look decisive
when it is noise.

---

## 3. Minimal from-scratch implementation plan

### 3.1 What already exists (the practice leg)

| Layer | Object | Role |
|---|---|---|
| study library | `pipeline.py: make_model(...)` | the seven frozen constructors: `glm_ohe`, `glm_scoped_splines`, `glm_interactions`, `hgbt_ohe`, `hgbt_monotone`, `lgbm_poisson`, `catboost_poisson` |
| study library | `pipeline.py: CatBoostPoisson` | the M1 prediction-space fix — `predict(..., prediction_type="Exponent")` |
| study library | `pipeline.py: ClippedRegressor` | clips μ to ≥ 1e-6 (the registry refuses μ ≤ 0 by contract) and **replays the frame-level transform** (log-Density, interaction products) at predict time |
| study library | `pipeline.py: _scoped_preprocessor` | the study-04 E0002 fix — the spline basis touches only `["DrivAge","BonusMalus","Density"]`, never the OHE dummies |
| forensics (off-ledger) | `forensics.py: segment_deviance_gap` | **M5**, E5 |
| forensics (off-ledger) | `forensics.py: surrogate_glm` | **M4**, E4 |
| forensics (off-ledger) | `forensics.py: two_way_pd_gap` | **M4** cross-check (PD₂ − PD₁ − PD₁, log scale) |
| kleinlib | `kleinlib.data.three_way_split` | the frozen 60/20/20 seed-42 split |
| kleinlib | `kleinlib.encoders.build_preprocessor(kind="ohe" \| "native")` | OHE for the GLM/HGBT/LGBM arms; native categoricals for `hgbt_monotone` (verified to emit columns as NUMERIC-then-CATEGORICAL, which is what the `monotonic_cst` and `categorical_features` index vectors assume) |
| kleinlib | `kleinlib.eval.evaluate_regression` | the `val_poisson_deviance` metric spec (exposure-weighted-rate convention), the `calibration_ratio` aux line (Σwμ̂ / Σwy), and the non-finite / near-constant prediction guards |
| kleinlib | `kleinlib.eval.save_holdout_predictions` | per-row sealed-run export (dims DrivAge, BonusMalus, VehGas, Region) feeding the off-ledger sealed-gap join and the pricing-eval double-lift card |
| kleinlib | `kleinlib.noise_floor.summarize_noise` / `floor_from_sidecar` / `yaml_block` | anchor-0 measurement sweeps → the measured `minimum_delta` |
| kleinlib | `kleinlib.sweep.SweepRunner` | the sanctioned escape hatch for the seed / bootstrap / data-volume sweeps |

**`kleinlib.torch_loop` is deliberately NOT used** — this study has no torch
component, so the MPS-safe streamed index-shuffle batching helper and the
torch/LightGBM `libomp` two-stage isolation war story do not apply. (LightGBM and
CatBoost run in the same process as sklearn without torch, which is the safe
combination.)

**Pre-loop sanity (evidence for the practice leg, run off-ledger on this branch):**
`hgbt_ohe` → **0.444689**, bit-matching study 04's published anchor;
`lgbm_poisson` → **0.444413**; `catboost_poisson` → **0.446332** through
`prediction_type="Exponent"`; `calibration_ratio` ≈ **1.02** on all three. The
constructors run, the metric registry accepts them, and the CatBoost prediction
space is right. These numbers are *not* ledger evidence — E0001–E0002 must
reproduce them through `klein run-one`.

### 3.2 The from-scratch sketch — M4 + M5 in ~30 lines of numpy/pandas

This is `forensics.py` distilled to its load-bearing arithmetic. No sklearn
estimator is needed for either method: M5 is a groupby over an identity and M4 is
one weighted `lstsq` plus ten weighted correlations.

```python
import numpy as np, pandas as pd
from itertools import combinations

def dev_rows(y, mu, w):                       # per-row weighted Poisson deviance; sum == D(m)
    t = np.where(y > 0, y * np.log(y / mu) - (y - mu), mu)
    return 2.0 * w * t                        # E5's summand — the whole basis of the decomposition

# ---- M5 (E5): exact additive attribution over ANY disjoint partition -------------
def gap_by_segment(y, w, mu_glm, mu_gbdt, seg, n_bins=8):
    if pd.api.types.is_numeric_dtype(seg) and seg.nunique() > n_bins:
        seg = pd.qcut(seg, n_bins, duplicates="drop")          # coarse bins: shares must be stable
    f = pd.DataFrame({"s": np.asarray(seg), "w": np.asarray(w, float),
                      "g": dev_rows(y, mu_glm, w), "b": dev_rows(y, mu_gbdt, w)})
    total = f.g.sum() - f.b.sum()             # == D(GLM) - D(GBDT): the headline gap, exactly
    k = f.groupby("s", observed=True)
    return pd.DataFrame({"exposure_share": k.w.sum() / f.w.sum(),          # never omit this column
                         "mean_dev_glm":   k.g.sum() / k.w.sum(),
                         "gap_share":      (k.g.sum() - k.b.sum()) / total  # sums to 1 by construction
                        }).sort_values("gap_share", ascending=False)

# ---- M4 (E4): surrogate GLM on the TEACHER's TRAIN-fold log-predictions ----------
def surrogate_screen(F_train, X_train, cols, w):      # F_train = log mu_gbdt(X_train); NEVER y
    z = {c: (lambda v: (v - v.mean()) / (v.std() + 1e-12))(X_train[c].to_numpy(float)) for c in cols}
    A = np.column_stack([np.ones(len(F_train))] + [z[c] ** p for c in cols for p in (1, 2, 3)])
    s = np.sqrt(np.asarray(w, float))
    beta, *_ = np.linalg.lstsq(A * s[:, None], F_train * s, rcond=None)     # weighted OLS
    r = F_train - A @ beta                    # what main effects CANNOT reproduce
    r2_main = 1 - np.sum(w * r**2) / np.sum(w * (F_train - np.average(F_train, weights=w)) ** 2)
    rank = []
    for a, b in combinations(cols, 2):        # C(5,2) = 10 screened — report this number
        p = z[a] * z[b]; p = (p - p.mean()) / (p.std() + 1e-12)
        rank.append((a, b, abs(np.average(p * r, weights=w))
                     / (np.sqrt(np.average(r**2, weights=w)) + 1e-12)))
    return r2_main, sorted(rank, key=lambda t: -t[2])          # adopt top-K, report K of 10
```

The adopted pairs then enter the ledger through the **existing** frozen surface —
`train.py`'s `INTERACTIONS = (("BonusMalus", "DrivAge"),)` with
`MODEL = "glm_interactions"` — so an adoption is a 2-line `train.py` diff evaluated
by the normal `klein run-one` transaction. No new library code, no new dependency.

### 3.3 Multiplicity discipline (non-negotiable)

| Step | Fold | What may be looked at |
|---|---|---|
| **Derive** | TRAIN only | the teacher's train-fold log-predictions; `R²_main`; the 10-pair ranking. Development labels are not read. |
| **Evaluate** | DEVELOPMENT | one `klein run-one` per adopted candidate; a candidate is kept only on a frontier improvement ≥ the **measured** glm `minimum_delta` |
| **Seal** | TEST, once per track | `klein run-one --final-test`; predictions exported; the sealed gap and its paired-difference SE computed off-ledger after **both** accesses are spent |

Reported in `findings.md` §③ verbatim: **screened = 10 pairs, adopted = K (K ≤ 2)**,
plus every candidate that was screened and *rejected*. A screen you report is a
screen; a screen you hide is p-hacking. Interactions are numeric×numeric only; if a
pair is adopted, its **cross-check** (`two_way_pd_gap` strength, in log-rate units)
is reported alongside its surrogate score.

### 3.4 Why not SHAP interaction ranking

TreeSHAP interaction values (Lundberg, Erion & Lee 2018) are the obvious
alternative instrument, and `SHAP for Actuaries` (Mayer, Meier & Wüthrich 2023) is
the actuarial-audience-facing version. Three reasons this study does not use them:

1. **No new dependency.** `shap` is not in the locked environment (`pyproject`
   extras are `gbdt` / `deep`). Adding it edits `uv.lock` — a **library** change,
   which the loop contract keeps rare and deliberate, not a per-experiment
   `train.py` diff. Nothing in RQ1–RQ7 requires it.
2. **SHAP ranks; the surrogate *translates*.** A SHAP interaction value tells you a
   pair matters and by how much *in the teacher's own attribution space*. It does
   not hand you a design-matrix column. The surrogate does both in one step — the
   product column that scores highest **is** the column promoted into the GLM — so
   the screening statistic and the intervention are the same object and a hit is
   directly falsifiable by a refit. For a study whose deliverable is
   *translate-back*, that is the deciding property.
3. **Cost and scope.** Exact TreeSHAP interaction values are O(T·L·D²) per row
   over a 135k-row fold and three different libraries; the surrogate screen is one
   `lstsq` (milliseconds). SHAP interactions are also defined for the tree ensemble
   only, whereas the surrogate/PD screen works against anything with `.predict` —
   which matters precisely because this study compares HGBT, LightGBM and CatBoost.

**The honest cost of that choice.** The surrogate screen sees only
**numeric × numeric products in a cubic basis**. A categorical × numeric
interaction (Region × DrivAge), or a pure *threshold* interaction, is invisible to
it. `two_way_pd_gap` covers part of that hole model-agnostically, and RQ5's
predicted hard non-additive residue (≥ 30% of the gap) is exactly where such
structure would hide. If the segment decomposition (M5) localises the gap in a
categorical dimension that the surrogate cannot reach, **say so** — "our instrument
could not see it" is a finding, and a stated blind spot is worth more than a
silently missed one.

---

## 4. When it pays / when it doesn't

### 4.1 Regime table

| # | Method | Pays when | Doesn't pay when | Verdict for THIS study (406,807 train rows; 0.0737 claims/exposure-yr; 5 numerics; cats ≤ 22 levels) |
|---|---|---|---|---|
| **M1** | Poisson boosting across libraries | you need a specific stack (GPU, deployment, native cats); or you are about to **publish a gap someone will re-run in their own library** | as an accuracy lever — at matched capacity and matched loss the three land inside noise on clean 10⁵–10⁶-row tabular data (`gbdt-tabular.md`: ~0.002 AUC spread) | **Equivalence expected, but capacity is NOT matched out of the box** (§4.3, risk R1). Pre-loop: LGBM−HGBT = −0.000276 (0.15× provisional floor, a tie); CatBoost−HGBT = +0.001643 (0.92× provisional floor, a small deficit) |
| **M2** | CatBoost ordered target statistics | high cardinality (10²–10⁴ levels), **few rows per level**; the greedy-TS bias scales ~1/n_level | ≤ ~50 levels with 10³⁺ rows each; or when you were going to OHE anyway | **Does not pay.** Region median level ≈ 9,000 train rows (≈350 claims); the thinnest level (≈795 rows, ≈31 claims) is 0.2% of the book. Nothing to leak where the exposure is. Matches study 04's 0.37×-floor native-vs-OHE tie and `gbdt-tabular.md`'s "native categorical handling is a small-data myth" |
| **M3** | Monotone constraints (HGBT) | the shape is **required for filing**; or the true effect is monotone and the constraint acts as a variance reducer at small n | the true effect is non-monotone (wrong sign cost −0.005 AUC in the ancestor campaign); or n is large enough that the model estimates the shape itself, so the constraint only removes fit | **Cheap but not free-by-assumption.** BonusMalus is an experience-rating index (higher = worse history), so +1 is the plausible sign — but the **empirical** sign must be checked before the cost is interpreted (`gbdt-tabular.md` standing warning) |
| **M4** | Surrogate-GLM distillation | the black-box beat is **real and large** relative to noise; the interpretable family is fixed by filing; the candidate structure is **low-dimensional** | the advantage lives in high-order or categorical-heavy structure the surrogate basis cannot span; the teacher is itself overfit (then you distil noise); or you are free to just deploy the black box | **Pays partially.** Gap = 0.010172 = 11.4 paired SEs — large enough to attribute. 10 candidate pairs is a tractable multiplicity. But the basis is numeric-only, so a categorical interaction escapes it |
| **M5** | Segment deviance decomposition | **almost always** — it is an identity, one groupby, and it converts a scalar into a map. Pays most when the aggregate delta is small but **concentrated** | as *evidence* — it is descriptive, same-fold, and carries no uncertainty; per-segment shares from thin segments are wildly unstable | **Pays, with discipline.** ≥ 8 quantile bins on numerics, raw levels for Region/VehBrand, exposure share always reported next to gap share, and bootstrap the shares before any share is quoted as a number in `findings.md` |

**Doctrinal position** (`gbdt-tabular.md`, Grinsztajn et al. 2022): trees still win
on typical tabular data; nothing here challenges that. The novelty of this study is
not *whether* the tree wins but **where the win lives and how much of it is
GLM-representable** — which is why M4 and M5, not M1–M3, are the methodological
core.

### 4.2 Falsifiable priors this card stakes

These are **method-level** priors, distinct from and additional to the six
outcome-level entries already in `study.yaml:predictions_to_falsify` (which cover
RQ1–RQ5 and RQ7). Each names a lever, a direction and a magnitude, and each can
come out false. `floor_gbdt` / `floor_glm` denote the **measured** anchor-0 floors;
where a number is quoted against the provisional 0.001786 floor it is flagged.

| ID | Prior | Falsified if |
|---|---|---|
| **M1-a** | **Capacity is not matched at nominal `max_iter=200`**: HGBT's fitted `n_iter_` at the E0002 anchor is **< 200**, because `early_stopping="auto"` engages above 10,000 samples and reserves `validation_fraction=0.1` of the train fold, while LGBM (`n_estimators=200`, no `eval_set`) and CatBoost (`iterations=200`, no eval set) build all 200 trees | `n_iter_ == 200` |
| **M1-b** | **The RQ2 tie survives the confound**: after matching *effective* capacity (HGBT with `early_stopping=False`, or LGBM truncated to HGBT's `n_iter_`), `\|Δ(LGBM, HGBT)\|` remains **< 2 × floor_gbdt** — i.e. the tie is a property of the algorithms, not an artefact of unequal tree counts | the matched-capacity delta exceeds 2 × floor_gbdt |
| **M2-a** | **CatBoost's deficit is structural, not categorical**: re-running `catboost_poisson` with `one_hot_max_size=32` (forcing OHE for Region/VehBrand/Area, switching ordered TS **off** for exactly the features RQ3 is about) moves development deviance by **< 0.5 × floor_gbdt**. The remaining CatBoost−HGBT deficit (+0.001643 pre-loop = 0.92× the provisional floor) is therefore attributable to **symmetric-tree capacity**, not to categorical handling | the `one_hot_max_size` change moves deviance by ≥ 0.5 × floor_gbdt (⇒ ordered TS *is* doing work here, and RQ3's prior is wrong for the stated reason) |
| **M3-a** | **The constraint sign is empirically correct**: exposure-weighted mean frequency is non-decreasing in BonusMalus across ≥ 90% of train-fold exposure when binned into 8 quantile bins, so `+1` is the right direction (a wrong-sign constraint would cost ≥ 5 × floor per the ancestor campaign) | monotonicity holds over < 90% of exposure |
| **M4-a** | **The gap is mostly not an interaction gap**: the train-fold surrogate's weighted `R²_main` against the HGBT log-score **exceeds 0.90** — i.e. ≥ 90% of the teacher's log-rate surface is main-effects-representable in a cubic basis | `R²_main ≤ 0.90` |
| **M4-b** | **The top-ranked pair is (BonusMalus, DrivAge)** — the two factors are structurally confounded in French MTPL (young drivers enter at the 100 base level), so their joint effect is the most likely non-additive signature | any other pair ranks first |
| **M5-a** | **The gap concentrates**: in an 8-bin quantile decomposition on BonusMalus, the top-3 segments by `gap_share` carry **≥ 50%** of the total gap while covering **≤ 25%** of exposure | the top-3 segments carry < 50% of the gap, or need > 25% of exposure to reach it (⇒ the advantage is diffuse, a genuinely different and equally reportable finding) |
| **M4-c** | **Multiplicity is bounded and honest**: exactly **10** pairs screened, **≤ 2** adopted, no candidate adopted on a development improvement smaller than 1 × floor_glm, and every rejected candidate reported | more than 2 adopted, or a sub-floor adoption, or an unreported screen |

*Not yet mirrored into `study.yaml`.* `study.yaml`'s hash is bound to the recorded
CONSULT gate and its `minimum_delta` is provisional pending anchor-0; the
orchestrator should append these as `predictions_to_falsify` entries at the same
time it re-records CONSULT with the measured floors. A ready-to-paste YAML block is
in the hand-back.

### 4.3 Method-level risks the loop must watch

| ID | Risk | Watch / mitigation |
|---|---|---|
| **R1** | **Unequal effective capacity across libraries.** HGBT early-stops (`early_stopping="auto"` fires above 10k samples) on 10% held-out train rows; LGBM and CatBoost at `n_estimators`/`iterations = 200` do not. "Matched capacity" at nominal 200 is not matched. | Log `n_iter_` (HGBT), `booster_.num_trees()` (LGBM), `tree_count_` (CatBoost) into `aux_metrics.tsv` on E0002–E0004. Test M1-b before writing RQ2's verdict. |
| **R2** | **`hgbt_monotone` changes TWO things at once.** `hgbt_ohe` uses `kind="ohe"`; `hgbt_monotone` uses `kind="native"`. Differencing them measures *monotone + encoding switch*, and RQ7's predicted effect (< 1× floor) is smaller than study 04's measured native-vs-OHE spread (0.37× floor). | Run an unconstrained **native** control (same constructor, `monotonic_cst=None`) and difference against **that**, or state the confound explicitly in the RQ7 verdict. |
| **R3** | **CatBoost tests ordered TS, not ordered boosting.** `boosting_type` defaults to `Plain` on CPU; `one_hot_max_size=2` means CTRs *are* built for Region/VehBrand/Area. | Record both settings in the manifest `extra`. Word RQ3's claim as "ordered target statistics", never "ordered boosting". |
| **R4** | **CatBoost prediction space.** Any future CatBoost variant that bypasses `CatBoostPoisson.predict` gets `RawFormulaVal` (a log) and will produce a nonsense deviance — or be rejected by the ≤ 0 guard, which is the *lucky* outcome. | The `prediction_type="Exponent"` call site is frozen in `pipeline.py`; never inline a `CatBoostRegressor` in `train.py`. |
| **R5** | **~2% A/E bias on all three models** (`calibration_ratio` ≈ 1.02 pre-loop). The GLM-vs-GBDT deviance comparison is between two similarly mis-calibrated models. | Report `calibration_ratio` for **every** ledger row and for both sealed runs. Do **not** silently rebase or isotonically recalibrate — it would break the 0.454861 / 0.444689 anchors and destroy cross-study comparability. If a recalibrated variant is wanted, it is a *new* candidate with its own row. |
| **R6** | **Segment shares are unstable in thin bins.** A 1%-exposure segment can show a >30% gap share by noise, and negative `Δ_k` makes shares exceed 1. | Never quote a `gap_share` without its `exposure_share`; use ≥ 8 quantile bins; bootstrap the shares (reuse the anchor-0 paired-bootstrap machinery) before any share enters `findings.md`. |
| **R7** | **Surrogate blind spot.** The screen only sees numeric × numeric products in a cubic basis; Region × DrivAge and pure threshold interactions are invisible. | Cross-check every adopted pair with `two_way_pd_gap`; if M5 localises the gap in a categorical dimension, state the blind spot rather than reporting "no interaction found". |
| **R8** | **`R²_main` misread as a deviance bound.** It measures the log-score surface, not deviance; a high value does not cap what interactions can recover in the GLM. | Report `R²_main` as a diagnostic with that sentence attached. |
| **R9** | **Duplicate feature profiles straddle train/dev** (4,872, recorded as a data-card NOTE and frozen for anchor comparability). The dev fold is mildly optimistic for *every* model. | Already a declared limitation; it applies equally to both tracks, so the **gap** is far more robust than either level. Say exactly that in the RQ1 verdict. |

---

## 5. Verified references

Every row verified 2026-07-31 via `WebFetch` / `WebSearch` against arXiv, the
NeurIPS proceedings, the official library documentation, Springer, and the Swiss
Association of Actuaries' Actuarial Data Science index. **0 UNVERIFIED.**

### Papers

| # | Reference | Where | Verified? |
|---|---|---|---|
| 1 | Prokhorenkova, L., Gusev, G., Vorobev, A., Dorogush, A.V., Gulin, A. (2018). *CatBoost: unbiased boosting with categorical features.* | Advances in NeurIPS **31** (NeurIPS 2018); [arXiv:1706.09516](https://arxiv.org/abs/1706.09516) | ✅ title, 5 authors and arXiv id from the arXiv abstract page; venue confirmed independently on the NeurIPS 2018 proceedings page |
| 2 | Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., Liu, T.-Y. (2017). *LightGBM: A Highly Efficient Gradient Boosting Decision Tree.* | Advances in NIPS **30** (NIPS 2017) | ✅ title, 8 authors, volume/year from the papers.nips.cc 2017 proceedings page |
| 3 | Craven, M. & Shavlik, J.W. *Extracting Tree-Structured Representations of Trained Networks* (TREPAN). | Advances in NIPS **8**; MIT Press | ✅ title + authors on papers.nips.cc (paper 1152). ⚠️ **year ambiguity, stated honestly**: papers.nips.cc labels the volume "NIPS 1995"; the ACM DL record labels the same proceedings the "9th International Conference on NIPS" and the MIT Press volume appeared **1996**. Cite as "NIPS 8 (1995 conference; MIT Press, 1996)" — do not silently pick one year |
| 4 | Hinton, G., Vinyals, O., Dean, J. (2015). *Distilling the Knowledge in a Neural Network.* | [arXiv:1503.02531](https://arxiv.org/abs/1503.02531); comments field: **NIPS 2014 Deep Learning Workshop** | ✅ title, authors, 2015-03-09 submission and the workshop comment from the arXiv abstract page |
| 5 | Lundberg, S.M., Erion, G.G., Lee, S.-I. (2018). *Consistent Individualized Feature Attribution for Tree Ensembles.* | [arXiv:1802.03888](https://arxiv.org/abs/1802.03888) | ✅ title, authors, year; abstract confirmed to "extend SHAP values to interaction effects and define SHAP interaction values" — the exact construct §3.4 declines to use |
| 6 | Grinsztajn, L., Oyallon, E., Varoquaux, G. (2022). *Why do tree-based models still outperform deep learning on typical tabular data?* | NeurIPS **35**, Datasets & Benchmarks Track; [arXiv:2207.08815](https://arxiv.org/abs/2207.08815) | ✅ venue/track from the NeurIPS 2022 D&B proceedings page. ⚠️ **title differs between sources**: arXiv reads "…on tabular data?", the proceedings read "…on *typical* tabular data?" — the proceedings title is used above |

### Insurance / actuarial

| # | Reference | Where | Verified? |
|---|---|---|---|
| 7 | Noll, A., Salzmann, R., Wüthrich, M.V. *Case Study: French Motor Third-Party Liability Claims.* | SSRN **3164764** (posted 2018, revised 2020-03-04) | ✅ title + 3 authors + SSRN id via search index; independently confirmed as "Case Study 1, Article on SSRN, ID 3164764" on the SAA Actuarial Data Science tutorials index. ⚠️ note: `papers.ssrn.com` returns **HTTP 403** to automated fetches — verified through two independent indexes, not by direct fetch |
| 8 | Wüthrich, M.V. & Merz, M. (2023). *Statistical Foundations of Actuarial Learning and its Applications.* | Springer Actuarial (SPACT), **Open Access**, DOI [10.1007/978-3-031-12409-9](https://doi.org/10.1007/978-3-031-12409-9); Ch. 2 *Exponential Dispersion Family*, Ch. 5 *Generalized Linear Models* | ✅ title, authors, series, 2023 copyright, DOI, OA status and chapter list from the Springer book page — the **offset / exposure-weight** treatment behind E1 |
| 9 | Denuit, M., Hainaut, D., Trufin, J. (2019). *Effective Statistical Learning Methods for Actuaries I: GLMs and Extensions.* | Springer Actuarial, DOI [10.1007/978-3-030-25820-7](https://doi.org/10.1007/978-3-030-25820-7); ISBN 978-3-030-25819-1 (softcover) / 978-3-030-25820-7 (eBook) | ✅ title, 3 authors, series, 2019, DOI and both ISBNs from the Springer book page — second source for the offset/exposure GLM treatment |
| 10 | Lorentzen, C. & Mayer, M. (2020). *Peeking into the Black Box: An Actuarial Case Study for Interpretable Machine Learning.* | SSRN **3595944**, DOI 10.2139/ssrn.3595944; SAA ADS tutorial 8 | ✅ title, both authors, 2020-05-07 posting, SSRN id via search index; independently present as ADS tutorial 8 with public R code — the freMTPL2-native precedent for the M4 forensics layer |
| 11 | Mayer, M., Meier, D., Wüthrich, M.V. (2023). *SHAP for Actuaries: Explain any Model.* | SSRN **4389797**; SAA ADS Case Study 14 | ✅ title, 3 authors, 2023-03-15 posting via search index; independently confirmed as "Case Study 14, SSRN ID 4389797" on the ADS tutorials index — the alternative instrument §3.4 declines |
| 12 | Actuarial Data Science tutorials index, Swiss Association of Actuaries. | <https://www.actuarialdatascience.org/ADS-Tutorials/> | ✅ fetched; 16 case studies listed, Case Study 1 = French MTPL with SSRN ID 3164764, each with GitHub code — the corroborating index for refs 7, 10, 11 |

### Library documentation (the implementation facts §2–§4 rest on)

| # | Reference | Where | Verified? |
|---|---|---|---|
| 13 | scikit-learn user guide — *Ensembles: gradient boosting …*, **v1.9.0** | <https://scikit-learn.org/stable/modules/ensemble.html> | ✅ `poisson` listed as an HGBT regression loss ("well suited to model counts and frequencies"); the monotonic-constraints section gives the `+1 / 0 / -1` encoding, the guarantee `x₁ ≤ x₁′ ⟹ F(x₁,x₂) ≤ F(x₁′,x₂)`, and "Since categories are unordered quantities, it is not possible to enforce monotonic constraints on categorical features" |
| 14 | scikit-learn API — `HistGradientBoostingRegressor`, **v1.9.0** | <https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html> | ✅ defaults captured: `max_iter=100`, `max_leaf_nodes=31`, `max_depth=None`, `min_samples_leaf=20`, `l2_regularization=0.0`, `max_bins=255`, `validation_fraction=0.1`, `n_iter_no_change=10`; **`early_stopping='auto'` = "early stopping is enabled if the sample size is larger than 10000"** (the source of risk R1); `poisson` loss "internally uses a log-link" |
| 15 | scikit-learn example — *Tweedie regression on insurance claims*, **v1.9.0** | <https://scikit-learn.org/stable/auto_examples/linear_model/plot_tweedie_regression_insurance_claims.html> | ✅ uses freMTPL2 (OpenML 41214/41215) and fits `PoissonRegressor` on `Frequency = ClaimNb/Exposure` with `sample_weight=Exposure` — the same parameterisation as this study. ⚠️ **verified absence**: the page does *not* state the offset↔weight equivalence in prose, so E1 is derived in §2 rather than cited to it |
| 16 | LightGBM parameters documentation (stable) | <https://lightgbm.readthedocs.io/en/stable/Parameters.html> | ✅ `objective="poisson"` present; **`poisson_max_delta_step` default 0.7** ("to safeguard optimization" — an HGBT-absent regulariser); `num_leaves=31`, `min_data_in_leaf=20`, `max_bin=255`, `lambda_l1=lambda_l2=0`, `feature_fraction=bagging_fraction=1.0`, `max_depth=-1`; growth is leaf-wise |
| 17 | CatBoost training parameters (common) | <https://catboost.ai/docs/en/references/training-parameters/common> | ✅ **`boosting_type` default `Plain` on CPU** (⇒ ordered boosting OFF, risk R3); **`one_hot_max_size` default 2** with "Ctrs are not calculated for such features" (⇒ ordered TS ON for Region/VehBrand/Area); `grow_policy` default `SymmetricTree`; `depth=6`; `l2_leaf_reg=3.0` |
| 18 | CatBoost `CatBoostRegressor.predict` | <https://catboost.ai/docs/en/concepts/python-reference_catboostregressor_predict> | ✅ `prediction_type ∈ {Probability, Class, RawFormulaVal, Exponent, LogProbability}`; "**Exponent for Poisson and Tweedie**, RawFormulaVal for all other loss functions" — the fact `pipeline.py:CatBoostPoisson` encodes (risk R4) |

**Frontier lit-scan.** None of M1–M5 is a 2023+ frontier architecture, so the scan
is a *positioning* scan rather than a novelty hunt. Seminal: CatBoost (ref 1),
LightGBM (ref 2), distillation (refs 3–4). Follow-up / alternative instrument:
TreeSHAP interaction values (ref 5), rejected with reasons in §3.4. Resonant
domain applications: the freMTPL2 case study itself (ref 7), *Peeking into the
Black Box* (ref 10) — the closest published precedent for this study's forensics
layer, on the **same dataset** — and *SHAP for Actuaries* (ref 11), the tooling
line this study deliberately does not follow. Standing tabular doctrine: Grinsztajn
et al. (ref 6). **Honest positioning:** the individual techniques are all
well-established; what this study contributes is not a new method but a
**protocol** — deriving translate-back structure on train, adopting it on
development under a reported multiplicity budget, and confirming the resulting gap
as a difference of **two sealed test numbers**. Ref 10 does the forensics without
the seal; study 04 did the seal on one track only. Doing both at once is the gap in
the literature this study fills.
