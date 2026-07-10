#!/usr/bin/env python3
"""
Summarize a Klein Auto Research results.tsv file and generate a simple SVG
progress plot.

This script intentionally uses only the Python standard library for its core
path (``argparse``/``csv``/``html``/``math``/``re`` — no plotting or data
libraries). PyYAML is used opportunistically for richer study.yaml parsing
when available (it is a core dependency of this repo) but every
yaml-dependent feature degrades gracefully — via a tiny hand-rolled parser
for the ``phases:`` block — when PyYAML is absent, e.g. in a foreign repo
that only copied this skill directory.

Features
--------

- Header-based TSV parsing (never positional) — a results.tsv with reordered
  columns parses identically to the canonical order.
- higher/lower goal support, auto-detected from the metric column name or
  set explicitly with ``--goal``.
- ``results_summary.md`` (frontier + keep/discard/crash counts) and
  ``progress.svg`` (stdlib SVG line/scatter plot).
- Aux panels: ``--aux <metric> [--aux-goal higher|lower]`` renders a top-10
  table for any metric in the study's ``aux_metrics.tsv`` sidecar (long
  format: experiment / metric / value), alongside the primary metric. Two
  panels — ``val_brier`` (lower) and ``val_lift_top10`` (higher) — render
  automatically whenever the sidecar exists and carries those metrics.
- Phase telemetry: when a ``study.yaml`` with a ``phases:`` block (each
  phase: ``id``, ``budget_h``, and an experiment range) sits next to
  results.tsv, and ``wall_seconds`` rows exist in the aux sidecar, a
  "phase actual vs budget" table is rendered (actual = sum of that phase's
  experiments' wall_seconds, converted to hours).
- ``--expand-study <study_id>`` prints the sweep sidecar table from
  ``sweeps/<study_id>.sidecar.tsv`` (relative to results.tsv's directory) if
  present.
"""

from __future__ import annotations

import argparse
import csv
import html
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised via the tiny fallback parser
    yaml = None  # type: ignore


# --------------------------------------------------------------------------
# Schema pointer (see kleinlib/schema.py — the single source of truth).
# Foreign-repo mode (no kleinlib on the path) falls back to the same
# literal values; this script does not restate the schema, only mirrors it.
# --------------------------------------------------------------------------

_FALLBACK_AUX_COLUMNS = ("experiment", "metric", "value")
try:
    _REPO_ROOT = Path(__file__).resolve().parents[4]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from kleinlib.schema import AUX_COLUMNS as _K_AUX_COLUMNS  # type: ignore
except ImportError:
    AUX_COLUMNS = _FALLBACK_AUX_COLUMNS
else:
    AUX_COLUMNS = tuple(_K_AUX_COLUMNS)


KNOWN_METRIC_COLUMNS = [
    "primary_metric",
    "metric",
    "val_auc",
    "val_accuracy",
    "val_loss",
    "val_rmse",
    "val_bpb",
    "score",
]
LOWER_IS_BETTER_HINTS = (
    "loss",
    "error",
    "rmse",
    "mae",
    "bpb",
    "perplexity",
    "brier",
    "logloss",
    "log_loss",
)

#: Automatic aux panels rendered whenever the sidecar exists and carries
#: these metrics — (metric_name, goal). See kleinlib eval additions
#: (PR-AUC, logloss, brier, lift@10, wall_seconds, ...).
AUTO_AUX_PANELS: tuple[tuple[str, str], ...] = (
    ("val_brier", "lower"),
    ("val_lift_top10", "higher"),
)


