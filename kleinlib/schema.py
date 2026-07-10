"""Klein results-schema contract — the single source of truth.

This module is THE authority on the shape of ``results.tsv`` and its
``aux_metrics.tsv`` sidecar. Every consumer — preflight, summarize,
study templates, docs, CI drift tests — must import these names or
point here; restating the column list anywhere else is a bug. (A
4-column vs 5-column doc drift once corrupted appends in the ancestor
project; this file exists so that class of bug is structurally
impossible.)

Pure stdlib. Safe to import from any environment.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# results.tsv
# --------------------------------------------------------------------------

#: Canonical column order for results.tsv. Do not restate elsewhere.
RESULTS_COLUMNS: tuple[str, ...] = (
    "experiment",
    "primary_metric",
    "status",
    "commit",
    "description",
)

#: Columns that MAY follow the canonical five, in this order.
OPTIONAL_COLUMNS: tuple[str, ...] = ("study_id",)

#: The only honest outcomes for an experiment row.
VALID_STATUSES: frozenset[str] = frozenset({"keep", "discard", "crash"})

#: Placeholder in the commit field for a row with no surviving commit.
NO_COMMIT: str = "-"

#: Placeholder in the primary_metric field for crashed experiments.
NA_METRIC: str = "NA"

_HEX_DIGITS = frozenset("0123456789abcdef")


def header_line() -> str:
    """Return the canonical tab-joined header (no trailing newline)."""
    return "\t".join(RESULTS_COLUMNS)


def is_valid_header(line: str) -> bool:
    """Return True if *line* is an acceptable results.tsv header.

    Accepts the canonical columns exactly, or the canonical columns
    followed by a prefix of :data:`OPTIONAL_COLUMNS` (e.g. a trailing
    ``study_id``). Anything else — reordered, missing, or unknown
    columns — is invalid.
    """
    fields = tuple(line.rstrip("\r\n").split("\t"))
    n = len(RESULTS_COLUMNS)
    if fields[:n] != RESULTS_COLUMNS:
        return False
    extra = fields[n:]
    return extra == OPTIONAL_COLUMNS[: len(extra)]


def validate_row(fields: list[str], *, n_columns: int) -> list[str]:
    """Validate one data row; return problem strings (empty list = valid).

    *n_columns* is the field count of the file's actual header, so rows
    are checked against the header present (5 canonical columns, or 6
    when ``study_id`` is in use). Fields beyond those present are
    skipped rather than guessed at.
    """
    problems: list[str] = []
    if len(fields) != n_columns:
        problems.append(
            f"expected {n_columns} fields to match header, got {len(fields)}"
        )

    def _field(name: str) -> str | None:
        idx = RESULTS_COLUMNS.index(name)
        return fields[idx] if idx < len(fields) else None

    experiment = _field("experiment")
    if experiment is not None:
        try:
            int(experiment)
        except ValueError:
            problems.append(f"experiment must be an integer, got {experiment!r}")

    status = _field("status")
    if status is not None and status not in VALID_STATUSES:
        problems.append(
            f"status must be one of {sorted(VALID_STATUSES)}, got {status!r}"
        )

    metric = _field("primary_metric")
    if metric is not None:
        if metric == NA_METRIC:
            if status != "crash":
                problems.append(
                    f"primary_metric may be {NA_METRIC!r} only when status is 'crash'"
                )
        else:
            try:
                float(metric)
            except ValueError:
                problems.append(
                    f"primary_metric must be a float "
                    f"(or {NA_METRIC!r} on crash), got {metric!r}"
                )

    commit = _field("commit")
    if commit is not None and commit != NO_COMMIT:
        if not (7 <= len(commit) <= 40) or not set(commit.lower()) <= _HEX_DIGITS:
            problems.append(
                f"commit must be 7-40 hex chars or {NO_COMMIT!r}, got {commit!r}"
            )

    return problems


# --------------------------------------------------------------------------
# aux_metrics.tsv sidecar (long format: one metric per line)
# --------------------------------------------------------------------------

#: Filename of the per-study auxiliary-metrics sidecar.
AUX_SIDECAR: str = "aux_metrics.tsv"

#: Column order for the sidecar. Everything that is not THE primary
#: metric (PR-AUC, brier, wall_seconds, model_path, ...) goes here.
AUX_COLUMNS: tuple[str, ...] = ("experiment", "metric", "value")
