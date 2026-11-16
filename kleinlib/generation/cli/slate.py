"""``klein generation slate …`` (the ``slates`` capability).
"""

from __future__ import annotations

import argparse

from ...errors import WorkflowError
from ._shared import (
    _error,
    _load,
    _number,
    _require_capability,
    _require_clean,
    _require_healthy_ledger,
    _state,
    _study,
    _testimony,
    _testimony_fields,
)


def register(actions: argparse._SubParsersAction) -> None:
    """``klein generation slate lock|amend|score|show`` (the ``slates`` capability).

    Argparse only, like every other group here: the handlers import
    ``kleinlib.generation.slate`` lazily, so a study that never declares
    ``slates`` never loads a line of it.
    """
    slate = actions.add_parser(
        "slate",
        help="record a phase's authored hypotheses and score the forecasts afterwards",
        description=(
            "A slate is 4-6 falsifiable rows the DRIVER wrote in slates/<phase>.yaml. "
            "`lock` assigns each row a permanent <study>#Hn id and hashes the file; "
            "`amend` records a new version with parents; `score` computes the Brier "
            "score of the forecasts at phase end. Nothing here proposes, ranks or "
            "selects a candidate - see references/phase-ritual.md."
        ),
    )
    slate_actions = slate.add_subparsers(dest="slate_action", required=True)

    lock = slate_actions.add_parser("lock", help="lock version 1 of a phase's slate")
    _study(lock)
    _testimony(lock)
    lock.add_argument("--phase", required=True, help="the phase id from study.yaml")
    lock.set_defaults(handler=_run_slate_lock, slate_amend=False)

    amend = slate_actions.add_parser(
        "amend", help="record the next version of a locked slate (ids are never recycled)"
    )
    _study(amend)
    _testimony(amend)
    amend.add_argument("--phase", required=True, help="the phase id from study.yaml")
    amend.set_defaults(handler=_run_slate_lock, slate_amend=True)

    score = slate_actions.add_parser(
        "score", help="close the cohort and compute the phase's calibration table"
    )
    _study(score)
    _testimony(score)
    score.add_argument("--phase", required=True, help="the phase id from study.yaml")
    score.add_argument(
        "--rescore",
        action="store_true",
        help="score a phase again after new evidence resolved a censored row",
    )
    score.add_argument("--reason", help="why this phase is being rescored (required by --rescore)")
    score.set_defaults(handler=_run_slate_score)

    show = slate_actions.add_parser("show", help="read-only: versions, cohort, panels")
    _study(show)
    show.add_argument("--phase", help="one phase (default: every locked phase)")
    show.set_defaults(handler=_run_slate_show)


