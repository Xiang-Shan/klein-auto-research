---
type: method-card
domain: "deep-learning scaling (image classification)"
profile: "ml-research"
status: complete
concepts: [data-scaling-law, log-log-least-squares, effective-exponent, irreducible-loss, extrapolation-leverage, seed-bootstrap, nested-subsamples, sealed-extrapolation, signed-relative-error, best-checkpoint-early-stopping]
related: [knowledge/method_cards/scaling-law-fits.md, knowledge/method_cards/cnn-image-classification.md, 22-cnn-data-scaling]
refs_verified: true   # 16/16 rows verified 2026-11-03 (arXiv API / Crossref / proceedings + full text), then `klein refs verify --record`: 16 ok, 0 failed
triad:                 # the Theory + Papers + Practice contract — self-asserted, gate-checked
  theory: true         # §2: notation table + five load-bearing equations
  papers: true         # references.yaml: 16 rows, every one verified (refs_verified: true)
  practice: true       # §3: the plan lib/protocol.py + lib/scaling.py + analyze.py already realize, plus a synthetic harness of lib/scaling.py run with a stated seed
---

# Method card — a data-scaling law fitted on six small training sets, tested on a seventh

> Gate 2 (METHOD). Pedagogy written BEFORE any cell runs. Protocol:
> `.claude/skills/klein/references/method-gate-protocol.md`. The study's CNN was not
> trained for this card. Every number below is literature (cited), protocol arithmetic
> (from `lib/protocol.py` constants), or **SYNTHETIC** (a made-up learning curve plus
> made-up noise pushed through `lib/scaling.py`, generator seeds stated in §3). None of
> it is evidence about Fashion-MNIST.

## 1. Intuition (for a practitioner)

You quote scaling exponents, so you know the picture: plot held-out loss against
training-set size on log-log axes, see a straight line, and read the slope as the exponent α.
Ten times more data then multiplies the loss by 10^-α. At α = 0.22 that is a 40% cut per
decade. This card is about how much that slope is worth once you leave the range it was
measured on.

**The analogy: a fitted scaling exponent is a tangent line, not a law.** On log-log axes
almost any smooth, decreasing curve looks straight over a short enough interval. A fit over
N = 500 to 16,000, which is 1.5 decades, measures the *average local slope of the
learning curve over that interval*, the chord slope. That number can be pinned very
precisely (in the synthetic checks below its seed-to-seed spread is about ±0.006) and still
be the wrong slope to extrapolate with. The question is not "how well is the line pinned?"
but "is the curve still a line out there?" Extrapolating to N = 60,000 means extrapolating
the tangent.

**Why the curve should bend here.** Four things sit inside one cell's loss besides the
amount of data:

- **Label ambiguity.** Some shirts look like T-shirts and some pullovers like coats. No
  model gets under that floor.
- **Model capacity.** This study fixes one 23,946-parameter network. The scaling-law
  literature that reports clean power laws usually grows the model with the data:
  Hestness et al. searched a best-fit model size for every shard. For a FIXED model the
  data curve saturates at a model-dependent floor (Rosenfeld et al. 2020). Equivalently,
  in Chinchilla's form E + A/P^α + B/D^β (P = parameters, D = data; Hoffmann et al. write
  N for parameters), freezing the model turns the first two terms into one constant floor.
- **The training budget.** Each cell trains for a schedule that depends on N. A cell that
  stops before its best possible loss sits above the data-limited curve.
- **Noise.** It comes in two kinds: which N images you happened to draw (data-sampling
  noise) and how the run went (initialization and minibatch order, training noise).

A floor makes the curve flatten as N grows. The local slope decays toward zero, so a
straight line fitted on the steep early part predicts too low a loss further out. The law
is then **optimistic**, and the signed relative error at 60,000 comes out positive. That
is the bet behind P4.

**What R² on log-log axes is and is not.** R² there is the fraction of the spread of the
six log-losses that the line accounts for. A steep curve has a big spread, so it buys R²
almost for free. R² ≥ 0.98 tolerates a root-mean-square wobble of about 3.7% around the
line at α = 0.22, and a floor that bends the curve only at the top of the range barely
moves it. So a high R² says "the six cells are roughly collinear in log-log". It does not
say "there is no floor", and it does not say "the line extrapolates". In the synthetic
checks a curve whose pure-law extrapolation misses by 20% still scores R² of 0.986 to 0.995
when α_eff is 0.25 to 0.36.

**Two kinds of noise, and nested subsamples.** Each cell is three seeds. A seed draws
its own subsample, so data-sampling noise is inside the cell's seed spread, not just
training noise. Within one seed the subsamples are *nested*: the 500 images are part of
the 1,000, which are part of the 2,000, and so on. One seed's six cells also start from
the same initial weights, because `seed_everything(seed)` runs before the model is built. That
makes one seed's six losses a correlated curve rather than six independent draws. This
matters for the error bar on α (equation 3), and in the opposite direction from the one
the instrument's docstring assumes.

