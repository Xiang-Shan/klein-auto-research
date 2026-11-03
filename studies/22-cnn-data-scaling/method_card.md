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
  practice: true       # §3: the plan lib/protocol.py + lib/scaling.py + analyze.py already realize, plus a synthetic harness of lib/scaling.py whose DGP, draw order and per-row seeds §3 states
---

# Method card — a data-scaling law fitted on six small training sets, tested on a seventh

> Gate 2 (METHOD). Pedagogy written BEFORE any cell runs. Protocol:
> `.claude/skills/klein/references/method-gate-protocol.md`. The study's CNN was not
> trained for this card. Every number below is literature (cited), protocol arithmetic
> (from `lib/protocol.py` constants), or **SYNTHETIC** (a made-up learning curve plus
> made-up noise pushed through `lib/scaling.py`, recipe and seeds stated in §3). None of
> it is evidence about Fashion-MNIST.
>
> Revision 2 (2026-11-03), after the DATA/METHOD review and before any cell. Pass counts
> now count the partial tail batch as a step. The fit pool is N★ = 59,992 with an 8,437-step
> budget. The inner-validation cadence is Δt. Every synthetic number was re-run from the §3
> recipe with per-row seeds. P4's reasoning is corrected for the sign of under-training
> (eq. 4), and the P1–P7 expectations now come from one stated belief (§4).

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
but "is the curve still a line out there?" Extrapolating to the full pool, N★ = 59,992,
means extrapolating the tangent.

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
is then **optimistic**, and the signed relative error at N★ comes out positive. That is
the main bet behind P4. It is not the only systematic term: equation 4 shows that
under-training of the large cells inside the fit pulls the error the other way.

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
matters for the error bar on α (equation 3), in the opposite direction from the one the
instrument's first docstring assumed (the lead has since corrected it).

**The sealed test.** After the six cells are pinned and the fit is frozen, the network is
trained once on the whole fit pool and scored once on the sealed test set. The pool is
N★ = 59,992 images: the 60,000 official training images minus the 8 development
near-copies `prepare.py` removed at DATA. The test set is the 9,995 kept t10k images (5
near-copies removed). The prediction a·N★^-α is compared with that measured loss. The
**signed relative error** (measured − predicted) / measured is positive when the law was
optimistic. P3 asks whether it is small (|e| ≤ 0.20), P4 whether it is positive, and P6
whether it lies in [+0.03, +0.25]. N★ is 3.75× past the last cell, a short extrapolation.
The order of magnitude you actually want to forecast is harder, and this study can only
tell you how wrong the simplest law already is at 3.75×.

**The step schedule.** Small N trains for many passes, and the best checkpoint is early
stopping. A cell trains max(400, ⌈20·n_fit/128⌉) optimizer steps (capped at 12,000),
where n_fit is the 90% of the subsample it trains on. The loop counts every minibatch as a
step, including the short batch left at the end of each shuffle, so one pass over the fit
set is ⌈n_fit/128⌉ steps. The smallest cells therefore loop over their data many times:
100 passes at N = 500 (4 steps per pass), 50 at 1,000, 26.7 at 2,000. The larger cells get
19.4 to 19.99 passes, not exactly 20: the budget counts 20 epochs of full batches, while each
pass also spends a step on its tail batch. A small network that sees 450 images 100 times
will memorize them, and its cross-entropy on new images rises as it becomes confidently
wrong. The protocol therefore holds out 10% of each subsample as an *inner* validation set,
scores it on a grid of checkpoints, and keeps the best one. That is early stopping, and it
is what makes the curve *data-limited* rather than *epoch-limited*. Kaplan et al.'s L(D) is
likewise stated for early-stopped training, and Nakkiran et al. note that sample-wise "more
data hurts" effects often vanish under optimal early stopping. It has a cost at small N:
the inner set at N = 500 is only 50 images, and each 400-step cell is scored at only 8
checkpoints (12.5 passes apart at N = 500), so the selected checkpoint is a noisy guess at
the best one.

## 2. Math core

