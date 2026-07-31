"""Fast tests for study 06 (hurricane gQLS return levels) — numpy/scipy only.

These pin the load-bearing claims of `estimators.py` against three independent
authorities, so a specification bug cannot pass silently:

  * **Closed-form theory** — the eq.-(3.8) grid, Serfling's eq.-(2.1) covariance for the
    normal member, and the textbook simple-regression formulas for oQLS.
  * **Monte Carlo** — gQLS recovers a known (mu, sigma); W is chi2_{k-2}-calibrated
    under H_0.
  * **The published thesis tables** — Table 6.8's summary statistics, Table 6.10's MLE
    lognormal cells (clean and contaminated), and the Sigma-star falsifier
    (o2-vs-g2 log-Cauchy sigma-hat, 0.23 vs 0.49) read from the COMMITTED
    `reference/thesis_tables.json`, never from a literal typed here twice.

Kept cheap enough for CI: no bootstrap, MC replicate counts in the hundreds.
"""

from __future__ import annotations

import json
from pathlib import Path

import estimators as E
import numpy as np
import pandas as pd
import pytest
import scipy.stats as st
import stress as S

STUDY_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = STUDY_DIR.parent.parent
BUNDLED_CSV = (
    REPO_ROOT / "datasets" / "hurricane_top30_pl1998" / "hurricane_top30_pl1998.csv"
)
THESIS_TABLES = STUDY_DIR / "reference" / "thesis_tables.json"


@pytest.fixture(scope="module")
def tables() -> dict:
    return json.loads(THESIS_TABLES.read_text())


@pytest.fixture(scope="module")
def damages() -> np.ndarray:
    """The 30 published damage amounts, in billions of 1995 USD."""
    return pd.read_csv(BUNDLED_CSV)["damage_bn_1995"].to_numpy(float)


@pytest.fixture(scope="module")
def log_dollars(damages: np.ndarray) -> np.ndarray:
    """The fitting column: x = log(damage_bn_1995 * 1e9)."""
    return np.log(damages * 1e9)


# (a) eq. (3.8) ----------------------------------------------------------------------
def test_a_quantile_grid_eq_3_8():
    """p_i = a + (i-1)/(k-1)(b-a): k=8 on (0.05, 0.95) is an 8-point equal ladder."""
    p = E.p_grid(0.05, 0.95, 8)
    assert p.shape == (8,)
    assert p[0] == pytest.approx(0.05)
    assert p[-1] == pytest.approx(0.95)
    assert p[1] == pytest.approx(0.05 + (0.95 - 0.05) / 7)  # 0.17857142857...
    assert p[1] == pytest.approx(0.1785714285714286, abs=1e-12)
    np.testing.assert_allclose(np.diff(p), (0.95 - 0.05) / 7, atol=1e-12)
    # breakdown point, eq. (2.4)
    assert E.breakdown_point(0.05, 0.95) == pytest.approx(0.05)
    assert E.breakdown_point(0.10, 0.90) == pytest.approx(0.10)
    with pytest.raises(ValueError):
        E.p_grid(0.9, 0.1, 8)  # a < b required
    with pytest.raises(ValueError):
        E.p_grid(0.05, 0.95, 1)  # k >= 2 required


# (b) eq. (2.1) against Serfling's closed form ----------------------------------------
def test_b_sigma_star_normal_matches_serfling_closed_form():
    """sigma_ij = p_i(1-p_j) / (phi(z_i) phi(z_j)) for i <= j, hand-checked entries."""
    p = E.p_grid(0.05, 0.95, 8)
    cov = E.sigma_star(p, "lognormal")

    assert cov.shape == (8, 8)
    np.testing.assert_allclose(cov, cov.T, atol=1e-12)  # symmetric

    z = st.norm.ppf(p)
    phi = st.norm.pdf(z)

    # entry (1,1): the widest variance, at p = 0.05.
    expected_11 = 0.05 * 0.95 / phi[0] ** 2
    assert cov[0, 0] == pytest.approx(expected_11, rel=1e-12)
    assert cov[0, 0] == pytest.approx(0.05 * 0.95 / st.norm.pdf(st.norm.ppf(0.05)) ** 2)

    # entry (4,5) straddles the median; i < j so the i<=j branch applies directly.
    expected_45 = p[3] * (1.0 - p[4]) / (phi[3] * phi[4])
    assert cov[3, 4] == pytest.approx(expected_45, rel=1e-12)
    assert cov[4, 3] == pytest.approx(expected_45, rel=1e-12)  # mirrored, not recomputed

    # entry (8,8): symmetric partner of (1,1) for a symmetric member.
    assert cov[7, 7] == pytest.approx(cov[0, 0], rel=1e-12)

    # a hand-computed scalar, independent of the module: p=0.5 on the standard normal.
    solo = E.sigma_star(np.array([0.25, 0.5, 0.75]), "lognormal")
    assert solo[1, 1] == pytest.approx(0.25 / st.norm.pdf(0.0) ** 2, rel=1e-12)
    assert solo[1, 1] == pytest.approx(0.25 * 2.0 * np.pi, rel=1e-12)

    # positive definite -> the GLS whitening is legitimate
    assert np.all(np.linalg.eigvalsh(cov) > 0)