**The sealed test.** After the six cells are pinned and the fit is frozen, the network is
trained once on all 60,000 official training images and scored once on the official
10,000 test images. The prediction a·60,000^-α is compared with that measured loss. The
**signed relative error** (measured − predicted) / measured is positive when the law was
optimistic. P3 asks whether it is small (|e| ≤ 0.20) and P4 asks whether it is positive.
3.75× past the last cell is a short extrapolation. The order of magnitude you actually
want to forecast is harder, and this study can only tell you how wrong the simplest law
already is at 3.75×.

**The step schedule.** Small N trains for many epochs, and the best checkpoint is
early stopping. A cell trains max(400, 20 epochs) optimizer steps (capped at 12,000), so
the smallest cells loop over their data many times: 114 epochs at N = 500, 57 at
1,000, 28 at 2,000. A small network that sees 450 images 114 times will memorize them,
and its cross-entropy on new images rises as it becomes confidently wrong. The protocol
therefore holds out 10% of each subsample as an *inner* validation set, scores it on a
grid of checkpoints, and keeps the best one. That is early stopping, and it is what makes
the curve *data-limited* rather than *epoch-limited*. Kaplan et al.'s L(D) is likewise
stated for early-stopped training, and Nakkiran et al. note that sample-wise "more data
hurts" effects often vanish under optimal early stopping. It has a cost at small N:
the inner set at N = 500 is only 50 images and the checkpoint grid is 14 epochs apart, so
the selected checkpoint is a noisy guess at the best one.

## 2. Math core

| Symbol | Meaning |
|---|---|
| `N` | training-set size of a cell: the drawn subsample, including its 10% inner validation share |
| `N_k`, `k = 0..5` | the six development sizes 500, 1,000, 2,000, 4,000, 8,000, 16,000 (doubling) |
| `N★ = 60,000` | the sealed cell's size (the whole official training set) |
| `s ∈ {0,1,2}` | seed: fixes the subsample, its inner split, the minibatch order and the initial weights |
| `L_{k,s}` | development cross-entropy (nats per image, `val_mlogloss`) of seed `s` at `N_k`, scored on the 10,000 development rows at the best inner checkpoint |
| `L̄_k` | the seed mean `(1/3) Σ_s L_{k,s}` (what `lib/scaling.py` fits) |
| `x_k = ln N_k`, `y_k = ln L̄_k` | log axes; `x̄ = 7.9475`, `S_xx = Σ(x_k − x̄)² = 8.4079` |
| `a`, `α` | scale and exponent of the pure law `L(N) = a N^-α` |
| `R²` | coefficient of determination of the line in log space |
| `L∞`, `b`, `β` | floor, scale and exponent of the saturating law `L(N) = L∞ + b N^-β` |
| `f(N) = L∞ / L(N)` | floor fraction: the share of the loss at `N` that more data cannot remove |
| `α_eff(N)` | local log-log slope `−d ln L / d ln N` |
| `w_k`, `h_k` | slope weights and extrapolation leverages of cell `k` (equations 1 and 4) |
| `B = 2,000` | bootstrap draws (`BOOTSTRAP_DRAWS`) |
| `L★_s` | sealed test cross-entropy of seed `s` at `N★` on t10k |
| `e_s`, `e` | per-seed signed relative error and its seed mean (`extrapolation_rel_error`) |
| `steps(N)`, `t*` | the step budget of a cell and its selected checkpoint (`best_step`) |

**(1) The pure law and its fit.** OLS on the six seed means in log space:

$$\ln \bar L_k = \ln a - \alpha\,x_k + \varepsilon_k,\qquad \hat\alpha = -\sum_k w_k\,y_k,\quad w_k = \frac{x_k-\bar x}{S_{xx}},\qquad R^2 = 1-\frac{\sum_k \hat\varepsilon_k^2}{\sum_k (y_k-\bar y)^2}$$

The weights are w = (−0.206, −0.124, −0.041, +0.041, +0.124, +0.206). The two end
cells carry the slope. For a noiseless pure law the denominator of R² is α²·S_xx (0.407
at α = 0.22), so R² ≥ 0.98 allows a residual RMS of √(0.02·0.407/6) ≈ 0.037. That is about
a 3.7% wobble per cell, and the allowance grows with α.

**(2) What a floor does to the fitted exponent.** For `L = L∞ + b N^-β`:

$$\alpha_{\text{eff}}(N) \;=\; -\frac{d\ln L}{d\ln N} \;=\; \beta\,\bigl(1 - f(N)\bigr),\qquad f(N)=\frac{L_\infty}{L(N)}$$

The local slope decays toward 0 as the loss approaches its floor. The pure-law fit returns
an average of α_eff over the six cells, which is larger than α_eff at 60,000, so the
extrapolation is too low. With six points over 1.5 decades this curvature is second-order
and R² barely sees it. A fixed model approaching its own limit is Bahri et al.'s
*variance-limited* regime, where the **excess** loss L − L∞ falls like 1/D. That is
steeper than the pure law in the excess and flat in the total, the wrong shape for
`a N^-α` at any α.

**(3) The bootstrap in `lib/scaling.py`, and what it targets.** Each draw resamples
three seed losses *with replacement, independently within each N*, refits, and takes the
2.5% and 97.5% quantiles of the B = 2,000 slopes. The true sampling variance of α̂ is
`wᵀ Σ̄ w`, where `Σ̄` is the covariance of the six seed means. The bootstrap estimates
something smaller:

