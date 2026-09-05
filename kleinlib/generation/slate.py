"""The ``slates`` capability — a phase's hypotheses, locked, then scored.

The phase ritual (``references/phase-ritual.md``) has always asked the driver to
write 4–6 falsifiable candidates down before touching the mutable surface.  This
capability does not run that ritual, propose a candidate, or rank one: it
**records** the rows the driver authored, gives each a permanent
``<study>#Hn`` id, binds a run to the hypothesis it was admitted for, and at
phase end **computes** the Brier score of the forecasts the driver typed.
Arithmetic on authored rows — R-SLA-6, and the module is grep-guarded for it in
``kleinlib/tests/test_generation_slate.py``.

Three properties are worth stating outright, because each closes a way of making
a calibration number look better than the work was:

**The prior is immutable.**  ``slate lock`` rewrites ``slates/<phase>.yaml`` with
the ids it assigned and hashes the committed bytes into the lock object.  Editing
``p_success`` afterwards changes the file's sha and FAILs verification for the
life of the study.  A forecast may be revised — but only through
``slate amend``, which records the change as a new version with
``revision_of`` and scores it in its OWN panel; the primary panels always use the
FIRST forecast.

**The denominator is frozen at lock (RF-05).**  Coverage is
``resolved / cohort`` where the cohort is every id ever locked for the phase.
Withdrawing a row does not shrink it — a withdrawn row stays in the cohort,
censored, with the reason on the record.  Perpetual deferral and quiet
withdrawal both show up as coverage below 1.0 and an outcome of ``conditional``,
never as a better Brier.

**A scouted row is not a forecast.**  A row whose outcome the scouting ledger
already observed (``provenance: scouted``) is computed into a panel labelled
``scouted_descriptive`` and is never summarised as calibration
(``consult-protocol.md`` "Prior provenance", A5 §2).  ``unscouted`` and
``derived`` are the panels that count.

The arithmetic itself lives in :mod:`kleinlib.generation.calibration`; this
module is the bookkeeping around it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ..contract import normalize_tracks, registered_predictions
from ..errors import WorkflowError
from ..manifest import load_manifests
from ..primitives import atomic_write_text, sha256_bytes, sha256_file
from . import calibration
from .admission import Context, load_receipts
from .chronology import run_started_events
from .envelope import GENERATION_SCHEMA
from .ledger import read_events, read_object
from .registry import Capability
from .verify import Check

if TYPE_CHECKING:  # pragma: no cover - types only
    from .admission import Match
    from .registry import FamilyContext

__all__ = [
    "AXES",
    "CAPABILITY",
    "COHORT_WINDOW",
    "MAX_ROWS",
    "MIN_ROWS",
    "PANELS",
    "PROVENANCE",
    "ROW_KEY_ORDER",
    "ROW_KINDS",
    "SLATE_EVENTS",
    "build_score",
    "build_version",
    "hypothesis_bindings",
    "latest_version",
    "next_hypothesis_number",
    "read_slate_file",
    "render_slate",
    "score_events",
    "slate_family",
    "slate_path",
    "slate_versions",
    "table_path",
    "table_text",
    "validation_problems",
]

#: A slate is 4–6 rows.  Three is not a comparison; seven is a wish list that no
#: phase budget can adjudicate (``phase-ritual.md`` §1, R-SLA-1).
MIN_ROWS = 4
MAX_ROWS = 6

#: The only cohort window this version knows: the phase closes the cohort.  It is
#: written into every lock so a later version that adds windows cannot silently
#: reinterpret an old one.
COHORT_WINDOW: dict[str, str] = {"closes": "phase-end"}

PROVENANCE: tuple[str, ...] = ("unscouted", "scouted", "derived")
ROW_KINDS: tuple[str, ...] = ("diff", "cell")
AXES: tuple[str, ...] = ("novelty", "testability", "information")

#: The panels ``slate score`` reports.  ``scouted_descriptive`` is computed and
#: labelled; it is never summarised as calibration.
PANELS: tuple[str, ...] = ("unscouted", "derived", "scouted_descriptive", "revisions")

SLATE_EVENTS: tuple[str, ...] = ("slate_locked", "slate_amended")
SCORE_EVENT = "slate_scored"

#: The order a locked row is written back in — the schema's order, so a diff of
#: two versions reads down the page.
ROW_KEY_ORDER: tuple[str, ...] = (
    "id",
    "kind",
    "track",
    "lever_family",
    "statement",
    "source_ids",
    "provenance",
    "p_success",
    "success_P",
    "expected_effect",
    "units",
    "floor_ref",
    "cost_budget",
    "novelty",
    "testability",
    "information",
    "parent_ids",
    "revision_of",
)

#: Fields that are FROZEN once an id is allocated.  Changing any of them under an
#: existing id is recycling the id onto a different hypothesis, which is the one
#: thing an amendment may never do (R-SLA-1, R-ADM-8).
FROZEN_ROW_KEYS: tuple[str, ...] = ("kind", "track", "statement", "success_P", "provenance")

#: The checkpoints that are development work on an enabled study and therefore
#: need a hypothesis.  ``sealed``, ``baseline``, ``repair`` and ``calibration``
#: are the typed obligations that legitimately carry no ``H`` (R-ADM-7).
HYPOTHESIS_ACTIONS: tuple[str, ...] = ("run", "cell")

_NO_HYPOTHESIS = (
    "an enabled study runs hypotheses; use --hypothesis, or "
    "--action calibration|baseline|repair"
)


# --------------------------------------------------------------------------
# paths and files
# --------------------------------------------------------------------------


def slate_path(study_dir: Path, phase: str) -> Path:
    """The driver's own file — study root, beside ``study.yaml``."""
    return study_dir / "slates" / f"{phase}.yaml"


