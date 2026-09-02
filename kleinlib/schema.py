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

import math

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

#: Schema-version 2 results are a *derived view* of immutable run manifests.  Keep
#: ``RESULTS_COLUMNS`` unchanged for legacy readers; callers select this explicitly.
V2_RESULTS_COLUMNS: tuple[str, ...] = (
    "experiment",
    "track",
    "primary_metric",
    "status",
    "commit",
    "description",
)

#: Columns that MAY follow the canonical five, in this order.
OPTIONAL_COLUMNS: tuple[str, ...] = ("study_id",)

#: The only honest outcomes for an experiment row.
VALID_STATUSES: frozenset[str] = frozenset({"keep", "discard", "crash"})

# --------------------------------------------------------------------------
# The three axes of a schema-3 inquiry (references/inquiry-model.md)
# --------------------------------------------------------------------------

#: Audience profiles that ship with Klein.  A repo that needs its own writes a
#: markdown profile and points ``profile_doc:`` at it — the ENGINE never reads
#: the skill directory, so a wheel installed in a foreign repo keeps working.
KNOWN_PROFILES: tuple[str, ...] = ("generic", "ml-research", "math", "insurance")

#: The evidence source's shape.  Selects the Gate-1 card variant and the split
#: vocabulary; it never changes what the engine checks.
KNOWN_MODALITIES: tuple[str, ...] = (
    "tabular",
    "timeseries",
    "image",
    "sequence",
    "graph",
    "text",
    "simulation",
    "none",
)

_CARD_SECTIONS_EVERY: tuple[str, ...] = (
    "Source & shape",
    "Ranked go / no-go issues",
    "Go / no-go",
)
_CARD_SECTIONS_TABLE: tuple[str, ...] = (
    "Profile summary",
    "Clean-room leakage audit",
)

#: Headings ``data_card.md`` must carry for each modality.  The DATA gate checks
#: heading PRESENCE only — the prose that belongs under each lives in
#: ``references/data-gate-protocol.md`` and ``assets/data-card-template.md``, and
#: this registry is what those two documents point at.
MODALITY_CARD_SECTIONS: dict[str, tuple[str, ...]] = {
    "tabular": _CARD_SECTIONS_EVERY + _CARD_SECTIONS_TABLE,
    "timeseries": _CARD_SECTIONS_EVERY + _CARD_SECTIONS_TABLE + ("Time policy",),
    "image": _CARD_SECTIONS_EVERY + _CARD_SECTIONS_TABLE + ("Group policy",),
    "sequence": _CARD_SECTIONS_EVERY + _CARD_SECTIONS_TABLE + ("Group policy",),
    "graph": _CARD_SECTIONS_EVERY + _CARD_SECTIONS_TABLE + ("Group policy",),
    "text": _CARD_SECTIONS_EVERY + _CARD_SECTIONS_TABLE + ("Group policy",),
    "simulation": _CARD_SECTIONS_EVERY + ("DGP card",),
    "none": _CARD_SECTIONS_EVERY + ("Verifier card",),
}

#: Placeholder in the commit field for a row with no surviving commit.
NO_COMMIT: str = "-"

#: Placeholder in the primary_metric field for crashed experiments.
NA_METRIC: str = "NA"

_HEX_DIGITS = frozenset("0123456789abcdef")


def header_line() -> str:
    """Return the canonical tab-joined header (no trailing newline)."""
    return "\t".join(RESULTS_COLUMNS)


def v2_header_line() -> str:
    """Return the schema-version 2 derived-ledger header."""
    return "\t".join(V2_RESULTS_COLUMNS)


def is_valid_v2_header(line: str) -> bool:
    """Return whether *line* is exactly the v2 derived-ledger header."""
    return tuple(line.rstrip("\r\n").split("\t")) == V2_RESULTS_COLUMNS


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
                numeric_metric = float(metric)
            except ValueError:
                problems.append(
                    f"primary_metric must be a float "
                    f"(or {NA_METRIC!r} on crash), got {metric!r}"
                )
            else:
                if not math.isfinite(numeric_metric):
                    problems.append(
                        f"primary_metric must be finite "
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

#: Numeric metric keys printed on EVERY run regardless of which evaluator a
#: study calls: the canonical block's unconditional numerics, the
#: `wall_seconds` line every evaluator prints since 1.2.0 (the study-05 F1
#: lesson), and the runner footer. `klein preflight` treats these as
#: guaranteed-visible when checking that every declared guardrail metric
#: will appear in the printed block the runner parses. Deliberately
#: excluded: non-numeric lines (``metric_name``, ``status``,
#: ``runner_status`` — ``parse_metric_log`` drops non-floats, so a
#: guardrail on one could never pass) and every key that prints ``NA`` or
#: nothing on at least one evaluator path (``training_seconds``/row counts
#: are ``NA`` for :func:`kleinlib.eval.evaluate_scalar`;
#: ``calibration_ratio``/``tweedie_power`` are conditional even within
#: regression). A blessed-but-unreachable key would turn the visibility
#: check into a false all-clear on exactly the failure it exists to catch.
#: Note: this ``wall_seconds`` is the EVALUATOR's total (identical to the
#: aux-sidecar row); the manifest's top-level ``wall_seconds`` measures the
#: whole subprocess and is a different, larger quantity.
AUTO_PRINTED_METRIC_KEYS: frozenset[str] = frozenset({
    "primary_metric",
    "total_seconds",
    "wall_seconds",
    "runner_exit_code",
})

#: Aux keys each evaluator prints unconditionally FOR ITSELF (numeric on
#: every one of its runs). `klein preflight` adds the union of the sets
#: whose evaluator name appears in the study's Python sources.
EVALUATOR_PRINTED_KEYS: dict[str, frozenset[str]] = {
    "evaluate": frozenset({
        "training_seconds",
        "train_rows",
        "val_rows",
        "val_pr_auc",
        "val_logloss",
        "val_brier",
        "val_lift_top10",
        "val_best_threshold",
        "val_f1_at_best",
    }),
    "evaluate_regression": frozenset({
        "training_seconds",
        "train_rows",
        "val_rows",
        "val_rmse",
        "val_mae",
        "val_r2",
    }),
    "evaluate_scalar": frozenset(),
}
