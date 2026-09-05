"""The ``premortem`` capability — a recorded red team, before the slate is final.

A slate is the driver's own list of candidates, and the driver is the last person
able to see what is wrong with it.  This capability records a REVIEW of a draft
slate — who reviewed it, what they were given, what they objected to — and the
driver's answer to each objection, so that a corrected slate is provably the
corrected one and an ignored mechanical defect provably blocks the work.

Three properties are worth stating outright, because each is a way a "red team"
usually turns into theatre:

**It never scores, ranks or selects.**  There is no quality score for an issue,
no ranking of reviewers, no tournament between candidates, and nothing here
chooses a row.  The capability records issues and responses and computes
arithmetic over them (is every issue answered? is every blocking mechanical
defect accepted, and did a NEW slate version follow?).  Selection judgement stays
where the phase ritual puts it: with the driver (``references/phase-ritual.md``).

**A blocking mechanical defect gates admission, and nothing else does.**  A
disagreement about substance is recorded as ``reject`` with a rationale — the
reviewer is not given a veto over the science.  A *mechanical* defect the
reviewer marked ``blocking`` (a denominator that omits failed batches, a metric
that cannot be computed on the stated partition) must be ``accept``ed, and the
acceptance must name the sha256 of a NEW slate version whose ancestry reaches the
draft that was reviewed.  Until then ``klein generation check --hypothesis`` is
refused, naming the issue ids.

**Independence is self-attested unless a receipt exists.**  ``reviewer.name`` is
testimony, like every other actor string in this layer.  A session receipt (a
file the driver points at, hashed into the record) raises the outcome from
``self-attested`` to ``receipted`` — and that is a statement about the RECORD,
never a certification that the review was independent, competent or read.  A
reviewer whose name equals the roster's ``referee`` FAILs: the proposal critic
may not be the closing referee (``references/referee-protocol.md``).

Registered, not wired in: this module exports one
:class:`~kleinlib.generation.registry.Capability` and the spine finds it through
:data:`kleinlib.generation.capabilities.MODULES`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ..errors import WorkflowError
from ..primitives import canonical_json, sha256_bytes, sha256_file
from ..transaction import git_blob, relative
from . import slate as _slate
from .admission import load_receipts
from .chronology import introducing_commit, run_started_events
from .envelope import GENERATION_SCHEMA
from .expert import roster_actor, same_actor
from .ledger import read_events, read_object
from .registry import Capability
from .verify import Check

if TYPE_CHECKING:  # pragma: no cover - types only
    from .admission import Context, Receipt
    from .registry import FamilyContext

__all__ = [
    "CAPABILITY",
    "CAPABILITY_NAME",
    "DISPOSITIONS",
    "ISSUE_ID_RE",
    "ISSUE_KINDS",
    "PREMORTEM_EVENTS",
    "RECORD_TYPE",
    "RESPOND_TYPE",
    "SEVERITIES",
    "build_record",
    "build_response",
    "evidence_marks",
    "hypothesis_receipts",
    "input_bundle",
    "is_late",
    "premortem_family",
    "premortem_path",
    "read_premortem_file",
    "record_problems",
    "records",
    "response_problems",
    "responses",
    "slate_ancestors",
]

CAPABILITY_NAME = "premortem"

RECORD_TYPE = "premortem_recorded"
RESPOND_TYPE = "premortem_responded"
PREMORTEM_EVENTS: tuple[str, ...] = (RECORD_TYPE, RESPOND_TYPE)

#: How badly the reviewer thinks the issue bites.  Only ``blocking`` gates
#: anything, and only in combination with ``mechanical``.
SEVERITIES: tuple[str, ...] = ("blocking", "major", "minor")

#: What KIND of objection it is.  A ``mechanical`` issue is one the record can
#: adjudicate — a denominator, a partition, a metric that cannot be computed as
#: written.  A ``scientific`` one is a judgement about the world, and the driver
#: may lawfully reject it with a rationale: forcing agreement would make the
#: reviewer the principal investigator.
ISSUE_KINDS: tuple[str, ...] = ("mechanical", "scientific")

#: What the driver may answer.  Every issue gets exactly one.
DISPOSITIONS: tuple[str, ...] = ("accept", "reject", "defer")

#: ``I1``, ``I2``, … — issue ids are local to one review.
ISSUE_ID_RE = re.compile(r"^I[1-9][0-9]*$")

#: Targets that are not a hypothesis id: the slate as a whole, or the study
#: design behind it.
NON_ROW_TARGETS: tuple[str, ...] = ("slate", "design")


# --------------------------------------------------------------------------
# the driver's file
# --------------------------------------------------------------------------


def premortem_path(study_dir: Path, phase: str) -> Path:
    """The driver's own file — study root, beside ``slates/``."""
    return study_dir / "premortem" / f"{phase}.yaml"


def read_premortem_file(study_dir: Path, phase: str) -> dict[str, Any]:
    path = premortem_path(study_dir, phase)
    if not path.is_file():
        raise WorkflowError(
            f"{path.relative_to(study_dir).as_posix()} does not exist — the reviewer's "
            "issues are authored first (`.claude/skills/klein/assets/premortem-template.yaml`)"
        )
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"could not read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{path.name} must contain a top-level mapping")
    return value


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


# --------------------------------------------------------------------------
# what is on the ledger
# --------------------------------------------------------------------------


