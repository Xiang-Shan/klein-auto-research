"""sim_dgp.py — study 09-iris-first-lesson SIMULATION LANE (known-DGP bias-variance lab).

The empirical lane's privilege gap, closed the study-03 way: in a synthetic lab
the truth is available for scoring, never for fitting. Binary Y ~ Bernoulli(p*(x))
is NEVER sampled for scoring — every risk below is the analytic expectation over
Y (E_Y Brier), so the only Monte Carlo left is over training draws and the fixed
truth-sample grid. LANE vocabulary (study.yaml VOCABULARY LAW): this is the
simulation LANE — never a "track"; klein ledger tracks are primary/challenger
and this script touches neither.

Registered design (verbatim):

  Four two-class, balanced DGPs with analytic p*(x); binary Y ~ Bernoulli(p*(x))
  never sampled for scoring (analytic E_Y):
  - G1 "linear-match": X|class=± ~ N(μ±, I₂), μ± = (±1, 0). Equal covariance ⇒
    linear Bayes boundary; p*(x) via the two Gaussian densities (priors 0.5/0.5).
  - G2 "irrelevant-dims": G1's two signal dims + 16 iid N(0,1) irrelevant dims
    appended (18 features; the noise dims are class-independent). p*(x) identical
    to G1 (depends on the 2 signal dims only).
  - G3 "unequal-cov": μ± = (±0.5, 0); Σ₀ = I₂ for class −; Σ₁ =
    R(45°)·diag(2.25, 0.25)·R(45°)ᵀ for class +. p*(x) via the two Gaussian
    densities.
  - G4 "xor": Gaussian mixture, components at (±1, ±1) with covariance 0.25·I₂
    (σ=0.5), class 1 = components {(1,1), (−1,−1)}, class 0 = {(1,−1), (−1,1)},
    equal component weights. p*(x) via the 4-component mixture densities.

  Models (6; sklearn, frozen configs matching study 08's family definitions with
  seed 20260909): lda = LDA(solver="svd"); slda = LDA(solver="lsqr",
  shrinkage="auto"); qda = QDA(reg_param=0.1); logit_l2 = Pipeline(StandardScaler,
  LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", max_iter=1000));
  svm_rbf_platt = CalibratedClassifierCV(Pipeline(StandardScaler, SVC(kernel="rbf",
  C=1.0, gamma="scale", probability=False, random_state=20260909)),
  method="sigmoid", cv=StratifiedKFold(3, shuffle=True, random_state=20260909),
  ensemble=False); hgbt = HistGradientBoostingClassifier(min_samples_leaf=5,
  max_leaf_nodes=4, early_stopping=False, random_state=20260909). NO TabPFN.
  iid simulation ⇒ plain StratifiedKFold inner CV is CORRECT here — the empirical
  lane's StratifiedGroupKFold guards a twin group this lane does not have; there
  are no groups to leak across an inner boundary in an iid draw.

  Grid: n ∈ {8, 12, 20, 30, 60, 120, 500}; 100 independent training draws per
  (DGP, n); training draws are class-balanced by construction (n/2 per class; odd
  folds impossible here since all n even). Seeds: training draw seed =
  2026400000 + dgp_index·100000 + n_index·1000 + rep (dgp_index 0..3, n_index
  0..6, rep 0..99); truth sample seed = 2026900000 + dgp_index. One fixed
  truth-evaluation sample per DGP: M = 4096 points drawn from the DGP marginal
  (mixture over both classes), with p*(x) computed analytically at those points.

Computation per (DGP, n, model): fit on each of the 100 draws; predict p̂_t(x_i)
on the fixed truth sample (probability of class 1). A draw that raises or
returns non-finite probabilities is a RECORDED FAILURE for that (cell, draw) —
logged to sim_cells_failed.tsv (dgp, n, model, rep, error), the run continues,
and the cell's effective k = number of surviving draws (published). Per truth
point over the k surviving fits:

  p̄(x_i)    = mean_t p̂_t(x_i)
  bias²(x_i) = (p̄(x_i) − p*(x_i))²
  var(x_i)   = population variance (ddof=0) of p̂_t(x_i)
  irr(x_i)   = p*(x_i)(1 − p*(x_i))
  risk_t(x_i)= p*(x_i)(1−p*(x_i)) + (p̂_t(x_i) − p*(x_i))²   (per-fit E_Y Brier)

Cell aggregates = means over the 4096 truth points: IRR, BIAS2, VAR,
TOTAL = mean_t mean_i risk_t(x_i), CHECK = IRR + BIAS2 + VAR.
IDENTITY: |TOTAL − CHECK| ≤ 1e-9 must hold in every cell (asserted; it is
algebraic with ddof=0). NO CLIPPING anywhere in these Brier-scale quantities.
MC uncertainty: mc_se = std_t(mean_i risk_t)/sqrt(k) (ddof=1 across draws).

Outputs (ALL under --out; this lane writes NOTHING under studies/):
  sim_risk.tsv          dgp, n, model, k_effective, irr, bias2, var, total,
                        check_abs_err, mc_se — full precision (repr).
  sim_cells_failed.tsv  dgp, n, model, rep, error — header always written;
                        rows only for recorded failures.

Determinism: no wall-clock in any output row (perf_counter timings go to stdout
only, for the lane report); no unseeded randomness; every seed asserted < 2**32.
Seed-domain note: the originally drafted truth base 2026500000 numerically
collided with four training-draw seeds; the collision was disclosed by the lane
build and the truth namespace was RE-REGISTERED pre-consult as 2026900000+dgp
(program.md Decisions 2026-08-27). The registry is now fully disjoint.

Run (from the repo root; outputs land in the scratchpad lane directory)::

    uv run --no-sync python <scratchpad>/study09_sim/sim_dgp.py \
        --out <scratchpad>/study09_sim [--n-jobs -1]

Smoke the wiring without spending the sweep: `--smoke` (G1 only, n=20, 5 draws,
M=256; prints a WARNING and must never feed the lane report).

MEASUREMENT sweep (sweep-rules.md carve-out): promotes no winner, writes no
results.tsv row — a measurement is not a search.
"""

