"""Fast tests for study 02 (RQLS PV severity) — small n/reps, scipy-only.

These pin the generator's determinism and known-truth, and the load-bearing estimator
claims: naive MLE recovers a clean single family, the truncated/censored MLE beats naive
under incompleteness, QLS matches MLE on clean data, and QLS beats naive MLE on premium
error under 10% contamination (the headline robustness claim). Kept cheap enough for CI.
"""

from __future__ import annotations

import numpy as np
import pytest

from generator import STD_DEDUCTIBLE, STD_LIMIT, PVLossGenerator
from estimators import (
    default_p_grid,
    mle_full,
    mle_truncated_censored,
    mtm,
    premium_error_pct,
    qls,
)

MU, SIGMA = 9.0, 1.1
D, U = STD_DEDUCTIBLE, STD_LIMIT


# (a) determinism -------------------------------------------------------------
def test_generator_determinism():
    gen = PVLossGenerator(contam_eps=0.05)
    a = gen.sample(3000, seed=7)
    b = gen.sample(3000, seed=7)
    c = gen.sample(3000, seed=8)
    assert np.array_equal(a.losses, b.losses)
    assert np.array_equal(a.contaminated, b.contaminated)
    assert not np.array_equal(a.losses, c.losses)


# (b) truth functionals vs Monte-Carlo ---------------------------------------
def test_truth_functionals_match_monte_carlo():
    gen = PVLossGenerator()  # default mixture, tail_mode off
    truth = gen.truth_functionals(D, U)

    rng = np.random.default_rng(0)
    comps = gen._components()
    w = np.array([c[0] for c in comps], float)
    w /= w.sum()
    idx = rng.choice(len(comps), size=1_000_000, p=w)
    x = np.empty(1_000_000)
    for k, (_, comp) in enumerate(comps):
        m = idx == k
        x[m] = comp.ppf(rng.random(m.sum()))
    payout = np.clip(np.minimum(x, U) - D, 0.0, None)

    assert truth["mean_payout"] == pytest.approx(payout.mean(), rel=0.01)
    assert truth["premium"] == pytest.approx(
        payout.mean() + gen.loading * (_tvar(payout, 0.99) - payout.mean()), rel=0.02
    )
    assert truth["var99"] == pytest.approx(np.quantile(payout, 0.99), rel=0.03)


def _tvar(y, p):
    var = np.quantile(y, p)
    tail = y[y >= var]
    return tail.mean() if len(tail) else var


# (c) naive MLE recovers a clean single family --------------------------------
def test_mle_full_recovers_lognormal():
    gen = PVLossGenerator(mu=MU, sigma=SIGMA, single_family=True)
    x = gen.sample(20_000, seed=1).losses
    fit = mle_full(x, "lognormal")
    assert fit.params["mu"] == pytest.approx(MU, abs=0.03)
    assert fit.params["sigma"] == pytest.approx(SIGMA, abs=0.03)


# (d) truncated/censored MLE beats naive under incompleteness -----------------
def test_truncated_mle_less_biased_than_naive():
    gen = PVLossGenerator(mu=MU, sigma=SIGMA, single_family=True, deductible=D, limit=U)
    naive_bias, tc_bias = [], []
    for r in range(20):
        s = gen.sample(5000, seed=100 + r, incomplete=True, contaminate=False)
        naive_bias.append(mle_full(s.losses, "lognormal").params["mu"] - MU)
        tc_bias.append(
            mle_truncated_censored(s.losses, D, U, s.censored, "lognormal").params["mu"] - MU
        )
    naive_bias, tc_bias = abs(np.mean(naive_bias)), abs(np.mean(tc_bias))
    assert naive_bias > 0.3          # naive is measurably biased (lower tail truncated)
    assert tc_bias < 0.05            # the proper estimator is ~unbiased
    assert tc_bias < naive_bias      # the ORDERING is the claim


# (e) QLS ~ MLE on clean data -------------------------------------------------
def test_qls_matches_mle_on_clean_data():
    gen = PVLossGenerator(mu=MU, sigma=SIGMA, single_family=True)
    x = gen.sample(20_000, seed=2).losses
    mle = mle_full(x, "lognormal")
    q = qls(x, d=0.0, u=np.inf, p_grid=default_p_grid(), family="lognormal")
    assert q.params["mu"] == pytest.approx(mle.params["mu"], abs=0.03)
    assert q.params["sigma"] == pytest.approx(mle.params["sigma"], rel=0.05)


# (f) QLS beats naive MLE on premium error under contamination ----------------
def test_qls_beats_mle_premium_error_under_contamination():
    gen = PVLossGenerator(mu=MU, sigma=SIGMA, single_family=True,
                          contam_eps=0.10, deductible=D, limit=U)
    truth = gen.truth_functionals(D, U)["premium"]
    trimmed = default_p_grid(trim=0.15)
    mle_err, qls_err = [], []
    for r in range(15):
        x = gen.sample(2000, seed=200 + r, incomplete=False, contaminate=True).losses
        mle_err.append(premium_error_pct(mle_full(x, "lognormal").premium(D, U), truth))
        qls_err.append(
            premium_error_pct(qls(x, 0.0, np.inf, trimmed, "lognormal").premium(D, U), truth)
        )
    assert np.mean(qls_err) < np.mean(mle_err)


# (g) contamination injects ~epsilon -----------------------------------------
def test_contamination_rate():
    gen = PVLossGenerator(contam_eps=0.10)
    s = gen.sample(50_000, seed=3, incomplete=False, contaminate=True)
    assert s.contaminated.mean() == pytest.approx(0.10, abs=0.01)


# (bonus) MTM is a sane robust estimator on clean data ------------------------
def test_mtm_recovers_lognormal():
    gen = PVLossGenerator(mu=MU, sigma=SIGMA, single_family=True)
    x = gen.sample(20_000, seed=4).losses
    fit = mtm(x, trim=0.1, family="lognormal")
    assert fit.params["mu"] == pytest.approx(MU, abs=0.05)
    assert fit.params["sigma"] == pytest.approx(SIGMA, abs=0.05)