def table_path(study_dir: Path, phase: str) -> Path:
    """The calibration table SYNTHESIZE pins as ``art:slate_calibration_<phase>``."""
    return study_dir / "generation" / "tables" / f"slate_calibration_{phase}.tsv"


def read_slate_file(study_dir: Path, phase: str) -> dict[str, Any]:
    path = slate_path(study_dir, phase)
    if not path.is_file():
        raise WorkflowError(
            f"{path.relative_to(study_dir).as_posix()} does not exist — author the slate "
            "first (`.claude/skills/klein/assets/slate-template.yaml`)"
        )
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"could not read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{path.name} must contain a top-level mapping")
    return value


def render_slate(payload: Mapping[str, Any]) -> str:
    """Deterministic YAML in the schema's key order — the bytes the lock hashes."""
    return yaml.safe_dump(
        dict(payload), sort_keys=False, default_flow_style=False, allow_unicode=True
    )


# --------------------------------------------------------------------------
# the versions on the ledger
# --------------------------------------------------------------------------


def slate_versions(
    study_dir: Path, events: Sequence[Mapping[str, Any]], phase: str | None = None
) -> list[dict[str, Any]]:
    """Every locked version, oldest first, as ``{event, sha, object}``."""
    out: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") not in SLATE_EVENTS:
            continue
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            obj = read_object(study_dir, sha)
        except WorkflowError:
            continue
        if phase is not None and obj.get("phase") != phase:
            continue
        out.append({"event": dict(event), "sha": sha, "object": obj})
    return out


