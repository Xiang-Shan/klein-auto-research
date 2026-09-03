"""Measurement instruments: the floor recipes and the family-wise selection guard.

``minimum_delta`` is measured, never guessed — and the measurement must be of the
RIGHT thing.  On real data the fit-seed spread, the marginal re-split spread and
the paired-difference spread can differ by an order of magnitude
(``knowledge/research-discipline.md`` lessons 1-2), so a floor without a named
**estimand** is not a registered decision rule.  This module ships the three
recipes the consult protocol names, each pinned to the estimand it answers:

===================  =====================  ==========================================
recipe               estimand               the question it answers
===================  =====================  ==========================================
``seed-sweep``       ``fit-noise``          how much does the SAME fit on the SAME
                                            split move when only the seed moves?
``split-lottery``    ``marginal-resplit``   how much does one candidate's own score
                                            move when the split is re-drawn?
``paired-bootstrap`` ``paired-comparison``  how much does the DIFFERENCE between two
                                            candidates move, on the same rows?
===================  =====================  ==========================================

A seed sweep measures *fit noise*, never the keep bar: it is recorded under
``metric.fit_noise`` and never pasted as ``minimum_delta`` (consult protocol,
Phase 0).  The other two produce a ``noise_floor:`` block whose
``suggested_minimum_delta`` is ``max(2*std, range/2)``.

The paired recipe enforces **common random numbers by construction**: exactly one
index draw is taken per replicate and applied to BOTH candidates, so the two
series can never be resampled out of step.  Nothing here can be told to use two
draws — the API has no seam for it.

:func:`family_maxt` is the sign-flip max-t **selection guard**, ported from the
frozen study-08 reference ``studies/08-iris-rematch/sweeps/rematch_analysis.py``
and re-verified against study 09's recorded ``sweeps/arena_verdicts.tsv``.  Read
its docstring before quoting an adjusted score: it limits family-wise false
DETECTION under a registered sign-symmetry assumption and says nothing about the
SIZE of what it detects, and nothing about a population beyond the rows measured
(``research-discipline.md`` lesson 6).

Pure numpy + stdlib: safe to import without sklearn, torch, or LightGBM.
"""

from __future__ import annotations

import itertools
import math
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

__all__ = [
    "ESTIMANDS",
    "FloorEstimate",
    "RECIPES",
    "RECIPE_ESTIMAND",
    "family_maxt",
    "paired_bootstrap",
    "seed_sweep",
    "split_lottery",
]

#: The floor recipes the consult protocol names (``klein noise-floor --recipe``).
RECIPES: tuple[str, ...] = ("seed-sweep", "split-lottery", "paired-bootstrap")

#: The estimands a floor may answer (``klein noise-floor --estimand``).
#: ``fit-noise`` is deliberately NOT a keep bar — see :data:`FloorEstimate.block_key`.
ESTIMANDS: tuple[str, ...] = ("fit-noise", "marginal-resplit", "paired-comparison")

#: The estimand each recipe measures when the caller does not say otherwise.
#: A recipe/estimand pair outside this map is legal but must be stated
#: explicitly — mismatching them silently is how a seed spread becomes a bar.
RECIPE_ESTIMAND: dict[str, str] = {
    "seed-sweep": "fit-noise",
    "split-lottery": "marginal-resplit",
    "paired-bootstrap": "paired-comparison",
}

#: Below this many replicate values a spread is not a measurement.
MIN_K: int = 3

#: Above this many randomization units the sign-flip family is sampled, never
#: enumerated: 2**17 x 17 float64 would be 17 MB of flip matrix for no gain.
_MAX_ENUMERATED_UNITS: int = 16

_NEVER = float("-inf")


