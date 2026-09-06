"""Simultaneous bounds for a REGISTERED family of paired differences.

One function, one job: given the per-unit paired differences of several metrics
measured on the SAME units, return a bound pair per metric that holds for the
whole family at once.  It is the arithmetic the parity decision rule reads, and
it is pure numpy so a study's scorer and ``klein generation parity assess``
compute the identical numbers from the identical table.

**The recipe.**  Resample BLOCKS with replacement — one draw shared by every
metric, so the metrics are never resampled out of step
(common random numbers, exactly as :func:`kleinlib.metrology.paired_bootstrap`
enforces for a pair of candidates).  Studentize each metric's bootstrap
deviation by its own bootstrap standard deviation, take the ``1 - alpha``
quantile of ``max_j |t_j|`` over the draws, and return ``mean_j ± q · sd_j``.
The single quantile is what makes the interval SIMULTANEOUS: widening every
metric by the same studentized critical value is the max-t construction.

**What it is and is not** (``knowledge/research-discipline.md`` lesson 6, whose
wording this deliberately echoes).  These are simultaneous bounds by the max-t
bootstrap under the DECLARED block structure; they are not a p-value, and they
are not FWER control for anything beyond this registered family.  A metric
outside the family that is bounded afterwards is not covered by them, and
neither is a metric whose block structure was chosen after the numbers were
seen.  "Simultaneous" is always shorthand for "over these metrics, on these
units, under this block declaration".

**Undefined is not zero.**  A metric with fewer than two blocks, a zero
bootstrap spread, or any non-finite unit value gets ``(nan, nan)`` and drops out
of the max — it can then never satisfy ``L >= -epsilon``, which is precisely the
preregistered "an undefined metric cannot pass" rule.  Inventing a bound for it
would be an arbitrary denominator adjustment.  "Zero spread" is read at
:data:`ZERO_SPREAD_REL`, not at exact zero: resampling blocks of unequal
size re-associates the same per-block sums in a different order, so a metric that
is genuinely constant comes back with a bootstrap sd around ``1e-17`` rather than
``0.0``, and studentizing by that residue would manufacture an interval of width
``1e-16`` around the mean — a metric nobody measured passing ``L >= -epsilon``.

**Reproducible under a seed, not bit-stable across numpy versions.**  The same
table, seed and numpy give the same bounds on every machine, which is what lets
``generation verify`` recompute an assessment.  ``numpy.random.Generator`` makes
no cross-VERSION bit-stream guarantee, though, so an upgrade can move the last
digits: the assessment records ``numpy``'s version beside ``n_boot`` and ``seed``,
verify compares the numbers at a relative tolerance rather than byte for byte,
and a disagreement prints both environments so the drift is diagnosable instead
of merely fatal.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

__all__ = [
    "MIN_BOOT",
    "ZERO_SPREAD_REL",
    "block_count",
    "block_index",
    "simultaneous_bounds",
]

#: Fewer replicates than this cannot resolve a 95% quantile of a max statistic
#: at all; the declared ``n_boot`` is checked against it rather than silently
#: producing a bound nobody could reproduce.
MIN_BOOT = 200

#: Relative size below which a bootstrap standard deviation is floating-point
#: residue rather than variation (see the module docstring).  Scaled by
#: ``max(1, |mean|)`` so the test means the same thing for a metric measured in
#: Gini points and one measured in claim counts.
ZERO_SPREAD_REL = 1e-12


def block_index(blocks: Sequence[Any] | np.ndarray | None, n_units: int) -> list[np.ndarray]:
    """``[indices of unit rows]`` per block, in first-appearance order.

    ``blocks is None`` means iid units — each unit is its own block, which is
    the honest reading of ``block_column: null`` in ``parity.yaml``.
    """
    if blocks is None:
        return [np.array([i], dtype=int) for i in range(n_units)]
    labels = list(blocks)
    if len(labels) != n_units:
        raise ValueError(
            f"block labels ({len(labels)}) and units ({n_units}) disagree — the block "
            "column is read from the same pinned table as the metrics"
        )
    order: list[Any] = []
    members: dict[Any, list[int]] = {}
    for index, label in enumerate(labels):
        key = str(label)
        if key not in members:
            members[key] = []
            order.append(key)
        members[key].append(index)
    return [np.asarray(members[key], dtype=int) for key in order]


def block_count(blocks: Sequence[Any] | np.ndarray | None, n_units: int) -> int:
    return len(block_index(blocks, n_units))


def simultaneous_bounds(
    deltas: Mapping[str, Sequence[float] | np.ndarray],
    blocks: Sequence[Any] | np.ndarray | None = None,
    *,
    n_boot: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict[str, tuple[float, float]]:
    """``{metric key: (L, U)}`` — simultaneous over the whole mapping.

    ``deltas`` maps a metric key to its per-unit, direction-adjusted paired
    difference (``sign * (ai - expert)``), one value per sampling unit, every
    metric on the SAME units in the SAME order.  ``blocks`` is the dependence
    block each unit belongs to (``None`` = iid units).

    Deterministic under ``seed`` for one numpy: the same table gives the same
    bounds, which is what lets ``generation verify`` recompute an assessment and
    compare it number for number (at a relative tolerance — see the module
    docstring on cross-version bit streams).
    """
    if not deltas:
        return {}
    if int(n_boot) < MIN_BOOT:
        raise ValueError(f"simultaneous_bounds: n_boot must be >= {MIN_BOOT}")
    if not 0.0 < float(alpha) < 1.0:
        raise ValueError(f"simultaneous_bounds: alpha must lie in (0, 1), got {alpha!r}")

    arrays: dict[str, np.ndarray] = {}
    for key, values in deltas.items():
        arr = np.asarray(values, dtype=float).ravel()
        if arr.size == 0:
            raise ValueError(f"simultaneous_bounds: metric {key!r} has no units")
        arrays[str(key)] = arr
    sizes = {arr.size for arr in arrays.values()}
    if len(sizes) != 1:
        raise ValueError(
            "simultaneous_bounds: every metric must be paired at the SAME sampling "
            f"unit, so the series must be the same length; got sizes {sorted(sizes)}"
        )
    n_units = sizes.pop()
    groups = block_index(blocks, n_units)
    n_blocks = len(groups)

    # A metric is LIVE only if it can carry a bound at all.  Non-finite units
    # (a top-to-bottom ratio on a zero-loss bottom decile, say) and a single
    # block both mean "this metric is undefined here", and an undefined metric
    # never enters the max.
    live = {
        key: arr
        for key, arr in arrays.items()
        if n_blocks >= 2 and bool(np.isfinite(arr).all())
    }
    if not live:
        return dict.fromkeys(arrays, (float("nan"), float("nan")))

    means = {key: float(arr.mean()) for key, arr in live.items()}
    rng = np.random.default_rng(int(seed))
    draws = int(n_boot)

    # A resampled mean is (sum of the drawn blocks' sums) / (their total count),
    # so the whole bootstrap is arithmetic on per-block sums — exact, and free of
    # a per-draw index gather.  Chunked so a study with many blocks cannot make
    # the draw matrix large.
    counts = np.array([group.size for group in groups], dtype=float)
    block_sums = {key: np.array([arr[g].sum() for g in groups]) for key, arr in live.items()}
    replicates = {key: np.empty(draws, dtype=float) for key in live}
    chunk = max(1, min(draws, 2_000_000 // max(1, n_blocks)))
    done = 0
    while done < draws:
        width = min(chunk, draws - done)
        # ONE block draw per replicate, shared by every metric — the
        # common-random-numbers guarantee, enforced by construction.
        chosen = rng.integers(0, n_blocks, size=(width, n_blocks))
        denominator = counts[chosen].sum(axis=1)
        for key, sums in block_sums.items():
            replicates[key][done : done + width] = sums[chosen].sum(axis=1) / denominator
        done += width

    sds = {key: float(values.std(ddof=1)) for key, values in replicates.items()}
    # Not `sds[key] > 0.0`: unequal block sizes make a CONSTANT metric resample
    # to sd ~1e-17 rather than exactly 0, and studentizing by that residue would
    # hand a metric nobody measured an interval narrow enough to pass.
    usable = [
        key
        for key in live
        if np.isfinite(sds[key]) and sds[key] > ZERO_SPREAD_REL * max(1.0, abs(means[key]))
    ]
    if not usable:
        return dict.fromkeys(arrays, (float("nan"), float("nan")))

    t_max = np.zeros(draws, dtype=float)
    for key in usable:
        t_max = np.maximum(t_max, np.abs(replicates[key] - means[key]) / sds[key])
    critical = float(np.quantile(t_max, 1.0 - float(alpha)))

    bounds: dict[str, tuple[float, float]] = dict.fromkeys(
        arrays, (float("nan"), float("nan"))
    )
    for key in usable:
        half = critical * sds[key]
        bounds[key] = (means[key] - half, means[key] + half)
    return bounds