def test_b2_sigma_star_pareto_uses_exponential_member():
    """Pareto I's standard member is the EXPONENTIAL (Table 3.4), so f_*(F_*^-1(p)) = 1-p."""
    p = np.array([0.1, 0.5, 0.9])
    cov = E.sigma_star(p, "pareto1")
    expected_11 = 0.1 * 0.9 / ((1 - 0.1) * (1 - 0.1))
    assert cov[0, 0] == pytest.approx(expected_11, rel=1e-12)
    member = E.STANDARD_MEMBERS["pareto1"]
    assert member.name == "exponential"
    assert member.ppf(np.array([0.5]))[0] == pytest.approx(np.log(2.0))


# (c) gQLS recovers (mu, sigma) on simulated normal data ------------------------------
def test_c_gqls_recovers_normal_parameters_monte_carlo():
    """Known-truth check: 300 replicates of n=2000 normals, MC-tolerance recovery."""
    mu_true, sigma_true = 3.0, 1.7
    rng = np.random.default_rng(4242)
    reps = 300
    mus = np.empty(reps)
    sigmas = np.empty(reps)
    for i in range(reps):
        x = rng.normal(mu_true, sigma_true, size=2000)
        fit = E.gqls(x, 0.05, 0.95, 15, "lognormal")
        mus[i], sigmas[i] = fit.mu, fit.sigma

    # unbiased to within the Monte-Carlo standard error of the mean (~3 s.e.)
    assert mus.mean() == pytest.approx(mu_true, abs=3 * mus.std(ddof=1) / np.sqrt(reps) + 5e-3)
    assert sigmas.mean() == pytest.approx(
        sigma_true, abs=3 * sigmas.std(ddof=1) / np.sqrt(reps) + 5e-3
    )
    # and each replicate is in the right neighbourhood
    assert np.median(np.abs(mus - mu_true)) < 0.1
    assert np.median(np.abs(sigmas - sigma_true)) < 0.1


def test_c2_gqls_beats_oqls_on_cauchy_efficiency():
    """The whole point of Sigma_*: gQLS is far more efficient than oQLS for a heavy member.

    Thesis Table 3.2 vs 3.3 (k=25, (0.05,0.95)): ARE 0.995 for gQLS-Cauchy versus 0.232
    for oQLS-Cauchy. The variance ratio here should be lopsided in the same direction.
    """
    rng = np.random.default_rng(7)
    reps = 200
    g = np.empty(reps)
    o = np.empty(reps)
    for i in range(reps):
        x = st.cauchy.rvs(loc=0.0, scale=1.0, size=500, random_state=rng)
        g[i] = E.gqls(x, 0.05, 0.95, 15, "log-cauchy").sigma
        o[i] = E.oqls(x, 0.05, 0.95, 15, "log-cauchy").sigma
    assert g.std(ddof=1) < o.std(ddof=1)
    assert np.median(np.abs(g - 1.0)) < np.median(np.abs(o - 1.0))