from __future__ import annotations

import argparse
import math
import time
import warnings
from pathlib import Path

import numpy as np
from scipy.special import expit, logsumexp
from sklearn.calibration import CalibratedClassifierCV
from sklearn.discriminant_analysis import (
    LinearDiscriminantAnalysis,
    QuadraticDiscriminantAnalysis,
)
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

# ---------------------------------------------------------------------------
# registered constants
# ---------------------------------------------------------------------------

ESTIMATOR_SEED = 20260909                # study 09's frozen estimator seed
N_GRID = (8, 12, 20, 30, 60, 120, 500)   # n_index 0..6, in this order
REPS = 100                               # training draws per (DGP, n)
TRUTH_M = 4096                           # fixed truth-evaluation sample size
DRAW_SEED_BASE = 2026400000              # + dgp_index*100000 + n_index*1000 + rep
TRUTH_SEED_BASE = 2026900000             # + dgp_index
IDENTITY_TOL = 1e-9                      # per-cell |TOTAL - CHECK| hard assert

SEED_DOMAIN = 2**32                      # numpy default_rng accepts more, but the
                                         # registered contract is 32-bit seeds


def _seed_ok(seed: int) -> int:
    """Every seed in this lane must live in [0, 2**32)."""
    assert 0 <= seed < SEED_DOMAIN, f"seed {seed} outside [0, 2**32)"
    return seed


def draw_seed(dgp_index: int, n_index: int, rep: int) -> int:
    assert 0 <= dgp_index <= 3 and 0 <= n_index <= 6 and 0 <= rep <= REPS - 1
    return _seed_ok(DRAW_SEED_BASE + dgp_index * 100000 + n_index * 1000 + rep)


def truth_seed(dgp_index: int) -> int:
    assert 0 <= dgp_index <= 3
    return _seed_ok(TRUTH_SEED_BASE + dgp_index)


def all_seeds() -> list[int]:
    """Every seed this lane can consume (for the seed-domain test)."""
    seeds = [ESTIMATOR_SEED]
    seeds += [truth_seed(g) for g in range(4)]
    seeds += [
        draw_seed(g, ni, rep)
        for g in range(4)
        for ni in range(len(N_GRID))
        for rep in range(REPS)
    ]
    return seeds


# ---------------------------------------------------------------------------
# DGPs — sample_class / sample_marginal / analytic p_star
# ---------------------------------------------------------------------------


def _gauss_logpdf(X: np.ndarray, mu: np.ndarray, cov_inv: np.ndarray, logdet: float) -> np.ndarray:
    d = X.shape[1]
    diff = X - mu
    quad = np.einsum("ij,jk,ik->i", diff, cov_inv, diff)
    return -0.5 * (d * math.log(2.0 * math.pi) + logdet + quad)