def _joined(
    study_dir: Path,
    events: Sequence[Mapping[str, Any]],
    event_type: str,
    phase: str | None = None,
) -> list[dict[str, Any]]:
    """``[{event, sha, object}]`` for one event type, in chain order.

    An object that cannot be read is skipped here and reported by the spine's
    ``generation orphans`` family — one broken object must not blind the rest.
    """
    out: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != event_type:
            continue
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            obj = read_object(study_dir, sha)
        except WorkflowError:
            continue
        if phase is not None and str(obj.get("phase")) != phase:
            continue
        out.append({"event": dict(event), "sha": sha, "object": obj})
    return out


def records(
    study_dir: Path, events: Sequence[Mapping[str, Any]], phase: str | None = None
) -> list[dict[str, Any]]:
    """Every recorded review, oldest first."""
    return _joined(study_dir, events, RECORD_TYPE, phase)


def responses(
    study_dir: Path, events: Sequence[Mapping[str, Any]], phase: str | None = None
) -> list[dict[str, Any]]:
    """Every recorded response set, oldest first."""
    return _joined(study_dir, events, RESPOND_TYPE, phase)


def response_for(
    study_dir: Path, events: Sequence[Mapping[str, Any]], record: Mapping[str, Any]
) -> dict[str, Any] | None:
    """The response set that answers this record, or None while it is open."""
    wanted = str(record["event"].get("id"))
    for entry in responses(study_dir, events, str(record["object"].get("phase"))):
        if str(entry["object"].get("record_event")) == wanted:
            return entry
    return None


def open_record(
    study_dir: Path, events: Sequence[Mapping[str, Any]], phase: str
) -> dict[str, Any] | None:
    """A review of this phase that has been recorded and not yet answered."""
    for entry in records(study_dir, events, phase):
        if response_for(study_dir, events, entry) is None:
            return entry
    return None


# --------------------------------------------------------------------------
# slate ancestry — "a NEW version, descended from the one reviewed"
# --------------------------------------------------------------------------


def slate_ancestors(
    study_dir: Path, events: Sequence[Mapping[str, Any]], sha: str
) -> list[str]:
    """``sha`` plus every slate object sha it descends from, newest first.

    A slate version names its parent by EVENT id (``kleinlib.generation.slate``
    writes ``parent_ids: [<the previous lock's event id>]``), so the walk is over
    the extension chain rather than over object hashes.  A cycle cannot occur on
    an append-only chain; the ``seen`` set makes that structural rather than
    hopeful.
    """
    versions = _slate.slate_versions(study_dir, events)
    by_event = {str(entry["event"].get("id")): entry for entry in versions}
    by_sha = {entry["sha"]: entry for entry in versions}
    chain: list[str] = []
    seen: set[str] = set()
    current = by_sha.get(sha)
    while current is not None and current["sha"] not in seen:
        seen.add(current["sha"])
        chain.append(current["sha"])
        parents = current["event"].get("parent_ids") or []
        parent = by_event.get(str(parents[0])) if parents else None
        current = parent
    return chain


def _is_slate_object(
    study_dir: Path, events: Sequence[Mapping[str, Any]], sha: Any, phase: str
) -> bool:
    if not isinstance(sha, str):
        return False
    return any(entry["sha"] == sha for entry in _slate.slate_versions(study_dir, events, phase))


# --------------------------------------------------------------------------
# the input bundle
# --------------------------------------------------------------------------


def _bundle_digest(entries: Sequence[Sequence[Any]]) -> str:
    """The same shape the spine's surface digest uses: a hash of ``[[path, sha]]``."""
    return sha256_bytes(canonical_json([list(entry) for entry in entries]).encode())


def input_bundle(study_dir: Path, inputs: Sequence[str]) -> tuple[str, list[list[Any]]]:
    """``(digest, [[path, sha256|null], …])`` for the files AS ON DISK.

    A missing file hashes as null rather than raising: the record then says, on
    the record, that the reviewer was handed a path that was not there.
    """
    entries: list[list[Any]] = []
    for name in inputs:
        path = study_dir / str(name)
        entries.append([str(name), sha256_bytes(path.read_bytes()) if path.is_file() else None])
    return _bundle_digest(entries), entries


def input_bundle_at(
    repo: Path, study_dir: Path, inputs: Sequence[str], commit: str
) -> tuple[str, list[list[Any]]]:
    """The same digest, read out of a commit rather than the working tree."""
    entries: list[list[Any]] = []
    for name in inputs:
        blob = git_blob(repo, commit, relative(repo, study_dir / str(name)))
        entries.append([str(name), sha256_bytes(blob) if blob is not None else None])
    return _bundle_digest(entries), entries


# --------------------------------------------------------------------------
# validation — the record
# --------------------------------------------------------------------------