@dataclass(frozen=True)
class FloorEstimate:
    """One measured spread, with the recipe and estimand that produced it.

    ``value_range`` (not ``range``) keeps the name off the builtin, matching
    :class:`kleinlib.noise_floor.NoiseFloor`, whose block this renders into.
    """

    recipe: str
    estimand: str
    k: int
    mean: float
    std: float
    value_range: float
    values: tuple[float, ...]
    seeds: tuple[int, ...] | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        if self.recipe not in RECIPES:
            raise ValueError(f"recipe must be one of {list(RECIPES)}, got {self.recipe!r}")
        if self.estimand not in ESTIMANDS:
            raise ValueError(
                f"estimand must be one of {list(ESTIMANDS)}, got {self.estimand!r}"
            )

    @property
    def suggested_minimum_delta(self) -> float:
        """``max(2*std, range/2)`` — the schema-3 floor bar.

        The larger of two standard deviations and half the observed range, so
        neither a lucky-tight std nor a narrow range can shrink the bar.  For
        ``k <= 16`` the ``2*std`` term always binds (the range can only reach
        it once a lottery is large enough for a rare wild draw to sit alone at
        one end), which is why a k-of-5 Phase 0 reads as ``2*std``.
        """
        return max(2.0 * self.std, self.value_range / 2.0)

    @property
    def block_key(self) -> str:
        """``fit_noise`` for the fit-noise estimand, else ``noise_floor``.

        A seed-only spread is provenance about the fit, not the bar a keep must
        clear; writing it under ``noise_floor:`` is how a study ends up
        defending a delta it never measured.
        """
        return "fit_noise" if self.estimand == "fit-noise" else "noise_floor"

    def as_noise_floor(self) -> Any:
        """This estimate as a :class:`kleinlib.noise_floor.NoiseFloor`."""
        from .noise_floor import NoiseFloor

        return NoiseFloor(
            k=self.k,
            mean=self.mean,
            std=self.std,
            value_range=self.value_range,
            values=self.values,
            seeds=self.seeds,
        )


def _summarize(
    values: Sequence[float],
    *,
    recipe: str,
    estimand: str,
    seeds: Sequence[int] | None = None,
    source: str | None = None,
) -> FloorEstimate:
    floats = [float(v) for v in values]
    if len(floats) < MIN_K:
        raise ValueError(
            f"{recipe}: a floor needs k >= {MIN_K} replicate values, got {len(floats)}"
        )
    if any(not math.isfinite(v) for v in floats):
        raise ValueError(f"{recipe}: every replicate value must be finite")
    return FloorEstimate(
        recipe=recipe,
        estimand=estimand,
        k=len(floats),
        mean=statistics.fmean(floats),
        std=statistics.stdev(floats),  # ddof=1
        value_range=max(floats) - min(floats),
        values=tuple(floats),
        seeds=None if seeds is None else tuple(int(s) for s in seeds),
        source=source,
    )


def _replicate(
    fn: Callable[[int], float],
    seeds: Sequence[int],
    *,
    recipe: str,
    estimand: str,
    source: str | None,
) -> FloorEstimate:
    seed_list = [int(s) for s in seeds]
    if len(seed_list) < MIN_K:
        raise ValueError(
            f"{recipe}: a floor needs k >= {MIN_K} seeds, got {len(seed_list)}"
        )
    if len(set(seed_list)) != len(seed_list):
        raise ValueError(f"{recipe}: seeds must be distinct — a repeat is not a replicate")
    values = [float(fn(seed)) for seed in seed_list]
    return _summarize(
        values, recipe=recipe, estimand=estimand, seeds=seed_list, source=source
    )


def seed_sweep(
    fn: Callable[[int], float],
    seeds: Sequence[int],
    *,
    source: str | None = None,
) -> FloorEstimate:
    """Re-fit the SAME configuration on the SAME split, varying only the seed.

    Estimand ``fit-noise``: the irreducible wobble of the fitting procedure.
    This is provenance, not a keep bar — the result lands under
    ``metric.fit_noise`` (see :attr:`FloorEstimate.block_key`).  ``fn(seed)``
    returns the run's primary metric.
    """
    return _replicate(
        fn, seeds, recipe="seed-sweep", estimand="fit-noise", source=source
    )