class TwoGaussianDGP:
    """X|class=c ~ N(mu_c, cov_c), priors 0.5/0.5; p* via the two densities."""

    def __init__(self, name: str, mu0, mu1, cov0, cov1) -> None:
        self.name = name
        self.mu = (np.asarray(mu0, dtype=float), np.asarray(mu1, dtype=float))
        cov0 = np.asarray(cov0, dtype=float)
        cov1 = np.asarray(cov1, dtype=float)
        self._chol = (np.linalg.cholesky(cov0), np.linalg.cholesky(cov1))
        self._inv = (np.linalg.inv(cov0), np.linalg.inv(cov1))
        self._logdet = (
            float(np.linalg.slogdet(cov0)[1]),
            float(np.linalg.slogdet(cov1)[1]),
        )
        self.dim = self.mu[0].shape[0]

    def sample_class(self, rng: np.random.Generator, cls: int, m: int) -> np.ndarray:
        z = rng.standard_normal((m, self.dim))
        return self.mu[cls] + z @ self._chol[cls].T

    def sample_marginal(self, rng: np.random.Generator, m: int) -> np.ndarray:
        y = rng.integers(0, 2, size=m)
        z = rng.standard_normal((m, self.dim))
        x0 = self.mu[0] + z @ self._chol[0].T
        x1 = self.mu[1] + z @ self._chol[1].T
        return np.where(y[:, None] == 1, x1, x0)

    def p_star(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        l0 = _gauss_logpdf(X, self.mu[0], self._inv[0], self._logdet[0])
        l1 = _gauss_logpdf(X, self.mu[1], self._inv[1], self._logdet[1])
        return expit(l1 - l0)  # equal priors cancel


class IrrelevantDimsDGP:
    """G1's two signal dims + 16 iid N(0,1) class-independent noise dims."""

    def __init__(self, name: str, signal: TwoGaussianDGP, n_noise: int) -> None:
        self.name = name
        self.signal = signal
        self.n_noise = n_noise
        self.dim = signal.dim + n_noise

    def sample_class(self, rng: np.random.Generator, cls: int, m: int) -> np.ndarray:
        xs = self.signal.sample_class(rng, cls, m)
        noise = rng.standard_normal((m, self.n_noise))
        return np.hstack([xs, noise])

    def sample_marginal(self, rng: np.random.Generator, m: int) -> np.ndarray:
        xs = self.signal.sample_marginal(rng, m)
        noise = rng.standard_normal((m, self.n_noise))
        return np.hstack([xs, noise])

    def p_star(self, X: np.ndarray) -> np.ndarray:
        return self.signal.p_star(np.asarray(X, dtype=float)[:, : self.signal.dim])


class XorMixtureDGP:
    """4 components at (±1,±1), cov 0.25·I₂; class 1 = {(1,1),(−1,−1)}."""

    CENTERS = {
        1: np.array([[1.0, 1.0], [-1.0, -1.0]]),
        0: np.array([[1.0, -1.0], [-1.0, 1.0]]),
    }
    SIGMA = 0.5  # component covariance 0.25·I₂

    def __init__(self, name: str) -> None:
        self.name = name
        self.dim = 2

    def sample_class(self, rng: np.random.Generator, cls: int, m: int) -> np.ndarray:
        comp = rng.integers(0, 2, size=m)   # equal component weights within class
        z = rng.standard_normal((m, 2))
        return self.CENTERS[cls][comp] + self.SIGMA * z

    def sample_marginal(self, rng: np.random.Generator, m: int) -> np.ndarray:
        y = rng.integers(0, 2, size=m)
        comp = rng.integers(0, 2, size=m)
        z = rng.standard_normal((m, 2))
        centers = np.where(
            y[:, None] == 1, self.CENTERS[1][comp], self.CENTERS[0][comp]
        )
        return centers + self.SIGMA * z

    def _class_logpdf(self, X: np.ndarray, cls: int) -> np.ndarray:
        var = self.SIGMA**2
        parts = []
        for c in self.CENTERS[cls]:
            diff = X - c
            quad = (diff**2).sum(axis=1) / var
            parts.append(-0.5 * (2 * math.log(2.0 * math.pi * var) + quad))
        return logsumexp(np.stack(parts, axis=0), axis=0)  # + log(0.5) cancels

    def p_star(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        l0 = self._class_logpdf(X, 0)
        l1 = self._class_logpdf(X, 1)
        return expit(l1 - l0)


def _rot45_cov() -> np.ndarray:
    c = math.cos(math.pi / 4.0)
    s = math.sin(math.pi / 4.0)
    R = np.array([[c, -s], [s, c]])
    return R @ np.diag([2.25, 0.25]) @ R.T


_G1 = TwoGaussianDGP("G1-linear-match", (-1.0, 0.0), (1.0, 0.0), np.eye(2), np.eye(2))

DGPS: tuple = (
    _G1,
    IrrelevantDimsDGP("G2-irrelevant-dims", _G1, 16),
    TwoGaussianDGP("G3-unequal-cov", (-0.5, 0.0), (0.5, 0.0), np.eye(2), _rot45_cov()),
    XorMixtureDGP("G4-xor"),
)
DGP_NAMES = tuple(d.name for d in DGPS)


def truth_sample(dgp_index: int, m: int = TRUTH_M) -> tuple[np.ndarray, np.ndarray]:
    """The fixed truth-evaluation sample: X from the marginal, analytic p*."""
    dgp = DGPS[dgp_index]
    rng = np.random.default_rng(truth_seed(dgp_index))
    X = dgp.sample_marginal(rng, m)
    return X, dgp.p_star(X)


def training_draw(dgp_index: int, n_index: int, rep: int) -> tuple[np.ndarray, np.ndarray]:
    """One class-balanced training draw: n/2 per class, class-0 block first."""
    dgp = DGPS[dgp_index]
    n = N_GRID[n_index]
    assert n % 2 == 0, "the registered grid is all-even; balance is by construction"
    m = n // 2
    rng = np.random.default_rng(draw_seed(dgp_index, n_index, rep))
    X0 = dgp.sample_class(rng, 0, m)
    X1 = dgp.sample_class(rng, 1, m)
    X = np.vstack([X0, X1])
    y = np.concatenate([np.zeros(m, dtype=int), np.ones(m, dtype=int)])
    return X, y


# ---------------------------------------------------------------------------
# models — frozen study-08 family configs, seed 20260909, fresh instance per draw
# ---------------------------------------------------------------------------


def _lda():
    return LinearDiscriminantAnalysis(solver="svd")


def _slda():
    return LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")


def _qda():
    return QuadraticDiscriminantAnalysis(reg_param=0.1)


def _logit_l2():
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", max_iter=1000)),
        ]
    )


