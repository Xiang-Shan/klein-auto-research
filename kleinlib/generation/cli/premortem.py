"""``klein generation premortem record|respond`` (the ``premortem`` capability): the slate-time pre-mortem.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ...errors import WorkflowError
from ._shared import (
    _error,
    _load,
    _refuse,
    _require_capability,
    _require_clean,
    _require_healthy_ledger,
    _study,
    _testimony,
    _testimony_fields,
)


def register(actions: argparse._SubParsersAction) -> None:
    """``klein generation premortem record|respond`` (the ``premortem`` capability).

    Argparse only, like every other group here: the handlers import
    ``kleinlib.generation.premortem`` lazily, so a study that never declares
    ``premortem`` never loads a line of it.
    """
    premortem = actions.add_parser(
        "premortem",
        help="record a red team's review of a DRAFT slate, and the driver's answer to it",
        description=(
            "A pre-mortem is a review of the phase's draft slate, written by someone "
            "other than the driver in a session the driver arranges - Klein calls no "
            "model. `record` binds the draft slate hash, the reviewer, the input bundle "
            "and the issues; `respond` records one disposition per issue. A blocking "
            "mechanical issue must be accepted, and the acceptance must name a NEW slate "
            "version, before any hypothesis of the phase is admitted. Nothing here scores, "
            "ranks or selects - see references/generation/premortem-protocol.md."
        ),
    )
    premortem_actions = premortem.add_subparsers(dest="premortem_action", required=True)

    record = premortem_actions.add_parser(
        "record", help="record the review of a phase's draft slate (responses stay empty)"
    )
    _study(record)
    _testimony(record)
    record.add_argument("--phase", required=True, help="the phase id from study.yaml")
    record.add_argument(
        "--session-receipt",
        metavar="PATH",
        help="study-relative path to the reviewer's session receipt; hashed into the "
        "record and the only thing that lifts independence above self-attested",
    )
    record.add_argument(
        "--allow-late",
        action="store_true",
        help="record a review AFTER the phase's first hypothesis admission: the first "
        "review of a phase then FAILs `generation premortem` permanently",
    )
    record.set_defaults(handler=_run_premortem_record)

    respond = premortem_actions.add_parser(
        "respond", help="record one disposition per issue (accept | reject | defer)"
    )
    _study(respond)
    _testimony(respond)
    respond.add_argument("--phase", required=True, help="the phase id from study.yaml")
    respond.set_defaults(handler=_run_premortem_respond)


def _premortem_setup(
    args: argparse.Namespace,
) -> tuple[Path, dict[str, Any], str, Path, list[dict[str, Any]], dict[str, Any]]:
    """Preconditions shared by both pre-mortem verbs.  Raises ``WorkflowError``."""
    from .. import manifest as gm
    from .. import premortem as gp
    from ..chronology import repo_for
    from ..ledger import read_events

    study, contract = _load(args)
    _require_capability(study, gp.CAPABILITY_NAME)
    _require_healthy_ledger(study)
    _require_clean(study, contract, f"premortem/{args.phase}.yaml")
    repo = repo_for(study)
    assert repo is not None  # _require_clean already refused a non-repo
    payload = gp.read_premortem_file(study, args.phase)
    return study, contract, gm.study_id(study, contract), repo, read_events(study), payload


def _session_receipt(
    study: Path, payload: dict[str, Any], flag: str | None
) -> tuple[str | None, str | None]:
    """``(path, sha256)`` for the reviewer's session receipt, or ``(None, None)``.

    The file's ``reviewer.session_receipt`` is authoritative; ``--session-receipt``
    fills it when the file leaves it null.  Two different answers are refused
    rather than silently reconciled — the artifact and the object must say the
    same thing about who reviewed under what receipt.
    """
    reviewer = payload.get("reviewer")
    declared = reviewer.get("session_receipt") if isinstance(reviewer, dict) else None
    if declared and flag and str(declared) != flag:
        raise WorkflowError(
            f"the file names session receipt {declared!r} and --session-receipt says "
            f"{flag!r} — they must agree"
        )
    name = str(declared or flag) if (declared or flag) else None
    if name is None:
        return None, None
    from ...primitives import sha256_file

    path = study / name
    if not path.is_file():
        raise WorkflowError(
            f"session receipt {name!r} is not a file in the study — independence is "
            "self-attested unless a receipt exists, and a receipt that is not there is not one"
        )
    return name, sha256_file(path)


def _run_premortem_record(args: argparse.Namespace) -> int:
    from ...primitives import sha256_file
    from .. import premortem as gp
    from ..admission import core_anchor, match_runs
    from ..chronology import git_head, read_core_events
    from ..ledger import append_event, commit_artifacts, write_object

    phase = args.phase
    try:
        study, contract, study_name, repo, events, payload = _premortem_setup(args)
        receipt_path, receipt_sha = _session_receipt(study, payload, args.session_receipt)
    except WorkflowError as exc:
        return _error(str(exc))

    open_review = gp.open_record(study, events, phase)
    if open_review is not None:
        return _error(
            f"review {open_review['event'].get('id')} of phase {phase!r} is still "
            "unanswered — `klein generation premortem respond` answers it before another "
            "review is recorded"
        )

    problems = gp.record_problems(
        payload, study=study_name, phase=phase, study_dir=study, events=events
    )
    if problems:
        print("premortem record refused:")
        for problem in problems:
            print(f"  - {problem}")
        return 2

    try:
        match = match_runs(study, contract, repo=repo, events=events)
    except WorkflowError:  # pragma: no cover - a broken study still records its review
        match = None
    late = gp.is_late(study, events, phase, core=read_core_events(study), match=match)
    if late and not args.allow_late:
        return _refuse(
            f"a hypothesis of phase {phase!r} has already been admitted: a pre-mortem "
            "written after the evidence started arriving criticised nothing. "
            "`--allow-late` records it anyway; `generation verify` then FAILs "
            "`generation premortem` for the life of the study."
        )

    previous = gp.records(study, events, phase)
    bundle_sha, entries = gp.input_bundle(study, payload.get("inputs") or [])
    obj = gp.build_record(
        payload,
        study=study_name,
        phase=phase,
        file_sha256=sha256_file(gp.premortem_path(study, phase)),
        bundle_sha256=bundle_sha,
        session_receipt=receipt_path,
        session_receipt_sha256=receipt_sha,
        version=len(previous) + 1,
        parent_ids=[str(previous[-1]["event"]["id"])] if previous else [],
        late=late,
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gp.RECORD_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=obj["parent_ids"],
        testimony_fields=_testimony_fields(args),
        phase=phase,
        version=obj["version"],
        issues=len(obj["issues"]),
        independence=obj["independence"],
        **({"late": True} if late else {}),
    )
    commit_artifacts(
        study,
        f"klein: premortem recorded ({study_name} {phase} v{obj['version']})",
        paths=[f"premortem/{phase}.yaml", "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} premortem {phase} v{obj['version']}: {len(obj['issues'])} issue(s) on "
        f"slate {str(obj['slate_object'])[:12]}…, independence {obj['independence']}, "
        f"object {sha[:12]}…"
    )
    for issue in obj["issues"]:
        print(
            f"  {issue['id']}  {issue['severity']}/{issue['kind']}  {issue['target']}  "
            f"→ {issue['text']}"
        )
    print(f"  inputs: {len(entries)} file(s), bundle {bundle_sha[:12]}…")
    if late:
        print(
            "WARNING: late review recorded — `klein generation verify` will FAIL "
            "`generation premortem` for the life of this study"
        )
    return 0


def _run_premortem_respond(args: argparse.Namespace) -> int:
    from ...primitives import sha256_file
    from .. import premortem as gp
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, commit_artifacts, write_object

    phase = args.phase
    try:
        study, _contract, study_name, repo, events, payload = _premortem_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    open_review = gp.open_record(study, events, phase)
    if open_review is None:
        recorded = gp.records(study, events, phase)
        return _error(
            f"phase {phase!r} has no unanswered review to respond to"
            + (
                f" (every one of the {len(recorded)} recorded review(s) is answered)"
                if recorded
                else " — `klein generation premortem record` files one first"
            )
        )

    problems = gp.response_problems(
        payload, record=open_review["object"], study_dir=study, events=events
    )
    if problems:
        print("premortem respond refused:")
        for problem in problems:
            print(f"  - {problem}")
        return 2

    obj = gp.build_response(
        payload,
        study=study_name,
        phase=phase,
        record_event=str(open_review["event"]["id"]),
        record_object=open_review["sha"],
        file_sha256=sha256_file(gp.premortem_path(study, phase)),
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gp.RESPOND_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[str(open_review["event"]["id"])],
        testimony_fields=_testimony_fields(args),
        phase=phase,
        record_event=obj["record_event"],
        responses=len(obj["responses"]),
    )
    commit_artifacts(
        study,
        f"klein: premortem answered ({study_name} {phase}, {len(obj['responses'])} responses)",
        paths=[f"premortem/{phase}.yaml", "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} premortem {phase} answered {obj['record_event']}: "
        f"{len(obj['responses'])} response(s), object {sha[:12]}…"
    )
    for row in obj["responses"]:
        changed = row.get("changed_artifact_hash")
        tail = f" → slate {str(changed)[:12]}…" if changed else ""
        print(f"  {row['issue']}  {row['disposition']}{tail}  — {row['rationale']}")
    return 0