$$\operatorname{Var}^*(\hat\alpha^*) \approx \frac{n-1}{n}\sum_k w_k^2\,\frac{s_k^2}{n}\Big|_{n=3} = \tfrac{2}{3}\,\textstyle\sum_k w_k^2\,\Sigma_{kk}/3 \quad\text{vs.}\quad \operatorname{Var}(\hat\alpha) = w^\top\bar\Sigma\,w$$

Two departures, with opposite signs:

- **The (n−1)/n factor.** The plug-in variance of a resampled mean of 3 values is 2/3 of
  the unbiased one, so the bootstrap SE is 0.816× the true SE before anything else.
- **Correlation across N within a seed.** The bootstrap breaks it.
  - A **seed-level** component that is the same at every N (here: the shared initial
    weights) shifts a whole curve up or down and leaves the slope alone. Breaking it makes
    the interval too **wide**. This is the case the instrument's docstring describes.
  - The **nested-data** component decays with the gap in N: Cov ∝ 1/max(N_k, N_l) under
    the Hoiem et al. variance model σ₀² + σ²/n. It concentrates on the small-N cells,
    which all carry negative slope weights. That *inflates* the true slope variance,
    about 1.18× in SE relative to independent subsamples. Breaking it makes the interval
    too **narrow**.

  Under a realistic mix the narrow effects win (§4: nominal 95% covers 71–81%).

The pairing-respecting alternative uses only pinned tables. Fit α_s on each seed's own
six-point curve, then take `mean ± t_{2, 0.975}·sd/√3` with t = 4.303. Seeds are the
independent units and each seed's curve keeps its correlations intact.

**(4) The sealed extrapolation and its leverage.** The fitted law's prediction at N★
is a fixed linear combination of the six log seed-means:

$$\ln \hat L(N^\star) = \sum_k h_k\,y_k,\qquad h_k = \tfrac{1}{6} + \frac{(\ln N^\star-\bar x)(x_k-\bar x)}{S_{xx}},\qquad e_s = \frac{L^\star_s - \hat L(N^\star)}{L^\star_s},\quad e=\tfrac13\sum_s e_s$$

The leverages are h = (−0.463, −0.211, +0.041, +0.293, +0.544, +0.796). They sum to 1,
and Σh² = 1.276, so noise is amplified about 1.13× for equal per-cell noise. The
N = 500 cell enters with a *negative* weight: anything that inflates the smallest cell's
loss (a poor checkpoint, the 50-image inner set) steepens the line and *lowers* the
prediction. A +3% bias at N = 500 raises α̂ by 0.006 and lowers L̂(60,000) by 1.4%, which
pushes e up by about +0.01. The denominator of e is the *measured* loss, so e > 0 means
"the law was optimistic". The notary averages the per-seed e_s. This differs from the
relative error of the seed-mean loss only at second order in the seed spread (Jensen), and
both are recomputable from the pinned `tables/sealed_*` rows.

**(5) The training budget and the checkpoint rule** (`lib/protocol.py`):

$$\text{steps}(N)=\min\!\Bigl(12000,\ \max\bigl(400,\ \lceil 20\cdot 0.9N/128\rceil\bigr)\Bigr),\qquad t^* = \arg\min_{t\,\in\,\{e,2e,\dots\}\cup\{\text{steps}\}} L_{\text{inner}}(t),\quad e=\max(50,\lfloor \text{steps}/40\rfloor)$$

| N | fit images | inner images | steps | epochs | eval every (steps) | grid spacing (epochs) |
|---|---|---|---|---|---|---|
| 500 | 450 | 50 | 400 | 113.8 | 50 | 14.2 |
| 1,000 | 900 | 100 | 400 | 56.9 | 50 | 7.1 |
| 2,000 | 1,800 | 200 | 400 | 28.4 | 50 | 3.6 |
| 4,000 | 3,600 | 400 | 563 | 20.0 | 50 | 1.8 |
| 8,000 | 7,200 | 800 | 1,125 | 20.0 | 50 | 0.9 |
| 16,000 | 14,400 | 1,600 | 2,250 | 20.0 | 56 | 0.5 |
| 60,000 (sealed) | 54,000 | 6,000 | 8,438 | 20.0 | 210 | 0.5 |

The schedule has a regime change between 2,000 and 4,000. Below it every cell gets the
same 400 steps (compute fixed, epochs fall with N). Above it every cell gets 20 epochs
(steps grow with N). This is not matched compute, and it is not meant to be: each cell is
supposed to reach its own early-stopped optimum. The diagnostic is `best_step`. A cell
whose best checkpoint is its LAST step was still improving, so it measures compute as
well as data.

## 3. Minimal from-scratch implementation plan

The plan is already realized outside the mutable surface. `analyze.py` is the one-knob
surface, `lib/protocol.py` is the training protocol and `lib/scaling.py` is the fit. The
smallest honest version, at numpy level:

