"""``klein generation …`` — the verbs of the opt-in generation layer.

One module per verb group so packages landing in parallel do not collide in
``cli.py`` (see :mod:`kleinlib.cli_doctor` for the convention and
:mod:`kleinlib.cli_claims` for a group with sub-subcommands):
``register(subparsers)`` builds the whole ``generation`` sub-command and hangs
its handler off the parsed namespace, and ``cli.py`` carries a single
registration line.  The verbs are the protocol's
(``.claude/skills/klein/references/generation-protocol.md`` "Verbs"):

    klein generation init    --study <dir> [--capability X]… [--allow-late]
    klein generation check   --study <dir> --action <checkpoint> --track <id>
    klein generation verify  --study <dir>
    klein generation label   --study <dir>
    klein generation status  --study <dir>
    klein generation recover --study <dir>
    klein generation slate   lock|amend|score|show --study <dir> --phase <id>

Capability packages add their own sub-groups the same way — one
``_register_<name>`` call at the end of :func:`register`, one delimited block of
handlers below, and no edit to the spine's verbs
(``references/expert-protocol.md``, ``references/reference-protocol.md``):

    klein generation expert    lock | amend | bind | repair | review
    klein generation reference record
    klein generation premortem record | respond --study <dir> --phase <id>

**The subpackage is imported inside the handlers, never at module scope.**
``register`` builds argparse and nothing else, so a defect in
``kleinlib.generation`` cannot break ``klein run-one`` — or any other verb — at
import time.  ``kleinlib/tests/test_generation_spine.py`` asserts that
``import kleinlib.cli`` leaves ``kleinlib.generation`` unimported.

Exit codes are three-valued and mean different things on purpose:

``0``  the verb did what it says.
``1``  an ERROR — the study is not in a state where the question can be asked
       (not schema 3, no manifest, broken chain, orphan objects, dirty tree).
       Nothing is recorded.
``2``  a REFUSAL or a FAILING audit — the question was asked and answered no.
       A refused ``check`` writes its receipt first: a refusal is evidence.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .contract import resolve_study
from .errors import WorkflowError

__all__ = ["register"]


def _study(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--study", default=".", help="study directory (default: .)")


def _testimony(parser: argparse.ArgumentParser) -> None:
    """The four self-reported provenance flags.  Recorded, never authenticated."""
    parser.add_argument("--actor", help="who is driving (testimony, not authenticated)")
    parser.add_argument("--tool", help="which agent/CLI is driving (testimony)")
    parser.add_argument("--model", help="which model is driving (testimony)")
    parser.add_argument("--session", help="a session identifier (testimony)")


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add ``klein generation`` to a parser built by :func:`kleinlib.cli.build_parser`."""
    generation = subparsers.add_parser(
        "generation",
        help="opt-in generation layer: admission receipts before actions, verified after",
        description=(
            "The generation layer records what was committed to BEFORE the evidence "
            "existed. It records, hashes, and computes arithmetic on rows the driver "
            "wrote; it never proposes, ranks, selects, schedules, or retries. Opt in "
            "before the CONSULT gate. Schema 3 only. See "
            ".claude/skills/klein/references/generation-protocol.md."
        ),
    )
    actions = generation.add_subparsers(dest="generation_action", required=True)

    init = actions.add_parser(
        "init", help="opt in: write generation/manifest.yaml and anchor it before CONSULT"
    )
    _study(init)
    _testimony(init)
    init.add_argument(
        "--capability",
        action="append",
        default=[],
        metavar="NAME",
        help="declare a capability to be checked (repeatable); none ships in this version",
    )
    init.add_argument("--predecessor", help="study id this study succeeds (inherited exposure)")
    init.add_argument("--custody-holder", help="who holds custody of any sealed bundle")
    init.add_argument("--custody-mechanism", help="how that custody is enforced (attested)")
    init.add_argument(
        "--allow-late",
        action="store_true",
        help="opt in AFTER the consult gate: recorded as late_opt_in and permanently "
        "FAILs `generation manifest` — the scope freeze cannot be established",
    )
    init.set_defaults(handler=_run_init)

    check = actions.add_parser(
        "check", help="record one admission receipt BEFORE one action (a refusal is evidence)"
    )
    _study(check)
    _testimony(check)
    check.add_argument(
        "--action",
        required=True,
        help="the checkpoint: run | sealed | baseline | repair | calibration | cell",
    )
    check.add_argument("--track", required=True, help="the track the action belongs to")
    check.add_argument(
        "--tests", nargs="*", default=[], metavar="P#", help="predictions the action adjudicates"
    )
    check.add_argument("--hypothesis", help="slate hypothesis id (requires the slates capability)")
    check.add_argument("--cell", help="discovery cell id (requires the surprise capability)")
    check.add_argument("--obligation", help="obligation id (requires the expertise capability)")
    check.set_defaults(handler=_run_check)

    verify = actions.add_parser(
        "verify", help="audit the generation ledger and write generation/verify_receipt.json"
    )
    _study(verify)
    verify.set_defaults(handler=_run_verify)

    label = actions.add_parser(
        "label", help="issue generation/label.json — needs BOTH audits passing at this HEAD"
    )
    _study(label)
    _testimony(label)
    label.set_defaults(handler=_run_label)

    status = actions.add_parser("status", help="read-only summary; writes nothing, commits nothing")
    _study(status)
    status.set_defaults(handler=_run_status)

    recover = actions.add_parser(
        "recover", help="void orphan objects (append-only) and file an uncommitted ledger"
    )
    _study(recover)
    _testimony(recover)
    recover.set_defaults(handler=_run_recover)

    # --- WP-01: expertise -----------------------------------------------------
    _register_expertise(actions)

    # --- WP-02: hypothesis slates + calibration -------------------------------
    _register_slate(actions)

    # --- WP-09: evidence design -----------------------------------------------
    _register_design(actions)

    # --- WP-03: the slate-time pre-mortem -------------------------------------
    _register_premortem(actions)

    return generation


def _register_slate(actions: argparse._SubParsersAction) -> None:
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


# --------------------------------------------------------------------------
# shared preconditions
# --------------------------------------------------------------------------


def _error(message: str) -> int:
    print(f"klein: error: {message}", file=sys.stderr)
    return 1