def _svm_rbf_platt():
    # iid simulation ⇒ plain stratified inner CV is correct here (no twin groups)
    return CalibratedClassifierCV(
        Pipeline(
            [
                ("scale", StandardScaler()),
                ("clf", SVC(kernel="rbf", C=1.0, gamma="scale", probability=False,
                            random_state=ESTIMATOR_SEED)),
            ]
        ),
        method="sigmoid",
        cv=StratifiedKFold(3, shuffle=True, random_state=ESTIMATOR_SEED),
        ensemble=False,
    )


def _hgbt():
    return HistGradientBoostingClassifier(
        min_samples_leaf=5, max_leaf_nodes=4, early_stopping=False,
        random_state=ESTIMATOR_SEED,
    )


MODELS: dict = {
    "lda": _lda,
    "slda": _slda,
    "qda": _qda,
    "logit_l2": _logit_l2,
    "svm_rbf_platt": _svm_rbf_platt,
    "hgbt": _hgbt,
}
MODEL_NAMES = tuple(MODELS)


# ---------------------------------------------------------------------------
# decomposition — the identity lives here (pure function, unit-tested)
# ---------------------------------------------------------------------------


def decompose(P: np.ndarray, p_star: np.ndarray) -> dict:
    """Bias²/variance/irreducible decomposition of mean E_Y Brier over k fits.

    P: (k, M) surviving predicted class-1 probabilities; p_star: (M,) truth.
    ddof=0 population variance across fits makes TOTAL == IRR + BIAS2 + VAR
    an algebraic identity. NO CLIPPING of any quantity.
    """
    P = np.asarray(P, dtype=np.float64)
    p_star = np.asarray(p_star, dtype=np.float64)
    k = P.shape[0]
    irr_i = p_star * (1.0 - p_star)
    pbar_i = P.mean(axis=0)
    bias2_i = (pbar_i - p_star) ** 2
    var_i = P.var(axis=0, ddof=0)
    per_draw = (irr_i[None, :] + (P - p_star[None, :]) ** 2).mean(axis=1)  # (k,)
    total = float(per_draw.mean())
    irr = float(irr_i.mean())
    bias2 = float(bias2_i.mean())
    var = float(var_i.mean())
    check_abs_err = abs(total - (irr + bias2 + var))
    mc_se = float(per_draw.std(ddof=1) / math.sqrt(k)) if k >= 2 else float("nan")
    return {
        "k_effective": k,
        "irr": irr,
        "bias2": bias2,
        "var": var,
        "total": total,
        "check_abs_err": check_abs_err,
        "mc_se": mc_se,
    }


