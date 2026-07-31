---
type: method-card
domain: "insurance"
status: complete
method: "generalized quantile least squares (gQLS) for log-location-scale loss models"
source_paper: "Adjieteh (2024), PhD thesis, UW-Milwaukee — §6.2.2 Hurricane Damages"
concepts:
  [
    quantile-least-squares,
    generalized-least-squares,
    log-location-scale-families,
    breakdown-point,
    influence-function,
    quantile-covariance,
    chi-square-goodness-of-fit,
    parametric-bootstrap,
    return-level,
    plotting-position-convention,
    heavy-tail-decision-instability,
  ]
related:
  [
    ../../knowledge/method_cards/quantile-least-squares.md,
    ../02-rqls-pv-severity/method_card.md,
  ]
refs_verified: true # every row's authors/venue/year/id confirmed online 2026-07-31; two PAGE-LEVEL caveats are flagged in §5
triad: # Theory + Papers + Practice — self-asserted, gate-checked
  theory: true # §2: notation table + eqs. (2.1)(2.4)(2.5)(3.4)(3.6)(3.8)(5.2)(5.3)
  papers: true # §5: 12 references verified online; refs_verified is true
  practice: true # estimators.py + stress.py + 20/20 tests + prepare.py gate PASS
practice_evidence:
  implementation: "studies/06-hurricane-gqls-returnlevels/estimators.py, stress.py"
  tests: "tests/test_gqls.py — 20 passed in 0.69s (uv run --no-sync pytest studies/06-hurricane-gqls-returnlevels/tests -q)"
  gate: "prepare.py — data-identity GATE PASS: 8/8 Table-6.8 statistics and both MLE-lognormal anchors reproduce to <= 1e-4"
  measured_result: "all 96 QLS cells of published Table 6.10 reproduced to mean |dev| 0.0020 / max 0.0052 under the thesis's own quantile convention"
---

# Method card — generalized quantile least squares (gQLS) for log-location-scale loss models

> Gate 2 (METHOD), depth FULL. Pedagogy written BEFORE the experiment loop.
> Protocol: `.claude/skills/klein/references/method-gate-protocol.md`.
> Reproduction target: Adjieteh (2024) §6.2.2, Tables 6.8 / 6.9 / 6.10 — transcribed
> cell-by-cell into `reference/thesis_tables.json` (236 cells, PDF pages 79/80/82).
>
> **This card extends, and does not duplicate,
> `knowledge/method_cards/quantile-least-squares.md`** — the validated card distilled
> from study 02's synthetic PV-severity lab. That card owns the *premium-error* story
> (QLS vs MLE vs MTM under truncation, censoring, and contamination, scored in dollars
> of layer premium). This card owns what study 02 explicitly skipped: **full-covariance
> GLS weighting** (study 02's verdict was "skip the diagonal plug-in GLS — it added
> noise"; here the full `Σ★` is *known in closed form*, which changes the verdict),
> **formal goodness-of-fit testing**, the **log-location-scale unification** of six
> families, and **return levels** as the decision unit.

---

## 1. Intuition (for a practitioner)

### The one-sentence version

**gQLS is a Q-Q plot fitted by generalized least squares.**

You already do the first half by hand. You take your losses, plot the empirical
quantiles against the theoretical quantiles of a candidate law, and eyeball whether the
points fall on a line. If they do, the *intercept* of that line is your location
parameter and the *slope* is your scale parameter. QLS stops eyeballing and runs the
regression. gQLS runs it with the right error covariance.

### Why a small set of quantiles buys robustness

Reach for the maximum likelihood estimator on the 30 hurricane losses and every
observation gets a vote weighted by the score function — including the 1926 Great Miami
storm at \$72.3bn, which is 5.3× the sample standard deviation above the mean. The MLE
has no mechanism for saying "that one is unusual." Feed it a version of the dataset in
which that single number is inflated tenfold (a decimal-point typo; a double-counted
recovery) and the lognormal σ̂ moves from **0.83 to 1.10** — a 32% shift in the
parameter that governs the entire tail, from *one* corrupted record out of thirty.

QLS never looks at that observation. It reads the sample at eight probability levels
between `a = 0.05` and `b = 0.95` and fits the quantile *curve* through those eight
points. The largest observation sits above `p = 0.95`; nothing in the estimating
equations consults it. Corrupt it, delete it, multiply it by a million — the estimate
does not move. That is not a heuristic; it is the definition of a **breakdown point**:

> `BP = min{a, 1 − b}` — the fraction of the sample you may corrupt arbitrarily
> before the estimate can be driven anywhere.

At `(a, b) = (0.05, 0.95)` that is 5% — and 5% of 30 events is 1.5, so **one** corrupted
event is tolerated and **two** are not. At `(0.10, 0.90)` it is 10%, so three are
tolerated. This is the study's RQ4 in one line: the trim you choose *is* the number of
bad records you are buying protection against, and at n = 30 you can count them on one
hand. There is no free lunch — the same trim that ignores the corrupted maximum also
ignores the *genuine* maximum, which is why part 4's regime table exists.

### Why the "generalized" matters — and what study 02 got wrong about it

Ordinary QLS (`oQLS`) runs plain OLS on the Q-Q plot. That silently assumes the eight
plotted points are equally reliable and mutually independent. **They are neither.**
Sample quantiles in the sparse tail wobble far more than sample quantiles near the
median, and adjacent quantiles from the same sample are strongly positively correlated
— they share order statistics.

The fix is generalized least squares: down-weight the noisy points, and account for the
correlation. GLS normally stalls here, because you would have to *estimate* the error
covariance. **In this problem you do not.** Once you commit to a family, Serfling's
joint asymptotic normality theorem hands you the covariance of the empirical quantile
vector in closed form, and after standardization it depends only on the *standard*
member — no unknown parameters at all. You can write `Σ★` down before seeing a single
data point.

How much does that buy? The thesis's asymptotic relative efficiencies (Tables 3.2/3.3,
k = 25, `(0.05, 0.95)`) tell the story bluntly:

| Standard member | oQLS ARE | gQLS ARE |
| --------------- | -------- | -------- |
| Normal          | 0.936    | 0.911    |
| Gumbel          | 0.902    | 0.893    |
| Logistic        | 0.704    | 0.955    |
| Laplace         | 0.757    | 0.947    |
| **Cauchy**      | **0.232** | **0.995** |

(Note the Normal row: gQLS is very slightly *worse* than oQLS there. For a light,
well-behaved member the identity-matrix pretence costs almost nothing, and the GLS
weighting's finite-sample overhead is not repaid. The gain is concentrated exactly where
the tail is heavy — which is where loss data lives.)

For a heavy standard member, ordinary QLS throws away ~77% of the available information
and gQLS throws away almost none. **That is the single largest effect in this method.**
And it is directly visible in the data we are reproducing: on the hurricane sample at
`(0.05, 0.95)`, log-Cauchy's σ̂ is **0.23 under oQLS and 0.49 under gQLS** — a factor of
2.1 from the weighting alone. That gap is this study's specification falsifier: if a
from-scratch `Σ★` is wrong, those two numbers will not split that way.

> **Correction to study 02's inherited advice.** Study 02 concluded "skip the diagonal
> plug-in GLS — it added noise, not efficiency." That verdict was about a *plug-in*,
> *diagonal* approximation estimated from a first-stage fit. Here `Σ★` is **exact,
> full, and parameter-free**. The two situations are not the same method, and the ARE
> table above is why. Study 02's own caveat already pointed here: "use OLS, or
> full-covariance GLS only on a coarse, stably-invertible grid" — k = 8 on the hurricane
> data *is* that coarse, stably-invertible grid.

### The catch this study exists to expose

Everything above is about **parameters**. An actuary does not sell a parameter; they
sell a number like "the 1-in-100 event loss." Getting from one to the other means
pushing the estimate through the quantile transform

`return level = exp(μ̂ + σ̂ · F*⁻¹(0.99))`

and that transform is not gentle. For the lognormal, `F*⁻¹(0.99) = 2.33`. For
**log-Cauchy** — the family that fits this data *best* by both goodness-of-fit tests —
`F*⁻¹(0.99) = tan(0.49π) = 31.82`. The same 0.04 wobble in σ̂ changes a lognormal
return level by 10% and a log-Cauchy return level by a factor of **3.6**.

So the method's headline claim ("robust parameters") and the decision-maker's actual
question ("stable 1-in-100") may come apart, and they may come apart *worst* for the
best-fitting model. That is RQ5/RQ6, and it is genuinely open. A pre-loop smoke check
of the implementation already showed the fitted log-Cauchy 1-in-100 landing several
orders of magnitude above the largest event ever recorded — enough to make the question
concrete, not enough to answer it.

---

## 2. Math core

### Notation

| Symbol | Meaning |
| --- | --- |
| `n` | sample size (here 30) |
| `X_(1) ≤ … ≤ X_(n)` | order statistics of the losses, in dollars |
| `x_i = log X_i` | the **fitting column** — log-dollars, `log(damage_bn_1995 × 1e9)` |
| `k` | number of quantile levels used for **estimation** (here 8) |
| `a, b` | extreme quantile levels, `0 < a = p_1 < … < p_k = b < 1` |
| `p_i` | the estimation grid, eq. (3.8) |
| `F̂⁻¹(p)` | empirical quantile — **the thesis defines it as `X_(⌈np⌉)`** |
| `f, F, F⁻¹` | pdf / cdf / quantile function of the fitted law |
| `f★, F★, F★⁻¹` | pdf / cdf / qf of the **standard member** (`μ = 0, σ = 1`) |
| `μ, σ` | log-location and log-scale; `β = (μ, σ)′` |
| `Y` | `(log F̂⁻¹(p_1), …, log F̂⁻¹(p_k))′` — the response, `k × 1` |
| `X` | design matrix `[1, F★⁻¹(p_i)]`, `k × 2` |
| `Σ★` | standard-member quantile covariance, `k × k`, **known** |
| `r`, `p^out` | number and levels of the **universal validation** grid (here `r = 25`) |
| `W`, `W_out` | in-sample and out-of-sample GoF statistics |
| `BP` | asymptotic breakdown point |
| `IF(x, ·)` | influence function |

### The five load-bearing equations

**(3.8) — the grid.** Fix the endpoints for robustness, then space the rest evenly:

```
p_i = a + (i − 1)/(k − 1) · (b − a),      i = 1, …, k
```