def record_problems(
    payload: Mapping[str, Any],
    *,
    study: str,
    phase: str,
    study_dir: Path,
    events: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Everything wrong with an authored review, one line each."""
    problems: list[str] = []
    if payload.get("type") not in (None, "premortem"):
        problems.append(f"type is {payload.get('type')!r}, expected 'premortem'")
    declared = payload.get("study")
    if declared is not None and str(declared) != study:
        problems.append(f"study is {declared!r}, expected {study!r}")
    if str(payload.get("phase")) != phase:
        problems.append(f"phase is {payload.get('phase')!r}, expected {phase!r}")

    versions = _slate.slate_versions(study_dir, events, phase)
    reviewed = payload.get("slate_object")
    if not versions:
        problems.append(
            f"no slate is locked for phase {phase!r} — a pre-mortem reviews a DRAFT slate, "
            "so `klein generation slate lock` comes first"
        )
    elif not _is_slate_object(study_dir, events, reviewed, phase):
        problems.append(
            f"slate_object {str(reviewed)[:12]!r} is not a locked slate object of phase "
            f"{phase!r} (newest: {versions[-1]['sha'][:12]}…)"
        )
    elif reviewed != versions[-1]["sha"]:
        problems.append(
            f"slate_object names version {_version_of(versions, reviewed)} but version "
            f"{versions[-1]['object'].get('version')} is in force — a review of a "
            "superseded draft cannot correct the slate that will run"
        )

    problems.extend(_reviewer_problems(payload.get("reviewer")))
    problems.extend(_input_problems(payload.get("inputs"), study_dir=study_dir, phase=phase))

    live = _live_row_ids(versions, reviewed)
    problems.extend(_issue_problems(payload.get("issues"), live=live))

    if _rows(payload.get("responses")):
        problems.append(
            "responses is not empty — a review is recorded BEFORE it is answered; "
            "write the dispositions afterwards and record them with "
            "`klein generation premortem respond`"
        )
    return problems


def _version_of(versions: Sequence[Mapping[str, Any]], sha: Any) -> Any:
    for entry in versions:
        if entry["sha"] == sha:
            return entry["object"].get("version")
    return "?"


def _live_row_ids(versions: Sequence[Mapping[str, Any]], sha: Any) -> set[str]:
    for entry in versions:
        if entry["sha"] == sha:
            rows = entry["object"].get("rows")
            return {
                str(row.get("id"))
                for row in (rows if isinstance(rows, list) else [])
                if isinstance(row, Mapping) and isinstance(row.get("id"), str)
            }
    return set()


def _reviewer_problems(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["reviewer must be a mapping {name, model, tool, session_receipt}"]
    problems: list[str] = []
    name = value.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("reviewer.name is required — testimony, and it is what independence reads")
    for key in ("model", "tool", "session_receipt"):
        item = value.get(key)
        if item is not None and not isinstance(item, str):
            problems.append(f"reviewer.{key} must be a string or null, got {item!r}")
    return problems


def _input_problems(value: Any, *, study_dir: Path, phase: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        return [
            "inputs must be a non-empty list of study-relative paths — what the reviewer "
            "was actually given"
        ]
    problems: list[str] = []
    seen: set[str] = set()
    for name in value:
        if name in seen:
            problems.append(f"inputs lists {name!r} twice")
        seen.add(name)
        if not (study_dir / name).is_file():
            problems.append(f"inputs names {name!r}, which is not a file in the study")
    wanted = f"slates/{phase}.yaml"
    if wanted not in seen:
        problems.append(
            f"inputs does not include {wanted!r} — the draft slate is the thing under review"
        )
    return problems


def _issue_problems(value: Any, *, live: set[str]) -> list[str]:
    """``id``, ``target``, ``severity``, ``kind`` and ``text`` are checked.

    Any FURTHER key the reviewer wrote — A3 §7's ``failure_story``,
    ``challenged_assumption``, ``source_or_counterexample``,
    ``discriminating_check`` — is copied into the record verbatim and never
    interpreted.  The schema is a floor on what a critique must say, not a
    ceiling; a structured issue that is specific and useless still passes it, and
    saying so is the protocol's job, not a check's.
    """
    rows = _rows(value)
    if not isinstance(value, list) or not rows or len(rows) != len(value):
        return ["issues must be a non-empty list of mappings"]
    problems: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        label = f"issue {index}"
        name = row.get("id")
        if not isinstance(name, str) or not ISSUE_ID_RE.match(name):
            problems.append(f"{label}: id is {name!r}, expected I1, I2, …")
        elif name in seen:
            problems.append(f"{label}: id {name!r} is used twice")
        else:
            seen.add(name)
        target = row.get("target")
        if not isinstance(target, str) or not target.strip():
            problems.append(
                f"{label}: target is required — a hypothesis id, 'slate' or 'design'"
            )
        elif "#H" in target and live and target not in live:
            problems.append(
                f"{label}: target {target!r} is not a live row of the slate being reviewed "
                f"({', '.join(sorted(live)) or 'no rows'})"
            )
        elif "#H" not in target and target not in NON_ROW_TARGETS:
            problems.append(
                f"{label}: target {target!r} is neither a hypothesis id nor one of "
                + ", ".join(NON_ROW_TARGETS)
            )
        if row.get("severity") not in SEVERITIES:
            problems.append(
                f"{label}: severity is {row.get('severity')!r}, expected one of "
                + ", ".join(SEVERITIES)
            )
        if row.get("kind") not in ISSUE_KINDS:
            problems.append(
                f"{label}: kind is {row.get('kind')!r}, expected one of " + ", ".join(ISSUE_KINDS)
            )
        if not isinstance(row.get("text"), str) or not str(row.get("text")).strip():
            problems.append(
                f"{label}: text is required — a generic 'consider bias' paragraph is not an issue"
            )
    return problems


# --------------------------------------------------------------------------
# validation — the responses
# --------------------------------------------------------------------------


def response_problems(
    payload: Mapping[str, Any],
    *,
    record: Mapping[str, Any],
    study_dir: Path,
    events: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Everything wrong with an authored response set, one line each."""
    problems: list[str] = []
    recorded_issues = _rows(record.get("issues"))
    if canonical_json(_rows(payload.get("issues"))) != canonical_json(recorded_issues):
        problems.append(
            "the issues in the file are not the ones that were recorded — a recorded review "
            "is immutable; answer it, or record a new review of a new draft"
        )
        return problems

    phase = str(record.get("phase"))
    reviewed = record.get("slate_object")
    rows = _rows(payload.get("responses"))
    if not rows:
        problems.append(
            "responses is empty — every issue gets exactly one disposition "
            "(accept | reject | defer) and a rationale"
        )
        return problems

    by_issue: dict[str, dict[str, Any]] = {}
    known = {str(issue.get("id")) for issue in recorded_issues}
    for index, row in enumerate(rows, start=1):
        label = f"response {index}"
        name = row.get("issue")
        if not isinstance(name, str) or name not in known:
            problems.append(
                f"{label}: issue is {name!r}, which the review does not carry "
                f"({', '.join(sorted(known))})"
            )
            continue
        if name in by_issue:
            problems.append(f"{label}: {name} already has a response — one per issue, exactly")
            continue
        by_issue[name] = row
        disposition = row.get("disposition")
        if disposition not in DISPOSITIONS:
            problems.append(
                f"{label}: disposition is {disposition!r}, expected one of "
                + ", ".join(DISPOSITIONS)
            )
        if not isinstance(row.get("rationale"), str) or not str(row.get("rationale")).strip():
            problems.append(f"{label}: rationale is required — a disposition without one is a shrug")
        problems.extend(
            _changed_hash_problems(
                row,
                label=label,
                phase=phase,
                reviewed=reviewed,
                study_dir=study_dir,
                events=events,
            )
        )

    missing = sorted(known - set(by_issue))
    if missing:
        problems.append(
            "no response for " + ", ".join(missing) + " — an unanswered issue is not a rejected one"
        )
    problems.extend(_blocking_problems(recorded_issues, by_issue))
    return problems


def _changed_hash_problems(
    row: Mapping[str, Any],
    *,
    label: str,
    phase: str,
    reviewed: Any,
    study_dir: Path,
    events: Sequence[Mapping[str, Any]],
) -> list[str]:
    """``accept`` names a NEW slate version descended from the one reviewed."""
    changed = row.get("changed_artifact_hash")
    if row.get("disposition") != "accept":
        if changed:
            return [
                f"{label}: changed_artifact_hash is only meaningful on an `accept` "
                "(a rejection changes nothing, and a deferral changes nothing yet)"
            ]
        return []
    if not isinstance(changed, str) or not changed.strip():
        return [
            f"{label}: an `accept` requires changed_artifact_hash — the sha256 of the NEW "
            "slate version the correction produced (`klein generation slate amend` prints it)"
        ]
    if not _is_slate_object(study_dir, events, changed, phase):
        return [
            f"{label}: changed_artifact_hash {changed[:12]}… is not a locked slate object of "
            f"phase {phase!r}"
        ]
    ancestry = slate_ancestors(study_dir, events, changed)
    if changed == reviewed:
        return [
            f"{label}: changed_artifact_hash names the very draft that was reviewed — an "
            "accepted correction produces a NEW version (`klein generation slate amend`)"
        ]
    if reviewed not in ancestry:
        return [
            f"{label}: slate version {changed[:12]}… does not descend from the reviewed draft "
            f"{str(reviewed)[:12]}…"
        ]
    return []


def _blocking_problems(
    issues: Sequence[Mapping[str, Any]], by_issue: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    unresolved = [
        str(issue.get("id"))
        for issue in issues
        if issue.get("severity") == "blocking"
        and issue.get("kind") == "mechanical"
        and str((by_issue.get(str(issue.get("id"))) or {}).get("disposition")) != "accept"
    ]
    if not unresolved:
        return []
    return [
        "blocking mechanical issue(s) "
        + ", ".join(unresolved)
        + " are not accepted — a mechanical defect the reviewer called blocking is fixed or "
        "the phase does not run; a scientific disagreement may be rejected with a rationale, "
        "a mechanical one may not"
    ]


# --------------------------------------------------------------------------
# building the objects
# --------------------------------------------------------------------------


def hypothesis_receipts(
    study_dir: Path,
    events: Sequence[Mapping[str, Any]],
    phase: str,
    *,
    verdict: str,
    receipts: Sequence[Receipt] | None = None,
) -> list[Receipt]:
    """Receipts of one verdict that named a hypothesis of this phase, in chain order."""
    allocated = _slate.allocated_rows(study_dir, events, phase)
    if not allocated:
        return []
    out: list[Receipt] = []
    for receipt in receipts if receipts is not None else load_receipts(study_dir, events):
        if receipt.verdict != verdict:
            continue
        try:
            obj = read_object(study_dir, receipt.sha)
        except WorkflowError:  # pragma: no cover - the orphan family reports this
            continue
        intended = obj.get("intended_action")
        named = intended.get("hypothesis_id") if isinstance(intended, Mapping) else None
        if isinstance(named, str) and named in allocated:
            out.append(receipt)
    return out


def evidence_marks(
    study_dir: Path,
    events: Sequence[Mapping[str, Any]],
    phase: str,
    *,
    core: Sequence[Mapping[str, Any]] = (),
    match: Any = None,
    receipts: Sequence[Receipt] | None = None,
) -> list[tuple[int, str]]:
    """``[(extension sequence, what)]`` — every sign this phase's hypotheses ran.

    Two signs, and they are different failures.  An **admitted** hypothesis
    receipt says the phase started lawfully.  A **refused** one that a run went
    ahead on anyway says it started in defiance of this very gate — and that
    second case is the one V-13 fixtures: with the gate working, a phase's first
    review cannot be late unless somebody ran past its refusal.

    A refusal on its own is deliberately NOT a sign.  While a review is open this
    capability refuses every hypothesis check, and reading its own refusals as
    "the phase already started" would lock the driver out of recording the very
    review that clears them.
    """
    marks = [
        (receipt.sequence, f"admitted receipt {receipt.event_id}")
        for receipt in hypothesis_receipts(
            study_dir, events, phase, verdict="admitted", receipts=receipts
        )
    ]
    refused = hypothesis_receipts(
        study_dir, events, phase, verdict="refused", receipts=receipts
    )
    if refused and match is not None:
        started = run_started_events(core)
        earliest = min(receipt.core_sequence for receipt in refused)
        first = min(receipt.sequence for receipt in refused)
        marks += [
            (first, f"run {run} went ahead on a refused hypothesis check")
            for run, classification in sorted(getattr(match, "runs", {}).items())
            if classification == "refused-but-run"
            and int((started.get(run) or {}).get("sequence") or 0) > earliest
        ]
    return sorted(marks)


def is_late(
    study_dir: Path,
    events: Sequence[Mapping[str, Any]],
    phase: str,
    *,
    core: Sequence[Mapping[str, Any]] = (),
    match: Any = None,
) -> bool:
    """Have this phase's hypotheses already produced evidence?"""
    return bool(evidence_marks(study_dir, events, phase, core=core, match=match))


def build_record(
    payload: Mapping[str, Any],
    *,
    study: str,
    phase: str,
    file_sha256: str,
    bundle_sha256: str,
    session_receipt: str | None,
    session_receipt_sha256: str | None,
    version: int,
    parent_ids: Sequence[str],
    late: bool,
) -> dict[str, Any]:
    """The ``premortem_recorded`` object — issues and reviewer copied VERBATIM."""
    reviewer = dict(payload.get("reviewer") or {})
    reviewer["session_receipt"] = session_receipt
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "premortem_record",
        "study": study,
        "phase": phase,
        "version": version,
        "slate_object": payload.get("slate_object"),
        "reviewer": reviewer,
        "inputs": [str(name) for name in (payload.get("inputs") or [])],
        "input_bundle_sha256": bundle_sha256,
        "issues": _rows(payload.get("issues")),
        "session_receipt_sha256": session_receipt_sha256,
        "independence": "receipted" if session_receipt_sha256 else "self-attested",
        "file_path": f"premortem/{phase}.yaml",
        "file_sha256": file_sha256,
        "parent_ids": list(parent_ids),
        "late": bool(late),
    }


def build_response(
    payload: Mapping[str, Any],
    *,
    study: str,
    phase: str,
    record_event: str,
    record_object: str,
    file_sha256: str,
) -> dict[str, Any]:
    """The ``premortem_responded`` object — dispositions copied VERBATIM."""
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "premortem_response",
        "study": study,
        "phase": phase,
        "record_event": record_event,
        "record_object": record_object,
        "responses": _rows(payload.get("responses")),
        "file_path": f"premortem/{phase}.yaml",
        "file_sha256": file_sha256,
    }