def _load(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    """The study directory and its contract; raises for anything below schema 3."""
    from .contract import load_contract, schema_version

    study = resolve_study(args.study)
    contract = load_contract(study)
    if schema_version(contract) < 3:
        raise WorkflowError(
            "generation layer requires schema_version 3 (schema-2 studies are frozen and "
            "nothing schema-2 is ever read for generation checks)"
        )
    return study, contract


def _state(study: Path, contract: dict[str, Any]) -> dict[str, Any]:
    from .state import load_state

    try:
        return load_state(study, contract)
    except WorkflowError:
        return {}


def _require_clean(study: Path, contract: dict[str, Any]) -> None:
    from .contract import mutable_surface
    from .generation.chronology import repo_for
    from .transaction import assert_run_worktree

    repo = repo_for(study)
    if repo is None:
        raise WorkflowError("a generation verb needs a git repository: git ancestry is one of the three chronology witnesses")
    assert_run_worktree(repo, study, surface=mutable_surface(contract))


def _require_healthy_ledger(study: Path) -> None:
    from .generation.ledger import (
        chain_problems,
        missing_object_shas,
        orphan_object_shas,
        read_events,
    )

    events = read_events(study)
    problems = chain_problems(events)
    if problems:
        raise WorkflowError(
            "the generation chain is broken: " + "; ".join(problems[:5])
        )
    orphans = orphan_object_shas(study, events)
    if orphans:
        raise WorkflowError(
            "orphan generation objects (written without an event): "
            + ", ".join(sha[:12] for sha in orphans)
            + " — run `klein generation recover` to void them"
        )
    missing = missing_object_shas(study, events)
    if missing:
        raise WorkflowError(
            "generation events whose object is missing: "
            + ", ".join(sha[:12] for sha in missing)
        )


def _testimony_fields(args: argparse.Namespace) -> dict[str, Any]:
    return {
        field: getattr(args, field, None)
        for field in ("actor", "tool", "model", "session")
    }


# --------------------------------------------------------------------------
# the verbs
# --------------------------------------------------------------------------


def _run_init(args: argparse.Namespace) -> int:
    from .generation import manifest as gm
    from .generation.admission import core_anchor
    from .generation.chronology import gate_events, git_head, read_core_events, repo_for
    from .generation.ledger import append_event, commit_generation, write_object
    from .primitives import atomic_write_text

    try:
        study, contract = _load(args)
    except WorkflowError as exc:
        return _error(str(exc))
    if gm.manifest_path(study).is_file():
        return _error(
            "generation/manifest.yaml already exists — the opt-in is immutable; "
            "capability additions are amendments, not a second init"
        )
    problems = gm.capability_problems(list(args.capability))
    if problems:
        return _error("; ".join(problems))
    repo = repo_for(study)
    if repo is None:
        return _error(
            "a generation verb needs a git repository: git ancestry is one of the "
            "three chronology witnesses"
        )
    try:
        _require_healthy_ledger(study)
    except WorkflowError as exc:
        return _error(str(exc))

    core = read_core_events(study)
    late = bool(gate_events(core, "consult"))
    if late and not args.allow_late:
        return _error(
            "the consult gate is already recorded: the generation opt-in must be "
            "anchored BEFORE CONSULT so the scope freeze means something. "
            "`--allow-late` records the opt-in anyway; `generation verify` then FAILs "
            "`generation manifest` permanently."
        )

    predecessor = (
        {"study_id": args.predecessor, "successor_receipt": None, "inherited_exposure": []}
        if args.predecessor
        else None
    )
    custody = (
        {"holder": args.custody_holder, "mechanism": args.custody_mechanism}
        if (args.custody_holder or args.custody_mechanism)
        else None
    )
    study_name = gm.study_id(study, contract)
    manifest = gm.build_manifest(
        study=study_name,
        capabilities=list(args.capability),
        protocols=gm.protocol_hashes(repo),
        predecessor=predecessor,
        custody=custody,
    )
    atomic_write_text(gm.manifest_path(study), gm.render_manifest(manifest))
    sha = write_object(study, gm.manifest_object(manifest))
    event = append_event(
        study,
        "generation_opted_in",
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        testimony_fields=_testimony_fields(args),
        manifest_sha256=gm.manifest_sha256(study),
        capabilities=list(args.capability),
        **({"late_opt_in": True} if late else {}),
    )
    commit_generation(
        study,
        f"klein: generation opt-in ({study_name})",
        paths=("generation/manifest.yaml", "generation/events.jsonl", "generation/objects"),
    )
    print(
        f"generation enabled: {event['id']} anchored at core sequence "
        f"{event['core_anchor']['sequence']}, manifest "
        f"{gm.manifest_sha256(study)[:12]}…, "
        f"{len(args.capability)} capability/ies declared"
    )
    if late:
        print(
            "WARNING: late opt-in recorded — `klein generation verify` will FAIL "
            "`generation manifest` for the life of this study"
        )
    return 0


def _run_check(args: argparse.Namespace) -> int:
    from .contract import normalize_tracks
    from .generation import manifest as gm
    from .generation.admission import Context, build_receipt, core_anchor, outstanding_receipt
    from .generation.chronology import git_head, repo_for
    from .generation.ledger import append_event, commit_generation, read_events, write_object

    try:
        study, contract = _load(args)
        manifest = gm.load_manifest(study)
        _require_healthy_ledger(study)
        _require_clean(study, contract)
    except WorkflowError as exc:
        return _error(str(exc))

    repo = repo_for(study)
    events = read_events(study)
    outstanding = outstanding_receipt(
        study, contract, repo=repo, events=events, track=args.track
    )
    context = Context(
        study_dir=study,
        repo=repo,
        contract=contract,
        state=_state(study, contract),
        manifest=manifest,
        action=args.action,
        track=args.track,
        tests=tuple(args.tests or ()),
        hypothesis=args.hypothesis,
        cell=args.cell,
        obligation=args.obligation,
        outstanding=outstanding,
        tracks=normalize_tracks(contract),
    )
    study_name = gm.study_id(study, contract)
    receipt = build_receipt(
        context,
        study=study_name,
        manifest_sha=gm.manifest_sha256(study),
        protocol_hashes=gm.protocol_hashes(repo),
        core_anchor=core_anchor(study),
        # Only an ADMITTED receipt supersedes: a refusal neither grants nor revokes.
        supersedes=outstanding.sha if outstanding is not None else None,
    )
    if receipt["verdict"] != "admitted":
        receipt.pop("supersedes", None)
        outstanding = None
    sha = write_object(study, receipt)
    event = append_event(
        study,
        "admission_checked",
        study=study_name,
        core_anchor=receipt["core_anchor"],
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[outstanding.event_id] if outstanding is not None else [],
        testimony_fields=_testimony_fields(args),
        checkpoint=args.action,
        track=args.track,
        verdict=receipt["verdict"],
        **({"supersedes": outstanding.sha} if outstanding is not None else {}),
    )
    commit_generation(
        study,
        f"klein: generation {receipt['verdict']} ({args.action} on {args.track})",
        paths=("generation/events.jsonl", "generation/objects"),
    )
    print(f"{event['id']} {receipt['verdict']}: {args.action} on {args.track} — object {sha[:12]}…")
    if outstanding is not None:
        print(f"supersedes {outstanding.sha[:12]}… ({outstanding.event_id}), never matched again")
    for reason in receipt["reasons"]:
        print(f"  - {reason}")
    return 0 if receipt["verdict"] == "admitted" else 2


def _run_verify(args: argparse.Namespace) -> int:
    from .generation.verify import write_receipt

    try:
        study, contract = _load(args)
    except WorkflowError as exc:
        return _error(str(exc))
    checks, path = write_receipt(study, contract)
    failed = 0
    warned = 0
    for check in checks:
        print(f"[{check.status}] {check.name} — {check.detail}")
        failed += check.status == "FAIL"
        warned += check.status == "WARN"
    print(f"summary: {len(checks)} checks, {failed} failed, {warned} warned")
    print(f"receipt: {path.relative_to(study).as_posix()}")
    return 0 if failed == 0 else 2


def _run_label(args: argparse.Namespace) -> int:
    from .generation import label as gl
    from .generation.admission import core_anchor
    from .generation.chronology import git_head, repo_for
    from .generation.ledger import append_event, commit_generation, write_object
    from .generation.manifest import study_id
    from .primitives import atomic_write_json

    try:
        study, contract = _load(args)
        _require_healthy_ledger(study)
        _require_clean(study, contract)
    except WorkflowError as exc:
        return _error(str(exc))
    repo = repo_for(study)
    head = git_head(repo)
    problems = gl.label_problems(study, repo, head)
    if problems:
        print("label refused:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    label = gl.build_label(study, contract, head)
    atomic_write_json(study / gl.LABEL_NAME, label)
    sha = write_object(study, label)
    append_event(
        study,
        "label_issued",
        study=study_id(study, contract),
        core_anchor=core_anchor(study),
        git_head=head,
        payload_sha256=sha,
        testimony_fields=_testimony_fields(args),
        label=label["label"],
        rung=label["rung"],
    )
    commit_generation(
        study,
        f"klein: generation label ({label['label']})",
        paths=("generation/label.json", "generation/events.jsonl", "generation/objects"),
    )
    print(f"label issued: {label['label']} @ {str(head)[:12]} (rung {label['rung']})")
    print(f"add this line to findings.md: {gl.findings_line(label)}")
    return 0


def _capability_lines(study: Path, manifest: dict[str, Any]) -> list[str]:
    """One `integrity / outcome` line per declared capability, once audited.

    Read-only and best effort: before the first `generation verify` there is no
    receipt to read, and status says so rather than inventing a verdict.
    """
    import json

    from .generation.verify import RECEIPT_NAME

    declared = [str(name) for name in (manifest.get("capabilities") or [])]
    if not declared:
        return []
    path = study / RECEIPT_NAME
    try:
        reported = json.loads(path.read_text(encoding="utf-8")).get("capabilities") or {}
    except (OSError, ValueError, AttributeError):
        return [f"  {name}: not audited yet (run `klein generation verify`)" for name in declared]
    lines = []
    for name in declared:
        entry = reported.get(name)
        if isinstance(entry, dict):
            lines.append(f"  {name}: {entry.get('integrity', '?')} / {entry.get('outcome', 'n/a')}")
        else:
            lines.append(f"  {name}: not audited yet (run `klein generation verify`)")
    return lines


def _run_status(args: argparse.Namespace) -> int:
    from .generation import manifest as gm
    from .generation.admission import load_receipts, match_runs
    from .generation.chronology import repo_for
    from .generation.ledger import orphan_object_shas, read_events

    try:
        study, contract = _load(args)
    except WorkflowError as exc:
        return _error(str(exc))
    if not gm.manifest_path(study).is_file():
        print("generation: not enabled (no generation/manifest.yaml)")
        return 0
    try:
        manifest = gm.load_manifest(study)
        events = read_events(study)
    except WorkflowError as exc:
        return _error(str(exc))
    repo = repo_for(study)
    print(f"generation: enabled for {manifest.get('study_id')}")
    print(f"  capabilities: {', '.join(manifest.get('capabilities') or []) or 'none (admission discipline only)'}")
    for line in _capability_lines(study, manifest):
        print(line)
    print(f"  chain: {len(events)} events; last core anchor: "
          f"{(events[-1].get('core_anchor', {}) if events else {}).get('sequence', 0)}")
    print(f"  receipts: {len(load_receipts(study, events))}")
    try:
        match = match_runs(study, contract, repo=repo, events=events)
    except WorkflowError as exc:
        print(f"  runs: unreadable ({exc})")
    else:
        if not match.in_scope:
            print("  runs: none in scope")
        for run in match.in_scope:
            print(f"  {run}: {match.runs.get(run)}")
    orphans = orphan_object_shas(study, events)
    print(f"  orphans: {', '.join(sha[:12] for sha in orphans) if orphans else 'none'}")
    label = study / "generation" / "label.json"
    print(f"  label: {'issued' if label.is_file() else 'not issued'}")
    return 0


def _run_recover(args: argparse.Namespace) -> int:
    from .generation.admission import core_anchor
    from .generation.manifest import study_id
    from .generation.recover import recover_generation

    try:
        study, contract = _load(args)
    except WorkflowError as exc:
        return _error(str(exc))
    try:
        result = recover_generation(
            study,
            study=study_id(study, contract),
            core_anchor=core_anchor(study),
            testimony_fields=_testimony_fields(args),
        )
    except WorkflowError as exc:
        return _error(str(exc))
    voided = result["voided"]
    print(
        "voided: " + (", ".join(sha[:12] for sha in voided) if voided else "none")
        + " (nothing deleted; the bytes stay on disk)"
    )
    print(f"commit: {result['commit'][:12] if result['commit'] else 'nothing to file'}")
    return 0


# ==========================================================================
# WP-01 — `klein generation expert …` and `klein generation reference …`
#
# The `expertise` capability's verbs.  Everything below is additive: the spine's
# argparse, handlers and helpers above are untouched, and `register` gains the
# single `_register_expertise(actions)` line.
# ==========================================================================


def _register_expertise(actions: argparse._SubParsersAction) -> None:
    """Add the ``expert`` and ``reference`` sub-groups to ``klein generation``."""
    expert = actions.add_parser(
        "expert",
        help="the expertise obligation: lock the domain card, reproduce its baseline, bind it",
        description=(
            "Lock domain_card.md before CONSULT, execute its baseline recipe as an "
            "ordinary run-one transaction after METHOD, and bind that run to the "
            "targets frozen at the lock. Targets never move: a repair changes the "
            "IMPLEMENTATION, never the bar. See "
            ".claude/skills/klein/references/expert-protocol.md."
        ),
    )
    expert_actions = expert.add_subparsers(dest="expert_action", required=True)

    lock = expert_actions.add_parser(
        "lock", help="freeze domain_card.md and its baseline targets (before the CONSULT gate)"
    )
    _study(lock)
    _testimony(lock)
    lock.add_argument(
        "--allow-late",
        action="store_true",
        help="lock AFTER the consult gate: recorded as late and permanently FAILs `expert card`",
    )
    lock.set_defaults(handler=_run_expert_lock, amend=False)

    amend = expert_actions.add_parser(
        "amend", help="record a new card version with parents; baseline targets may NOT change"
    )
    _study(amend)
    _testimony(amend)
    amend.set_defaults(handler=_run_expert_lock, amend=True, allow_late=True)

    bind = expert_actions.add_parser(
        "bind", help="adjudicate one baseline/repair run against the frozen targets"
    )
    _study(bind)
    _testimony(bind)
    bind.add_argument("run", metavar="E####", help="the run that executed the baseline recipe")
    bind.set_defaults(handler=_run_expert_bind)

    repair = expert_actions.add_parser(
        "repair", help="record a versioned repair after a bind that did not reproduce"
    )
    _study(repair)
    _testimony(repair)
    repair.add_argument(
        "--changed",
        action="append",
        default=[],
        metavar="PATH",
        help="a study-relative file the repair changed (repeatable); never the verifier",
    )
    repair.add_argument("--note", required=True, help="what was wrong and what was changed")
    repair.set_defaults(handler=_run_expert_repair)

    review = expert_actions.add_parser(
        "review", help="record a practitioner's review of the reproduced baseline (testimony)"
    )
    _study(review)
    _testimony(review)
    review.add_argument("--reviewer", required=True, help="who reviewed it (testimony)")
    review.add_argument("--reviewer-model", help="the reviewer's model, if a model reviewed it")
    review.add_argument("--reviewer-tool", help="the reviewer's tool or CLI")
    review.add_argument(
        "--session-receipt",
        metavar="PATH",
        help="a file evidencing the review session; its sha256 is what raises the rung",
    )
    review.add_argument("--statement", required=True, help="what the reviewer attests")
    review.set_defaults(handler=_run_expert_review)

    reference = actions.add_parser(
        "reference",
        help="reference records: what a citation rests on, and how closely it was checked",
        description=(
            "Write one write-once record under knowledge/references/<id>.json: the "
            "locator, the statement it is cited for, the hash of the bytes that were "
            "read, and the verification basis (read-at-source > bibliography > "
            "abstract-only > hash-only). Klein copies no bytes. See "
            ".claude/skills/klein/references/reference-protocol.md."
        ),
    )
    reference_actions = reference.add_subparsers(dest="reference_action", required=True)
    record = reference_actions.add_parser("record", help="write one reference record")
    _study(record)
    _testimony(record)
    record.add_argument("--id", required=True, dest="record_id", help="record id ([a-z0-9][a-z0-9._-]*)")
    record.add_argument("--title", required=True, help="the work's title")
    record.add_argument("--year", help="year of publication")
    record.add_argument("--authors", nargs="*", default=[], metavar="NAME", help="authors, in order")
    record.add_argument("--venue", help="journal, conference or publisher")
    record.add_argument("--identifier", help="doi / arXiv id / ISBN — the durable identifier")
    record.add_argument("--locator", required=True, help="doi | arxiv | url | isbn | path")
    record.add_argument(
        "--statement", required=True, help="the ONE statement this record is cited for"
    )
    record.add_argument(
        "--basis",
        required=True,
        help="verification basis: read-at-source | bibliography | abstract-only | hash-only",
    )
    record.add_argument(
        "--blob",
        metavar="PATH",
        help="a local file whose sha256 is recorded; the bytes stay where they are",
    )
    record.add_argument(
        "--retained",
        action="store_true",
        help="the driver still holds the source bytes (required by read-at-source)",
    )
    record.add_argument("--checker", help="who checked it (testimony)")
    record.add_argument("--supersedes", help="the record id this one corrects")
    record.set_defaults(handler=_run_reference_record)


def _refuse(message: str) -> int:
    """Exit 2: the question was asked and answered no."""
    print(f"klein: refused: {message}", file=sys.stderr)
    return 2


def _require_clean_with(study: Path, contract: dict[str, Any], *extra: str) -> None:
    """``_require_clean``, plus the human artifacts THIS verb is about to file.

    ``domain_card.md`` is written by the driver and filed by ``expert lock``; a
    repair's changed files are written by the driver and (when they are not the
    mutable surface) filed by ``expert repair``.  Everything else in the tree
    must still be committed — the operator's other edits stay the operator's
    problem, exactly as at ``run-one``.
    """
    from .contract import mutable_surface
    from .generation.chronology import repo_for
    from .transaction import assert_run_worktree

    repo = repo_for(study)
    if repo is None:
        raise WorkflowError(
            "a generation verb needs a git repository: git ancestry is one of the "
            "three chronology witnesses"
        )
    assert_run_worktree(repo, study, surface=(*mutable_surface(contract), *extra))


def _expert_setup(
    args: argparse.Namespace, *, extra: tuple[str, ...] = ()
) -> tuple[Path, dict[str, Any], dict[str, Any], Path, list[dict[str, Any]]]:
    """Preconditions shared by every expertise verb.  Raises ``WorkflowError``."""
    from .generation import manifest as gm
    from .generation.admission import declared_capabilities
    from .generation.chronology import repo_for
    from .generation.expert import CAPABILITY_NAME
    from .generation.ledger import read_events

    study, contract = _load(args)
    manifest = gm.load_manifest(study)
    if CAPABILITY_NAME not in declared_capabilities(manifest):
        raise WorkflowError(
            f"this study did not declare the {CAPABILITY_NAME!r} capability — "
            "`klein generation init --capability expertise` does, and the opt-in is "
            "immutable, so an existing study needs a successor rather than an edit"
        )
    _require_healthy_ledger(study)
    _require_clean_with(study, contract, *extra)
    repo = repo_for(study)
    assert repo is not None  # _require_clean_with already refused a non-repo
    return study, contract, manifest, repo, read_events(study)


def _run_expert_lock(args: argparse.Namespace) -> int:
    """``expert lock`` and ``expert amend`` — one transaction, two entry points."""
    from .generation import expert as ge
    from .generation import manifest as gm
    from .generation.admission import core_anchor
    from .generation.chronology import gate_events, git_head, read_core_events
    from .generation.ledger import append_event, write_object
    from .primitives import canonical_json, sha256_file
    from .transaction import commit_state_writes

    amend = bool(args.amend)
    try:
        study, contract, _manifest, repo, events = _expert_setup(args, extra=(ge.CARD_NAME,))
    except WorkflowError as exc:
        return _error(str(exc))

    locks = ge.joined(study, events, ge.LOCK_TYPE)
    if locks and not amend:
        return _error(
            f"{ge.CARD_NAME} is already locked at version {locks[-1][1].get('version')} — "
            "a change is `klein generation expert amend`, which keeps the parents and "
            "cannot move a target"
        )
    if amend and not locks:
        return _error("nothing to amend: `klein generation expert lock` records version 1")

    card = study / ge.CARD_NAME
    if not card.is_file():
        return _error(
            f"{ge.CARD_NAME} is missing — copy assets/domain-card-template.md into the "
            "study and fill its frontmatter"
        )
    try:
        front, _body = ge.parse_card(card)
    except WorkflowError as exc:
        return _refuse(str(exc))

    study_name = gm.study_id(study, contract)
    problems = ge.card_problems(study, repo, front, study=study_name)
    if problems:
        return _refuse("; ".join(problems))

    late = bool(gate_events(read_core_events(study), "consult"))
    if late and not amend and not args.allow_late:
        return _refuse(
            "the consult gate is already recorded: the domain card must be locked BEFORE "
            "CONSULT so the shortlist and the baseline targets precede what they "
            "constrain. `--allow-late` records the lock anyway; `generation verify` then "
            "FAILs `expert card` permanently."
        )
    if amend and canonical_json(ge.normalized_targets(front)) != canonical_json(
        ge.lock_targets(locks[0][1])
    ):
        return _refuse(
            "this amendment changes baseline.targets. Targets and tolerances are frozen at "
            "version 1: lowering a bar you did not clear is not a repair. A target change "
            "requires a successor study."
        )

    version = len(locks) + 1
    parents = [str(locks[-1][0].get("id"))] if locks else []
    card_sha = sha256_file(card)
    obj = ge.lock_object(
        study=study_name,
        version=version,
        frontmatter=front,
        card_sha256=card_sha,
        parent_ids=parents,
        late=late,
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        ge.LOCK_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=parents,
        testimony_fields=_testimony_fields(args),
        version=version,
        card_sha256=card_sha,
        **({"late": True} if late else {}),
    )
    commit_state_writes(
        study,
        f"klein: expert {'amend' if amend else 'lock'} v{version} ({study_name})",
        paths=[ge.CARD_NAME, "generation/events.jsonl", "generation/objects"],
        scope="own",
    )
    targets = ge.lock_targets(obj)
    print(
        f"{event['id']} expert lock v{version}: {ge.CARD_NAME} {card_sha[:12]}…, "
        f"{len(targets)} target(s) frozen, object {sha[:12]}…"
    )
    for target in targets:
        limit = "×|value|" if target["rel"] else ""
        print(f"  - {target['key']} = {target['value']:.12g} ± {target['tol']:.12g}{limit}")
    if late:
        print(
            "WARNING: late lock recorded — `klein generation verify` will FAIL "
            "`expert card` for the life of this study"
        )
    return 0


def _run_expert_bind(args: argparse.Namespace) -> int:
    from .generation import expert as ge
    from .generation import manifest as gm
    from .generation.admission import core_anchor, load_receipts, match_runs
    from .generation.chronology import git_head
    from .generation.ledger import append_event, commit_generation, write_object
    from .manifest import load_manifests

    try:
        study, contract, _manifest, repo, events = _expert_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    locks = ge.joined(study, events, ge.LOCK_TYPE)
    if not locks:
        return _error(
            f"{ge.CARD_NAME} is not locked: there are no targets to bind this run to"
        )
    run = str(args.run)
    try:
        manifests = {str(m.get("experiment")): m for m in load_manifests(study)}
        match = match_runs(study, contract, repo=repo, events=events)
    except WorkflowError as exc:
        return _error(str(exc))
    manifest = manifests.get(run)
    if manifest is None:
        return _error(f"no run manifest for {run} — bind the run that executed the baseline")

    receipts = {receipt.sha: receipt for receipt in load_receipts(study, events)}
    consumed = next((sha for sha, by in match.consumed.items() if by == run), None)
    receipt = receipts.get(consumed) if consumed else None
    if receipt is None:
        return _refuse(
            f"{run} is {match.runs.get(run, 'not in scope')}: only a run that consumed an "
            "admitted receipt can discharge the obligation"
        )
    if receipt.checkpoint not in ge.BASELINE_CHECKPOINTS:
        return _refuse(
            f"{run} was admitted as {receipt.checkpoint!r}; only "
            f"{' or '.join(ge.BASELINE_CHECKPOINTS)} discharges the baseline obligation"
        )

    lock_event, lock = locks[-1]
    lock_sha = str(lock_event.get("payload_sha256"))
    metrics = manifest.get("metrics")
    rows = ge.evaluate_targets(ge.lock_targets(lock), metrics if isinstance(metrics, dict) else {})
    verdict = ge.bind_verdict(str(manifest.get("disposition")), rows)
    repairs = ge.joined(study, events, ge.REPAIR_TYPE)
    repair_sha = (
        str(repairs[-1][0].get("payload_sha256"))
        if repairs and receipt.checkpoint == "repair"
        else None
    )
    study_name = gm.study_id(study, contract)
    obj = ge.bind_object(
        study=study_name,
        run=run,
        checkpoint=str(receipt.checkpoint),
        verdict=verdict,
        targets=rows,
        lock_sha=lock_sha,
        repair_sha=repair_sha,
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        ge.BIND_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[str(lock_event.get("id"))],
        testimony_fields=_testimony_fields(args),
        run=run,
        checkpoint=receipt.checkpoint,
        verdict=verdict,
    )
    commit_generation(
        study,
        f"klein: expert bind {run} ({verdict})",
        paths=("generation/events.jsonl", "generation/objects"),
    )
    print(f"{event['id']} expert bind {run}: {verdict} — object {sha[:12]}…")
    for row in rows:
        observed = "not printed" if row["observed"] is None else f"{row['observed']:.12g}"
        delta = "—" if row["delta"] is None else f"{row['delta']:+.12g}"
        print(
            f"  - {row['key']}: target {row['value']:.12g} ± {row['tol']:.12g}"
            f"{'×|value|' if row['rel'] else ''}, observed {observed}, delta {delta} "
            f"→ {'within' if row['within'] else 'OUTSIDE'}"
        )
    if verdict != "reproduced":
        print(
            "the obligation stays open: record a versioned `expert repair`, take a "
            "`--action repair` admission, run it, and bind again"
        )
    return 0 if verdict == "reproduced" else 2


def _run_expert_repair(args: argparse.Namespace) -> int:
    from .contract import mutable_surface
    from .generation import expert as ge
    from .generation import manifest as gm
    from .generation.admission import core_anchor
    from .generation.chronology import git_head
    from .generation.ledger import append_event, write_object
    from .primitives import sha256_file
    from .transaction import commit_state_writes

    changed = [str(name) for name in (args.changed or [])]
    if not changed:
        return _error("a repair must name at least one changed file with --changed")
    # The clean-tree exemption is taken BEFORE the paths are validated, so an
    # in-flight repair edit does not read as a dirty tree.
    try:
        study, contract, _manifest, repo, events = _expert_setup(args, extra=tuple(changed))
    except WorkflowError as exc:
        return _error(str(exc))

    binds = ge.joined(study, events, ge.BIND_TYPE)
    if not binds:
        return _refuse(
            "there is nothing to repair: bind the baseline run first, so the record says "
            "what failed before it says what changed"
        )
    last_event, last_bind = binds[-1]
    if last_bind.get("verdict") == "reproduced":
        return _refuse(
            f"the last bind ({last_bind.get('run')}) reproduced the baseline — a repair "
            "after a successful reproduction would be an unrecorded change of recipe"
        )

    verifiers = ge.verifier_scripts(contract)
    surface = set(mutable_surface(contract))
    entries: list[list[Any]] = []
    for name in changed:
        path = study / name
        if ".." in Path(name).parts or Path(name).is_absolute():
            return _refuse(f"--changed {name!r} must be a study-relative path inside the study")
        if name in verifiers:
            return _refuse(
                f"--changed {name!r} is a declared verifier — the checker is never the "
                "searcher, and it is never the repair either"
            )
        if not path.is_file():
            return _refuse(f"--changed {name!r} does not exist in the study")
        entries.append([name, sha256_file(path)])

    version = len(ge.joined(study, events, ge.REPAIR_TYPE)) + 1
    study_name = gm.study_id(study, contract)
    obj = ge.repair_object(
        study=study_name,
        version=version,
        parent_ids=[str(last_event.get("id"))],
        changed_files=entries,
        note=str(args.note),
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        ge.REPAIR_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[str(last_event.get("id"))],
        testimony_fields=_testimony_fields(args),
        version=version,
        changed=len(entries),
    )
    # The mutable surface is NEVER committed here: `run-one` owns it, and filing
    # it would silently move the restore anchor. Everything else the repair
    # touched is filed, because the next run refuses a dirty tree.
    filed = [name for name, _sha in entries if name not in surface]
    commit_state_writes(
        study,
        f"klein: expert repair v{version} ({study_name})",
        paths=[*filed, "generation/events.jsonl", "generation/objects"],
        scope="own",
    )
    print(f"{event['id']} expert repair v{version}: {len(entries)} file(s) — object {sha[:12]}…")
    for name, file_sha in entries:
        where = "filed" if name in filed else "left in the surface for run-one"
        print(f"  - {name} {file_sha[:12]}… ({where})")
    print("next: `klein generation check --action repair`, then run it, then bind again")
    return 0


def _run_expert_review(args: argparse.Namespace) -> int:
    from .generation import expert as ge
    from .generation import manifest as gm
    from .generation.admission import core_anchor
    from .generation.chronology import git_head
    from .generation.ledger import append_event, commit_generation, write_object
    from .primitives import sha256_file

    try:
        study, contract, _manifest, repo, events = _expert_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))
    locks = ge.joined(study, events, ge.LOCK_TYPE)
    if not locks:
        return _error(f"{ge.CARD_NAME} is not locked: there is no baseline to review")

    receipt_sha: str | None = None
    if args.session_receipt:
        path = Path(args.session_receipt)
        if not path.is_file():
            return _error(f"--session-receipt {args.session_receipt!r} is not a file")
        receipt_sha = sha256_file(path)

    study_name = gm.study_id(study, contract)
    obj = ge.review_object(
        study=study_name,
        name=str(args.reviewer),
        model=args.reviewer_model,
        tool=args.reviewer_tool,
        session_receipt=receipt_sha,
        statement=str(args.statement),
        lock_sha=str(locks[-1][0].get("payload_sha256")),
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        ge.REVIEW_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[str(locks[-1][0].get("id"))],
        testimony_fields=_testimony_fields(args),
        reviewer=str(args.reviewer),
        receipted=receipt_sha is not None,
    )
    commit_generation(
        study,
        f"klein: expert review ({args.reviewer})",
        paths=("generation/events.jsonl", "generation/objects"),
    )
    experimenter = ge.roster_experimenter(study)
    independent = receipt_sha is not None and not ge.same_actor(str(args.reviewer), experimenter)
    print(f"{event['id']} expert review by {args.reviewer} — object {sha[:12]}…")
    if receipt_sha is None:
        print("  no session receipt: the outcome stays `source-reconstructed` (testimony only)")
    elif experimenter is None:
        print("  program.md's roster names no experimenter, so independence cannot be established")
    elif not independent:
        print(f"  the reviewer matches the roster experimenter ({experimenter}): no rung is raised")
    else:
        print("  session receipt recorded and the reviewer is not the experimenter: "
              "`generation verify` will report `independent-review`")
    return 0


