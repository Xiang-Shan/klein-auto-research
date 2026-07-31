"""estimators.py — from-scratch quantile least squares for log-location-scale loss models.

A numpy/scipy-only reimplementation of the estimators and goodness-of-fit tests in
Adjieteh (2024), *Robust-Efficient Fitting of Loss Models via Quantile Least Squares*
(PhD thesis, UW-Milwaukee; advisor V. Brazauskas). Equation numbers below are the
thesis's own.

The whole method is **OLS/GLS run on the quantile scale**. For a log-location-scale
family, ``log F^{-1}(u) = mu + sigma * F_*^{-1}(u)`` is *linear* in ``(mu, sigma)``, so
regressing the k empirical log-quantiles on the k standard-member quantiles recovers the
parameters in closed form:

    oQLS (3.4):  beta_hat = (X'X)^{-1} X'Y                    -- ordinary LS
    gQLS (3.6):  beta_hat = (X'S*^{-1}X)^{-1} X'S*^{-1}Y      -- GLS with the KNOWN
                                                                 quantile covariance S*

with ``X = [1, F_*^{-1}(p_i)]`` (3.3), ``Y = (log Fhat^{-1}(p_1), ..., log Fhat^{-1}(p_k))'``
(§3.5), and ``S*`` the standard-member quantile covariance of Serfling's Theorem B (2.1).
Robustness is structural: the grid (3.8) never places a point outside ``[a, b]``, so the
asymptotic breakdown point is ``min{a, 1-b} > 0`` (2.4) and the influence function (2.5)
is bounded.

Contents
--------
``p_grid``            eq. (3.8) equally-spaced quantile levels on ``[a, b]``
``STANDARD_MEMBERS``  the six standard members (thesis Tables 3.1 / 3.4) as (f*, F*^{-1})
``sigma_star``        eq. (2.1) quantile covariance of the standard member
``oqls`` / ``gqls``   eqs. (3.4) / (3.6)
``mle``               maximum likelihood for the same six families
``W`` / ``W_out``     eqs. (5.2) / (5.3) in-sample and out-of-sample GoF statistics
``return_level``      the decision functional: ``exp(mu + sigma * F_*^{-1}(p))`` in dollars

Conventions that are NOT free choices (they change the third digit at n=30)
--------------------------------------------------------------------------
* **Sample-quantile definition.** The thesis *defines* ``Fhat^{-1}(p) = X_(ceil(np))``
  (§2, opening paragraph) -- the inverse-ECDF convention, ``method="inverted_cdf"``,
  exported here as :data:`THESIS_QUANTILE_METHOD`. Its Table 6.8 summary statistics,
  however, reproduce only under **Hazen** plotting positions (MATLAB's ``quantile``
  default), so the two conventions coexist inside one chapter.

  ``method="hazen"`` is this module's DEFAULT, because the study pre-registered a
  quantile-convention sweep and the default must not pre-empt it. But the answer is
  already visible and is recorded here so nobody re-derives it: measured against the
  96 QLS cells of Table 6.10, ``inverted_cdf`` gives mean |deviation| **0.0020**
  (max 0.0052) while ``hazen`` gives **0.0084** (max 0.0318) -- i.e. only the thesis's
  own stated convention lands inside the 0.005 half-digit reporting resolution, and
  ``hazen`` breaches the study's 0.02 ``max_abs_param_deviation`` guardrail. At n=30
  the choice of quantile DEFINITION is a larger error source than anything else in the
  pipeline. That is a finding, not a bug.
* **Quantile space.** The thesis writes ``Y = log Fhat^{-1}(p)`` -- quantile the
  *dollars*, then take logs. Under order-statistic conventions that is identical to
  quantiling the log-dollars (log is monotone); under interpolating conventions
  (hazen/linear) it is not. ``quantile_space="log"`` (default, and what the study's
  prepared column holds) quantiles the log-dollars; ``"dollar"`` is the thesis-literal
  path. Both are exposed for the convention sweep.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import scipy.linalg as sla
import scipy.stats as st
from scipy.optimize import minimize

__all__ = [
    "FAMILIES",
    "THESIS_QUANTILE_METHOD",
    "SUMMARY_QUANTILE_METHOD",
    "StandardMember",
    "STANDARD_MEMBERS",
    "Fit",
    "p_grid",
    "sample_log_quantiles",
    "sigma_star",
    "design_matrix",
    "oqls",
    "gqls",
    "mle",
    "W",
    "W_out",
    "return_level",
    "breakdown_point",
    "mean_loss",
    "cte",
]

#: The six log-location-scale families fitted in thesis §6.2.2 (Tables 6.9 / 6.10).
FAMILIES: tuple[str, ...] = (
    "log-cauchy",
    "log-gumbel",
    "log-laplace",
    "log-logistic",
    "lognormal",
    "pareto1",
)

#: Families whose standard member has NO finite mean -- every moment functional is
#: undefined, so this module refuses to compute one rather than return a number.
_NO_FINITE_MOMENTS: frozenset[str] = frozenset({"log-cauchy"})

#: The convention the thesis DEFINES in §2: ``Fhat^{-1}(p) = X_(ceil(np))``. Reproduces
#: Tables 6.9 / 6.10 to <= 0.0052 across all 96 QLS cells. Flip the study's fitting
#: ``method=`` to this to land inside the reporting resolution.
THESIS_QUANTILE_METHOD = "inverted_cdf"

#: The convention the thesis's DESCRIPTIVE table (6.8) was computed with -- Hazen
#: plotting positions ``(i - 0.5)/n``, MATLAB's ``quantile`` default. Reproduces the
#: published quartiles 4.0560 / 7.6885 / 12.4340 exactly; the estimator tables it does not.
SUMMARY_QUANTILE_METHOD = "hazen"

QuantileMethod = str
QuantileSpace = Literal["log", "dollar"]


# --------------------------------------------------------------------------------------
# Standard members (thesis Table 3.1 for the location-scale members, Table 3.4 for their
# log-location-scale counterparts). Pareto I is the log-location-scale family whose
# standard member is the standard EXPONENTIAL, under the reparametrization
# mu = log(theta), sigma = 1/alpha -- which is why its Q-Q plot is against exponential
# quantiles (thesis Figure 6.8, bottom-right panel).
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class StandardMember:
    """``(f_*, F_*^{-1})`` of a standard (mu=0, sigma=1) location-scale law."""

    name: str
    pdf: Callable[[np.ndarray], np.ndarray]  # f_*(z)
    ppf: Callable[[np.ndarray], np.ndarray]  # F_*^{-1}(u)
    logpdf: Callable[[np.ndarray], np.ndarray]  # log f_*(z)
    #: True when the support is (0, inf) -- mu is the left boundary, not a centre.
    positive_support: bool = False


def _cauchy_pdf(z: np.ndarray) -> np.ndarray:
    return 1.0 / (np.pi * (1.0 + np.asarray(z, float) ** 2))


def _cauchy_logpdf(z: np.ndarray) -> np.ndarray:
    return -np.log(np.pi) - np.log1p(np.asarray(z, float) ** 2)


def _cauchy_ppf(u: np.ndarray) -> np.ndarray:
    return np.tan(np.pi * (np.asarray(u, float) - 0.5))


def _gumbel_pdf(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, float)
    return np.exp(-z - np.exp(-z))


def _gumbel_logpdf(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, float)
    return -z - np.exp(-z)


def _gumbel_ppf(u: np.ndarray) -> np.ndarray:
    return -np.log(-np.log(np.asarray(u, float)))


def _laplace_pdf(z: np.ndarray) -> np.ndarray:
    return 0.5 * np.exp(-np.abs(np.asarray(z, float)))


def _laplace_logpdf(z: np.ndarray) -> np.ndarray:
    return np.log(0.5) - np.abs(np.asarray(z, float))


def _laplace_ppf(u: np.ndarray) -> np.ndarray:
    u = np.asarray(u, float)
    return np.where(u <= 0.5, np.log(2.0 * u), -np.log(2.0 * (1.0 - u)))


def _logistic_pdf(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, float)
    e = np.exp(-np.abs(z))  # stable: f_* is symmetric
    return e / (1.0 + e) ** 2


def _logistic_logpdf(z: np.ndarray) -> np.ndarray:
    z = np.abs(np.asarray(z, float))
    return -z - 2.0 * np.log1p(np.exp(-z))


def _logistic_ppf(u: np.ndarray) -> np.ndarray:
    u = np.asarray(u, float)
    return -np.log(1.0 / u - 1.0)


def _normal_pdf(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, float)
    return np.exp(-0.5 * z**2) / np.sqrt(2.0 * np.pi)


def _normal_logpdf(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, float)
    return -0.5 * np.log(2.0 * np.pi) - 0.5 * z**2


def _normal_ppf(u: np.ndarray) -> np.ndarray:
    return st.norm.ppf(np.asarray(u, float))


def _exponential_pdf(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, float)
    return np.where(z > 0.0, np.exp(-np.clip(z, 0.0, None)), 0.0)


def _exponential_logpdf(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, float)
    return np.where(z > 0.0, -z, -np.inf)


def _exponential_ppf(u: np.ndarray) -> np.ndarray:
    return -np.log1p(-np.asarray(u, float))


STANDARD_MEMBERS: dict[str, StandardMember] = {
    "log-cauchy": StandardMember("cauchy", _cauchy_pdf, _cauchy_ppf, _cauchy_logpdf),
    "log-gumbel": StandardMember("gumbel", _gumbel_pdf, _gumbel_ppf, _gumbel_logpdf),
    "log-laplace": StandardMember("laplace", _laplace_pdf, _laplace_ppf, _laplace_logpdf),
    "log-logistic": StandardMember(
        "logistic", _logistic_pdf, _logistic_ppf, _logistic_logpdf
    ),
    "lognormal": StandardMember("normal", _normal_pdf, _normal_ppf, _normal_logpdf),
    "pareto1": StandardMember(
        "exponential",
        _exponential_pdf,
        _exponential_ppf,
        _exponential_logpdf,
        positive_support=True,
    ),
}


def _member(family: str) -> StandardMember:
    try:
        return STANDARD_MEMBERS[family]
    except KeyError:
        raise ValueError(
            f"unknown family {family!r}; expected one of {FAMILIES}"
        ) from None


# --------------------------------------------------------------------------------------
# Fitted-model container
# --------------------------------------------------------------------------------------
@dataclass
class Fit:
    """A fitted log-location-scale law on the LOG-DOLLAR scale.

    ``mu`` is the log-location, ``sigma`` the log-scale. Both are reported in the
    thesis's own units, so ``mu ~ 22.8`` means ``exp(22.8) ~ $8.0e9``.
    """

    family: str
    mu: float
    sigma: float
    estimator: str  # "oqls" | "gqls" | "mle"
    n: int
    a: float | None = None
    b: float | None = None
    k: int | None = None
    method: QuantileMethod | None = None
    quantile_space: QuantileSpace | None = None
    #: 2-norm condition number of Sigma_* (gQLS only) -- the GLS whitening's numerical
    #: risk indicator; log it, never silently trust it.
    sigma_star_cond: float | None = None
    diagnostics: dict = field(default_factory=dict)

    @property
    def params(self) -> tuple[float, float]:
        return (self.mu, self.sigma)

    def return_level(self, p: float) -> float:
        """1-in-1/(1-p) loss in DOLLARS -- see :func:`return_level`."""
        return return_level(self, p)

    def breakdown_point(self) -> float | None:
        return breakdown_point(self.a, self.b) if self.a is not None else None


# --------------------------------------------------------------------------------------
# eq. (3.8) -- the quantile grid
# --------------------------------------------------------------------------------------
def p_grid(a: float, b: float, k: int) -> np.ndarray:
    """Thesis eq. (3.8): ``p_i = a + (i-1)/(k-1) * (b - a)``, ``i = 1..k``.

    ``a`` and ``b`` are the extreme quantile levels; nothing outside ``[a, b]`` is ever
    consulted, which is exactly why the estimator has breakdown point ``min{a, 1-b}``.
    """
    if not (0.0 < a < b < 1.0):
        raise ValueError(f"need 0 < a < b < 1, got a={a}, b={b}")
    if k < 2:
        raise ValueError(f"need k >= 2 (two parameters to identify), got k={k}")
    i = np.arange(1, k + 1, dtype=float)
    return a + (i - 1.0) / (k - 1.0) * (b - a)


def breakdown_point(a: float, b: float) -> float:
    """Thesis eq. (2.4): ``BP = min{LBP, UBP} = min{a, 1-b}``."""
    return float(min(a, 1.0 - b))


# --------------------------------------------------------------------------------------
# Empirical log-quantiles (the regression response Y)
# --------------------------------------------------------------------------------------
def sample_log_quantiles(
    x: np.ndarray,
    p: np.ndarray,
    *,
    method: QuantileMethod = "hazen",
    quantile_space: QuantileSpace = "log",
) -> np.ndarray:
    """``Y`` of §3.5 from LOG-DOLLAR data ``x``.

    ``quantile_space="log"``  -> ``quantile(x, p)``            (quantile the log-dollars)
    ``quantile_space="dollar"`` -> ``log(quantile(exp(x), p))``  (thesis-literal)

    Identical for order-statistic conventions (``inverted_cdf``, ``closest_observation``);
    they differ by O(1e-3) at n=30 for interpolating conventions.
    """
    x = np.asarray(x, float).ravel()
    p = np.asarray(p, float).ravel()
    if quantile_space == "log":
        return np.quantile(x, p, method=method)
    if quantile_space == "dollar":
        return np.log(np.quantile(np.exp(x), p, method=method))
    raise ValueError(f"quantile_space must be 'log' or 'dollar', got {quantile_space!r}")


# --------------------------------------------------------------------------------------
# eq. (2.1) -- the standard-member quantile covariance Sigma_*
# --------------------------------------------------------------------------------------
def sigma_star(p: np.ndarray, family: str) -> np.ndarray:
    """Thesis eq. (2.1) evaluated at the STANDARD member (so it is fully known).

        sigma_ij = p_i (1 - p_j) / (f_*(F_*^{-1}(p_i)) f_*(F_*^{-1}(p_j))),  i <= j

    symmetrized by ``sigma_ij = sigma_ji`` for ``i > j``. Proposition 3.1 shows the
    log-location-scale family inherits exactly this matrix (the Jacobian of ``log``
    cancels the ``F^{-1}(p_i) F^{-1}(p_j)`` factors), which is why the same ``Sigma_*``
    serves both the location-scale and the log-location-scale case.
    """
    p = np.asarray(p, float).ravel()
    if p.ndim != 1 or p.size < 2:
        raise ValueError("p must be a 1-D grid with at least 2 levels")
    if not np.all((p > 0.0) & (p < 1.0)):
        raise ValueError("all quantile levels must lie strictly inside (0, 1)")
    member = _member(family)
    dens = np.asarray(member.pdf(member.ppf(p)), float)
    if not np.all(np.isfinite(dens)) or np.any(dens <= 0.0):
        raise ValueError(
            f"standard density vanished on the grid for {family!r}; "
            "shrink (a, b) or reduce k"
        )
    # upper triangle p_i (1 - p_j) for i <= j, then mirror.
    upper = np.triu(np.outer(p, 1.0 - p))
    core = upper + np.triu(upper, 1).T
    return core / np.outer(dens, dens)


def design_matrix(p: np.ndarray, family: str) -> np.ndarray:
    """Thesis eq. (3.3): ``X = [1, F_*^{-1}(p_i)]``, shape ``(k, 2)``."""
    member = _member(family)
    p = np.asarray(p, float).ravel()
    return np.column_stack([np.ones_like(p), np.asarray(member.ppf(p), float)])


def _cholesky_or_none(sigma: np.ndarray) -> np.ndarray | None:
    try:
        return sla.cholesky(sigma, lower=True)
    except (sla.LinAlgError, np.linalg.LinAlgError):
        return None


def _quad_form(sigma: np.ndarray, resid: np.ndarray) -> float:
    """``resid' Sigma^{-1} resid`` WITHOUT forming ``Sigma^{-1}``.

    Cholesky-whitening first (``||L^{-1} r||^2``); a least-squares solve of
    ``Sigma z = r`` is the fallback when ``Sigma`` is too ill-conditioned to factor.
    """
    resid = np.asarray(resid, float).ravel()
    chol = _cholesky_or_none(sigma)
    if chol is not None:
        z = sla.solve_triangular(chol, resid, lower=True)
        return float(z @ z)
    z, *_ = np.linalg.lstsq(sigma, resid, rcond=None)
    return float(resid @ z)


# --------------------------------------------------------------------------------------
# eq. (3.4) -- ordinary QLS
# --------------------------------------------------------------------------------------
def oqls(
    x: np.ndarray,
    a: float = 0.05,
    b: float = 0.95,
    k: int = 8,
    family: str = "lognormal",
    *,
    method: QuantileMethod = "hazen",
    quantile_space: QuantileSpace = "log",
) -> Fit:
    """Thesis eq. (3.4): ``beta_hat_oQLS = (X'X)^{-1} X'Y``.

    Plain OLS of the empirical log-quantiles on the standard-member quantiles -- the
    intercept is ``mu_hat``, the slope is ``sigma_hat``. Implicitly assumes
    ``Sigma_* = I_k`` (thesis §3.2), which is *wrong* but consistent; the resulting
    efficiency loss is largest exactly for the heavy-tailed members (Table 3.3: ARE
    0.232 for Cauchy vs 0.936 for Normal at k=25).
    """
    x = np.asarray(x, float).ravel()
    p = p_grid(a, b, k)
    y = sample_log_quantiles(x, p, method=method, quantile_space=quantile_space)
    design = design_matrix(p, family)
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    return Fit(
        family=family,
        mu=float(beta[0]),
        sigma=float(beta[1]),
        estimator="oqls",
        n=x.size,
        a=a,
        b=b,
        k=k,
        method=method,
        quantile_space=quantile_space,
        diagnostics={"p": p, "y": y, "residuals": resid},
    )


# --------------------------------------------------------------------------------------
# eq. (3.6) -- generalized QLS
# --------------------------------------------------------------------------------------
def gqls(
    x: np.ndarray,
    a: float = 0.05,
    b: float = 0.95,
    k: int = 8,
    family: str = "lognormal",
    *,
    method: QuantileMethod = "hazen",
    quantile_space: QuantileSpace = "log",
) -> Fit:
    """Thesis eq. (3.6): ``beta_hat_gQLS = (X'Sigma_*^{-1}X)^{-1} X'Sigma_*^{-1}Y``.

    Solved through the **whitened** system, never by inverting ``Sigma_*``:
    factor ``Sigma_* = L L'``, form ``L^{-1}X`` and ``L^{-1}Y``, and run OLS on those.
    The 2-norm condition number of ``Sigma_*`` is recorded on the returned
    :class:`Fit` (``sigma_star_cond``) -- for log-Cauchy on a wide grid it runs to
    1e5+, which is the numerical price of the efficiency gain.
    """
    x = np.asarray(x, float).ravel()
    p = p_grid(a, b, k)
    y = sample_log_quantiles(x, p, method=method, quantile_space=quantile_space)
    design = design_matrix(p, family)
    cov = sigma_star(p, family)
    cond = float(np.linalg.cond(cov))

    chol = _cholesky_or_none(cov)
    if chol is not None:
        design_w = sla.solve_triangular(chol, design, lower=True)
        y_w = sla.solve_triangular(chol, y, lower=True)
        whitening = "cholesky"
    else:  # pragma: no cover - only fires on a numerically hopeless grid
        eigvals, eigvecs = np.linalg.eigh(cov)
        eigvals = np.clip(eigvals, 1e-300, None)
        root_inv = eigvecs @ np.diag(eigvals ** -0.5) @ eigvecs.T
        design_w, y_w = root_inv @ design, root_inv @ y
        whitening = "eigh"

    beta, *_ = np.linalg.lstsq(design_w, y_w, rcond=None)
    resid = y - design @ beta
    return Fit(
        family=family,
        mu=float(beta[0]),
        sigma=float(beta[1]),
        estimator="gqls",
        n=x.size,
        a=a,
        b=b,
        k=k,
        method=method,
        quantile_space=quantile_space,
        sigma_star_cond=cond,
        diagnostics={
            "p": p,
            "y": y,
            "residuals": resid,
            "whitening": whitening,
            "sigma_star_cond": cond,
        },
    )


# --------------------------------------------------------------------------------------
# Maximum likelihood for the same six families (the efficiency benchmark)
# --------------------------------------------------------------------------------------
def _nll(theta: np.ndarray, x: np.ndarray, member: StandardMember) -> float:
    mu, log_sigma = float(theta[0]), float(theta[1])
    sigma = np.exp(log_sigma)
    z = (x - mu) / sigma
    lp = member.logpdf(z)
    if not np.all(np.isfinite(lp)):
        return np.inf
    return float(-np.sum(lp) + x.size * log_sigma)


def mle(x: np.ndarray, family: str = "lognormal") -> Fit:
    """Maximum likelihood on the LOG-DOLLAR scale, i.e. for the location-scale member.

    * **lognormal** -- closed form: ``mu_hat = mean(x)``, ``sigma_hat = sqrt(mean((x-mu)^2))``
      (the ML divisor, ``ddof=0``).
    * **Pareto I** -- boundary MLE under the thesis's parametrization ``mu = log(theta)``,
      ``sigma = 1/alpha``: ``theta_hat = min(X)`` so ``mu_hat = min(x)``, and
      ``alpha_hat = n / sum(x_i - mu_hat)`` so ``sigma_hat = mean(x) - min(x)``.
    * **log-Laplace** -- ``mu_hat = median(x)``, ``sigma_hat = mean|x - mu_hat|``.
    * **log-Cauchy / log-Gumbel / log-Logistic** -- Nelder-Mead on the negative
      log-likelihood in ``(mu, log sigma)``, started from robust moments.
    """
    x = np.asarray(x, float).ravel()
    if x.size < 2:
        raise ValueError("need at least 2 observations")
    member = _member(family)

    if family == "lognormal":
        mu = float(np.mean(x))
        sigma = float(np.sqrt(np.mean((x - mu) ** 2)))
        return Fit(family, mu, sigma, "mle", x.size, diagnostics={"closed_form": True})

    if family == "pareto1":
        mu = float(np.min(x))
        sigma = float(np.mean(x - mu))
        return Fit(
            family,
            mu,
            sigma,
            "mle",
            x.size,
            diagnostics={"closed_form": True, "alpha_hat": 1.0 / sigma if sigma else np.inf},
        )

    if family == "log-laplace":
        mu = float(np.median(x))
        sigma = float(np.mean(np.abs(x - mu)))
        return Fit(family, mu, sigma, "mle", x.size, diagnostics={"closed_form": True})

    # Numerical: Nelder-Mead on (mu, log sigma), robust start (median / IQR-scaled MAD).
    mu0 = float(np.median(x))
    scale0 = float(np.median(np.abs(x - mu0))) or float(np.std(x)) or 1.0
    result = minimize(
        _nll,
        x0=np.array([mu0, np.log(scale0)]),
        args=(x, member),
        method="Nelder-Mead",
        options={"xatol": 1e-10, "fatol": 1e-12, "maxiter": 20000, "maxfev": 20000},
    )
    mu = float(result.x[0])
    sigma = float(np.exp(result.x[1]))
    return Fit(
        family,
        mu,
        sigma,
        "mle",
        x.size,
        diagnostics={"closed_form": False, "nll": float(result.fun), "success": bool(result.success)},
    )


# --------------------------------------------------------------------------------------
# eq. (5.2) -- in-sample goodness of fit
# --------------------------------------------------------------------------------------
def W(
    x: np.ndarray,
    fit: Fit,
    *,
    a: float | None = None,
    b: float | None = None,
    k: int | None = None,
    method: QuantileMethod | None = None,
    quantile_space: QuantileSpace | None = None,
) -> dict:
    """Thesis eq. (5.2): ``W = (n / sigma_hat^2) (Y - X beta_hat)' Sigma_*^{-1} (Y - X beta_hat)``.

    Under ``H_0`` (the data came from this family), ``W`` is asymptotically
    ``chi^2_{k-2}`` -- two degrees of freedom are spent on ``(mu, sigma)``. Proposition
    5.2 derives this by the orthogonal decomposition ``Q = Q_1 + Q_2`` with
    ``Q ~ chi^2_k`` and ``Q_2 ~ chi^2_2``.

    The thesis derives the asymptotics for ``beta_hat_gQLS``; passing an oQLS or MLE fit
    still yields a usable diagnostic (the study uses it as a GoF guardrail), but the
    chi-square calibration is only claimed for gQLS -- ``chi2_calibrated`` records which.

    Returns ``{"W", "df", "p_value", "chi2_calibrated"}``.
    """
    x = np.asarray(x, float).ravel()
    a = fit.a if a is None else a
    b = fit.b if b is None else b
    k = fit.k if k is None else k
    method = (fit.method or "hazen") if method is None else method
    quantile_space = (fit.quantile_space or "log") if quantile_space is None else quantile_space
    if a is None or b is None or k is None:
        raise ValueError(
            "W needs a quantile grid: pass a, b, k explicitly for an MLE fit "
            "(the thesis evaluates GoF on the SAME grid used for estimation)"
        )
    if k <= 2:
        raise ValueError(f"W needs k > 2 for a positive df (k-2), got k={k}")

    p = p_grid(a, b, k)
    y = sample_log_quantiles(x, p, method=method, quantile_space=quantile_space)
    design = design_matrix(p, fit.family)
    resid = y - design @ np.array([fit.mu, fit.sigma])
    quad = _quad_form(sigma_star(p, fit.family), resid)
    stat = x.size / fit.sigma**2 * quad
    df = k - 2
    return {
        "W": float(stat),
        "df": int(df),
        "p_value": float(st.chi2.sf(stat, df)),
        "chi2_calibrated": fit.estimator == "gqls",
    }


# --------------------------------------------------------------------------------------
# eq. (5.3) -- out-of-sample goodness of fit
# --------------------------------------------------------------------------------------
def _out_levels(r: int, a_out: float = 0.01, b_out: float = 0.99) -> np.ndarray:
    """The 'universal' validation grid: eq.-(3.8) spacing on ``[a_out, b_out]``.

    Thesis §6.2.1 describes it as "the universal set of 50 quantile levels (from 0.01 to
    0.99)"; §6.2.2 uses ``r = 25`` for the hurricane data (Table 6.9 caption). Universal
    = the same levels for every ``(a, b)``, which is what makes fits with different trims
    comparable.
    """
    return p_grid(a_out, b_out, r)


def W_out(
    x: np.ndarray,
    fit: Fit,
    *,
    r: int = 25,
    mode: Literal["chi2", "bootstrap"] = "chi2",
    B: int = 1000,
    seed: int | None = 12345,
    a_out: float = 0.01,
    b_out: float = 0.99,
    method: QuantileMethod | None = None,
    quantile_space: QuantileSpace | None = None,
) -> dict:
    """Thesis eq. (5.3): the out-of-sample GoF statistic on a universal ``r``-level grid.

        W_out = (n / sigma_hat^2) (Y_out - X_out beta_hat)' Sigma_out^{-1} (Y_out - X_out beta_hat)

    ``beta_hat`` still comes from the ESTIMATION grid ``p_1..p_k``; ``Y_out`` is read at
    the universal levels ``p_1^out..p_r^out``. Because the two grids do not coincide, the
    thesis calls the null distribution "a major challenge" and prices the p-value by
    parametric bootstrap (§5.2, Steps 1-4, ``B = 1000``).

    ``mode="chi2"`` uses a ``chi^2_{r-2}`` reference instead -- the study's RQ2 asks
    whether that shortcut is distinguishable from the bootstrap ON THIS DATA. Both are
    implemented so the comparison is a measurement, not an assumption.

    Returns ``{"W_out", "r", "mode", "p_value", "df"|"B"}``.
    """
    x = np.asarray(x, float).ravel()
    method = (fit.method or "hazen") if method is None else method
    quantile_space = (fit.quantile_space or "log") if quantile_space is None else quantile_space
    if r <= 2:
        raise ValueError(f"W_out needs r > 2, got r={r}")

    p_out = _out_levels(r, a_out, b_out)
    cov_out = sigma_star(p_out, fit.family)
    design_out = design_matrix(p_out, fit.family)
    beta = np.array([fit.mu, fit.sigma])

    def _statistic(sample: np.ndarray, beta_hat: np.ndarray, sigma_hat: float) -> float:
        y_out = sample_log_quantiles(
            sample, p_out, method=method, quantile_space=quantile_space
        )
        return sample.size / sigma_hat**2 * _quad_form(cov_out, y_out - design_out @ beta_hat)

    stat = _statistic(x, beta, fit.sigma)

    if mode == "chi2":
        df = r - 2
        return {
            "W_out": float(stat),
            "r": int(r),
            "mode": "chi2",
            "df": int(df),
            "p_value": float(st.chi2.sf(stat, df)),
        }
    if mode != "bootstrap":
        raise ValueError(f"mode must be 'chi2' or 'bootstrap', got {mode!r}")

    # Parametric bootstrap, thesis §5.2 Steps 1-4.
    if fit.a is None or fit.b is None or fit.k is None:
        raise ValueError("bootstrap mode needs the estimation grid (a, b, k) on the fit")
    rng = np.random.default_rng(seed)
    member = _member(fit.family)
    p_est = p_grid(fit.a, fit.b, fit.k)
    design_est = design_matrix(p_est, fit.family)
    cov_est = sigma_star(p_est, fit.family)
    chol_est = _cholesky_or_none(cov_est)

    boot = np.empty(B, dtype=float)
    for i in range(B):
        u = rng.random(x.size)
        sample = fit.mu + fit.sigma * np.asarray(member.ppf(u), float)  # log-dollars
        y_est = sample_log_quantiles(
            sample, p_est, method=method, quantile_space=quantile_space
        )
        if chol_est is not None:
            design_w = sla.solve_triangular(chol_est, design_est, lower=True)
            y_w = sla.solve_triangular(chol_est, y_est, lower=True)
        else:  # pragma: no cover
            design_w, y_w = design_est, y_est
        beta_b, *_ = np.linalg.lstsq(design_w, y_w, rcond=None)
        boot[i] = _statistic(sample, beta_b, float(beta_b[1]))

    return {
        "W_out": float(stat),
        "r": int(r),
        "mode": "bootstrap",
        "B": int(B),
        "seed": seed,
        "p_value": float(np.mean(boot > stat)),
        "bootstrap_mean": float(np.mean(boot)),
    }


# --------------------------------------------------------------------------------------
# The decision functional
# --------------------------------------------------------------------------------------
def return_level(fit: Fit, p: float = 0.99, family: str | None = None) -> float:
    """``exp(mu_hat + sigma_hat * F_*^{-1}(p))`` -- the 1-in-1/(1-p) loss, in DOLLARS.

    This is the actuarial decision unit and the study's second track. Note how brutally
    the transform amplifies ``sigma_hat`` for a heavy standard member: at ``p = 0.99``
    the log-Cauchy quantile is ``tan(0.49*pi) = 31.82``, so a 0.04 move in ``sigma_hat``
    multiplies the return level by ``exp(0.04 * 31.82) ~ 3.6``. Parameter robustness and
    decision robustness are different properties.
    """
    if not (0.0 < p < 1.0):
        raise ValueError(f"need 0 < p < 1, got {p}")
    member = _member(family or fit.family)
    return float(np.exp(fit.mu + fit.sigma * float(member.ppf(np.array([p]))[0])))


def _refuse_moments(family: str, what: str) -> None:
    if family in _NO_FINITE_MOMENTS:
        raise NotImplementedError(
            f"{what} is undefined for {family!r}: the log-Cauchy distribution has NO "
            "finite moments (its standard member is Cauchy, whose mean integral "
            "diverges), so every mean-, CTE-, and TVaR-style functional is undefined -- "
            "not merely large. Price this family through QUANTILES (return_level) or "
            "choose a family with a finite mean; a finite number here would be an "
            "artifact of truncation, not an estimate."
        )


def mean_loss(fit: Fit) -> float:
    """``E[X]`` in dollars. Raises for log-Cauchy -- see :func:`return_level`'s note."""
    _refuse_moments(fit.family, "the mean loss E[X]")
    if fit.family == "lognormal":
        return float(np.exp(fit.mu + 0.5 * fit.sigma**2))
    if fit.family == "pareto1":
        alpha = 1.0 / fit.sigma
        if alpha <= 1.0:
            raise NotImplementedError(
                f"Pareto I with alpha = {alpha:.4f} <= 1 has an infinite mean"
            )
        return float(np.exp(fit.mu) * alpha / (alpha - 1.0))
    raise NotImplementedError(
        f"closed-form mean not implemented for {fit.family!r}; integrate the quantile "
        "function numerically if you need it, and check finiteness first"
    )


def cte(fit: Fit, p: float = 0.99, n_grid: int = 20000) -> float:
    """``CTE_p = E[X | X > VaR_p]`` in dollars, by quantile integration.

    Raises for log-Cauchy: conditioning on the tail does not rescue a divergent mean.
    """
    _refuse_moments(fit.family, f"the conditional tail expectation CTE_{p}")
    if not (0.0 < p < 1.0):
        raise ValueError(f"need 0 < p < 1, got {p}")
    member = _member(fit.family)
    u = np.linspace(p, 1.0, n_grid + 1)[:-1] + 0.5 * (1.0 - p) / n_grid
    levels = np.exp(fit.mu + fit.sigma * np.asarray(member.ppf(u), float))
    if not np.all(np.isfinite(levels)):
        raise NotImplementedError(
            f"CTE_{p} diverged numerically for {fit.family!r} -- check tail finiteness"
        )
    return float(np.mean(levels))