| Symbol | Meaning |
|---|---|
| `N` | training-set size of a cell: the drawn subsample, including its 10% inner validation share |
| `n_fit = N − round(0.1·N)` | the images a cell trains on; the other `N − n_fit` are its inner validation set |
| `N_k`, `k = 0..5` | the six development sizes 500, 1,000, 2,000, 4,000, 8,000, 16,000 (doubling) |
| `N★ = 59,992` | the sealed cell's size: the whole fit pool, 60,000 official training images minus 8 development near-copies (`lib/protocol.py: N_FULL`) |
| `s ∈ {0,1,2}` | seed: fixes the subsample, its inner split, the minibatch order and the initial weights |
| `L_{k,s}` | development cross-entropy (nats per image, `val_mlogloss`) of seed `s` at `N_k`, scored on the 9,992 development rows at the best inner checkpoint |
| `L̄_k` | the seed mean `(1/3) Σ_s L_{k,s}` (what `lib/scaling.py` fits) |
| `x_k = ln N_k`, `y_k = ln L̄_k` | log axes; `x̄ = 7.9475`, `S_xx = Σ(x_k − x̄)² = 8.4079` |
| `a`, `α` | scale and exponent of the pure law `L(N) = a N^-α` |
| `R²` | coefficient of determination of the line in log space |
| `L∞`, `b`, `β` | floor, scale and exponent of the saturating law `L(N) = L∞ + b N^-β` |
| `f(N) = L∞ / L(N)` | floor fraction: the share of the loss at `N` that more data cannot remove |
| `α_eff(N)` | local log-log slope `−d ln L / d ln N` |
| `w_k`, `h_k` | slope weights and extrapolation leverages of cell `k` (equations 1 and 4) |
| `δ_k`, `δ★` | a systematic log-inflation of the seed-mean loss at `N_k` or at `N★` (a poor checkpoint, under-training) |
| `B = 2,000` | bootstrap draws (`BOOTSTRAP_DRAWS`) |
| `L★_s` | sealed test cross-entropy of seed `s` at `N★`, on the 9,995 kept t10k images |
| `e_s`, `e` | per-seed signed relative error and its seed mean (`extrapolation_rel_error`) |
| `steps(N)`, `t*` | the step budget of a cell and its selected checkpoint (`best_step`) |
| `Δt` | the inner-validation cadence in steps (`eval_every`) |
| `p(N)` | passes over the fit set, `steps(N) / ⌈n_fit/128⌉`; one step is one minibatch, the partial tail batch included |

**(1) The pure law and its fit.** OLS on the six seed means in log space:

$$\ln \bar L_k = \ln a - \alpha\,x_k + \varepsilon_k,\qquad \hat\alpha = -\sum_k w_k\,y_k,\quad w_k = \frac{x_k-\bar x}{S_{xx}},\qquad R^2 = 1-\frac{\sum_k \hat\varepsilon_k^2}{\sum_k (y_k-\bar y)^2}$$

The weights are w = (−0.206, −0.124, −0.041, +0.041, +0.124, +0.206). The two end
cells carry the slope. For a noiseless pure law the denominator of R² is α²·S_xx (0.407
at α = 0.22), so R² ≥ 0.98 allows a residual RMS of √(0.02·0.407/6) ≈ 0.037. That is about
a 3.7% wobble per cell, and the allowance grows with α.

**(2) What a floor does to the fitted exponent.** For `L = L∞ + b N^-β`:

$$\alpha_{\text{eff}}(N) \;=\; -\frac{d\ln L}{d\ln N} \;=\; \beta\,\bigl(1 - f(N)\bigr),\qquad f(N)=\frac{L_\infty}{L(N)}$$

The local slope decays toward 0 as the loss approaches its floor. The pure-law fit returns
an average of α_eff over the six cells, which is larger than α_eff at N★, so the
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
    the interval too **wide**. This is the case the instrument's first docstring described.
  - The **nested-data** component decays with the gap in N: Cov ∝ 1/max(N_k, N_l) under
    the Hoiem et al. variance model σ₀² + σ²/n. It concentrates on the small-N cells,
    which all carry negative slope weights. That *inflates* the true slope variance,
    1.18× in SE relative to independent subsamples. Breaking it makes the interval
    too **narrow**.

  Under a realistic mix the narrow effects win (§4 (c): nominal 95% covers 0.74 to 0.83 across the structures, 0.79 to 0.80 under the medium mix).

The pairing-respecting alternative uses only pinned tables. Fit α_s on each seed's own
six-point curve, then take `mean ± t_{2, 0.975}·sd/√3` with t = 4.303. Seeds are the
independent units and each seed's curve keeps its correlations intact.

**(4) The sealed extrapolation and its leverage.** The fitted law's prediction at N★
is a fixed linear combination of the six log seed-means, so a systematic inflation of any
cell moves the error through that cell's leverage:

$$\ln \hat L(N^\star) = \sum_k h_k\,y_k,\quad h_k = \tfrac{1}{6} + \frac{(\ln N^\star-\bar x)(x_k-\bar x)}{S_{xx}},\quad e_s = \frac{L^\star_s - \hat L(N^\star)}{L^\star_s},\quad e=\tfrac13\sum_s e_s,\quad \Delta e \approx \delta^\star - \sum_k h_k\,\delta_k$$

The leverages are h = (−0.463, −0.211, +0.041, +0.293, +0.544, +0.796). They sum to 1,
and Σh² = 1.276, so noise is amplified about 1.13× for equal per-cell noise. The last
term is first order, because e = 1 − L̂/L★ ≈ ln L★ − ln L̂. Read the signs off it:

- **Inflated small cells push e UP.** N = 500 and 1,000 enter with negative weights.
  Anything that inflates them (a poor checkpoint, the 50-image inner set) steepens the line
  and lowers the prediction. A +3% bias at N = 500 raises α̂ by 0.006 and lowers
  L̂(N★) by 1.4%, so e rises by about +0.014.
- **Inflated large in-fit cells push e DOWN.** The 4,000, 8,000 and 16,000 cells carry
  leverages summing to +1.633. Under-training that inflates them raises L̂(N★) and lowers e.
- **An inflated sealed cell pushes e UP**, one for one with its own deficit δ★.