# --------------------------------------------------------------------------
# admission
# --------------------------------------------------------------------------


def _current_phase(ctx: Context) -> str | None:
    value = ctx.state.get("current_phase")
    return value if isinstance(value, str) and value else None


def _governing(
    study_dir: Path, events: Sequence[Mapping[str, Any]], phase: str
) -> tuple[dict[str, Any] | None, str | None]:
    """``(the review that governs the slate in force, why none does)``.

    The governing review is the newest one whose ``slate_object`` is the version
    in force or an ancestor of it.  A review of a version the slate has since
    branched away from governs nothing — and neither does one of a version that
    does not exist yet.
    """
    version = _slate.latest_version(study_dir, events, phase)
    if version is None:
        return None, None  # the slates capability already refuses this
    ancestry = set(slate_ancestors(study_dir, events, version["sha"]))
    candidates = [
        entry
        for entry in records(study_dir, events, phase)
        if entry["object"].get("slate_object") in ancestry
    ]
    if not candidates:
        return None, (
            f"no pre-mortem is recorded for the slate in force in phase {phase!r} — "
            "`klein generation premortem record` files the review of the draft before "
            "its hypotheses run"
        )
    return candidates[-1], None


def _rule_hypothesis_needs_an_answered_premortem(ctx: Context) -> list[str]:
    """A hypothesis runs only after its slate was reviewed and the review answered."""
    if not ctx.hypothesis:
        return []
    phase = _current_phase(ctx)
    if phase is None:
        return []  # the slates capability's own rule reports this
    events = read_events(ctx.study_dir)
    governing, problem = _governing(ctx.study_dir, events, phase)
    if problem:
        return [problem]
    if governing is None:
        return []
    answer = response_for(ctx.study_dir, events, governing)
    if answer is None:
        return [
            f"pre-mortem {governing['event'].get('id')} has no recorded response — "
            "`klein generation premortem respond` records one disposition per issue"
        ]
    version = _slate.latest_version(ctx.study_dir, events, phase)
    in_force = set(slate_ancestors(ctx.study_dir, events, version["sha"])) if version else set()
    reasons: list[str] = []
    by_issue = {str(row.get("issue")): row for row in _rows(answer["object"].get("responses"))}
    for issue in _rows(governing["object"].get("issues")):
        if issue.get("severity") != "blocking" or issue.get("kind") != "mechanical":
            continue
        name = str(issue.get("id"))
        row = by_issue.get(name) or {}
        if row.get("disposition") != "accept":
            reasons.append(
                f"{name} is a blocking mechanical issue answered "
                f"{str(row.get('disposition') or 'not at all')!r} — it is accepted and fixed, "
                "or the phase does not run"
            )
            continue
        changed = row.get("changed_artifact_hash")
        if not isinstance(changed, str) or changed not in in_force:
            reasons.append(
                f"{name} was accepted with slate version {str(changed)[:12]}…, which is not "
                "the version in force nor an ancestor of it — the correction never reached "
                "the slate this run would use"
            )
    return reasons


