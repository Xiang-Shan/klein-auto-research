"""generator.py — PVLossGenerator: a known-truth synthetic lab for PV loss severity.

This is study 02's "data": a photovoltaic (PV) loss-severity generator whose exact
risk functionals (mean payout, VaR, TVaR, risk-loaded premium under a deductible/limit
layer) are KNOWN, so every estimator can be scored against ground truth. It is the DATA
side of a robust-estimation study — the METHOD side (MLE / QLS / MTM) lives in
``estimators.py``.

Design (per the study plan spec table)
--------------------------------------
Peril mix (mixture weights):
    inverter 0.45 · storm 0.20 · degradation 0.15 · fire 0.12 · hail 0.08
Severity body: lognormal(mu=9.0, sigma=1.1) baseline (median loss ~ $8.1k), with an
optional gamma(k=1.5, theta=9000) body variant. Per-peril adjustments:
  * hail  — location-shifted heavy severity: scale x ``hail_mult`` (=8), i.e. mu + ln 8
            for lognormal (or theta x 8 for gamma). Low frequency (8% of claims) x high
            severity reproduces the industry loss-concentration story (a small share of
            claims drives a large share of dollars; pv-magazine 2025, market context only).
  * fire  — heavier tail: when ``tail_mode`` is on, a Generalized Pareto (GPD, xi=0.4)
            tail is spliced above ``tail_threshold`` ($250k). Off by default.

Contamination (measurement error, NOT real risk): with probability ``contam_eps`` a
recorded value is a gross error — either a big over-report (x Uniform(10, 100)) or a
unit-typo (x 0.01, e.g. dollars keyed as hundreds). Split by ``contam_gross_share``.

Incompleteness (only when ``incomplete=True`` is passed to :meth:`sample`):
  * deductible ``d`` — left TRUNCATION: true losses <= d are never filed (UNOBSERVED).
  * limit ``u``      — right CENSORING: true losses >= u are recorded as u, flagged.
Truncation and censoring act on the TRUE loss (the deductible and limit are properties of
the true loss); contamination corrupts the RECORDED value.

Truth functionals & the premium loading convention
--------------------------------------------------
The premium is priced on the per-policy layer payout Y = (min(X, u) - d)_+ (0 when the
loss is below the deductible). Truth functionals are computed on the CLEAN mixture (no
contamination — contamination is data error, not risk) by 1-D numeric integration of the
mixture survival function S(x) = 1 - F(x):

    E[Y]        = ∫_d^u S(x) dx                              (layer / stop-loss identity)
    VaR_p(Y)    = min(Q_X(p), u) - d      for p > F(d), else 0   (Q_X via root-find on F)
    TVaR_p(Y)   = VaR_p(Y) + (1/(1-p)) ∫_{d+VaR_p}^u S(x) dx
    premium     = E[Y] + loading * (TVaR99(Y) - E[Y])      (loading default 0.10)

i.e. the risk-loaded premium is the expected layer payout plus a 10% load on the TVaR99
risk margin *above* the mean. Because the upper limit u is finite, every integral is over
a finite interval and TVaR is finite even with the xi<1 GPD tail. The tests verify these
functionals against a 10^6-draw Monte-Carlo within 1%.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import scipy.stats as st
from scipy.integrate import quad
from scipy.optimize import brentq

# --- study constants (the standard PV product layer priced throughout) ------
DEFAULT_PERILS: dict[str, float] = {
    "inverter": 0.45,
    "storm": 0.20,
    "degradation": 0.15,
    "fire": 0.12,
    "hail": 0.08,
}
STD_DEDUCTIBLE = 5_000.0
STD_LIMIT = 2_000_000.0
PREMIUM_LOADING = 0.10  # load on the TVaR99 risk margin above the mean payout


# --- components: each exposes .cdf / .sf / .ppf on the RAW loss scale --------
class _Spliced:
    """Body distribution with a Generalized-Pareto tail spliced above ``t``.

    F(x) = F_body(x) for x <= t; for x > t, F(x) = p_t + (1-p_t) G(x-t) with G the
    GPD(xi, beta) CDF and p_t = F_body(t). Continuous in F at t (density may jump — fine
    for a generator). Exactly invertible, so sampling and truth functionals stay exact.
    """

    def __init__(self, body, t: float, xi: float, beta: float) -> None:
        self.body = body
        self.t = float(t)
        self.xi = float(xi)
        self.beta = float(beta)
        self.pt = float(body.cdf(t))

    def cdf(self, x):
        x = np.asarray(x, dtype=float)
        excess = np.maximum(x - self.t, 0.0)
        g = 1.0 - (1.0 + self.xi * excess / self.beta) ** (-1.0 / self.xi)
        return np.where(x <= self.t, self.body.cdf(x), self.pt + (1.0 - self.pt) * g)

    def sf(self, x):
        return 1.0 - self.cdf(x)

    def ppf(self, p):
        p = np.asarray(p, dtype=float)
        pe = np.clip((p - self.pt) / (1.0 - self.pt), 0.0, 1.0 - 1e-15)
        excess = self.beta / self.xi * ((1.0 - pe) ** (-self.xi) - 1.0)
        return np.where(p <= self.pt, self.body.ppf(np.minimum(p, self.pt)), self.t + excess)


def layer_functionals(sf, qf, d: float, u: float, loading: float = PREMIUM_LOADING) -> dict:
    """Risk functionals of the layer payout Y=(min(X,u)-d)_+ for ANY loss law.

    ``sf`` is the survival function S(x)=P(X>x) and ``qf`` the quantile function Q_X(p)
    of the ground-up loss X. Shared by the generator (mixture truth) and the estimators
    (fitted single-component law), so "truth" and "estimate" are computed identically.
    """
    mean_payout = float(quad(sf, d, u, limit=200)[0])
    f_d = 1.0 - float(sf(d))  # F(d)

    def var(p: float) -> float:
        if p <= f_d:
            return 0.0
        return float(min(float(qf(p)), u) - d)

    var95, var99 = var(0.95), var(0.99)
    tail = float(quad(sf, d + var99, u, limit=200)[0]) if d + var99 < u else 0.0
    tvar99 = var99 + tail / (1.0 - 0.99)
    premium = mean_payout + loading * (tvar99 - mean_payout)
    return {
        "mean_payout": mean_payout,
        "var95": var95,
        "var99": var99,
        "tvar99": tvar99,
        "premium": premium,
    }


@dataclass
class SampleResult:
    """One observed sample: recorded losses plus per-observation flags."""

    losses: np.ndarray  # recorded values (censored capped at u; contamination in effect)
    censored: np.ndarray  # bool: true loss >= u (recorded as u)
    contaminated: np.ndarray  # bool: recorded value corrupted by a gross error


@dataclass
class PVLossGenerator:
    """Known-truth PV loss-severity generator (see module docstring for the spec)."""

    body: str = "lognormal"  # "lognormal" | "gamma"
    mu: float = 9.0  # lognormal log-location
    sigma: float = 1.1  # lognormal log-scale (sdlog)
    gamma_k: float = 1.5  # gamma shape
    gamma_theta: float = 9000.0  # gamma scale
    hail_mult: float = 8.0  # hail severity multiplier (location shift x8)
    tail_mode: bool = False  # splice a GPD tail onto the fire peril
    tail_threshold: float = 250_000.0
    tail_xi: float = 0.4
    tail_beta: float = 125_000.0
    deductible: float = STD_DEDUCTIBLE  # d — truncation point AND payout deductible
    limit: float = STD_LIMIT  # u — censoring point AND payout limit
    contam_eps: float = 0.0  # contamination rate epsilon
    contam_gross_share: float = 0.5  # of contaminated points, share that are gross-over
    single_family: bool = False  # pure body (no perils/mix) — used by the E1 truth gate
    loading: float = PREMIUM_LOADING
    perils: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_PERILS))

    # -- component construction ---------------------------------------------
    def _body_dist(self, mult: float = 1.0):
        if self.body == "lognormal":
            return st.lognorm(s=self.sigma, scale=np.exp(self.mu) * mult)
        if self.body == "gamma":
            return st.gamma(a=self.gamma_k, scale=self.gamma_theta * mult)
        raise ValueError(f"unknown body {self.body!r} (want 'lognormal' or 'gamma')")

    def _components(self) -> list[tuple[float, object]]:
        """Return [(weight, component)] with each component exposing cdf/sf/ppf."""
        if self.single_family:
            return [(1.0, self._body_dist())]
        comps: list[tuple[float, object]] = []
        for peril, w in self.perils.items():
            if peril == "hail":
                comps.append((w, self._body_dist(self.hail_mult)))
            elif peril == "fire" and self.tail_mode:
                comps.append(
                    (w, _Spliced(self._body_dist(), self.tail_threshold, self.tail_xi, self.tail_beta))
                )
            else:
                comps.append((w, self._body_dist()))
        return comps

    # -- mixture law (clean, pre-contamination) -----------------------------
    def mixture_sf(self, x) -> float:
        return float(sum(w * float(np.asarray(c.sf(x))) for w, c in self._components()))

    def mixture_cdf(self, x) -> float:
        return 1.0 - self.mixture_sf(x)

    def loss_quantile(self, p: float) -> float:
        """Q_X(p) of the clean mixture, via a robust root-find on the CDF."""
        lo, hi = 1e-3, 1e12
        return float(brentq(lambda x: self.mixture_cdf(x) - p, lo, hi, xtol=1e-6, rtol=1e-8))

    # -- truth --------------------------------------------------------------
    def truth_functionals(self, d: float | None = None, u: float | None = None) -> dict:
        """Exact risk functionals of the layer payout under the CLEAN mixture."""
        d = self.deductible if d is None else d
        u = self.limit if u is None else u
        return layer_functionals(self.mixture_sf, self.loss_quantile, d, u, self.loading)

    # -- sampling -----------------------------------------------------------
    def sample(
        self,
        n: int,
        seed: int,
        *,
        incomplete: bool = False,
        contaminate: bool = True,
    ) -> SampleResult:
        """Draw ``n`` policies. Deterministic in ``seed`` (inverse-CDF sampling).

        ``incomplete`` applies deductible truncation + limit censoring (on the TRUE
        loss). ``contaminate`` injects gross errors at rate ``contam_eps`` into the
        RECORDED value. E1 calls with incomplete=False, contaminate=False.
        """
        rng = np.random.default_rng(seed)
        comps = self._components()
        weights = np.array([w for w, _ in comps], dtype=float)
        weights /= weights.sum()

        # inverse-CDF draw per component (exact & reproducible)
        u_draw = rng.random(n)
        if len(comps) == 1:
            x = np.asarray(comps[0][1].ppf(u_draw), dtype=float)
        else:
            idx = rng.choice(len(comps), size=n, p=weights)
            x = np.empty(n, dtype=float)
            for k, (_, comp) in enumerate(comps):
                m = idx == k
                if m.any():
                    x[m] = np.asarray(comp.ppf(u_draw[m]), dtype=float)

        # contamination corrupts the RECORDED value (independent of truncation)
        contaminated = (rng.random(n) < self.contam_eps) if contaminate else np.zeros(n, bool)
        rec = x.copy()
        if contaminated.any():
            is_gross = rng.random(n) < self.contam_gross_share
            gross = contaminated & is_gross
            typo = contaminated & ~is_gross
            rec[gross] *= rng.uniform(10.0, 100.0, size=gross.sum())
            rec[typo] *= 0.01

        if incomplete:
            censored = x >= self.limit  # censor on TRUE loss
            rec[censored] = self.limit
            contaminated = contaminated & ~censored  # admin records the limit, not the mis-key
            keep = x > self.deductible  # truncate on TRUE loss (below-deductible unobserved)
            return SampleResult(rec[keep], censored[keep], contaminated[keep])
        return SampleResult(rec, np.zeros(n, bool), contaminated)


def dollar_concentration(gen: PVLossGenerator, n: int = 200_000, seed: int = 0) -> dict:
    """Diagnostic: each peril's share of claims vs share of dollars (the hail story)."""
    rng = np.random.default_rng(seed)
    comps = gen._components()
    weights = np.array([w for w, _ in comps], float)
    weights /= weights.sum()
    names = list(gen.perils) if not gen.single_family else ["body"]
    idx = rng.choice(len(comps), size=n, p=weights)
    x = np.array([comps[k][1].ppf(rng.random()) for k in idx])
    total = x.sum()
    return {
        names[k]: {
            "claim_share": float((idx == k).mean()),
            "dollar_share": float(x[idx == k].sum() / total),
        }
        for k in range(len(comps))
    }