```python
# ---- one cell (N, seed): lib/protocol.py + analyze.run_primary --------------------
rng = np.random.default_rng(seed); seed_everything(seed, deterministic=True)  # kleinlib.dl
perm = rng.permutation(n_pool)[:N]                     # nested across N for one seed
n_in = round(0.1 * N); fit, inner = perm[:N - n_in], perm[N - n_in:]
steps = min(12000, max(400, ceil(20 * len(fit) / 128))); every = max(50, steps // 40)
best = inf
for t in range(1, steps + 1):                          # streamed index-shuffle batches,
    idx = next(iterate_minibatches(len(fit), 128, shuffle=True, generator=rng))  # never DataLoader
    adamw_step(model, X[fit][idx], y[fit][idx], lr=1e-3, wd=1e-4)
    if t % every == 0 or t == steps:
        l = mean_xent(model, X[inner], y[inner])
        if l < best: best, t_star, snapshot = l, t, copy(model.state)
L_cell = mean_xent(snapshot, X[dev], y[dev])           # val_mlogloss, one number per (N, seed)

# ---- the fit: lib/scaling.fit_cells ---------------------------------------------
x, y = np.log(N_k), np.log(L[k, :].mean(axis=1))       # seed means, then logs
slope, icpt = np.polyfit(x, y, 1); alpha, a = -slope, np.exp(icpt)
r2 = 1 - np.sum((y - (icpt + slope * x))**2) / np.sum((y - y.mean())**2)
boot = [-np.polyfit(x, np.log([rng_b.choice(L[k], 3).mean() for k in K]), 1)[0]
        for _ in range(2000)]                          # within-N, independently across N
ci = np.quantile(boot, [0.025, 0.975])

# ---- the pairing-respecting interval (recomputable from pinned cell tables) ------
alpha_s = [-np.polyfit(x, np.log(L[:, s]), 1)[0] for s in (0, 1, 2)]
ci_t = np.mean(alpha_s) + np.array([-1, 1]) * 4.303 * np.std(alpha_s, ddof=1) / np.sqrt(3)

# ---- the sealed point: analyze.run_primary under --final-test --------------------
pred = a * 60000 ** -alpha                             # from the PINNED tables/scaling_fit.tsv
e = np.mean([(L_test[s] - pred) / L_test[s] for s in (0, 1, 2)])
```

**Where each piece lives and which kleinlib helper it leans on:**

| Piece | File | kleinlib helper |
|---|---|---|
| contract split + `split_fingerprint:` line | `analyze.py` | `kleinlib.data.load_items`, `kleinlib.data.partition_fingerprints` |
| nested subsample, inner split, steps, checkpoint grid | `lib/protocol.py` (`draw_subsample`, `steps_for`, `eval_every`) | — |
| MPS-safe batching (war story 2) | `lib/protocol.train` | `kleinlib.torch_loop.iterate_minibatches` |
| seeding, hardware / usage record | `analyze.py` | `kleinlib.dl.seed_everything`, `kleinlib.dl.report_usage` |
| cross-entropy block; probabilities validated; collapsed-prediction guard | `analyze.py` | `kleinlib.eval_multiclass.evaluate_multiclass`, `multiclass_metrics` |
| exponent block (value + interval) | `analyze.run_exponent` | `kleinlib.eval.evaluate_estimate` |
| pinned-only cell collection, OLS, bootstrap, extrapolation | `lib/scaling.py` | `kleinlib.primitives.sha256_file` |
| categorical encoding | not used: pixels only | `kleinlib.encoders` is not needed here |

**Synthetic harness used for §4.** The checks were run outside the study tree on
`lib/scaling.py` itself; the script is not evidence and nothing reads the data.

- **Truth.** `L(N) = L∞ + b N^-β`, anchored at chosen `L(500)` and `L(16,000)`.
- **Per seed s and size k, in log space:**
  - `c_s ~ N(0, σ_c²)`, shared across N (initialization);
  - `d_{s,k} = σ_d·√500·mean(first N_k of a per-seed N(0,1) stream)`, nested, so
    Cov ∝ 500/max(N_k, N_l);
  - `e_{s,k} ~ N(0, σ_e²)`, independent;
  - a development-set offset common to every cell, `~ N(0, σ_dev²)`.
- **Sealed point.** Adds its own `d` at N★, an independent `e`, a test-set offset
  `~ N(0, σ_test²)` common to the 3 seeds, and an optional shift.
- **"Medium" noise.** σ_c = 0.01, σ_d = 0.03, σ_e = 0.015, σ_dev = 0.02, σ_test = 0.025.
  That gives a per-seed CV of about 3.5% at N = 500 and 1.9% at 16,000. A mean
  cross-entropy over 10,000 items with mean 0.25 and per-item SD of about 0.6 has a
  relative SE of about 2.5%. "Low" is half these values and "high" is double.
- **Generator seeds.** 20261103 (main run), 20261104 (bias thresholds and floor test),
  20261105 (curvature), 20261106 (per-seed interval).

## 4. When it pays / when it doesn't

Doctrine anchors.

**ml-research profile §3.** Report seed variance; never let a k-seed spread stand in for a
keep bar (this is a registered track, so there is no keep bar). Compare at matched compute,
which this curve deliberately is NOT (§2 eq. 5). Each cell is early-stopped instead, so the
curve is a data-limited learning curve under a stated per-N budget, and `best_step` is the
check on that claim.

