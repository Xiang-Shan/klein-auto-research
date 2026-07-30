"""The only per-candidate mutable surface in a Klein v2 study.

Simulation harness for noisy-Rosenbrock derivative-free optimization: the
CONFIG block below is the 5–15-line experiment surface; objective.py and
optimizers.py are stable study libraries.
"""

from __future__ import annotations

import csv
import os
import statistics
import time
from pathlib import Path

from kleinlib.eval import evaluate_scalar
from objective import (
    DEV_BASE,
    EVAL_BUDGET,
    F_STAR,
    FINAL_BASE,
    N_REPS,
    NoisyBudgetedObjective,
    block,
    rosenbrock,
)
from optimizers import nelder_mead, nm_restarts, spsa

EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID")
TRACK = os.environ.get("KLEIN_TRACK")

# ---- CONFIG: the per-experiment surface (keep diffs 5-15 lines) ----
OPTIMIZER = "spsa"        # nm | nm_restarts | spsa
ADAPTIVE = False          # Nelder-Mead adaptive (Gao-Han) parameters
N_RESTARTS = 4            # nm_restarts: starts sharing the SAME total budget
SPSA_A0 = 50.0            # SPSA gain-sequence scale
SEED_BASE_OVERRIDE = None  # measurement sweeps only; never for frontier runs
# --------------------------------------------------------------------


def run_rep(seed: int) -> float:
    objective = NoisyBudgetedObjective(seed, budget=EVAL_BUDGET)
    x0 = objective.random_start()
    if OPTIMIZER == "nm":
        answer = nelder_mead(objective, x0, EVAL_BUDGET, adaptive=ADAPTIVE)
    elif OPTIMIZER == "nm_restarts":
        answer = nm_restarts(objective, N_RESTARTS, EVAL_BUDGET, adaptive=ADAPTIVE)
    elif OPTIMIZER == "spsa":
        answer = spsa(objective, x0, EVAL_BUDGET, a0=SPSA_A0)
    else:
        raise RuntimeError(f"unknown OPTIMIZER {OPTIMIZER!r}")
    return rosenbrock(answer) - F_STAR  # scored on the TRUE function


def seed_base(evaluation_kind: str) -> int:
    if SEED_BASE_OVERRIDE is not None:
        return int(SEED_BASE_OVERRIDE)
    return FINAL_BASE if evaluation_kind == "final_test" else DEV_BASE


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
    missing = [
        name
        for name, value in (
            ("KLEIN_EVALUATION_KIND", evaluation_kind),
            ("KLEIN_EXPERIMENT_ID", EXPERIMENT_ID),
            ("KLEIN_TRACK", TRACK),
        )
        if value is None
    ]
    if missing:
        raise RuntimeError(
            "train.py must be invoked through `klein run-one`; missing "
            + ", ".join(missing)
        )
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")

    base = seed_base(evaluation_kind)
    gaps = [run_rep(seed) for seed in block(base, N_REPS)]
    mean_gap = statistics.fmean(gaps)

    if OPTIMIZER == "nm" and not ADAPTIVE and base == DEV_BASE:
        reference = Path("data/prepared/reference_cell.csv")
        if reference.is_file():
            with reference.open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            ref_mean = statistics.fmean(float(r["final_gap"]) for r in rows)
            if abs(ref_mean - mean_gap) > 1e-9:
                raise RuntimeError(
                    f"split-identity anchor FAILED: prepared reference mean {ref_mean!r} "
                    f"vs recomputed {mean_gap!r} — seed plumbing drifted, STOP"
                )

    evaluate_scalar(
        mean_gap,
        exp_id=EXPERIMENT_ID,
        metric_name="mean_final_gap",
        metric_goal="lower",
        study_dir=".",
        t0=t0,
        extra={
            "gap_std_across_reps": statistics.stdev(gaps),
            "gap_median": statistics.median(gaps),
            "gap_worst": max(gaps),
            "n_reps": float(N_REPS),
            "wall_seconds": time.time() - t0,
        },
    )


if __name__ == "__main__":
    main()
