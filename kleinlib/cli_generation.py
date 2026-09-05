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

    # --- WP-02: hypothesis slates + calibration -------------------------------
    _register_slate(actions)

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
