"""Derivative-free optimizers for study 03 — stable library surface.

Created deliberately BEFORE the loop (library changes are never part of a
per-experiment diff); train.py's config block selects among them. Every
optimizer receives a NoisyBudgetedObjective and must live inside its budget;
the return value is the candidate point the optimizer commits to.
"""

from __future__ import annotations

import numpy as np
from objective import BudgetExhausted, NoisyBudgetedObjective
from scipy.optimize import minimize


def nelder_mead(objective: NoisyBudgetedObjective, x0, budget: int, *, adaptive: bool = False):
    """Single-start Nelder-Mead under a hard evaluation budget."""

    def guarded(point):
        try:
            return objective(point)
        except BudgetExhausted:
            # scipy has no clean stop-by-callback for maxfev overruns mid-iteration;
            # returning +inf makes every further probe worthless without lying about
            # the budget (calls stopped counting at the cap).
            return float("inf")

    result = minimize(
        guarded,
        np.asarray(x0, dtype=float),
        method="Nelder-Mead",
        options={"maxfev": budget, "adaptive": adaptive, "xatol": 1e-8, "fatol": 1e-8},
    )
    return result.x


def nm_restarts(objective: NoisyBudgetedObjective, n_restarts: int, budget: int, *, adaptive: bool = False):
    """Split the SAME total budget across random restarts; commit to the start
    whose final simplex reported the best (noisy) value."""
    per_start = budget // n_restarts
    best_point, best_seen = None, float("inf")
    for _ in range(n_restarts):
        x0 = objective.random_start()

        def guarded(point):
            try:
                return objective(point)
            except BudgetExhausted:
                return float("inf")

        result = minimize(
            guarded,
            x0,
            method="Nelder-Mead",
            options={"maxfev": per_start, "adaptive": adaptive},
        )
        if result.fun < best_seen:
            best_seen, best_point = float(result.fun), result.x
    return best_point


def spsa(objective: NoisyBudgetedObjective, x0, budget: int, *, a0: float, c0: float = 0.1,
         alpha: float = 0.602, gamma: float = 0.101, A: float | None = None):
    """Simultaneous Perturbation Stochastic Approximation (Spall 1992).

    Two noisy evaluations per iteration; no gradient clipping BY DESIGN — an
    aggressive gain sequence is allowed to diverge honestly (the crash is the
    evidence, not a bug to hide).
    """
    theta = np.asarray(x0, dtype=float)
    iterations = budget // 2
    A = A if A is not None else 0.1 * iterations
    rng = objective.rng  # perturbations ride the rep's own stream
    for k in range(iterations):
        ak = a0 / (k + 1 + A) ** alpha
        ck = c0 / (k + 1) ** gamma
        delta = rng.choice((-1.0, 1.0), size=theta.shape)
        try:
            y_plus = objective(theta + ck * delta)
            y_minus = objective(theta - ck * delta)
        except BudgetExhausted:
            break
        gradient_estimate = (y_plus - y_minus) / (2.0 * ck) * delta
        theta = theta - ak * gradient_estimate
    return theta
