"""e3_breakdown.py — E3 sweep: the contamination-breakdown grid (study 02, RQ2).

Sweep escape-hatch per `.claude/skills/klein/references/sweep-rules.md`: 4 estimators
x eps in {0, 1, 2, 5, 10}% = 20 (estimator, eps) cells, each a 500-rep Monte-Carlo
measurement on the single-family lognormal lab. EVERY cell -> one sidecar row
(`sweeps/e3_breakdown.sidecar.tsv`) with its rep count inside params_json (Phase-1
steer 1). Exactly ONE results.tsv row follows, whose primary is the PRE-REGISTERED
reported cell (program.md): trimmed QLS-OLS at eps=10%. Rule 5 (pickle winner) is n/a
in a simulation study — no model object; the reported cell's config is snapshotted
into train.py (rule 4).

Run:  uv run python studies/02-rqls-pv-severity/sweeps/e3_breakdown.py 2>&1 | tee studies/02-rqls-pv-severity/run.log
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

_STUDY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_STUDY_DIR))  # generator, estimators
sys.path.insert(0, str(_STUDY_DIR.parents[1]))  # repo root for kleinlib

from kleinlib.eval import evaluate_scalar  # noqa: E402
from kleinlib.sweep import SweepRunner  # noqa: E402
from generator import STD_DEDUCTIBLE, STD_LIMIT, PVLossGenerator  # noqa: E402
from estimators import default_p_grid, mle_full, mtm, qls  # noqa: E402

EXPERIMENT_ID = 3
RANDOM_SEED = 42
N = 2000          # policies per Monte-Carlo rep
REPS = 500        # Monte-Carlo reps per cell (pre-registered for E3)
MU_TRUE, SIGMA_TRUE = 9.0, 1.1
D, U = STD_DEDUCTIBLE, STD_LIMIT
EPS_GRID = (0.0, 0.01, 0.02, 0.05, 0.10)
TRIMMED_GRID = default_p_grid(trim=0.15)   # robust QLS grid p in [0.15, 0.85] x 19
MTM_TRIM = 0.10
REPORTED = {"estimator": "qls_ols", "eps": 0.10}  # pre-registered reported cell

ESTIMATORS = {
    "mle": lambda x: mle_full(x, "lognormal"),
    "qls_ols": lambda x: qls(x, 0.0, np.inf, TRIMMED_GRID, "lognormal", weights="ols"),
    "qls_gls": lambda x: qls(x, 0.0, np.inf, TRIMMED_GRID, "lognormal", weights="gls"),
    "mtm": lambda x: mtm(x, trim=MTM_TRIM, family="lognormal"),
}


def run_cell(params: dict) -> dict:
    """One (estimator, eps) cell: REPS-rep MC measurement of premium error vs truth."""
    est, eps = params["estimator"], params["eps"]
    gen = PVLossGenerator(mu=MU_TRUE, sigma=SIGMA_TRUE, single_family=True,
                          contam_eps=eps, deductible=D, limit=U)
    truth = gen.truth_functionals(D, U)["premium"]
    fn = ESTIMATORS[est]
    prem, sigmas = [], []
    for r in range(REPS):
        x = gen.sample(N, seed=RANDOM_SEED + r, incomplete=False, contaminate=True).losses
        fit = fn(x)
        prem.append(fit.premium(D, U))
        sigmas.append(fit.params["sigma"])
    prem, sigmas = np.asarray(prem), np.asarray(sigmas)
    err = np.abs(prem - truth) / truth * 100.0
    return {
        "primary_metric": float(err.mean()),
        "err_sd": float(err.std(ddof=1)),
        "prem_bias_pct": float((prem - truth).mean() / truth * 100.0),
        "rmse_sigma": float(np.sqrt(((sigmas - SIGMA_TRUE) ** 2).mean())),
    }


def main() -> None:
    t0 = time.time()
    params_list = [{"estimator": est, "eps": eps, "reps": REPS, "n": N}
                   for est in ESTIMATORS for eps in EPS_GRID]
    runner = SweepRunner("e3_breakdown", _STUDY_DIR, run_cell, params_list,
                         metric_goal="lower")
    summary = runner.run()

    truth_premium = PVLossGenerator(mu=MU_TRUE, sigma=SIGMA_TRUE,
                                    single_family=True).truth_functionals(D, U)["premium"]
    extra = {"reps_per_cell": REPS, "n_per_rep": N, "cells": len(summary.trials),
             "qls_grid": "0.15-0.85x19 (trimmed)", "mtm_trim": MTM_TRIM,
             "truth_premium": f"{truth_premium:.2f}"}
    reported = None
    for t in summary.trials:
        est, eps = t.params["estimator"], t.params["eps"]
        key = f"{est}_eps{eps * 100:g}"
        if t.status != "ok":
            extra[f"prem_err_{key}"] = "crash"
            continue
        extra[f"prem_err_{key}"] = f"{t.primary_metric:.4f}"
        extra[f"prem_bias_pct_{key}"] = f"{t.extra['prem_bias_pct']:+.4f}"
        extra[f"rmse_sigma_{key}"] = f"{t.extra['rmse_sigma']:.5f}"
        if est == REPORTED["estimator"] and eps == REPORTED["eps"]:
            reported = t

    if reported is None:
        print("E3: reported cell (trimmed QLS-OLS @ eps=10%) missing or crashed — see sidecar")
        raise SystemExit(1)

    extra["reported_cell"] = f"{REPORTED['estimator']}@eps={REPORTED['eps']:.0%}"
    extra["prem_err_sd_reported"] = f"{reported.extra['err_sd']:.4f}"
    evaluate_scalar(float(reported.primary_metric), exp_id=EXPERIMENT_ID,
                    metric_name="premium_error_pct", metric_goal="lower",
                    status="ok", t0=t0, study_dir=_STUDY_DIR, extra=extra)

    curve = {est: [next(t.primary_metric for t in summary.trials
                        if t.params["estimator"] == est and t.params["eps"] == e)
                   for e in EPS_GRID] for est in ESTIMATORS}
    print(f"E3 breakdown sweep: 20 cells x {REPS} reps (sidecar: sweeps/e3_breakdown.sidecar.tsv)")
    print(f"premium error % by eps {[f'{e:.0%}' for e in EPS_GRID]}  (MC floor at eps=0 ~= 4.1-4.3%):")
    for est, vals in curve.items():
        print(f"  {est:8s}: " + "  ".join(f"{v:8.3f}" for v in vals))
    print(f"reported cell {extra['reported_cell']}: {reported.primary_metric:.3f}% "
          f"(sd {reported.extra['err_sd']:.3f}, {REPS} reps)")


if __name__ == "__main__":
    main()