# (d) oQLS equals the closed-form regression -----------------------------------------
def test_d_oqls_equals_closed_form_simple_regression(log_dollars: np.ndarray):
    """oQLS is literally OLS of empirical log-quantiles on standard quantiles."""
    a, b, k, family = 0.05, 0.95, 8, "lognormal"
    p = E.p_grid(a, b, k)
    y = E.sample_log_quantiles(log_dollars, p, method="hazen")
    z = E.STANDARD_MEMBERS[family].ppf(p)

    # textbook simple-regression closed form, written out independently of the module
    zbar, ybar = z.mean(), y.mean()
    slope = np.sum((z - zbar) * (y - ybar)) / np.sum((z - zbar) ** 2)
    intercept = ybar - slope * zbar

    fit = E.oqls(log_dollars, a, b, k, family, method="hazen")
    assert fit.mu == pytest.approx(intercept, rel=1e-12)
    assert fit.sigma == pytest.approx(slope, rel=1e-12)

    # and the same via explicit normal equations (X'X)^-1 X'Y
    design = E.design_matrix(p, family)
    beta = np.linalg.solve(design.T @ design, design.T @ y)
    assert fit.mu == pytest.approx(beta[0], rel=1e-10)
    assert fit.sigma == pytest.approx(beta[1], rel=1e-10)

    # oQLS and gQLS must NOT coincide — Sigma_* is not proportional to the identity
    assert E.gqls(log_dollars, a, b, k, family, method="hazen").sigma != pytest.approx(
        fit.sigma, abs=1e-6
    )


# (e) W is chi2_{k-2}-calibrated under H_0 --------------------------------------------
def test_e_W_is_chi2_km2_calibrated_under_null():
    """500 replicates from the null family; KS against chi2_{k-2}, loose tolerance.

    The statistic is asymptotic (Proposition 5.2), so at finite n we only demand that
    the null distribution is not grossly miscalibrated: KS p-value above 0.01 and the
    mean within 25% of the nominal df.
    """
    k, n, reps = 8, 400, 500
    df = k - 2
    rng = np.random.default_rng(31337)
    stats = np.empty(reps)
    for i in range(reps):
        x = rng.normal(10.0, 2.0, size=n)  # H_0: lognormal in dollars <=> normal in logs
        fit = E.gqls(x, 0.05, 0.95, k, "lognormal")
        stats[i] = E.W(x, fit)["W"]

    assert np.all(np.isfinite(stats))
    ks = st.kstest(stats, "chi2", args=(df,))
    assert ks.pvalue > 0.01, f"W badly miscalibrated vs chi2_{df} (KS p={ks.pvalue:.4g})"
    assert stats.mean() == pytest.approx(df, rel=0.25)
    # and the nominal 5% level rejects roughly 5% of the time
    reject_rate = float(np.mean(st.chi2.sf(stats, df) < 0.05))
    assert 0.01 < reject_rate < 0.15


def test_e2_W_out_grid_and_modes(log_dollars: np.ndarray):
    """W_out reads the universal r-level grid and offers both p-value references."""
    fit = E.gqls(log_dollars, 0.05, 0.95, 8, "lognormal", method=E.THESIS_QUANTILE_METHOD)
    chi2_result = E.W_out(log_dollars, fit, r=25, mode="chi2")
    assert chi2_result["df"] == 23  # r - 2
    assert chi2_result["mode"] == "chi2"
    assert 0.0 <= chi2_result["p_value"] <= 1.0

    boot = E.W_out(log_dollars, fit, r=25, mode="bootstrap", B=60, seed=11)
    assert boot["W_out"] == pytest.approx(chi2_result["W_out"], rel=1e-12)
    assert boot["mode"] == "bootstrap"
    assert 0.0 <= boot["p_value"] <= 1.0
    # deterministic given the seed
    assert (
        E.W_out(log_dollars, fit, r=25, mode="bootstrap", B=60, seed=11)["p_value"]
        == boot["p_value"]
    )
    with pytest.raises(ValueError):
        E.W_out(log_dollars, fit, r=2)


# (f) Table 6.8's summary statistics ---------------------------------------------------
def test_f_table_6_8_summary_statistics(damages: np.ndarray, tables: dict):
    """The data-identity gate: hazen quartiles + ddof=1 sd reproduce the published row."""
    pub = tables["table_6_8"]
    assert damages.size == pub["n"] == 30
    assert damages.min() == pytest.approx(pub["min"], abs=1e-4)
    assert np.quantile(damages, 0.25, method="hazen") == pytest.approx(pub["q1"], abs=1e-4)
    assert np.quantile(damages, 0.50, method="hazen") == pytest.approx(pub["q2"], abs=1e-4)
    assert np.quantile(damages, 0.75, method="hazen") == pytest.approx(pub["q3"], abs=1e-4)
    assert damages.max() == pytest.approx(pub["max"], abs=1e-4)
    assert damages.mean() == pytest.approx(pub["mean"], abs=1e-4)
    assert damages.std(ddof=1) == pytest.approx(pub["std_dev"], abs=1e-4)