So under-training has no fixed sign. Noiseless, at the f = 0.5 anchors of §4 (base error
+0.091), deficits of about 5% move e by:

| deficit profile | first-order Δe | exact e |
|---|---|---|
| equal in all four ~20-pass cells (4,000, 8,000, 16,000, N★) | (1 − 1.633)·0.05 ≈ −0.032 | +0.062 |
| in the in-fit 4,000–16,000 cells only, the sealed cell converged | −0.082 | +0.014 |
| at the sealed cell only | +0.050 | +0.136 |
| growing like 0.02·ln(N/4,000): 0 at 4,000, 5.4% at N★ | +0.025 | +0.113 |

The ~20-pass cells see equal passes but step budgets that fall from 8,437 at N★ to 563 at
N = 4,000. A deficit that does not grow with N is therefore at least as plausible as one
that does, and the two profiles of that kind (the first two rows) lower e.

The denominator of e is the *measured* loss, so e > 0 means "the law was optimistic". The
notary averages the per-seed e_s. This differs from the relative error of the seed-mean
loss only at second order in the seed spread (Jensen), and both are recomputable from the
pinned `tables/sealed_*` rows.

**(5) The training budget and the checkpoint rule** (`lib/protocol.py`):

$$\text{steps}(N)=\min\!\Bigl(12000,\ \max\bigl(400,\ \lceil 20\,n_{\text{fit}}/128\rceil\bigr)\Bigr),\quad p(N)=\frac{\text{steps}(N)}{\lceil n_{\text{fit}}/128\rceil},\quad t^* = \arg\min_{t\,\in\,\{\Delta t,\,2\Delta t,\,\dots\}\cup\{\text{steps}\}} L_{\text{inner}}(t),\quad \Delta t=\max\bigl(50,\lfloor \text{steps}/40\rfloor\bigr)$$

| N | n_fit | inner images | steps | steps per pass (tail batch) | passes p | Δt (steps) | grid spacing (passes) | checkpoints |
|---|---|---|---|---|---|---|---|---|
| 500 | 450 | 50 | 400 | 4 (66) | 100.0 | 50 | 12.5 | 8 |
| 1,000 | 900 | 100 | 400 | 8 (4) | 50.0 | 50 | 6.25 | 8 |
| 2,000 | 1,800 | 200 | 400 | 15 (8) | 26.7 | 50 | 3.33 | 8 |
| 4,000 | 3,600 | 400 | 563 | 29 (16) | 19.4 | 50 | 1.72 | 12 |
| 8,000 | 7,200 | 800 | 1,125 | 57 (32) | 19.7 | 50 | 0.88 | 23 |
| 16,000 | 14,400 | 1,600 | 2,250 | 113 (64) | 19.9 | 56 | 0.50 | 41 |
| 59,992 (sealed) | 53,993 | 5,999 | 8,437 | 422 (105) | 19.99 | 210 | 0.50 | 41 |

The schedule has a regime change between 2,000 and 4,000. Below it every cell gets the
same 400 steps (compute fixed, passes fall with N). Above it every cell gets about 20
passes (19.4–19.99), so steps grow with N. This is not matched compute, and it is not meant
to be: each cell is supposed to reach its own early-stopped optimum. The N = 4,000 cell gets
563 steps for twice the 2,000 cell's data, which is where a kink would show (P2). The
diagnostic is `best_step`. A cell whose best checkpoint is its LAST step was still
improving, so it measures compute as well as data.

One quirk is stated, not changed: the tail batch is 4 images at N = 1,000 and 8 at 2,000,
so one step in 8 (or 15) is an AdamW update from a handful of images. Adam normalizes the
step size, so these are full-size, noisy updates.

## 3. Minimal from-scratch implementation plan

The plan is already realized outside the mutable surface. `analyze.py` is the one-knob
surface, `lib/protocol.py` is the training protocol and `lib/scaling.py` is the fit. The
smallest honest version, at numpy level:

```python
# ---- one cell (N, seed): lib/protocol.py + analyze.run_primary --------------------
rng = np.random.default_rng(seed); seed_everything(seed, deterministic=True)  # kleinlib.dl
perm = rng.permutation(n_pool)[:N]                     # nested across N for one seed
n_in = round(0.1 * N); fit, inner = perm[:N - n_in], perm[N - n_in:]
steps = min(12000, max(400, ceil(20 * len(fit) / 128))); dt = max(50, steps // 40)
best, t = inf, 0
while t < steps:                                       # one pass = ceil(len(fit)/128) steps:
    for idx in iterate_minibatches(len(fit), 128, shuffle=True, generator=rng):  # tail batch is a step
        adamw_step(model, X[fit][idx], y[fit][idx], lr=1e-3, wd=1e-4); t += 1  # never DataLoader
        if t % dt == 0 or t == steps:
            l = mean_xent(model, X[inner], y[inner])
            if l < best: best, t_star, snapshot = l, t, copy(model.state)
        if t == steps: break
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
pred = a * N_FULL ** -alpha                            # N_FULL = 59,992; a, alpha from the PINNED tables/scaling_fit.tsv
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

**Synthetic harness used for §4.** It runs outside the study tree on `lib/scaling.py`
itself (`ols_loglog`, `fit_cells`) with N★ = `N_FULL`. Nothing reads the data and the
script is not evidence. The recipe below is meant to be complete enough to reproduce every
row:

- **Truth.** `L(N) = L∞ + b N^-β` with `L∞ = f·L(16,000)`, anchored at `L(500) = 0.60` and
  `L(16,000) = 0.30` (α_eff = 0.20). Another α_eff sets `L(500) = 0.30·32^α_eff`.
- **One replication, 3 seeds, drawn in this order** (log space, `rng.normal` calls):
  1. `c_s ~ N(0, σ_c²)`, shape (R, 3), shared along seed s's six cells and its sealed point
     (initialization);
  2. `z_{s,j} ~ N(0, 1)`, shape (R, 3, 7): item-block sums for blocks of 500, 500, 1,000,
     2,000, 4,000, 8,000 and N★ − 16,000 items. Then
     `d_{s,k} = σ_d·√500·cumsum_j(z_{s,j}·√block_j)_k / N_k`, so Var = σ_d²·500/N_k and
     Cov = σ_d²·500/max(N_k, N_l) (nested); index 6 is the sealed point;
  3. `ε_{s,j} ~ N(0, σ_e²)`, shape (R, 3, 7), independent (index 6: sealed);
  4. a development offset `~ N(0, σ_dev²)`, shape (R, 1), common to the 18 cells;
  5. a test offset `~ N(0, σ_test²)`, shape (R, 1), common to the 3 sealed seeds; then an
     optional fixed log shift.
- **Noise levels.** "Medium" is σ_c = 0.01, σ_d = 0.03, σ_e = 0.015, σ_dev = 0.02,
  σ_test = 0.025. That gives a per-seed CV of about 3.5% at N = 500 and 1.9% at 16,000. A
  mean cross-entropy over about 10,000 items with mean 0.25 and per-item SD of about 0.6
  has a relative SE of about 2.5%. "Low" is half these values and "high" is double. The
  single-structure rows of (c) switch on one or two medium components at their medium
  values and set the rest to 0.
- **Seeds.** Row i (0-based, in the order printed) of each table draws from
  `np.random.default_rng([seed, i])`: (b) 20261103; (d) 20261104; (c) 20261105; the
  per-seed t-interval 20261106; the noisy corner (b′) 20261107; the dev → test shift
  20261108; the MC2 curvature 20261109. The prior-predictive belief in §4 uses one
  `np.random.default_rng(20261110)`, restarted for each configuration. `fit_cells` adds its
  own fixed `BOOTSTRAP_SEED`.

## 4. When it pays / when it doesn't

Doctrine anchors.

**ml-research profile §3.** Report seed variance; never let a k-seed spread stand in for a
keep bar (this is a registered track, so there is no keep bar). Compare at matched compute,
which this curve deliberately is NOT (§2 eq. 5). Each cell is early-stopped instead, so the
curve is a data-limited learning curve under a stated per-N budget, and `best_step` is the
check on that claim.

**Seed card `knowledge/method_cards/scaling-law-fits.md`.** Its regime table holds here:

- 1.5 decades with 3 seeds identifies α (synthetic printed-interval width 0.016,
  medium noise).
- A loss near its floor makes the pure law under-predict the largest cell (synthetic
  table below).
- Epochs are not fixed across N. The seed card's warning ("larger N gets more steps —
  confounded; fix steps or state it") is answered by stating it (§2 eq. 5) plus the
  `best_step` diagnostic.

| Regime | Data size | Signal | Verdict |
|---|---|---|---|
| α as a summary of the measured range | 6 cells × 3 seeds over 500–16,000 (1.5 decades) | seed-mean noise ≈ 1–2% | **pays**: α̂ is the chord slope, synthetic sd ≈ 0.006 (medium noise), 0.011 (high) |
| short extrapolation, weak floor | 3.75× past the last cell | floor ≤ half of L(16k) at α_eff ≈ 0.2 | **pays**: noiseless bias ≤ +0.091 |
| short extrapolation, strong floor or steep curve | 3.75× | f(16k) ≥ 0.70 at α_eff ≈ 0.25, or ≥ 0.55 at α_eff ≈ 0.32 | **doesn't**: bias ≥ +0.20 (P3 fails) while noiseless R² is still ≥ 0.986 |
| the extrapolation the audience wants | ≥ 10× (an order of magnitude) | any nonzero floor, fixed model | **doesn't**: α_eff = β(1 − f) keeps falling, so the pure law's miss grows with the ratio |
| model grown with data (Hestness composites) | — | — | not this curve: those exponents (ImageNet cross-entropy −0.35) are for best-fit model size per shard |
| data-sampling noise dominates | small N, nested subsamples | per-seed CV ≈ 3–4% | **doesn't** for the printed CI: within-N bootstrap covers 0.74 (nested only) to 0.78 (nested + independent) for nominal 0.95; use per-seed slopes (0.95) |
| training noise dominates | large N | independent per cell | printed CI still narrow: the (n−1)/n factor alone gives 0.83 coverage |
| dev → t10k distribution shift | the sealed point | data card: per-image SMD +0.015, class-mix χ² p = 0.90 | **not expected to matter**: each ±5% multiplicative shift moves e by ≈ ±0.04 to ±0.05 (synthetic) |
| R² as model-selection evidence | 6 points | floors up to f ≈ 0.72–0.78 of L(16k) | **doesn't**: noiseless R² ≥ 0.98 still holds at misses of +0.18 (α_eff 0.20) to +0.28 (α_eff 0.32) |
| under-training of the ~20-pass cells | 4,000–N★ | deficit δ per cell | **ambiguous sign**: Δe ≈ δ★ − Σh_kδ_k; an equal deficit lowers e by 0.63δ (eq. 4) |

**Synthetic checks of `lib/scaling.py`.** These are synthetic only: no data read, no
model trained. Recipe and seeds are in §3.

*(a) Noiseless bias of the pure-law extrapolation to N★ = 59,992, anchors L(500) = 0.60,
L(16,000) = 0.30 (α_eff = 0.20):*

| floor fraction f(16k) | 0 | 0.25 | 0.50 | 2/3 | 0.75 | 5/6 |
|---|---|---|---|---|---|---|
| fitted α | 0.200 | 0.200 | 0.200 | 0.200 | 0.200 | 0.199 |
| R² of the pure fit | 1.0000 | 0.9995 | 0.9966 | 0.9903 | 0.9833 | 0.9698 |
| signed rel. error at N★ | +0.000 | +0.039 | +0.091 | +0.138 | +0.167 | +0.201 |

*Floor fraction at which the noiseless miss first reaches +0.10 / +0.20, by effective
exponent.* The scan runs f = 0 to 0.95 on a 0.001 grid. "Not reached" therefore means not
reached for f ≤ 0.95. The one such row was extended to 0.999.

| α_eff | +0.10 at f = | +0.20 at f = | R² there |
|---|---|---|---|
| 0.136 | 0.755 | not reached for f ≤ 0.95 (max +0.179 there); first at f = 0.979 | 0.988 / 0.867 |
| 0.200 | 0.535 | 0.831 | 0.996 / 0.970 |
| 0.253 | 0.404 | 0.696 | 0.998 / 0.986 |
| 0.317 | 0.295 | 0.552 | 0.999 / 0.993 |
| 0.361 | 0.242 | 0.471 | 0.999 / 0.995 |

The steeper the curve, the smaller the floor needed for a 20% miss, and the higher the R²
that hides it.

*(b) With noise (20,000 replications per row, anchors as in (a)).*

| noise | f(16k) | P(R² ≥ 0.98) | mean e | sd e | P(\|e\| ≤ 0.20) | P(e > 0) | P(0.03 ≤ e ≤ 0.25) |
|---|---|---|---|---|---|---|---|
| medium | 0 | 1.000 | −0.001 | 0.036 | 1.000 | 0.502 | 0.198 |
| medium | 0.50 | 1.000 | +0.091 | 0.033 | 1.000 | 0.996 | 0.966 |
| medium | 2/3 | 0.980 | +0.137 | 0.031 | 0.982 | 1.000 | 0.999 |
| medium | 0.75 | 0.691 | +0.166 | 0.030 | 0.876 | 1.000 | 0.999 |
| medium | 5/6 | 0.030 | +0.201 | 0.029 | 0.481 | 1.000 | 0.962 |
| high | 0.50 | 0.959 | +0.089 | 0.065 | 0.962 | 0.911 | 0.817 |
| high | 0.75 | 0.500 | +0.165 | 0.059 | 0.713 | 0.995 | 0.912 |

*(b′) The corner the expectations lean on: floor half to two-thirds of L(16k), α_eff 0.20
to 0.25 (medium noise, 20,000 replications per row).*

| α_eff | f(16k) | noiseless e | mean e | sd e | P(\|e\| ≤ 0.20) | P(e > 0) | P(0.03 ≤ e ≤ 0.25) | P(R² ≥ 0.98) |
|---|---|---|---|---|---|---|---|---|
| 0.20 | 0.50 | +0.091 | +0.091 | 0.033 | 1.000 | 0.996 | 0.965 | 1.000 |
| 0.20 | 2/3 | +0.138 | +0.137 | 0.031 | 0.983 | 1.000 | 1.000 | 0.980 |
| 0.25 | 0.50 | +0.128 | +0.127 | 0.031 | 0.993 | 1.000 | 0.999 | 1.000 |
| 0.25 | 2/3 | +0.186 | +0.185 | 0.029 | 0.685 | 1.000 | 0.988 | 0.980 |

Over this corner the noiseless bias runs from +0.091 to +0.186, and its top corner sits
0.014 under P3's threshold.

P1's band [0.10, 0.60] contained α̂ in 100% of the replications of (b). That is by
construction (α_eff = 0.20), so it says only that the band is wide relative to the noise:
about 31× the printed interval's mean width.

*(c) The printed bootstrap interval: 1,000 replications per row through `fit_cells`. The
target is the noiseless fit's α, 0.200 in every row. σ levels are the ones used; unlisted
components are 0.*

| noise structure (σ levels) | sd(α̂) | mean CI width | coverage of nominal 95% | analytic SE ratio boot/true |
|---|---|---|---|---|
| medium mix (σ_c 0.01, σ_d 0.03, σ_e 0.015, σ_dev 0.02), f = 0 | 0.0057 | 0.0160 | 0.801 | 0.786 |
| medium mix (same σ), f = 0.75 | 0.0057 | 0.0157 | 0.787 | 0.786 |
| nested data only (σ_d 0.03) | 0.0046 | 0.0115 | 0.741 | 0.692 |
| independent only (σ_e 0.015) | 0.0031 | 0.0092 | 0.830 | 0.816 (= √(2/3)) |
| nested + independent (σ_d 0.03, σ_e 0.015) | 0.0056 | 0.0146 | 0.776 | 0.730 |
| seed-level only (σ_c 0.01) | 0.0000 | 0.0055 | 1.000 | — (slope unaffected) |

The per-seed-slope t-interval (eq. 3; 20,000 replications per row, seed 20261106) covers at
the nominal level in every structure: 0.950 / 0.950 / 0.951 / 0.950 / 0.951 for medium /
nested only / independent only / nested + independent / high. It is 2.7× wider than
the printed interval (mean width 0.0425 at medium noise). The coverage figures in (c) carry
a Monte Carlo SE of about 0.013 at 1,000 replications.

**The first docstring of `lib/scaling.py` and program.md's first instrument note claimed
the within-N bootstrap "errs wide". That is true only for the shared-initialization
component. Under nested data it errs narrow. The lead has withdrawn the claim, and the
docstring now calls the interval descriptive. Read the printed `[ci_low, ci_high]` as
roughly an 80% interval.**

*(d) Can six cells tell a power law from a power law plus a floor?* This used a profile
least-squares fit of `L∞ + b N^-β` (a grid of 200 values of L∞ in [0, 0.985·min_k L̄_k],
OLS for b and β at each) and an F(1, 3) test of the extra parameter at 5% (critical
10.13), 4,000 replications per row.

| noise | α_eff | f(16k) | test prefers the floor | L̂∞ 5–95% (true) | P(\|e\| ≤ 0.2): pure law / floor fit |
|---|---|---|---|---|---|
| medium | 0.20 | 0 | 0.037 (false alarms) | 0.000–0.103 (0) | 1.000 / 1.000 |
| medium | 0.20 | 0.25 | 0.178 | 0.000–0.146 (0.075) | 1.000 / 1.000 |
| medium | 0.20 | 0.50 | 0.628 | 0.086–0.193 (0.150) | 1.000 / 1.000 |
| medium | 0.32 | 0.50 | 0.982 | 0.119–0.177 (0.150) | 0.767 / 1.000 |
| high | 0.20 | 0.50 | 0.238 | 0.000–0.225 (0.150) | 0.961 / 0.984 |
| high | 0.20 | 0.75 | 0.724 | 0.159–0.267 (0.225) | 0.724 / 0.988 |

The honest reading has three parts:

- **R² cannot tell them apart.** A direct curvature test can, but only once the floor is
  at least half the loss at the top of the range and the seed-mean noise is small.
  Small floors (f ≤ 0.25) are mostly invisible (power ≤ 0.18). Even when the test fires,
  the floor's *value* stays poorly pinned: 5–95% range 0.086–0.193 around a true 0.150 at
  medium noise, and 0.000–0.225 at high noise.
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

**One stated belief, pushed through the harness.** Each probability below is first
computed from a single belief about the curve, then adjusted only for a factor the harness
does not model, and that factor is named. The belief, drawn in this order:

- the chord exponent over 500–16,000, α_eff ~ N(0.23, 0.06²), truncated to [0.08, 0.45];
- the floor fraction f(16k) ~ U(0.40, 0.80): the half-to-two-thirds corner of (b′),
  widened more upward than downward, because a 24k-parameter net may sit near its limit;
- a net under-training term on e ~ U(−0.05, +0.03), centred slightly negative because the
  step budgets make a deficit that does not grow with N at least as plausible as one that
  does, and those profiles lower e (eq. 4);
- a +3% selection inflation of the N = 500 cell, and medium noise.

There are 20,000 samples, one DGP replication each. α_eff is drawn as 80,000 normals, of which
the first 20,000 inside the truncation are kept. Under it α̂ has mean 0.237 (10–90%: 0.160–0.314) and e has median +0.147 (10–90%: +0.061 to
+0.247). Three sensitivity runs change one input each: a wider floor U(0.25, 0.80), a
symmetric under-training term U(−0.05, +0.05), and high noise.

| ID | Rule | Belief arithmetic: main (sensitivity range) | Stated | Adjusted for |
|---|---|---|---|---|
| P1 | α̂ ∈ [0.10, 0.60] | 0.995 (0.993–0.995) | ≈ 0.95 | training failures the harness cannot produce (e.g. step-starved large cells flattening the curve) |
| P2 | R² ≥ 0.98 | 0.74 (0.64–0.81) | ≈ 0.7 | the 400-step / ~20-pass kink between 2,000 and 4,000 |
| P3 | \|e\| ≤ 0.20 | 0.75 (0.71–0.82) | ≈ 0.7 | dev → test shift (±0.04–0.05 per 5%) and curvature outside the floor family, which enlarges the miss |
| P4 | e > 0 | 0.99 (0.95–0.99) | ≈ 0.9 | a floor below a quarter of L(16k), which the belief does not sample |
| P5 | α̂ ∈ [0.15, 0.32] | 0.85 (0.84–0.85) | ≈ 0.8 | as P1, plus the kink of P2 |
| P6 | e ∈ [0.03, 0.25] | 0.87 (0.78–0.87) | ≈ 0.8 | the factors of P3 and P4 together, one per tail |
| P7 | sealed seed-mean best_step ≥ 6,329 | not modeled | ≈ 0.65 | judgment about training dynamics (below) |

- **P1: α̂ ∈ [0.10, 0.60]. Expect SUPPORTED (≈ 0.95).**
  - *Central α̂ ≈ 0.24, likely range 0.16–0.31.* A 24k-parameter CNN on 450 images should
    land around 0.6–0.8 nats of development cross-entropy. At 14,400 images it should be
    near 0.30–0.35, against the sklearn benchmark context of 0.84–0.90 accuracy at full
    data (Xiao et al.). That is a ratio of 1.8–2.6 over 32×, so α ≈ 0.17–0.28, and the
    N = 500 selection term adds about +0.006.
  - *The upper bound is close to arithmetic.* α > 0.60 needs L(500)/L(16k) > 8, and a
    best-checkpoint loss near the uniform ln 10 = 2.30 against L(16k) ≈ 0.29 gives at
    most 7.9.
  - *The lower bound is the only live risk.* α < 0.10 needs a ratio below 1.41, which
    would mean 450 images already get within 41% of the 14,400-image loss.
  - The prior band is wide, and the literature value it rests on (−0.35 for ImageNet
    cross-entropy) is for model-grown-with-data curves.
- **P2: R² ≥ 0.98. Expect SUPPORTED (≈ 0.7; the first draft said 0.8).**
  - *Why it holds.* By synthetic (b) it holds with probability ≥ 0.98 at medium noise for
    any floor up to two-thirds of L(16k).
  - *What breaks it:*
    - a floor fraction ≥ 0.75 (0.69 at f = 0.75, 0.03 at 5/6), which the belief samples;
    - a kink at the regime change between 2,000 and 4,000 (563 steps for twice the data);
    - selection noise at N = 500 from the 50-image inner set and 8 checkpoints.
  - *Reading.* A pass is weak evidence. It is compatible with a 15–20% extrapolation miss.
- **P3: |e| ≤ 0.20. Expect SUPPORTED, but not surely (≈ 0.7).**
  - *Central e ≈ +0.15 (median +0.147), 10–90% +0.06 to +0.25.* This replaces the first
    draft's +0.12.
  - *Why the central value moved.* The floor corner I named gives a noiseless bias of
    +0.091 to +0.186 (table b′), not the +0.09 to +0.17 first written. Add the +0.014
    small-N selection term and the corner's top reaches the threshold. At that corner P3
    holds only 0.685 of the time.
  - *Where it fails.* Above f ≈ 0.70 at α_eff 0.25, above 0.55 at 0.32, above 0.83 at
    0.20. The belief puts real weight there, so P3 is a near-coin at the upper edge of my
    own guess.
  - *Why not lower.* A deficit in the large in-fit cells lowers e (eq. 4), which helps P3.
    The stated 0.7 is the arithmetic's 0.75 less the named adjustment. The draft's 0.7,
    set against a +0.12 centre, had no arithmetic behind it.
- **P4: e > 0. Expect SUPPORTED (≈ 0.9).**
  - *What pushes e up.* The fixed-model floor (Rosenfeld; Hoffmann; Bahri), the small-N
    selection effect through the negative leverages of N = 500 and 1,000, and any deficit
    at the sealed cell.
  - *What pulls it down.* Under-training of the in-fit 4,000–16,000 cells. Their leverages
    sum to +1.633, so inflating them raises L̂(N★). To first order, an equal 5% deficit in
    every ~20-pass cell lowers e by 0.032, and a 5% deficit in the in-fit cells alone
    lowers it by 0.082 (eq. 4 table). The first draft said every systematic term pushes e
    positive. That contradicted eq. 4 and is withdrawn.
  - *What could flip it.* A floor below about a quarter of L(16k) (noiseless bias
    ≤ +0.04), together with an in-fit deficit; noise (sd ≈ 0.03 at medium, 0.06 at high);
    a dev → test shift making t10k *easier* by ≥ 5%. The data card measured no first-order
    shift.
  - *Reading.* A positive e does not identify the floor. MC5 / P7 and the per-cell
    `best_step` are what separate the floor from under-training.
- **P5: α̂ ∈ [0.15, 0.32]. Expect SUPPORTED (≈ 0.8).** This is P1's likely range made
  into a rule: a fixed 24k-parameter net should show a smaller exponent than the
  model-grown-with-data −0.35. It fails low if step-starved large cells flatten the top of
  the curve. It fails high if the small cells' selected checkpoints are far from their
  optima, since inflating N = 500 steepens the line.
- **P6: e ∈ [+0.03, +0.25]. Expect SUPPORTED (≈ 0.8).** The law is optimistic, but by
  less than a quarter. It fails low with a weak floor or an in-fit deficit (P4's risks).
  It fails high with a strong floor or a steep curve. The noiseless miss reaches +0.25 at
  f = 0.815 when α_eff = 0.25 (0.785 once the +0.014 selection term is added), and at
  f = 0.926 when α_eff = 0.20. That is P3's failure region, pushed out by about 0.1 in f.
- **P7: sealed seed-mean best_step ≥ 6,329. Expect SUPPORTED, weakly (≈ 0.65).**
  - *Why late.* The net has low capacity, AdamW runs at a constant 1e-3, and there are
    about 20 passes over 53,993 images, so overfitting should be slow. The 5,999-image
    inner loss is likely still falling, or flat, in the last quarter. The rule needs the
    three seeds' best checkpoints to average at least 6,329. Only the last 11 of the 41
    grid points lie at or above it (6,510 to 8,400 every 210, plus 8,437).
  - *Why not surely.* A plateau by mid-training lets constant-LR noise scatter the argmin
    over the flat part, and an early onset of overfitting pulls it before pass 15.
  - *The threshold.* 6,329 is 75.0% of 8,437. It was set from the first draft's 8,438-step
    budget and kept as registered; no grid point lies between 6,300 and 6,510, so the
    difference cannot matter.

### Falsifiable priors this card stakes

Each prior names a lever, a direction, and a magnitude with units, and each can come out
false. All are keyed to notarized output: a printed key of a run, or a pinned table.

| ID | Prior | Read from | False if |
|---|---|---|---|
| MC1 (= P5) | Over N = 500 → 16,000 the exponent of seed-mean development cross-entropy is α̂ ∈ **[0.15, 0.32]** (exponent units; central 0.24) | exponent run `primary_metric` | α̂ < 0.15 or > 0.32 |
| MC2 | The curve FLATTENS: the local exponent over the three smallest cells (500–2,000) exceeds that over the three largest (4,000–16,000) by **≥ +0.03** (exponent units; central +0.11 under the belief, of which about +0.02 is the N = 500 selection term alone; synthetic sd 0.017 at medium noise) | `tables/scaling_fit.tsv` `mean_val_mlogloss` (two 3-point OLS slopes) | difference < +0.03 |
| MC3 (= P6) | The pure law is optimistic at N★ = 59,992 by a bounded amount: `extrapolation_rel_error` ∈ **[+0.03, +0.25]** (fraction of the measured loss; central +0.15) | sealed run `extrapolation_rel_error` | e < +0.03 or e > +0.25 |
| MC4 | The printed 95% bootstrap interval is narrow, **ci_high − ci_low ≤ 0.04** exponent units. The per-seed-slope 95% t-interval (eq. 3) is **≥ 2×** wider | exponent run `ci_low`, `ci_high`; pinned `tables/cell_*_s*.tsv` | width > 0.04, or t-interval < 2× the printed width |
| MC5 (sealed half = P7) | The full-pool cell is near compute-limited: sealed seed-mean `best_step` **≥ 6,329** steps (75.0% of its 8,437). The N = 16,000 cell's seed-mean `best_step` **≥ 1,125** (50% of 2,250) | sealed run and N = 16,000 cell `best_step` | either is below its bound |

Expectations for the unregistered priors, from the same belief and harness:

- **MC2 ≈ 0.9.** The belief arithmetic gives 0.98 (0.94–0.98 across the sensitivity runs).
  It is shaded because a step-limited N = 4,000 cell can bend the top of the curve either
  way. A pass here can come from small-N selection alone: a +3% inflation at N = 500 adds
  +0.02 by itself, so MC2 does not identify the floor.
- **MC4 ≈ 0.7.** In (c)'s medium row the printed width was ≤ 0.04 in every one of 1,000
  replications (mean 0.016). The t-interval was at least 2× wider in 0.715 of them (median
  ratio 2.70; 0.742 at f = 0.75). The risk is the t-interval's own noise: with 3 seeds its
  sd has 2 degrees of freedom.

MC5 is the interpretive key for P4 and P6. If both halves hold, the large in-fit cells and
the sealed cell were both still improving at their last checkpoints. By eq. 4 the net
effect of that deficit on e can have either sign, so `findings.md` must credit e neither to
the floor alone nor to under-training alone.

**Registration status.** Before any cell ran, the lead registered MC1, MC3 and the sealed
half of MC5 as **P5, P6 and P7** in `study.yaml` (program.md, "Lead decisions after the
DATA/METHOD review"). This schema-3 contract registers `predictions:`, and the contract
validator refuses `predictions_to_falsify:` beside it ("give predictions: or
predictions_to_falsify:, never both"). So the card's priors are mirrored as registered
predictions, not into that field. MC2, MC4 and the N = 16,000 half of MC5 read pinned
tables and stay unregistered. If the lead registers one before the fit phase,
`klein predict adjudicate` decides it against the tables' hashes. Otherwise SYNTHESIZE holds
them to account as the card's stated expectations.

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
