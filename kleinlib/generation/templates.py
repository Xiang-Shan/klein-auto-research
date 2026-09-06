"""The three discovery-cell table producers — library code, never the surface.

A discovery cell asks one question of a table: *does any segment deviate from
what we said to expect?*  Three shapes cover the field-general cases, and all
three reduce to the same contract — **one row per unit, carrying
the quantity whose mean is the segment's statistic**:

``residual_by_segment``
    mean signed observation-minus-expectation.  Ecological residuals by
    habitat, assay bias by batch, pricing residuals by territory.
``error_slices``
    mean declared loss by segment.  Which slice does the model serve worst?
``family_disagreement``
    the signed difference between two competing models' expected quantities.
    Where do two constitutive laws part company?

**Why the pinned table is per-unit and not per-segment.**  The multiplicity
rule this capability offers first is a sign-flip max-t
(:func:`kleinlib.metrology.family_maxt`), and a sign flip acts on UNITS.  A
summary table of means cannot be re-permuted, so a summary-only artifact would
leave the family correction un-recomputable — and an un-recomputable screening
correction is exactly the denominator hiding that surprise mining exists to
prevent.  The per-unit table is the evidence; the per-segment summary is
derived from it, by ``klein generation surprise record`` and again by
``klein generation verify``, and the two must agree to the last digit.

**These functions are pure and they are not the mutable surface.**  A study's
entrypoint imports them, an adapter (``lib/<adapter>.py``, hashed at
registration and outside ``entrypoint.mutable``) maps field measurements into
their arguments, and the cell's table is written where the registration said it
would be.  Nothing here proposes a segmentation, chooses a template, or decides
whether a deviation is interesting.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

__all__ = [
    "EXPECTATION_FOR_STATISTIC",
    "STATISTIC_FOR_TEMPLATE",
    "STATISTICS",
    "TABLE_COLUMNS",
    "TEMPLATES",
    "aggregate_by_group",
    "error_slices",
    "family_disagreement",
    "parse_table",
    "printed_summary",
    "render_table",
    "residual_by_segment",
    "segments_in_order",
    "slug",
    "slug_collisions",
    "table_columns",
]

#: The pinned table's columns.  One row per unit; the header is exact.
TABLE_COLUMNS: tuple[str, ...] = ("segment", "unit", "value")


def table_columns(group_column: str | None = None) -> tuple[str, ...]:
    """The header a cell's pinned table must carry.

    Three columns for a unit-level cell — unchanged, and the only shape that
    existed before clustered cells.  A cell whose ``group_policy`` names a
    clustering column carries that column FOURTH, under its own declared name,
    so "the group column is absent from the table" is a comparison of two
    headers rather than a convention a reader has to be told.
    """
    return TABLE_COLUMNS if not group_column else (*TABLE_COLUMNS, str(group_column))

#: The three producers, by the name a cell declares as its ``template``.
TEMPLATES: tuple[str, ...] = (
    "residual_by_segment",
    "error_slices",
    "family_disagreement",
)

#: The statistic each template produces.  A cell declares BOTH, and
#: :mod:`kleinlib.generation.surprise` refuses a mismatched pair: the statistic
#: names what the number means, the template names how it was computed, and a
#: cell that gets them out of step is measuring something nobody registered.
STATISTIC_FOR_TEMPLATE: dict[str, str] = {
    "residual_by_segment": "mean_signed_residual",
    "error_slices": "mean_loss",
    "family_disagreement": "distance",
}

STATISTICS: tuple[str, ...] = tuple(dict.fromkeys(STATISTIC_FOR_TEMPLATE.values()))

#: Where each statistic's expectation comes from — the null the deviation is
#: measured against, fixed by the statistic and never by the outcome.
#:
#: ``zero``
#:     A calibrated expectation has zero mean signed residual, and two families
#:     that agree differ by zero.  The expectation is a property of the claim
#:     being tested, so it is a constant.
#: ``pooled_mean``
#:     "No slice is worse than the whole" — the expectation is the mean over
#:     EVERY unit in the table, which is why the table must carry every eligible
#:     segment before it can be computed at all.
EXPECTATION_FOR_STATISTIC: dict[str, str] = {
    "mean_signed_residual": "zero",
    "mean_loss": "pooled_mean",
    "distance": "zero",
}

_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")


def slug(value: Any) -> str:
    """A printed-key-safe rendering of a segment name (``[A-Za-z][A-Za-z0-9_]*``).

    Segment names are the driver's own vocabulary — ``"wet meadow"``, ``"38.5°C"``
    — and the printed block's grammar is narrower than that
    (``kleinlib.decision.METRIC_LINE_RE``).  The slug is for the PRINTED key
    only; the table, the record and the receipts all carry the segment name
    verbatim.
    """
    text = _SLUG_RE.sub("_", str(value)).strip("_")
    if not text:
        text = "segment"
    return text if text[0].isalpha() else f"s_{text}"


def slug_collisions(names: Iterable[Any]) -> dict[str, list[str]]:
    """``{printed key: the segment names that all render to it}`` — collisions only.

    ``"38.5°C"`` and ``"38 5 C"`` are different segments and the same printed
    key.  A family whose printed block cannot name its members one-to-one
    cannot have its expectation adjudicated segment by segment, so the
    collision is refused at registration rather than discovered in a block.
    """
    grouped: dict[str, list[str]] = {}
    for name in names:
        grouped.setdefault(slug(name), []).append(str(name))
    return {key: values for key, values in grouped.items() if len(values) > 1}


def _number(row: Mapping[str, Any], column: str, index: int) -> float:
    if column not in row:
        raise KeyError(f"row {index}: no column {column!r} (columns: {sorted(row)})")
    try:
        value = float(row[column])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {index}: {column}={row[column]!r} is not a number") from exc
    if not math.isfinite(value):
        raise ValueError(
            f"row {index}: {column}={row[column]!r} is not finite — a non-finite unit is "
            "not a measurement, and dropping it silently would shrink the denominator"
        )
    return value


def _unit_id(row: Mapping[str, Any], column: str | None, index: int) -> str:
    if column is None:
        return str(index)
    if column not in row:
        raise KeyError(f"row {index}: no unit column {column!r}")
    text = str(row[column]).strip()
    if not text:
        raise ValueError(f"row {index}: unit column {column!r} is empty")
    return text


def _segment(row: Mapping[str, Any], column: str, index: int) -> str:
    if column not in row:
        raise KeyError(f"row {index}: no segment column {column!r}")
    text = str(row[column]).strip()
    if not text:
        raise ValueError(f"row {index}: segment column {column!r} is empty")
    return text


def _rows(
    rows: Iterable[Mapping[str, Any]],
    segment_column: str,
    unit_column: str | None,
    value_of: Any,
    group_column: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise TypeError(f"row {index}: expected a mapping, got {type(row).__name__}")
        segment = _segment(row, segment_column, index)
        unit = _unit_id(row, unit_column, index)
        key = (segment, unit)
        if key in seen:
            raise ValueError(
                f"row {index}: unit {unit!r} appears twice in segment {segment!r} — "
                "unit ids are the randomization units the family rule flips, so they "
                "must be unique inside a segment"
            )
        seen.add(key)
        made = {"segment": segment, "unit": unit, "value": value_of(row, index)}
        if group_column is not None:
            made["group"] = _group(row, group_column, index)
        out.append(made)
    if not out:
        raise ValueError("no rows — a cell that measured nothing has not measured anything")
    return out


def _group(row: Mapping[str, Any], column: str, index: int) -> str:
    if column not in row:
        raise KeyError(f"row {index}: no group column {column!r}")
    text = str(row[column]).strip()
    if not text:
        raise ValueError(
            f"row {index}: group column {column!r} is empty — a unit with no cluster "
            "cannot be flipped with its cluster, and dropping it would shrink the family"
        )
    return text


def aggregate_by_group(units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Collapse a per-unit table to one row per (segment, group): the group's mean.

    This is the whole of group-level inference.  When a cell's ``group_policy``
    names a clustering column, the segment's statistic is the mean of the GROUP
    means, the dispersion is over groups, and the sign flip
    (:func:`kleinlib.metrology.family_maxt`) acts on groups — because a sign flip
    that treats correlated units as independent understates the null spread and
    manufactures violations.  Running the identical arithmetic on this collapsed
    table is what makes the two levels of inference one implementation.

    Groups are ordered by name within a segment so the family's slot alignment
    is a pure function of the pinned bytes, exactly as it is per unit.
    """
    totals: dict[tuple[str, str], list[float]] = {}
    order: list[tuple[str, str]] = []
    for index, row in enumerate(units, start=1):
        group = row.get("group")
        if not isinstance(group, str) or not group.strip():
            raise ValueError(f"row {index}: no group value — this table is not clustered")
        key = (str(row["segment"]), group.strip())
        if key not in totals:
            totals[key] = []
            order.append(key)
        totals[key].append(float(row["value"]))
    segments = list(dict.fromkeys(segment for segment, _group_name in order))
    out: list[dict[str, Any]] = []
    for segment in segments:
        members = sorted(name for seg, name in order if seg == segment)
        for name in members:
            values = totals[(segment, name)]
            out.append(
                {
                    "segment": segment,
                    "unit": name,
                    "value": sum(values) / len(values),
                    "group": name,
                    "n_units": len(values),
                }
            )
    return out


