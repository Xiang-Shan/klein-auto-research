---
title: "Robust Quantile Least Squares for Loss Severity"
type: method-card
domain: insurance
status: validated
source: studies/02-rqls-pv-severity
concepts: [quantile-least-squares, method-of-trimmed-moments, left-truncation-right-censoring, observable-window-fit, gls-quantile-weights, layer-map-cancellation, mixture-misspecification, cap-bounded-tail, monte-carlo-floor, tvar-loaded-premium]
related: [glm-pricing.md, gbdt-tabular.md, dae-tabular.md]
---

# Robust Quantile Least Squares for Loss Severity

*Validated card distilled from `studies/02-rqls-pv-severity` (7-experiment known-truth
synthetic lab — a PV loss-severity generator whose exact layer premium is known, so every
estimator is scored in dollars of premium error against ground truth; full trail in that
study's `method_card.md`, `findings.md`, `results.tsv`, and the two sweep sidecars). The
methods (QLS / MTM / truncated-censored MLE) are from the peer-reviewed severity literature;
the PV bridge is the study's own construction.*

## 1. Practitioner intuition

**QLS is percentile matching grown up.** When you say "median ≈ $8k, 95th ≈ $100k, so a
lognormal fits," you match two percentiles. QLS fits the parameters so the model quantile
*curve* passes closest (least squares) to a whole *grid* of empirical quantiles — OLS run
on the quantile scale, not the mean.

**Why an actuary cares — the three ways loss data breaks.** (i) One bad record moves the
MLE's premium (a weighted average over every point) but barely moves a middle quantile — so
QLS fits the quantiles you trust and ignores extremes by not placing grid points there.
(ii) A deductible is a **left-truncation**, a limit a **right-censoring**; QLS fits only the
**observable window** using the *known* d, u. (iii) Data errors are contamination, to which
QLS has a *bounded* response and the MLE does not.

**The trade:** on perfectly clean, complete data the MLE is most efficient and QLS gives up
a little for nothing; the moment data is contaminated or incomplete — always, for real loss
data — that small premium buys an estimator that does not blow up. **MTM** (Brazauskas–
Jones–Zitikis) is the cousin: trim *moments* instead of a quantile grid.

## 2. Math core

- Objective: `θ̂ = argmin Σ wᵢ (Q̂(pᵢ) − Q_θ(pᵢ))²` — weighted LS on the quantile scale.
- **Closed form (location-scale).** Lognormal is location-scale in log space:
  `Q_Z(p) = μ + σ·z_p`, `z_p = Φ⁻¹(p)`. So QLS on log-losses is OLS of the empirical
  log-quantiles on `z_p`: **slope = σ̂, intercept = μ̂**. No likelihood, no iteration.
- **Observable window.** Under d, u you see the *conditional* quantiles; because d, u are
  known, write them exactly: `Q_cond(p;θ) = μ + σ·Φ⁻¹(Φ((a−μ)/σ) + p·[Φ((b−μ)/σ) − Φ((a−μ)/σ)])`,
  `a=log d, b=log u`. Fitting over the window identifies (μ,σ) from the middle alone; as
  `d→0, u→∞` it collapses to `μ+σ·z_p`.
- **GLS weights** from the joint covariance of sample quantiles:
  `Σᵢⱼ = pᵢ(1−pⱼ)/(f(Qᵢ)f(Qⱼ)n)`. Diagonal inverse-variance form `wᵢ = f(Qᵢ)²n/(pᵢ(1−pᵢ))`.
- **Robustness:** trim the grid (keep `p∈[0.15,0.85]`) → bounded influence by construction.
- **Premium (the decision functional).** Layer `Y=(min(X,u)−d)₊`, priced by 1-D
  integration of the survival function: `E[Y]=∫_d^u S`, `VaR_p=min(Q(p),u)−d`,
  `TVaR_p=VaR_p + (1/(1−p))∫ S`, `premium = E[Y] + 0.10·(TVaR₉₉ − E[Y])`. Truth and every
  fit are scored through the SAME routine.

## 3. Minimal implementation sketch

```text
obs = x[(~censored) & (x > d) & (x < u)]     # the observable window IS the robustifier
z, qhat = log(obs), quantile(log(obs), p_grid)
if complete data and weights=="ols":         # the QLS core — 3 lines
    slope, intercept = polyfit(norm.ppf(p_grid), qhat, 1);  mu, sigma = intercept, abs(slope)
else:                                        # windowed: match CONDITIONAL quantiles
    cond_q(mu,s) = mu + s*norm.ppf(F(d) + p_grid*(F(u)-F(d)))
    mu, sigma = least_squares(sqrt(w)*(qhat - cond_q(...))).x
# robustness   : trim p_grid to [0.15,0.85]  (drop tails where gross errors land)
# GLS (skip it): w = pdf(Q)**2 * n / (p*(1-p))  from a first-stage OLS fit
```

Baselines it is measured against (same `estimators.py`): `mle_full` (the naive full-sample
MLE), `mle_truncated_censored` (proper conditional likelihood: uncensored `f/S(d)`, censored
`S(u)/S(d)`, via Nelder-Mead), `mtm` (trimmed moments). Score with one call:
`premium_error_pct(fit.premium(d,u), truth_premium)`.

## 4. When it pays / when it doesn't

**Observed (study 02, PV loss-severity known-truth lab — the validated numbers). The MC
floor at n=2,000 is ≈ 4.28% premium error even for a perfect estimator; read everything
against it, never against 0.**

| Regime | Result | Verdict |
|---|---|---|
| **Efficiency, clean (ε=0)** | QLS-OLS **1.083×** the MLE (rel. eff 0.846 premium / 0.805 σ̂); GLS **1.123×** (worse); MTM 1.219× | E2: robustness costs ~8% more premium error on clean data — a small, real insurance premium |
| **Breakdown (contamination)** | MLE **4.21→352.19%** over ε 0→10%; trimmed-QLS **5.42→49.97%**. At ε=5%: MLE 136.6% vs QLS 20.3% / MTM 22.7% | E3: **QLS/MTM pay big** — one bad record in 100 (ε=1%) already puts the MLE at 5× the floor |
| **Incomplete (d=$5k trunc + u=$2M cens)** | window-QLS **4.83%** ≈ floor, trunc-MLE 4.68% recover; naive-MLE param bias +0.596/−0.347 (theory-exact) yet premium only **−5.2%** | E4: recovery **pays**; but param bias ≠ pricing bias — the biases cancel in the layer map ("wrong parameters, nearly right layer") |
| **Window ≫ trim** | window-only **8.90%** ≫ window+trim 18.78% ≫ naive-QLS 23.74% ≫ trim-only **35.90%** | E5: the **observable window is the principled robustifier**; blind trimming deletes real hail-tail signal |
| **Heavy tail under a policy cap** | the $2M limit bounds the whole GPD ξ=0.4 tail to **+0.174%** of premium; POT tail-aware is *worse* (ξ̂ 0.217 vs 0.4, +1.86pp premium) | E6: a cap is itself tail protection — **quantify it before buying tail machinery**; noisy POT can hurt |

**The cancellation caveat (E7 decision grid — carry it into any filing).** On a *misspecified*
single-family fit of a peril mixture, EVERY estimator underprices by 23–42% at ε=0 (pure
mixture-misspecification bias); contamination biases *up*, so as ε rises the two errors
**cancel**. No cell reaches the MC floor by skill — every low-|error| cell is
misspecification-undercharge meeting contamination-overcharge (naive MLE: −33.9% at ε=0 →
+188.9% at ε=10, crossing near-zero at ε≈2%). **The structural fix is modeling the mixture
(per-peril fits), not choosing among single-family estimators.**

**When it pays:** contaminated severity data (gross errors / unit typos); incomplete data
(deductible + limit) via the window fit; any setting where you must bound the influence of a
few bad records on a tail-sensitive (TVaR-loaded) premium. **When it doesn't:** clean,
complete, correctly-specified data (the MLE wins, QLS costs ~8%); a *misspecified* family
(no robust estimator rescues the wrong model — fix the family first); tiny n (sampling noise
dominates — report the floor). **Skip the diagonal plug-in GLS** — it added noise, not
efficiency; use OLS, or full-covariance GLS only on a coarse, stably-invertible grid.

## 5. References

All verified during the study's METHOD gate (`studies/02-rqls-pv-severity/method_card.md` §5,
2026-07-10):

