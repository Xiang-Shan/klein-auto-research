"""Forecast arithmetic — Brier, the Murphy decomposition, coverage, bounds.

Pure functions over plain lists of ``(p, y)`` pairs.  Nothing here reads a file,
touches git, or knows what a slate is: the arithmetic is separated from the
bookkeeping so it can be hand-checked against a textbook on three numbers
(``kleinlib/tests/test_generation_slate.py`` does exactly that).

**This module scores forecasts; it never produces, ranks or selects them.**  It
has no notion of a candidate, and every ``p`` it sees was typed by the driver
into ``slates/<phase>.yaml`` before the evidence existed (R-SLA-6).

Three facts about the numbers, because each one is easy to over-read:

``brier`` vs ``binned_brier``
    The Brier score is the mean of ``(p − y)²`` over the RESOLVED rows.  The
    Murphy identity ``BS = reliability − resolution + uncertainty`` holds
    EXACTLY only when every forecast inside a bin is replaced by that bin's mean
    — so :func:`binned_brier` is reported beside :func:`brier` and is the one
    the identity closes on.  With five bins and four rows the two differ; saying
    so in the receipt is cheaper than a reader deriving it.

``skill``
    ``1 − brier / base_rate_brier`` against the driver's own frozen base-rate
    forecast, NOT against the realized base rate.  It is ``None`` when the
    base-rate forecast happened to score 0, because dividing by it would invent
    an infinity.

``best_case_brier`` / ``worst_case_brier``
    The censored rows are not missing at random — a row nobody ran is a row
    somebody chose not to run.  Rather than drop them, the two bounds score
    every unresolved row the most and the least favourably possible, so a
    coverage-0.5 panel reports the interval its own gaps allow.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

__all__ = [
    "BIN_COUNT",
    "base_rate_brier",
    "bin_edges",
    "bin_index",
    "binned_brier",
    "bins",
    "bounds",
    "brier",
    "coverage",
    "murphy",
    "numbers_agree",
    "panel",
    "skill",
]

#: Five equal-width bins on [0, 1] — the resolution the phase ritual's 4–6 rows
#: can actually support.  More bins would report noise as structure.
BIN_COUNT = 5

Pair = tuple[float, int]


def bin_index(p: float) -> int:
    """Which of the :data:`BIN_COUNT` equal-width bins ``p`` falls in.

    The top bin is closed on the right so ``p == 1.0`` has a home; a slate
    refuses ``p`` outside the open interval (0, 1) long before this is reached.
    """
    return min(int(float(p) * BIN_COUNT), BIN_COUNT - 1)


def bin_edges(index: int) -> tuple[float, float]:
    return (index / BIN_COUNT, (index + 1) / BIN_COUNT)


def brier(pairs: Sequence[Pair]) -> float | None:
    """Mean ``(p − y)²`` over the resolved rows; ``None`` when there are none."""
    if not pairs:
        return None
    return sum((float(p) - float(y)) ** 2 for p, y in pairs) / len(pairs)


def base_rate_brier(forecast: float, pairs: Sequence[Pair]) -> float | None:
    """The same score for a constant forecast — the driver's frozen base rate."""
    if not pairs:
        return None
    return sum((float(forecast) - float(y)) ** 2 for _p, y in pairs) / len(pairs)


def skill(observed: float | None, base: float | None) -> float | None:
    """``1 − observed/base``; ``None`` when either is missing or ``base`` is 0."""
    if observed is None or base is None or base == 0:
        return None
    return 1.0 - observed / base


def bins(pairs: Sequence[Pair]) -> list[dict[str, object]]:
    """All :data:`BIN_COUNT` bins, always — an empty bin is a fact, not a gap.

    Reporting the empty bins keeps the table the same shape for every panel and
    every study, which is what makes two receipts comparable at all.
    """
    buckets: list[list[Pair]] = [[] for _ in range(BIN_COUNT)]
    for p, y in pairs:
        buckets[bin_index(p)].append((float(p), int(y)))
    rows: list[dict[str, object]] = []
    for index, bucket in enumerate(buckets):
        low, high = bin_edges(index)
        rows.append(
            {
                "lo": low,
                "hi": high,
                "n": len(bucket),
                "mean_p": (sum(p for p, _y in bucket) / len(bucket)) if bucket else None,
                "mean_y": (sum(y for _p, y in bucket) / len(bucket)) if bucket else None,
            }
        )
    return rows


def binned_brier(pairs: Sequence[Pair]) -> float | None:
    """Brier with each forecast replaced by its bin's mean forecast.

    This is the quantity the Murphy identity closes on exactly:
    ``binned_brier == reliability − resolution + uncertainty``.
    """
    if not pairs:
        return None
    total = 0.0
    for row in bins(pairs):
        count = int(row["n"] or 0)
        if not count:
            continue
        mean_p = float(row["mean_p"])  # type: ignore[arg-type]
        mean_y = float(row["mean_y"])  # type: ignore[arg-type]
        total += count * ((mean_p - mean_y) ** 2 + mean_y * (1.0 - mean_y))
    return total / len(pairs)


