"""Noisy Rosenbrock — the known-truth landscape for study 03.

True function: f(x, y) = (1-x)^2 + 100 (y - x^2)^2, minimum f* = 0 at (1, 1).
Every EVALUATION the optimizer sees is corrupted with N(0, SIGMA^2) noise; the
reported gap is always measured on the TRUE function at the optimizer's answer
(the privilege of a synthetic lab: the truth is available for scoring, never
for optimizing).

Seed-block contract (comparability under `split.kind: none`):
- development block: seeds DEV_BASE + rep         (rep = 0..N_REPS-1)
- noise-floor blocks: FLOOR_BASES[j] + rep        (disjoint from both by construction)
- sealed final test:  FINAL_BASE + rep            (fresh noise, touched once)
`assert_blocks_disjoint()` proves the contract mechanically; prepare.py runs it.
"""

from __future__ import annotations

import numpy as np

SIGMA = 0.5
F_STAR = 0.0
X_STAR = (1.0, 1.0)
START_DOMAIN = (-2.0, 2.0)
N_REPS = 40
EVAL_BUDGET = 200

DEV_BASE = 42
FLOOR_BASES = (142, 242, 342, 442)  # + DEV_BASE itself makes k=5 measurement cells
FINAL_BASE = 10042


def rosenbrock(point) -> float:
    x, y = float(point[0]), float(point[1])
    return (1.0 - x) ** 2 + 100.0 * (y - x * x) ** 2


class NoisyBudgetedObjective:
    """One rep's objective: noisy evaluations, hard evaluation budget."""

    def __init__(self, seed: int, budget: int = EVAL_BUDGET) -> None:
        self.rng = np.random.default_rng(seed)
        self.budget = budget
        self.calls = 0

    def __call__(self, point) -> float:
        if self.calls >= self.budget:
            raise BudgetExhausted
        self.calls += 1
        return rosenbrock(point) + float(self.rng.normal(0.0, SIGMA))

    def random_start(self):
        low, high = START_DOMAIN
        return self.rng.uniform(low, high, size=2)


class BudgetExhausted(Exception):
    """Raised when an optimizer asks for evaluation budget it does not have."""


def block(base: int, n_reps: int = N_REPS) -> range:
    return range(base, base + n_reps)


def assert_blocks_disjoint() -> None:
    dev = set(block(DEV_BASE))
    final = set(block(FINAL_BASE))
    floors = [set(block(b)) for b in FLOOR_BASES]
    all_sets = [dev, final, *floors]
    for i, a in enumerate(all_sets):
        for b in all_sets[i + 1 :]:
            overlap = a & b
            if overlap:
                raise AssertionError(f"seed blocks overlap: {sorted(overlap)[:5]}")
