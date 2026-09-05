"""The ``surprise`` capability — register the search space, keep the null slices.

A materials scientist searches four hundred temperature/composition bins and
reports the one that looked anomalous.  Nothing in that sentence is false, and
nothing in it is evidence: the reader never learns the denominator.  A2 calls
the genre *surprise theatre*, and this capability is the bookkeeping that makes
it detectable rather than the judgement that makes it wrong.

Four commitments, all made before the evidence exists:

**The search space is registered.**  ``discovery_cells.yaml`` names every cell —
its template, its statistic, its adapter and inputs with their hashes, its
partition, its unit and group policy, and the COMPLETE segment inventory.  A
segment invented afterwards is a new cell, labelled ``post_observation``; it
cannot acquire preregistration by citing an earlier run (R-INV-5).

**The table is complete, and it is per-unit.**  Every eligible segment appears —
the null ones, the boring ones, the ones that embarrass the hypothesis — and
each row is one randomization unit, because the multiplicity rule this
capability offers first is a sign-flip max-t and a sign flip acts on units
(:mod:`kleinlib.generation.templates` says why at length).  An omitted eligible
segment is a FAIL, not a rounding of the story.

**The multiplicity rule is declared, and a floor is not one.**  RF-13: a
measured effect floor answers "is this bigger than noise on one comparison",
never "is this bigger than noise on the largest of four hundred".  Each cell
declares ``family_maxt`` (:func:`kleinlib.metrology.family_maxt`, applied to
both signs of every segment so the guard is two-sided), ``bonferroni``, or a
``declared`` threshold from a registered null sweep — before it runs.

**A receipt records an observation, never an explanation.**  ``<study>#Sn``
carries the cell, the run, the segment, the deviation, the adjusted score and
the pinned table's hash.  Its ``explanation`` starts ``unresolved`` and STAYS
unresolved until a human writes one: A2's anomaly ledger, whose whole value is
that the unexplained entries are still in it.  And an S receipt can never carry
a ``confirmed`` claim — discovery is exploratory by construction, and
confirmation belongs to a separately registered ``test`` study on evidence
independent of the selection (R-INV-6).

Registered, not wired in: this module exports one
:class:`~kleinlib.generation.registry.Capability` and the spine finds it through
:data:`kleinlib.generation.capabilities.MODULES`.
"""

from __future__ import annotations

import datetime as _datetime
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ..contract import PREDICTION_ID_RE, mutable_surface, normalize_tracks, registered_predictions
from ..errors import WorkflowError
from ..primitives import sha256_bytes, sha256_file
from ..transaction import git_blob, relative
from .admission import Context, load_receipts
from .calibration import numbers_agree
from .chronology import gate_events
from .envelope import GENERATION_SCHEMA
from .ledger import read_events, read_object
from .registry import Capability
from .templates import (
    EXPECTATION_FOR_STATISTIC,
    STATISTIC_FOR_TEMPLATE,
    STATISTICS,
    TABLE_COLUMNS,
    TEMPLATES,
    parse_table,
    segments_in_order,
)
from .verify import Check

if TYPE_CHECKING:  # pragma: no cover - types only
    from .registry import FamilyContext

__all__ = [
    "CAPABILITY",
    "CAPABILITY_NAME",
    "CELLS_NAME",
    "CELL_ID_RE",
    "MULTIPLICITY_METHODS",
    "RECEIPT_TYPE",
    "RECORD_TYPE",
    "REGISTER_TYPE",
    "SUMMARY_COLUMNS",
    "VERDICTS",
    "adjusted_scores",
    "build_record",
    "build_registration",
    "cell_runs",
    "cells_path",
    "cells_problems",
    "next_surprise_number",
    "ordered_cell",
    "parse_cells",
    "read_units",
    "segment_inventory",
    "receipt_object",
    "receipts",
    "records",
    "registered_cells",
    "registrations",
    "render_cells",
    "summarize",
    "summary_table_path",
    "summary_table_text",
    "surprise_family",
    "table_relpath",
    "write_summary_table",
]

CAPABILITY_NAME = "surprise"

#: The driver's own file — study root, beside ``study.yaml``, because a search
#: space is meant to be READ before it is run.
CELLS_NAME = "discovery_cells.yaml"

REGISTER_TYPE = "cells_registered"
RECORD_TYPE = "surprise_recorded"
RECEIPT_TYPE = "surprise_receipt"

#: Cell ids are plain and local (``cell_residuals_by_habitat``).  The
#: ``<study>#Sn`` ids the receipts carry are allocated by ``record`` and are
#: always fully qualified — RF-02: a bare ``S3`` is a scouting-ledger entry, and
#: the two must never be readable as the same token.
CELL_ID_RE = re.compile(r"^cell_[a-z0-9][a-z0-9_]*$")

SURPRISE_ID_RE = re.compile(r"^(?P<study>[^#\s]+)#S(?P<number>\d+)$")

#: A bare ``S3`` in findings §③ — the ambiguity RF-02 names, warned about but
#: never failed: the scouting ledger legitimately uses bare ``S#`` ids, and
#: ``kleinlib.claims.SENTENCE_EXEMPT_RE`` exempts them from the numbers scan.
BARE_S_RE = re.compile(r"(?<![#\w])S\d+\b")

MULTIPLICITY_METHODS: tuple[str, ...] = ("family_maxt", "bonferroni", "declared")

#: A segment's verdict.  ``inconclusive`` is a first-class outcome, not a
#: missing one: a slice below ``minimum_n`` was searched and could not answer,
#: and it stays in the family and in the table saying so.
VERDICTS: tuple[str, ...] = ("violation", "null", "inconclusive")

#: The derived summary this capability writes under ``generation/tables/``.  The
#: pinned per-unit table is the study's evidence; this is the reading of it that
#: SYNTHESIZE cites and the referee scans.
SUMMARY_COLUMNS: tuple[str, ...] = (
    "segment",
    "n",
    "statistic",
    "expected",
    "deviation",
    "sd",
    "t",
    "adjusted_p",
    "verdict",
)

#: The default two-sided level when a rule declares no ``alpha``.  Recorded into
#: the registration object, so a later release cannot reinterpret an old cell.
DEFAULT_ALPHA = 0.05

_CELL_KEYS: tuple[str, ...] = (
    "cell_id",
    "track",
    "expectation_P",
    "template",
    "statistic",
    "input_refs",
    "adapter",
    "partition",
    "unit_policy",
    "group_policy",
    "segments",
    "units",
    "floor_ref",
    "minimum_n",
    "multiplicity_rule",
    "output_columns",
    "post_observation",
)

#: The partition a cell may never read.  A discovery cell is exploratory by
#: construction and the seal is a track's single confirmation look; spending it
#: on a screen would buy nothing and cost the study its confirmation.
SEALED_PARTITION = "sealed"


# --------------------------------------------------------------------------
# paths and files
# --------------------------------------------------------------------------


def cells_path(study_dir: Path) -> Path:
    return study_dir / CELLS_NAME


def table_relpath(cell_id: str) -> str:
    """Where a cell's pinned per-unit table lives, study-relative and POSIX."""
    return f"tables/{cell_id}.tsv"


def summary_table_path(study_dir: Path, cell_id: str) -> Path:
    """The derived per-segment summary, written by ``record`` and re-derived by ``verify``."""
    return study_dir / "generation" / "tables" / f"surprise_{cell_id}.tsv"