@dataclass
class ResultRow:
    row_number: int
    commit: str
    metric: float | None
    status: str
    description: str
    raw: dict[str, str]
    experiment_num: int | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize results.tsv and generate a plot.")
    parser.add_argument("results_path", type=Path, help="Path to results.tsv")
    parser.add_argument("--metric-col", help="Metric column name. Defaults to auto-detect.")
    parser.add_argument(
        "--goal",
        choices=("higher", "lower"),
        help="Optimization direction. Defaults to inference from the metric name.",
    )
    parser.add_argument("--title", help="Optional plot title override.")
    parser.add_argument("--summary-out", type=Path, help="Output markdown path.")
    parser.add_argument("--plot-out", type=Path, help="Output SVG path.")
    parser.add_argument(
        "--aux",
        help="Aux metric name (from aux_metrics.tsv) for an extra top-10 panel.",
    )
    parser.add_argument(
        "--aux-goal",
        choices=("higher", "lower"),
        help="Direction for --aux. Defaults to inference from the metric name.",
    )
    parser.add_argument(
        "--aux-path",
        type=Path,
        help="Path to aux_metrics.tsv (default: alongside results.tsv).",
    )
    parser.add_argument(
        "--study-yaml",
        type=Path,
        help="Path to study.yaml for phase telemetry (default: alongside results.tsv).",
    )
    parser.add_argument(
        "--expand-study",
        metavar="STUDY_ID",
        help="Print sweeps/<STUDY_ID>.sidecar.tsv (relative to results.tsv's directory) if present.",
    )
    parser.add_argument(
        "--sweeps-dir",
        type=Path,
        help="Directory holding sweep sidecars (default: <results dir>/sweeps).",
    )
    return parser.parse_args(argv)


def pick_metric_column(fieldnames: list[str], requested: str | None) -> str:
    if requested:
        if requested not in fieldnames:
            raise ValueError(f"Requested metric column {requested!r} not found in TSV header")
        return requested
    for name in KNOWN_METRIC_COLUMNS:
        if name in fieldnames:
            return name
    for name in fieldnames:
        if name not in {"experiment", "commit", "status", "description", "memory_gb", "metric_name", "metric_goal"}:
            return name
    raise ValueError("Could not infer a metric column from the TSV header")


def infer_goal(metric_col: str, requested: str | None) -> str:
    if requested:
        return requested
    name = metric_col.lower()
    return "lower" if any(token in name for token in LOWER_IS_BETTER_HINTS) else "higher"