def score_events(
    study_dir: Path, events: Sequence[Mapping[str, Any]], phase: str | None = None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != SCORE_EVENT:
            continue
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            obj = read_object(study_dir, sha)
        except WorkflowError:
            continue
        if phase is not None and obj.get("phase") != phase:
            continue
        out.append({"event": dict(event), "sha": sha, "object": obj})
    return out


def latest_version(
    study_dir: Path, events: Sequence[Mapping[str, Any]], phase: str
) -> dict[str, Any] | None:
    versions = slate_versions(study_dir, events, phase)
    return versions[-1] if versions else None


def _rows(version: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = version.get("rows")
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _row_by_id(version: Mapping[str, Any], hypothesis: str) -> dict[str, Any] | None:
    for row in _rows(version):
        if row.get("id") == hypothesis:
            return row
    return None


def next_hypothesis_number(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> int:
    """One past the highest ``Hn`` ever allocated — across every phase.

    Ids are monotonic study-wide and are never recycled, so a reader who sees
    ``#H7`` in findings can find exactly one row in exactly one slate.
    """
    highest = 0
    for version in slate_versions(study_dir, events):
        for row in _rows(version["object"]):
            number = _hypothesis_number(row.get("id"))
            if number is not None:
                highest = max(highest, number)
    return highest + 1


def _hypothesis_number(value: Any) -> int | None:
    if not isinstance(value, str) or "#H" not in value:
        return None
    tail = value.rsplit("#H", 1)[1]
    return int(tail) if tail.isdigit() else None


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


def validation_problems(
    payload: Mapping[str, Any],
    *,
    study: str,
    phase: str,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    allocated: Mapping[str, dict[str, Any]],
) -> list[str]:
    """Everything wrong with an authored slate, one line each.

    ``previous`` is the version this one amends (``None`` for a first lock);
    ``allocated`` maps every id ever allocated for this phase to its row, so a
    withdrawn id cannot be revived and a live id cannot be re-pointed.
    """
    problems: list[str] = []
    if payload.get("type") not in (None, "slate"):
        problems.append(f"type is {payload.get('type')!r}, expected 'slate'")
    declared_study = payload.get("study")
    if declared_study is not None and str(declared_study) != study:
        problems.append(f"study is {declared_study!r}, expected {study!r}")
    if str(payload.get("phase")) != phase:
        problems.append(f"phase is {payload.get('phase')!r}, expected {phase!r}")
    if phase not in _phase_ids(contract):
        problems.append(
            f"phase {phase!r} is not configured in study.yaml (phases: "
            + (", ".join(_phase_ids(contract)) or "none")
            + ")"
        )
    window = payload.get("cohort_window")
    if window is not None and dict(window) != COHORT_WINDOW:
        problems.append(
            f"cohort_window is {window!r}; this version freezes it at {COHORT_WINDOW!r}"
        )
    problems.extend(_probability_problems(payload.get("base_rate_forecast"), "base_rate_forecast"))
    if previous is not None:
        if payload.get("base_rate_forecast") != previous.get("base_rate_forecast"):
            problems.append(
                "base_rate_forecast is frozen at the first lock "
                f"({previous.get('base_rate_forecast')!r}); an amendment may not restate it"
            )
    allocation = payload.get("budget_allocation")
    if allocation is not None and not isinstance(allocation, Mapping):
        problems.append("budget_allocation must be a mapping of row id/index to units")

    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        return [*problems, "rows must be a non-empty list"]
    if not MIN_ROWS <= len(rows) <= MAX_ROWS:
        problems.append(
            f"a slate is {MIN_ROWS}–{MAX_ROWS} rows, got {len(rows)} — fewer is not a "
            "comparison, more is a wish list the phase budget cannot adjudicate"
        )
    tracks = normalize_tracks(contract)
    registered = registered_predictions(contract)
    sweeps = state.get("sweeps") if isinstance(state.get("sweeps"), Mapping) else {}
    live_before = {row.get("id") for row in _rows(previous or {})}
    statements: dict[str, int] = {}
    for index, raw in enumerate(rows, start=1):
        if not isinstance(raw, Mapping):
            problems.append(f"row {index}: must be a mapping")
            continue
        label = f"row {index}"
        problems.extend(
            _row_problems(
                raw,
                label,
                tracks=tracks,
                registered=registered,
                sweeps=sweeps,
                allocated=allocated,
                live_before=live_before,
            )
        )
        statement = raw.get("statement")
        if isinstance(statement, str):
            if statement in statements:
                problems.append(
                    f"{label}: the same statement as row {statements[statement]} — two rows "
                    "with one hypothesis is one hypothesis with two ids"
                )
            statements.setdefault(statement, index)
    return problems


def _phase_ids(contract: Mapping[str, Any]) -> list[str]:
    phases = contract.get("phases")
    if not isinstance(phases, list):
        return []
    return [str(p["id"]) for p in phases if isinstance(p, Mapping) and "id" in p]


def _probability_problems(value: Any, label: str) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return [f"{label} must be a number strictly inside (0, 1), got {value!r}"]
    if not 0.0 < float(value) < 1.0:
        return [
            f"{label} is {value!r}; a forecast lies strictly inside (0, 1) — 0 and 1 are "
            "certainties, not forecasts"
        ]
    return []


def _row_problems(
    row: Mapping[str, Any],
    label: str,
    *,
    tracks: Mapping[str, Any],
    registered: Mapping[str, Any],
    sweeps: Mapping[str, Any],
    allocated: Mapping[str, dict[str, Any]],
    live_before: set[Any],
) -> list[str]:
    problems: list[str] = []
    if row.get("kind") not in ROW_KINDS:
        problems.append(f"{label}: kind is {row.get('kind')!r}, expected one of {', '.join(ROW_KINDS)}")
    track = row.get("track")
    if track not in tracks:
        problems.append(
            f"{label}: track {track!r} is not declared in study.yaml "
            f"(declared: {', '.join(sorted(tracks)) or 'none'})"
        )
    if not isinstance(row.get("statement"), str) or not str(row.get("statement")).strip():
        problems.append(f"{label}: statement must be one falsifiable sentence")
    if not isinstance(row.get("lever_family"), str) or not str(row.get("lever_family")).strip():
        problems.append(f"{label}: lever_family is required")
    sources = row.get("source_ids")
    if not isinstance(sources, list) or not sources or not all(isinstance(s, str) for s in sources):
        problems.append(f"{label}: source_ids must be a non-empty list of strings")
    if row.get("provenance") not in PROVENANCE:
        problems.append(
            f"{label}: provenance is {row.get('provenance')!r}, expected one of "
            + ", ".join(PROVENANCE)
        )
    problems.extend(_probability_problems(row.get("p_success"), f"{label}: p_success"))
    problems.extend(_success_problems(row, label, tracks=tracks, registered=registered))
    if isinstance(row.get("expected_effect"), bool) or not isinstance(
        row.get("expected_effect"), int | float
    ):
        problems.append(f"{label}: expected_effect must be a number")
    if not isinstance(row.get("units"), str) or not str(row.get("units")).strip():
        problems.append(f"{label}: units is required — a bare number is not an effect")
    problems.extend(_floor_problems(row.get("floor_ref"), label, sweeps=sweeps))
    if row.get("cost_budget") is None:
        problems.append(f"{label}: cost_budget is required (a number or a phrase)")
    for axis in AXES:
        if row.get(axis) not in (1, 2, 3):
            problems.append(f"{label}: {axis} is {row.get(axis)!r}, expected 1, 2 or 3")
    parents = row.get("parent_ids")
    if parents is not None and not isinstance(parents, list):
        problems.append(f"{label}: parent_ids must be a list of hypothesis ids")
    problems.extend(_id_problems(row, label, allocated=allocated, live_before=live_before))
    return problems


def _success_problems(
    row: Mapping[str, Any],
    label: str,
    *,
    tracks: Mapping[str, Any],
    registered: Mapping[str, Any],
) -> list[str]:
    """``success_P`` must be adjudicable by the notary, on this row's track.

    A manual prediction is refused here rather than at admission: the notary
    cannot decide it inside a run, so ``y`` could never resolve and the row
    would sit censored forever, quietly lowering coverage.
    """
    names = row.get("success_P")
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        return [f"{label}: success_P must be a non-empty list of registered prediction ids"]
    problems: list[str] = []
    for name in names:
        entry = registered.get(name)
        if entry is None:
            problems.append(
                f"{label}: success_P names {name!r}, which study.yaml does not register "
                f"({', '.join(sorted(registered)) or 'none registered'})"
            )
            continue
        if entry.get("rule") is None:
            problems.append(
                f"{label}: {name} is manual (no rule) — the notary cannot adjudicate it "
                "inside a run, so this row's y could never resolve"
            )
        declared = entry.get("track")
        if declared is not None and str(declared) != str(row.get("track")):
            problems.append(
                f"{label}: {name} belongs to track {declared!r}, not {row.get('track')!r}"
            )
    return problems


def _floor_problems(value: Any, label: str, *, sweeps: Mapping[str, Any]) -> list[str]:
    """``minimum_delta`` or a REGISTERED ``sweep:<name>``.

    Registered sweeps live in ``study_state.json``'s ``sweeps`` map, written by
    ``klein sweep register`` (``kleinlib/cli_sweep.py``) and read the same way by
    the claims law (``kleinlib/claims.py``).  This module only reads it.
    """
    if value == "minimum_delta":
        return []
    if isinstance(value, str) and value.startswith("sweep:"):
        name = value.split(":", 1)[1]
        if not name:
            return [f"{label}: floor_ref 'sweep:' names no sweep"]
        if name not in sweeps:
            return [
                f"{label}: floor_ref {value!r} is not registered in study_state.json's "
                "sweeps — `klein sweep register` pins the sidecar the floor came from"
            ]
        return []
    return [
        f"{label}: floor_ref is {value!r}, expected 'minimum_delta' or 'sweep:<registered name>'"
    ]


def _id_problems(
    row: Mapping[str, Any],
    label: str,
    *,
    allocated: Mapping[str, dict[str, Any]],
    live_before: set[Any],
) -> list[str]:
    """An authored ``id`` may only carry an existing, still-live row forward."""
    given = row.get("id")
    if given is None:
        return []
    if not isinstance(given, str):
        return [f"{label}: id must be a string (omit it and the lock allocates one)"]
    if given not in allocated:
        return [
            f"{label}: id {given!r} was never allocated for this phase — omit the id and "
            "the lock allocates the next one"
        ]
    if given not in live_before:
        return [
            f"{label}: id {given!r} was withdrawn by an earlier version — ids are never "
            "recycled; a returning hypothesis is a new row with a new id"
        ]
    previous = allocated[given]
    problems: list[str] = []
    for key in FROZEN_ROW_KEYS:
        if row.get(key) != previous.get(key):
            problems.append(
                f"{label}: {key} changed under id {given!r} "
                f"({previous.get(key)!r} → {row.get(key)!r}) — that is a different "
                "hypothesis and needs a different id"
            )
    return problems


# --------------------------------------------------------------------------
# building a version
# --------------------------------------------------------------------------


def build_version(
    study_dir: Path,
    payload: Mapping[str, Any],
    *,
    study: str,
    phase: str,
    events: Sequence[Mapping[str, Any]],
    parent: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """``(the file payload with ids assigned, the object body without file_sha256)``.

    Ids are allocated in row order from one past the highest ever used; a row
    that already carries an id keeps it, and gains ``revision_of`` when its
    ``p_success`` differs from the version it came from.
    """
    number = next_hypothesis_number(study_dir, events)
    previous_rows = {row.get("id"): row for row in _rows(parent or {})}
    parent_version = int((parent or {}).get("version") or 0)
    rows: list[dict[str, Any]] = []
    for raw in payload.get("rows") or []:
        row = dict(raw)
        given = row.get("id")
        if not isinstance(given, str):
            row["id"] = f"{study}#H{number}"
            number += 1
            row.setdefault("revision_of", None)
        else:
            before = previous_rows.get(given, {})
            row["revision_of"] = (
                parent_version if before.get("p_success") != row.get("p_success") else None
            )
        row.setdefault("parent_ids", [])
        rows.append({key: row[key] for key in ROW_KEY_ORDER if key in row})

    version = parent_version + 1
    file_payload: dict[str, Any] = {
        "type": "slate",
        "study": study,
        "phase": phase,
        "version": version,
        "cohort_window": dict(COHORT_WINDOW),
        "base_rate_forecast": payload.get("base_rate_forecast"),
    }
    if payload.get("budget_allocation") is not None:
        file_payload["budget_allocation"] = dict(payload["budget_allocation"])
    file_payload["rows"] = rows

    obj = {
        "schema": GENERATION_SCHEMA,
        "kind": "slate",
        "phase": phase,
        "version": version,
        "parent_ids": [],
        "file_sha256": None,
        "rows": [dict(row) for row in rows],
        "base_rate_forecast": payload.get("base_rate_forecast"),
        "cohort_window": dict(COHORT_WINDOW),
        "late": False,
    }
    return file_payload, obj


def write_version(study_dir: Path, phase: str, file_payload: Mapping[str, Any]) -> str:
    """Rewrite the driver's file with the ids assigned; return its sha256."""
    path = slate_path(study_dir, phase)
    atomic_write_text(path, render_slate(file_payload))
    return sha256_file(path)


def is_late(
    study_dir: Path, events: Sequence[Mapping[str, Any]], allocated: Mapping[str, Any]
) -> bool:
    """Did a hypothesis admission for this phase already happen?

    True only when a receipt already names an id this phase had allocated —
    which cannot happen before a phase's FIRST lock through the CLI (admission
    refuses an id no locked slate carries), and which for an amendment simply
    records that the phase was already under way.  Verification treats it as a
    FAIL on version 1 alone; the general "admission before the lock in force"
    case is caught by the anchor-order check in :func:`slate_family`.
    """
    if not allocated:
        return False
    for receipt in load_receipts(study_dir, events):
        obj = _receipt_object(study_dir, receipt.sha)
        if obj is None:
            continue
        intended = obj.get("intended_action")
        named = intended.get("hypothesis_id") if isinstance(intended, Mapping) else None
        if isinstance(named, str) and named in allocated:
            return True
    return False


def allocated_rows(
    study_dir: Path, events: Sequence[Mapping[str, Any]], phase: str
) -> dict[str, dict[str, Any]]:
    """``{id: its newest row}`` over every version of this phase's slate."""
    out: dict[str, dict[str, Any]] = {}
    for version in slate_versions(study_dir, events, phase):
        for row in _rows(version["object"]):
            if isinstance(row.get("id"), str):
                out[row["id"]] = row
    return out


def _receipt_object(study_dir: Path, sha: str) -> dict[str, Any] | None:
    try:
        return read_object(study_dir, sha)
    except WorkflowError:  # pragma: no cover - the ledger guard catches this first
        return None


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------


def hypothesis_bindings(
    study_dir: Path, events: Sequence[Mapping[str, Any]], match: Match
) -> dict[str, str]:
    """``{H: the run its LAST admitted receipt was consumed by}``.

    A receipt is in ``match.consumed`` only when the matcher classified the run
    ``admitted`` — so a hypothesis whose run was ``mismatched``, ``replayed`` or
    ``refused-but-run`` binds nothing, and the row censors rather than
    resolving on evidence the extension already rejected.
    """
    bound: dict[str, tuple[int, str]] = {}
    for receipt in load_receipts(study_dir, events):
        run = match.consumed.get(receipt.sha)
        if run is None or receipt.verdict != "admitted":
            continue
        obj = _receipt_object(study_dir, receipt.sha)
        intended = obj.get("intended_action") if isinstance(obj, Mapping) else None
        named = intended.get("hypothesis_id") if isinstance(intended, Mapping) else None
        if not isinstance(named, str):
            continue
        if named not in bound or receipt.sequence > bound[named][0]:
            bound[named] = (receipt.sequence, run)
    return {name: run for name, (_sequence, run) in bound.items()}


def _outcome_for_run(
    manifest: Mapping[str, Any], success: Sequence[str], run: str
) -> tuple[str, int | None, str]:
    """``(status, y, reason)`` for one bound run — the exact rule of plan §A.4."""
    if str(manifest.get("disposition")) == "crash":
        return ("resolved", 0, f"{run} crashed")
    verdicts = manifest.get("predictions")
    verdicts = verdicts if isinstance(verdicts, Mapping) else {}
    refuted = [name for name in success if _verdict(verdicts, name) == "refuted"]
    if refuted:
        return ("resolved", 0, f"{', '.join(refuted)} refuted on {run}")
    missing = [name for name in success if _verdict(verdicts, name) is None]
    if missing:
        return (
            "censored",
            None,
            f"{', '.join(missing)} was not adjudicated on {run}",
        )
    unclear = [name for name in success if _verdict(verdicts, name) == "inconclusive"]
    if unclear:
        return ("censored", None, f"{', '.join(unclear)} inconclusive on {run}")
    return ("resolved", 1, f"all of {', '.join(success)} supported on {run}")


def _verdict(verdicts: Mapping[str, Any], name: str) -> str | None:
    entry = verdicts.get(name)
    if isinstance(entry, Mapping) and isinstance(entry.get("verdict"), str):
        return entry["verdict"]
    return str(entry) if isinstance(entry, str) else None


def build_score(
    study_dir: Path,
    *,
    phase: str,
    events: Sequence[Mapping[str, Any]],
    core: Sequence[Mapping[str, Any]],
    match: Match,
    manifests: Mapping[str, Mapping[str, Any]],
    closed_at: int,
) -> dict[str, Any]:
    """The whole ``slate_scored`` body except ``table_sha256`` — pure and replayable.

    ``klein generation slate score`` writes what this returns; ``generation
    verify`` calls it again from the same ledger and compares every number.  It
    reads nothing but the ledger, the manifests and the core chain, so the two
    calls cannot disagree unless something on disk changed.
    """
    versions = slate_versions(study_dir, events, phase)
    if not versions:
        raise WorkflowError(f"no slate is locked for phase {phase!r}")
    live = {row.get("id") for row in _rows(versions[-1]["object"])}
    base_rate = float(versions[0]["object"].get("base_rate_forecast"))

    first_seen: dict[str, dict[str, Any]] = {}
    newest: dict[str, dict[str, Any]] = {}
    withdrawn_in: dict[str, int] = {}
    for version in versions:
        obj = version["object"]
        for row in _rows(obj):
            name = row.get("id")
            if not isinstance(name, str):
                continue
            first_seen.setdefault(name, row)
            newest[name] = row
        for name in list(first_seen):
            if name not in {r.get("id") for r in _rows(obj)} and name not in withdrawn_in:
                withdrawn_in[name] = int(obj.get("version") or 0)

    bindings = hypothesis_bindings(study_dir, events, match)
    started = run_started_events(core)

    cohort: list[dict[str, Any]] = []
    for name in sorted(first_seen, key=lambda value: (_hypothesis_number(value) or 0, value)):
        row = newest[name]
        p_first = float(first_seen[name].get("p_success"))
        p_latest = float(row.get("p_success"))
        provenance = str(row.get("provenance"))
        run = bindings.get(name)
        if name not in live:
            status, y, reason = (
                "withdrawn",
                None,
                f"withdrawn in version {withdrawn_in.get(name, '?')} — retained in the cohort",
            )
            run = None
        elif run is None:
            status, y, reason = ("censored", None, "no admitted run was bound to it")
        elif int((started.get(run) or {}).get("sequence") or 0) > closed_at:
            status, y, reason = ("censored", None, f"{run} started after the cohort window closed")
            run = None
        elif run not in manifests:
            status, y, reason = ("censored", None, f"{run} has no manifest to read")
        else:
            success = [str(name) for name in (row.get("success_P") or [])]
            status, y, reason = _outcome_for_run(manifests[run], success, run)
        cohort.append(
            {
                "id": name,
                "p_first": p_first,
                "p_latest": p_latest,
                "provenance": provenance,
                "status": status,
                "y": y,
                "reason": reason,
                "run": run,
                "revision_of": row.get("revision_of"),
            }
        )

    panels = _panels(cohort, base_rate)
    resolved = sum(1 for entry in cohort if entry["status"] == "resolved")
    covered = calibration.coverage(resolved, len(cohort))
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "slate_score",
        "phase": phase,
        "closed_at_core_sequence": closed_at,
        "cohort": cohort,
        "panels": panels,
        "coverage": covered,
        "outcome": "complete" if covered == 1.0 else "conditional",
    }


def _panels(cohort: Sequence[Mapping[str, Any]], base_rate: float) -> dict[str, Any]:
    """One panel per provenance, plus the revisions panel on ``p_latest``."""
    panels: dict[str, Any] = {}
    for name in PANELS:
        if name == "revisions":
            members = [row for row in cohort if row.get("revision_of") is not None]
            key = "p_latest"
        else:
            wanted = "scouted" if name == "scouted_descriptive" else name
            members = [row for row in cohort if row["provenance"] == wanted]
            key = "p_first"
        pairs = [
            (float(row[key]), int(row["y"]))
            for row in members
            if row["status"] == "resolved" and row["y"] is not None
        ]
        unresolved = [float(row[key]) for row in members if row["status"] != "resolved"]
        panels[name] = calibration.panel(pairs, unresolved, base_rate=base_rate)
    return panels


#: The calibration table's columns.  SYNTHESIZE pins the file as
#: ``art:slate_calibration_<phase>`` and cites it beside findings §②.
TABLE_COLUMNS: tuple[str, ...] = (
    "id",
    "panel",
    "p_first",
    "p_latest",
    "status",
    "y",
    "reason",
    "run",
)


def table_text(score: Mapping[str, Any]) -> str:
    """The pinned TSV — one row per cohort member, in id order, deterministic."""
    lines = ["\t".join(TABLE_COLUMNS)]
    for row in score.get("cohort") or []:
        panel_name = (
            "scouted_descriptive" if row["provenance"] == "scouted" else str(row["provenance"])
        )
        lines.append(
            "\t".join(
                [
                    str(row["id"]),
                    panel_name,
                    format(float(row["p_first"]), ".12g"),
                    format(float(row["p_latest"]), ".12g"),
                    str(row["status"]),
                    "" if row["y"] is None else str(int(row["y"])),
                    str(row["reason"]).replace("\t", " "),
                    "" if row["run"] is None else str(row["run"]),
                ]
            )
        )
    return "\n".join(lines) + "\n"


def write_table(study_dir: Path, phase: str, score: Mapping[str, Any]) -> str:
    path = table_path(study_dir, phase)
    text = table_text(score)
    atomic_write_text(path, text)
    return sha256_bytes(text.encode())


# --------------------------------------------------------------------------
# admission
# --------------------------------------------------------------------------


def _current_phase(ctx: Context) -> str | None:
    value = ctx.state.get("current_phase")
    return value if isinstance(value, str) and value else None


def _rule_hypothesis_is_a_live_slate_row(ctx: Context) -> list[str]:
    """The whole hypothesis-admission rule, in the order a driver hits it.

    A development run on an enabled study names the hypothesis it is testing; a
    calibration, baseline, repair or sealed action legitimately does not
    (R-ADM-7).  The named row must be live on the phase's newest locked slate,
    on the track being run, and the notary must be asked to adjudicate every
    ``success_P`` — otherwise the row's ``y`` could never resolve and the
    forecast would be scored against nothing.
    """
    if not ctx.hypothesis:
        return [_NO_HYPOTHESIS] if ctx.action in HYPOTHESIS_ACTIONS else []
    phase = _current_phase(ctx)
    if phase is None:
        return ["study_state.json names no current phase, so no slate is in force"]
    events = read_events(ctx.study_dir)
    version = latest_version(ctx.study_dir, events, phase)
    if version is None:
        return [
            f"no slate is locked for phase {phase!r} — `klein generation slate lock` "
            "records the hypotheses before any of them runs"
        ]
    row = _row_by_id(version["object"], ctx.hypothesis)
    if row is None:
        allocated = allocated_rows(ctx.study_dir, events, phase)
        if ctx.hypothesis in allocated:
            return [
                f"{ctx.hypothesis} was withdrawn from the phase {phase!r} slate "
                f"(version {version['object'].get('version')}); a withdrawn row stays in "
                "the cohort, censored, and never runs again"
            ]
        return [
            f"{ctx.hypothesis} is not a row of the phase {phase!r} slate "
            f"(version {version['object'].get('version')}: "
            + (", ".join(str(r.get("id")) for r in _rows(version["object"])) or "no rows")
            + ")"
        ]
    problems: list[str] = []
    if str(row.get("track")) != ctx.track:
        problems.append(
            f"{ctx.hypothesis} is a row of track {row.get('track')!r}, not {ctx.track!r}"
        )
    success = [str(name) for name in (row.get("success_P") or [])]
    missing = [name for name in success if name not in ctx.tests]
    if missing:
        problems.append(
            f"--tests must include every success_P of {ctx.hypothesis} "
            f"({', '.join(success)}); missing {', '.join(missing)} — the notary must "
            "adjudicate them on this run or the row's y can never resolve"
        )
    return problems


def _receipt_inputs(ctx: Context) -> dict[str, str | None]:
    """The lock this admission was taken under — pinned into the receipt."""
    if not ctx.hypothesis:
        return {}
    phase = _current_phase(ctx)
    if phase is None:
        return {}
    version = latest_version(ctx.study_dir, read_events(ctx.study_dir), phase)
    return {"slate": version["sha"]} if version is not None else {}


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

NAME = "generation slate"


def slate_family(ctx: FamilyContext) -> tuple[list[Check], dict[str, Any]]:
    """The ``slate`` check family: integrity of the record, then the outcome."""
    checks: list[Check] = []
    problems: list[str] = []
    versions = slate_versions(ctx.study_dir, ctx.events)
    phases = sorted({str(v["object"].get("phase")) for v in versions})

    if not versions:
        checks.append(
            Check(
                NAME,
                "WARN",
                "the slates capability is declared and no slate has been locked yet — "
                "`klein generation slate lock` records the phase's hypotheses",
            )
        )
        return checks, {"integrity": "PASS", "outcome": "unscored", "phases": {}}

    problems.extend(_id_ledger_problems(versions))
    problems.extend(_file_problems(ctx.study_dir, versions, phases))
    problems.extend(_admission_order_problems(ctx.study_dir, ctx.events, versions))

    manifests = {str(m.get("experiment")): m for m in load_manifests(ctx.study_dir)}
    summary: dict[str, Any] = {}
    notes: list[str] = []
    for phase in phases:
        phase_problems, phase_summary, warnings = _phase_checks(
            ctx, phase, manifests=manifests
        )
        problems.extend(phase_problems)
        summary[phase] = phase_summary
        notes.extend(warnings)

    if problems:
        checks.append(Check(NAME, "FAIL", "; ".join(problems[:8])))
        integrity = "FAIL"
    else:
        checks.append(
            Check(
                NAME,
                "PASS",
                f"{len(versions)} locked version(s) across {len(phases)} phase(s); "
                "every admitted hypothesis is a live row of the slate in force, and every "
                "recorded score recomputes",
            )
        )
        integrity = "PASS"
    checks.extend(Check(NAME, "WARN", note) for note in notes)
    scored = [phase for phase, entry in summary.items() if entry.get("coverage") is not None]
    if not scored:
        outcome = "unscored"
    elif len(scored) == len(phases) and all(
        summary[phase]["coverage"] == 1.0 for phase in scored
    ):
        outcome = "complete"
    else:
        outcome = "conditional"
    return checks, {"integrity": integrity, "outcome": outcome, "phases": summary}


def _id_ledger_problems(versions: Sequence[Mapping[str, Any]]) -> list[str]:
    """Ids are allocated once, study-wide, and never go backwards."""
    problems: list[str] = []
    owner: dict[str, tuple[str, str]] = {}
    highest = 0
    for version in versions:
        obj = version["object"]
        phase = str(obj.get("phase"))
        for row in _rows(obj):
            name = row.get("id")
            number = _hypothesis_number(name)
            if not isinstance(name, str) or number is None:
                problems.append(f"{phase} v{obj.get('version')}: row id {name!r} is not <study>#Hn")
                continue
            claimed = owner.get(name)
            if claimed is None:
                if number <= highest:
                    problems.append(
                        f"{name} was allocated after #H{highest} — ids are monotonic "
                        "across the study and are never recycled"
                    )
                owner[name] = (phase, str(row.get("statement")))
                highest = max(highest, number)
            elif claimed[0] != phase or claimed[1] != str(row.get("statement")):
                problems.append(
                    f"{name} names a different hypothesis in {phase} "
                    f"v{obj.get('version')} than where it was allocated"
                )
    return problems


def _file_problems(
    study_dir: Path, versions: Sequence[Mapping[str, Any]], phases: Sequence[str]
) -> list[str]:
    """The driver's file still IS the bytes the newest version hashed."""
    problems: list[str] = []
    for phase in phases:
        newest = [v for v in versions if str(v["object"].get("phase")) == phase][-1]
        path = slate_path(study_dir, phase)
        if not path.is_file():
            problems.append(f"slates/{phase}.yaml is missing; version {newest['object'].get('version')} hashed it")
            continue
        actual = sha256_file(path)
        recorded = newest["object"].get("file_sha256")
        if actual != recorded:
            problems.append(
                f"slates/{phase}.yaml is {actual[:12]}… but version "
                f"{newest['object'].get('version')} locked {str(recorded)[:12]}… — a locked "
                "forecast is immutable; revise it with `klein generation slate amend`"
            )
        first = [v for v in versions if str(v["object"].get("phase")) == phase][0]
        if first["object"].get("late"):
            problems.append(
                f"the first lock for phase {phase} was recorded after a hypothesis "
                "admission already named one of its rows"
            )
    return problems


def _admission_order_problems(
    study_dir: Path, events: Sequence[Mapping[str, Any]], versions: Sequence[Mapping[str, Any]]
) -> list[str]:
    """Every admitted hypothesis was a live row of the version then in force."""
    problems: list[str] = []
    for receipt in load_receipts(study_dir, events):
        if receipt.verdict != "admitted":
            continue
        obj = _receipt_object(study_dir, receipt.sha)
        intended = obj.get("intended_action") if isinstance(obj, Mapping) else None
        named = intended.get("hypothesis_id") if isinstance(intended, Mapping) else None
        if not isinstance(named, str):
            continue
        in_force: dict[str, Mapping[str, Any]] = {}
        for version in versions:
            if int(version["event"].get("sequence") or 0) < receipt.sequence:
                in_force[str(version["object"].get("phase"))] = version["object"]
        live = {row.get("id") for obj in in_force.values() for row in _rows(obj)}
        if named not in live:
            problems.append(
                f"{receipt.event_id} admitted {named}, which is not a live row of any slate "
                "version locked before it"
            )
    return problems


def _phase_checks(
    ctx: FamilyContext, phase: str, *, manifests: Mapping[str, Mapping[str, Any]]
) -> tuple[list[str], dict[str, Any], list[str]]:
    """Recompute this phase's newest score and compare every number."""
    problems: list[str] = []
    warnings: list[str] = []
    scores = score_events(ctx.study_dir, ctx.events, phase)
    if not scores:
        if _phase_is_closed(ctx.core, phase):
            warnings.append(
                f"phase {phase} was acknowledged without a `klein generation slate score` — "
                "the forecasts it locked were never scored"
            )
        return problems, {"coverage": None, "brier_unscouted": None, "n": 0}, warnings

    recorded = scores[-1]["object"]
    closed_at = int(recorded.get("closed_at_core_sequence") or 0)
    try:
        recomputed = build_score(
            ctx.study_dir,
            phase=phase,
            events=ctx.events,
            core=ctx.core,
            match=ctx.match,
            manifests=manifests,
            closed_at=closed_at,
        )
    except WorkflowError as exc:  # pragma: no cover - a score without a lock cannot exist
        return [f"phase {phase}: the score cannot be recomputed ({exc})"], {
            "coverage": None,
            "brier_unscouted": None,
            "n": 0,
        }, warnings

    comparable = {key: recorded.get(key) for key in ("cohort", "panels", "coverage", "outcome")}
    expected = {key: recomputed[key] for key in ("cohort", "panels", "coverage", "outcome")}
    for line in calibration.numbers_agree(comparable, expected):
        problems.append(f"phase {phase} score: {line}")

    path = table_path(ctx.study_dir, phase)
    if not path.is_file():
        problems.append(f"phase {phase}: {path.name} is missing; the score hashed it")
    elif sha256_file(path) != recorded.get("table_sha256"):
        problems.append(
            f"phase {phase}: {path.name} is not the table the score hashed "
            f"({str(recorded.get('table_sha256'))[:12]}…)"
        )
    elif path.read_text(encoding="utf-8") != table_text(recomputed):
        problems.append(f"phase {phase}: {path.name} does not match the recomputed cohort")

    covered = recorded.get("coverage")
    if isinstance(covered, int | float) and float(covered) < 1.0:
        warnings.append(
            f"phase {phase}: coverage {float(covered):.12g} — the score is `conditional`; "
            "censored rows are listed with their reasons in the pinned table"
        )
    unscouted = (recorded.get("panels") or {}).get("unscouted") or {}
    return (
        problems,
        {
            "coverage": covered,
            "brier_unscouted": unscouted.get("brier"),
            "n": unscouted.get("n", 0),
        },
        warnings,
    )


def _phase_is_closed(core: Sequence[Mapping[str, Any]], phase: str) -> bool:
    """Did the core record this phase's boundary acknowledgement?

    ``klein gate record phase`` writes a ``phase_acknowledged`` core event (not a
    ``gate_recorded``, see ``kleinlib/state.py``), and that event IS the phase
    closing — after it, no further evidence can reach the cohort.
    """
    return any(
        event.get("type") == "phase_acknowledged" and event.get("phase") == phase
        for event in core
    )


CAPABILITY = Capability(
    name="slates",
    admission_rules=(_rule_hypothesis_is_a_live_slate_row,),
    verify_family=slate_family,
    receipt_inputs=_receipt_inputs,
)