def residual_by_segment(
    rows: Iterable[Mapping[str, Any]],
    *,
    segment_column: str,
    observed_column: str,
    expected_column: str,
    unit_column: str | None = None,
    group_column: str | None = None,
) -> list[dict[str, Any]]:
    """Signed observation-minus-expectation per unit (``mean_signed_residual``).

    The expectation is the model's, column by column: the template subtracts,
    it does not fit.  A segment whose residuals average away from zero is the
    surprise; ``expected: 0`` is the null every segment is measured against.

    ``group_column`` carries each unit's cluster into the table when the cell
    declared one; the rows stay per-unit either way.
    """
    return _rows(
        rows,
        segment_column,
        unit_column,
        lambda row, index: _number(row, observed_column, index)
        - _number(row, expected_column, index),
        group_column,
    )


def error_slices(
    rows: Iterable[Mapping[str, Any]],
    *,
    segment_column: str,
    loss_column: str,
    unit_column: str | None = None,
    group_column: str | None = None,
) -> list[dict[str, Any]]:
    """The declared per-unit loss (``mean_loss``).

    The loss is whatever the study declared it to be — squared error, absolute
    deviance, a domain cost — computed by the adapter, never here.  The
    expectation is the POOLED mean over every unit in the table, so the question
    is "is this slice served worse than the whole", and the whole cannot be
    computed unless every eligible segment is present.
    """
    return _rows(
        rows,
        segment_column,
        unit_column,
        lambda row, index: _number(row, loss_column, index),
        group_column,
    )


