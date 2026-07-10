"""e7_decision.py — E7 sweep: the consolidated premium-error DECISION TABLE (study 02).

Second sanctioned sweep (sweep-rules.md): the realistic-lab grid — full PV mixture
(tail off) + deductible truncation (d=$5k) + limit censoring (u=$2M) at every
eps in {0, 1, 2, 5, 10}% x 4 estimators = 20 cells x 500 reps. EVERY cell -> one
sidecar row (`sweeps/e7_decision.sidecar.tsv`, rep count in params_json); per-cell
mean/sd premium error + signed bias -> aux. Exactly ONE results.tsv row: the
PRE-REGISTERED reported cell = window-QLS-trimmed at the realistic eps=5% — the same
config+seeds as E5's primary, so it must reproduce 18.783886 exactly (consistency
check). The markdown decision table lands in program.md (Phase-2 steer 2). Rule 5
(pickle) n/a — simulation study; the reported cell is snapshotted into train.py.

Run:  uv run python studies/02-rqls-pv-severity/sweeps/e7_decision.py 2>&1 | tee studies/02-rqls-pv-severity/run.log
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
from estimators import default_p_grid, mle_full, mle_truncated_censored, mtm, qls  # noqa: E402

EXPERIMENT_ID = 7
RANDOM_SEED = 42
N = 2000          # policies DRAWN per Monte-Carlo rep
REPS = 500        # Monte-Carlo reps per cell (pre-registered for E7)
D, U = STD_DEDUCTIBLE, STD_LIMIT
EPS_GRID = (0.0, 0.01, 0.02, 0.05, 0.10)
TRIM_GRID = default_p_grid(trim=0.15)   # window-QLS-trimmed = the E5 primary config
MTM_TRIM = 0.10
REPORTED = {"estimator": "qls_window_trim", "eps": 0.05}  # pre-registered reported cell

ESTIMATORS = {
    "mle_naive": lambda s: mle_full(s.losses, "lognormal"),
    "mle_tc": lambda s: mle_truncated_censored(s.losses, D, U, s.censored, "lognormal"),
    "qls_window_trim": lambda s: qls(s.losses, D, U, TRIM_GRID, "lognormal",
                                     weights="ols", censored=s.censored),
    "mtm": lambda s: mtm(s.losses, trim=MTM_TRIM, family="lognormal"),
}


def run_cell(params: dict) -> dict:
    """One (estimator, eps) cell on the realistic lab: 500-rep premium-error MC."""
    est, eps = params["estimator"], params["eps"]
    gen = PVLossGenerator(contam_eps=eps, deductible=D, limit=U)  # mixture, tail off
    truth = gen.truth_functionals(D, U)["premium"]
    fn = ESTIMATORS[est]
    prem = []
    for r in range(REPS):
        s = gen.sample(N, seed=RANDOM_SEED + r, incomplete=True, contaminate=True)
        prem.append(fn(s).premium(D, U))
    prem = np.asarray(prem)
    err = np.abs(prem - truth) / truth * 100.0
    return {
        "primary_metric": float(err.mean()),
        "err_sd": float(err.std(ddof=1)),
        "prem_bias_pct": float((prem - truth).mean() / truth * 100.0),
    }


def main() -> None:
    t0 = time.time()
    params_list = [{"estimator": est, "eps": eps, "reps": REPS, "n": N}
                   for est in ESTIMATORS for eps in EPS_GRID]
    runner = SweepRunner("e7_decision", _STUDY_DIR, run_cell, params_list,
                         metric_goal="lower")
    summary = runner.run()

    truth_premium = PVLossGenerator(deductible=D, limit=U).truth_functionals(D, U)["premium"]
    extra = {"reps_per_cell": REPS, "n_drawn_per_rep": N, "cells": len(summary.trials),
             "cell_config": "mixture, tail off, trunc d=$5k + cens u=$2M",
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
        extra[f"prem_err_sd_{key}"] = f"{t.extra['err_sd']:.4f}"
        extra[f"prem_bias_pct_{key}"] = f"{t.extra['prem_bias_pct']:+.4f}"
        if est == REPORTED["estimator"] and eps == REPORTED["eps"]:
            reported = t

    if reported is None:
        print("E7: reported cell (window-QLS-trimmed @ eps=5%) missing or crashed — see sidecar")
        raise SystemExit(1)

    extra["reported_cell"] = f"{REPORTED['estimator']}@eps={REPORTED['eps']:.0%}"
    evaluate_scalar(float(reported.primary_metric), exp_id=EXPERIMENT_ID,
                    metric_name="premium_error_pct", metric_goal="lower",
                    status="ok", t0=t0, study_dir=_STUDY_DIR, extra=extra)

    print(f"E7 decision table: 20 cells x {REPS} reps on the realistic lab "
          f"(sidecar: sweeps/e7_decision.sidecar.tsv); truth premium ${truth_premium:,.0f}")
    header = "  estimator        " + "".join(f"  eps={e:>4.0%}" for e in EPS_GRID)
    print(header)
    for est in ESTIMATORS:
        cells = {t.params["eps"]: t for t in summary.trials if t.params["estimator"] == est}
        row = "".join(f"  {cells[e].extra['prem_bias_pct']:+8.2f}" for e in EPS_GRID)
        print(f"  {est:16s}{row}   (signed premium bias %)")
    print(f"reported cell {extra['reported_cell']}: {reported.primary_metric:.6f}% "
          f"(sd {reported.extra['err_sd']:.3f}, {REPS} reps) — must equal E5 primary 18.783886")


if __name__ == "__main__":
    main()