def test_f2_hazen_is_required_for_the_published_quartiles(damages: np.ndarray, tables: dict):
    """Guards the convention itself: 'linear' (numpy's default) misses q1/q3."""
    pub = tables["table_6_8"]
    assert np.quantile(damages, 0.25, method="linear") != pytest.approx(pub["q1"], abs=1e-3)
    assert E.SUMMARY_QUANTILE_METHOD == "hazen"


# (g) MLE-lognormal anchors, clean and contaminated -------------------------------------
def test_g_mle_lognormal_reproduces_published_anchors(log_dollars: np.ndarray, tables: dict):
    """22.8002 / 0.8339 clean; 22.8769 / 1.0975 under the thesis's 10x modification."""
    clean = E.mle(log_dollars, "lognormal")
    assert clean.mu == pytest.approx(22.8002, abs=1e-4)
    assert clean.sigma == pytest.approx(0.8339, abs=1e-4)

    modified = E.mle(S.inflate_max(log_dollars, 10.0), "lognormal")
    assert modified.mu == pytest.approx(22.8769, abs=1e-4)
    assert modified.sigma == pytest.approx(1.0975, abs=1e-4)

    # ...and both round to the published Table 6.10 cells
    pub_clean = tables["table_6_10"]["estimators"]["MLE"]["lognormal"]
    pub_mod = tables["table_6_10"]["estimators"]["MLE*"]["lognormal"]
    assert round(clean.mu, 2) == pub_clean["mu"]
    assert round(clean.sigma, 2) == pub_clean["sigma"]
    assert round(modified.mu, 2) == pub_mod["mu"]
    assert round(modified.sigma, 2) == pub_mod["sigma"]

    # the headline non-robustness: sigma-hat moves 0.83 -> 1.10, a 31.6% jump
    assert modified.sigma / clean.sigma > 1.3


def test_g2_pareto1_mle_is_the_boundary_closed_form(log_dollars: np.ndarray, tables: dict):
    """mu_hat = log(theta_hat) = min(x); sigma_hat = 1/alpha_hat = mean(x) - min(x)."""
    fit = E.mle(log_dollars, "pareto1")
    assert fit.mu == pytest.approx(float(np.min(log_dollars)), rel=1e-12)
    assert fit.sigma == pytest.approx(
        float(np.mean(log_dollars) - np.min(log_dollars)), rel=1e-12
    )
    pub = tables["table_6_10"]["estimators"]["MLE"]["pareto1"]
    assert round(fit.mu, 2) == pub["mu"]
    assert round(fit.sigma, 2) == pub["sigma"]


# (h) the Sigma-star falsifier ---------------------------------------------------------
def test_h_sigma_star_falsifier_o2_vs_g2_log_cauchy(log_dollars: np.ndarray, tables: dict):
    """If Sigma_* were mis-specified, o2 and g2 would not split 0.23 vs 0.49.

    This is the study's single sharpest specification check: for log-Cauchy at
    (a,b) = (0.05, 0.95), OLS on the quantile scale (which pretends Sigma_* = I) gives
    sigma-hat = 0.23, while GLS through the true Sigma_* gives 0.49 — a factor of 2.1.
    Both are compared to the COMMITTED Table 6.10 transcription, under the thesis's own
    quantile convention, at the study's 0.005 reporting-resolution tolerance.
    """
    pub_o2 = tables["table_6_10"]["estimators"]["o2"]["log-cauchy"]["sigma"]
    pub_g2 = tables["table_6_10"]["estimators"]["g2"]["log-cauchy"]["sigma"]
    assert (pub_o2, pub_g2) == (0.23, 0.49)  # the transcription itself is pinned

    meth = E.THESIS_QUANTILE_METHOD
    o2 = E.oqls(log_dollars, 0.05, 0.95, 8, "log-cauchy", method=meth)
    g2 = E.gqls(log_dollars, 0.05, 0.95, 8, "log-cauchy", method=meth)

    assert o2.sigma == pytest.approx(pub_o2, abs=0.005), (
        f"oQLS log-Cauchy sigma-hat {o2.sigma:.4f} != published {pub_o2} — "
        "the design matrix or the standard member is wrong"
    )
    assert g2.sigma == pytest.approx(pub_g2, abs=0.005), (
        f"gQLS log-Cauchy sigma-hat {g2.sigma:.4f} != published {pub_g2} — "
        "Sigma_* (eq. 2.1) is mis-specified"
    )
    assert g2.sigma / o2.sigma == pytest.approx(pub_g2 / pub_o2, rel=0.05)

    # the mu's agree even though the sigmas do not — the split is a SCALE phenomenon
    assert o2.mu == pytest.approx(
        tables["table_6_10"]["estimators"]["o2"]["log-cauchy"]["mu"], abs=0.005
    )

    # gQLS logs its whitening condition number, and it is large for a heavy member
    assert g2.sigma_star_cond is not None and g2.sigma_star_cond > 100.0
    assert E.gqls(log_dollars, 0.05, 0.95, 8, "lognormal").sigma_star_cond < g2.sigma_star_cond


