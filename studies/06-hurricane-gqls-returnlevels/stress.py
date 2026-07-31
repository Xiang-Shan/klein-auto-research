"""stress.py — perturbations of the 30-event sample, and the decision-track metric.

The thesis stresses its estimators exactly once: it multiplies the single largest
observation by ten (72.303 -> 723.03) and reports the parameter shift (Table 6.10,
starred rows). That is one point of one curve. This module supplies the rest of the
curve, because the study's second track scores a *decision*, not a parameter:

    return_level_instability_pct = max over the stress set of the absolute percentage
    change in the fitted 1-in-100 event loss, relative to the clean fit.

Why a MAX and not a mean: a reinsurance attachment point is set once, and it is the
worst plausible perturbation that decides whether the layer is mispriced. An average
would let one catastrophic cell hide behind several benign ones.

The three perturbations, and what each is a proxy for:

* :func:`leave_top_k_out`  -- "what if the Great Miami hurricane had not been in the
  record?" Sampling variability at the top of a 30-point heavy tail. This is the stress
  the thesis does NOT run, and it bites exactly where eq. (2.4)'s breakdown point
  ``min{a, 1-b}`` predicts: at n = 30, dropping k points removes ``k/30`` of the mass,
  so ``k = 2`` (0.067) breaches the (0.05, 0.95) trim but not (0.10, 0.90).
* :func:`inflate_max`      -- gross-error contamination (a unit typo, a
  double-counted claim). ``factor=10`` reproduces the thesis's own modification.
* :func:`bootstrap_samples` -- ordinary resampling noise; the floor against which the
  other two must be read (a 40% swing means nothing if resampling alone gives 35%).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from estimators import Fit, return_level

__all__ = [
    "StressCase",
    "leave_top_k_out",
    "inflate_max",
    "bootstrap_samples",
    "default_stress_set",
    "instability_pct",
]


@dataclass(frozen=True)
class StressCase:
    """One perturbed sample plus a label the results ledger can carry."""

    label: str
    x: np.ndarray


def leave_top_k_out(x: np.ndarray, k: int) -> np.ndarray:
    """Drop the ``k`` largest observations.

    Removes ``k/n`` of the upper mass, which is the quantity to compare against the
    upper breakdown point ``1 - b`` of eq. (2.4).
    """
    x = np.asarray(x, float).ravel()
    if not (0 <= k < x.size):
        raise ValueError(f"need 0 <= k < n = {x.size}, got k={k}")
    if k == 0:
        return x.copy()
    return np.sort(x)[: x.size - k]


def inflate_max(x: np.ndarray, factor: float) -> np.ndarray:
    """Multiply the single largest observation by ``factor`` (on the DOLLAR scale).

    Inputs and outputs are LOG-dollars, so a dollar-scale factor is an additive
    ``log(factor)`` shift of the maximum -- which is what makes the thesis's 10x
    modification a clean ``+log(10) = 2.3026`` bump of one point.
    """
    x = np.asarray(x, float).ravel()
    if factor <= 0:
        raise ValueError(f"factor must be positive, got {factor}")
    out = x.copy()
    out[int(np.argmax(out))] += float(np.log(factor))
    return out


def bootstrap_samples(
    x: np.ndarray, B: int = 200, seed: int | None = 20260731
) -> list[np.ndarray]:
    """``B`` nonparametric bootstrap resamples of the n events, drawn with replacement."""
    x = np.asarray(x, float).ravel()
    if B < 1:
        raise ValueError(f"need B >= 1, got {B}")
    rng = np.random.default_rng(seed)
    return [rng.choice(x, size=x.size, replace=True) for _ in range(B)]


def default_stress_set(
    x: np.ndarray,
    *,
    top_k: Sequence[int] = (1, 2, 3),
    inflate_factors: Sequence[float] = (10.0,),
    n_bootstrap: int = 0,
    seed: int | None = 20260731,
) -> list[StressCase]:
    """The study's adaptive stress set: leave-top-k-out, gross-error inflation, bootstrap.

    ``n_bootstrap=0`` by default -- bootstrap replicates belong in the noise-FLOOR
    measurement, not in the adaptive stress set, or the metric would be measuring
    sampling noise instead of robustness.
    """
    cases = [StressCase(f"leave_top_{k}_out", leave_top_k_out(x, k)) for k in top_k]
    cases += [
        StressCase(f"inflate_max_x{f:g}", inflate_max(x, f)) for f in inflate_factors
    ]
    if n_bootstrap:
        cases += [
            StressCase(f"bootstrap_{i:03d}", s)
            for i, s in enumerate(bootstrap_samples(x, n_bootstrap, seed))
        ]
    return cases


def instability_pct(
    fits_fn: Callable[[np.ndarray], Fit],
    x: np.ndarray,
    stress_set: Iterable[StressCase] | Iterable[np.ndarray],
    p: float = 0.99,
) -> dict:
    """The decision-track primary metric.

    ``fits_fn`` maps a LOG-dollar sample to a :class:`Fit` (e.g.
    ``lambda s: gqls(s, 0.05, 0.95, 8, "lognormal")``). The clean fit sets the
    reference return level; every stressed fit is scored as

        100 * |RL_stressed - RL_clean| / RL_clean

    and the metric is the MAXIMUM over the stress set (see the module docstring).

    Returns ``{"instability_pct", "baseline_return_level", "worst_case", "per_case"}``.
    ``per_case`` is a label -> ``{"return_level", "pct_change"}`` map so a run can log
    the whole curve, not just its peak.
    """
    x = np.asarray(x, float).ravel()
    base_fit = fits_fn(x)
    base_rl = return_level(base_fit, p)
    if not np.isfinite(base_rl) or base_rl <= 0.0:
        raise ValueError(
            f"baseline return level at p={p} is not usable ({base_rl!r}); "
            "the fit is degenerate, so a percentage change is meaningless"
        )

    per_case: dict[str, dict] = {}
    for i, case in enumerate(stress_set):
        if isinstance(case, StressCase):
            label, sample = case.label, case.x
        else:
            label, sample = f"case_{i:03d}", np.asarray(case, float).ravel()
        rl = return_level(fits_fn(sample), p)
        per_case[label] = {
            "return_level": float(rl),
            "pct_change": float(100.0 * abs(rl - base_rl) / base_rl),
        }

    if not per_case:
        raise ValueError("stress_set is empty — nothing to measure instability over")
    worst = max(per_case, key=lambda k: per_case[k]["pct_change"])
    return {
        "instability_pct": float(per_case[worst]["pct_change"]),
        "baseline_return_level": float(base_rl),
        "p": float(p),
        "worst_case": worst,
        "n_cases": len(per_case),
        "per_case": per_case,
    }