def _run_reference_record(args: argparse.Namespace) -> int:
    from .generation import expert as ge
    from .generation import manifest as gm
    from .generation import references as gr
    from .generation.admission import core_anchor
    from .generation.chronology import git_head
    from .generation.ledger import append_event, write_object
    from .primitives import sha256_file, utc_now
    from .transaction import git, git_commit, relative

    try:
        study, contract, _manifest, repo, _events = _expert_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    record_id = str(args.record_id)
    if not gr.ID_RE.match(record_id):
        return _refuse(f"--id {record_id!r} must match {gr.ID_RE.pattern}")
    blob_sha: str | None = None
    if args.blob:
        blob = Path(args.blob)
        if not blob.is_file():
            return _error(f"--blob {args.blob!r} is not a file")
        blob_sha = sha256_file(blob)

    record = gr.build_record(
        record_id=record_id,
        title=str(args.title),
        year=args.year,
        authors=list(args.authors or []),
        venue=args.venue,
        identifier=args.identifier,
        locator=str(args.locator),
        retrieved_at=utc_now(),
        source_blob_sha256=blob_sha,
        blob_retained=bool(args.retained),
        supported_statement=str(args.statement),
        checker=args.checker or args.actor,
        verification_basis=str(args.basis),
        recorded_by=_testimony_fields(args),
        supersedes=args.supersedes,
    )
    problems = gr.record_problems(record)
    if problems:
        return _refuse("; ".join(problems))
    try:
        path, record_sha = gr.write_record(repo, record)
    except WorkflowError as exc:
        return _refuse(str(exc))

    study_name = gm.study_id(study, contract)
    link = ge.reference_link_object(
        study=study_name, record_id=record_id, record_sha256=record_sha
    )
    sha = write_object(study, link)
    event = append_event(
        study,
        ge.REFERENCE_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        testimony_fields=_testimony_fields(args),
        record_id=record_id,
        basis=str(args.basis),
    )
    # One commit, two homes: the record is repo-level (a fact about the
    # literature) and the link is the study's (a fact about this study).
    rels = [relative(repo, path)]
    for name in ("generation/events.jsonl", "generation/objects"):
        if (study / name).exists():
            rels.append(relative(repo, study / name))
    git(repo, ["add", "--", *rels])
    if git(repo, ["diff", "--cached", "--quiet", "--", *rels], check=False).returncode != 0:
        git_commit(repo, f"klein: reference record {record_id}", only=rels)
    print(
        f"{event['id']} reference record {record_id} ({args.basis}) — "
        f"{gr.RECORD_DIR}/{record_id}.json {record_sha[:12]}…"
    )
    print(f"  supports: {args.statement}")
    if blob_sha and not args.retained:
        print("  the source bytes were hashed but are NOT retained — say so when citing it")
    return 0


