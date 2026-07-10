---
type: method-card
domain: insurance
status: complete
concepts: [quantile-least-squares, robust-estimation, method-of-trimmed-moments, truncation, censoring, severity-modeling, tail-risk]
related: [robust-severity, loss-models, generalized-pareto, VaR-TVaR]
refs_verified: true   # every reference below verified via WebFetch/WebSearch (2026-07-10)
---

# Method card — Robust Quantile Least Squares (QLS) for loss severity

> Gate 2 (METHOD). Pedagogy for a frontier robust estimator, written BEFORE the ladder
> runs. Protocol: `.claude/skills/klein/references/method-gate-protocol.md`. The five
> parts are an authoring arc — read them in order.

## 1. Intuition (for a practitioner)

**You already do a special case of QLS.** When an actuary eyeballs a loss table and says
"the median claim is about $8k and the 95th percentile is about $100k, so a lognormal with
these two percentiles fits" — that is *percentile matching*: pick the parameters that make
the model's quantiles line up with the data's quantiles. **Quantile Least Squares (QLS)
is percentile matching grown up.** Instead of matching two hand-picked percentiles exactly,
it matches a whole *grid* of percentiles in a least-squares sense — fit the parameters so
the model quantile curve passes as close as possible to the empirical quantiles across the
grid. It is, almost literally, *ordinary least squares run on the quantile scale* rather
than on the mean.

Why an actuary should care, in three moves that map to how real loss data is broken:

- **One bad record moves the MLE's premium; it barely moves a quantile you can see.** The
  maximum-likelihood fit is a weighted average over *every* data point, so a single
  fat-fingered "$5,000,000" (a units typo, a duplicated claim, a reserve mistaken for a
  payment) drags the fitted σ — and therefore the tail, the TVaR, and the premium — with
  it. An empirical quantile in the *middle* of the data does not budge when the largest
  point gets larger. QLS fits to the quantiles you can actually trust and **ignores the
  extremes by simply not putting grid points there.**

- **A deductible is a left-truncation; a limit is a right-censoring.** Below-deductible
  losses are never filed, so you never see them — the data is *truncated*, not merely
  missing. Losses above the policy limit are recorded *at* the limit — *censored*. Both
  distort a naive fit. QLS handles them by fitting only on the **observable window** and
  using the fact that the deductible and limit are *known numbers*.

- **Data errors are contamination.** Real severity data is a clean model *plus* a small
  fraction of gross errors. QLS is designed to have a *bounded* response to that fraction;
  the MLE is not.

The trade you are making: on *perfectly clean, complete* data the MLE is the most
efficient estimator there is, and QLS gives up a little efficiency for nothing in return.
The moment the data is contaminated or incomplete — which is *always*, for real loss data —
that small insurance premium buys you an estimator that does not blow up. This study
measures both sides of that trade in dollars of premium error.

## 2. Math core

### Notation

| Symbol | Meaning |
|---|---|
| $X$ | ground-up loss (severity), density $f$, CDF $F$, survival $S=1-F$ |
| $Q(p)=F^{-1}(p)$ | quantile function of the loss |
| $\hat Q(p)$ | empirical $p$-quantile of the sample |
| $\theta$ | parameters to estimate (lognormal $(\mu,\sigma)$; gamma $(k,\theta_s)$) |
| $Q_\theta(p)$ | model quantile function under $\theta$ |
| $z_p=\Phi^{-1}(p)$ | standard-normal quantile (the "standard member" for lognormal-via-log) |
| $\{p_i\}$ | the probability grid QLS fits on |
| $w_i$ | grid weights (OLS: $w_i\equiv1$; GLS: from the quantile covariance) |
| $d,\;u$ | deductible (left-truncation) and limit (right-censoring) |
| $Y=(\min(X,u)-d)_+$ | per-policy layer payout — what the premium is built on |
| $\varepsilon$ | contamination fraction |

### The objective

QLS estimates $\theta$ by weighted least squares **on the quantile scale**:

$$ \hat\theta \;=\; \arg\min_{\theta}\ \sum_i w_i\,\bigl(\hat Q(p_i) - Q_\theta(p_i)\bigr)^2 . $$