def test_h2_full_table_6_9_grid_under_the_thesis_convention(log_dollars: np.ndarray, tables: dict):
    """RQ1's whole object: 36 published gQLS parameters, one from-scratch pass.

    Tolerance 0.02 is the study's `max_abs_param_deviation` guardrail. The single
    outlier is the (0.10, 0.90) log-Gumbel mu, which Table 6.9 prints as 22.34 while
    Table 6.10's g3 row prints 22.36 for the same fit — a documented internal
    inconsistency in the thesis (see reference/thesis_tables.json known_discrepancies).
    """
    meth = E.THESIS_QUANTILE_METHOD
    deviations = []
    for trim in tables["table_6_9"]["trims"].values():
        a, b = trim["a"], trim["b"]
        for family in E.FAMILIES:
            fit = E.gqls(log_dollars, a, b, 8, family, method=meth)
            deviations += [abs(fit.mu - trim[family]["mu"]), abs(fit.sigma - trim[family]["sigma"])]
    deviations = np.array(deviations)
    assert deviations.size == 36
    assert deviations.mean() < 0.005
    assert deviations.max() <= 0.02
    assert np.sum(deviations > 0.005) <= 1  # only the documented log-Gumbel cell


def test_h3_the_documented_thesis_internal_inconsistency(log_dollars: np.ndarray, tables: dict):
    """Our g3 log-Gumbel mu agrees with Table 6.10 (22.36), not Table 6.9 (22.34)."""
    fit = E.gqls(log_dollars, 0.10, 0.90, 8, "log-gumbel", method=E.THESIS_QUANTILE_METHOD)
    assert tables["table_6_9"]["trims"]["0.10_0.90"]["log-gumbel"]["mu"] == 22.34
    assert tables["table_6_10"]["estimators"]["g3"]["log-gumbel"]["mu"] == 22.36
    assert round(fit.mu, 2) == 22.36


# (i) the log-Cauchy moment guard -----------------------------------------------------
def test_i_log_cauchy_moments_raise(log_dollars: np.ndarray):
    """No finite mean means NO number — not a big one. The refusal is the teaching."""
    fit = E.gqls(log_dollars, 0.05, 0.95, 8, "log-cauchy")

    with pytest.raises(NotImplementedError, match="no finite moments|NO finite moments"):
        E.mean_loss(fit)
    with pytest.raises(NotImplementedError, match="no finite moments|NO finite moments"):
        E.cte(fit, 0.99)

    # ...but a QUANTILE is perfectly well defined, and that is how the family is priced
    rl = E.return_level(fit, 0.99)
    assert np.isfinite(rl) and rl > 0.0

    # a family WITH finite moments must still work
    ln = E.gqls(log_dollars, 0.05, 0.95, 8, "lognormal")
    assert np.isfinite(E.mean_loss(ln)) and E.mean_loss(ln) > 0.0
    assert E.cte(ln, 0.99) > E.return_level(ln, 0.99)


