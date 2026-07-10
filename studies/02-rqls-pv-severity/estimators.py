"""estimators.py — severity estimators for the RQLS study (lognormal + gamma).

Four estimators, each returning a :class:`Fit` (fitted params + implied layer functionals
+ risk-loaded premium under a deductible/limit product):

  * :func:`mle_full`               — the NAIVE full-sample MLE (ignores truncation/
                                     censoring; the estimator every actuary reaches for).
  * :func:`mle_truncated_censored` — the PROPER conditional-likelihood MLE that corrects
                                     for the deductible (left truncation) and limit (right
                                     censoring) via scipy.optimize.
  * :func:`qls`                    — Quantile Least Squares on the OBSERVABLE window with
                                     conditional empirical quantiles; robustness by
                                     restricting/trimming the p-grid.
  * :func:`mtm`                    — Method of Trimmed Moments (Brazauskas-Jones-Zitikis).

Scoring is uniform: :func:`premium_error_pct` gives the absolute risk-loaded premium
error % vs a known truth — study 02's single primary metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import scipy.stats as st
from scipy.optimize import least_squares, minimize

from generator import PREMIUM_LOADING, layer_functionals

_FAMILIES = ("lognormal", "gamma")


# --- fitted-model container --------------------------------------------------
@dataclass
class Fit:
    """A fitted severity law; knows how to price a (d, u) layer."""

    family: str
    params: dict  # lognormal: {'mu','sigma'}; gamma: {'k','theta'}

    def dist(self):
        if self.family == "lognormal":
            return st.lognorm(s=self.params["sigma"], scale=np.exp(self.params["mu"]))
        if self.family == "gamma":
            return st.gamma(a=self.params["k"], scale=self.params["theta"])
        raise ValueError(f"unknown family {self.family!r}")

    def functionals(self, d: float, u: float, loading: float = PREMIUM_LOADING) -> dict:
        dist = self.dist()
        return layer_functionals(dist.sf, dist.ppf, d, u, loading)

    def premium(self, d: float, u: float, loading: float = PREMIUM_LOADING) -> float:
        return self.functionals(d, u, loading)["premium"]


def _frozen(family: str, theta: np.ndarray):
    """(unconstrained theta) -> frozen scipy dist. lognormal:(mu,log_sig); gamma:(log_k,log_th)."""
    if family == "lognormal":
        return st.lognorm(s=np.exp(theta[1]), scale=np.exp(theta[0]))
    return st.gamma(a=np.exp(theta[0]), scale=np.exp(theta[1]))


def _params(family: str, theta: np.ndarray) -> dict:
    if family == "lognormal":
        return {"mu": float(theta[0]), "sigma": float(np.exp(theta[1]))}
    return {"k": float(np.exp(theta[0])), "theta": float(np.exp(theta[1]))}


def _theta0(family: str, x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, float)
    x = x[x > 0]
    if family == "lognormal":
        z = np.log(x)
        return np.array([z.mean(), np.log(z.std(ddof=0) + 1e-9)])
    m, v = x.mean(), x.var(ddof=0) + 1e-9
    k = m * m / v  # method-of-moments start
    return np.array([np.log(max(k, 1e-2)), np.log(max(v / m, 1e-6))])


# --- 1. naive full-sample MLE ------------------------------------------------
def mle_full(x: Sequence[float], family: str = "lognormal") -> Fit:
    """Full-sample MLE that IGNORES truncation/censoring (the naive baseline)."""
    x = np.asarray(x, float)
    x = x[x > 0]
    if family == "lognormal":
        z = np.log(x)
        return Fit("lognormal", {"mu": float(z.mean()), "sigma": float(z.std(ddof=0))})
    if family == "gamma":
        k, _loc, theta = st.gamma.fit(x, floc=0.0)
        return Fit("gamma", {"k": float(k), "theta": float(theta)})
    raise ValueError(f"unknown family {family!r}")


# --- 2. proper truncated + censored MLE --------------------------------------
def mle_truncated_censored(
    x: Sequence[float],
    d: float,
    u: float,
    censored: Sequence[bool] | None = None,
    family: str = "lognormal",
) -> Fit:
    """Conditional-likelihood MLE correcting for a deductible (left trunc) + limit (cens).

    Uncensored obs contribute f(x)/S(d) (data are conditioned on X>d); censored obs
    (flagged, recorded at u) contribute S(u)/S(d). Recorded values <= d — which can only
    arise from contamination — are dropped as unobservable under the truncated model.
    """
    x = np.asarray(x, float)
    cens = np.zeros(len(x), bool) if censored is None else np.asarray(censored, bool)
    unc = x[(~cens) & (x > d) & (x < u)]
    n_cens = int(cens.sum())

    def nll(theta: np.ndarray) -> float:
        dist = _frozen(family, theta)
        log_sd = np.log(dist.sf(d)) if d > 0 else 0.0
        ll = float(np.sum(dist.logpdf(unc))) - len(unc) * log_sd
        if n_cens:
            ll += n_cens * (float(np.log(max(dist.sf(u), 1e-300))) - log_sd)
        return -ll

    res = minimize(nll, _theta0(family, unc), method="Nelder-Mead",
                   options={"xatol": 1e-6, "fatol": 1e-8, "maxiter": 4000})
    return Fit(family, _params(family, res.x))


# --- 3. Quantile Least Squares (observable window) ---------------------------
def default_p_grid(trim: float = 0.0, n: int = 19) -> np.ndarray:
    """A probability grid on the observable window; ``trim`` drops each tail for robustness."""
    return np.linspace(trim if trim > 0 else 0.05, 1.0 - (trim if trim > 0 else 0.05), n)


def qls(
    x: Sequence[float],
    d: float,
    u: float,
    p_grid: Sequence[float],
    family: str = "lognormal",
    weights: str = "ols",
    censored: Sequence[bool] | None = None,
) -> Fit:
    """Quantile Least Squares on the observable window (d, u).

    Matches empirical conditional quantiles q̂(p) to the family's theoretical conditional
    quantiles Q_cond(p; θ) = Q(F(d) + p*(F(u)-F(d))) over the KNOWN window — so the fit
    stays consistent under truncation/censoring. Robustness comes from choosing/trimming
    ``p_grid`` (drop the tails where gross errors and unit-typos land). For lognormal it is
    OLS/GLS of the log-quantiles on standard-normal quantiles (closed form when the window
    is the whole line); ``weights='gls'`` uses inverse-variance weights from the asymptotic
    covariance of sample quantiles Σ_ij = p_i(1-p_j)/(f(Q_i)f(Q_j)n), i<=j (diagonal form).
    """
    x = np.asarray(x, float)
    cens = np.zeros(len(x), bool) if censored is None else np.asarray(censored, bool)
    obs = x[(~cens) & (x > d) & (x < u)]
    p = np.asarray(p_grid, float)
    n = len(obs)

    if family == "lognormal":
        z = np.log(obs)
        a = -np.inf if d <= 0 else np.log(d)
        b = np.inf if not np.isfinite(u) else np.log(u)
        qhat = np.quantile(z, p)
        full_line = (not np.isfinite(a)) and (not np.isfinite(b))

        if full_line and weights == "ols":  # closed-form linear regression (the QLS core)
            zp = st.norm.ppf(p)
            slope, intercept = np.polyfit(zp, qhat, 1)
            return Fit("lognormal", {"mu": float(intercept), "sigma": float(abs(slope))})

        def cond_q(mu: float, sigma: float) -> np.ndarray:
            lo = 0.0 if not np.isfinite(a) else st.norm.cdf((a - mu) / sigma)
            hi = 1.0 if not np.isfinite(b) else st.norm.cdf((b - mu) / sigma)
            return mu + sigma * st.norm.ppf(lo + p * (hi - lo))

        w = np.ones_like(p)
        if weights == "gls":
            mu0, s0 = float(z.mean()), float(z.std(ddof=0))
            q0 = mu0 + s0 * st.norm.ppf(np.clip(p, 1e-4, 1 - 1e-4))
            dens = st.norm.pdf((q0 - mu0) / s0) / s0
            w = dens ** 2 * n / (p * (1.0 - p))
        sw = np.sqrt(w)

        def resid(theta: np.ndarray) -> np.ndarray:
            return sw * (qhat - cond_q(theta[0], np.exp(theta[1])))

        sol = least_squares(resid, [float(z.mean()), np.log(z.std(ddof=0) + 1e-9)])
        return Fit("lognormal", {"mu": float(sol.x[0]), "sigma": float(np.exp(sol.x[1]))})

    if family == "gamma":  # gamma is not location-scale: raw-scale conditional-quantile LS
        qhat = np.quantile(obs, p)

        def resid(theta: np.ndarray) -> np.ndarray:
            dist = _frozen("gamma", theta)
            lo = dist.cdf(d) if d > 0 else 0.0
            hi = dist.cdf(u) if np.isfinite(u) else 1.0
            return qhat - dist.ppf(lo + p * (hi - lo))

        sol = least_squares(resid, _theta0("gamma", obs))
        return Fit("gamma", _params("gamma", sol.x))
    raise ValueError(f"unknown family {family!r}")


# --- 4. Method of Trimmed Moments --------------------------------------------
def mtm(x: Sequence[float], trim: float = 0.1, family: str = "lognormal") -> Fit:
    """Method of Trimmed Moments: symmetric ``trim`` each tail, match trimmed moments.

    Lognormal (log-space, closed form): μ̂ = trimmed mean of log x; σ̂ = sqrt(trimmed
    variance / c(trim)), c(trim) the variance of a standard normal truncated to
    (Φ⁻¹(trim), Φ⁻¹(1-trim)). Gamma: numerically match trimmed mean+variance to the
    family's truncated moments. Trimming buys robustness to contamination on clean data.
    """
    x = np.asarray(x, float)
    x = x[x > 0]
    if family == "lognormal":
        z = np.sort(np.log(x))
        lo = int(np.floor(len(z) * trim))
        ztr = z[lo: len(z) - lo] if lo > 0 else z
        zc = st.norm.ppf(1.0 - trim)
        c = 1.0 - 2.0 * zc * st.norm.pdf(zc) / (1.0 - 2.0 * trim) if trim > 0 else 1.0
        return Fit("lognormal", {"mu": float(ztr.mean()), "sigma": float(np.sqrt(ztr.var(ddof=0) / c))})

    if family == "gamma":
        xs = np.sort(x)
        lo = int(np.floor(len(xs) * trim))
        xtr = xs[lo: len(xs) - lo] if lo > 0 else xs
        m_hat, v_hat = float(xtr.mean()), float(xtr.var(ddof=0))
        alpha = np.array([trim, 1.0 - trim])

        def trunc_moments(theta):
            dist = _frozen("gamma", theta)
            qa, qb = dist.ppf(alpha[0]) if trim > 0 else 0.0, dist.ppf(alpha[1]) if trim > 0 else dist.ppf(1 - 1e-9)
            grid = np.linspace(1e-4, 1 - 1e-4, 400)
            vals = dist.ppf(grid)
            keep = (vals >= qa) & (vals <= qb)
            vv = vals[keep]
            return vv.mean(), vv.var()

        def resid(theta):
            m, v = trunc_moments(theta)
            return [m - m_hat, np.sqrt(v) - np.sqrt(v_hat)]

        sol = least_squares(resid, _theta0("gamma", xtr))
        return Fit("gamma", _params("gamma", sol.x))
    raise ValueError(f"unknown family {family!r}")


# --- uniform scoring ---------------------------------------------------------
def premium_error_pct(fitted_premium: float, truth_premium: float) -> float:
    """Absolute risk-loaded premium error %, study 02's single primary metric (lower=better)."""
    return float(abs(fitted_premium - truth_premium) / truth_premium * 100.0)