### Closed form for location–scale families

A lognormal is location–scale *in log space*: with $Z=\log X\sim\mathcal N(\mu,\sigma)$,
the quantile is **linear** in the standard-normal quantile,

$$ Q_Z(p) \;=\; \mu + \sigma\,z_p, \qquad z_p=\Phi^{-1}(p). $$

So QLS on the log-losses is *ordinary linear regression of the empirical log-quantiles on
$z_p$*: regress $\hat Q_Z(p_i)$ on $z_{p_i}$ — the **slope is $\hat\sigma$, the intercept
is $\hat\mu$** (a weighted regression when $w_i\neq1$). That is the whole estimator on clean,
complete data — no likelihood, no iteration.

### GLS weights (efficiency)

The efficient weights come from the **joint asymptotic covariance of sample quantiles**
(Adjieteh & Brazauskas 2025). For $p_i\le p_j$,

$$ \Sigma_{ij} \;=\; \frac{p_i\,(1-p_j)}{f\!\bigl(Q(p_i)\bigr)\,f\!\bigl(Q(p_j)\bigr)\,n}, $$

and the generalized-least-squares fit solves
$\min_\theta (\hat Q-Q_\theta)^{\!\top}\Sigma^{-1}(\hat Q-Q_\theta)$. Plugging in $f,Q$ from
a first-stage OLS fit gives feasible GLS. (This card's implementation uses the stable
inverse-variance — diagonal — form $w_i = f(Q_i)^2\,n/[p_i(1-p_i)]$; the full off-diagonal
$\Sigma^{-1}$ is the efficiency ceiling but is prone to ill-conditioning on fine grids.)

### Robustness — restrict / trim the $p$-grid

Because each grid point is a *middle* order statistic, dropping the extreme $p_i$ makes the
estimator **ignore the tails where gross errors live**. Gross over-reports inflate the top
quantiles; unit-typos deflate the bottom. A symmetric trim (e.g. keep $p\in[0.15,0.85]$)
gives a *bounded-influence* fit: the breakdown point is controlled by how much of the grid
you trim. This is robustness by *construction*, not by down-weighting.

### Incompleteness — fit on the observable window $[F(d),F(u)]$

Under a deductible $d$ and limit $u$, you observe $X\mid d<X<u$. The empirical quantiles of
that sample estimate the **conditional** (truncated) quantiles, not the unconditional ones.
Because $d,u$ are *known*, the conditional model quantile is written exactly (lognormal, in
log space, $a=\log d,\ b=\log u$):

$$ Q^{\text{cond}}_\theta(p) \;=\; \mu + \sigma\,\Phi^{-1}\!\Bigl(\Phi\!\bigl(\tfrac{a-\mu}{\sigma}\bigr) + p\,\bigl[\Phi\!\bigl(\tfrac{b-\mu}{\sigma}\bigr)-\Phi\!\bigl(\tfrac{a-\mu}{\sigma}\bigr)\bigr]\Bigr). $$

Fitting $\hat Q(p_i)\approx Q^{\text{cond}}_\theta(p_i)$ over the window **identifies
$(\mu,\sigma)$ from the middle alone** — the known truncation points do the rest. As
$d\to0,\ u\to\infty$ this collapses back to $\mu+\sigma z_p$. This is exactly what lets
window-QLS recover the truth where a naive full-sample MLE (which pretends the truncated
data is complete) is biased.

### From parameters to the decision — the premium

The premium is priced on the layer payout $Y=(\min(X,u)-d)_+$. Truth and every fitted model
are scored through the **same** functionals, computed by 1-D integration of the survival
function (finite interval $\Rightarrow$ finite even under a heavy tail):

$$ \mathbb E[Y]=\!\int_d^u\! S(x)\,dx,\quad
\text{VaR}_p(Y)=\min(Q(p),u)-d,\quad
\text{TVaR}_p(Y)=\text{VaR}_p+\frac{1}{1-p}\!\int_{d+\text{VaR}_p}^{u}\!\! S(x)\,dx. $$

**Premium loading convention (used everywhere in this study):**