def test_i2_return_level_amplification_hazard(log_dollars: np.ndarray):
    """tan(0.49*pi) = 31.82: the log-Cauchy 1-in-100 is astronomically sigma-sensitive."""
    z99 = float(E.STANDARD_MEMBERS["log-cauchy"].ppf(np.array([0.99]))[0])
    assert z99 == pytest.approx(np.tan(0.49 * np.pi), rel=1e-12)
    assert z99 == pytest.approx(31.82, abs=0.02)

    fit = E.gqls(log_dollars, 0.05, 0.95, 8, "log-cauchy", method=E.THESIS_QUANTILE_METHOD)
    bumped = E.Fit(**{**fit.__dict__, "sigma": fit.sigma + 0.04})
    ratio = E.return_level(bumped, 0.99) / E.return_level(fit, 0.99)
    assert ratio == pytest.approx(np.exp(0.04 * z99), rel=1e-9)
    assert ratio > 3.0  # a 0.04 parameter move triples the decision number

    # the lognormal's z_0.99 = 2.326 makes the same move a ~10% change
    ln_ratio = np.exp(0.04 * float(st.norm.ppf(0.99)))
    assert ln_ratio < 1.15


# stress.py --------------------------------------------------------------------------
def test_stress_perturbations(log_dollars: np.ndarray, damages: np.ndarray):
    """leave_top_k_out drops the k largest; inflate_max is an exact log(factor) bump."""
    dropped = S.leave_top_k_out(log_dollars, 2)
    assert dropped.size == 28
    assert dropped.max() < np.sort(log_dollars)[-3] + 1e-12
    assert S.leave_top_k_out(log_dollars, 0).size == 30

    inflated = S.inflate_max(log_dollars, 10.0)
    assert inflated.size == 30
    assert inflated.max() == pytest.approx(np.log(723.03 * 1e9), rel=1e-12)
    assert np.sum(~np.isclose(inflated, log_dollars)) == 1  # exactly one point moved

    boots = S.bootstrap_samples(log_dollars, B=5, seed=3)
    assert len(boots) == 5 and all(b.size == 30 for b in boots)
    assert np.array_equal(boots[0], S.bootstrap_samples(log_dollars, B=5, seed=3)[0])

    cases = S.default_stress_set(log_dollars)
    assert [c.label for c in cases] == [
        "leave_top_1_out",
        "leave_top_2_out",
        "leave_top_3_out",
        "inflate_max_x10",
    ]


def test_instability_pct_is_a_max_over_the_stress_set(log_dollars: np.ndarray):
    """The decision metric: max |%delta| of the fitted 1-in-100 return level."""
    def fits(sample: np.ndarray) -> E.Fit:
        return E.gqls(sample, 0.05, 0.95, 8, "lognormal", method=E.THESIS_QUANTILE_METHOD)

    out = S.instability_pct(fits, log_dollars, S.default_stress_set(log_dollars), p=0.99)

    assert out["n_cases"] == 4
    assert out["p"] == 0.99
    assert out["baseline_return_level"] == pytest.approx(
        E.return_level(fits(log_dollars), 0.99), rel=1e-12
    )
    assert out["instability_pct"] == max(
        v["pct_change"] for v in out["per_case"].values()
    )
    assert out["instability_pct"] == out["per_case"][out["worst_case"]]["pct_change"]
    assert out["instability_pct"] >= 0.0

    # an empty stress set is an error, not a silent zero
    with pytest.raises(ValueError):
        S.instability_pct(fits, log_dollars, [])

    # a no-op stress must score exactly 0
    zero = S.instability_pct(
        fits, log_dollars, [S.StressCase("identity", log_dollars.copy())]
    )
    assert zero["instability_pct"] == pytest.approx(0.0, abs=1e-9)


def test_transcription_shape(tables: dict):
    """The committed JSON has every cell the study's metrics will read."""
    assert len(tables["table_6_9"]["trims"]) == 3
    for trim in tables["table_6_9"]["trims"].values():
        for family in E.FAMILIES:
            assert set(trim[family]) == {"mu", "sigma", "W", "p_W", "W_out", "p_Wout"}
    estimators = tables["table_6_10"]["estimators"]
    assert set(estimators) == {"MLE", "MLE*", "o2", "o2*", "o3", "o3*", "g2", "g2*", "g3", "g3*"}
    for row in estimators.values():
        assert set(row) == set(E.FAMILIES)
        for cell in row.values():
            assert set(cell) == {"mu", "sigma"}
    counts = tables["_provenance"]["cell_counts"]
    assert counts == {"table_6_8": 8, "table_6_9": 108, "table_6_10": 120, "total": 236}