def split_lottery(
    fn: Callable[[int], float],
    seeds: Sequence[int],
    *,
    source: str | None = None,
) -> FloorEstimate:
    """Re-draw the split, refit, rescore — one candidate, many partitions.

    Estimand ``marginal-resplit``: how much ONE candidate's own score moves
    when the lottery is re-run.  This is the honest floor for a level, not for
    a comparison — for a comparison use :func:`paired_bootstrap` (or a paired
    lottery) and say so in the block's ``estimand``.  ``fn(seed)`` re-splits
    with that seed and returns the metric.
    """
    return _replicate(
        fn, seeds, recipe="split-lottery", estimand="marginal-resplit", source=source
    )


def paired_bootstrap(
    a: Sequence[float] | np.ndarray,
    b: Sequence[float] | np.ndarray,
    *,
    n_boot: int = 1000,
    seed: int = 0,
    statistic: Callable[[np.ndarray, np.ndarray], float] | None = None,
    source: str | None = None,
) -> FloorEstimate:
    """Bootstrap the DIFFERENCE between two candidates under common random numbers.

    ``a`` and ``b`` are per-row contributions to the metric (per-row losses, or
    per-row scores) for two candidates evaluated on the SAME rows, in the SAME
    order — that alignment is what makes the comparison paired.  Each replicate
    draws ONE index vector and applies it to both series, so the two can never
    be resampled out of step: common random numbers are enforced by
    construction, not by a flag the caller may forget.

    The default statistic is ``mean(a) - mean(b)`` on the resampled rows, i.e.
    the paired difference of the metric.  Pass ``statistic`` for a metric that
    is not a row mean (it receives the two ALREADY-ALIGNED resamples and must
    return a float).

    Estimand ``paired-comparison``.  Returns the spread of the ``n_boot``
    replicate differences; ``suggested_minimum_delta`` is the bar a comparison
    on these rows must clear.
    """
    left = np.asarray(a, dtype=float)
    right = np.asarray(b, dtype=float)
    if left.ndim != 1 or right.ndim != 1:
        raise ValueError("paired-bootstrap: a and b must be 1-D per-row series")
    if left.shape != right.shape:
        raise ValueError(
            "paired-bootstrap: a and b must cover the SAME rows — got "
            f"{left.shape[0]} and {right.shape[0]} values; an unpaired comparison "
            "measures the wrong estimand"
        )
    n = left.shape[0]
    if n < 2:
        raise ValueError("paired-bootstrap: needs at least 2 paired rows")
    if not (np.isfinite(left).all() and np.isfinite(right).all()):
        raise ValueError("paired-bootstrap: a and b must be finite")
    if int(n_boot) < MIN_K:
        raise ValueError(f"paired-bootstrap: n_boot must be >= {MIN_K}")

    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(int(n_boot)):
        # ONE draw, applied to both series — the CRN guarantee.
        idx = rng.integers(0, n, size=n)
        if statistic is None:
            values.append(float(left[idx].mean() - right[idx].mean()))
        else:
            values.append(float(statistic(left[idx], right[idx])))
    return _summarize(
        values,
        recipe="paired-bootstrap",
        estimand="paired-comparison",
        seeds=None,
        source=source,
    )


# --------------------------------------------------------------------------
# The family-wise selection guard
# --------------------------------------------------------------------------


def _t_stat(values: np.ndarray) -> float:
    """One-sample t on the unit-level deltas; the reference's exact conventions.

    ``sd`` is the ddof=1 sample standard deviation.  Fewer than two units, or an
    all-NaN cell, is a never-firing placeholder (``-inf``).  A zero spread is
    ``+inf`` when the mean is positive, ``-inf`` when negative, ``0.0`` when the
    deltas are identically zero.
    """
    finite = values[np.isfinite(values)]
    if finite.size < 2:
        return _NEVER
    sd = float(np.std(finite, ddof=1))
    mean = float(np.mean(finite))
    if sd == 0.0:
        return math.inf if mean > 0 else (_NEVER if mean < 0 else 0.0)
    return mean / (sd / math.sqrt(finite.size))