# --------------------------------------------------------------------------
# WP-02: hypothesis slates + calibration
# --------------------------------------------------------------------------


def _require_capability(study: Path, name: str) -> dict[str, Any]:
    """The manifest, once it is confirmed to DECLARE the capability being used."""
    from .generation import manifest as gm
    from .generation.admission import declared_capabilities

    manifest = gm.load_manifest(study)
    if name not in declared_capabilities(manifest):
        raise WorkflowError(
            f"this study did not declare the {name!r} capability; the opt-in is immutable, "
            "so a study that wants it declares it at `klein generation init`"
        )
    return manifest


def _require_clean_but(study: Path, contract: dict[str, Any], *extra: str) -> None:
    """A clean tree except the mutable surface AND the artifact being locked.

    The authored slate is uncommitted BY CONSTRUCTION — it is what the verb is
    about to hash and file — exactly as the candidate edit is uncommitted when
    ``check`` runs.  Everything else must already be filed.
    """
    from .contract import mutable_surface
    from .generation.chronology import repo_for
    from .transaction import assert_run_worktree

    repo = repo_for(study)
    if repo is None:
        raise WorkflowError(
            "a generation verb needs a git repository: git ancestry is one of the "
            "three chronology witnesses"
        )
    assert_run_worktree(repo, study, surface=[*mutable_surface(contract), *extra])