**Seed card `knowledge/method_cards/scaling-law-fits.md`.** Its regime table holds here:

- 1.5 decades with 3 seeds identifies α (synthetic interval width 0.016, medium noise).
- A loss near its floor makes the pure law under-predict the largest cell (synthetic
  table below).
- Epochs are not fixed across N. The seed card's warning ("larger N gets more steps —
  confounded; fix steps or state it") is answered by stating it (§2 eq. 5) plus the
  `best_step` diagnostic.

| Regime | Data size | Signal | Verdict |
|---|---|---|---|
| α as a summary of the measured range | 6 cells × 3 seeds over 500–16,000 (1.5 decades) | seed-mean noise ≈ 1–2% | **pays**: α̂ is the chord slope, synthetic sd ≈ 0.006 (medium noise), 0.011 (high) |
| short extrapolation, weak floor | 3.75× past the last cell | floor ≤ half of L(16k) at α_eff ≈ 0.2 | **pays**: noiseless bias ≤ +0.09 |
| short extrapolation, strong floor or steep curve | 3.75× | f(16k) ≥ 0.70 at α_eff ≈ 0.25, or ≥ 0.55 at α_eff ≈ 0.32 | **doesn't**: bias ≥ +0.20 (P3 fails) while noiseless R² is still ≥ 0.986 |
| the extrapolation the audience wants | ≥ 10× (an order of magnitude) | any nonzero floor, fixed model | **doesn't**: α_eff = β(1 − f) keeps falling, so the pure law's miss grows with the ratio |
| model grown with data (Hestness composites) | — | — | not this curve: those exponents (ImageNet cross-entropy −0.35) are for best-fit model size per shard |
| data-sampling noise dominates | small N, nested subsamples | per-seed CV ≈ 3–4% | **doesn't** for the printed CI: within-N bootstrap covers 0.71–0.80 for nominal 0.95; use per-seed slopes (0.95) |
| training noise dominates | large N | independent per cell | printed CI still narrow: the (n−1)/n factor alone gives 0.81 coverage |
| dev → t10k distribution shift | the sealed point | data card: per-image SMD +0.015, class-mix χ² p = 0.91 | **not expected to matter**: each ±5% multiplicative shift moves e by ≈ ±0.05 (synthetic) |
| R² as model-selection evidence | 6 points | any floor up to f ≈ 0.7 | **doesn't**: R² ≥ 0.98 holds for floors that cause 15–25% misses |

**Synthetic checks of `lib/scaling.py`.** These are synthetic only: no data read, no
model trained. Seeds are in §3.

*(a) Noiseless bias of the pure-law extrapolation to 60,000, anchors L(500) = 0.60,
L(16,000) = 0.30 (α_eff = 0.20):*

| floor fraction f(16k) | 0 | 0.25 | 0.50 | 0.67 | 0.75 | 0.83 |
|---|---|---|---|---|---|---|
| fitted α | 0.200 | 0.200 | 0.200 | 0.200 | 0.200 | 0.199 |
| R² of the pure fit | 1.0000 | 0.9995 | 0.9966 | 0.9903 | 0.9833 | 0.9699 |
| signed rel. error at 60k | +0.000 | +0.039 | +0.091 | +0.138 | +0.167 | +0.201 |

*Floor fraction at which the noiseless miss first reaches +0.10 / +0.20, by effective
exponent:*

| α_eff | +0.10 at f = | +0.20 at f = | R² there |
|---|---|---|---|
| 0.136 | 0.76 | not reached | 0.988 |
| 0.200 | 0.54 | 0.83 | 0.996 / 0.970 |
| 0.253 | 0.40 | 0.70 | 0.998 / 0.986 |
| 0.317 | 0.29 | 0.55 | 0.999 / 0.993 |
| 0.361 | 0.24 | 0.47 | 0.999 / 0.995 |

The steeper the curve, the smaller the floor needed for a 20% miss, and the higher the R²
that hides it.

*(b) With noise (20,000 replications, anchors as in (a)).*

| noise | f(16k) | P(R² ≥ 0.98) | mean e | sd e | P(\|e\| ≤ 0.20) | P(e > 0) |
|---|---|---|---|---|---|---|
| medium | 0 | 1.000 | −0.001 | 0.036 | 1.000 | 0.498 |
| medium | 0.50 | 1.000 | +0.090 | 0.033 | 1.000 | 0.997 |
| medium | 0.67 | 0.980 | +0.137 | 0.031 | 0.983 | 1.000 |
| medium | 0.75 | 0.682 | +0.166 | 0.030 | 0.870 | 1.000 |
| medium | 0.83 | 0.034 | +0.201 | 0.029 | 0.484 | 1.000 |
| high | 0.50 | 0.959 | +0.089 | 0.066 | 0.961 | 0.908 |
| high | 0.75 | 0.495 | +0.164 | 0.060 | 0.719 | 0.994 |

P1's band [0.10, 0.60] contained α̂ in 100% of all synthetic replications. That is by
construction (α_eff = 0.20), so it says only that the band is wide relative to the
noise: about 30× the printed interval's width.

