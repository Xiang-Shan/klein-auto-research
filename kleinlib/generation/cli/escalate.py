"""``klein generation escalate …`` (the ``escalation`` capability).

The `escalation` capability's verbs.
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
    _state,
    _study,
    _testimony,
    _testimony_fields,
)


def register(actions: argparse._SubParsersAction) -> None:
    """Add the ``escalate`` sub-group to ``klein generation``.

    Argparse only — the vocabulary (rungs, budget units, exposure kinds) lives in
    ``kleinlib.generation.escalate`` and is validated by the handlers, so
    building the parser still imports not one line of the subpackage.
    """
    escalate = actions.add_parser(
        "escalate",
        help="the escalation ladder: account for getting unstuck, before you do it",
        description=(
            "Lock escalation_plan.yaml at CONSULT (triggers reconstructed from the "
            "manifests, five rungs in one fixed order, unit-bearing budgets, stop and "
            "pivot as terminal actions); once a trigger trips, record a <study>#Dn "
            "decision BEFORE the next candidate, close it with its actual costs, and "
            "pivot to a successor study when the question itself has to change. This "
            "verb neither chooses a rung nor launches, schedules or retries work. See "
            ".claude/skills/klein/references/escalation-protocol.md."
        ),
    )
    escalate_actions = escalate.add_subparsers(dest="escalate_action", required=True)

    lock = escalate_actions.add_parser(
        "lock", help="freeze escalation_plan.yaml (before the CONSULT gate is recorded)"
    )
    _study(lock)
    _testimony(lock)
    lock.add_argument(
        "--allow-late",
        action="store_true",
        help="lock AFTER the consult gate: recorded as late and permanently FAILs "
        "`escalation plan`",
    )
    lock.set_defaults(handler=_run_escalate_lock)

    record = escalate_actions.add_parser(
        "record", help="file one <study>#Dn escalation decision BEFORE its action"
    )
    _study(record)
    _testimony(record)
    record.add_argument("--trigger", required=True, metavar="T#", help="the trigger being answered")
    record.add_argument(
        "--track", help="the track a per-track trigger is counted on (when the plan names none)"
    )
    record.add_argument(
        "--rung",
        required=True,
        help="the rung being taken: metric_diagnosis | method_family | data_leverage | "
        "adjacent_field_analogy | human_expert; `stop` is always available",
    )
    record.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="RUNG=REASON",
        help="a lower rung skipped, and why (repeatable); a silent skip is refused",
    )
    record.add_argument("--action", required=True, help="the action being considered")
    record.add_argument(
        "--changed",
        required=True,
        metavar="TEXT",
        help="the concrete resource or assumption this changes (a rung label alone is a story)",
    )
    record.add_argument("--rationale", required=True, help="why this rung, now")
    record.add_argument(
        "--estimated-cost",
        action="append",
        default=[],
        metavar="UNIT=VALUE",
        help="the cost vector — compute, person_time, money, samples; `unknown` is allowed",
    )
    record.add_argument("--next", dest="next_condition", help="the condition that would close this")
    record.add_argument("--successor", help="the successor study this decision anticipates")
    record.add_argument("--advisor", help="who was consulted (required at the human_expert rung)")
    record.add_argument("--advice", help="the advice, pinned verbatim")
    record.add_argument(
        "--advice-accepted",
        action="store_true",
        help="the advice was accepted (default: recorded and not accepted)",
    )
    record.add_argument(
        "--advice-cost",
        action="append",
        default=[],
        metavar="UNIT=VALUE",
        help="what the consultation cost (repeatable)",
    )
    record.set_defaults(handler=_run_escalate_record)

    close = escalate_actions.add_parser(
        "close", help="add the outcome and the actual costs to an open decision"
    )
    _study(close)
    _testimony(close)
    close.add_argument("--decision", required=True, metavar="ID", help="the <study>#Dn to close")
    close.add_argument(
        "--actual-cost",
        action="append",
        default=[],
        metavar="UNIT=VALUE",
        help="what it actually cost — compute, person_time, money, samples; "
        "`unknown` is allowed",
    )
    close.add_argument(
        "--cost-evidence", help="where the actuals come from (required when any is unknown)"
    )
    close.add_argument("--outcome", required=True, help="what the escalation bought")
    close.set_defaults(handler=_run_escalate_close)

    pivot = escalate_actions.add_parser(
        "pivot", help="link a successor study: both contract hashes, and everything already seen"
    )
    _study(pivot)
    _testimony(pivot)
    pivot.add_argument("--decision", required=True, metavar="ID", help="the decision that pivots")
    pivot.add_argument("--successor", required=True, metavar="STUDY", help="the successor study id")
    pivot.add_argument(
        "--new-contract", required=True, metavar="PATH", help="the successor's study.yaml"
    )
    pivot.add_argument(
        "--inherited",
        action="append",
        default=[],
        metavar="KIND=REF",
        help="exposure Klein cannot see — kind one of sealed, held-out, scouted (repeatable)",
    )
    pivot.set_defaults(handler=_run_escalate_pivot)

    show = escalate_actions.add_parser(
        "show", help="read-only: the plan, the live trigger counts, the decisions"
    )
    _study(show)
    show.set_defaults(handler=_run_escalate_show)


def _pairs(values: list[str], label: str) -> tuple[dict[str, str], list[str]]:
    """``KEY=VALUE`` flags into a mapping, with the malformed ones named."""
    parsed: dict[str, str] = {}
    problems: list[str] = []
    for item in values:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            problems.append(f"{label} {item!r} must look like KEY=VALUE")
            continue
        parsed[key.strip()] = value.strip()
    return parsed, problems


def _cost_vector(values: list[str], label: str) -> tuple[dict[str, Any], list[str]]:
    """A cost vector from ``UNIT=VALUE`` flags: numbers stay numbers, `unknown` stays a word."""
    parsed, problems = _pairs(values, label)
    vector: dict[str, Any] = {}
    for unit, raw in parsed.items():
        if raw == "unknown":
            vector[unit] = "unknown"
            continue
        try:
            number = float(raw)
        except ValueError:
            problems.append(f"{label} {unit}={raw!r} must be a number or 'unknown'")
            continue
        vector[unit] = int(number) if number.is_integer() else number
    return vector, problems


def _escalate_setup(
    args: argparse.Namespace, *, extra: tuple[str, ...] = ()
) -> tuple[Path, dict[str, Any], dict[str, Any], Path, list[dict[str, Any]]]:
    """Preconditions shared by every escalate verb.  Raises ``WorkflowError``."""
    from .. import manifest as gm
    from ..admission import declared_capabilities
    from ..chronology import repo_for
    from ..escalate import CAPABILITY_NAME
    from ..ledger import read_events

    study, contract = _load(args)
    manifest = gm.load_manifest(study)
    if CAPABILITY_NAME not in declared_capabilities(manifest):
        raise WorkflowError(
            f"this study did not declare the {CAPABILITY_NAME!r} capability — "
            "`klein generation init --capability escalation` does, and the opt-in is "
            "immutable, so an existing study needs a successor rather than an edit"
        )
    _require_healthy_ledger(study)
    _require_clean(study, contract, *extra)
    repo = repo_for(study)
    assert repo is not None  # _require_clean already refused a non-repo
    return study, contract, manifest, repo, read_events(study)


def _run_escalate_lock(args: argparse.Namespace) -> int:
    """``escalate lock`` — freeze the triggers, the ladder and the budgets."""
    from ...primitives import sha256_file
    from .. import escalate as ge
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import gate_events, git_head, read_core_events
    from ..ledger import append_event, commit_artifacts, write_object

    try:
        study, contract, _manifest, repo, events = _escalate_setup(args, extra=(ge.PLAN_NAME,))
    except WorkflowError as exc:
        return _error(str(exc))

    if ge.locks(study, events):
        return _error(
            f"{ge.PLAN_NAME} is already locked — the plan is locked once; editing a "
            "threshold after the stall is exactly what the lock prevents"
        )
    path = ge.plan_path(study)
    if not path.is_file():
        return _error(
            f"{ge.PLAN_NAME} is missing — copy assets/escalation-plan-template.yaml into "
            "the study and fill its triggers, budgets and terminal actions"
        )
    try:
        document = ge.parse_plan(path)
    except WorkflowError as exc:
        return _error(str(exc))

    study_name = gm.study_id(study, contract)
    problems = ge.plan_problems(contract, document, study=study_name)
    if problems:
        return _refuse("; ".join(problems))

    late = bool(gate_events(read_core_events(study), "consult"))
    if late and not args.allow_late:
        return _refuse(
            "the consult gate is already recorded: the escalation plan is locked at "
            "CONSULT, so the stall rule predates the stall. `--allow-late` records the "
            "lock anyway; `generation verify` then FAILs `escalation plan` permanently."
        )

    plan_sha = sha256_file(path)
    obj = ge.lock_object(
        study=study_name, document=document, plan_sha256=plan_sha, late=late
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        ge.LOCK_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        testimony_fields=_testimony_fields(args),
        plan_sha256=plan_sha,
        triggers=len(document.get("triggers") or []),
        **({"late": True} if late else {}),
    )
    commit_artifacts(
        study,
        f"klein: escalation plan locked ({study_name})",
        paths=[ge.PLAN_NAME, "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} escalation plan: {ge.PLAN_NAME} {plan_sha[:12]}…, "
        f"{len(document.get('triggers') or [])} trigger(s), object {sha[:12]}…"
    )
    for trigger in document.get("triggers") or []:
        if isinstance(trigger, dict):
            print(f"  {trigger.get('id')}: {trigger.get('kind')}")
    print("  rungs: " + " → ".join(ge.RUNGS) + f" (+ {ge.STOP_RUNG}, always available)")
    if late:
        print(
            "WARNING: late lock recorded — `klein generation verify` will FAIL "
            "`escalation plan` for the life of this study"
        )
    return 0


def _run_escalate_record(args: argparse.Namespace) -> int:
    """``escalate record`` — one decision, filed before the action it describes."""
    from ...manifest import load_manifests
    from .. import escalate as ge
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import git_head, read_core_events, run_started_events
    from ..ledger import append_event, commit_generation, write_object

    try:
        study, contract, _manifest, repo, events = _escalate_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    plan = ge.plan_document(study, events)
    if plan is None:
        return _error(
            f"{ge.PLAN_NAME} is not locked — `klein generation escalate lock` first; a "
            "decision answering an unregistered trigger answers nothing"
        )
    declared = [
        trigger
        for trigger in plan.get("triggers") or []
        if isinstance(trigger, dict) and str(trigger.get("id")) == args.trigger
    ]
    if not declared:
        known = ", ".join(
            str(t.get("id")) for t in plan.get("triggers") or [] if isinstance(t, dict)
        )
        return _error(
            f"trigger {args.trigger!r} is not in the locked plan (declared: {known or 'none'})"
        )

    state = _state(study, contract)
    reconstructed = ge.trips(
        {"triggers": declared},
        contract=contract,
        state=state,
        manifests=load_manifests(study),
        started=run_started_events(read_core_events(study)),
        track=args.track,
    )
    if not reconstructed:
        return _error(
            f"trigger {args.trigger!r} counts per track and the plan names none — pass "
            "`--track <id>` so the count in the receipt is the count that refused the run"
        )
    trip = reconstructed[0]

    # The flags first (exit 1: the decision cannot be TYPED), the ladder second
    # (exit 2: the ledger says this rung cannot be taken from where the study is).
    skipped, flag_problems = _pairs(args.skip, "--skip")
    estimated, cost_flag_problems = _cost_vector(args.estimated_cost, "--estimated-cost")
    flag_problems.extend(cost_flag_problems)
    flag_problems.extend(ge.cost_problems(estimated, "--estimated-cost"))
    advice: dict[str, Any] | None = None
    if args.advisor or args.advice:
        cost, advice_problems = _cost_vector(args.advice_cost, "--advice-cost")
        flag_problems.extend(advice_problems)
        advice = {
            "advisor": args.advisor or "unavailable",
            "statement": args.advice or "",
            "accepted": bool(args.advice_accepted),
            "cost": cost,
        }
    if args.rung == "human_expert" and (advice is None or not advice["statement"].strip()):
        flag_problems.append(
            "the human_expert rung pins the consultation: `--advisor <who> --advice "
            '"<what they said>"` (and `--advice-accepted` when it was taken); expertise '
            "that was not available is recorded as `--advisor unavailable`"
        )
    if flag_problems:
        return _error("; ".join(flag_problems))

    rows = ge.decisions(study, events)
    episode = ge.next_episode(study, events)
    problems = ge.rung_problems(
        args.rung, skipped, accounted=ge.accounted_rungs(rows, episode)
    )
    if problems:
        return _refuse("; ".join(problems))

    study_name = gm.study_id(study, contract)
    identifier = f"{study_name}#D{ge.next_decision_number(study, events)}"
    obj = ge.decision_object(
        study=study_name,
        identifier=identifier,
        episode=episode,
        trip=trip,
        rung=args.rung,
        skipped=skipped,
        considered_action=args.action,
        changed=args.changed,
        rationale=args.rationale,
        estimated_cost=estimated,
        next_condition=args.next_condition,
        successor_study=args.successor,
        human_advice=advice,
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        ge.RECORD_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        testimony_fields=_testimony_fields(args),
        decision=identifier,
        episode=episode,
        trigger=trip.trigger,
        rung=args.rung,
    )
    commit_generation(study, f"klein: escalation recorded ({identifier}, {args.rung})")
    print(
        f"{event['id']} {identifier}: episode {episode}, trigger {trip.trigger} "
        f"({trip.kind}, count {trip.count}/{trip.threshold}), rung {args.rung}"
    )
    if trip.evidence:
        print("  evidence: " + ", ".join(trip.evidence))
    for name, reason in sorted(skipped.items()):
        print(f"  skipped {name}: {reason}")
    print(f"  changes: {args.changed}")
    print(
        "  estimated cost: "
        + ", ".join(f"{unit}={estimated.get(unit)}" for unit in ge.BUDGET_UNITS)
    )
    if not trip.tripped:
        print(
            f"NOTE: {trip.trigger} is not tripped ({trip.detail}) — a voluntary escalation "
            "is recorded like any other"
        )
    return 0


def _run_escalate_close(args: argparse.Namespace) -> int:
    """``escalate close`` — the outcome and the actual costs, unknowns included."""
    from .. import escalate as ge
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, commit_generation, write_object

    try:
        study, contract, _manifest, repo, events = _escalate_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    rows = {row.id: row for row in ge.decisions(study, events)}
    row = rows.get(args.decision)
    if row is None:
        return _error(
            f"{args.decision!r} is not a recorded decision (known: "
            + (", ".join(sorted(rows)) or "none")
            + ")"
        )
    if row.closed is not None:
        return _error(
            f"{args.decision} is already {row.status} — a close is recorded once; the next "
            "rung is a new `escalate record`"
        )

    # Every problem here reads a flag, so a close that cannot be typed is exit 1.
    actual, problems = _cost_vector(args.actual_cost, "--actual-cost")
    problems.extend(ge.cost_problems(actual, "--actual-cost"))
    unknown = [unit for unit in ge.BUDGET_UNITS if actual.get(unit) == "unknown"]
    if unknown and not (args.cost_evidence or "").strip():
        problems.append(
            f"{', '.join(unknown)} recorded as unknown — pass `--cost-evidence` saying why "
            "it cannot be measured; an unavailable actual is recorded, not waved through"
        )
    if problems:
        return _error("; ".join(problems))

    study_name = gm.study_id(study, contract)
    status = "stopped" if row.rung == ge.STOP_RUNG else "closed"
    obj = ge.close_object(
        study=study_name,
        decision=row.id,
        status=status,
        actual_cost=actual,
        cost_evidence=args.cost_evidence,
        outcome=args.outcome,
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        ge.CLOSE_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[row.event_id],
        testimony_fields=_testimony_fields(args),
        decision=row.id,
        status=status,
    )
    commit_generation(study, f"klein: escalation {status} ({row.id})")
    print(f"{event['id']} {row.id} {status}: {args.outcome}")
    print("  actual cost: " + ", ".join(f"{unit}={actual.get(unit)}" for unit in ge.BUDGET_UNITS))
    if unknown:
        print(f"  unknown ({', '.join(unknown)}): {args.cost_evidence}")
    return 0


def _run_escalate_pivot(args: argparse.Namespace) -> int:
    """``escalate pivot`` — a linked successor, and everything it inherits."""
    from pathlib import Path as _Path

    from ...primitives import sha256_file
    from .. import escalate as ge
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, commit_generation, write_object

    try:
        study, contract, _manifest, repo, events = _escalate_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    rows = {row.id: row for row in ge.decisions(study, events)}
    row = rows.get(args.decision)
    if row is None:
        return _error(
            f"{args.decision!r} is not a recorded decision (known: "
            + (", ".join(sorted(rows)) or "none")
            + ")"
        )
    if any(str(obj.get("decision")) == row.id for _event, obj in ge.pivots(study, events)):
        return _error(f"{row.id} already pivoted — one decision links one successor")
    named = row.recorded.get("successor_study")
    if isinstance(named, str) and named.strip() and named != args.successor:
        return _refuse(
            f"{row.id} anticipated successor {named!r}; this pivot names {args.successor!r} — "
            "record the change as its own decision rather than re-aiming this one"
        )

    new_contract = _Path(args.new_contract)
    if not new_contract.is_file():
        return _error(f"--new-contract {args.new_contract!r} does not exist")
    exposure_extra, problems = _pairs(args.inherited, "--inherited")
    unknown_kinds = [kind for kind in exposure_extra if kind not in ge.EXPOSURE_KINDS]
    if unknown_kinds:
        problems.append(
            "--inherited kind(s) "
            + ", ".join(unknown_kinds)
            + " must be one of "
            + ", ".join(ge.EXPOSURE_KINDS)
        )
    old_sha = ge.committed_contract_sha(repo, study, "HEAD")
    if old_sha is None:
        problems.append("study.yaml is not committed, so the old contract cannot be pinned")
    if problems:
        return _error("; ".join(problems))

    study_name = gm.study_id(study, contract)
    exposure = ge.inherited_exposure(
        study,
        events,
        contract=contract,
        state=_state(study, contract),
        study=study_name,
        extra=[{"kind": kind, "ref": ref} for kind, ref in sorted(exposure_extra.items())],
    )
    obj = ge.pivot_object(
        study=study_name,
        decision=row.id,
        successor_study=args.successor,
        old_contract_sha256=str(old_sha),
        new_contract_sha256=sha256_file(new_contract),
        exposure=exposure,
        ids=ge.handed_ids(study, events, study_name),
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        ge.PIVOT_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[row.event_id],
        testimony_fields=_testimony_fields(args),
        decision=row.id,
        successor_study=args.successor,
    )
    commit_generation(study, f"klein: escalation pivot ({row.id} → {args.successor})")
    print(
        f"{event['id']} pivot {row.id} → {args.successor}: old contract "
        f"{str(old_sha)[:12]}…, new contract {obj['new_contract_sha256'][:12]}…"
    )
    for entry in exposure:
        print(f"  inherited {entry['kind']}: {entry['ref']}")
    if obj["handed_ids"]:
        print("  handed ids: " + ", ".join(obj["handed_ids"]))
    print(
        f"  the successor records this link with `klein generation init --predecessor "
        f"{study_name} --successor-receipt {sha}` — a successor id restores no blindness"
    )
    return 0


def _run_escalate_show(args: argparse.Namespace) -> int:
    """``escalate show`` — read-only: writes nothing, commits nothing."""
    from ...manifest import load_manifests
    from .. import escalate as ge
    from .. import manifest as gm
    from ..chronology import read_core_events, run_started_events
    from ..ledger import read_events

    try:
        study, contract = _load(args)
        _require_capability(study, ge.CAPABILITY_NAME)
    except WorkflowError as exc:
        return _error(str(exc))
    events = read_events(study)
    plan = ge.plan_document(study, events)
    if plan is None:
        print(f"{ge.PLAN_NAME} is not locked")
        return 0
    print(
        f"{ge.PLAN_NAME}: {len(plan.get('triggers') or [])} trigger(s), evidence window "
        f"{(plan.get('evidence_window') or {}).get('runs')} run(s)"
    )
    for trip in ge.trips(
        plan,
        contract=contract,
        state=_state(study, contract),
        manifests=load_manifests(study),
        started=run_started_events(read_core_events(study)),
    ):
        mark = "TRIPPED" if trip.tripped else "ok"
        print(f"  {trip.trigger} [{mark}] {trip.detail}")
    rows = ge.decisions(study, events)
    for row in rows:
        print(
            f"{row.event_id} {row.id}: episode {row.episode}, rung {row.rung}, "
            f"{row.status} — {row.recorded.get('considered_action')}"
        )
        for name, reason in sorted(row.skipped.items()):
            print(f"    skipped {name}: {reason}")
        if row.closed is not None:
            print(f"    outcome: {row.closed.get('outcome')}")
    for _event, obj in ge.pivots(study, events):
        print(
            f"pivot {obj.get('decision')} → {obj.get('successor_study')}: "
            f"{len(obj.get('inherited_exposure') or [])} inherited exposure record(s)"
        )
    if not rows:
        print(f"no escalation decision recorded for {gm.study_id(study, contract)}")
    return 0