def _run_slate_lock(args: argparse.Namespace) -> int:
    from .. import manifest as gm
    from .. import slate as gs
    from ..admission import core_anchor
    from ..chronology import git_head, repo_for
    from ..ledger import append_event, commit_artifacts, read_events, write_object

    amending = bool(getattr(args, "slate_amend", False))
    phase = args.phase
    try:
        study, contract = _load(args)
        _require_capability(study, "slates")
        _require_healthy_ledger(study)
        _require_clean(study, contract, f"slates/{phase}.yaml")
        payload = gs.read_slate_file(study, phase)
    except WorkflowError as exc:
        return _error(str(exc))

    events = read_events(study)
    previous = gs.latest_version(study, events, phase)
    if amending and previous is None:
        return _error(
            f"phase {phase!r} has no locked slate to amend — `klein generation slate lock` first"
        )
    if not amending and previous is not None:
        return _error(
            f"phase {phase!r} is already locked at version "
            f"{previous['object'].get('version')} — a locked forecast is immutable; "
            "`klein generation slate amend` records the next version with its parent"
        )

    study_name = gm.study_id(study, contract)
    allocated = gs.allocated_rows(study, events, phase)
    problems = gs.validation_problems(
        payload,
        study=study_name,
        phase=phase,
        contract=contract,
        state=_state(study, contract),
        previous=previous["object"] if previous else None,
        allocated=allocated,
        known_ids=gs.all_hypothesis_ids(study, events),
    )
    if problems:
        print(f"slate {'amend' if amending else 'lock'} refused:")
        for problem in problems:
            print(f"  - {problem}")
        return 2

    file_payload, obj = gs.build_version(
        study,
        payload,
        study=study_name,
        phase=phase,
        events=events,
        parent=previous["object"] if previous else None,
    )
    obj["file_sha256"] = gs.write_version(study, phase, file_payload)
    obj["late"] = gs.is_late(study, events, allocated)
    obj["parent_ids"] = [previous["event"]["id"]] if previous else []

    sha = write_object(study, obj)
    repo = repo_for(study)
    event = append_event(
        study,
        "slate_amended" if amending else "slate_locked",
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=obj["parent_ids"],
        testimony_fields=_testimony_fields(args),
        phase=phase,
        version=obj["version"],
        rows=len(obj["rows"]),
        late=obj["late"],
    )
    commit_artifacts(
        study,
        f"klein: slate {'amended' if amending else 'locked'} ({study_name} {phase} "
        f"v{obj['version']})",
        paths=[f"slates/{phase}.yaml", "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} slate {phase} v{obj['version']}: {len(obj['rows'])} rows, "
        f"file {obj['file_sha256'][:12]}…, object {sha[:12]}…"
    )
    for row in obj["rows"]:
        print(f"  {row['id']}  p={row['p_success']}  {row['provenance']}  → {row['statement']}")
    if obj["late"]:
        print("WARNING: a hypothesis admission for this phase already existed when this "
              "version was locked")
    return 0


def _run_slate_score(args: argparse.Namespace) -> int:
    from ...manifest import load_manifests
    from .. import manifest as gm
    from .. import slate as gs
    from ..admission import core_anchor, match_runs
    from ..chronology import core_tip, git_head, read_core_events, repo_for
    from ..ledger import append_event, commit_artifacts, read_events, write_object

    phase = args.phase
    if args.rescore and not (args.reason or "").strip():
        return _error("--rescore records WHY the cohort was reopened; pass --reason")
    try:
        study, contract = _load(args)
        _require_capability(study, "slates")
        _require_healthy_ledger(study)
        _require_clean(study, contract)
    except WorkflowError as exc:
        return _error(str(exc))

    events = read_events(study)
    existing = gs.score_events(study, events, phase)
    if existing and not args.rescore:
        return _error(
            f"phase {phase!r} was already scored ({existing[-1]['event']['id']}, coverage "
            f"{existing[-1]['object'].get('coverage')}); `--rescore --reason <why>` records a "
            "new score whose parent is that one"
        )

    repo = repo_for(study)
    core = read_core_events(study)
    try:
        match = match_runs(study, contract, repo=repo, events=events)
        score = gs.build_score(
            study,
            phase=phase,
            events=events,
            core=core,
            match=match,
            manifests={str(m.get("experiment")): m for m in load_manifests(study)},
            closed_at=int(core_tip(core).get("sequence") or 0),
        )
    except WorkflowError as exc:
        return _error(str(exc))

    score["table_sha256"] = gs.write_table(study, phase, score)
    sha = write_object(study, score)
    study_name = gm.study_id(study, contract)
    event = append_event(
        study,
        "slate_scored",
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[existing[-1]["event"]["id"]] if existing else [],
        testimony_fields=_testimony_fields(args),
        phase=phase,
        coverage=score["coverage"],
        outcome=score["outcome"],
        **({"reason": args.reason} if args.rescore else {}),
    )
    commit_artifacts(
        study,
        f"klein: slate scored ({study_name} {phase}, {score['outcome']})",
        paths=["generation/tables", "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} slate {phase} scored: coverage "
        f"{_number(score['coverage'])} → {score['outcome']}"
    )
    for name, entry in score["panels"].items():
        print(
            f"  {name}: n={entry['n']} brier={_number(entry['brier'])} "
            f"skill={_number(entry['skill'])} "
            f"bounds=[{_number(entry['best_case_brier'])}, "
            f"{_number(entry['worst_case_brier'])}]"
        )
    for row in score["cohort"]:
        bound = int(row.get("n_bound_runs") or 0)
        note = "" if bound <= 1 else f"  [{bound} admitted runs; the first one scores]"
        print(f"  {row['id']}: {row['status']} y={_number(row['y'])} — {row['reason']}{note}")
    print(f"table: {gs.table_path(study, phase).relative_to(study).as_posix()}")
    return 0


def _run_slate_show(args: argparse.Namespace) -> int:
    from .. import slate as gs
    from ..ledger import read_events

    try:
        study, contract = _load(args)
        _require_capability(study, "slates")
    except WorkflowError as exc:
        return _error(str(exc))
    events = read_events(study)
    versions = gs.slate_versions(study, events, args.phase)
    if not versions:
        print(f"no slate is locked{f' for phase {args.phase}' if args.phase else ''}")
        return 0
    for version in versions:
        obj = version["object"]
        print(
            f"{version['event']['id']} {obj['phase']} v{obj['version']}: "
            f"{len(obj['rows'])} rows, base rate {obj['base_rate_forecast']}, "
            f"file {str(obj['file_sha256'])[:12]}…"
        )
        for row in obj["rows"]:
            revision = "" if row.get("revision_of") is None else f" (revision of v{row['revision_of']})"
            print(f"  {row['id']}  p={row['p_success']}  {row['provenance']}{revision}")
    for score in gs.score_events(study, events, args.phase):
        obj = score["object"]
        print(
            f"{score['event']['id']} {obj['phase']} scored: coverage "
            f"{_number(obj['coverage'])} → {obj['outcome']} "
            f"(closed at core sequence {obj['closed_at_core_sequence']})"
        )
    return 0
