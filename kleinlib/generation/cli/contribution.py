"""``klein generation contribution record|show`` (the ``contribution`` capability).
"""

from __future__ import annotations

import argparse

from ...errors import WorkflowError
from ._shared import (
    _error,
    _load,
    _require_capability,
    _require_clean,
    _require_healthy_ledger,
    _study,
    _testimony,
    _testimony_fields,
)


def register(actions: argparse._SubParsersAction) -> None:
    """``klein generation contribution record|show`` (the ``contribution`` capability)."""
    contribution = actions.add_parser(
        "contribution",
        help="the AI-value ledger: proposals, decisions, rejections and errors",
        description=(
            "Append one line to ai_value.jsonl and seal its hash into the generation "
            "chain. Coverage includes rejections; an accepted row with no human acceptor "
            "is recorded as agent-accepted and never promoted; causal AI value requires a "
            "matched frozen-2.0 ablation, which parity.yaml's ablation_study cites. See "
            ".claude/skills/klein/references/generation/expert-parity-protocol.md."
        ),
    )
    contribution_actions = contribution.add_subparsers(dest="contribution_action", required=True)

    record = contribution_actions.add_parser("record", help="append one ledger line")
    _study(record)
    _testimony(record)
    record.add_argument(
        "--kind", required=True, help="proposal | decision | rejection | error"
    )
    record.add_argument(
        "--subject", required=True, help="what this is about: <study>#Hn, E####, or an artifact"
    )
    record.add_argument("--origin", required=True, help="ai | human — who proposed it")
    # `--actor` is the spine's testimony flag: the actor in the envelope and the
    # actor on the ledger line are one self-reported string, not two.
    record.add_argument("--decision", help="accepted | rejected | deferred")
    record.add_argument(
        "--human-acceptor",
        help="the HUMAN who accepted it; omitting it on an accepted row records agent-accepted",
    )
    record.add_argument("--implementation-ref", help="the E#### or path that implemented it")
    record.add_argument(
        "--refs",
        action="append",
        default=[],
        metavar="ID",
        help="related ids (comma-separated or repeatable): P#, E####, <study>#Cn",
    )
    record.add_argument("--outcome", help="what happened (free text)")
    record.add_argument("--cost", help="what it cost (free text; `unknown` is allowed)")
    record.add_argument("--transcript-hash", help="sha256 of the transcript or span, if retained")
    record.set_defaults(handler=_run_contribution_record)

    show = contribution_actions.add_parser("show", help="read-only: the ledger and its coverage")
    _study(show)
    show.set_defaults(handler=_run_contribution_show)


def _run_contribution_record(args: argparse.Namespace) -> int:
    from ...primitives import sha256_bytes
    from .. import contribution as gc
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import git_head, repo_for
    from ..ledger import append_event, commit_artifacts, read_events, write_object

    try:
        study, contract = _load(args)
        _require_capability(study, "contribution")
        _require_healthy_ledger(study)
        _require_clean(study, contract, gc.LEDGER_NAME)
        lines = gc.read_lines(study)
    except WorkflowError as exc:
        return _error(str(exc))

    events = read_events(study)
    recorded = gc.joined(study, events, gc.RECORD_TYPE)
    if len(lines) != len(recorded):
        return _error(
            f"{gc.LEDGER_NAME} has {len(lines)} line(s) against {len(recorded)} recorded "
            "event(s): an interrupted write left the two witnesses out of step. Remove the "
            "uncommitted trailing line (it is not committed) and record it again."
        )

    refs = [ref.strip() for raw in args.refs for ref in str(raw).split(",") if ref.strip()]
    # Every one of these reads a flag: a line that cannot be TYPED is a malformed
    # invocation, not a rule of the study saying no.
    problems = gc.record_problems(
        kind=args.kind,
        subject=args.subject,
        origin=args.origin,
        actor=str(args.actor or ""),
        decision=args.decision,
        human_acceptor=args.human_acceptor,
    )
    if problems:
        return _error("; ".join(problems))

    study_name = gm.study_id(study, contract)
    sequence = len(lines) + 1
    record = gc.build_record(
        study=study_name,
        sequence=sequence,
        kind=args.kind,
        subject=args.subject.strip(),
        origin=args.origin,
        actor=str(args.actor).strip(),
        decision=args.decision,
        human_acceptor=args.human_acceptor,
        implementation_ref=args.implementation_ref,
        refs=refs,
        outcome=args.outcome,
        cost=args.cost,
        transcript_hash=args.transcript_hash,
    )
    payload = gc.line_bytes(record)
    line_sha = sha256_bytes(payload)
    path = gc.ledger_path(study)
    with path.open("ab") as handle:
        handle.write(payload)

    obj = gc.record_object(
        study=study_name, sequence=sequence, line_sha256=line_sha, record=record
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gc.RECORD_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo_for(study)),
        payload_sha256=sha,
        parent_ids=[str(recorded[-1][0].get("id"))] if recorded else [],
        testimony_fields=_testimony_fields(args),
        # not `sequence`: that is an envelope field, and the ledger's own
        # position is a different number from the chain's.
        line_number=sequence,
        subject=record["subject"],
        line_sha256=line_sha,
    )
    commit_artifacts(
        study,
        f"klein: contribution recorded ({study_name} #{sequence} {record['kind']})",
        paths=[gc.LEDGER_NAME, "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} contribution #{sequence}: {record['kind']} on {record['subject']} "
        f"({record['origin']}/{record['actor']}) → {record['decision'] or 'no decision'}; "
        f"line {line_sha[:12]}…"
    )
    if record["decision"] == "accepted" and not record["human_acceptor"]:
        print(
            "NOTE: no human_acceptor — recorded as agent-accepted; agent acceptance never "
            "becomes human acceptance"
        )
    return 0


def _run_contribution_show(args: argparse.Namespace) -> int:
    from .. import contribution as gc
    from ..ledger import read_events

    try:
        study, _contract = _load(args)
        _require_capability(study, "contribution")
        lines = gc.read_lines(study)
    except WorkflowError as exc:
        return _error(str(exc))
    events = gc.joined(study, read_events(study), gc.RECORD_TYPE)
    print(f"contribution: {len(lines)} line(s), {len(events)} sealed event(s)")
    for record in lines:
        acceptor = record.get("human_acceptor") or (
            "agent-accepted" if record.get("decision") == "accepted" else "—"
        )
        print(
            f"  #{record.get('sequence')} {record.get('kind')} {record.get('subject')} "
            f"[{record.get('origin')}/{record.get('actor')}] "
            f"{record.get('decision') or 'no decision'} / {acceptor}"
        )
    return 0
