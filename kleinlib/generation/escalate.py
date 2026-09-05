"""The ``escalation`` capability — account for getting unstuck, without automating it.

A study that stalls is the moment the record is worth the least and the
temptation is worth the most.  The evidence has stopped moving, the deadline has
not, and every way out — retune the same method, reach for more data, ask
somebody, change the question — is available *and* deniable afterwards.  The
cheapest repair is the one nobody writes down: quietly relabel a fourth round of
the same tuning as "data leverage", or edit the threshold that declared the
stall in the first place.

``escalation_plan.yaml`` closes that door before it opens.  Locked into the
extension chain **at CONSULT, before the consult gate**, it freezes four things:

1. **Triggers** — the arithmetic that says a stall HAPPENED, reconstructed from
   the run manifests, never asserted in prose: ``consecutive_discards`` (the
   ``stop:`` rule's own counter, reused verbatim), ``headroom_closed`` (a track
   whose ``h < 1``), ``budget_exhausted`` (a phase past its registered
   ``max_experiments``).
2. **The ladder** — five rungs, in one fixed order: metric diagnosis → method
   family → data leverage → adjacent-field analogy → human expert.  Each is
   *considered* in order; skipping an inapplicable rung costs a written reason.
   ``stop`` is always available as a rung, because stopping is a decision and
   not a failure to decide.
3. **Budgets** — unit-bearing vectors (compute, person-time, money, samples), so
   "this cost more than we said" is arithmetic rather than an impression.
4. **Terminal actions** — ``stop`` and, when the question itself has to change,
   ``pivot``: a linked successor study carrying both contract hashes and the
   exposure it inherits.

Every escalation is a ``<study>#Dn`` decision receipt filed BEFORE its action:
which trigger, which evidence, which rung, which lower rungs were skipped and
why, what concrete resource or assumption changes, the estimated cost, and the
condition that would close it.  ``escalate close`` adds the outcome and the
actual costs; an unavailable actual is recorded as ``unknown`` with evidence,
never omitted.

**Three things this establishes, and three it does not.**  It establishes that
the stall was declared before it was hit, that a rung was accounted for before
the next one was climbed, and that a pivot did not quietly rewrite the contract
it left behind (the old ``study.yaml`` hash is pinned and re-read from the
commit that filed the receipt).  It does NOT establish that the rung
label fits the work: whether a fourth round of tuning really is "data leverage"
is reviewable judgement, which is why every receipt must name the concrete
changed resource or assumption for a referee to read.  It does not evaluate a
``next_condition``, which is prose.  And it does not restore blindness: a
successor study id is a new contract, not a new set of eyes — everything the
predecessor saw is listed in ``inherited_exposure`` and stays seen.

**The CLI neither chooses a rung nor launches, schedules, or retries work.**  It
reconstructs counts, refuses an admission while a declared trigger stands
undischarged, and does arithmetic on the rows the driver wrote.

Registered, not wired in: this module exports one
:class:`~kleinlib.generation.registry.Capability` and the spine finds it through
:data:`kleinlib.generation.capabilities.MODULES`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..contract import normalize_tracks
from ..decision import _headroom_context, _incumbent, _seed_external_incumbent
from ..errors import WorkflowError
from ..manifest import load_manifests
from ..primitives import sha256_bytes, sha256_file
from ..stop import consecutive_discards
from ..transaction import git_blob, relative
from .chronology import (
    gate_events,
    introducing_commit,
    is_ancestor,
    read_core_events,
    run_started_events,
    study_event_commit,
)
from .envelope import GENERATION_SCHEMA
from .ledger import read_object
from .registry import Capability, FamilyContext
from .verify import Check

__all__ = [
    "BUDGET_UNITS",
    "CAPABILITY",
    "CAPABILITY_NAME",
    "CLOSE_TYPE",
    "EXPOSURE_KINDS",
    "EXTEND_BUDGET",
    "LOCK_TYPE",
    "PIVOT_TYPE",
    "PLAN_NAME",
    "RECORD_TYPE",
    "RUNGS",
    "STOP_RUNG",
    "TERMINAL_ACTIONS",
    "TRIGGER_KINDS",
    "Decision",
    "Trip",
    "accounted_rungs",
    "close_object",
    "committed_contract_sha",
    "cost_problems",
    "decision_object",
    "decisions",
    "episodes",
    "handed_ids",
    "inherited_exposure",
    "lock_object",
    "locks",
    "next_decision_number",
    "next_episode",
    "parse_plan",
    "pivot_object",
    "pivots",
    "plan_document",
    "plan_path",
    "plan_problems",
    "resolve_predecessor",
    "rung_problems",
    "trips",
    "trips_at",
]

CAPABILITY_NAME = "escalation"

#: The human artifact.  Study root, not ``generation/``: the plan is meant to be
#: READ — at CONSULT, when the stall arrives, and by the referee afterwards.
PLAN_NAME = "escalation_plan.yaml"

LOCK_TYPE = "escalation_locked"
RECORD_TYPE = "escalation_recorded"
CLOSE_TYPE = "escalation_closed"
PIVOT_TYPE = "pivot_recorded"

#: The ladder, in the one order this layer fixes.  Cheap and local first, expensive
#: and external last; a rung is CONSIDERED in order, never required to be taken.
RUNGS: tuple[str, ...] = (
    "metric_diagnosis",
    "method_family",
    "data_leverage",
    "adjacent_field_analogy",
    "human_expert",
)

#: Not a rung of the ladder — the option standing beside every rung of it.
STOP_RUNG = "stop"

#: What the arithmetic can say happened.  Every one is reconstructed from the
#: manifests, the contract and the state; none is asserted by a receipt.
TRIGGER_KINDS: tuple[str, ...] = (
    "consecutive_discards",
    "headroom_closed",
    "budget_exhausted",
)

#: The cost vector.  All four units are always present: a missing unit reads as
#: zero, and an unrecorded cost is not a zero cost — say ``unknown`` instead.
BUDGET_UNITS: tuple[str, ...] = ("compute", "person_time", "money", "samples")

#: How an escalation episode can end.
TERMINAL_ACTIONS: tuple[str, ...] = ("stop", "pivot")

#: What a successor inherits and can never un-see.
EXPOSURE_KINDS: tuple[str, ...] = ("sealed", "held-out", "scouted")

#: The one ``considered_action`` token the arithmetic reads: a budget may only be
#: exceeded after a receipt that said so first.
EXTEND_BUDGET = "extend-budget"

#: A decision receipt's lifecycle.  ``stopped`` is what a CLOSED decision at the
#: ``stop`` rung becomes — the episode ended on purpose rather than ran out.
STATUSES: tuple[str, ...] = ("open", "closed", "stopped")

_TRIGGER_ID_RE = re.compile(r"^T[0-9]+$")
_SCOPES: tuple[str, ...] = ("track", "phase", "study")
_UNKNOWN = "unknown"


# --------------------------------------------------------------------------
# the plan document
# --------------------------------------------------------------------------


def plan_path(study_dir: Path) -> Path:
    return study_dir / PLAN_NAME


def parse_plan(path: Path) -> dict[str, Any]:
    """The plan as a plain, hashable mapping."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowError(f"could not read {PLAN_NAME}: {exc}") from exc
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WorkflowError(f"{PLAN_NAME}: invalid YAML: {exc}") from exc
    if not isinstance(value, Mapping):
        raise WorkflowError(f"{PLAN_NAME} must contain a top-level mapping")
    return {str(key): item for key, item in value.items()}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _listing(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _phase_ids(contract: Mapping[str, Any]) -> list[str]:
    return [
        str(phase["id"])
        for phase in contract.get("phases") or []
        if isinstance(phase, Mapping) and "id" in phase
    ]


def _phase_limit(contract: Mapping[str, Any], phase_id: str) -> int | None:
    for phase in contract.get("phases") or []:
        if isinstance(phase, Mapping) and str(phase.get("id")) == phase_id:
            return _positive_int(phase.get("max_experiments"))
    return None


def _trigger_problems(contract: Mapping[str, Any], triggers: Any) -> list[str]:
    if not _listing(triggers) or not triggers:
        return ["triggers must be a non-empty list — a plan with no trigger declares no stall"]
    problems: list[str] = []
    seen: set[str] = set()
    tracks = set(normalize_tracks(contract))
    phases = set(_phase_ids(contract))
    for index, trigger in enumerate(triggers, start=1):
        label = f"triggers[{index}]"
        if not isinstance(trigger, Mapping):
            problems.append(f"{label} must be a mapping")
            continue
        trigger_id = trigger.get("id")
        if not _text(trigger_id) or not _TRIGGER_ID_RE.fullmatch(str(trigger_id)):
            problems.append(f"{label}.id must look like T1, T2, … (got {trigger_id!r})")
        elif str(trigger_id) in seen:
            problems.append(f"{label}.id {trigger_id!r} is used twice")
        else:
            seen.add(str(trigger_id))
        kind = trigger.get("kind")
        if kind not in TRIGGER_KINDS:
            problems.append(
                f"{label}.kind must be one of {', '.join(TRIGGER_KINDS)} (got {kind!r})"
            )
            continue
        if kind == "consecutive_discards":
            if _positive_int(trigger.get("max")) is None:
                problems.append(f"{label}.max must be a positive integer")
            scope = trigger.get("scope", "track")
            if scope not in _SCOPES:
                problems.append(f"{label}.scope must be one of {', '.join(_SCOPES)}")
            track = trigger.get("track")
            if track is not None and str(track) not in tracks:
                problems.append(
                    f"{label}.track {track!r} is not declared in study.yaml "
                    f"(declared: {', '.join(sorted(tracks)) or 'none'})"
                )
        elif kind == "budget_exhausted":
            phase = trigger.get("phase")
            if not _text(phase) or str(phase) not in phases:
                problems.append(
                    f"{label}.phase must name a declared phase "
                    f"({', '.join(sorted(phases)) or 'none'}); got {phase!r}"
                )
            elif _phase_limit(contract, str(phase)) is None:
                problems.append(f"{label}.phase {phase!r} declares no positive max_experiments")
    return problems


def _budget_problems(budgets: Any) -> list[str]:
    if not isinstance(budgets, Mapping):
        return [
            "budgets must be a mapping over " + ", ".join(BUDGET_UNITS) + " — a budget "
            "without units is a number nobody can exceed"
        ]
    problems: list[str] = []
    for unit in BUDGET_UNITS:
        if unit not in budgets:
            problems.append(f"budgets.{unit} is required (use {_UNKNOWN} when there is no cap)")
            continue
        value = budgets[unit]
        if value == _UNKNOWN:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            problems.append(
                f"budgets.{unit} must be a non-negative number or {_UNKNOWN!r} (got {value!r})"
            )
    extra = [str(key) for key in budgets if str(key) not in BUDGET_UNITS]
    if extra:
        problems.append(
            "budgets carries unknown unit(s) " + ", ".join(sorted(extra)) + "; the vector is "
            + ", ".join(BUDGET_UNITS)
        )
    return problems


def plan_problems(
    contract: Mapping[str, Any], doc: Mapping[str, Any], *, study: str
) -> list[str]:
    """Everything ``escalate lock`` refuses on, in one list."""
    problems: list[str] = []
    if doc.get("type") != "escalation-plan":
        problems.append(f"type must be 'escalation-plan' (got {doc.get('type')!r})")
    if str(doc.get("study")) != study:
        problems.append(f"study must be {study!r} (got {doc.get('study')!r})")
    problems.extend(_trigger_problems(contract, doc.get("triggers")))

    window = doc.get("evidence_window")
    if not isinstance(window, Mapping) or _positive_int(window.get("runs")) is None:
        problems.append(
            "evidence_window.runs must be a positive integer — how many runs a decision "
            "is allowed to cover before it is stale"
        )

    rungs = doc.get("rungs")
    if not _listing(rungs) or [str(rung) for rung in rungs] != list(RUNGS):
        problems.append(
            "rungs must be exactly " + ", ".join(RUNGS) + " in that order — the ladder is "
            "fixed so that skipping a rung is visible rather than definitional"
        )
    problems.extend(_budget_problems(doc.get("budgets")))

    terminal = doc.get("terminal_actions")
    if not _listing(terminal) or not terminal:
        problems.append("terminal_actions must be a non-empty list")
    else:
        unknown = [str(item) for item in terminal if str(item) not in TERMINAL_ACTIONS]
        if unknown:
            problems.append(
                "terminal_actions may only contain " + ", ".join(TERMINAL_ACTIONS)
                + f" (got {', '.join(unknown)})"
            )
        elif STOP_RUNG not in [str(item) for item in terminal]:
            problems.append(
                "terminal_actions must include 'stop' — stopping is always a recorded option"
            )
    return problems


# --------------------------------------------------------------------------
# reading the ledger
# --------------------------------------------------------------------------


def _objects(
    study_dir: Path, events: Sequence[Mapping[str, Any]], event_type: str
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    """``[(event, object)]`` for one event type, in chain order.

    An event whose object is unreadable is skipped here and reported by the
    spine's ``generation orphans`` family — one broken object must not blind
    every other check.
    """
    rows: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    for event in events:
        if event.get("type") != event_type:
            continue
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            rows.append((event, read_object(study_dir, sha)))
        except WorkflowError:
            continue
    return rows


def locks(
    study_dir: Path, events: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    """The ``escalation_locked`` events joined to their objects, in chain order."""
    return _objects(study_dir, events, LOCK_TYPE)


def plan_document(
    study_dir: Path, events: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    """The locked plan, or ``None`` when nothing is locked yet."""
    rows = locks(study_dir, events)
    if not rows:
        return None
    document = rows[0][1].get("document")
    return dict(document) if isinstance(document, Mapping) else None


def pivots(
    study_dir: Path, events: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    return _objects(study_dir, events, PIVOT_TYPE)


@dataclass(frozen=True)
class Decision:
    """One ``<study>#Dn`` receipt, joined to the close that terminated it."""

    id: str
    sha: str
    event_id: str
    sequence: int
    core_sequence: int
    episode: int
    recorded: dict[str, Any]
    closed: dict[str, Any] | None

    @property
    def status(self) -> str:
        if self.closed is None:
            return "open"
        return str(self.closed.get("status", "closed"))

    @property
    def rung(self) -> str:
        return str(self.recorded.get("rung"))

    @property
    def trigger_id(self) -> str:
        trigger = self.recorded.get("trigger")
        return str(trigger.get("id")) if isinstance(trigger, Mapping) else ""

    @property
    def reconstructed_count(self) -> Any:
        trigger = self.recorded.get("trigger")
        return trigger.get("reconstructed_count") if isinstance(trigger, Mapping) else None

    @property
    def skipped(self) -> dict[str, str]:
        rows = self.recorded.get("skipped_rungs")
        return {
            str(row.get("rung")): str(row.get("reason", ""))
            for row in (rows if _listing(rows) else [])
            if isinstance(row, Mapping)
        }


def _core_sequence(event: Mapping[str, Any]) -> int:
    anchor = event.get("core_anchor")
    value = anchor.get("sequence") if isinstance(anchor, Mapping) else None
    return int(value or 0)


def decisions(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> list[Decision]:
    """Every decision receipt in chain order, with its close folded in."""
    closes: dict[str, dict[str, Any]] = {}
    for _event, obj in _objects(study_dir, events, CLOSE_TYPE):
        identifier = obj.get("decision")
        if isinstance(identifier, str):
            closes[identifier] = obj
    rows: list[Decision] = []
    for event, obj in _objects(study_dir, events, RECORD_TYPE):
        identifier = str(obj.get("id"))
        sha = event.get("payload_sha256")
        rows.append(
            Decision(
                id=identifier,
                sha=str(sha),
                event_id=str(event.get("id")),
                sequence=int(event.get("sequence") or 0),
                core_sequence=_core_sequence(event),
                episode=int(obj.get("episode") or 0),
                recorded=obj,
                closed=closes.get(identifier),
            )
        )
    return rows


def next_decision_number(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> int:
    """One past the highest ``Dn`` ever allocated.  Ids are never recycled."""
    highest = 0
    for row in decisions(study_dir, events):
        if "#D" in row.id:
            tail = row.id.rsplit("#D", 1)[1]
            if tail.isdigit():
                highest = max(highest, int(tail))
    return highest + 1


def episodes(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """``{decision id: the episode it belongs to}``, recomputed from the chain.

    An episode is one stall, worked from whatever rung the driver started at
    until a decision in it is CLOSED.  The next record after that close opens the
    next episode — so the rung ladder is accounted per stall rather than once per
    study, and a second stall cannot inherit the first one's skipped reasons.
    """
    assignment: dict[str, int] = {}
    current = 0
    terminated = True
    open_ids: set[str] = set()
    for event in events:
        event_type = event.get("type")
        if event_type not in (RECORD_TYPE, CLOSE_TYPE):
            continue
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            obj = read_object(study_dir, sha)
        except WorkflowError:
            continue
        if event_type == RECORD_TYPE:
            if terminated:
                current += 1
                terminated = False
                open_ids = set()
            identifier = str(obj.get("id"))
            assignment[identifier] = current
            open_ids.add(identifier)
        elif str(obj.get("decision")) in open_ids:
            terminated = True
    return assignment


def next_episode(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> int:
    """The episode the NEXT ``escalate record`` joins (or opens)."""
    assignment = episodes(study_dir, events)
    if not assignment:
        return 1
    current = max(assignment.values())
    rows = {row.id: row for row in decisions(study_dir, events)}
    terminated = any(
        rows[identifier].closed is not None
        for identifier, episode in assignment.items()
        if episode == current and identifier in rows
    )
    return current + 1 if terminated else current


# --------------------------------------------------------------------------
# reconstructing the triggers
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Trip:
    """One trigger, reconstructed from the evidence rather than asserted."""

    trigger: str
    kind: str
    count: int
    threshold: int
    evidence: tuple[str, ...]
    anchor_sequence: int
    detail: str
    subject: str | None = None
    """The track a per-track trigger was resolved against, so the count that
    refused an admission is the count verification recomputes later."""

    @property
    def tripped(self) -> bool:
        return self.count >= self.threshold


def _in_scope(
    manifest: Mapping[str, Any], scope: str, *, track: str | None, phase: str | None
) -> bool:
    """Mirrors ``kleinlib.stop._in_scope`` — the counter's own scope filter.

    Duplicated rather than imported because ``stop.py`` is read-only here and
    the private helper is not part of its surface; ``test_generation_escalate``
    asserts the evidence list this produces is exactly as long as
    :func:`kleinlib.stop.consecutive_discards` says, so the two cannot drift.
    """
    if manifest.get("evaluation_kind", "development") != "development":
        return False
    if scope == "study":
        return True
    if scope == "phase":
        return str(manifest.get("phase")) == str(phase)
    return str(manifest.get("track")) == track


def _trailing_discards(
    manifests: Sequence[Mapping[str, Any]], scope: str, *, track: str | None, phase: str | None
) -> list[str]:
    """The experiment ids behind ``consecutive_discards``' number."""
    ids: list[str] = []
    for manifest in reversed(list(manifests)):
        if not _in_scope(manifest, scope, track=track, phase=phase):
            continue
        disposition = str(manifest.get("disposition"))
        if disposition == "crash":
            continue
        if disposition == "discard":
            ids.append(str(manifest.get("experiment")))
            continue
        break
    ids.reverse()
    return ids


def _sequence_of(started: Mapping[str, Mapping[str, Any]], run: str) -> int:
    event = started.get(run)
    return int(event.get("sequence") or 0) if isinstance(event, Mapping) else 0


def _anchor(started: Mapping[str, Mapping[str, Any]], evidence: Sequence[str]) -> int:
    return max((_sequence_of(started, run) for run in evidence), default=0)


def _consecutive_discards_trip(
    trigger: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
    manifests: Sequence[Mapping[str, Any]],
    started: Mapping[str, Mapping[str, Any]],
    track: str | None,
) -> Trip | None:
    scope = str(trigger.get("scope", "track"))
    declared = trigger.get("track")
    subject = str(declared) if declared is not None else track
    if scope == "track" and subject is None:
        return None  # a per-track trigger with no track in hand: not applicable here
    if scope == "track" and declared is not None and track is not None and str(declared) != track:
        return None  # a trigger bound to another track says nothing about this one
    phase = state.get("current_phase")
    phase = str(phase) if isinstance(phase, str) and phase else None
    count = consecutive_discards(
        manifests, scope=scope, track=subject or "", phase=phase
    )
    evidence = _trailing_discards(manifests, scope, track=subject, phase=phase)
    threshold = _positive_int(trigger.get("max")) or 1
    where = {"study": "the study", "phase": f"phase {phase}"}.get(scope, f"track {subject!r}")
    return Trip(
        trigger=str(trigger.get("id")),
        kind="consecutive_discards",
        count=count,
        threshold=threshold,
        evidence=tuple(evidence),
        anchor_sequence=_anchor(started, evidence),
        detail=f"{count} consecutive discards on {where} (registered limit {threshold})",
        subject=subject if scope == "track" else None,
    )


def _headroom_trip(
    trigger: Mapping[str, Any],
    *,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    manifests: Sequence[Mapping[str, Any]],
    started: Mapping[str, Mapping[str, Any]],
    track: str | None,
) -> Trip:
    """``h < 1`` on any track: no keep is arithmetically possible any more.

    The headroom itself is recomputed with the very helpers ``run-one`` enforces
    on (``kleinlib.decision``), so the trigger and the refusal can never
    disagree.  ``study_state.json``'s ``headroom`` block is read only as a
    fallback for a track whose incumbent the manifests no longer resolve — an
    acknowledgement records the h it was taken at.
    """
    tracks = normalize_tracks(contract)
    closed: list[str] = []
    evidence: list[str] = []
    for name, spec in tracks.items():
        if track is not None and name != track:
            continue
        incumbent = _seed_external_incumbent(spec, _incumbent(manifests, name))
        context = _headroom_context(spec, incumbent)
        h = context["h"] if context is not None else None
        if h is None:
            entry = state.get("headroom")
            entry = entry.get(name) if isinstance(entry, Mapping) else None
            value = entry.get("h") if isinstance(entry, Mapping) else None
            h = float(value) if isinstance(value, (int, float)) else None
        if h is None or h >= 1:
            continue
        closed.append(name)
        if isinstance(incumbent, Mapping) and incumbent.get("experiment"):
            evidence.append(str(incumbent["experiment"]))
    return Trip(
        trigger=str(trigger.get("id")),
        kind="headroom_closed",
        count=len(closed),
        threshold=1,
        evidence=tuple(evidence),
        anchor_sequence=_anchor(started, evidence),
        detail=(
            "headroom h < 1 on " + ", ".join(closed) + " — no keep is arithmetically "
            "possible on that frontier"
            if closed
            else "no track has h < 1"
        ),
        subject=track,
    )


def _budget_trip(
    trigger: Mapping[str, Any],
    *,
    contract: Mapping[str, Any],
    manifests: Sequence[Mapping[str, Any]],
    started: Mapping[str, Mapping[str, Any]],
) -> Trip:
    """A phase past its registered ``max_experiments``.

    Experiments, not seconds: ``budget_seconds`` is the core's own limit and is
    enforced by ``run-one``; counting it here would report a stall the notary
    had already refused.
    """
    phase = str(trigger.get("phase"))
    spent = [
        str(manifest.get("experiment"))
        for manifest in manifests
        if str(manifest.get("phase")) == phase
    ]
    threshold = _phase_limit(contract, phase) or 1
    return Trip(
        trigger=str(trigger.get("id")),
        kind="budget_exhausted",
        count=len(spent),
        threshold=threshold,
        evidence=tuple(spent),
        anchor_sequence=_anchor(started, spent),
        detail=(
            f"{len(spent)} experiment(s) recorded in phase {phase} against a registered "
            f"limit of {threshold}"
        ),
    )


def trips(
    plan: Mapping[str, Any],
    *,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    manifests: Sequence[Mapping[str, Any]],
    started: Mapping[str, Mapping[str, Any]],
    track: str | None = None,
) -> list[Trip]:
    """Reconstruct every applicable trigger from the evidence.

    ``track`` narrows the reconstruction to one track's frontier — what an
    admission on that track needs to know.  Passing ``None`` reconstructs
    everything the plan declared, which is what verification reads.
    """
    rows: list[Trip] = []
    for trigger in plan.get("triggers") or []:
        if not isinstance(trigger, Mapping):
            continue
        kind = trigger.get("kind")
        trip: Trip | None
        if kind == "consecutive_discards":
            trip = _consecutive_discards_trip(
                trigger, state=state, manifests=manifests, started=started, track=track
            )
        elif kind == "headroom_closed":
            trip = _headroom_trip(
                trigger,
                contract=contract,
                state=state,
                manifests=manifests,
                started=started,
                track=track,
            )
        elif kind == "budget_exhausted":
            trip = _budget_trip(
                trigger, contract=contract, manifests=manifests, started=started
            )
        else:
            trip = None
        if trip is not None:
            rows.append(trip)
    return rows


def trips_at(
    plan: Mapping[str, Any],
    *,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    manifests: Sequence[Mapping[str, Any]],
    started: Mapping[str, Mapping[str, Any]],
    core_sequence: int,
    track: str | None = None,
) -> list[Trip]:
    """The same reconstruction, as of a point in the core chain.

    Only the runs that had already STARTED by ``core_sequence`` are counted, so
    "was this trigger tripped when that receipt was written" is answered by the
    same arithmetic that answers "is it tripped now".  ``study_state.json`` is
    read as it is today (the layer keeps no history of it) — the approximation
    touches only ``current_phase`` and the headroom fallback, and is recorded
    here rather than hidden.
    """
    earlier = [
        manifest
        for manifest in manifests
        if _sequence_of(started, str(manifest.get("experiment"))) < core_sequence
    ]
    return trips(
        plan,
        contract=contract,
        state=state,
        manifests=earlier,
        started=started,
        track=track,
    )


def _discharging(
    trip: Trip, rows: Sequence[Decision], *, before: tuple[int, int] | None = None
) -> Decision | None:
    """The decision that answers *trip*, if one was filed after it tripped.

    "After" is core-anchor order, with the extension sequence as the tiebreaker:
    no generation verb writes a core event, so a decision and the admission that
    follows it commonly share one anchor and are separated only by the chain.
    """
    for row in rows:
        if row.trigger_id != trip.trigger or row.core_sequence <= trip.anchor_sequence:
            continue
        if before is not None:
            core, sequence = before
            if row.core_sequence > core or (row.core_sequence == core and row.sequence >= sequence):
                continue
        return row
    return None


# --------------------------------------------------------------------------
# the rungs and the costs
# --------------------------------------------------------------------------


def rung_problems(
    rung: str,
    skipped: Mapping[str, str],
    *,
    accounted: Sequence[str],
) -> list[str]:
    """A rung is reached only over rungs that were taken or excused.

    ``accounted`` is what earlier decisions IN THIS EPISODE already settled —
    the rungs they took, plus the rungs they skipped with a reason.  A rung
    skipped silently is the failure mode this exists for: an agent that retunes
    the same method four times and calls the fourth "data leverage".
    """
    problems: list[str] = []
    if rung == STOP_RUNG:
        return problems  # stopping is always available, from any position
    if rung not in RUNGS:
        return [f"unknown rung {rung!r}; the ladder is {', '.join((*RUNGS, STOP_RUNG))}"]
    for name, reason in skipped.items():
        if name not in RUNGS:
            problems.append(f"cannot skip unknown rung {name!r}")
        elif not reason.strip():
            problems.append(
                f"skipping {name!r} needs a recorded reason — an inapplicable rung is a "
                "judgement someone has to be able to disagree with"
            )
        elif name == rung:
            problems.append(f"rung {name!r} cannot be both taken and skipped")
        elif RUNGS.index(name) > RUNGS.index(rung):
            problems.append(
                f"{name!r} sits above {rung!r} on the ladder; only the rungs BELOW the one "
                "being taken have to be accounted for"
            )
    settled = {name for name in accounted} | {
        name for name, reason in skipped.items() if reason.strip()
    }
    missing = [name for name in RUNGS[: RUNGS.index(rung)] if name not in settled]
    if missing:
        problems.append(
            "unaccounted rung(s) " + ", ".join(missing) + f" below {rung!r} — each lower rung "
            "must have been taken in this episode or be skipped here with a reason"
        )
    return problems


def accounted_rungs(rows: Sequence[Decision], episode: int) -> list[str]:
    """The rungs an episode has already taken or excused."""
    settled: list[str] = []
    for row in rows:
        if row.episode != episode:
            continue
        if row.rung in RUNGS:
            settled.append(row.rung)
        settled.extend(name for name, reason in row.skipped.items() if reason.strip())
    return settled


def cost_problems(vector: Any, label: str) -> list[str]:
    """A cost vector carries all four units; an unavailable one says so."""
    if not isinstance(vector, Mapping):
        return [f"{label} must be a mapping over {', '.join(BUDGET_UNITS)}"]
    problems: list[str] = []
    for unit in BUDGET_UNITS:
        if unit not in vector:
            problems.append(
                f"{label}.{unit} is missing — an unrecorded cost is not a zero cost; "
                f"write {_UNKNOWN!r} when it cannot be measured"
            )
            continue
        value = vector[unit]
        if value == _UNKNOWN:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            problems.append(
                f"{label}.{unit} must be a non-negative number or {_UNKNOWN!r} (got {value!r})"
            )
    extra = [str(key) for key in vector if str(key) not in BUDGET_UNITS]
    if extra:
        problems.append(f"{label} carries unknown unit(s) " + ", ".join(sorted(extra)))
    return problems


def _unknown_units(vector: Mapping[str, Any]) -> list[str]:
    return [unit for unit in BUDGET_UNITS if vector.get(unit) == _UNKNOWN]


def _numeric(vector: Mapping[str, Any], unit: str) -> float:
    value = vector.get(unit)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _is_extend_budget(action: Any) -> bool:
    """Does this ``considered_action`` declare a budget extension?

    The token is read, not the sentence: ``extend-budget: two more GPU-days``
    counts, ``we may need more budget`` does not.  Anything the arithmetic reads
    has to be a token the driver typed on purpose.
    """
    if not isinstance(action, str):
        return False
    head = action.strip().split(":", 1)[0].split()[0] if action.strip() else ""
    return head == EXTEND_BUDGET


# --------------------------------------------------------------------------
# successors
# --------------------------------------------------------------------------

_SIDECAR_ID_RE = re.compile(r"#[HS][0-9]+")


def handed_ids(
    study_dir: Path, events: Sequence[Mapping[str, Any]], study: str
) -> list[str]:
    """Every ``<study>#Hn`` / ``<study>#Sn`` this study allocated, sorted.

    Scanned out of the objects rather than imported from the slate or surprise
    modules: a successor inherits whatever ids the predecessor issued, and this
    stays true for capabilities that ship after this one.
    """
    found: set[str] = set()
    for event in events:
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            text = (study_dir / "generation" / "objects" / f"{sha}.json").read_text("utf-8")
        except OSError:
            continue
        for match in _SIDECAR_ID_RE.finditer(text):
            start = match.start() - len(study)
            if start >= 0 and text[start : match.start()] == study:
                found.add(study + match.group())
    return sorted(found, key=lambda value: (value.split("#")[1][0], int(value.split("#")[1][1:])))


def inherited_exposure(
    study_dir: Path,
    events: Sequence[Mapping[str, Any]],
    *,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    study: str,
    extra: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """What the successor inherits and can never un-see.

    Three sources, all of them already on the record: a spent seal per track, the
    development partition every adaptive run has read, and any hypothesis whose
    outcome the scouting ledger had already observed.  ``extra`` carries what
    Klein cannot see — a field sample, a colleague who read the data.
    """
    rows: list[dict[str, Any]] = []
    access = state.get("final_holdout_access")
    if isinstance(access, Mapping):
        for track, entry in sorted(access.items()):
            count = entry.get("count") if isinstance(entry, Mapping) else None
            if isinstance(count, int) and count >= 1:
                rows.append({"kind": "sealed", "ref": f"track:{track}"})
    fingerprint = contract.get("data", {})
    if isinstance(fingerprint, Mapping) and fingerprint.get("split"):
        rows.append({"kind": "held-out", "ref": "data.split (the development partition)"})
    for identifier in handed_ids(study_dir, events, study):
        if "#S" in identifier:
            rows.append({"kind": "scouted", "ref": identifier})
    rows.extend({"kind": str(row.get("kind")), "ref": str(row.get("ref"))} for row in extra)
    return rows


def committed_contract_sha(repo: Path, study_dir: Path, commit: str) -> str | None:
    """sha256 of ``study.yaml`` AS IT WAS at *commit* — the pivot's anchor."""
    blob = git_blob(repo, commit, relative(repo, study_dir / "study.yaml"))
    return sha256_bytes(blob) if blob is not None else None


def resolve_predecessor(study_dir: Path, predecessor: str) -> Path | None:
    """The predecessor study's directory, when it lives beside this one."""
    parent = study_dir.parent
    if not parent.is_dir():
        return None
    candidate = parent / predecessor
    if (candidate / "generation" / "manifest.yaml").is_file():
        return candidate
    for entry in sorted(parent.iterdir()):
        path = entry / "generation" / "manifest.yaml"
        if not path.is_file():
            continue
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(document, Mapping) and str(document.get("study_id")) == predecessor:
            return entry
    return None


# --------------------------------------------------------------------------
# admission rules
# --------------------------------------------------------------------------


def _rule_a_tripped_trigger_needs_a_decision(ctx: Any) -> list[str]:
    """Once a declared trigger trips, the next candidate costs a receipt.

    Only ``run`` and ``--hypothesis`` admissions are refused: a metric
    diagnosis, a baseline reproduction, a repair or the sealed confirmation are
    not more of the same, and blocking them would make the ladder harder to
    climb than to ignore.  The refusal names the trigger and its evidence, so
    the receipt that discharges it can cite the same run ids.
    """
    from .ledger import read_events

    if ctx.action != "run" and not ctx.hypothesis:
        return []
    events = read_events(ctx.study_dir)
    plan = plan_document(ctx.study_dir, events)
    if plan is None:
        return [
            f"{PLAN_NAME} is not locked: `klein generation escalate lock` freezes the "
            "triggers, the ladder and the budgets at CONSULT — a stall rule written "
            "after the stall is a description of what you decided to do anyway"
        ]
    manifests = load_manifests(ctx.study_dir)
    started = run_started_events(read_core_events(ctx.study_dir))
    rows = decisions(ctx.study_dir, events)
    reasons: list[str] = []
    for trip in trips(
        plan,
        contract=ctx.contract,
        state=ctx.state,
        manifests=manifests,
        started=started,
        track=ctx.track,
    ):
        if not trip.tripped or _discharging(trip, rows) is not None:
            continue
        evidence = ", ".join(trip.evidence) or "no runs"
        reasons.append(
            f"trigger {trip.trigger} ({trip.kind}) is tripped: {trip.detail} [{evidence}] — "
            "record the escalation decision before the next candidate: "
            f"`klein generation escalate record --trigger {trip.trigger} --rung <rung> …`"
        )
    return reasons


# --------------------------------------------------------------------------
# the verify family
# --------------------------------------------------------------------------

PLAN_CHECK = "escalation plan"
TRIGGER_CHECK = "escalation triggers"
RECEIPT_CHECK = "escalation receipts"
COST_CHECK = "escalation costs"
PIVOT_CHECK = "escalation pivot"
PREDECESSOR_CHECK = "escalation predecessor"


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


def _pass(name: str, detail: str) -> Check:
    return Check(name, "PASS", detail)


def _warn(name: str, detail: str) -> Check:
    return Check(name, "WARN", detail)


def _lock_order_problems(
    ctx: FamilyContext, first: tuple[Mapping[str, Any], dict[str, Any]]
) -> list[str]:
    """The plan must precede the CONSULT gate by BOTH sequence and ancestry.

    The lock object's own ``late: true`` is not consulted.  That flag is what
    ``escalate lock`` wrote about itself when it saw a consult gate, and a
    hand-written ledger can set it to ``false`` as easily as to ``true``; the
    order is re-derived here from the two witnesses a writer does not control —
    the core anchor sequence, and whether the commit that filed the lock is an
    ancestor of the commit that filed the gate record.
    """
    gates = gate_events(ctx.core, "consult")
    if not gates:
        return []
    event, _obj = first
    anchor = event.get("core_anchor")
    anchor_sequence = anchor.get("sequence") if isinstance(anchor, Mapping) else None
    gate_sequence = gates[0].get("sequence")
    if not isinstance(anchor_sequence, int) or not isinstance(gate_sequence, int):
        return ["the escalation lock anchor or the consult gate record has no sequence"]
    problems: list[str] = []
    if anchor_sequence >= gate_sequence:
        problems.append(
            f"the plan is anchored at core sequence {anchor_sequence}, at or after the "
            f"consult gate record (sequence {gate_sequence}) — a stall rule registered "
            "once the study is running cannot constrain it"
        )
    repo = ctx.repo
    sha = event.get("payload_sha256")
    if repo is not None and isinstance(sha, str):
        lock_commit = introducing_commit(
            repo, relative(repo, ctx.study_dir / "generation" / "objects" / f"{sha}.json")
        )
        gate_hash = gates[0].get("event_hash")
        gate_commit = (
            study_event_commit(repo, ctx.study_dir, str(gate_hash))
            if isinstance(gate_hash, str)
            else None
        )
        if lock_commit is None:
            problems.append("the escalation lock object is not committed, so ancestry cannot be read")
        elif gate_commit is not None and not is_ancestor(repo, lock_commit, gate_commit):
            problems.append(
                f"the lock commit {lock_commit[:12]} is not an ancestor of the consult "
                f"gate commit {gate_commit[:12]}"
            )
    return problems


def _plan_checks(
    ctx: FamilyContext, rows: list[tuple[Mapping[str, Any], dict[str, Any]]], study: str
) -> list[Check]:
    if not rows:
        return [
            _fail(
                PLAN_CHECK,
                f"{PLAN_NAME} is not locked — `klein generation escalate lock` freezes the "
                "triggers, the ladder and the budgets before the CONSULT gate",
            )
        ]
    problems: list[str] = []
    if len(rows) > 1:
        problems.append(
            f"{len(rows)} escalation plans locked — the plan is locked once; changing a "
            "threshold after the evidence is what the lock exists to prevent"
        )
    event, first = rows[0]
    problems.extend(_lock_order_problems(ctx, rows[0]))
    path = plan_path(ctx.study_dir)
    if not path.is_file():
        problems.append(f"{PLAN_NAME} is missing but a lock exists")
    else:
        current = sha256_file(path)
        if current != first.get("plan_sha256"):
            problems.append(
                f"{PLAN_NAME} sha256 {current[:12]}… does not match the lock "
                f"({str(first.get('plan_sha256'))[:12]}…) — editing the threshold cannot "
                "discharge the stall it declared"
            )
    document = first.get("document")
    if isinstance(document, Mapping):
        problems.extend(plan_problems(ctx.contract, document, study=study))
    else:
        problems.append("the lock carries no plan document")
    if problems:
        return [_fail(PLAN_CHECK, "; ".join(problems[:8]))]
    triggers = len(document.get("triggers") or []) if isinstance(document, Mapping) else 0
    return [
        _pass(
            PLAN_CHECK,
            f"{PLAN_NAME} locked at core sequence {_core_sequence(event)}, before the "
            f"consult gate, unchanged since ({str(first.get('plan_sha256'))[:12]}…); "
            f"{triggers} trigger(s), five rungs, {len(BUDGET_UNITS)} budget units",
        )
    ]


def _trigger_checks(
    ctx: FamilyContext,
    plan: Mapping[str, Any] | None,
    rows: Sequence[Decision],
    manifests: Sequence[Mapping[str, Any]],
    started: Mapping[str, Mapping[str, Any]],
) -> list[Check]:
    """The trigger after the fact: counts recompute, and no candidate slipped past."""
    if plan is None:
        return []
    problems: list[str] = []

    for row in rows:
        matching = [
            trigger
            for trigger in plan.get("triggers") or []
            if isinstance(trigger, Mapping) and str(trigger.get("id")) == row.trigger_id
        ]
        if not matching:
            problems.append(
                f"{row.id} cites trigger {row.trigger_id!r}, which the locked plan does "
                "not declare"
            )
            continue
        declared = row.recorded.get("trigger")
        subject = declared.get("scope_subject") if isinstance(declared, Mapping) else None
        recomputed = trips_at(
            {"triggers": matching},
            contract=ctx.contract,
            state=ctx.state,
            manifests=manifests,
            started=started,
            core_sequence=row.core_sequence,
            track=str(subject) if isinstance(subject, str) else None,
        )
        if not recomputed:
            continue
        actual = recomputed[0].count
        if row.reconstructed_count != actual:
            problems.append(
                f"{row.id} records trigger.reconstructed_count "
                f"{row.reconstructed_count!r}; the manifests say {actual} at core "
                f"sequence {row.core_sequence}"
            )

    for receipt in ctx.receipts:
        if receipt.verdict != "admitted" or receipt.checkpoint != "run":
            continue
        for trip in trips_at(
            plan,
            contract=ctx.contract,
            state=ctx.state,
            manifests=manifests,
            started=started,
            core_sequence=receipt.core_sequence,
            track=receipt.track,
        ):
            if not trip.tripped:
                continue
            if _discharging(trip, rows, before=(receipt.core_sequence, receipt.sequence)) is None:
                problems.append(
                    f"admission {receipt.sha[:12]}… on track {receipt.track!r} was granted "
                    f"while trigger {trip.trigger} stood tripped ({trip.detail}) and no "
                    "decision receipt lay between them"
                )

    if problems:
        return [_fail(TRIGGER_CHECK, "; ".join(problems[:8]))]
    live = [
        trip
        for trip in trips(
            plan,
            contract=ctx.contract,
            state=ctx.state,
            manifests=manifests,
            started=started,
        )
        if trip.tripped
    ]
    undischarged = [trip for trip in live if _discharging(trip, rows) is None]
    if undischarged:
        return [
            _warn(
                TRIGGER_CHECK,
                "tripped and undischarged: "
                + "; ".join(f"{trip.trigger} — {trip.detail}" for trip in undischarged)
                + " — no run admission is granted until a decision is recorded",
            )
        ]
    return [
        _pass(
            TRIGGER_CHECK,
            f"{len(plan.get('triggers') or [])} trigger(s) reconstructed from the "
            f"manifests; {len(live)} tripped, each answered by a decision recorded after it",
        )
    ]


def _receipt_checks(
    ctx: FamilyContext,
    plan: Mapping[str, Any] | None,
    rows: Sequence[Decision],
    started: Mapping[str, Mapping[str, Any]],
) -> list[Check]:
    """Episodes, the rung ladder, and decisions that outlived their window."""
    if plan is None or not rows:
        return []
    problems: list[str] = []
    recomputed_episodes = episodes(ctx.study_dir, list(ctx.events))
    window = plan.get("evidence_window")
    limit = _positive_int(window.get("runs")) if isinstance(window, Mapping) else None

    for index, row in enumerate(rows):
        expected = recomputed_episodes.get(row.id)
        if expected is not None and row.episode != expected:
            problems.append(
                f"{row.id} records episode {row.episode}; the chain says episode {expected}"
            )
        problems.extend(
            f"{row.id}: {problem}"
            for problem in rung_problems(
                row.rung,
                row.skipped,
                accounted=accounted_rungs(rows[:index], expected or row.episode),
            )
        )
        if not _text(row.recorded.get("changed_resource_or_assumption")):
            problems.append(
                f"{row.id} names no changed resource or assumption — a rung label without "
                "one is the relabelling this record exists to expose"
            )
        if row.status == "open" and limit is not None:
            after = [
                run
                for run, event in started.items()
                if int(event.get("sequence") or 0) > row.core_sequence
            ]
            if len(after) > limit:
                problems.append(
                    f"{row.id} is still open after {len(after)} runs (evidence_window is "
                    f"{limit}) — a decision recorded after its action is not a prospective "
                    "decision; close it or record the next rung"
                )
    if problems:
        return [_fail(RECEIPT_CHECK, "; ".join(problems[:8]))]
    open_rows = [row for row in rows if row.status == "open"]
    return [
        _pass(
            RECEIPT_CHECK,
            f"{len(rows)} decision receipt(s) across "
            f"{len(set(recomputed_episodes.values()))} episode(s); every rung accounted for, "
            f"{len(open_rows)} open",
        )
    ]


def _cost_checks(plan: Mapping[str, Any] | None, rows: Sequence[Decision]) -> list[Check]:
    """The ladder's other half: closed means costed, and a budget is not exceeded quietly."""
    if plan is None or not rows:
        return []
    problems: list[str] = []
    for row in rows:
        problems.extend(
            f"{row.id}: {problem}"
            for problem in cost_problems(row.recorded.get("estimated_cost"), "estimated_cost")
        )
        if row.closed is None:
            continue
        actual = row.closed.get("actual_cost")
        problems.extend(
            f"{row.id}: {problem}" for problem in cost_problems(actual, "actual_cost")
        )
        if isinstance(actual, Mapping):
            unknown = _unknown_units(actual)
            if unknown and not _text(row.closed.get("cost_evidence")):
                problems.append(
                    f"{row.id} closes with {', '.join(unknown)} unknown and no "
                    "cost_evidence — an unavailable actual is recorded, not waved through"
                )

    budgets = plan.get("budgets")
    if isinstance(budgets, Mapping):
        for unit in BUDGET_UNITS:
            cap = budgets.get(unit)
            if not isinstance(cap, (int, float)) or isinstance(cap, bool):
                continue
            spent = 0.0
            for row in rows:
                vector = row.closed.get("actual_cost") if row.closed else None
                if not isinstance(vector, Mapping):
                    vector = row.recorded.get("estimated_cost")
                if isinstance(vector, Mapping):
                    spent += _numeric(vector, unit)
                if spent <= cap:
                    continue
                extended = any(
                    _is_extend_budget(earlier.recorded.get("considered_action"))
                    and (
                        earlier.core_sequence < row.core_sequence
                        or (
                            earlier.core_sequence == row.core_sequence
                            and earlier.sequence <= row.sequence
                        )
                    )
                    for earlier in rows
                )
                if not extended:
                    problems.append(
                        f"{unit} budget {cap:g} exceeded at {row.id} ({spent:g}) with no "
                        f"earlier decision whose considered_action is '{EXTEND_BUDGET}'"
                    )
                break
    if problems:
        return [_fail(COST_CHECK, "; ".join(problems[:8]))]
    closed = [row for row in rows if row.closed is not None]
    return [
        _pass(
            COST_CHECK,
            f"{len(rows)} estimate(s) and {len(closed)} actual(s) carry all "
            f"{len(BUDGET_UNITS)} units; no budget was passed without a recorded extension",
        )
    ]


def _pivot_checks(
    ctx: FamilyContext,
    rows: Sequence[Decision],
    pivot_rows: list[tuple[Mapping[str, Any], dict[str, Any]]],
) -> list[Check]:
    """The contract a pivot left behind is the one it recorded."""
    if not pivot_rows:
        return []
    problems: list[str] = []
    identifiers = {row.id for row in rows}
    for event, obj in pivot_rows:
        decision = str(obj.get("decision"))
        if decision not in identifiers:
            problems.append(f"pivot names {decision!r}, which is not a decision receipt")
        if not _text(obj.get("successor_study")):
            problems.append(f"pivot on {decision} names no successor study")
        repo = ctx.repo
        sha = event.get("payload_sha256")
        if repo is None or not isinstance(sha, str):
            continue
        commit = introducing_commit(
            repo, relative(repo, ctx.study_dir / "generation" / "objects" / f"{sha}.json")
        )
        if commit is None:
            problems.append(f"the pivot object for {decision} is not committed")
            continue
        actual = committed_contract_sha(repo, ctx.study_dir, commit)
        if actual is None:
            problems.append(f"study.yaml is unreadable at the pivot commit {commit[:12]}")
        elif actual != obj.get("old_contract_sha256"):
            problems.append(
                f"pivot on {decision} pins old_contract_sha256 "
                f"{str(obj.get('old_contract_sha256'))[:12]}…, but study.yaml at its own "
                f"commit {commit[:12]} hashes to {actual[:12]}… — the predecessor's "
                "contract was rewritten"
            )
    if problems:
        return [_fail(PIVOT_CHECK, "; ".join(problems[:8]))]
    successors = ", ".join(str(obj.get("successor_study")) for _event, obj in pivot_rows)
    return [
        _pass(
            PIVOT_CHECK,
            f"{len(pivot_rows)} pivot(s) to {successors}; both contract hashes pinned and "
            "the old one still hashes as recorded — a successor id restores no blindness",
        )
    ]


def _predecessor_checks(ctx: FamilyContext, study: str) -> list[Check]:
    """The successor's half of the link: the receipt that created it must exist."""
    predecessor = ctx.manifest.get("predecessor")
    if not isinstance(predecessor, Mapping):
        return [_pass(PREDECESSOR_CHECK, "this study declares no predecessor")]
    name = str(predecessor.get("study_id"))
    sha = predecessor.get("successor_receipt")
    if not isinstance(sha, str) or not sha.strip():
        return [
            _fail(
                PREDECESSOR_CHECK,
                f"the manifest names predecessor {name!r} with no successor_receipt — a "
                "successor cites the pivot receipt that created it "
                "(`klein generation init --predecessor <id> --successor-receipt <sha>`)",
            )
        ]
    directory = resolve_predecessor(ctx.study_dir, name)
    if directory is None:
        return [
            _warn(
                PREDECESSOR_CHECK,
                f"predecessor {name!r} is not resolvable from here, so the pivot receipt "
                f"{sha[:12]}… cannot be read — the link is recorded, not verified",
            )
        ]
    try:
        obj = read_object(directory, sha)
    except WorkflowError:
        return [
            _fail(
                PREDECESSOR_CHECK,
                f"predecessor {name!r} holds no object {sha[:12]}… — the receipt this "
                "study says created it does not exist",
            )
        ]
    if obj.get("kind") != "pivot" or str(obj.get("successor_study")) != study:
        return [
            _fail(
                PREDECESSOR_CHECK,
                f"object {sha[:12]}… in {name!r} is not a pivot naming {study!r} "
                f"(kind {obj.get('kind')!r}, successor {obj.get('successor_study')!r})",
            )
        ]
    exposure = obj.get("inherited_exposure")
    return [
        _pass(
            PREDECESSOR_CHECK,
            f"successor of {name!r} at receipt {sha[:12]}…, inheriting "
            f"{len(exposure) if _listing(exposure) else 0} exposure record(s) — a successor "
            "id restores no blindness",
        )
    ]


def _outcome(rows: Sequence[Decision], pivot_rows: Sequence[Any]) -> str:
    if pivot_rows:
        return "pivoted"
    if any(row.status == "stopped" for row in rows):
        return "stopped"
    return "escalated" if rows else "none"


def verify_family(ctx: FamilyContext) -> tuple[list[Check], dict[str, Any]]:
    """The ``escalation`` family: was getting unstuck accounted for, or narrated?"""
    from .manifest import study_id

    study = study_id(ctx.study_dir, ctx.contract)
    events = list(ctx.events)
    lock_rows = locks(ctx.study_dir, events)
    plan = plan_document(ctx.study_dir, events)
    rows = decisions(ctx.study_dir, events)
    pivot_rows = pivots(ctx.study_dir, events)
    manifests = load_manifests(ctx.study_dir)
    started = run_started_events(list(ctx.core))

    checks = _plan_checks(ctx, lock_rows, study)
    checks += _trigger_checks(ctx, plan, rows, manifests, started)
    checks += _receipt_checks(ctx, plan, rows, started)
    checks += _cost_checks(plan, rows)
    checks += _pivot_checks(ctx, rows, pivot_rows)
    checks += _predecessor_checks(ctx, study)

    integrity = "FAIL" if any(check.status == "FAIL" for check in checks) else "PASS"
    return checks, {
        "integrity": integrity,
        "outcome": _outcome(rows, pivot_rows),
        "episodes": len(set(episodes(ctx.study_dir, events).values())),
        "open": len([row for row in rows if row.status == "open"]),
    }


#: The registration.  Everything above is reachable only through this object.
CAPABILITY = Capability(
    name=CAPABILITY_NAME,
    admission_rules=(_rule_a_tripped_trigger_needs_a_decision,),
    verify_family=verify_family,
)


# --------------------------------------------------------------------------
# object builders (used by the CLI; kept here so the shapes live with the rules)
# --------------------------------------------------------------------------


def lock_object(
    *, study: str, document: Mapping[str, Any], plan_sha256: str, late: bool
) -> dict[str, Any]:
    """The lock: the plan VERBATIM, plus the hash of the bytes it came from."""
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "escalation_plan",
        "study": study,
        "plan_path": PLAN_NAME,
        "plan_sha256": plan_sha256,
        "document": {str(key): value for key, value in document.items()},
        "late": bool(late),
    }


def decision_object(
    *,
    study: str,
    identifier: str,
    episode: int,
    trip: Trip,
    rung: str,
    skipped: Mapping[str, str],
    considered_action: str,
    changed: str,
    rationale: str,
    estimated_cost: Mapping[str, Any],
    next_condition: str | None,
    successor_study: str | None,
    human_advice: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """One ``<study>#Dn`` decision, filed BEFORE the action it describes."""
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "escalation_decision",
        "study": study,
        "id": identifier,
        "episode": episode,
        "trigger": {
            "id": trip.trigger,
            "kind": trip.kind,
            "evidence": list(trip.evidence),
            "reconstructed_count": trip.count,
            "threshold": trip.threshold,
            "scope_subject": trip.subject,
        },
        "rung": rung,
        "skipped_rungs": [
            {"rung": name, "reason": reason} for name, reason in sorted(skipped.items())
        ],
        "considered_action": considered_action,
        "changed_resource_or_assumption": changed,
        "rationale": rationale,
        "status": "open",
        "estimated_cost": dict(estimated_cost),
        "actual_cost": None,
        "cost_evidence": None,
        "next_condition": next_condition,
        "successor_study": successor_study,
        "human_advice": dict(human_advice) if human_advice else None,
    }


def close_object(
    *,
    study: str,
    decision: str,
    status: str,
    actual_cost: Mapping[str, Any],
    cost_evidence: str | None,
    outcome: str,
) -> dict[str, Any]:
    """The close: what the escalation actually cost, and what it bought."""
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "escalation_close",
        "study": study,
        "decision": decision,
        "status": status,
        "actual_cost": dict(actual_cost),
        "cost_evidence": cost_evidence,
        "outcome": outcome,
    }


def pivot_object(
    *,
    study: str,
    decision: str,
    successor_study: str,
    old_contract_sha256: str,
    new_contract_sha256: str,
    exposure: Sequence[Mapping[str, Any]],
    ids: Sequence[str],
) -> dict[str, Any]:
    """The successor link: both contracts, everything already seen, every id issued."""
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "pivot",
        "study": study,
        "decision": decision,
        "successor_study": successor_study,
        "old_contract_sha256": old_contract_sha256,
        "new_contract_sha256": new_contract_sha256,
        "inherited_exposure": [dict(row) for row in exposure],
        "handed_ids": list(ids),
    }