def _receipt_inputs(ctx: Context) -> dict[str, str | None]:
    """The review this admission rests on — pinned into the receipt."""
    if not ctx.hypothesis:
        return {}
    phase = _current_phase(ctx)
    if phase is None:
        return {}
    governing, _problem = _governing(ctx.study_dir, read_events(ctx.study_dir), phase)
    return {"premortem": governing["sha"]} if governing is not None else {}


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

NAME = "generation premortem"


def premortem_family(ctx: FamilyContext) -> tuple[list[Check], dict[str, Any]]:
    """The ``premortem`` family: integrity of the record, then the independence."""
    checks: list[Check] = []
    all_records = records(ctx.study_dir, ctx.events)
    if not all_records:
        return [
            Check(
                NAME,
                "WARN",
                "the premortem capability is declared and no review has been recorded yet — "
                "`klein generation premortem record` files the red team's issues before the "
                "final slate lock",
            )
        ], {
            # `incomplete`, never `n/a`: the label's `n/a` means "this study did
            # not declare the capability", and it comes only from
            # `label.capability_outcomes`'s defaults.  A DECLARED capability that
            # was never exercised is honestly incomplete — a label-eligible
            # outcome — and saying `n/a` would read as though nothing was promised.
            "integrity": "PASS",
            "outcome": "incomplete",
            "phases": {},
        }

    problems: list[str] = []
    warnings: list[str] = []
    summary: dict[str, Any] = {}
    referee = roster_actor(ctx.study_dir, "referee")
    experimenter = roster_actor(ctx.study_dir, "experimenter")

    for phase in sorted({str(entry["object"].get("phase")) for entry in all_records}):
        phase_problems, phase_warnings, phase_summary = _phase_checks(
            ctx, phase, referee=referee, experimenter=experimenter
        )
        problems.extend(phase_problems)
        warnings.extend(phase_warnings)
        summary[phase] = phase_summary

    if problems:
        checks.append(Check(NAME, "FAIL", "; ".join(problems[:8])))
        integrity = "FAIL"
    else:
        answered = sum(1 for entry in summary.values() if entry["answered"])
        checks.append(
            Check(
                NAME,
                "PASS",
                f"{len(all_records)} recorded review(s) across {len(summary)} phase(s); "
                f"{answered} answered; every blocking mechanical issue that gated a run was "
                "accepted into a slate version the run used",
            )
        )
        integrity = "PASS"
    checks.extend(Check(NAME, "WARN", note) for note in warnings)

    # `receipted` only when EVERY phase's every review carried one: the outcome
    # describes the weakest link in the record, never the strongest.
    rungs = [entry["independence"] for entry in summary.values()]
    outcome = "receipted" if rungs and all(rung == "receipted" for rung in rungs) else "self-attested"
    return checks, {"integrity": integrity, "outcome": outcome, "phases": summary}


