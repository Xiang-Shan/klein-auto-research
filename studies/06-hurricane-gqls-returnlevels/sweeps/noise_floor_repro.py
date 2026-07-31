"""Phase-0 measurement: the reproduction track's floor (sweep-rules.md carve-out).

Promotes NO winner and writes NO `results.tsv` row — a measurement is not a search.
Three candidate floors are measured, and the honest answer is that only one of them is
a *floor* at all:

1. **Numerical floor.** Every fit here is a 2-parameter GLS solve on 8 points. Re-running
   it is bit-identical (spread EXACTLY 0), and solving the same normal equations by an
   independent route — explicit ``(X' S*^-1 X)^-1 X' S*^-1 Y`` via a dense linear solve,
   instead of `estimators.gqls`'s Cholesky-whitened least squares — agrees to ~1e-16.
   There is no stochastic component to average over: **recording ~0 IS the finding**, and
   it means every disagreement with the published tables is a MODELING CHOICE, never
   solver noise.
2. **Reporting-resolution floor = 0.005.** Table 6.9 prints two decimals, so a published
   22.79 is any true value in [22.785, 22.795). No reproduction difference smaller than
   half the last printed digit can be evidence about anything.
3. **Convention spread (this sweep's k=5 cells).** The five sample-quantile conventions
   — the thesis's own ``inverted_cdf``, the descriptive table's ``hazen``, and three
   plotting-position variants — are not noise: each is a defensible DEFINITION of an
   empirical quantile, and at n = 30 they disagree by far more than the reporting
   resolution. This is a *specification* spread, not a sampling spread, so it may not be
   folded into `minimum_delta`: once a candidate FIXES the convention it is a constant,
   not a fluctuation. It is measured here because its size is the study's own RQ (the
   pre-registered prediction "convention spread EXCEEDS 0.005"), and because a
   `minimum_delta` chosen while the convention is still floating would be meaningless.

Recommendation printed at the end: ``minimum_delta = 0.005`` — resolution-governed, the
binding floor once the convention is FIXED by a kept candidate.

Run from the study directory:  uv run --no-sync python sweeps/noise_floor_repro.py
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analysis as A
import estimators as E
import numpy as np
import scipy.linalg as sla

from kleinlib.sweep import SweepRunner


def convention_cell(params: dict) -> dict:
    """One cell = the full 18-cell Table-6.9 grid fitted under one quantile convention."""
    primary, _extra = A.grid(str(params["convention"]))
    return {"primary_metric": primary, "status": "ok"}


def gls_via_normal_equations(
    x: np.ndarray, a: float, b: float, k: int, family: str, method: str
) -> tuple[float, float]:
    """`beta = (X' S*^-1 X)^-1 X' S*^-1 Y`, formed explicitly — an INDEPENDENT route.

    `estimators.gqls` never touches `S*^-1`: it factors `S* = L L'` and runs least
    squares on the whitened system. Solving the normal equations with a dense solver
    instead exercises a different code path through LAPACK, so the gap between the two
    answers is a genuine numerical-floor measurement rather than a re-run.
    """
    p = E.p_grid(a, b, k)
    y = E.sample_log_quantiles(x, p, method=method)
    design = E.design_matrix(p, family)
    cov = E.sigma_star(p, family)
    solved = sla.solve(cov, np.column_stack([design, y]))
    cov_inv_x, cov_inv_y = solved[:, :2], solved[:, 2]
    beta = np.linalg.solve(design.T @ cov_inv_x, design.T @ cov_inv_y)
    return float(beta[0]), float(beta[1])


def numerical_floor(convention: str) -> tuple[float, float]:
    """(re-run spread, independent-route spread) of the grid's mean |dtheta|."""
    first, _ = A.grid(convention)
    second, _ = A.grid(convention)
    x = A.sample()
    devs: list[float] = []
    for trim in A.tables()["table_6_9"]["trims"].values():
        a, b = float(trim["a"]), float(trim["b"])
        for family in E.FAMILIES:
            mu, sigma = gls_via_normal_equations(x, a, b, A.K_DEFAULT, family, convention)
            devs += [
                abs(mu - float(trim[family]["mu"])),
                abs(sigma - float(trim[family]["sigma"])),
            ]
    return abs(second - first), abs(float(np.mean(devs)) - first)


def main() -> None:
    runner = SweepRunner(
        "noise_floor_repro",
        Path(__file__).resolve().parents[1],
        convention_cell,
        [{"convention": c} for c in A.CONVENTIONS],
        metric_goal="lower",
    )
    summary = runner.run()
    print(f"\nmeasurement sweep complete: {len(runner.params_list)} cells -> {runner.sidecar_path}")

    values = [t.primary_metric for t in summary.trials if t.primary_metric is not None]
    print("\n=== cell results (primary = mean |dtheta| over Table 6.9's 36 parameters) ===")
    for convention, value in zip(A.CONVENTIONS, values, strict=True):
        print(f"  {convention:>16s}  {value:.6f}")
    spread = max(values) - min(values)
    print(f"  {'spread (range)':>16s}  {spread:.6f}")
    print(f"  {'std (ddof=1)':>16s}  {statistics.stdev(values):.6f}")

    default = A.CONVENTIONS[1]  # "hazen" — train.py's registered default
    rerun_gap, route_gap = numerical_floor(default)
    print(f"\n=== numerical floor (convention = {default}) ===")
    print(f"  identical re-run                       : {rerun_gap:.3e}   (deterministic)")
    print(f"  independent normal-equations route     : {route_gap:.3e}")

    print("\n=== floors, and which one binds ===")
    print(f"  numerical (solver route)   : {max(rerun_gap, route_gap):.3e}   <- not binding")
    print(f"  reporting resolution       : {A.REPORTING_RESOLUTION:.3f}         <- BINDS")
    print(
        f"  convention spread          : {spread:.6f}      <- specification, NOT noise: "
        "constant once a kept candidate fixes the convention"
    )
    print(
        f"\nRECOMMENDATION  minimum_delta = {A.REPORTING_RESOLUTION} "
        "(reporting-resolution-governed). The convention spread is measured, reported, "
        "and deliberately NOT folded in: it is a modeling choice the ladder resolves, "
        "not a fluctuation the metric must tolerate."
    )


if __name__ == "__main__":
    main()