def _plain(value: Any) -> Any:
    """Coerce a YAML value into something ``canonical_json`` can hash."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (_datetime.date, _datetime.datetime)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def parse_cells(path: Path) -> dict[str, Any]:
    """``discovery_cells.yaml`` as a plain, hashable mapping."""
    if not path.is_file():
        raise WorkflowError(
            f"{CELLS_NAME} does not exist — copy "
            "`.claude/skills/klein/assets/discovery-cells-template.yaml` into the study "
            "and declare the cells before their evidence"
        )
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"could not read {CELLS_NAME}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise WorkflowError(f"{CELLS_NAME} must contain a top-level mapping")
    return _plain(value)


def render_cells(payload: Mapping[str, Any]) -> str:
    """Deterministic YAML in the schema's key order — the bytes the registration hashes."""
    return yaml.safe_dump(
        dict(payload), sort_keys=False, default_flow_style=False, allow_unicode=True
    )


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _listing(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def ordered_cell(cell: Mapping[str, Any]) -> dict[str, Any]:
    """One cell in the schema's key order, so a diff of two versions reads down the page."""
    return {key: cell[key] for key in _CELL_KEYS if key in cell}


def segment_inventory(cell: Mapping[str, Any]) -> list[str]:
    """The complete, frozen segment inventory of one cell — the denominator."""
    return _segment_values(cell.get("segments"))


def _segment_values(block: Any) -> list[str]:
    """The frozen inventory, as an ordered list of segment names.

    ``values:`` names them outright; ``bins:`` names cut points and the segments
    are the intervals between them, rendered exactly as the adapter must render
    them, so the inventory is a list of strings either way.
    """
    if not isinstance(block, Mapping):
        return []
    values = block.get("values")
    if _listing(values):
        return [str(item) for item in values]
    bins = block.get("bins")
    if _listing(bins) and len(bins) >= 2:
        return [f"[{bins[i]}, {bins[i + 1]})" for i in range(len(bins) - 1)]
    return []


def _multiplicity_problems(rule: Any, label: str) -> list[str]:
    """RF-13, in one function: a floor is not a multiple-testing correction."""
    if not isinstance(rule, Mapping):
        return [
            f"{label}: multiplicity_rule is required — a screening family without a "
            "declared correction reports the largest of many comparisons as if it were "
            "the only one (family_maxt | bonferroni | declared)"
        ]
    method = rule.get("method")
    if method not in MULTIPLICITY_METHODS:
        return [
            f"{label}: multiplicity_rule.method is {method!r}, expected one of "
            + ", ".join(MULTIPLICITY_METHODS)
            + " — a measured effect floor is not a multiplicity correction: it answers "
            "'bigger than noise on ONE comparison', never 'bigger than noise on the "
            "largest of many'"
        ]
    problems: list[str] = []
    alpha = rule.get("alpha", DEFAULT_ALPHA)
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not 0.0 < float(alpha) < 1.0:
        problems.append(f"{label}: multiplicity_rule.alpha is {alpha!r}, expected a number in (0, 1)")
    if method == "family_maxt":
        n_perm = rule.get("n_perm")
        if isinstance(n_perm, bool) or not isinstance(n_perm, int) or n_perm < 1:
            problems.append(f"{label}: multiplicity_rule.n_perm is {n_perm!r}, expected a positive integer")
        seed = rule.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            problems.append(f"{label}: multiplicity_rule.seed is {seed!r}, expected an integer")
    if method == "declared":
        if not _text(rule.get("sweep")):
            problems.append(
                f"{label}: multiplicity_rule.sweep must name the registered null sweep the "
                "threshold came from"
            )
        threshold = rule.get("threshold")
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or float(threshold) <= 0:
            problems.append(
                f"{label}: multiplicity_rule.threshold is {threshold!r} — a declared rule "
                "states the |t| the null sweep put the family's largest statistic at"
            )
    return problems


def _cell_problems(
    cell: Any,
    index: int,
    *,
    study_dir: Path,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    adapters: Mapping[str, str],
) -> list[str]:
    label = f"cell {index}"
    if not isinstance(cell, Mapping):
        return [f"{label}: must be a mapping"]
    cell_id = cell.get("cell_id")
    if not _text(cell_id) or not CELL_ID_RE.match(str(cell_id)):
        return [
            f"{label}: cell_id is {cell_id!r}, expected cell_<lowercase name> — the "
            "<study>#Sn ids are allocated by `surprise record`, never authored here"
        ]
    label = str(cell_id)
    problems: list[str] = []
    unknown = set(cell) - set(_CELL_KEYS)
    if unknown:
        problems.append(f"{label}: unknown keys {sorted(unknown)}")

    tracks = normalize_tracks(contract)
    track = cell.get("track")
    if track not in tracks:
        problems.append(
            f"{label}: track {track!r} is not declared in study.yaml "
            f"(declared: {', '.join(sorted(tracks)) or 'none'})"
        )

    template = cell.get("template")
    if template not in TEMPLATES:
        problems.append(f"{label}: template is {template!r}, expected one of {', '.join(TEMPLATES)}")
    statistic = cell.get("statistic")
    if statistic not in STATISTICS:
        problems.append(
            f"{label}: statistic is {statistic!r}, expected one of {', '.join(STATISTICS)}"
        )
    elif template in TEMPLATES and STATISTIC_FOR_TEMPLATE[str(template)] != statistic:
        problems.append(
            f"{label}: template {template!r} produces "
            f"{STATISTIC_FOR_TEMPLATE[str(template)]!r}, not {statistic!r} — the pair says "
            "what the number means and how it was computed, and they must agree"
        )

    problems.extend(_expectation_problems(cell, label, contract=contract))

    partition = cell.get("partition")
    if not _text(partition):
        problems.append(f"{label}: partition is required (development | train | <named block>)")
    elif str(partition).strip() == SEALED_PARTITION:
        problems.append(
            f"{label}: partition is {SEALED_PARTITION!r} — a discovery cell never reads the "
            "sealed block; screening on confirmation evidence spends the seal and buys "
            "nothing that could be confirmed afterwards"
        )
    if not _text(cell.get("unit_policy")):
        problems.append(f"{label}: unit_policy must say, in words, what one row of the table is")
    if "group_policy" not in cell:
        problems.append(f"{label}: group_policy is required (null when the units are independent)")
    if not _text(cell.get("units")):
        problems.append(f"{label}: units is required — a bare deviation is not a quantity")

    inventory = _segment_values(cell.get("segments"))
    block = cell.get("segments")
    if not isinstance(block, Mapping) or not _text(block.get("column")):
        problems.append(f"{label}: segments.column must name the column the inventory partitions")
    if not inventory:
        problems.append(
            f"{label}: segments must declare a non-empty inventory (values: [...] or "
            "bins: [...]) — the complete inventory IS the denominator"
        )
    elif len(set(inventory)) != len(inventory):
        problems.append(f"{label}: the segment inventory repeats a name")

    minimum_n = cell.get("minimum_n")
    if isinstance(minimum_n, bool) or not isinstance(minimum_n, int) or minimum_n < 2:
        problems.append(
            f"{label}: minimum_n is {minimum_n!r}, expected an integer >= 2 — a one-unit "
            "slice has no dispersion and cannot answer anything"
        )
    problems.extend(_floor_problems(cell.get("floor_ref"), label, state=state))
    problems.extend(_multiplicity_problems(cell.get("multiplicity_rule"), label))

    columns = cell.get("output_columns")
    if list(columns or []) != list(TABLE_COLUMNS):
        problems.append(
            f"{label}: output_columns is {columns!r}, expected {list(TABLE_COLUMNS)} — the "
            "pinned table is per-unit; the per-segment summary is derived by "
            "`klein generation surprise record`"
        )
    if not isinstance(cell.get("post_observation"), bool):
        problems.append(
            f"{label}: post_observation must be true or false — a cell added after its "
            "outputs were seen is labelled, never silently preregistered"
        )

    adapter = cell.get("adapter")
    if not _text(adapter):
        problems.append(f"{label}: adapter must name the declared adapter that fills the table")
    elif str(adapter) not in adapters:
        problems.append(
            f"{label}: adapter {adapter!r} is not in the document's adapters list "
            f"({', '.join(sorted(adapters)) or 'none declared'})"
        )
    problems.extend(_input_problems(cell.get("input_refs"), label, study_dir=study_dir))
    return problems


def _expectation_problems(
    cell: Mapping[str, Any], label: str, *, contract: Mapping[str, Any]
) -> list[str]:
    """``expectation_P`` is registered, adjudicable, and on the cell's track.

    Adjudicable because the cell runs through ordinary ``run-one --tests P#``:
    a manual prediction the notary cannot decide inside the run would leave the
    cell's expectation unadjudicated and the receipt resting on prose.
    """
    name = cell.get("expectation_P")
    if not _text(name) or not PREDICTION_ID_RE.match(str(name).strip()):
        return [f"{label}: expectation_P must name a registered prediction (P<number>)"]
    registered = registered_predictions(contract)
    entry = registered.get(str(name).strip())
    if entry is None:
        return [
            f"{label}: expectation_P names {name!r}, which study.yaml does not register "
            f"({', '.join(sorted(registered)) or 'none registered'})"
        ]
    problems: list[str] = []
    if entry.get("rule") is None:
        problems.append(
            f"{label}: {name} is manual (no rule) — the notary cannot adjudicate it inside "
            "the cell's run, so the expectation would never be decided by arithmetic"
        )
    declared = entry.get("track")
    if declared is not None and str(declared) != str(cell.get("track")):
        problems.append(f"{label}: {name} belongs to track {declared!r}, not {cell.get('track')!r}")
    return problems


def _floor_problems(value: Any, label: str, *, state: Mapping[str, Any]) -> list[str]:
    """``minimum_delta`` or a REGISTERED ``sweep:<name>`` — the same rule slates use."""
    if value == "minimum_delta":
        return []
    if isinstance(value, str) and value.startswith("sweep:"):
        name = value.split(":", 1)[1]
        sweeps = state.get("sweeps") if isinstance(state.get("sweeps"), Mapping) else {}
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


def _input_problems(refs: Any, label: str, *, study_dir: Path) -> list[str]:
    if not _listing(refs) or not refs:
        return [f"{label}: input_refs must be a non-empty list of {{path, sha256}}"]
    problems: list[str] = []
    for index, ref in enumerate(refs, start=1):
        where = f"{label}: input_refs[{index}]"
        if not isinstance(ref, Mapping) or not _text(ref.get("path")):
            problems.append(f"{where} must be a mapping with a study-relative path")
            continue
        problems.extend(_pin_problems(study_dir, str(ref["path"]), ref.get("sha256"), where))
    return problems


def _pin_problems(study_dir: Path, rel: str, recorded: Any, where: str) -> list[str]:
    """One pinned file: inside the study, present, and hashing to what was pinned."""
    path = (study_dir / rel).resolve()
    try:
        path.relative_to(study_dir.resolve())
    except ValueError:
        return [f"{where}: {rel!r} escapes the study directory"]
    if not path.is_file():
        return [f"{where}: {rel!r} does not exist"]
    if recorded is None:
        return []
    actual = sha256_file(path)
    if actual != recorded:
        return [
            f"{where}: {rel} is {actual[:12]}… but the registration pinned "
            f"{str(recorded)[:12]}… — a discovery adapter and its inputs are frozen "
            "before the evidence"
        ]
    return []


def _adapter_map(doc: Mapping[str, Any]) -> dict[str, str | None]:
    """``{path: pinned sha or None}`` from the document's ``adapters`` list."""
    out: dict[str, str | None] = {}
    entries = doc.get("adapters")
    if not _listing(entries):
        return out
    for entry in entries:
        if isinstance(entry, Mapping) and _text(entry.get("path")):
            sha = entry.get("sha256")
            out[str(entry["path"])] = str(sha) if _text(sha) else None
    return out


def cells_problems(
    doc: Mapping[str, Any],
    *,
    study: str,
    study_dir: Path,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
) -> list[str]:
    """Everything wrong with an authored ``discovery_cells.yaml``, one line each.

    ``previous`` is the newest registered version, so a re-registration can add
    cells but never restate one: a registered cell is frozen field for field,
    and a change of segments, statistic or inputs under a live id is a different
    search that would inherit the first one's chronology.
    """
    problems: list[str] = []
    if doc.get("type") != "discovery-cells":
        problems.append(f"type must be 'discovery-cells', got {doc.get('type')!r}")
    declared = doc.get("study")
    if declared is not None and str(declared) != study:
        problems.append(f"study is {declared!r}, expected {study!r}")
    unknown = set(doc) - {"type", "study", "adapters", "cells"}
    if unknown:
        problems.append(f"unknown top-level keys {sorted(unknown)}")

    adapters = _adapter_map(doc)
    if not adapters:
        problems.append(
            "adapters must list the adapter modules the cells use — they map field "
            "measurements into the table contract and are hashed here"
        )
    surface = set(mutable_surface(contract))
    for rel, sha in adapters.items():
        where = f"adapter {rel}"
        if rel in surface:
            problems.append(
                f"{where} is part of entrypoint.mutable — an adapter inside the mutable "
                "surface is edited per experiment, so nothing it produced can be "
                "attributed to the version that was registered"
            )
        problems.extend(_pin_problems(study_dir, rel, sha, where))

    cells = doc.get("cells")
    if not _listing(cells) or not cells:
        return [*problems, "cells must be a non-empty list"]

    seen: dict[str, int] = {}
    frozen = {
        str(cell.get("cell_id")): cell
        for cell in ((previous or {}).get("cells") or [])
        if isinstance(cell, Mapping)
    }
    for index, cell in enumerate(cells, start=1):
        problems.extend(
            _cell_problems(
                cell,
                index,
                study_dir=study_dir,
                contract=contract,
                state=state,
                adapters=adapters,
            )
        )
        if not isinstance(cell, Mapping):
            continue
        cell_id = cell.get("cell_id")
        if not _text(cell_id):
            continue
        name = str(cell_id)
        if name in seen:
            problems.append(f"{name}: declared twice (cells {seen[name]} and {index})")
        seen.setdefault(name, index)
        before = frozen.get(name)
        if before is not None and _plain(dict(cell)) != _plain(dict(before)):
            problems.append(
                f"{name}: a registered cell is frozen — this version changes it. A "
                "different search space is a different cell with a different id, and "
                "one added now is labelled post_observation"
            )
    for name in frozen:
        if name not in seen:
            problems.append(
                f"{name}: was registered and is missing from this version — a registered "
                "cell is never withdrawn; its table and its null verdicts stay evidence"
            )
    return problems


# --------------------------------------------------------------------------
# reading the ledger
# --------------------------------------------------------------------------


def _objects(
    study_dir: Path, events: Sequence[Mapping[str, Any]], event_type: str
) -> list[dict[str, Any]]:
    """``[{event, sha, object}]`` in chain order; an unreadable object is skipped.

    Skipped because the spine's ``generation orphans`` family reports it: one
    broken object must not blind every other check.
    """
    out: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != event_type:
            continue
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            out.append({"event": dict(event), "sha": sha, "object": read_object(study_dir, sha)})
        except WorkflowError:
            continue
    return out


def registrations(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return _objects(study_dir, events, REGISTER_TYPE)


def records(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return _objects(study_dir, events, RECORD_TYPE)


def receipts(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return _objects(study_dir, events, RECEIPT_TYPE)


def registered_cells(
    study_dir: Path, events: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    """``{cell_id: the cell as registered}`` over every version, newest wins."""
    out: dict[str, dict[str, Any]] = {}
    for version in registrations(study_dir, events):
        for cell in version["object"].get("cells") or []:
            if isinstance(cell, Mapping) and _text(cell.get("cell_id")):
                out[str(cell["cell_id"])] = dict(cell)
    return out


def next_surprise_number(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> int:
    """One past the highest ``Sn`` ever allocated.  Ids are never recycled."""
    highest = 0
    for entry in receipts(study_dir, events):
        match = SURPRISE_ID_RE.match(str(entry["object"].get("id")))
        if match:
            highest = max(highest, int(match.group("number")))
    return highest + 1


def cell_runs(
    study_dir: Path, events: Sequence[Mapping[str, Any]], match: Any
) -> dict[str, str]:
    """``{run: cell_id}`` for every run an ADMITTED cell receipt was consumed by.

    ``match.consumed`` only carries receipts the spine classified ``admitted``,
    so a cell whose run was ``mismatched`` or ``refused-but-run`` binds nothing
    here and is reported by the spine's own ``generation admission`` family.
    """
    bound: dict[str, str] = {}
    for receipt in load_receipts(study_dir, events):
        run = match.consumed.get(receipt.sha)
        if run is None or receipt.verdict != "admitted":
            continue
        try:
            obj = read_object(study_dir, receipt.sha)
        except WorkflowError:  # pragma: no cover - the ledger guard catches this first
            continue
        intended = obj.get("intended_action")
        cell = intended.get("cell_id") if isinstance(intended, Mapping) else None
        if isinstance(cell, str) and cell:
            bound[run] = cell
    return bound


# --------------------------------------------------------------------------
# the arithmetic
# --------------------------------------------------------------------------


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _sd(values: Sequence[float]) -> float:
    """The ddof=1 sample standard deviation — ``metrology._t_stat``'s convention."""
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _t(deviation: float, sd: float, n: int) -> float | None:
    """The one-sample t on a segment's unit deviations, or ``None`` when it cannot fire.

    ``None`` is :func:`kleinlib.metrology.family_maxt`'s never-firing placeholder
    in JSON: fewer than two units has no dispersion.  A zero spread is infinite
    and is reported as such rather than silently dropped.
    """
    if n < 2:
        return None
    if sd == 0.0:
        return math.inf if deviation > 0 else (-math.inf if deviation < 0 else 0.0)
    return deviation / (sd / math.sqrt(n))


def summarize(
    units: Sequence[Mapping[str, Any]], *, statistic: str, inventory: Sequence[str]
) -> list[dict[str, Any]]:
    """One row per FROZEN segment, in inventory order — including the empty ones.

    Inventory order, not table order: the denominator is what was registered,
    so a segment the table never mentions still gets a row (``n: 0``) and is
    reported as missing rather than quietly leaving the family.
    """
    values = [float(row["value"]) for row in units]
    pooled = _mean(values) if values else 0.0
    expected = pooled if EXPECTATION_FOR_STATISTIC[statistic] == "pooled_mean" else 0.0
    rows: list[dict[str, Any]] = []
    for segment in inventory:
        members = [float(row["value"]) for row in units if str(row["segment"]) == segment]
        n = len(members)
        mean = _mean(members) if members else 0.0
        sd = _sd(members)
        deviation = mean - expected if members else 0.0
        rows.append(
            {
                "segment": segment,
                "n": n,
                "statistic": mean if members else None,
                "expected": expected,
                "deviation": deviation if members else None,
                "sd": sd if members else None,
                "t": _t(deviation, sd, n) if members else None,
            }
        )
    return rows


def _deltas(
    units: Sequence[Mapping[str, Any]], *, inventory: Sequence[str], expected: float
) -> dict[str, list[float]]:
    """Per-segment unit deviations, PADDED with NaN to a common width.

    ``family_maxt`` applies one sign vector jointly to the whole family, so every
    member must carry the same number of slots; a shorter segment pads at the
    end (the reference's own instruction).  Alignment is therefore fixed by
    position in the pinned table, which is why the table's row order is part of
    the evidence.
    """
    by_segment = {
        segment: [
            float(row["value"]) - expected for row in units if str(row["segment"]) == segment
        ]
        for segment in inventory
    }
    width = max((len(values) for values in by_segment.values()), default=0)
    if width == 0:
        return {}
    return {
        segment: values + [math.nan] * (width - len(values))
        for segment, values in by_segment.items()
    }


def _normal_two_sided(t: float | None) -> float:
    """P(|Z| >= |t|) — the Bonferroni route's raw score, in the standard library.

    A normal approximation, declared as such: a t-distribution CDF would cost a
    dependency this layer does not take, and the approximation is
    anti-conservative on small samples.  ``surprise-protocol.md`` says to declare
    ``family_maxt`` when the segments are small, which is the honest fix rather
    than a better table lookup.
    """
    if t is None:
        return 1.0
    if math.isinf(t):
        return 0.0
    return math.erfc(abs(t) / math.sqrt(2.0))


def adjusted_scores(
    units: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    *,
    inventory: Sequence[str],
    expected: float,
    rule: Mapping[str, Any],
) -> dict[str, float | None]:
    """The declared multiplicity correction, applied to the WHOLE frozen family.

    ``family_maxt``
        A sign-flip max-t over both signs of every segment, so the guard is
        two-sided: the null distribution is the maximum over ``2m`` members and
        a segment's score is ``P(max >= |t_obs|)``.  Sparse and empty segments
        stay in the family as never-firing placeholders (score ``1.0``);
        dropping them once the outcomes are visible would shrink the denominator
        the guard exists to correct for.
    ``bonferroni``
        ``min(1, m · P(|Z| >= |t|))`` over the same ``m``.
    ``declared``
        No score: the cell declared a ``|t|`` threshold from a registered null
        sweep, and :func:`_verdicts` compares against it directly.
    """
    method = str(rule.get("method"))
    if method == "declared":
        return dict.fromkeys(inventory)
    if method == "bonferroni":
        size = len(inventory)
        return {
            str(row["segment"]): min(1.0, size * _normal_two_sided(row["t"])) for row in rows
        }
    deltas = _deltas(units, inventory=inventory, expected=expected)
    if not deltas:
        return dict.fromkeys(inventory)
    from ..metrology import family_maxt

    family: dict[str, list[float]] = {}
    for segment, values in deltas.items():
        family[f"{segment}↑"] = values
        family[f"{segment}↓"] = [-value for value in values]
    scores = family_maxt(
        family, n_perm=int(rule.get("n_perm", 1024)), seed=int(rule.get("seed", 0))
    )
    return {
        segment: float(min(scores[f"{segment}↑"], scores[f"{segment}↓"]))
        for segment in deltas
    }


def _verdicts(
    rows: Sequence[Mapping[str, Any]],
    scores: Mapping[str, float | None],
    *,
    minimum_n: int,
    rule: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """``minimum_n`` first, then the family rule.  Sparse is inconclusive, never null."""
    alpha = float(rule.get("alpha", DEFAULT_ALPHA))
    threshold = rule.get("threshold")
    out: list[dict[str, Any]] = []
    for row in rows:
        entry = dict(row)
        score = scores.get(str(row["segment"]))
        entry["adjusted_p"] = None if score is None else float(score)
        if int(row["n"]) < minimum_n:
            entry["verdict"] = "inconclusive"
        elif str(rule.get("method")) == "declared":
            t = row["t"]
            fired = t is not None and abs(float(t)) >= float(threshold)
            entry["verdict"] = "violation" if fired else "null"
        else:
            score = entry["adjusted_p"]
            entry["verdict"] = "violation" if score is not None and score <= alpha else "null"
        out.append(entry)
    return out


def build_record(
    *,
    run: str,
    cell: Mapping[str, Any],
    units: Sequence[Mapping[str, Any]],
    table_sha256: str,
) -> dict[str, Any]:
    """The whole ``surprise_recorded`` body — pure, and replayable from the table.

    ``klein generation surprise record`` writes what this returns;
    ``klein generation verify`` calls it again from the same pinned bytes and
    compares every number.  It reads the registered cell and the table and
    nothing else, so the two calls cannot disagree unless something on disk
    changed — which is the whole point.
    """
    statistic = str(cell["statistic"])
    inventory = _segment_values(cell.get("segments"))
    rule = dict(cell.get("multiplicity_rule") or {})
    rows = summarize(units, statistic=statistic, inventory=inventory)
    expected = float(rows[0]["expected"]) if rows else 0.0
    scores = adjusted_scores(units, rows, inventory=inventory, expected=expected, rule=rule)
    segments = _verdicts(rows, scores, minimum_n=int(cell["minimum_n"]), rule=rule)
    present = set(segments_in_order(units))
    missing = [name for name in inventory if name not in present]
    extra = [name for name in segments_in_order(units) if name not in set(inventory)]
    violations = [row["segment"] for row in segments if row["verdict"] == "violation"]
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "surprise_record",
        "run": run,
        "cell_id": str(cell["cell_id"]),
        "table_path": table_relpath(str(cell["cell_id"])),
        "table_sha256": table_sha256,
        "statistic": statistic,
        "expectation": EXPECTATION_FOR_STATISTIC[statistic],
        "expected": expected,
        "minimum_n": int(cell["minimum_n"]),
        "multiplicity_rule": rule,
        "family_size": len(inventory),
        "units_measured": len(units),
        "segments": segments,
        "missing_segments": missing,
        "extra_segments": extra,
        "n_violations": len(violations),
        "post_observation": bool(cell.get("post_observation")),
        "outcome": "complete" if not missing and not extra else "defective",
    }


def summary_table_text(record: Mapping[str, Any]) -> str:
    """The derived per-segment TSV, in inventory order, deterministic."""
    lines = ["\t".join(SUMMARY_COLUMNS)]
    for row in record.get("segments") or []:
        lines.append(
            "\t".join(
                (
                    str(row["segment"]).replace("\t", " "),
                    str(int(row["n"])),
                    _cell(row["statistic"]),
                    _cell(row["expected"]),
                    _cell(row["deviation"]),
                    _cell(row["sd"]),
                    _cell(row["t"]),
                    _cell(row["adjusted_p"]),
                    str(row["verdict"]),
                )
            )
        )
    return "\n".join(lines) + "\n"


def _cell(value: Any) -> str:
    return "" if value is None else format(float(value), ".12g")


def receipt_object(
    *,
    surprise_id: str,
    record: Mapping[str, Any],
    segment: Mapping[str, Any],
    cell: Mapping[str, Any],
    explanation: str,
    exposure: Sequence[str],
) -> dict[str, Any]:
    """One ``<study>#Sn`` — an observation, its provenance, and no explanation.

    ``explanation`` defaults to ``unresolved`` and is testimony when it is
    anything else: nothing here checks that a mechanism is real, and A2's
    anomaly ledger is worth keeping precisely because the unexplained rows stay
    in it.
    """
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "surprise_receipt",
        "id": surprise_id,
        "cell_id": str(cell["cell_id"]),
        "run": str(record["run"]),
        "segment": str(segment["segment"]),
        "statistic": str(record["statistic"]),
        "n": int(segment["n"]),
        "deviation": segment["deviation"],
        "units": str(cell.get("units")),
        "adjusted_p": segment["adjusted_p"],
        "table_path": str(record["table_path"]),
        "table_sha256": str(record["table_sha256"]),
        "family_size": int(record["family_size"]),
        "explanation": explanation,
        "label": "post-observation" if record.get("post_observation") else "preregistered",
        "exposure": list(exposure),
    }


def build_registration(
    doc: Mapping[str, Any],
    *,
    study: str,
    version: int,
    parent_ids: Sequence[str],
    file_sha256: str,
    late: bool,
) -> dict[str, Any]:
    """The ``cells_registered`` object: the document VERBATIM, plus its lineage.

    Verbatim because verification re-validates the registry rather than trusting
    a recorded verdict, and re-validating a summary would only prove the summary.
    """
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "discovery_cells",
        "study": study,
        "version": version,
        "parent_ids": list(parent_ids),
        "cells_path": CELLS_NAME,
        "file_sha256": file_sha256,
        "adapters": _plain(doc.get("adapters") or []),
        "cells": _plain(doc.get("cells") or []),
        "late": bool(late),
    }


# --------------------------------------------------------------------------
# admission
# --------------------------------------------------------------------------


def _rule_cell_is_registered(ctx: Context) -> list[str]:
    """The admission rule, in the order a driver hits it.

    A cell admission is admitted iff the cell is registered, its adapter and
    inputs still hash to what the registration pinned, the track is the cell's
    own, and ``--tests`` asks the notary to adjudicate the registered
    expectation.  The last clause is the load-bearing one: without it the cell's
    expectation is decided by prose afterwards, which is the failure the whole
    capability exists to make impossible.
    """
    if ctx.action != "cell" and not ctx.cell:
        return []
    if ctx.cell and ctx.action != "cell":
        return [
            f"--cell {ctx.cell} names a discovery cell, but the action is {ctx.action!r} — "
            "a cell runs as `--action cell`"
        ]
    if not ctx.cell:
        return [
            "a cell admission on a surprise-enabled study names its registered cell with "
            "--cell (`klein generation surprise register` locks them before their evidence)"
        ]
    events = read_events(ctx.study_dir)
    index = registered_cells(ctx.study_dir, events)
    cell = index.get(ctx.cell)
    if cell is None:
        return [
            f"{ctx.cell} is not a registered discovery cell "
            f"(registered: {', '.join(sorted(index)) or 'none'}) — a cell that was not "
            "registered before its evidence cannot acquire preregistration afterwards"
        ]
    problems: list[str] = []
    if str(cell.get("track")) != ctx.track:
        problems.append(f"{ctx.cell} is a cell of track {cell.get('track')!r}, not {ctx.track!r}")
    expectation = str(cell.get("expectation_P"))
    if expectation not in ctx.tests:
        problems.append(
            f"--tests must include {expectation}, the cell's registered expectation — the "
            "notary adjudicates it on this run's printed block, and nothing else decides it"
        )
    adapter = cell.get("adapter")
    if _text(adapter):
        pinned = _adapter_pin(ctx.study_dir, events, str(adapter))
        problems.extend(_pin_problems(ctx.study_dir, str(adapter), pinned, f"adapter {adapter}"))
    for index_, ref in enumerate(cell.get("input_refs") or [], start=1):
        if isinstance(ref, Mapping) and _text(ref.get("path")):
            problems.extend(
                _pin_problems(
                    ctx.study_dir, str(ref["path"]), ref.get("sha256"), f"input_refs[{index_}]"
                )
            )
    return problems


def _adapter_pin(
    study_dir: Path, events: Sequence[Mapping[str, Any]], adapter: str
) -> str | None:
    for version in registrations(study_dir, events):
        for entry in version["object"].get("adapters") or []:
            if isinstance(entry, Mapping) and str(entry.get("path")) == adapter:
                sha = entry.get("sha256")
                return str(sha) if _text(sha) else None
    return None


def _receipt_inputs(ctx: Context) -> dict[str, str | None]:
    """The registration this admission was taken under — pinned into the receipt."""
    if ctx.action != "cell" and not ctx.cell:
        return {}
    versions = registrations(ctx.study_dir, read_events(ctx.study_dir))
    return {"cells": versions[-1]["sha"]} if versions else {}


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

CELLS_CHECK = "surprise cells"
RECORDS_CHECK = "surprise records"
RECEIPTS_CHECK = "surprise receipts"
CLAIMS_CHECK = "surprise claims"
FINDINGS_CHECK = "surprise findings"


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


def _pass(name: str, detail: str) -> Check:
    return Check(name, "PASS", detail)


def _warn(name: str, detail: str) -> Check:
    return Check(name, "WARN", detail)


def _cells_checks(ctx: FamilyContext, versions: Sequence[Mapping[str, Any]]) -> list[Check]:
    problems: list[str] = []
    first = versions[0]
    if first["object"].get("late"):
        problems.append(
            "the first registration was recorded after a cell admission already named one "
            "of its cells — a search space registered once its outputs are visible is a "
            "description of them"
        )
    problems.extend(_method_order_problems(ctx, first))

    newest = versions[-1]["object"]
    path = cells_path(ctx.study_dir)
    if not path.is_file():
        problems.append(f"{CELLS_NAME} is missing but a registration exists")
    elif sha256_file(path) != newest.get("file_sha256"):
        problems.append(
            f"{CELLS_NAME} is {sha256_file(path)[:12]}… but version "
            f"{newest.get('version')} registered {str(newest.get('file_sha256'))[:12]}… — "
            "a registered search space is not edited in place"
        )

    surface = set(mutable_surface(ctx.contract))
    for entry in newest.get("adapters") or []:
        if not isinstance(entry, Mapping) or not _text(entry.get("path")):
            continue
        rel = str(entry["path"])
        if rel in surface:
            problems.append(f"adapter {rel} is now part of entrypoint.mutable")
        problems.extend(_pin_problems(ctx.study_dir, rel, entry.get("sha256"), f"adapter {rel}"))

    registered = registered_cells(ctx.study_dir, list(ctx.events))
    for name, cell in sorted(registered.items()):
        for index, ref in enumerate(cell.get("input_refs") or [], start=1):
            if isinstance(ref, Mapping) and _text(ref.get("path")):
                problems.extend(
                    _pin_problems(
                        ctx.study_dir,
                        str(ref["path"]),
                        ref.get("sha256"),
                        f"{name}: input_refs[{index}]",
                    )
                )
        problems.extend(_contract_drift_problems(ctx.contract, cell, name))

    if problems:
        return [_fail(CELLS_CHECK, "; ".join(problems[:8]))]
    segments = sum(len(_segment_values(cell.get("segments"))) for cell in registered.values())
    return [
        _pass(
            CELLS_CHECK,
            f"{len(registered)} cell(s) across {len(versions)} version(s), "
            f"{segments} frozen segment(s); adapters and inputs unchanged since "
            "registration",
        )
    ]


def _method_order_problems(ctx: FamilyContext, first: Mapping[str, Any]) -> list[str]:
    """Registration comes after METHOD: the adapters are named on the method card."""
    gates = gate_events(ctx.core, "method")
    if not gates:
        return []
    anchor = first["event"].get("core_anchor")
    sequence = anchor.get("sequence") if isinstance(anchor, Mapping) else None
    gate_sequence = gates[0].get("sequence")
    if not isinstance(sequence, int) or not isinstance(gate_sequence, int):
        return ["the registration anchor or the method gate record has no sequence"]
    if sequence < gate_sequence:
        return [
            f"the cells were registered at core sequence {sequence}, before the method "
            f"gate (sequence {gate_sequence}) — the adapters a cell freezes are the ones "
            "the method card named"
        ]
    return []


def _contract_drift_problems(
    contract: Mapping[str, Any], cell: Mapping[str, Any], name: str
) -> list[str]:
    """The registry is frozen; ``study.yaml`` is not.  Re-read the link, now."""
    problems: list[str] = []
    tracks = normalize_tracks(contract)
    if str(cell.get("track")) not in tracks:
        problems.append(f"{name}: track {cell.get('track')!r} is no longer declared in study.yaml")
    registered = registered_predictions(contract)
    expectation = str(cell.get("expectation_P"))
    entry = registered.get(expectation)
    if entry is None:
        problems.append(f"{name}: {expectation} is no longer a registered prediction")
    elif entry.get("rule") is None:
        problems.append(f"{name}: {expectation} lost its rule and can no longer be adjudicated")
    return problems


def _manifests(ctx: FamilyContext) -> dict[str, dict[str, Any]]:
    from ..manifest import load_manifests

    try:
        return {str(m.get("experiment")): dict(m) for m in load_manifests(ctx.study_dir)}
    except WorkflowError:  # pragma: no cover - the core receipt reports a broken manifest
        return {}


def _records_checks(
    ctx: FamilyContext, recorded: Sequence[Mapping[str, Any]]
) -> tuple[list[Check], dict[str, Any]]:
    problems: list[str] = []
    manifests = _manifests(ctx)
    registered = registered_cells(ctx.study_dir, list(ctx.events))
    ran = cell_runs(ctx.study_dir, list(ctx.events), ctx.match)
    by_run = {str(entry["object"].get("run")): entry for entry in recorded}

    for run, cell_id in sorted(ran.items()):
        if run not in by_run:
            problems.append(
                f"{run} ran cell {cell_id} and was never recorded — `klein generation "
                f"surprise record --run {run}` reads the pinned table and retains every "
                "segment, including the null ones"
            )
    for run, entry in sorted(by_run.items()):
        problems.extend(
            _one_record_problems(
                ctx, run, entry, ran=ran, registered=registered, manifests=manifests
            )
        )

    violations = sum(int(entry["object"].get("n_violations") or 0) for entry in recorded)
    summary = {
        "runs": len(by_run),
        "violations": violations,
        "post_observation": sum(
            1 for entry in recorded if entry["object"].get("post_observation")
        ),
    }
    if problems:
        return [_fail(RECORDS_CHECK, "; ".join(problems[:8]))], summary
    if not recorded:
        return [
            _warn(
                RECORDS_CHECK,
                "no discovery cell has run yet — the cells are registered and their tables "
                "are still to come",
            )
        ], summary
    return [
        _pass(
            RECORDS_CHECK,
            f"{len(by_run)} recorded cell run(s); every pinned table recomputes to the "
            f"segments, family sizes and verdicts on the record ({violations} violation(s))",
        )
    ], summary


def _one_record_problems(
    ctx: FamilyContext,
    run: str,
    entry: Mapping[str, Any],
    *,
    ran: Mapping[str, str],
    registered: Mapping[str, Mapping[str, Any]],
    manifests: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    record = entry["object"]
    cell_id = str(record.get("cell_id"))
    problems: list[str] = []
    if ran.get(run) != cell_id:
        return [
            f"{run}: a record for cell {cell_id} exists, but no admitted cell admission "
            f"binds that run to it (bound: {ran.get(run) or 'nothing'})"
        ]
    cell = registered.get(cell_id)
    if cell is None:
        return [f"{run}: cell {cell_id} is not registered"]
    manifest = manifests.get(run)
    if manifest is None:
        return [f"{run}: no manifest to read"]
    if manifest.get("evaluation_kind") == "final_test":
        problems.append(
            f"{run}: the cell ran as a sealed final test — a discovery cell never reads "
            "the sealed block"
        )
    rel = table_relpath(cell_id)
    artifacts = manifest.get("artifacts")
    pinned = artifacts.get(rel) if isinstance(artifacts, Mapping) else None
    if not isinstance(pinned, Mapping):
        problems.append(
            f"{run}: the manifest pins no artifact {rel} — the cell's entrypoint prints "
            "`artifact: " + rel + "` and the notary hashes it"
        )
    elif pinned.get("sha256") != record.get("table_sha256"):
        problems.append(
            f"{run}: the record hashed {str(record.get('table_sha256'))[:12]}… but the "
            f"manifest pinned {str(pinned.get('sha256'))[:12]}…"
        )
    problems.extend(_pinned_at_commit_problems(ctx, run, manifest, cell))

    path = ctx.study_dir / rel
    if not path.is_file():
        problems.append(f"{run}: {rel} is missing; the record hashed it")
        return problems
    if sha256_file(path) != record.get("table_sha256"):
        problems.append(f"{run}: {rel} is not the table the record hashed")
        return problems
    try:
        units = parse_table(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        problems.append(f"{run}: {rel} is unreadable ({exc})")
        return problems

    recomputed = build_record(
        run=run, cell=cell, units=units, table_sha256=str(record.get("table_sha256"))
    )
    keys = (
        "segments",
        "missing_segments",
        "extra_segments",
        "family_size",
        "n_violations",
        "expected",
        "units_measured",
        "outcome",
    )
    for line in numbers_agree(
        {key: record.get(key) for key in keys}, {key: recomputed[key] for key in keys}
    ):
        problems.append(f"{run}: {line}")
    if record.get("missing_segments"):
        problems.append(
            f"{run}: {len(record['missing_segments'])} eligible segment(s) are missing from "
            f"{rel} ({', '.join(str(s) for s in record['missing_segments'][:4])}) — the "
            "complete inventory IS the denominator"
        )
    if record.get("extra_segments"):
        problems.append(
            f"{run}: {rel} carries segment(s) the registration never froze "
            f"({', '.join(str(s) for s in record['extra_segments'][:4])}) — a new slice is "
            "a new cell, labelled post_observation"
        )
    summary_path = summary_table_path(ctx.study_dir, cell_id)
    if not summary_path.is_file():
        problems.append(f"{run}: {summary_path.name} is missing; the record hashed it")
    elif summary_path.read_text(encoding="utf-8") != summary_table_text(recomputed):
        problems.append(f"{run}: {summary_path.name} does not match the recomputed segments")
    return problems


def _pinned_at_commit_problems(
    ctx: FamilyContext, run: str, manifest: Mapping[str, Any], cell: Mapping[str, Any]
) -> list[str]:
    """R-INV-3: the adapter and inputs AT THE RUN'S CANDIDATE COMMIT, not now.

    "Unchanged today" is not the question — a file edited before the run and
    restored afterwards would pass that. What has to hold is that the bytes the
    run actually executed are the bytes the registration pinned.
    """
    repo = ctx.repo
    commit = manifest.get("candidate_commit")
    if repo is None or not isinstance(commit, str):
        return []
    wanted: list[tuple[str, Any]] = []
    adapter = cell.get("adapter")
    if _text(adapter):
        wanted.append((str(adapter), _adapter_pin(ctx.study_dir, list(ctx.events), str(adapter))))
    for ref in cell.get("input_refs") or []:
        if isinstance(ref, Mapping) and _text(ref.get("path")):
            wanted.append((str(ref["path"]), ref.get("sha256")))
    problems: list[str] = []
    for rel, sha in wanted:
        if sha is None:
            continue
        blob = git_blob(repo, commit, relative(repo, ctx.study_dir / rel))
        if blob is None:
            problems.append(f"{run}: {rel} does not exist at the run's candidate commit")
        elif sha256_bytes(blob) != sha:
            problems.append(
                f"{run}: {rel} at the candidate commit is {sha256_bytes(blob)[:12]}…, not the "
                f"registered {str(sha)[:12]}… — the cell ran a different adapter or input"
            )
    return problems


def _receipts_checks(
    ctx: FamilyContext,
    recorded: Sequence[Mapping[str, Any]],
    issued: Sequence[Mapping[str, Any]],
    study: str,
) -> tuple[list[Check], dict[str, Any]]:
    problems: list[str] = []
    by_run: dict[str, list[Mapping[str, Any]]] = {}
    highest = 0
    seen: set[str] = set()
    for entry in issued:
        obj = entry["object"]
        name = str(obj.get("id"))
        match = SURPRISE_ID_RE.match(name)
        if match is None or match.group("study") != study:
            problems.append(
                f"receipt id {name!r} is not {study}#Sn — a surprise id is ALWAYS fully "
                "qualified, because a bare S3 is a scouting-ledger entry"
            )
            continue
        number = int(match.group("number"))
        if name in seen:
            problems.append(f"{name} was issued twice — ids are never recycled")
        elif number <= highest:
            problems.append(f"{name} was allocated after #S{highest} — ids are monotonic")
        seen.add(name)
        highest = max(highest, number)
        by_run.setdefault(str(obj.get("run")), []).append(obj)

    for entry in recorded:
        record = entry["object"]
        run = str(record.get("run"))
        expected = [
            row for row in record.get("segments") or [] if row.get("verdict") == "violation"
        ]
        got = by_run.get(run, [])
        if len(got) != len(expected):
            problems.append(
                f"{run}: {len(expected)} violation(s) recorded, {len(got)} receipt(s) issued "
                "— every violation gets one, and nothing else does"
            )
            continue
        wanted = {str(row["segment"]) for row in expected}
        for obj in got:
            if str(obj.get("segment")) not in wanted:
                problems.append(
                    f"{obj.get('id')}: segment {obj.get('segment')!r} is not a violating "
                    f"segment of {run}"
                )
            if obj.get("table_sha256") != record.get("table_sha256"):
                problems.append(f"{obj.get('id')}: does not carry the run's pinned table hash")
            label = "post-observation" if record.get("post_observation") else "preregistered"
            if obj.get("label") != label:
                problems.append(
                    f"{obj.get('id')}: label {obj.get('label')!r}, expected {label!r}"
                )
            if not _text(obj.get("explanation")):
                problems.append(
                    f"{obj.get('id')}: explanation is empty — `unresolved` is the honest "
                    "value and the ledger keeps it"
                )

    unresolved = sum(
        1 for entry in issued if str(entry["object"].get("explanation")) == "unresolved"
    )
    summary = {"issued": len(issued), "unresolved": unresolved}
    if problems:
        return [_fail(RECEIPTS_CHECK, "; ".join(problems[:8]))], summary
    if not issued:
        return [
            _pass(RECEIPTS_CHECK, "no segment violated its expectation; nothing to receipt")
        ], summary
    return [
        _pass(
            RECEIPTS_CHECK,
            f"{len(issued)} receipt(s), ids fully qualified and monotonic; {unresolved} "
            "unresolved (an unexplained anomaly stays unexplained)",
        )
    ], summary


def _claims_checks(ctx: FamilyContext, study: str) -> list[Check]:
    """R-INV-6: a discovery receipt can never carry a ``confirmed`` claim."""
    path = ctx.study_dir / "claims.lock"
    if not path.is_file():
        return [_pass(CLAIMS_CHECK, "no claims.lock yet")]
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # pragma: no cover - the claims law reports this
        return [_warn(CLAIMS_CHECK, f"claims.lock is unreadable ({exc})")]
    if not isinstance(lock, Mapping):
        return [_warn(CLAIMS_CHECK, "claims.lock is not an object")]

    registered = registered_cells(ctx.study_dir, list(ctx.events))
    tables = {table_relpath(name) for name in registered}
    artifacts = lock.get("artifacts") if isinstance(lock.get("artifacts"), Mapping) else {}
    derived = {
        alias
        for alias, meta in artifacts.items()
        if isinstance(meta, Mapping) and str(meta.get("path")) in tables
    }
    qualified = re.compile(rf"{re.escape(study)}#S\d+")
    problems: list[str] = []
    claims = lock.get("claims") if isinstance(lock.get("claims"), Mapping) else {}
    for cid, claim in sorted(claims.items()):
        if not isinstance(claim, Mapping) or claim.get("strength") != "confirmed":
            continue
        for item in claim.get("evidence") or []:
            alias = str(item)[len("art:") :] if str(item).startswith("art:") else None
            if alias in derived:
                problems.append(
                    f"{cid} is confirmed and cites art:{alias}, a discovery cell's table — "
                    "a screen selects what to look at and cannot also confirm it; the "
                    "confirmation is a separately registered `test` study on fresh evidence"
                )
            if qualified.search(str(item)):
                problems.append(f"{cid} is confirmed and cites {item} — an S receipt is exploratory")
        if qualified.search(str(claim.get("claim") or "")):
            problems.append(
                f"{cid} is confirmed and its sentence names a {study}#Sn receipt — a "
                "surprise is a hypothesis for the next study, never a confirmed finding"
            )
    if problems:
        return [_fail(CLAIMS_CHECK, "; ".join(problems[:6]))]
    return [
        _pass(
            CLAIMS_CHECK,
            f"no confirmed claim rests on a discovery table or an {study}#Sn receipt "
            f"({len(derived)} cell table(s) pinned)",
        )
    ]


def _findings_checks(ctx: FamilyContext) -> list[Check]:
    """RF-02: a bare ``S3`` in §③ reads as a scouting entry.  WARN, never FAIL."""
    path = ctx.study_dir / "findings.md"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    section = text
    where = "findings.md"
    for block in re.split(r"^## ", text, flags=re.M):
        if block.startswith("③"):
            section = block
            where = "findings.md §③"
            break
    bare = sorted(set(BARE_S_RE.findall(section)))
    if not bare:
        return [_pass(FINDINGS_CHECK, f"no bare S# token in {where}")]
    return [
        _warn(
            FINDINGS_CHECK,
            f"{where} carries the bare token(s) {', '.join(bare)} — a bare S# means a "
            "scouting-ledger entry (and the claims law's sentence scan exempts it as one); "
            "a surprise receipt is written fully qualified as <study>#Sn",
        )
    ]


def surprise_family(ctx: FamilyContext) -> tuple[list[Check], dict[str, Any]]:
    """The ``surprise`` family: integrity of the search record, then what it found."""
    from .manifest import study_id

    study = study_id(ctx.study_dir, ctx.contract)
    events = list(ctx.events)
    versions = registrations(ctx.study_dir, events)
    if not versions:
        return [
            _warn(
                CELLS_CHECK,
                "the surprise capability is declared and no discovery cell has been "
                "registered yet — `klein generation surprise register` locks the search "
                "space after METHOD and before its evidence",
            )
        ], {
            # `incomplete`, never `n/a`: `n/a` is the label's word for "not
            # declared" and comes only from `label.capability_outcomes`'s
            # defaults.  A declared-but-unexercised capability is incomplete.
            "integrity": "PASS",
            "outcome": "incomplete",
            "cells": 0,
            "violations": 0,
        }

    recorded = records(ctx.study_dir, events)
    issued = receipts(ctx.study_dir, events)
    checks = _cells_checks(ctx, versions)
    record_checks, record_summary = _records_checks(ctx, recorded)
    checks += record_checks
    receipt_checks, receipt_summary = _receipts_checks(ctx, recorded, issued, study)
    checks += receipt_checks
    checks += _claims_checks(ctx, study)
    checks += _findings_checks(ctx)

    integrity = "FAIL" if any(check.status == "FAIL" for check in checks) else "PASS"
    return checks, {
        "integrity": integrity,
        "outcome": "registered",
        "cells": len(registered_cells(ctx.study_dir, events)),
        "runs": record_summary["runs"],
        "violations": receipt_summary["issued"],
        "unresolved": receipt_summary["unresolved"],
        "post_observation": record_summary["post_observation"],
    }


#: The registration.  Everything above is reachable only through this object.
CAPABILITY = Capability(
    name=CAPABILITY_NAME,
    admission_rules=(_rule_cell_is_registered,),
    verify_family=surprise_family,
    receipt_inputs=_receipt_inputs,
)


# --------------------------------------------------------------------------
# helpers the CLI uses (kept here so the shapes live with the rules)
# --------------------------------------------------------------------------


def write_summary_table(study_dir: Path, record: Mapping[str, Any]) -> str:
    """Write the derived per-segment TSV; return its sha256."""
    from ..primitives import atomic_write_text

    path = summary_table_path(study_dir, str(record["cell_id"]))
    text = summary_table_text(record)
    atomic_write_text(path, text)
    return sha256_bytes(text.encode())


def read_units(study_dir: Path, cell_id: str) -> list[dict[str, Any]]:
    """The pinned per-unit table of one cell, parsed."""
    path = study_dir / table_relpath(cell_id)
    if not path.is_file():
        raise WorkflowError(
            f"{table_relpath(cell_id)} does not exist — the cell's run pins it with an "
            "`artifact:` line, and a cell that cannot produce its table measured nothing"
        )
    try:
        return parse_table(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise WorkflowError(f"{table_relpath(cell_id)}: {exc}") from exc