def _phase_checks(
    ctx: FamilyContext, phase: str, *, referee: str | None, experimenter: str | None
) -> tuple[list[str], list[str], dict[str, Any]]:
    problems: list[str] = []
    warnings: list[str] = []
    phase_records = records(ctx.study_dir, ctx.events, phase)
    marks = evidence_marks(
        ctx.study_dir,
        ctx.events,
        phase,
        core=ctx.core,
        match=ctx.match,
        receipts=ctx.receipts,
    )
    answered = 0
    independence = "receipted"
    issues_total = 0

    if phase_records and referee is None:
        # Once per phase, not once per review: "reviewer ≠ referee" is checked as
        # string inequality against the roster, and an ABSENT roster row makes
        # that check vacuous rather than satisfied.
        warnings.append(
            f"phase {phase}: program.md's roster names no referee, so reviewer "
            "independence cannot be established"
        )

    for index, entry in enumerate(phase_records):
        obj = entry["object"]
        label = f"phase {phase} review v{obj.get('version')}"
        issues_total += len(_rows(obj.get("issues")))
        order_problems, order_warnings = _order_problems(entry, index, marks, label)
        problems.extend(order_problems)
        warnings.extend(order_warnings)
        problems.extend(_reviewer_check_problems(obj, label, referee=referee))
        warnings.extend(_reviewer_warnings(obj, label, experimenter=experimenter))
        problems.extend(_bundle_problems(ctx, entry, label))
        problems.extend(_record_file_problems(ctx, entry, label))
        if obj.get("independence") != "receipted":
            independence = "self-attested"

        answer = response_for(ctx.study_dir, ctx.events, entry)
        if answer is None:
            if marks:
                problems.append(
                    f"{label} is unanswered and the phase already ran: "
                    + "; ".join(what for _sequence, what in marks[:3])
                )
            else:
                warnings.append(f"{label} is recorded and not yet answered")
            continue
        answered += 1
        problems.extend(_answer_problems(ctx, entry, answer, label, marks))

    problems.extend(_file_problems(ctx, phase, label=f"premortem/{phase}.yaml"))
    return (
        problems,
        warnings,
        {
            "reviews": len(phase_records),
            "issues": issues_total,
            "answered": answered == len(phase_records),
            "independence": independence,
        },
    )