def _run_slate_lock(args: argparse.Namespace) -> int:
    from .generation import manifest as gm
    from .generation import slate as gs
    from .generation.admission import core_anchor
    from .generation.chronology import git_head, repo_for
    from .generation.ledger import append_event, read_events, write_object
    from .transaction import commit_state_writes

    amending = bool(getattr(args, "slate_amend", False))
    phase = args.phase
    try:
        study, contract = _load(args)
        _require_capability(study, "slates")
        _require_healthy_ledger(study)
        _require_clean_but(study, contract, f"slates/{phase}.yaml")
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
    commit_state_writes(
        study,
        f"klein: slate {'amended' if amending else 'locked'} ({study_name} {phase} "
        f"v{obj['version']})",
        paths=[f"slates/{phase}.yaml", "generation/events.jsonl", "generation/objects"],
        scope="own",
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
    from .generation import manifest as gm
    from .generation import slate as gs
    from .generation.admission import core_anchor, match_runs
    from .generation.chronology import core_tip, git_head, read_core_events, repo_for
    from .generation.ledger import append_event, read_events, write_object
    from .manifest import load_manifests
    from .transaction import commit_state_writes

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
    commit_state_writes(
        study,
        f"klein: slate scored ({study_name} {phase}, {score['outcome']})",
        paths=["generation/tables", "generation/events.jsonl", "generation/objects"],
        scope="own",
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
        print(f"  {row['id']}: {row['status']} y={_number(row['y'])} — {row['reason']}")
    print(f"table: {gs.table_path(study, phase).relative_to(study).as_posix()}")
    return 0


def _number(value: Any) -> str:
    return "n/a" if value is None else format(float(value), ".6g")


def _run_slate_show(args: argparse.Namespace) -> int:
    from .generation import slate as gs
    from .generation.ledger import read_events

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


# ==========================================================================
# ---- design verbs (WP-09)
#
# The `design` capability's verb.  Everything below is additive: the spine's
# argparse, handlers and helpers above are untouched, and `register` gains the
# single `_register_design(actions)` line.
# ==========================================================================


def _register_design(actions: argparse._SubParsersAction) -> None:
    """Add the ``design`` sub-group to ``klein generation``."""
    design = actions.add_parser(
        "design",
        help="the evidence design: what the evidence is FOR, locked before the DATA gate",
        description=(
            "Lock evidence_design.yaml before the DATA gate: the estimand and its "
            "population, the uncertainty method and the validity conditions (each "
            "naming a registered prediction whose rule can actually fire it), the "
            "evidence representations and their acquisition custody, the warrant that "
            "carries the evidence to a claim, and the typed continuation. See the "
            "'Evidence design' section of "
            ".claude/skills/klein/references/generation-protocol.md."
        ),
    )
    design_actions = design.add_subparsers(dest="design_action", required=True)

    lock = design_actions.add_parser(
        "lock", help="freeze evidence_design.yaml (before the DATA gate is recorded)"
    )
    _study(lock)
    _testimony(lock)
    lock.add_argument(
        "--allow-late",
        action="store_true",
        help="lock AFTER the data gate: recorded as late and permanently FAILs `design lock`",
    )
    lock.set_defaults(handler=_run_design_lock)


def _design_setup(
    args: argparse.Namespace, *, extra: tuple[str, ...] = ()
) -> tuple[Path, dict[str, Any], dict[str, Any], Path, list[dict[str, Any]]]:
    """Preconditions shared by every design verb.  Raises ``WorkflowError``."""
    from .generation import manifest as gm
    from .generation.admission import declared_capabilities
    from .generation.chronology import repo_for
    from .generation.design import CAPABILITY_NAME
    from .generation.ledger import read_events

    study, contract = _load(args)
    manifest = gm.load_manifest(study)
    if CAPABILITY_NAME not in declared_capabilities(manifest):
        raise WorkflowError(
            f"this study did not declare the {CAPABILITY_NAME!r} capability — "
            "`klein generation init --capability design` does, and the opt-in is "
            "immutable, so an existing study needs a successor rather than an edit"
        )
    _require_healthy_ledger(study)
    _require_clean_with(study, contract, *extra)
    repo = repo_for(study)
    assert repo is not None  # _require_clean_with already refused a non-repo
    return study, contract, manifest, repo, read_events(study)


def _run_design_lock(args: argparse.Namespace) -> int:
    """``design lock`` — one transaction: validate, hash, anchor, commit."""
    from .generation import design as gd
    from .generation import manifest as gm
    from .generation.admission import core_anchor
    from .generation.chronology import gate_events, git_head, read_core_events
    from .generation.ledger import append_event, write_object
    from .primitives import sha256_file
    from .transaction import commit_state_writes

    try:
        study, contract, _manifest, repo, events = _design_setup(args, extra=(gd.DESIGN_NAME,))
    except WorkflowError as exc:
        return _error(str(exc))

    if gd.locks(study, events):
        return _error(
            f"{gd.DESIGN_NAME} is already locked — the design is locked once; a change "
            "of estimand, validity condition or warrant is a successor study"
        )
    path = study / gd.DESIGN_NAME
    if not path.is_file():
        return _error(
            f"{gd.DESIGN_NAME} is missing — copy assets/evidence-design-template.yaml "
            "into the study and fill its five blocks"
        )
    try:
        document = gd.parse_design(path)
    except WorkflowError as exc:
        return _refuse(str(exc))

    study_name = gm.study_id(study, contract)
    problems = gd.design_problems(contract, document, study=study_name)
    if problems:
        return _refuse("; ".join(problems))

    late = bool(gate_events(read_core_events(study), "data"))
    if late and not args.allow_late:
        return _refuse(
            "the data gate is already recorded: the evidence design must be locked "
            "BEFORE the DATA gate, so the estimand and the validity conditions precede "
            "the first look at the evidence. `--allow-late` records the lock anyway; "
            "`generation verify` then FAILs `design lock` permanently."
        )

    design_sha = sha256_file(path)
    warrant = (document.get("claim") or {}).get("warrant")
    obj = gd.lock_object(
        study=study_name, document=document, design_sha256=design_sha, late=late
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gd.LOCK_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        testimony_fields=_testimony_fields(args),
        design_sha256=design_sha,
        warrant=warrant,
        **({"late": True} if late else {}),
    )
    commit_state_writes(
        study,
        f"klein: design lock ({study_name})",
        paths=[gd.DESIGN_NAME, "generation/events.jsonl", "generation/objects"],
        scope="own",
    )
    print(
        f"{event['id']} design lock: {gd.DESIGN_NAME} {design_sha[:12]}…, warrant "
        f"{warrant!r}, object {sha[:12]}…"
    )
    for item in (document.get("prediction") or {}).get("validity_conditions") or []:
        if isinstance(item, dict):
            print(f"  - {item.get('rule_ref')}: {item.get('condition')}")
    for entry in (document.get("evidence") or {}).get("acquisition") or []:
        if isinstance(entry, dict) and entry.get("kind") == "acquisition":
            print(
                f"  - acquired {entry.get('source')!r} at {entry.get('acquired_at')}, "
                f"custody attested by {entry.get('attested_by')!r} "
                "(testimony, never verified)"
            )
    if late:
        print(
            "WARNING: late lock recorded — `klein generation verify` will FAIL "
            "`design lock` for the life of this study"
        )
    return 0


# ---- premortem verbs (WP-03) ---------------------------------------------
# --------------------------------------------------------------------------
# WP-03: the slate-time pre-mortem
# --------------------------------------------------------------------------


def _register_premortem(actions: argparse._SubParsersAction) -> None:
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
            "ranks or selects - see references/premortem-protocol.md."
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
    from .generation import manifest as gm
    from .generation import premortem as gp
    from .generation.chronology import repo_for
    from .generation.ledger import read_events

    study, contract = _load(args)
    _require_capability(study, gp.CAPABILITY_NAME)
    _require_healthy_ledger(study)
    _require_clean_but(study, contract, f"premortem/{args.phase}.yaml")
    repo = repo_for(study)
    assert repo is not None  # _require_clean_but already refused a non-repo
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
    from .primitives import sha256_file

    path = study / name
    if not path.is_file():
        raise WorkflowError(
            f"session receipt {name!r} is not a file in the study — independence is "
            "self-attested unless a receipt exists, and a receipt that is not there is not one"
        )
    return name, sha256_file(path)


def _run_premortem_record(args: argparse.Namespace) -> int:
    from .generation import premortem as gp
    from .generation.admission import core_anchor, match_runs
    from .generation.chronology import git_head, read_core_events
    from .generation.ledger import append_event, write_object
    from .primitives import sha256_file
    from .transaction import commit_state_writes

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
    commit_state_writes(
        study,
        f"klein: premortem recorded ({study_name} {phase} v{obj['version']})",
        paths=[f"premortem/{phase}.yaml", "generation/events.jsonl", "generation/objects"],
        scope="own",
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
    from .generation import premortem as gp
    from .generation.admission import core_anchor
    from .generation.chronology import git_head
    from .generation.ledger import append_event, write_object
    from .primitives import sha256_file
    from .transaction import commit_state_writes

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
    commit_state_writes(
        study,
        f"klein: premortem answered ({study_name} {phase}, {len(obj['responses'])} responses)",
        paths=[f"premortem/{phase}.yaml", "generation/events.jsonl", "generation/objects"],
        scope="own",
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