_NAN_CELL = {
    "irr": float("nan"), "bias2": float("nan"), "var": float("nan"),
    "total": float("nan"), "check_abs_err": float("nan"), "mc_se": float("nan"),
}


def _error_string(exc: BaseException) -> str:
    msg = " ".join(f"{type(exc).__name__}: {exc}".split())
    return msg[:300]


# cosmetic-noise filters ONLY — real failures always land in the failure TSV
_SUPPRESSED_WARNINGS = (
    dict(category=FutureWarning, message=".*probability.*"),   # SVC(probability=) deprecation
    dict(category=FutureWarning, message=".*penalty.*"),       # LogisticRegression penalty= (1.8)
    dict(category=UserWarning, message=".*collinear.*"),       # QDA at n=8 in 18-dim G2
)


def run_cell(
    dgp_index: int,
    n_index: int,
    model_name: str,
    reps: int = REPS,
    truth_m: int = TRUTH_M,
    model_registry: dict | None = None,
) -> dict:
    """Fit `reps` seeded draws, score on the fixed truth sample, decompose.

    Returns the published cell aggregates plus the recorded failures and the
    in-worker fit+predict seconds (stdout reporting only — never written to a
    deterministic output row).
    """
    registry = MODELS if model_registry is None else model_registry
    X_truth, p_star = truth_sample(dgp_index, truth_m)
    probs: list[np.ndarray] = []
    failures: list[tuple[int, str]] = []
    t0 = time.perf_counter()
    with warnings.catch_warnings():
        for spec in _SUPPRESSED_WARNINGS:
            warnings.filterwarnings("ignore", **spec)
        for rep in range(reps):
            X, y = training_draw(dgp_index, n_index, rep)
            try:
                model = registry[model_name]()
                model.fit(X, y)
                proba = model.predict_proba(X_truth)
                col = int(np.flatnonzero(model.classes_ == 1)[0])
                p_hat = np.asarray(proba, dtype=np.float64)[:, col]
                if not np.isfinite(p_hat).all():
                    bad = int((~np.isfinite(p_hat)).sum())
                    raise ValueError(f"{bad} non-finite of {truth_m} probabilities")
                probs.append(p_hat)
            except Exception as exc:  # recorded failure — the run continues
                failures.append((rep, _error_string(exc)))
    seconds = time.perf_counter() - t0
    if probs:
        cell = decompose(np.stack(probs, axis=0), p_star)
        assert cell["check_abs_err"] <= IDENTITY_TOL, (
            f"identity broken in cell ({DGP_NAMES[dgp_index]}, n={N_GRID[n_index]}, "
            f"{model_name}): |TOTAL-CHECK| = {cell['check_abs_err']!r}"
        )
    else:
        cell = {"k_effective": 0, **_NAN_CELL}
    return {
        "dgp_index": dgp_index,
        "n_index": n_index,
        "model": model_name,
        **cell,
        "failures": failures,
        "seconds": seconds,
    }


# ---------------------------------------------------------------------------
# grid runner + TSV writers (full-precision repr; nothing wall-clock in a row)
# ---------------------------------------------------------------------------

RISK_COLUMNS = (
    "dgp", "n", "model", "k_effective",
    "irr", "bias2", "var", "total", "check_abs_err", "mc_se",
)
FAIL_COLUMNS = ("dgp", "n", "model", "rep", "error")


def _fmt(value) -> str:
    if isinstance(value, float):
        return repr(value)
    return str(value)