def maybe_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _maybe_int(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def read_results(path: Path, metric_col: str) -> tuple[list[str], list[ResultRow]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if not reader.fieldnames:
            raise ValueError("results.tsv is empty or missing a header row")
        rows: list[ResultRow] = []
        for row_number, raw in enumerate(reader, start=1):
            rows.append(
                ResultRow(
                    row_number=row_number,
                    commit=(raw.get("commit") or "").strip(),
                    metric=maybe_float(raw.get(metric_col)),
                    status=(raw.get("status") or "").strip().lower(),
                    description=(raw.get("description") or "").strip(),
                    raw=raw,
                    experiment_num=_maybe_int(raw.get("experiment")),
                )
            )
    return reader.fieldnames, rows


def is_better(candidate: float, incumbent: float, goal: str) -> bool:
    return candidate > incumbent if goal == "higher" else candidate < incumbent


def running_frontier(rows: list[ResultRow], goal: str) -> list[ResultRow]:
    frontier: list[ResultRow] = []
    best_value: float | None = None
    for row in rows:
        if row.metric is None or row.status == "crash":
            continue
        if best_value is None or is_better(row.metric, best_value, goal):
            frontier.append(row)
            best_value = row.metric
    return frontier


def format_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"


# --------------------------------------------------------------------------
# Aux sidecar (long format: experiment / metric / value)
# --------------------------------------------------------------------------


def read_aux_metrics(path: Path) -> dict[str, dict[int, float]] | None:
    """Parse aux_metrics.tsv into ``{metric_name: {experiment_num: value}}``.

    Returns ``None`` when the sidecar does not exist so callers can degrade
    gracefully rather than rendering an empty/misleading panel.
    """
    if not path.exists():
        return None
    table: dict[str, dict[int, float]] = {}
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            if not reader.fieldnames:
                return None
            for raw in reader:
                exp = _maybe_int(raw.get("experiment"))
                metric = (raw.get("metric") or "").strip()
                value = maybe_float(raw.get("value"))
                if exp is None or not metric or value is None:
                    continue
                table.setdefault(metric, {})[exp] = value
    except OSError:
        return None
    return table


def build_aux_panel(
    metric_name: str,
    goal: str,
    metric_col: str,
    rows: list[ResultRow],
    values: dict[int, float],
) -> list[str]:
    lines = [
        f"### {metric_name} ({goal}) — top 10",
        "",
        f"| Run | Commit | {metric_name} | {metric_col} | Status | Description |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    entries: list[tuple[ResultRow, float]] = []
    for row in rows:
        key = row.experiment_num if row.experiment_num is not None else row.row_number
        if key in values:
            entries.append((row, values[key]))
    if not entries:
        lines.append(f"| - | - | - | - | - | no rows with `{metric_name}` in aux_metrics.tsv |")
        lines.append("")
        return lines
    entries.sort(key=lambda pair: pair[1], reverse=(goal == "higher"))
    for row, value in entries[:10]:
        lines.append(
            f"| {row.row_number} | `{row.commit or 'n/a'}` | {value:.6f} | {format_metric(row.metric)} | "
            f"{row.status or 'n/a'} | {row.description or 'n/a'} |"
        )
    lines.append("")
    return lines


def build_aux_section(
    rows: list[ResultRow],
    metric_col: str,
    aux_table: dict[str, dict[int, float]] | None,
    custom: tuple[str, str] | None = None,
) -> list[str]:
    """Assemble the "## Aux Panels" block: the two automatic panels (when
    their metric is present) plus an optional user-requested ``--aux`` one.
    Returns ``[]`` when there is nothing to show (no sidecar, no data).
    """
    if not aux_table:
        if custom is not None:
            return [
                "## Aux Panels",
                "",
                f"_aux_metrics.tsv sidecar not found; cannot render `--aux {custom[0]}` panel._",
            ]
        return []

    panels: list[tuple[str, str]] = list(AUTO_AUX_PANELS)
    if custom is not None and custom not in panels:
        panels.append(custom)

    body: list[str] = []
    rendered_any = False
    for metric_name, goal in panels:
        values = aux_table.get(metric_name)
        if not values:
            continue
        rendered_any = True
        body.extend(build_aux_panel(metric_name, goal, metric_col, rows, values))
    if not rendered_any:
        return []
    return ["## Aux Panels", ""] + body


# --------------------------------------------------------------------------
# Phase telemetry (study.yaml `phases:` block; actual = sum of that phase's
# experiments' wall_seconds from the aux sidecar, converted to hours)
# --------------------------------------------------------------------------

# Canonical phases-block shape this parser understands (documented for
# assets/study.yaml-template authors):
#
#   phases:
#     - id: phase0-baseline
#       budget_h: 0.5
#       experiments: {min: 1, max: 3}
#     - id: phase1-tuning
#       budget_h: 1.0
#       experiments: {min: 4, max: 8}
#
# A flat `min`/`max` directly on the phase (instead of nested under
# `experiments`/`experiment_range`/`range`) is also accepted.
# NOTE: `min_experiments`/`max_experiments` (assets/study-template.yaml) are
# COUNT bounds for the phase stop rule, not ID ranges — they are deliberately
# ignored here. A phase without an explicit ID range gets no telemetry row.

_RANGE_KEYS = ("experiments", "experiment_range", "range")
_PHASES_LINE_RE = re.compile(r"^phases:\s*(#.*)?$")
_LIST_ITEM_RE = re.compile(r"^-\s*(.*)$")


def _parse_flow_mapping(text: str) -> dict[str, str]:
    """Parse a tiny flow mapping like ``{min: 1, max: 3}`` -> {'min': '1', ...}."""
    inner = text.strip()
    if inner.startswith("{") and inner.endswith("}"):
        inner = inner[1:-1]
    result: dict[str, str] = {}
    for part in inner.split(","):
        if ":" not in part:
            continue
        k, _, v = part.partition(":")
        result[k.strip()] = v.strip().strip("'\"")
    return result


def _coerce_phase(raw: dict[str, object]) -> dict[str, object]:
    """Normalize a raw phase mapping (from either yaml.safe_load or the tiny
    parser) into ``{"id": str, "budget_h": float|None, "min": int|None, "max": int|None}``.
    """
    raw_id = raw.get("id")
    norm: dict[str, object] = {"id": "n/a" if raw_id is None or raw_id == "" else raw_id}
    budget = raw.get("budget_h")
    try:
        norm["budget_h"] = float(budget) if budget is not None and budget != "" else None
    except (TypeError, ValueError):
        norm["budget_h"] = None

    range_map: dict[str, object] | None = None
    for key in _RANGE_KEYS:
        candidate = raw.get(key)
        if isinstance(candidate, dict):
            range_map = candidate
            break
        if isinstance(candidate, str) and candidate.strip().startswith("{"):
            range_map = _parse_flow_mapping(candidate)
            break

    # min_experiments/max_experiments are COUNT bounds for the stop rule,
    # NOT experiment-ID ranges — never read them here. Attribution needs an
    # explicit `experiments: {min,max}` ID range (or flat min/max).
    min_v = (range_map or {}).get("min", raw.get("min"))
    max_v = (range_map or {}).get("max", raw.get("max"))
    try:
        norm["min"] = int(min_v) if min_v is not None and min_v != "" else None
    except (TypeError, ValueError):
        norm["min"] = None
    try:
        norm["max"] = int(max_v) if max_v is not None and max_v != "" else None
    except (TypeError, ValueError):
        norm["max"] = None
    return norm


def _tiny_parse_phases(text: str) -> list[dict[str, object]] | None:
    """Stdlib-only fallback extractor for just the ``phases:`` block, used
    when PyYAML is unavailable (or fails). Not a general YAML parser — it
    only understands the canonical shape documented above (a top-level
    ``phases:`` list of mappings, one level deep, with an optional
    flow-mapping value for the experiment range).
    """
    lines = text.splitlines()
    base_indent: int | None = None
    start = None
    for idx, line in enumerate(lines):
        if _PHASES_LINE_RE.match(line.strip()):
            base_indent = len(line) - len(line.lstrip(" "))
            start = idx
            break
    if start is None:
        return None

    raw_phases: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in lines[start + 1 :]:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= (base_indent or 0):
            break
        stripped = line.strip()
        item_match = _LIST_ITEM_RE.match(stripped)
        if item_match:
            if current is not None:
                raw_phases.append(current)
            current = {}
            stripped = item_match.group(1).strip()
            if not stripped:
                continue
        if current is None:
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            current[key.strip()] = value.strip()
    if current is not None:
        raw_phases.append(current)

    return [_coerce_phase(p) for p in raw_phases]


def _load_phases(path: Path) -> list[dict[str, object]] | None:
    """Load the ``phases:`` block of a study.yaml. Returns ``None`` when the
    file is missing, has no ``phases:`` key, or cannot be parsed at all —
    every branch degrades gracefully rather than raising, so a missing or
    foreign-shaped study.yaml never crashes summarize_results.py.
    """
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    if yaml is not None:
        try:
            data = yaml.safe_load(text)
        except Exception:
            return _tiny_parse_phases(text)
        if not isinstance(data, dict):
            return None
        phases = data.get("phases")
        if not isinstance(phases, list):
            return None
        return [_coerce_phase(p) for p in phases if isinstance(p, dict)]

    return _tiny_parse_phases(text)


def _fmt_hours(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def build_phase_table(phases: list[dict[str, object]], wall_seconds: dict[int, float]) -> list[str]:
    lines = [
        "## Phase Telemetry",
        "",
        "| Phase | Experiments | Budget (h) | Actual (h) | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for phase in phases:
        raw_pid = phase.get("id")
        pid = "n/a" if raw_pid is None or raw_pid == "" else raw_pid
        lo, hi = phase.get("min"), phase.get("max")
        budget = phase.get("budget_h")
        if lo is None or hi is None:
            lines.append(f"| {pid} | n/a | {_fmt_hours(budget)} | n/a | n/a |")
            continue
        matched = [v for exp, v in wall_seconds.items() if lo <= exp <= hi]
        actual_h = (sum(matched) / 3600.0) if matched else None
        if budget is not None and actual_h is not None:
            status = "OVER budget" if actual_h > budget else "under budget"
        else:
            status = "n/a"
        lines.append(f"| {pid} | {lo}-{hi} | {_fmt_hours(budget)} | {_fmt_hours(actual_h)} | {status} |")
    lines.append("")
    return lines


def build_phase_section(
    phases: list[dict[str, object]] | None,
    aux_table: dict[str, dict[int, float]] | None,
) -> list[str]:
    if not phases:
        return []
    wall_seconds = (aux_table or {}).get("wall_seconds", {})
    return build_phase_table(phases, wall_seconds)


# --------------------------------------------------------------------------
# Sweep sidecar (--expand-study)
# --------------------------------------------------------------------------


def render_tsv_table(path: Path) -> str:
    """Render any header-having TSV as an aligned plain-text table. Used for
    ``--expand-study`` (sweeps/<id>.sidecar.tsv); the sidecar schema is
    per-sweep (see sweep-rules.md), so this reads whatever header is present
    rather than assuming fixed columns.
    """
    if not path.exists():
        return f"[expand-study] sidecar not found: {path}"
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f, delimiter="\t"))
    except OSError as exc:
        return f"[expand-study] could not read {path}: {exc}"
    if not rows:
        return f"[expand-study] {path} is empty"

    ncols = len(rows[0])
    if any(len(r) != ncols for r in rows):
        # Ragged rows — don't guess at alignment, just show the raw fields.
        return "\n".join("\t".join(r) for r in rows)

    widths = [max(len(row[i]) for row in rows) for i in range(ncols)]
    lines = []
    for idx, row in enumerate(rows):
        lines.append("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))
        if idx == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# results_summary.md
# --------------------------------------------------------------------------


def _display_source(results_path: Path) -> str:
    """Repo-relative when possible — committed summaries must not embed machine paths."""
    try:
        return str(results_path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(results_path)


def build_summary(
    results_path: Path,
    metric_col: str,
    goal: str,
    rows: list[ResultRow],
    extra_sections: list[list[str]] | None = None,
) -> str:
    valid_rows = [row for row in rows if row.metric is not None and row.status != "crash"]
    frontier = running_frontier(rows, goal)
    baseline = valid_rows[0] if valid_rows else None
    best = frontier[-1] if frontier else None

    counts = {"keep": 0, "discard": 0, "crash": 0}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1

    improvement = None
    if baseline and best:
        improvement = best.metric - baseline.metric if goal == "higher" else baseline.metric - best.metric

    lines = [
        "# Results Summary",
        "",
        f"- source: `{_display_source(results_path)}`",
        f"- metric column: `{metric_col}`",
        f"- goal: `{goal}`",
        f"- total experiments: {len(rows)}",
        f"- keep: {counts.get('keep', 0)}",
        f"- discard: {counts.get('discard', 0)}",
        f"- crash: {counts.get('crash', 0)}",
        "",
        "## Overview",
        "",
        f"- baseline metric: {format_metric(baseline.metric if baseline else None)}",
        f"- best metric: {format_metric(best.metric if best else None)}",
        f"- total improvement: {format_metric(improvement)}" if improvement is not None else "- total improvement: n/a",
    ]

    if best:
        lines.extend(
            [
                f"- best commit: `{best.commit or 'n/a'}`",
                f"- best description: {best.description or 'n/a'}",
            ]
        )

    lines.extend(["", "## Frontier", "", "| Run | Commit | Metric | Status | Description |", "| --- | --- | --- | --- | --- |"])
    if frontier:
        for row in frontier:
            lines.append(
                f"| {row.row_number} | `{row.commit or 'n/a'}` | {format_metric(row.metric)} | {row.status or 'n/a'} | {row.description or 'n/a'} |"
            )
    else:
        lines.append("| - | - | - | - | No valid experiment rows found |")

    lines.extend(["", "## Recent Runs", "", "| Run | Commit | Metric | Status | Description |", "| --- | --- | --- | --- | --- |"])
    recent_rows = rows[-10:]
    for row in recent_rows:
        lines.append(
            f"| {row.row_number} | `{row.commit or 'n/a'}` | {format_metric(row.metric)} | {row.status or 'n/a'} | {row.description or 'n/a'} |"
        )

    for section in extra_sections or []:
        if not section:
            continue
        lines.append("")
        lines.extend(section)

    return "\n".join(lines) + "\n"


def placeholder_svg(title: str, message: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="240" viewBox="0 0 1000 240">
  <rect width="1000" height="240" fill="#fbfaf6"/>
  <text x="40" y="70" font-family="Menlo, monospace" font-size="24" fill="#1f2937">{html.escape(title)}</text>
  <text x="40" y="120" font-family="Menlo, monospace" font-size="16" fill="#6b7280">{html.escape(message)}</text>
</svg>
"""


def build_plot_svg(title: str, metric_col: str, goal: str, rows: list[ResultRow]) -> str:
    valid_rows = [row for row in rows if row.metric is not None and row.status != "crash"]
    if not valid_rows:
        return placeholder_svg(title, "No plottable metric rows found in results.tsv")

    frontier = running_frontier(rows, goal)
    width, height = 1200, 720
    left, right, top, bottom = 80, 40, 70, 90
    plot_w = width - left - right
    plot_h = height - top - bottom

    x_min = 1
    x_max = max(row.row_number for row in rows) if rows else 1
    y_values = [row.metric for row in valid_rows if row.metric is not None]
    y_min = min(y_values)
    y_max = max(y_values)
    if math.isclose(y_min, y_max):
        pad = 1.0 if y_min == 0 else abs(y_min) * 0.05
        y_min -= pad
        y_max += pad
    else:
        pad = (y_max - y_min) * 0.08
        y_min -= pad
        y_max += pad

    def x_pos(row_number: int) -> float:
        if x_max == x_min:
            return left + plot_w / 2
        return left + (row_number - x_min) * plot_w / (x_max - x_min)

    def y_pos(metric: float) -> float:
        return top + (y_max - metric) * plot_h / (y_max - y_min)

    elements: list[str] = [
        f'<rect width="{width}" height="{height}" fill="#fbfaf6"/>',
        f'<text x="{left}" y="36" font-family="Menlo, monospace" font-size="24" fill="#111827">{html.escape(title)}</text>',
        f'<text x="{left}" y="58" font-family="Menlo, monospace" font-size="14" fill="#6b7280">metric={html.escape(metric_col)} goal={html.escape(goal)}</text>',
    ]

    for tick_index in range(6):
        y_value = y_min + (y_max - y_min) * tick_index / 5
        y = y_pos(y_value)
        elements.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1"/>')
        elements.append(
            f'<text x="{left - 12}" y="{y + 5:.1f}" text-anchor="end" font-family="Menlo, monospace" font-size="12" fill="#6b7280">{y_value:.4f}</text>'
        )

    for tick_index in range(min(max(x_max, 1), 10)):
        row_number = 1 + round((x_max - 1) * tick_index / max(1, min(max(x_max, 1), 10) - 1)) if x_max > 1 else 1
        x = x_pos(row_number)
        elements.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height-bottom}" stroke="#f1f5f9" stroke-width="1"/>')
        elements.append(
            f'<text x="{x:.1f}" y="{height-bottom + 24}" text-anchor="middle" font-family="Menlo, monospace" font-size="12" fill="#6b7280">{row_number}</text>'
        )

    elements.append(f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#111827" stroke-width="2"/>')
    elements.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#111827" stroke-width="2"/>')

    if frontier:
        frontier_points = " ".join(f"{x_pos(row.row_number):.1f},{y_pos(row.metric):.1f}" for row in frontier if row.metric is not None)
        elements.append(
            f'<polyline fill="none" stroke="#0f766e" stroke-width="3" points="{frontier_points}"/>'
        )

    for row in valid_rows:
        color = "#16a34a" if row.status == "keep" else "#9ca3af"
        elements.append(
            f'<circle cx="{x_pos(row.row_number):.1f}" cy="{y_pos(row.metric):.1f}" r="4.5" fill="{color}" stroke="#111827" stroke-width="0.8"/>'
        )

    best = frontier[-1] if frontier else None
    if best and best.metric is not None:
        x = x_pos(best.row_number)
        y = y_pos(best.metric)
        elements.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="none" stroke="#dc2626" stroke-width="2"/>')
        elements.append(
            f'<text x="{x + 12:.1f}" y="{y - 10:.1f}" font-family="Menlo, monospace" font-size="12" fill="#991b1b">best {best.metric:.6f}</text>'
        )

    elements.append(
        f'<text x="{width / 2:.1f}" y="{height - 24}" text-anchor="middle" font-family="Menlo, monospace" font-size="14" fill="#374151">Experiment #</text>'
    )
    elements.append(
        f'<text x="24" y="{height / 2:.1f}" transform="rotate(-90 24 {height / 2:.1f})" text-anchor="middle" font-family="Menlo, monospace" font-size="14" fill="#374151">{html.escape(metric_col)}</text>'
    )

    return "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{}\" height=\"{}\" viewBox=\"0 0 {} {}\">\n{}\n</svg>\n".format(
        width,
        height,
        width,
        height,
        "\n".join(f"  {element}" for element in elements),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results_path = args.results_path.resolve()
    if not results_path.exists():
        raise FileNotFoundError(f"results file not found: {results_path}")

    with results_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if not reader.fieldnames:
            raise ValueError("results.tsv is empty or missing a header row")
        fieldnames = reader.fieldnames

    metric_col = pick_metric_column(fieldnames, args.metric_col)
    goal = infer_goal(metric_col, args.goal)
    _, rows = read_results(results_path, metric_col)

    # Aux panels — degrade gracefully when the sidecar is missing/unreadable.
    aux_path = args.aux_path or results_path.with_name("aux_metrics.tsv")
    try:
        aux_table = read_aux_metrics(aux_path)
    except Exception:
        aux_table = None
    custom_aux = None
    if args.aux:
        custom_aux = (args.aux, args.aux_goal or infer_goal(args.aux, args.aux_goal))
    aux_section = build_aux_section(rows, metric_col, aux_table, custom=custom_aux)

    # Phase telemetry — degrade gracefully when study.yaml/phases is missing.
    study_yaml_path = args.study_yaml or results_path.with_name("study.yaml")
    try:
        phases = _load_phases(study_yaml_path)
    except Exception:
        phases = None
    phase_section = build_phase_section(phases, aux_table)

    summary_out = args.summary_out or results_path.with_name("results_summary.md")
    plot_out = args.plot_out or results_path.with_name("progress.svg")
    title = args.title or f"Experiment Progress: {results_path.parent.name or results_path.stem}"

    summary_text = build_summary(
        results_path, metric_col, goal, rows, extra_sections=[aux_section, phase_section]
    )
    summary_out.write_text(summary_text, encoding="utf-8")
    plot_out.write_text(build_plot_svg(title, metric_col, goal, rows), encoding="utf-8")

    print(f"summary: {summary_out}")
    print(f"plot:    {plot_out}")
    print(f"metric:  {metric_col} ({goal})")
    print(f"rows:    {len(rows)}")
    if phase_section:
        print()
        print("\n".join(phase_section))

    if args.expand_study:
        sweeps_dir = args.sweeps_dir or (results_path.parent / "sweeps")
        sidecar_path = sweeps_dir / f"{args.expand_study}.sidecar.tsv"
        print()
        print(f"[expand-study] {sidecar_path}")
        print(render_tsv_table(sidecar_path))

    return 0


if __name__ == "__main__":
    sys.exit(main())