def family_maxt(
    deltas_by_cell: Mapping[str, Sequence[float] | np.ndarray],
    *,
    n_perm: int = 1024,
    seed: int = 0,
) -> dict[str, float]:
    """Sign-flip max-t family-wise selection guard over a FIXED family of cells.

    ``deltas_by_cell`` maps a cell id to that cell's **unit-level** paired
    deltas — one value per independent randomization unit (study 08 and 09 used
    the repeat, not the fold), positive meaning "this cell improved on the
    anchor".  Every live cell must carry the same number of units, because one
    sign vector is applied JOINTLY to the whole family; ``nan`` marks a unit a
    cell is missing.

    Returns the adjusted score per cell:
    ``p(c) = #{eps : max over live cells of t*(., eps) >= t_obs(c)} / n_flips``.
    Cells that cannot fire (fewer than two finite units) stay in the family as
    never-firing placeholders and score ``1.0`` — dropping them after outcomes
    are visible would shrink the family the guard corrects for.

    When ``2**J <= n_perm`` the ``2**J`` sign vectors are ENUMERATED (exact, and
    ``seed`` is unused); otherwise ``n_perm`` Rademacher vectors are drawn from
    ``numpy.random.default_rng(seed)``.  Study 08 and 09 both enumerated
    ``2**10 = 1024``.

    What this is NOT (``research-discipline.md`` lesson 6): it is a
    randomization diagnostic under a REGISTERED symmetry assumption — that a
    cell which neither helps nor hurts has sign-symmetric unit deltas, jointly
    with every other cell.  It is not exact FWER control, not a p-value about
    any population, and it carries no information about EFFECT SIZE: of 113
    cells in study 08 exactly one cleared it, at eight training rows, and the
    registered fragility exhibit did not confirm it; in study 09, 0 of 42
    cleared.  "Detectable" is always shorthand for "cleared this guard on these
    rows under this procedure".
    """
    if not deltas_by_cell:
        return {}
    if int(n_perm) < 1:
        raise ValueError("family_maxt: n_perm must be >= 1")

    arrays: dict[str, np.ndarray] = {}
    for cell, values in deltas_by_cell.items():
        arr = np.asarray(values, dtype=float).ravel()
        if arr.size == 0:
            raise ValueError(f"family_maxt: cell {cell!r} has no unit deltas")
        arrays[cell] = arr

    unit_counts = {arr.size for arr in arrays.values()}
    if len(unit_counts) != 1:
        raise ValueError(
            "family_maxt: one sign vector is applied jointly to the whole family, so "
            "every cell must carry the same number of units (pad a missing unit with "
            f"nan); got sizes {sorted(unit_counts)}"
        )
    n_units = unit_counts.pop()

    t_obs = {cell: _t_stat(arr) for cell, arr in arrays.items()}
    live = {cell: arr for cell, arr in arrays.items() if t_obs[cell] != _NEVER}
    if not live:
        # Every cell is a placeholder: nothing can fire, and nothing is claimed.
        return dict.fromkeys(arrays, 1.0)

    if n_units <= _MAX_ENUMERATED_UNITS and 2**n_units <= int(n_perm):
        flips: np.ndarray = np.array(
            list(itertools.product((1.0, -1.0), repeat=n_units)), dtype=float
        )
    else:
        rng = np.random.default_rng(seed)
        flips = rng.integers(0, 2, size=(int(n_perm), n_units)).astype(float) * 2.0 - 1.0

    max_dist = np.full(flips.shape[0], _NEVER, dtype=float)
    for arr in live.values():
        mask = np.isfinite(arr)
        # NaN units keep their slot in the shared sign vector; only the finite
        # entries enter the cell's own statistic (the reference's semantics).
        cell_units = arr[mask]
        cell_flips = flips[:, mask]
        flipped = cell_flips * cell_units  # (n_flips, n_finite_units)
        mean = flipped.mean(axis=1)
        sd = flipped.std(axis=1, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            t = mean / (sd / math.sqrt(cell_units.size))
        zero_sd = sd == 0.0
        if zero_sd.any():
            t = np.where(
                zero_sd,
                np.where(mean > 0, math.inf, np.where(mean < 0, _NEVER, 0.0)),
                t,
            )
        max_dist = np.maximum(max_dist, t)

    n_flips = float(flips.shape[0])
    return {
        cell: (1.0 if t == _NEVER else float((max_dist >= t).sum()) / n_flips)
        for cell, t in t_obs.items()
    }