- Adjieteh, M. & Brazauskas, V. (2025). *Quantile Least Squares: A Flexible Approach for
  Robust Estimation and Validation of Location-Scale Families.* Statistics and Computing
  **35**, Art. 106 — DOI 10.1007/s11222-025-10626-6; arXiv:2402.07837. The QLS estimator +
  OLS/GLS quantile weighting.
- Poudyal, C. & Brazauskas, V. (2022). *Robust Estimation of Loss Models for Truncated and
  Censored Severity Data.* Variance **15**(2) — arXiv:2202.13000. The truncation/censoring
  framework.
- Brazauskas, V., Jones, B. & Zitikis, R. (2009). *Robust fitting of claim severity
  distributions and the method of trimmed moments.* JSPI **139**(6), 2028–2043. The MTM
  cousin.
- Poudyal, C. (2021). *Robust Estimation of Loss Models for Lognormal Insurance Payment
  Severity Data.* ASTIN Bulletin **51**(2) — DOI 10.1017/asb.2021.4; arXiv:2103.02089.
- `studies/02-rqls-pv-severity/{findings.md, results.tsv, aux_metrics.tsv, sweeps/*.sidecar.tsv}`
  — the observed table above, experiment-by-experiment.

*Honesty note (from the study method card): no published paper applies QLS to photovoltaic
risk — the PV bridge is the study's original synthetic-lab construction; the PV
loss-concentration figures are industry-reported market context (pv-magazine 2025), not
validated model parameters.*