$$ \boxed{\ \text{premium} \;=\; \mathbb E[Y] \;+\; 0.10\,\bigl(\text{TVaR}_{99}(Y)-\mathbb E[Y]\bigr)\ } $$

— the expected layer payout plus a **10% load on the TVaR99 risk margin above the mean**.
The single primary metric is `premium_error_pct` $= |\text{premium}_{\text{fit}} -
\text{premium}_{\text{truth}}|/\text{premium}_{\text{truth}}\times100$.

## 2b. The MTM cousin — Method of Trimmed Moments

QLS's older sibling (Brazauskas, Jones & Zitikis 2009) trims *moments* instead of a
*quantile grid*. Trim a fraction $\alpha$ from each tail of the sample, compute the trimmed
sample moments, and match them to the family's theoretical trimmed moments. For a lognormal
in log space this is a **closed form**:

$$ \hat\mu = \text{trimmed mean}(\log x),\qquad
\hat\sigma = \sqrt{\dfrac{\text{trimmed variance}(\log x)}{c(\alpha)}}, $$

where $c(\alpha)=1-\dfrac{2\,z^\star\phi(z^\star)}{1-2\alpha}$ is the variance of a standard
normal truncated to $(\!-z^\star,z^\star)$, $z^\star=\Phi^{-1}(1-\alpha)$. MTM and QLS are
cousins: both throw away the tails to bound influence; QLS works on the quantile scale
(and, via the window trick, handles truncation/censoring cleanly), MTM on the moment scale.

## 3. Minimal from-scratch implementation plan

The smallest honest version is a handful of `numpy`/`scipy` lines — no framework magic
(realized in `estimators.py`; the E1 gate driver is `train.py`, scored by
`kleinlib.eval.evaluate_scalar`):

```
# QLS for lognormal on the observable window (OLS)
obs = x[(x > d) & (x < u)]                 # observable-window points
z   = np.log(obs)
qhat = np.quantile(z, p_grid)              # empirical conditional quantiles
if d <= 0 and u == inf:                    # complete data: the closed form
    slope, intercept = np.polyfit(norm.ppf(p_grid), qhat, 1)
    mu, sigma = intercept, abs(slope)
else:                                      # windowed: match conditional quantiles
    def cond_q(mu, s):
        lo, hi = norm.cdf((log(d)-mu)/s), norm.cdf((log(u)-mu)/s)
        return mu + s*norm.ppf(lo + p_grid*(hi-lo))
    mu, sigma = least_squares(lambda th: sqrt(w)*(qhat - cond_q(th[0], exp(th[1]))), x0).x
# robustness: choose p_grid to TRIM the tails (e.g. linspace(0.15, 0.85, 16))
# GLS: w_i = pdf(Q_i)**2 * n / (p_i*(1-p_i)) from a first-stage OLS fit
```

Baselines it is measured against, same file: `mle_full` (naive full-sample MLE — the
estimator every actuary reaches for), `mle_truncated_censored` (the proper conditional
likelihood via `scipy.optimize.minimize`), and `mtm` (the trimmed-moments cousin). Each
returns fitted params **and** the implied layer functionals + premium, so scoring is one
call to `premium_error_pct(fit.premium(d,u), truth["premium"])`.

## 4. When it pays / when it doesn't

Keyed on the two ways real loss data is broken — contamination and incompleteness:

| Regime | Data condition | Verdict |
|---|---|---|
| Clean & complete, large $n$ | $\varepsilon=0$, no $d/u$ | **MLE wins** — QLS ~85–95% as efficient; robustness costs a little for nothing gained |
| Contaminated | $\varepsilon>0$ (gross errors / typos) | **QLS / MTM pay big** — MLE's premium diverges; trimmed grid/moments stay bounded |
| Incomplete | deductible + limit | **window-QLS / truncated-MLE pay** — naive full-sample MLE is biased; the window fit recovers truth |
| Heavy-tailed | GPD tail ($\xi$ near 1) | **tail-aware needed** — tail-blind fits underprice TVaR99 and the premium; QLS's mid-quantile fit must be paired with an explicit tail |
| Tiny $n$ | few claims | neither is magic — sampling noise dominates; report the floor (E1 shows ~4% premium error even for the *unbiased* MLE at $n=2000$) |