def _order_problems(
    entry: Mapping[str, Any], index: int, marks: Sequence[tuple[int, str]], label: str
) -> tuple[list[str], list[str]]:
    """``(problems, warnings)`` — the review precedes the phase's first evidence.

    Order is read off the extension chain, whose ``sequence`` totally orders every
    generation event, and reported with the core anchor the record carries.  Only
    version 1 FAILs: a later review of a later draft follows the phase's earlier
    work by construction, and is LABELLED rather than failed (R-ADM-8) — exactly
    the treatment ``expert amend`` and ``slate amend`` get.
    """
    if not marks:
        return [], []
    first, what = marks[0]
    if int(entry["event"].get("sequence") or 0) < first:
        return [], []
    anchor = entry["event"].get("core_anchor")
    at = anchor.get("sequence") if isinstance(anchor, Mapping) else "?"
    if index > 0:
        return [], [
            f"{label} was recorded after the phase was already under way ({what}, core "
            f"anchor {at}) — lawful for a later draft, and labelled"
        ]
    return [
        f"{label} was recorded after a hypothesis admission of the same phase "
        f"({what}, core anchor {at}) — a pre-mortem written after the evidence started "
        "arriving criticised nothing"
    ], []


def _reviewer_check_problems(
    obj: Mapping[str, Any], label: str, *, referee: str | None
) -> list[str]:
    reviewer = obj.get("reviewer")
    name = reviewer.get("name") if isinstance(reviewer, Mapping) else None
    if not isinstance(name, str) or not name.strip():
        return [f"{label}: the record carries no reviewer name"]
    if same_actor(name, referee):
        return [
            f"{label}: reviewer {name!r} is the roster's referee {referee!r} — the proposal "
            "critic may not be the closing referee, or the study has no independent review "
            "left to give"
        ]
    return []


def _reviewer_warnings(
    obj: Mapping[str, Any], label: str, *, experimenter: str | None
) -> list[str]:
    reviewer = obj.get("reviewer") if isinstance(obj.get("reviewer"), Mapping) else {}
    name = reviewer.get("name")
    warnings: list[str] = []
    if not obj.get("session_receipt_sha256"):
        warnings.append(
            f"{label}: no session receipt — independence is self-attested, and the record "
            "must not be read as certifying it"
        )
    if isinstance(name, str) and same_actor(name, experimenter):
        warnings.append(
            f"{label}: reviewer {name!r} matches the roster experimenter {experimenter!r} — "
            "a red team of one's own slate raises no rung"
        )
    return warnings


def _bundle_problems(ctx: FamilyContext, entry: Mapping[str, Any], label: str) -> list[str]:
    """The inputs are still the bytes the reviewer was handed.

    Recomputed from the commit that INTRODUCED the record's object file, so a
    later legitimate edit of ``playbook.md`` does not retroactively break a
    review, and a rewritten history does not silently pass.
    """
    repo = ctx.repo
    obj = entry["object"]
    inputs = [str(name) for name in (obj.get("inputs") or [])]
    if repo is None:
        return []
    commit = introducing_commit(
        repo, relative(repo, ctx.study_dir / "generation" / "objects" / f"{entry['sha']}.json")
    )
    if commit is None:
        return [f"{label}: the record object is not committed, so its input bundle cannot be read"]
    digest, rows = input_bundle_at(repo, ctx.study_dir, inputs, commit)
    if digest == obj.get("input_bundle_sha256"):
        return []
    absent = [str(name) for name, sha in rows if sha is None]
    detail = f" (uncommitted at {commit[:12]}: {', '.join(absent)})" if absent else ""
    return [
        f"{label}: the input bundle recomputes to {digest[:12]}… but the record hashed "
        f"{str(obj.get('input_bundle_sha256'))[:12]}…{detail}"
    ]