def family_disagreement(
    rows: Iterable[Mapping[str, Any]],
    *,
    segment_column: str,
    left_column: str,
    right_column: str,
    unit_column: str | None = None,
    group_column: str | None = None,
) -> list[dict[str, Any]]:
    """The SIGNED difference between two families' expected quantities (``distance``).

    Signed, not absolute: an absolute distance has no zero-centred null and no
    direction to report, and "family A reads high in this segment" is a
    different finding from "family B does".  A study that genuinely wants an
    unsigned distance declares it as the loss of an ``error_slices`` cell, where
    the pooled mean is the honest expectation.
    """
    return _rows(
        rows,
        segment_column,
        unit_column,
        lambda row, index: _number(row, left_column, index)
        - _number(row, right_column, index),
        group_column,
    )


def render_table(units: Sequence[Mapping[str, Any]], group_column: str | None = None) -> str:
    """The pinned TSV, deterministic: the header, then the units in ORDER.

    Order is load-bearing.  ``family_maxt`` applies ONE sign vector jointly to
    the whole family, so which unit of segment A shares a sign with which unit
    of segment B is fixed by position in this file — which makes the adjusted
    scores a pure function of the pinned bytes, and re-derivable by anyone.

    A clustered cell passes its ``group_column``; the column is written fourth,
    under the name the registration declared.
    """
    lines = ["\t".join(table_columns(group_column))]
    for row in units:
        cells = [
            str(row["segment"]).replace("\t", " "),
            str(row["unit"]).replace("\t", " "),
            format(float(row["value"]), ".12g"),
        ]
        if group_column:
            cells.append(str(row["group"]).replace("\t", " "))
        lines.append("\t".join(cells))
    return "\n".join(lines) + "\n"


