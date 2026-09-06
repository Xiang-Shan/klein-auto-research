"""The ``contribution`` capability — who proposed what, and what happened to it.

``ai_value.jsonl`` is an append-only ledger of proposals, decisions, rejections
and errors: one line per event, each naming its subject (a ``<study>#Hn``, a run
id, an artifact), its origin (``ai`` or ``human``), the actor, the decision, and
— when the decision was ``accepted`` — the HUMAN who accepted it.  Every line's
hash is sealed into the generation chain the moment it is written, so the file
and the chain are two witnesses to one record.

Three properties are the whole point, and each closes a way of overstating what
an agent contributed:

**Coverage includes rejections.**  A ledger that records only the accepted
proposals is a highlight reel.  The family checks every slate row and every
hypothesis admission against the ledger's subjects, and a subject with no line
is an integrity FAIL — the denominator is the work, not the wins.

**Agent acceptance never becomes human acceptance.**  A row with
``decision: accepted`` and ``human_acceptor: null`` is counted as
``agent_accepted`` and reported as such.  It stays in the ledger, it is not an
error, and it is never quietly promoted.

**The ledger is attribution, not causation.**  The capability outcome is
``descriptive`` unless ``parity.yaml`` cites a matched ablation study, in which
case it is ``ablation-cited`` — and even then the outcome names the citation
rather than asserting the effect.  "Causal AI value requires a matched
frozen-2.0 ablation; the ledger establishes recorded attribution and outcomes."
Recorded activity is also not all activity: work in scratch copies,
other checkouts and chat transcripts is invisible here, and partial transcripts
earn partial attribution.

``joined`` is imported from :mod:`kleinlib.generation.expert` — the package's
generic "event type → (event, object)" join, which lives in the first capability
module that needed it.  Reading it there rather than re-implementing it keeps
one join in the package.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..errors import WorkflowError
from ..primitives import canonical_json, sha256_bytes
from .envelope import GENERATION_SCHEMA
from .expert import joined
from .ledger import read_object
from .registry import Capability
from .verify import Check

if TYPE_CHECKING:  # pragma: no cover - types only
    from .registry import FamilyContext

__all__ = [
    "DECISIONS",
    "KINDS",
    "LEDGER_NAME",
    "ORIGINS",
    "RECORD_TYPE",
    "CAPABILITY",
    "build_record",
    "contribution_family",
    "ledger_path",
    "line_bytes",
    "read_lines",
    "record_object",
    "record_problems",
]

CAPABILITY_NAME = "contribution"

#: The human artifact.  Study root: the ledger is meant to be read alongside
#: `program.md`, and its lines are what SYNTHESIZE cites for attribution.
LEDGER_NAME = "ai_value.jsonl"

RECORD_TYPE = "contribution_recorded"

#: What a line records.  A rejection and an error are first-class events: a
#: ledger without them cannot support any attribution claim at all.
KINDS: tuple[str, ...] = ("proposal", "decision", "rejection", "error")

ORIGINS: tuple[str, ...] = ("ai", "human")

DECISIONS: tuple[str, ...] = ("accepted", "rejected", "deferred")

#: The key order every line is written in — canonical, so the file reads down
#: the page and the hash is a function of the content, not of the dict order.
LINE_KEY_ORDER: tuple[str, ...] = (
    "schema",
    "study",
    "sequence",
    "kind",
    "subject",
    "origin",
    "actor",
    "decision",
    "human_acceptor",
    "implementation_ref",
    "refs",
    "outcome",
    "cost",
    "transcript_hash",
)


def ledger_path(study_dir: Path) -> Path:
    return study_dir / LEDGER_NAME


def line_bytes(record: Mapping[str, Any]) -> bytes:
    """The exact bytes one ledger line occupies, hash included."""
    return (canonical_json(dict(record)) + "\n").encode()


def read_lines(study_dir: Path) -> list[dict[str, Any]]:
    """Every ledger line, in file order.  A malformed line is a hard error."""
    path = ledger_path(study_dir)
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"{LEDGER_NAME} line {number} is not JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise WorkflowError(f"{LEDGER_NAME} line {number} is not an object")
        records.append(value)
    return records


def build_record(
    *,
    study: str,
    sequence: int,
    kind: str,
    subject: str,
    origin: str,
    actor: str,
    decision: str | None,
    human_acceptor: str | None,
    implementation_ref: str | None,
    refs: Sequence[str],
    outcome: str | None,
    cost: str | None,
    transcript_hash: str | None,
) -> dict[str, Any]:
    """One ledger line, in canonical key order and free of any clock.

    No timestamp: the envelope of the ``contribution_recorded`` event carries
    ``created_at``, and a second clock in the line would make the same
    contribution hash differently on a replay.
    """
    record = {
        "schema": GENERATION_SCHEMA,
        "study": study,
        "sequence": int(sequence),
        "kind": kind,
        "subject": subject,
        "origin": origin,
        "actor": actor,
        "decision": decision,
        "human_acceptor": human_acceptor,
        "implementation_ref": implementation_ref,
        "refs": [str(ref) for ref in refs],
        "outcome": outcome,
        "cost": cost,
        "transcript_hash": transcript_hash,
    }
    return {key: record[key] for key in LINE_KEY_ORDER}


def record_object(*, study: str, sequence: int, line_sha256: str, record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "contribution_record",
        "study": study,
        "sequence": int(sequence),
        "line_sha256": line_sha256,
        "record": dict(record),
    }


def record_problems(
    *,
    kind: str,
    subject: str,
    origin: str,
    actor: str,
    decision: str | None,
    human_acceptor: str | None,
) -> list[str]:
    """Why this line cannot be recorded as typed."""
    problems: list[str] = []
    if kind not in KINDS:
        problems.append(f"--kind must be one of {', '.join(KINDS)}, got {kind!r}")
    if not subject.strip():
        problems.append("--subject is required (a <study>#Hn, an E####, or an artifact path)")
    if origin not in ORIGINS:
        problems.append(f"--origin must be one of {', '.join(ORIGINS)}, got {origin!r}")
    if not actor.strip():
        problems.append("--actor is required (testimony, never authenticated)")
    if decision is not None and decision not in DECISIONS:
        problems.append(f"--decision must be one of {', '.join(DECISIONS)}, got {decision!r}")
    if kind == "decision" and decision is None:
        problems.append("a `decision` line records what was decided; pass --decision")
    if kind == "rejection" and decision not in (None, "rejected"):
        problems.append("a `rejection` line's decision is `rejected`")
    if human_acceptor is not None and decision != "accepted":
        problems.append(
            "--human-acceptor names who ACCEPTED; it belongs only on --decision accepted"
        )
    return problems


# --------------------------------------------------------------------------
# the verify family
# --------------------------------------------------------------------------

LEDGER_CHECK = "contribution ledger"
COVERAGE_CHECK = "contribution coverage"


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


def _warn(name: str, detail: str) -> Check:
    return Check(name, "WARN", detail)


def _pass(name: str, detail: str) -> Check:
    return Check(name, "PASS", detail)


def contribution_family(ctx: FamilyContext) -> tuple[list[Check], dict[str, Any]]:
    """The ``contribution`` family: the two witnesses agree, and cover the work."""
    events = joined(ctx.study_dir, ctx.events, RECORD_TYPE)
    try:
        lines = read_lines(ctx.study_dir)
    except WorkflowError as exc:
        return [_fail(LEDGER_CHECK, str(exc))], {
            "integrity": "FAIL",
            "outcome": "descriptive",
            "coverage": None,
            "agent_accepted": 0,
        }

    checks: list[Check] = []
    checks += _witness_checks(events, lines)
    subjects = {str(record.get("subject")) for record in lines}
    coverage_checks, coverage = _coverage_checks(ctx, subjects)
    checks += coverage_checks

    agent_accepted = sum(
        1
        for record in lines
        if record.get("decision") == "accepted" and record.get("human_acceptor") in (None, "")
    )
    if agent_accepted:
        checks.append(
            _warn(
                LEDGER_CHECK,
                f"{agent_accepted} accepted row(s) carry no human_acceptor — recorded as "
                "agent-accepted; agent acceptance never becomes human acceptance",
            )
        )
    integrity = "FAIL" if any(check.status == "FAIL" for check in checks) else "PASS"
    return checks, {
        "integrity": integrity,
        "outcome": _outcome(ctx),
        "coverage": coverage,
        "agent_accepted": agent_accepted,
    }


def _witness_checks(
    events: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    lines: Sequence[Mapping[str, Any]],
) -> list[Check]:
    """The file and the chain are the same list, in the same order."""
    if not events and not lines:
        return [
            _warn(
                LEDGER_CHECK,
                "the contribution capability is declared and no line has been recorded yet — "
                "`klein generation contribution record` writes one",
            )
        ]
    problems: list[str] = []
    if len(events) != len(lines):
        problems.append(
            f"{len(lines)} ledger line(s) against {len(events)} recorded event(s) — a line "
            "without an event was never notarized, and an event without its line lost its "
            "evidence"
        )
    for index, (event, obj) in enumerate(events):
        if index >= len(lines):
            problems.append(f"{event.get('id')} has no line {index + 1} in {LEDGER_NAME}")
            continue
        actual = sha256_bytes(line_bytes(lines[index]))
        if actual != obj.get("line_sha256"):
            problems.append(
                f"{LEDGER_NAME} line {index + 1} is {actual[:12]}… but {event.get('id')} "
                f"sealed {str(obj.get('line_sha256'))[:12]}… — the ledger is append-only"
            )
        elif int(obj.get("sequence") or 0) != index + 1:
            problems.append(
                f"{event.get('id')} records sequence {obj.get('sequence')} at file position "
                f"{index + 1}: the order is part of the record"
            )
    if problems:
        return [_fail(LEDGER_CHECK, "; ".join(problems[:6]))]
    return [
        _pass(
            LEDGER_CHECK,
            f"{len(lines)} ledger line(s); every line's hash matches the event that sealed it, "
            "in order",
        )
    ]


def _coverage_checks(ctx: FamilyContext, subjects: set[str]) -> tuple[list[Check], float | None]:
    """Every slate row and every admitted hypothesis appears in the ledger."""
    expected = sorted(_slate_ids(ctx) | _admitted_hypotheses(ctx))
    if not expected:
        return [], None
    missing = [name for name in expected if name not in subjects]
    coverage = (len(expected) - len(missing)) / len(expected)
    if missing:
        return (
            [
                _fail(
                    COVERAGE_CHECK,
                    f"coverage {coverage:.12g}: no ledger line names "
                    + ", ".join(missing[:8])
                    + " — every proposal and decision is recorded, rejections included",
                )
            ],
            coverage,
        )
    return (
        [_pass(COVERAGE_CHECK, f"coverage 1: all {len(expected)} subject(s) appear in the ledger")],
        1.0,
    )


def _slate_ids(ctx: FamilyContext) -> set[str]:
    """Every ``<study>#Hn`` ever locked — withdrawn rows included."""
    from . import slate

    ids: set[str] = set()
    for version in slate.slate_versions(ctx.study_dir, ctx.events):
        for row in version["object"].get("rows") or ():
            if isinstance(row, Mapping) and isinstance(row.get("id"), str):
                ids.add(row["id"])
    return ids


def _admitted_hypotheses(ctx: FamilyContext) -> set[str]:
    """Every hypothesis id an admission receipt named, admitted or refused."""
    ids: set[str] = set()
    for receipt in ctx.receipts:
        try:
            obj = read_object(ctx.study_dir, receipt.sha)
        except WorkflowError:  # pragma: no cover - the orphan family catches this
            continue
        intended = obj.get("intended_action")
        named = intended.get("hypothesis_id") if isinstance(intended, Mapping) else None
        if isinstance(named, str) and named:
            ids.add(named)
    return ids


def _outcome(ctx: FamilyContext) -> str:
    """``ablation-cited`` only when the parity lock names a matched ablation study."""
    from . import parity

    versions = parity.locks(ctx.study_dir, ctx.events)
    if not versions:
        return "descriptive"
    payload = versions[-1][1].get("payload")
    cited = payload.get("ablation_study") if isinstance(payload, Mapping) else None
    return "ablation-cited" if isinstance(cited, str) and cited.strip() else "descriptive"


CAPABILITY = Capability(
    name=CAPABILITY_NAME,
    verify_family=contribution_family,
)