For `k = 8, (a, b) = (0.05, 0.95)`:
`[0.05, 0.178571, 0.307143, 0.435714, 0.564286, 0.692857, 0.821429, 0.95]`.
The three trims the thesis reports are `(0.02, 0.98)`, `(0.05, 0.95)`, `(0.10, 0.90)`.

**(2.1) — the quantile covariance (Serfling's Theorem B).** The empirical quantile
vector is asymptotically normal about the true quantiles with covariance `σ_ij / n`,

```
σ_ij = p_i (1 − p_j) / [ f(F⁻¹(p_i)) · f(F⁻¹(p_j)) ]     for i ≤ j,    σ_ij = σ_ji otherwise
```

Two things make this usable. First, once the family is fixed, replacing `f, F⁻¹` by the
**standard** `f★, F★⁻¹` removes every unknown — `Σ★` is a matrix of pure numbers.
Second (thesis Proposition 3.1), for a **log**-location-scale family the Jacobian of the
`log` transform is diagonal with entries `1/F⁻¹(p_i)`, and the `F⁻¹(p_i)F⁻¹(p_j)` factors
cancel exactly against the `σ²·F⁻¹(p_i)F⁻¹(p_j)` in the numerator. **The log family
inherits the very same `Σ★`.** That cancellation is the reason six different loss laws
share one piece of code.

**(3.4) / (3.6) — the two estimators.** With `Y = Xβ + ε`, `ε ~ AN(0, σ²Σ★/n)`:

```
oQLS:   β̂ = (X′X)⁻¹ X′Y                       — pretends Σ★ = I_k
gQLS:   β̂ = (X′Σ★⁻¹X)⁻¹ X′Σ★⁻¹Y                — uses the known Σ★
```

with asymptotic covariances `(σ²/n)(X′X)⁻¹X′Σ★X(X′X)⁻¹` (3.5) and `(σ²/n)(X′Σ★⁻¹X)⁻¹`
(3.7). **Numerically, never form `Σ★⁻¹`.** Factor `Σ★ = LL′` and run OLS on the whitened
system `L⁻¹X`, `L⁻¹Y` — mathematically identical, numerically far safer. `Σ★`'s condition
number reaches ~2·10³ for log-Cauchy on `(0.05, 0.95)` with k = 8 and grows sharply as
`a → 0`; `estimators.py` returns it on every gQLS fit so the loop can see it.

**(5.2) — in-sample goodness of fit.** The gQLS residuals `ε̂ = Y − Xβ̂` support a
quadratic form. Proposition 5.2 decomposes `Q = (n/σ²)(Y − Xβ)′Σ★⁻¹(Y − Xβ) ~ χ²_k`
orthogonally into `Q₁ + Q₂` with `Q₂ ~ χ²_2` (the two fitted parameters), leaving

```
W = (n / σ̂²_gQLS) · (Y − Xβ̂)′ Σ★⁻¹ (Y − Xβ̂)   ~   χ²_{k−2}      under H₀
```

Here `k = 8`, so **`W ~ χ²_6`** and the p-value is `P(χ²_6 > W)`. Sanity anchor: the
thesis's log-Cauchy `W = 3.00` at `(0.02, 0.98)` gives `P(χ²_6 > 3.00) = 0.809`, printed
as 0.81. Ali & Umbach (1989) proposed a similar test but estimated `σ²` by the **sample
variance**, which requires a finite second moment; (5.2) uses `σ̂²_gQLS` instead and
therefore survives Cauchy-type tails — a small change with large consequences here,
where the winning family has no moments at all.

**(5.3) — out-of-sample goodness of fit.** `W` has a structural flaw for model
*comparison*: it scores residuals only on the estimation grid, so a more aggressive trim
shrinks the very interval being scored and looks better for free. The fix is a
**universal** grid `p^out_1..p^out_r`, the same for every `(a, b)`:

```
W_out = (n / σ̂²_gQLS) · (Y_out − X_out β̂)′ Σ_out⁻¹ (Y_out − X_out β̂)
```

with `β̂` still from the estimation grid, and `Σ_out` from (2.1) at the out-levels. The
universal grid is `r = 25` levels spanning 0.01 to 0.99 (§6.2.1 describes the Google-stock
analogue as "the universal set of 50 quantile levels (from 0.01 to 0.99)"; eq.-(3.8)
spacing on `[0.01, 0.99]` reproduces the published `W_out` statistics to ≤ 0.005).
Because the two grids overlap only partially, the thesis calls the null distribution
"a major challenge" and prices the p-value by **parametric bootstrap** (§5.2, Steps 1–4,
B = 1000): simulate from the fitted law, refit, recompute `W_out`, and report the
exceedance fraction. `estimators.py` implements both that bootstrap **and** a naive
`χ²_{r−2} = χ²_23` reference, because RQ2 asks whether the expensive one earns its keep.

**(2.4) / (2.5) — why it is robust, formally.** `BP = min{a, 1 − b} > 0`, and the
influence function is bounded:

```
IF(x, β̂_oQLS) = (X′X)⁻¹X′ · ( IF(x, F̂⁻¹(p_1)), …, IF(x, F̂⁻¹(p_k)) )′
IF(x, β̂_gQLS) = (X′Σ★⁻¹X)⁻¹X′Σ★⁻¹ · ( same vector )′
```

where each `IF(x, F̂⁻¹(p_i)) = [p_i − 1{x ≤ F⁻¹(p_i)}] / f(F⁻¹(p_i))` is a bounded step
function. Boundedness is what "one bad record cannot move it far" means; positivity of
`BP` is what "several bad records still cannot" means. The two are different guarantees
and the study tests both (contamination → RQ3, deletion → RQ4).

### The log-location-scale unification (and Pareto I's disguise)

A law is **log-location-scale** when `log X` is location-scale (thesis eq. 3.9):

```
f(x) = (1/xσ) f★( (log x − μ)/σ ),      F⁻¹(u) = exp( μ + σ F★⁻¹(u) )
```

so `log F⁻¹(u) = μ + σ F★⁻¹(u)` — **linear in the parameters**, which is the whole reason
a closed-form regression exists. The six families are one code path with six
`(f★, F★⁻¹)` pairs:

| Family | `f★(z)` | `F★⁻¹(u)` | Source |
| --- | --- | --- | --- |
| log-Cauchy | `1/(π(1+z²))` | `tan(π(u − 0.5))` | Table 3.4 |
| log-Gumbel | `exp(−z − e^{−z})` | `−log(−log u)` | **Table 3.1** (see note) |
| log-Laplace | `0.5 e^{−|z|}` | `log(2u)` if `u ≤ 0.5`, else `−log(2(1−u))` | Table 3.4 |
| log-Logistic | `e^{−z}/(1+e^{−z})²` | `−log(1/u − 1)` | Table 3.4 |
| lognormal | `φ(z)` | `Φ⁻¹(u)` | Table 3.4 |
| **Pareto I** | `e^{−z}, z > 0` | `−log(1 − u)` | Table 3.4 |

> **Table-number correction.** The study brief cited "Table 3.1" for the standard
> members. Table 3.1 (printed p. 11 / PDF p. 22) is the **location-scale** table —
> Cauchy, Laplace, Logistic, Normal, Exponential, Gumbel, Lévy. The **log**-location-scale
> table is **Table 3.4** (printed p. 20 / PDF p. 31), and it lists only **five** members:
> log-Cauchy, log-Laplace, log-Logistic, lognormal, Pareto I. **log-Gumbel is absent from
> Table 3.4** — its standard member has to be taken from Table 3.1's Gumbel row. The two
> tables are otherwise identical in their `(f★, F★⁻¹)` columns, which is Proposition 3.1
> in tabular form.

**Pareto I is the one worth staring at.** Written the usual way — `S(x) = (θ/x)^α`,
`x > θ` — it looks nothing like a location-scale law. Reparametrize `μ = log θ`,
`σ = 1/α` and `log X` becomes a **two-parameter exponential**: standard member
`f★(z) = e^{−z}` on `z > 0`. Three consequences, all load-bearing:

1. Its Q-Q plot is against **standard exponential** quantiles — which is exactly what
   the thesis's Figure 6.8 bottom-right panel is labelled (`Standard Exponential
   Quantiles`), and it looks anomalous next to the five symmetric panels for good reason.
2. `μ` is not a centre, it is the **left boundary of the support**. Its MLE is the
   boundary estimator `μ̂ = min(x)`, not a mean — and `σ̂ = mean(x) − min(x)`.
   (Reproduced exactly: 21.5413 / 1.2589 → the printed 21.54 / 1.26.)
3. Because `μ̂` depends only on the *minimum*, Pareto I's MLE is perfectly insensitive to
   the contaminated *maximum* — Table 6.10 shows `μ̂ = 21.54` unchanged, while σ̂ moves
   1.26 → 1.34 by exactly `log(10)/30 = 0.0768`. That is robustness by accident of
   parametrization, not by design, and it is a nice teaching contrast.

### The plotting-position subtlety at n = 30 — the biggest error source in this study

`F̂⁻¹(p)` is not one thing. NumPy ships nine conventions; MATLAB's `quantile` uses a
tenth-by-name (Hazen). At n = 3,000 they agree to four decimals. **At n = 30 they
disagree in the second.**

The thesis uses **both**, in the same chapter, without saying so:

- **Chapter 2, opening paragraph** *defines* `F̂⁻¹(p) = X_(⌈np⌉)` — the inverse-ECDF
  convention (`numpy method="inverted_cdf"`). That is the definition the **estimators**
  inherit.
- **Table 6.8**'s quartiles (`q1 = 4.0560`, `q3 = 12.4340`) reproduce **only** under
  **Hazen** plotting positions `(i − 0.5)/n` — MATLAB's `quantile` default. Under
  `inverted_cdf` they do not; under NumPy's default `linear` they do not either.

Measured, not assumed — from-scratch fits against the 96 published QLS cells of
Table 6.10:

| Fitting convention | mean \|deviation\| | max \|deviation\| | cells > 0.005 (of 96) |
| --- | --- | --- | --- |
| `inverted_cdf` (the thesis's own definition) | **0.0020** | **0.0052** | **1** |
| `hazen` | 0.0084 | 0.0318 | 59 — and it breaches the study's 0.02 guardrail |
| `linear` (NumPy default) | 0.0115 | 0.0324 | 78 |
| `normal_unbiased` | 0.0215 | 0.1112 | 83 |
| `closest_observation` | 0.0240 | 0.0543 | 84 |
| `median_unbiased` | 0.0261 | 0.1465 | 84 |
| `weibull` | 0.0631 | 0.4288 | 86 |

So: **Hazen for the descriptive table, `⌈np⌉` for the estimators.** `estimators.py`
exports both as named constants (`SUMMARY_QUANTILE_METHOD`, `THESIS_QUANTILE_METHOD`)
and takes `method=` everywhere, because the study pre-registered a convention sweep and
the module must not pre-empt it. One further wrinkle, exposed as `quantile_space=`: the
thesis writes `Y = log F̂⁻¹(p)` (quantile the **dollars**, then log), which is identical
to quantiling the log-dollars under order-statistic conventions but *not* under
interpolating ones.

**The lesson generalizes past this thesis:** when a paper reports parameters to two
decimals from n ≈ 30, the plotting-position convention is a first-order term in your
reproduction error budget, not a footnote. Reproduce the paper's *descriptive* table
first — it silently identifies which convention its software used.

---

## 3. Minimal from-scratch implementation plan

The plan is realized — `estimators.py` (numpy/scipy only, no library one-liners) is
written, tested, and reproducing the published tables. The honest core is short enough
to read in full:

```python
# 1. the grid, eq. (3.8)
p = a + (np.arange(1, k+1) - 1) / (k - 1) * (b - a)

# 2. design and response — log F^-1(u) = mu + sigma * F_*^-1(u)
X = np.column_stack([np.ones(k), Fstar_inv(p)])         # eq. (3.3)
Y = np.quantile(x_logdollars, p, method=method)         # the convention matters (§2)

# 3. the KNOWN covariance, eq. (2.1) at the standard member
dens  = fstar(Fstar_inv(p))
upper = np.triu(np.outer(p, 1 - p))                     # p_i(1-p_j) for i <= j
Sig   = (upper + np.triu(upper, 1).T) / np.outer(dens, dens)

# 4a. oQLS, eq. (3.4)                       4b. gQLS, eq. (3.6) — WHITENED, never Sig^-1
mu, sigma = np.linalg.lstsq(X, Y)[0]        L  = cholesky(Sig, lower=True)
                                            mu, sigma = lstsq(solve_tri(L, X), solve_tri(L, Y))[0]

# 5. GoF, eq. (5.2): quadratic form via the same factor — ||L^-1 r||^2, again no inverse
r = Y - X @ [mu, sigma]
W = n / sigma**2 * (solve_tri(L, r) ** 2).sum()
p_value = chi2.sf(W, k - 2)

# 6. the decision functional
return_level = np.exp(mu + sigma * Fstar_inv(p_target))     # dollars
```

**Module map** (all under `studies/06-hurricane-gqls-returnlevels/`):

| Object | Equation | Note |
| --- | --- | --- |
| `p_grid(a, b, k)` | (3.8) | validates `0 < a < b < 1`, `k ≥ 2` |
| `STANDARD_MEMBERS` | Tables 3.1/3.4 | six `(f★, F★⁻¹, log f★)` triples |
| `sigma_star(p, family)` | (2.1) | upper-triangle build + mirror; rejects vanishing density |
| `design_matrix(p, family)` | (3.3) | `[1, F★⁻¹(p)]` |
| `oqls(...)` / `gqls(...)` | (3.4) / (3.6) | gQLS whitens by Cholesky, records `sigma_star_cond` |
| `mle(x, family)` | — | closed form for lognormal / Pareto I / log-Laplace; Nelder-Mead on `(μ, log σ)` otherwise |
| `W(x, fit)` | (5.2) | `χ²_{k−2}`; flags `chi2_calibrated` false for non-gQLS fits |
| `W_out(x, fit, r, mode)` | (5.3) | `mode="chi2"` (χ²_{r−2}) **and** `mode="bootstrap"` (§5.2 Steps 1–4) |
| `return_level(fit, p)` | — | `exp(μ̂ + σ̂ F★⁻¹(p))`, dollars |
| `mean_loss` / `cte` | — | **raise `NotImplementedError` for log-Cauchy** (see below) |
| `stress.py` | — | `leave_top_k_out`, `inflate_max`, `bootstrap_samples`, `instability_pct` |

**The deliberate refusal.** Any path that would compute a mean or a CTE for log-Cauchy
raises `NotImplementedError` with an explanation, rather than returning a number.
Log-Cauchy has **no finite moments** — the mean integral diverges, and conditioning on
the tail does not rescue it. A numerical CTE would return a large float that is an
artifact of where the quadrature was truncated, and it would look exactly like an
estimate. Since log-Cauchy is the family that *fits this data best*, an actuary
following the goodness-of-fit test straight into a TVaR-loaded premium would get a
confident number with no meaning. The refusal is the teaching moment; price this family
through **quantiles** (`return_level`) or change families.

**What `train.py` will lean on.** `kleinlib.data.load_data_hub` (the `$DATA_HUB` seam,
bundled fallback) via `prepare.py`; `kleinlib.schema` for the results ledger. No
`kleinlib.torch_loop` / `kleinlib.encoders` — there is no neural network and no
categorical encoding here; the "model" is two parameters and the entire fit is a
2-column least-squares solve that runs in microseconds. `kleinlib.eval`'s
near-constant/non-finite prediction diagnostics do not apply either; the analogous guard
is `instability_pct`'s refusal of a non-finite or non-positive baseline return level.

**Verification already standing** (the practice leg, not a promise):

- `tests/test_gqls.py` — **20 passed in 0.69 s**. Pins the (3.8) grid; `Σ★` against
  Serfling's closed form at hand-computed entries; gQLS parameter recovery on simulated
  normals; gQLS < oQLS sampling variance on simulated Cauchy; oQLS against the textbook
  simple-regression formulas; `W`'s `χ²_6` calibration by KS over 500 null replicates;
  Table 6.8's eight statistics; both MLE-lognormal anchors; the `Σ★` falsifier; the
  moment refusal; and the full 36-parameter Table 6.9 grid.
- `prepare.py` — **data-identity GATE PASS**, 8/8 published statistics and both anchors
  to ≤ 1e-4, through the real `$DATA_HUB` seam *and* the bundled fallback.
- `reference/thesis_tables.json` — 236 transcribed cells with page-level provenance.

---

## 4. When it pays / when it doesn't

### The regime table

Data size is the wrong axis here — n is 30 and cannot change. The axes that matter are
**how contaminated the sample is** and **how heavy the fitted tail is**.

| Regime | Contamination | Tail | Verdict |
| --- | --- | --- | --- |
| Clean, light-tailed, correct family | none | normal-ish | **Doesn't pay.** MLE is efficient by construction; gQLS gives up ~9% ARE (0.911 for the normal member at k = 25) for protection you are not using — and there it is even marginally *worse* than oQLS. |
| Clean, **heavy**-tailed | none | Cauchy-like | **oQLS doesn't pay, gQLS does.** oQLS ARE 0.232 vs gQLS 0.995 — the weighting, not the trimming, is the whole story. Never run oQLS on a heavy member. |
| Gross errors, ≤ `min{a,1−b}` of the sample | 1 record in 30 | any | **Pays, decisively.** MLE σ̂ 0.83 → 1.10; gQLS parameters unchanged to two decimals (Table 6.10 starred rows). This is the thesis's headline and it is real. |
| Gross errors, **above** the breakdown point | 2+ records in 30 at `(0.05,0.95)` | any | **Stops paying — cliff, not slope.** `BP` is a guarantee, and past it there is none. Buy the wider trim `(0.10,0.90)` *before* you need it. |
| Small n, **tail-sensitive decision** | any | heavy | **Open — this study's question.** Parameter robustness does not imply return-level robustness; the quantile transform can undo it (RQ5/RQ6). |
| Wrong family | any | any | **Doesn't pay.** No robust estimator rescues a misspecified family — study 02's E7 cancellation lesson transfers unchanged. Fix the family first; that is what `W`/`W_out` are for. |

### Three honest costs

1. **Efficiency on clean data.** Small for gQLS (AREs 0.89–1.00 across the members at
   k = 25), large for oQLS on heavy members. Study 02 measured the analogous premium cost
   at ~8% for QLS-OLS on clean synthetic data.
2. **Conditioning.** `Σ★` is well-conditioned for the normal member (cond ≈ 35 at k = 8,
   `(0.05,0.95)`) and reaches ~2·10³ for log-Cauchy; on the `r = 25` validation grid it
   is far worse, since `f★(F★⁻¹(0.01)) ≈ 3·10⁻⁴` for Cauchy. Cholesky whitening handles
   it; forming `Σ★⁻¹` would not. This is why the condition number is logged, not hidden.
3. **Convention sensitivity.** At n = 30, holding everything else fixed and changing only
   the quantile *definition* moves a fitted parameter by **0.073 on average and up to
   0.461** across the seven NumPy conventions — that worst cell is **92×** the thesis's
   0.005 reporting resolution and **23×** the study's own 0.02 guardrail. Any claim at the
   second decimal from n = 30 is partly a claim about your software's `quantile()` default.

### Falsifiable priors this study will test

`study.yaml` is sealed; these mirror its eight pre-registered
`predictions_to_falsify` **verbatim in substance**, with magnitudes sharpened where the
pre-loop implementation work has made them measurable. Nothing here was appended to
`study.yaml` — the orchestrator owns that decision, and the three "PRE-LOOP" flags below
say exactly which predictions are already partly answered by specification work.

| # | Lever | Prediction (signed, with units) | Status |
| --- | --- | --- | --- |
| P1 | full 18-cell gQLS grid vs Table 6.9 (RQ1) | mean \|Δθ\| ≤ 0.01 **and** max ≤ 0.02 | **PRE-LOOP: holds under `inverted_cdf`** (mean 0.0028, max 0.0187) and **fails under `hazen`** (max 0.0313). The max is one documented cell — see P1b. |
| P1b | Table 6.9 vs Table 6.10 internal consistency | the `(0.10,0.90)` log-Gumbel μ̂ printed 22.34 in Table 6.9 is a **typo**; Table 6.10's g3 prints 22.36 and a correct fit gives 22.3587 | **PRE-LOOP: confirmed.** New — not in `study.yaml`; a discrepancy the loop would otherwise chase. |
| P2 | `W_out` bootstrap vs `χ²_23` (RQ2) | all published p-values within 0.02 of the χ² reference → the B=1000 bootstrap is redundant **on this data** | **PRE-LOOP: PARTIALLY FALSIFIED.** 16/18 agree to ≤ 0.005 — *tighter than a B=1000 bootstrap can be* (MC s.e. ≈ 0.016), so the published values look χ²-derived. But **2/18 exceed 0.02**: `(0.02,0.98)` log-Logistic (0.16 vs 0.594, Δ = 0.434) and `(0.10,0.90)` log-Laplace (0.55 vs 0.450, Δ = 0.100). The prior's "all" is false. |
| P3 | `Σ★` falsifier, o2 vs g2 log-Cauchy σ̂ | 0.23 vs 0.49 reproduced within 0.005, else `Σ★` is mis-specified → STOP | **PRE-LOOP: holds** — 0.2299 and 0.4851. |
| P4 | quantile-convention sweep | convention spread **exceeds** the 0.005 reporting resolution → at n = 30 the quantile *definition* dominates reproduction uncertainty | **PRE-LOOP: holds, overwhelmingly.** Across-convention spread on the same cell: mean 0.073, max **0.461** = 92× the resolution. Only `inverted_cdf` lands inside it. |
| P5 | MLE-lognormal 1-in-100 under leave-top-1-out | moves **> 40%** | open — loop measures |
| P6 | gQLS log-Cauchy decision stability (RQ5) | instability **< 1/3** of MLE-lognormal's; refutation is the seminar punchline (robust parameters, unstable decisions) | open — **the study's sharpest question.** The `tan(0.49π) = 31.82` amplification makes refutation live. |
| P7 | lighter-tailed GoF-passing families (lognormal / log-logistic) (RQ6) | **materially more stable** 1-in-100 than log-Cauchy despite slightly worse fit → fit quality and decision stability are different axes | open |
| P8 | instability vs breakdown point across the three trims (RQ4/RQ6) | **monotone decreasing** in `min{a, 1−b}`, at a GoF cost < 1× the `W` floor | open |
| P9 | leave-top-k-out vs breakdown theory (RQ4) | `k ≤ 1` stable at `(0.05,0.95)`; `k = 2` (2/30 = 0.067 > 0.05) **breaches** that trim but not `(0.10,0.90)` | open — the stress the thesis never ran |

**Reading P1–P4 honestly.** These are *specification* checks — they measure whether our
code implements the paper, not whether the method works. They had to be answered before
the gate could close, and answering them is what the METHOD and prepare gates are for.
The loop still owns them as receipts (`results.tsv` rows with manifests); it does not own
them as open questions. **P5–P9 are untouched**, and they are where the study's actual
contribution lies.

---

## 5. Verified references

Every row's authors, venue, year, and identifier were confirmed against the live web on
**2026-07-31**, and cross-checked against the thesis's own bibliography (PDF pages
85–87), which I read directly. Two **page-level** caveats are marked ⚠️ — in both cases
the *reference* is verified and only an interior page range rests on the thesis's own
citation.

| # | Reference | Where | Verified? |
| --- | --- | --- | --- |
| 1 | **Adjieteh, Mohammed Adjei (2024).** *Robust-Efficient Fitting of Loss Models via Quantile Least Squares.* PhD dissertation (Mathematics), University of Wisconsin–Milwaukee, August 2024. Advisor: Vytaras Brazauskas. | MINDS@UW: `minds.wisc.edu/bitstream/handle/1793/93605/Adjieteh_uwm_0263D_13880.pdf` | ✅ **corrected** — the brief said "Michael"; the title page reads **Mohammed Adjei Adjieteh** |
| 2 | **Adjieteh, M. & Brazauskas, V. (2025).** *Quantile Least Squares: A Flexible Approach for Robust Estimation and Validation of Location-Scale Families.* | *Statistics and Computing* **35**, art. 106 — DOI `10.1007/s11222-025-10626-6`; arXiv:2402.07837 (v1 2024-02-12, v2 2025-05-02, identical title) | ✅ DOI resolves; arXiv is the same paper |
| 3 | **Serfling, R. J. (2002a).** *Approximation Theorems of Mathematical Statistics.* Wiley. Orig. 1980 (ISBN 0-471-02403-1); 2002 Wiley-Interscience paperback (ISBN 0-471-21927-4). **Theorem B** (joint AN of sample quantiles) is the source of eq. (2.1); the sample-quantile influence function is the source of eq. (2.5). | Wiley | ✅ book verified · ⚠️ the thesis's interior cites (**p. 80** Thm B, **p. 265** IF) were not independently checked against the 2002 pagination |
| 4 | **Serfling, R. (2002b).** *Efficient and robust fitting of lognormal distributions* (with discussion). | *North American Actuarial Journal* **6**(4), 95–109; Discussion **7**(3), 112–116; Reply **7**(3), 116 | ✅ — note this is **not** the Statistica Neerlandica "Quantile functions for multivariate analysis" paper, a different Serfling 2002 |
| 5 | **Ali, M. M. & Umbach, D. (1989).** *A Shapiro-Wilk type goodness-of-fit test using a few order statistics.* | *JSPI* **22**(2), 251–261 | ✅ — the precursor eq. (5.2) improves on (it estimated `σ²` by the sample variance, so it needs a finite second moment) |
| 6 | **Ali, M. M. & Umbach, D. (1998).** *Optimal linear inference using selected order statistics in location-scale models.* | *Handbook of Statistics, Vol. 17: Order Statistics — Applications* (Balakrishnan & Rao, eds.), 183–213, Elsevier | ✅ volume verified (ISBN 9780444829221) · ⚠️ the 183–213 range rests on the thesis's bibliography (Elsevier ToC returned 403) |
| 7 | **Pielke, R. A. Jr. & Landsea, C. W. (1998).** *Normalized Hurricane Damages in the United States: 1925–95.* | *Weather and Forecasting* **13**(3), 621–631 — DOI `10.1175/1520-0434(1998)013<0621:NHDITU>2.0.CO;2` | ✅ — **the data source.** See the dataset README's provenance trap: the "1925–95" label is a mislabel; Table 8 carries three supplemental pre-1925 storms |
| 8 | **Brazauskas, V. & Serfling, R. (2000).** *Robust estimation of tail parameters for two-parameter Pareto and exponential models via generalized quantile statistics.* | *Extremes* **3**(3), 231–249 — DOI `10.1023/A:1011455027066` | ✅ — the one the thesis cites (**not** their NAAJ 4(4) single-parameter-Pareto paper of the same year) |
| 9 | **Genton, M. G. & de Luna, X. (2000).** *Robust simulation-based estimation.* | *Statistics and Probability Letters* **48**(3), 253–259 | ✅ — the indirect-estimator IF result behind eq. (2.5) |
| 10 | **Genton, M. G. & Ronchetti, E. (2003).** *Robust indirect inference.* | *JASA* **98**(461), 67–76 — DOI `10.1198/016214503388619102` | ✅ |
| 11 | **Xu, Y., Iglewicz, B. & Chervoneva, I. (2014).** *Robust estimation of the parameters of g-and-h distributions, with applications to outlier detection.* | *CSDA* **75**, 66–80 — DOI `10.1016/j.csda.2014.01.003` | ✅ — the paper whose §2.1 argument the thesis generalizes from g-and-h to location-scale |
| 12 | **`knowledge/method_cards/quantile-least-squares.md`** — Klein's own validated card from `studies/02-rqls-pv-severity` (archived at tag v1.0.0). | local | ✅ read in full; this card extends it (see the header note and §1's GLS correction) |

### Frontier lit-scan — positioning

**Seminal line.** Fitting parameters from a handful of order statistics is old: Mosteller
(1946) "On some useful *inefficient* statistics", then Sarhan & Greenberg (1962),
Chan (1970) and Cane (1974) for the Cauchy, and Ali & Umbach (1989/1998) for optimal
spacings and a Shapiro–Wilk-type test. What was missing was a *general* recipe for
arbitrary location-scale families with a matching goodness-of-fit apparatus.

**This work.** Adjieteh & Brazauskas supply it. The genuinely new pieces are (i) the
**closed-form, parameter-free `Σ★`** that makes full-covariance GLS practical rather than
aspirational, (ii) the ARE/IF characterization showing gQLS recovers near-full efficiency
*while* keeping a positive breakdown point, and (iii) the **paired GoF tests** (5.2)/(5.3),
of which (5.3)'s universal grid is the honest fix for comparing estimators with different
trims. The 2025 *Statistics and Computing* paper is the peer-reviewed form; the 2024
thesis carries the loss-model applications (Chapter 4's Pareto II–IV, Chapter 6's real
data) that the paper does not.

**Neighbours in the robust-severity literature.** The Brazauskas school's other
estimators — MTM (Brazauskas–Jones–Zitikis 2009), MWM (Zhao–Brazauskas–Ghorai 2018a) and
its small-sample log-location-scale study (2018b), Poudyal–Zhao–Brazauskas (2024) for
truncated/censored lognormal — trim or Winsorize **moments**. QLS trims the **quantile
grid** instead, and that is what lets it handle log-Cauchy at all: a moment-based
estimator has nothing to trim when no moment exists. Study 02 measured MTM against QLS
directly and found them comparable under contamination (20.3% vs 22.7% premium error at
ε = 5%); this study can say something MTM structurally cannot.

**Where it sits against the trend.** Robust statistics is not fashionable, and the
tabular-ML doctrine Klein carries elsewhere (Grinsztajn: trees still win) has nothing to
say at n = 30 — there is no signal to learn, only a distribution to estimate. The right
frame is the opposite one: **when data is this scarce, the estimator's failure modes are
the entire game**, because you will never have enough observations to average them away.
That is also why the study's second track is a *decision* and not a fit statistic.

**The honest gap this study fills.** The thesis's own §7.2 (Future Work) names extending
the estimators to risk measures as an open direction, and §6.2.2 stops at parameters and
p-values — it never converts a fitted hurricane law into a return level. Every published
number in Tables 6.9/6.10 is a parameter. **No published work carries these fits through
to the 1-in-100 event loss, and none runs a leave-top-k-out stress on this sample.** RQ4,
RQ5 and RQ6 are therefore genuinely open, not re-derivations — and the
`tan(0.49π) = 31.82` amplification means the answer could easily be that the thesis's
best-fitting family is the worst one to price with.