def _record_file_problems(ctx: FamilyContext, entry: Mapping[str, Any], label: str) -> list[str]:
    """The record IS the file the reviewer wrote — checked at its own commit.

    ``reviewer`` and ``issues`` are copied verbatim into the record object, and
    ``file_sha256`` is the hash of ``premortem/<phase>.yaml`` at that moment.
    Nothing re-read that hash: a record whose object says one reviewer while the
    file it hashed says another was invisible, because the two halves were only
    ever compared at write time.  Here the file is read back out of the commit
    that INTRODUCED the record object — so a later, lawful edit between `record`
    and `respond` does not retroactively break it, and a rewrite does not pass.
    """
    repo = ctx.repo
    obj = entry["object"]
    if repo is None:
        return []
    phase = str(obj.get("phase"))
    commit = introducing_commit(
        repo, relative(repo, ctx.study_dir / "generation" / "objects" / f"{entry['sha']}.json")
    )
    if commit is None:
        return [f"{label}: the record object is not committed, so its file cannot be read"]
    rel = relative(repo, premortem_path(ctx.study_dir, phase))
    blob = git_blob(repo, commit, rel)
    if blob is None:
        return [f"{label}: premortem/{phase}.yaml is absent from {commit[:12]}, which filed it"]
    actual = sha256_bytes(blob)
    if actual != obj.get("file_sha256"):
        return [
            f"{label}: premortem/{phase}.yaml at {commit[:12]} hashes {actual[:12]}… but the "
            f"record froze {str(obj.get('file_sha256'))[:12]}… — the record and the file it "
            "claims to copy are not the same document"
        ]
    try:
        document = yaml.safe_load(blob.decode("utf-8")) or {}
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        return [f"{label}: premortem/{phase}.yaml at {commit[:12]} is unreadable: {exc}"]
    if not isinstance(document, Mapping):
        return [f"{label}: premortem/{phase}.yaml at {commit[:12]} is not a mapping"]
    problems: list[str] = []
    filed = document.get("reviewer")
    filed = dict(filed) if isinstance(filed, Mapping) else {}
    recorded = obj.get("reviewer")
    recorded = dict(recorded) if isinstance(recorded, Mapping) else {}
    # `session_receipt` is REPLACED at record time by the path the driver passed,
    # so it is the one key the file is not expected to match.
    filed.pop("session_receipt", None)
    kept = {key: value for key, value in recorded.items() if key != "session_receipt"}
    if canonical_json(_plainish(filed)) != canonical_json(_plainish(kept)):
        problems.append(
            f"{label}: the record's reviewer {kept!r} is not the reviewer the file names "
            f"({filed!r})"
        )
    inputs = [str(name) for name in (document.get("inputs") or [])]
    if inputs != [str(name) for name in (obj.get("inputs") or [])]:
        problems.append(
            f"{label}: the record's inputs {list(obj.get('inputs') or [])} are not the inputs "
            f"the file names ({inputs})"
        )
    return problems


def _plainish(value: Any) -> Any:
    """YAML dates and the like, coerced so ``canonical_json`` can compare them."""
    if isinstance(value, Mapping):
        return {str(key): _plainish(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plainish(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _answer_problems(
    ctx: FamilyContext,
    entry: Mapping[str, Any],
    answer: Mapping[str, Any],
    label: str,
    marks: Sequence[tuple[int, str]],
) -> list[str]:
    """Every issue answered once; every blocking mechanical one accepted and landed."""
    problems: list[str] = []
    obj = entry["object"]
    phase = str(obj.get("phase"))
    issues = _rows(obj.get("issues"))
    rows = _rows(answer["object"].get("responses"))
    by_issue: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = str(row.get("issue"))
        if name in by_issue:
            problems.append(f"{label}: {name} carries two responses")
        by_issue[name] = row
    missing = sorted({str(issue.get("id")) for issue in issues} - set(by_issue))
    if missing:
        problems.append(f"{label}: unanswered issue(s) " + ", ".join(missing))
    unknown = sorted(set(by_issue) - {str(issue.get("id")) for issue in issues})
    if unknown:
        problems.append(f"{label}: response(s) for issue(s) the review never raised: " + ", ".join(unknown))

    for row in rows:
        changed = row.get("changed_artifact_hash")
        if row.get("disposition") != "accept" or not isinstance(changed, str):
            continue
        if not _is_slate_object(ctx.study_dir, ctx.events, changed, phase):
            problems.append(
                f"{label}: {row.get('issue')} was accepted with {changed[:12]}…, which is not "
                f"a slate object of phase {phase}"
            )
        elif obj.get("slate_object") not in slate_ancestors(ctx.study_dir, ctx.events, changed):
            problems.append(
                f"{label}: {row.get('issue')} was accepted with a slate version that does not "
                "descend from the reviewed draft"
            )

    if marks:
        for issue in issues:
            if issue.get("severity") != "blocking" or issue.get("kind") != "mechanical":
                continue
            name = str(issue.get("id"))
            if str((by_issue.get(name) or {}).get("disposition")) != "accept":
                problems.append(
                    f"{label}: blocking mechanical issue {name} was never accepted and the "
                    "phase's hypotheses ran anyway"
                )
    return problems


def _file_problems(ctx: FamilyContext, phase: str, *, label: str) -> list[str]:
    """The driver's file still IS the bytes the newest premortem event hashed.

    The file is frozen from the moment a response is recorded.  Between ``record``
    and ``respond`` it legitimately changes — the dispositions are written into
    it — so the freeze begins at the answer, and ``respond`` itself refuses a file
    whose issues moved.
    """
    events = [
        *records(ctx.study_dir, ctx.events, phase),
        *responses(ctx.study_dir, ctx.events, phase),
    ]
    if not events:
        return []
    newest = max(events, key=lambda entry: int(entry["event"].get("sequence") or 0))
    if newest["object"].get("kind") != "premortem_response":
        return []
    path = premortem_path(ctx.study_dir, phase)
    if not path.is_file():
        return [f"{label} is missing; the recorded response hashed it"]
    actual = sha256_file(path)
    if actual != newest["object"].get("file_sha256"):
        return [
            f"{label} is {actual[:12]}… but the recorded response hashed "
            f"{str(newest['object'].get('file_sha256'))[:12]}… — an answered review is "
            "immutable; a new draft gets a new review"
        ]
    return []


#: The registration.  Everything above is reachable only through this object.
CAPABILITY = Capability(
    name=CAPABILITY_NAME,
    admission_rules=(_rule_hypothesis_needs_an_answered_premortem,),
    verify_family=premortem_family,
    receipt_inputs=_receipt_inputs,
)