def run_grid(
    out_dir: Path,
    cells: list[tuple[int, int, str]] | None = None,
    reps: int = REPS,
    truth_m: int = TRUTH_M,
    model_registry: dict | None = None,
    n_jobs: int = 1,
) -> dict:
    """Run the cells (registered order), write sim_risk.tsv + sim_cells_failed.tsv."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    registry = MODELS if model_registry is None else model_registry
    if cells is None:
        cells = [
            (g, ni, m)
            for g in range(len(DGPS))
            for ni in range(len(N_GRID))
            for m in registry
        ]
    t0 = time.perf_counter()
    if n_jobs == 1:
        results = [
            run_cell(g, ni, m, reps=reps, truth_m=truth_m, model_registry=model_registry)
            for (g, ni, m) in cells
        ]
    else:
        from joblib import Parallel, delayed

        results = Parallel(n_jobs=n_jobs, prefer="processes")(
            delayed(run_cell)(g, ni, m, reps=reps, truth_m=truth_m,
                              model_registry=model_registry)
            for (g, ni, m) in cells
        )
    wall = time.perf_counter() - t0

    risk_path = out_dir / "sim_risk.tsv"
    fail_path = out_dir / "sim_cells_failed.tsv"
    with risk_path.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(RISK_COLUMNS) + "\n")
        for r in results:
            row = (
                DGP_NAMES[r["dgp_index"]], N_GRID[r["n_index"]], r["model"],
                r["k_effective"], r["irr"], r["bias2"], r["var"], r["total"],
                r["check_abs_err"], r["mc_se"],
            )
            fh.write("\t".join(_fmt(v) for v in row) + "\n")
    n_failures = 0
    with fail_path.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(FAIL_COLUMNS) + "\n")
        for r in results:
            for rep, err in r["failures"]:
                fh.write(
                    "\t".join(
                        _fmt(v)
                        for v in (DGP_NAMES[r["dgp_index"]], N_GRID[r["n_index"]],
                                  r["model"], rep, err)
                    )
                    + "\n"
                )
                n_failures += 1
    return {"results": results, "wall_seconds": wall, "n_failures": n_failures,
            "risk_path": risk_path, "fail_path": fail_path}


def _print_summary(run: dict) -> None:
    results = run["results"]
    per_model: dict[str, float] = {}
    for r in results:
        per_model[r["model"]] = per_model.get(r["model"], 0.0) + r["seconds"]
    print(f"cells: {len(results)}   wall: {run['wall_seconds']:.1f}s   "
          f"recorded failures: {run['n_failures']}")
    print("in-worker fit+predict seconds per model (sums across cells):")
    for m, s in per_model.items():
        print(f"  {m:<14} {s:8.1f}s")
    max_err = max((r["check_abs_err"] for r in results if r["k_effective"] > 0),
                  default=float("nan"))
    print(f"max |TOTAL-CHECK| over populated cells: {max_err!r}")
    fail_cells = [r for r in results if r["failures"]]
    if fail_cells:
        print("cells with recorded failures:")
        for r in fail_cells:
            print(f"  {DGP_NAMES[r['dgp_index']]:<20} n={N_GRID[r['n_index']]:<4} "
                  f"{r['model']:<14} k_effective={r['k_effective']} "
                  f"failed={len(r['failures'])}")
    print(f"wrote {run['risk_path']}")
    print(f"wrote {run['fail_path']}  ({run['n_failures']} failure rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description="study 09 simulation lane (measurement sweep)")
    parser.add_argument("--out", type=Path, required=True,
                        help="output directory (the scratchpad lane dir — never studies/)")
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--smoke", action="store_true",
                        help="wiring smoke: G1 only, n=20, 5 draws, M=256")
    args = parser.parse_args()

    for seed in all_seeds():
        _seed_ok(seed)
    print(f"seed domain OK: {len(all_seeds())} seeds, all < 2**32")

    if args.smoke:
        cells = [(0, N_GRID.index(20), m) for m in MODEL_NAMES]
        run = run_grid(args.out, cells=cells, reps=5, truth_m=256, n_jobs=1)
        _print_summary(run)
        print("WARNING: smoke geometry (5 draws, M=256) — wiring only; "
              "must never feed the lane report.")
    else:
        run = run_grid(args.out, n_jobs=args.n_jobs)
        _print_summary(run)

    print("MEASUREMENT SWEEP: no winner promoted, no results.tsv row "
          "(sweep-rules.md carve-out); simulation LANE — outputs only under --out.")


if __name__ == "__main__":
    main()
