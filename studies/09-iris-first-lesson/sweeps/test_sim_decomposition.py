"""Unit tests for the study 09 simulation lane (sim_dgp.py).

Registered checks: (1) the ddof=0 decomposition identity on a tiny real run;
(2) a hand-computed 3-fit example pins the ddof=0 convention; (3) analytic p*
sanity on all four DGPs; (4) seed-domain and truth-sample reproducibility;
(5) the recorded-failure path (always-raising model -> k_effective=0 + a row
in sim_cells_failed.tsv, never a crash).

Run:  uv run --no-sync python -m pytest -p no:cacheprovider <this file>
(the cacheprovider stays off so pytest writes nothing outside the scratchpad).
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sim_dgp  # noqa: E402

# WRITE-ONLY-SCRATCHPAD: all test artifacts stay next to this file, never in
# pytest's system tmp_path and never under the read-only study repo.
_TEST_TMP = Path(__file__).resolve().parent / "_test_tmp"


def test_identity_holds_on_tiny_real_run():
    """1 DGP (G1), n=20, 5 draws, M=256 — identity to 1e-12 for all 6 models."""
    ni = sim_dgp.N_GRID.index(20)
    for model in sim_dgp.MODEL_NAMES:
        cell = sim_dgp.run_cell(0, ni, model, reps=5, truth_m=256)
        assert cell["k_effective"] == 5, (model, cell["failures"])
        assert cell["check_abs_err"] <= 1e-12, (model, cell["check_abs_err"])
        assert np.isfinite(cell["total"]) and np.isfinite(cell["mc_se"])


def test_ddof0_convention_hand_computed():
    """3 fits x 2 truth points, every aggregate checked against hand arithmetic."""
    P = np.array([[0.2, 0.7], [0.4, 0.5], [0.9, 0.6]])
    p_star = np.array([0.5, 0.25])
    cell = sim_dgp.decompose(P, p_star)
    # point 1: pbar=0.5, bias2=0, var=(0.09+0.01+0.16)/3=0.26/3, irr=0.25
    # point 2: pbar=0.6, bias2=0.1225, var=(0.01+0.01+0)/3=0.02/3, irr=0.1875
    assert cell["k_effective"] == 3
    assert abs(cell["irr"] - 0.21875) < 1e-15
    assert abs(cell["bias2"] - 0.06125) < 1e-15
    assert abs(cell["var"] - 0.14 / 3.0) < 1e-15
    # per-draw mean risks: 0.365, 0.255, 0.36 -> TOTAL = 0.98/3
    assert abs(cell["total"] - 0.98 / 3.0) < 1e-15
    assert cell["check_abs_err"] <= 1e-15
    per_draw = np.array([0.365, 0.255, 0.36])
    expect_se = per_draw.std(ddof=1) / np.sqrt(3.0)
    assert abs(cell["mc_se"] - expect_se) < 1e-15
    # ddof=0 is load-bearing: the ddof=1 variant must NOT satisfy the identity
    var1 = P.var(axis=0, ddof=1).mean()
    assert abs(cell["total"] - (cell["irr"] + cell["bias2"] + var1)) > 1e-3


def test_p_star_sanity():
    g1, g2, g3, g4 = sim_dgp.DGPS
    # G1 on the boundary: exactly 1/2
    assert abs(float(g1.p_star(np.array([[0.0, 0.0]]))[0]) - 0.5) < 1e-12
    # G1 closed form expit(2*x1) cross-checks the density route
    xs = np.array([[0.3, -1.2], [-2.0, 0.7], [1.5, 3.0]])
    from scipy.special import expit
    assert np.allclose(g1.p_star(xs), expit(2.0 * xs[:, 0]), atol=1e-12)
    # G2's p* ignores the 16 noise dims and matches G1 on the signal dims
    x18 = np.hstack([xs, np.full((3, 16), 7.7)])
    assert np.allclose(g2.p_star(x18), g1.p_star(xs), atol=1e-15)
    # G4 deep inside a class-1 component
    assert float(g4.p_star(np.array([[1.0, 1.0]]))[0]) > 0.9
    # balanced DGPs: mean p* on the registered truth sample near 1/2
    for gi in range(4):
        _, p_star = sim_dgp.truth_sample(gi)
        assert 0.45 <= float(p_star.mean()) <= 0.55, (gi, float(p_star.mean()))


def test_seed_domain_and_truth_reproducibility():
    seeds = sim_dgp.all_seeds()
    assert len(seeds) == 1 + 4 + 4 * 7 * 100
    assert min(seeds) >= 0 and max(seeds) < 2**32
    with pytest.raises(AssertionError):
        sim_dgp._seed_ok(2**32)
    with pytest.raises(AssertionError):
        sim_dgp._seed_ok(-1)
    # same seed -> byte-identical truth sample (sha256 of the array bytes)
    for gi in range(4):
        xa, pa = sim_dgp.truth_sample(gi)
        xb, pb = sim_dgp.truth_sample(gi)
        assert hashlib.sha256(xa.tobytes()).hexdigest() == \
               hashlib.sha256(xb.tobytes()).hexdigest()
        assert hashlib.sha256(pa.tobytes()).hexdigest() == \
               hashlib.sha256(pb.tobytes()).hexdigest()
    # distinct DGPs use distinct truth seeds
    assert len({sim_dgp.truth_seed(g) for g in range(4)}) == 4


class _AlwaysRaises:
    def fit(self, X, y):
        raise RuntimeError("registered failure-path probe")


def test_failure_recording_path():
    out = _TEST_TMP / "failure_path"
    if out.exists():
        shutil.rmtree(out)
    registry = {"boom": _AlwaysRaises}
    run = sim_dgp.run_grid(
        out, cells=[(0, sim_dgp.N_GRID.index(20), "boom")],
        reps=3, truth_m=64, model_registry=registry, n_jobs=1,
    )
    try:
        (r,) = run["results"]
        assert r["k_effective"] == 0
        assert np.isnan(r["total"]) and np.isnan(r["check_abs_err"])
        assert run["n_failures"] == 3
        fail_lines = (out / "sim_cells_failed.tsv").read_text().splitlines()
        assert fail_lines[0] == "dgp\tn\tmodel\trep\terror"
        assert len(fail_lines) == 4  # header + one row per failed draw
        first = fail_lines[1].split("\t")
        assert first[:4] == ["G1-linear-match", "20", "boom", "0"]
        assert "RuntimeError" in first[4]
        # the k=0 cell is still published in sim_risk.tsv (nan metrics)
        risk_lines = (out / "sim_risk.tsv").read_text().splitlines()
        assert len(risk_lines) == 2
        row = risk_lines[1].split("\t")
        assert row[3] == "0" and row[7] == "nan"
    finally:
        shutil.rmtree(out, ignore_errors=True)