*(c) The printed bootstrap interval (400 replications through `fit_cells`, target = the
noiseless fit's α):*

| noise structure | sd(α̂) | mean CI width | coverage of nominal 95% | analytic SE ratio boot/true |
|---|---|---|---|---|
| medium mix, no floor | 0.0054 | 0.0163 | 0.797 | 0.786 |
| medium mix, f = 0.75 | 0.0056 | 0.0160 | 0.777 | 0.786 |
| nested data only | 0.0066 | 0.0152 | 0.713 | 0.692 |
| independent only | 0.0063 | 0.0184 | 0.807 | 0.816 (= √(2/3)) |
| seed-level only | 0.0000 | 0.0171 | 1.000 | — (slope unaffected) |

The per-seed-slope t-interval (eq. 3, 20,000 replications) covers at the nominal level
in every structure: 0.950 / 0.948 / 0.948 / 0.950 for medium / nested / independent /
high. It is 2.6× wider (mean width 0.042 at medium noise). **The docstring of
`lib/scaling.py` and the program.md instrument note claim the within-N bootstrap "errs
wide". That is true only for the shared-initialization component. Under nested data it
errs narrow. Read the printed `[ci_low, ci_high]` as roughly an 80% interval.**

*(d) Can six cells tell a power law from a power law plus a floor?* This used a profile
least-squares fit of `L∞ + b N^-β` and an F(1, 3) test of the extra parameter at 5%
(critical 10.13), 4,000 replications.

| noise | α_eff | f(16k) | test prefers the floor | L̂∞ 5–95% (true) | P(\|e\| ≤ 0.2): pure law / floor fit |
|---|---|---|---|---|---|
| medium | 0.20 | 0 | 0.035 (false alarms) | 0.000–0.103 (0) | 1.000 / 1.000 |
| medium | 0.20 | 0.25 | 0.188 | 0.000–0.146 (0.075) | 1.000 / 1.000 |
| medium | 0.20 | 0.50 | 0.649 | 0.085–0.193 (0.150) | 1.000 / 1.000 |
| medium | 0.32 | 0.50 | 0.982 | 0.119–0.177 (0.150) | 0.777 / 1.000 |
| high | 0.20 | 0.50 | 0.260 | 0.000–0.224 (0.150) | 0.962 / 0.985 |
| high | 0.20 | 0.75 | 0.713 | 0.155–0.266 (0.225) | 0.715 / 0.989 |

The honest reading has three parts:

- **R² cannot tell them apart.** A direct curvature test can, but only once the floor is
  at least half the loss at the top of the range and the seed-mean noise is small.
  Small floors (f ≤ 0.25) are mostly invisible (power ≤ 0.19). Even when the test fires,
  the floor's *value* stays poorly pinned: 5–95% range 0.085–0.193 around a true 0.150 at
  medium noise, and 0.000–0.224 at high noise.
- **The floor fit only looks good here because the truth was built in that form.** The
  three-parameter fit extrapolates well in these runs because the synthetic truth IS
  `L∞ + b N^-β`. Real curvature can also come from compute-limited large cells or a
  broken power law, and M2-style floor fits fail when the curve leaves the power-law
  regime (Alabdulmohsin et al. 2022; Caballero et al. 2023).
- **The value of L∞ is not identified.** Hoiem et al. found the same on CNN learning
  curves: the level and local slope are stable, but "predicted asymptotic error α varies
  widely".

The registered law is the pure one. A floor fit on the pinned table is exploratory, and
`findings.md` must label it so.

**Frontier lit-scan: where this method sits.**

- **Seminal.** Cortes et al. (1993) already fitted "power-law decays to the asymptotic
  value" and extrapolated from reduced to full database size. They pinned the floor by
  fitting test AND training error together. This study records no training loss, so that
  route is closed here.
- **Modern origin.** Hestness et al. (2017) reported clean power laws across domains with
  exponents between −0.07 and −0.35, for best-fit model sizes per shard.
- **Key follow-ups.** They moved the floor into the law:
  - Rosenfeld et al. (2020): for a fixed model the data curve saturates at c_n(m);
  - Hoffmann et al. (2022): E + A/N^α + B/D^β;
  - Bahri et al. (2024): the variance-limited 1/D approach to a limit;
  - Kaplan et al. (2020) stated L(D) for early-stopped large models.
- **The current trend.** Fits are judged by **extrapolation**, not interpolation
  (Alabdulmohsin et al. 2022). Broken and multi-regime forms (Caballero et al. 2023) are
  used where one exponent fails. Published fit intervals are audited (Besiroglu et al.
  2024 found Chinchilla's "implausibly narrow").
- **The skeptical frame.** Viering & Loog's review: offset power laws fit best and many
  deep-net power-law claims were eyeballed. Clauset et al. on power-law distributions:
  a high r² "cannot be taken as evidence".
- **Resonant application in the study's field.** Hoiem et al. (2021): CNN learning curves
  for vision, `e(n) = α + η n^γ`, noting a log-linear relationship "holds only when
  asymptotic error is zero".

**Honest positioning.** This study registers the 2017-style pure law on purpose and holds
it to a sealed point. It measures how wrong the simplest exponent already is at 3.75×
for a small fixed CNN. It does not find the best law, and it does not forecast an order
of magnitude.

### Expectations for the registered predictions (no training; reasons above)

- **P1: α̂ ∈ [0.10, 0.60]. Expect SUPPORTED (≈ 0.9).**
  - *Central α̂ ≈ 0.22, likely range 0.15–0.32.* A 24k-parameter CNN on 450 images should
    land around 0.6–0.8 nats of development cross-entropy. At 14,400 images it should be
    near 0.30–0.35, against the sklearn benchmark context of 0.84–0.90 accuracy at full
    data (Xiao et al.). That is a ratio of 1.8–2.6 over 32×, so α ≈ 0.17–0.28.
  - *The upper bound is close to arithmetic.* α > 0.60 needs L(500)/L(16k) > 8, and a
    best-checkpoint loss near the uniform ln 10 = 2.30 against L(16k) ≈ 0.29 gives at
    most 7.9.
  - *The lower bound is the only live risk.* α < 0.10 needs a ratio below 1.41, which
    would mean 450 images already get within 41% of the 14,400-image loss.
  - The prior band is wide, and the literature value it rests on (−0.35 for ImageNet
    cross-entropy) is for model-grown-with-data curves.
- **P2: R² ≥ 0.98. Expect SUPPORTED (≈ 0.8).**
  - *Why it holds.* By synthetic (b) it holds with probability ≥ 0.98 at medium noise for
    any floor up to two-thirds of L(16k).
  - *What breaks it:*
    - a floor fraction ≥ 0.75;
    - a kink at the 400-step / 20-epoch regime change between 2,000 and 4,000;
    - selection noise at N = 500 from the 50-image inner set and the 14-epoch grid.
  - *Reading.* A pass is weak evidence. It is compatible with a 15–20% extrapolation miss.
- **P3: |e| ≤ 0.20. Expect SUPPORTED, but less surely (≈ 0.7).**
  - *Central e ≈ +0.12, likely range +0.03 to +0.25.*
  - *My guess for the floor.* The fixed net's floor (capacity plus label ambiguity) is
    about half to two-thirds of L(16k), at α_eff ≈ 0.2–0.25. That gives a noiseless bias
    of +0.09 to +0.17 (tables a, b).
  - *Further positive contributions.* Under-training at 60,000 adds 0 to +0.03.
    Small-cell selection noise steepening the line adds about +0.01 (eq. 4 leverage).
  - *Noise.* Seed noise plus test- and development-item sampling give sd ≈ 0.035 at
    medium noise (table b). The data card's null shift adds ≈ 0.
  - *Where it fails.* P3 fails if the floor is above about 0.7 of L(16k) at α_eff ≥ 0.25.
    That is plausible for a 24k-parameter net, hence 0.7 rather than the 0.55 written at
    CONSULT. The difference is the effect of the synthetic tables.
- **P4: e > 0. Expect SUPPORTED (≈ 0.9).**
  - *Why positive.* Every systematic term I can name pushes e positive: the fixed-model
    floor (Rosenfeld; Hoffmann; Bahri), compute-limited large cells, and the small-N
    selection effect through the negative leverage of the N = 500 cell.
  - *What could flip it.* Only noise (sd ≈ 0.035, so a flip needs a true bias below
    about +0.04) or a dev → test shift making t10k *easier* by ≥ 5%. The data card
    measured no first-order shift.

### Falsifiable priors this card stakes

Each prior names a lever, a direction, and a magnitude with units, and each can come out
false. All are keyed to notarized output: a printed key of a run, or a pinned table.

| ID | Prior | Read from | False if |
|---|---|---|---|
| MC1 | Over N = 500 → 16,000 the exponent of seed-mean development cross-entropy is α̂ ∈ **[0.15, 0.32]** (exponent units; central 0.22) | exponent run `primary_metric` | α̂ < 0.15 or > 0.32 |
| MC2 | The curve FLATTENS: the local exponent over the three smallest cells (500–2,000) exceeds that over the three largest (4,000–16,000) by **≥ +0.03** (exponent units; central +0.07; synthetic sd 0.017 at medium noise) | `tables/scaling_fit.tsv` `mean_val_mlogloss` (two 3-point OLS slopes) | difference < +0.03 |
| MC3 | The pure law is optimistic at 60,000 by a bounded amount: `extrapolation_rel_error` ∈ **[+0.03, +0.25]** (fraction of the measured loss; central +0.12) | sealed run `extrapolation_rel_error` | e < +0.03 or e > +0.25 |
| MC4 | The printed 95% bootstrap interval is narrow, **ci_high − ci_low ≤ 0.04** exponent units. The per-seed-slope 95% t-interval (eq. 3) is **≥ 2×** wider | exponent run `ci_low`, `ci_high`; pinned `tables/cell_*_s*.tsv` | width > 0.04, or t-interval < 2× the printed width |
| MC5 | The full-data cell is near compute-limited: sealed seed-mean `best_step` **≥ 6,329** steps (75% of its 8,438). The N = 16,000 cell's seed-mean `best_step` **≥ 1,125** (50% of 2,250) | sealed run and N = 16,000 cell `best_step` | either is below its bound |

MC5 is the interpretive key for P4. If P4 holds AND MC5 holds, a positive e is partly
under-training, not only an irreducible floor, and `findings.md` must not credit the miss
to "the floor" alone.

**Mirroring status.** These priors are NOT mirrored into `study.yaml`, for two reasons:

- This schema-3 contract already registers `predictions:` (P1–P4), and the contract
  validator refuses `predictions_to_falsify:` beside it ("give predictions: or
  predictions_to_falsify:, never both").
- This worker may touch only `method_card.md` and `references.yaml`.

**Proposed registration, for the lead to decide BEFORE any cell runs.** Doing it after
CONSULT may need a consult re-record:

```yaml
- {id: P5, track: exponent, statement: "MC1", rule: {key: primary_metric, op: between, value: [0.15, 0.32]}}
- {id: P6, track: primary,  statement: "MC3", rule: {key: extrapolation_rel_error, op: between, value: [0.03, 0.25]}}
- {id: P7, track: primary,  statement: "MC5 (sealed half)", rule: {key: best_step, op: ">=", value: 6329}}
```

MC2 and MC4 read pinned tables. If registered, they are adjudicated with
`klein predict adjudicate` against those tables' hashes. Unregistered, SYNTHESIZE holds them
to account as the card's stated expectations.

## 5. Verified references

Every row was checked against its record on 2026-11-03: the arXiv API entry or Crossref
record, the publisher or proceedings page, and the full text for every paper whose
content the card uses. `klein refs verify --study studies/22-cnn-data-scaling --record`
then resolved each DOI and arXiv id: 16 ok, 0 failed, 15 recorded. `cortes1993` is
url-only (NeurIPS 1993 predates DOIs) and was checked by a reader against the proceedings
page, metadata JSON and PDF. Keys resolve as `ref:<key>` against `references.yaml`.

| Key | Reference | Where | Verified? |
|---|---|---|---|
| `xiao2017` | Xiao, Rasul & Vollgraf 2017, Fashion-MNIST: a Novel Image Dataset for Benchmarking Machine Learning Algorithms | arXiv:1708.07747 | ✅ |
| `cortes1993` | Cortes, Jackel, Solla, Vapnik & Denker 1993, Learning Curves: Asymptotic Values and Rate of Convergence | NIPS 6 (1993), pp. 327–334, proceedings.neurips.cc | ✅ (url-only) |
| `hestness2017` | Hestness et al. 2017, Deep Learning Scaling is Predictable, Empirically | arXiv:1712.00409 | ✅ |
| `rosenfeld2020` | Rosenfeld, Rosenfeld, Belinkov & Shavit 2020, A Constructive Prediction of the Generalization Error Across Scales | ICLR 2020, arXiv:1909.12673 | ✅ |
| `kaplan2020` | Kaplan et al. 2020, Scaling Laws for Neural Language Models | arXiv:2001.08361 | ✅ |
| `hoffmann2022` | Hoffmann et al. 2022, Training Compute-Optimal Large Language Models (Chinchilla) | NeurIPS 2022, arXiv:2203.15556 | ✅ |
| `bahri2024` | Bahri, Dyer, Kaplan, Lee & Sharma 2024, Explaining neural scaling laws | PNAS 121(27) e2311878121, doi:10.1073/pnas.2311878121; arXiv:2102.06701 (2021) | ✅ |
| `viering2023` | Viering & Loog 2023 (DOI 2022), The Shape of Learning Curves: A Review | IEEE TPAMI 45(6) 7799–7819, doi:10.1109/TPAMI.2022.3220744; arXiv:2103.10948 | ✅ |
| `alabdulmohsin2022` | Alabdulmohsin, Neyshabur & Zhai 2022, Revisiting Neural Scaling Laws in Language and Vision | NeurIPS 2022, arXiv:2209.06640 | ✅ |
| `caballero2023` | Caballero, Gupta, Rish & Krueger 2023, Broken Neural Scaling Laws | ICLR 2023, arXiv:2210.14891 | ✅ |
| `besiroglu2024` | Besiroglu, Erdil, Barnett & You 2024, Chinchilla Scaling: A replication attempt | arXiv:2404.10102 | ✅ |
| `hoiem2021` | Hoiem, Gupta, Li & Shlapentokh-Rothman 2021, Learning Curves for Analysis of Deep Networks | ICML 2021, PMLR 139:4287–4296; arXiv:2010.11029 | ✅ |
| `nakkiran2020` | Nakkiran et al. 2020, Deep Double Descent: Where Bigger Models and More Data Hurt | ICLR 2020, arXiv:1912.02292; J. Stat. Mech. (2021) 124003 | ✅ |
| `clauset2009` | Clauset, Shalizi & Newman 2009, Power-law distributions in empirical data | SIAM Review 51(4) 661–703, doi:10.1137/070710111 | ✅ |
| `loshchilov2019` | Loshchilov & Hutter 2019, Decoupled Weight Decay Regularization (AdamW) | ICLR 2019, arXiv:1711.05101 | ✅ |
| `efron1993` | Efron & Tibshirani 1993, An Introduction to the Bootstrap | Chapman & Hall (MSAP 57), doi:10.1007/978-1-4899-4541-9 | ✅ |

The lit-scan is done (§4, "Frontier lit-scan"). No row is unverified.