Doctrine (Adjieteh & Brazauskas 2025; Poudyal & Brazauskas 2022): robustness is an
*insurance* purchase — you pay a small, known efficiency premium on clean data to cap a
large, unknown loss when the data misbehaves. For a quantity as tail-sensitive as a
TVaR-loaded premium, that cap is the difference between a fileable rate and a blown one.

**Falsifiable priors this study will test** (mirrored to `study.yaml:predictions_to_falsify`):

1. **RQ1 (efficiency cost).** At $\varepsilon=0$, QLS premium error $\approx1.05$–$1.18\times$
   MLE (relative efficiency 85–95%); QLS is *slightly worse* on clean data.
2. **RQ2 (breakdown).** As $\varepsilon$ grows, the naive MLE's premium error diverges
   (`>50%` by $\varepsilon=5\%$) while QLS/MTM stay bounded (`<25%`).
3. **RQ3 (incompleteness).** Under $d=\$5\text{k}$ + $u=\$2\text{M}$, naive MLE-full is
   materially biased (premium error `>20%`); window-QLS and the truncated/censored MLE
   recover truth (`<5%`).
4. **RQ4 (propagation).** Estimator error is amplified by TVaR99 and the premium; an
   ignored GPD fire tail underprices TVaR99 → premium error `>10%`.

## 5. Verified references

Every row verified on 2026-07-10 via WebFetch of the arXiv abstract page and/or the
publisher, confirming title, authors, venue, and identifier.

| Reference | Where | Verified? |
|---|---|---|
| Adjieteh, M. & Brazauskas, V. (2025). *Quantile Least Squares: A Flexible Approach for Robust Estimation and Validation of Location-Scale Families.* | Statistics and Computing **35**, Art. 106 (2025); DOI 10.1007/s11222-025-10626-6; arXiv:2402.07837 | ✅ (title, authors, venue, DOI, arXiv all confirmed) |
| Poudyal, C. & Brazauskas, V. (2022). *Robust Estimation of Loss Models for Truncated and Censored Severity Data.* | Variance **15**(2) (2022); arXiv:2202.13000 | ✅ (title, authors, arXiv confirmed; venue Variance 15(2) confirmed via variancejournal.org) |
| Brazauskas, V., Jones, B. & Zitikis, R. (2009). *Robust fitting of claim severity distributions and the method of trimmed moments.* | Journal of Statistical Planning and Inference **139**(6), 2028–2043 | ✅ (title, authors, venue, volume/pages confirmed) |
| Poudyal, C. (2021). *Robust Estimation of Loss Models for Lognormal Insurance Payment Severity Data.* | ASTIN Bulletin **51**(2) (2021); DOI 10.1017/asb.2021.4; arXiv:2103.02089 | ✅ (title, author, venue, DOI, arXiv all confirmed) |

The QLS estimator, the joint asymptotic normality of sample quantiles, and the OLS/GLS
weighting come from **Adjieteh & Brazauskas 2025**. The truncation/censoring/scaling
framework and the T-/W-estimator robustness results come from **Poudyal & Brazauskas 2022**
and **Poudyal 2021** (lognormal payment severity). The **method of trimmed moments** is
**Brazauskas, Jones & Zitikis 2009**.

## Mandatory honesty note

**No published paper applies QLS to photovoltaic (PV) risk — the PV bridge is this study's
original construction.** The QLS / MTM / truncated-MLE methods and their asymptotics are
from the peer-reviewed severity-modeling literature above; grafting them onto a PV
loss-severity generator (peril mix, hail concentration, fire GPD tail) is our own synthetic
lab, built to make the estimators' behavior *visible against a known truth*. The PV
loss-concentration figures that motivate the peril mix (a small share of hail claims
driving a large share of dollars) are **industry-reported (pv-magazine, 2025) and are used
as market context only** — not as validated model parameters. The generator's numbers are
chosen to be *illustrative and plausible*, not fitted to any PV book.