def murphy(pairs: Sequence[Pair]) -> tuple[float | None, float | None, float | None]:
    """``(reliability, resolution, uncertainty)`` over :data:`BIN_COUNT` bins.

    - reliability ``Σ nₖ (p̄ₖ − ȳₖ)² / n`` — how far the forecasts sit from what
      actually happened at that confidence.  Lower is better.
    - resolution ``Σ nₖ (ȳₖ − ȳ)² / n`` — how far the bins separate from the
      overall rate.  Higher is better; a constant forecaster scores 0.
    - uncertainty ``ȳ(1 − ȳ)`` — the difficulty of the events themselves, which
      no forecaster can change.
    """
    if not pairs:
        return (None, None, None)
    total = len(pairs)
    overall = sum(float(y) for _p, y in pairs) / total
    reliability = 0.0
    resolution = 0.0
    for row in bins(pairs):
        count = int(row["n"] or 0)
        if not count:
            continue
        mean_p = float(row["mean_p"])  # type: ignore[arg-type]
        mean_y = float(row["mean_y"])  # type: ignore[arg-type]
        reliability += count * (mean_p - mean_y) ** 2
        resolution += count * (mean_y - overall) ** 2
    return (reliability / total, resolution / total, overall * (1.0 - overall))


def bounds(
    pairs: Sequence[Pair], unresolved: Sequence[float]
) -> tuple[float | None, float | None]:
    """``(best_case, worst_case)`` Brier once every unresolved row is scored.

    The best case gives each censored row the outcome its forecast wanted
    (``y = 1`` when ``p ≥ 0.5``, else ``y = 0``); the worst case gives it the
    other one.  With no unresolved rows both equal the plain Brier.
    """
    if not pairs and not unresolved:
        return (None, None)
    best = [*pairs, *((float(p), 1 if float(p) >= 0.5 else 0) for p in unresolved)]
    worst = [*pairs, *((float(p), 0 if float(p) >= 0.5 else 1) for p in unresolved)]
    return (brier(best), brier(worst))


def coverage(resolved: int, cohort: int) -> float | None:
    """``resolved / cohort`` — and the denominator is the FROZEN cohort.

    Withdrawing a row does not shrink it (RF-05): a slate that quietly drops the
    hypotheses it did not like reports lower coverage, never a better Brier.
    """
    if cohort <= 0:
        return None
    return resolved / cohort


def panel(
    pairs: Sequence[Pair], unresolved: Sequence[float], *, base_rate: float
) -> dict[str, object]:
    """One panel's whole arithmetic, in the receipt's key order."""
    observed = brier(pairs)
    base = base_rate_brier(base_rate, pairs)
    reliability, resolution, uncertainty = murphy(pairs)
    best, worst = bounds(pairs, unresolved)
    return {
        "n": len(pairs),
        "brier": observed,
        "binned_brier": binned_brier(pairs),
        "base_rate_brier": base,
        "skill": skill(observed, base),
        "reliability": reliability,
        "resolution": resolution,
        "uncertainty": uncertainty,
        "bins": bins(pairs),
        "best_case_brier": best,
        "worst_case_brier": worst,
    }


def numbers_agree(left: object, right: object, *, rel_tol: float = 1e-12) -> list[str]:
    """Compare two recomputed structures; return one line per disagreement.

    Numbers are compared with :func:`math.isclose`, everything else exactly, so
    a receipt is judged on its arithmetic rather than on float formatting.
    """
    problems: list[str] = []
    _walk("", left, right, rel_tol, problems)
    return problems


def _walk(path: str, left: object, right: object, rel_tol: float, out: list[str]) -> None:
    where = path or "<root>"
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        for key in sorted(set(left) | set(right)):
            if key not in left:
                out.append(f"{where}.{key}: recorded is missing it")
            elif key not in right:
                out.append(f"{where}.{key}: recomputation does not produce it")
            else:
                _walk(f"{path}.{key}" if path else str(key), left[key], right[key], rel_tol, out)
        return
    if isinstance(left, Sequence) and isinstance(right, Sequence) and not isinstance(
        left, str | bytes
    ) and not isinstance(right, str | bytes):
        if len(left) != len(right):
            out.append(f"{where}: {len(left)} entries recorded, {len(right)} recomputed")
            return
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            _walk(f"{path}[{index}]", a, b, rel_tol, out)
        return
    if isinstance(left, bool) or isinstance(right, bool):
        if left is not right:
            out.append(f"{where}: recorded {left!r}, recomputed {right!r}")
        return
    if isinstance(left, int | float) and isinstance(right, int | float):
        if not math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=rel_tol):
            out.append(f"{where}: recorded {left!r}, recomputed {right!r}")
        return
    if left != right:
        out.append(f"{where}: recorded {left!r}, recomputed {right!r}")