def parse_table(text: str, group_column: str | None = None) -> list[dict[str, Any]]:
    """Read a pinned cell table back.  Raises ``ValueError`` on anything unusable.

    With no ``group_column`` the header must be exactly the three unit-level
    columns — the shape every unclustered cell has always written.  With one,
    the header must carry that column fourth, by name: a cell that declared a
    clustering column and pinned a table without it measured something else.
    """
    wanted = table_columns(group_column)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("the cell table is empty")
    header = tuple(lines[0].split("\t"))
    if header != wanted:
        raise ValueError(
            f"the cell table's header is {list(header)}, expected {list(wanted)}"
        )
    units: list[dict[str, Any]] = []
    for number, line in enumerate(lines[1:], start=2):
        parts = line.split("\t")
        if len(parts) != len(wanted):
            raise ValueError(f"line {number}: {len(parts)} column(s), expected {len(wanted)}")
        try:
            value = float(parts[2])
        except ValueError as exc:
            raise ValueError(f"line {number}: value {parts[2]!r} is not a number") from exc
        if not math.isfinite(value):
            raise ValueError(f"line {number}: value {parts[2]!r} is not finite")
        unit: dict[str, Any] = {"segment": parts[0], "unit": parts[1], "value": value}
        if group_column:
            if not parts[3].strip():
                raise ValueError(f"line {number}: the {group_column!r} column is empty")
            unit["group"] = parts[3]
        units.append(unit)
    if not units:
        raise ValueError("the cell table carries no units")
    return units


def segments_in_order(units: Sequence[Mapping[str, Any]]) -> list[str]:
    """The segments the table carries, first appearance first."""
    return list(dict.fromkeys(str(row["segment"]) for row in units))


def printed_summary(
    units: Sequence[Mapping[str, Any]],
    *,
    statistic: str,
    prefix: str = "cell",
    grouped: bool = False,
) -> dict[str, float]:
    """The numbers a cell's entrypoint prints, so a registered rule can fire.

    The registered ``expectation_P`` is adjudicated by the notary on the PRINTED
    block, not on this table, so the quantities its rule needs have to be
    printed: the family size, the smallest segment, the largest absolute
    deviation, and one ``<prefix>_deviation_<segment>`` per segment.  A cell
    whose expectation is "no segment deviates by more than δ" writes
    ``{key: cell_max_abs_deviation, op: "<", value: δ}`` and needs nothing else.

    These are summaries for the RULE.  The verdicts are not here and cannot be:
    they need the multiplicity rule, which is applied once, afterwards, by
    ``klein generation surprise record``.

    ``grouped=True`` collapses the table to its group means first, so a
    clustered cell's printed deviations are the ones its record will recompute.
    """
    if statistic not in EXPECTATION_FOR_STATISTIC:
        raise ValueError(
            f"unknown statistic {statistic!r}; expected one of {', '.join(STATISTICS)}"
        )
    if grouped:
        units = aggregate_by_group(units)
    collisions = slug_collisions(segments_in_order(units))
    if collisions:
        raise ValueError(
            "segment names collide on one printed key: "
            + "; ".join(
                f"{key} <- {', '.join(names)}" for key, names in sorted(collisions.items())
            )
            + " — the printed block must be able to name each segment once"
        )
    values = [float(row["value"]) for row in units]
    pooled = sum(values) / len(values) if values else 0.0
    expected = pooled if EXPECTATION_FOR_STATISTIC[statistic] == "pooled_mean" else 0.0
    printed: dict[str, float] = {}
    deviations: list[float] = []
    counts: list[int] = []
    for segment in segments_in_order(units):
        members = [float(row["value"]) for row in units if str(row["segment"]) == segment]
        deviation = sum(members) / len(members) - expected
        deviations.append(deviation)
        counts.append(len(members))
        printed[f"{prefix}_deviation_{slug(segment)}"] = deviation
    printed[f"{prefix}_segments"] = float(len(counts))
    printed[f"{prefix}_units"] = float(len(values))
    printed[f"{prefix}_min_n"] = float(min(counts)) if counts else 0.0
    printed[f"{prefix}_expected"] = expected
    printed[f"{prefix}_max_abs_deviation"] = max((abs(d) for d in deviations), default=0.0)
    return printed
