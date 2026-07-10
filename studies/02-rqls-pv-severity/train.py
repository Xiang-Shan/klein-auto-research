"""train.py — Klein study 02, Experiment E7: reported cell of the decision-table sweep.

Thin surface (SKILL.md Hard Rules). E7 ran as the second sanctioned sweep
(`sweeps/e7_decision.py` -> `sweeps/e7_decision.sidecar.tsv`: 4 estimators x
eps in {0,1,2,5,10}% on the REALISTIC lab — mixture, trunc d=$5k, cens u=$2M —
20 cells x 500 reps). Per sweep-rules rule 4 this file is the SNAPSHOT of the
pre-registered reported cell — window-QLS-trimmed at the realistic eps=5 % — which is
the SAME config+seeds as E5's primary and must reproduce 18.783886 exactly. The
official exp-7 aux rows (the full decision grid) were written by the sweep run; this
snapshot evaluates with study_dir=None so a reproduction rerun can never clobber
them. The sidecar is the authoritative grid; the filing-memo markdown table lives in
program.md (Phase-2 steer 2).

Run:  uv run python studies/02-rqls-pv-severity/train.py 2>&1 | tee run.log
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

_STUDY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_STUDY_DIR))  # generator, estimators (siblings)
sys.path.insert(0, str(_STUDY_DIR.parents[1]))  # repo root for kleinlib

from kleinlib.eval import evaluate_scalar  # noqa: E402
from generator import STD_DEDUCTIBLE, STD_LIMIT, PVLossGenerator  # noqa: E402
from estimators import default_p_grid, qls  # noqa: E402

# --- experiment knobs (the mutable surface) ---------------------------------
EXPERIMENT_ID = 7
RANDOM_SEED = 42
N = 2000          # policies DRAWN per rep
REPS = 500        # Monte-Carlo reps (pre-registered for E7 cells)
D, U = STD_DEDUCTIBLE, STD_LIMIT
CONTAM_EPS = 0.05                       # reported cell: the realistic eps
TRIM_GRID = default_p_grid(trim=0.15)   # window-QLS-trimmed (E5 primary config)


def main() -> None:
    t0 = time.time()
    gen = PVLossGenerator(contam_eps=CONTAM_EPS, deductible=D, limit=U)  # mixture
    truth = gen.truth_functionals(D, U)["premium"]

    prem = []
    for r in range(REPS):
        s = gen.sample(N, seed=RANDOM_SEED + r, incomplete=True, contaminate=True)
        fit = qls(s.losses, D, U, TRIM_GRID, "lognormal", weights="ols", censored=s.censored)
        prem.append(fit.premium(D, U))
    prem = np.asarray(prem)
    err = np.abs(prem - truth) / truth * 100.0

    # study_dir=None: reproduction snapshot — official exp-7 aux was written by the sweep.
    evaluate_scalar(float(err.mean()), exp_id=EXPERIMENT_ID,
                    metric_name="premium_error_pct", metric_goal="lower",
                    status="ok", t0=t0, study_dir=None,
                    extra={"reps": REPS, "n_drawn_per_rep": N, "contam_eps": CONTAM_EPS,
                           "prem_err_sd": f"{err.std(ddof=1):.4f}",
                           "note": "snapshot of sweep reported cell (window-QLS-trimmed @ eps=5%, realistic lab)"})
    print(f"E7 reported-cell snapshot: window-QLS-trimmed @ eps={CONTAM_EPS:.0%} on the realistic lab, "
          f"n={N} x {REPS} reps -> premium error {err.mean():.6f}% (sd {err.std(ddof=1):.3f}) "
          f"— must equal E5 primary 18.783886")


if __name__ == "__main__":
    main()
