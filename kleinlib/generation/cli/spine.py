"""``klein generation init|check|verify|label|status|recover`` and ``custody attest``.

The spine's verbs.  ``custody`` belongs to no capability: any generation-enabled
study may record one, so it lives here but is registered last by
:func:`kleinlib.generation.cli.register`.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ...errors import WorkflowError
from ._shared import (
    _error,
    _load,
    _require_clean,
    _require_healthy_ledger,
    _study,
    _testimony,
    _testimony_fields,
)

#: The ``--action`` vocabulary, duplicated from
#: :data:`kleinlib.generation.admission.CHECKPOINTS` on purpose: ``register()``
#: builds argparse without importing the package, so the choices cannot be read
#: from it.  ``test_generation_spine.py`` asserts the two tuples stay equal, so
#: the duplication is checked rather than trusted.
CHECKPOINT_CHOICES: tuple[str, ...] = ("run", "sealed", "baseline", "repair", "calibration", "cell")


def register(actions: argparse._SubParsersAction) -> None:
    """``klein generation init|check|verify|label|status|recover`` — the spine's verbs."""
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
        help="declare a capability to be checked (repeatable); this version ships all ten",
    )
    init.add_argument("--predecessor", help="study id this study succeeds (inherited exposure)")
    # A successor cites the pivot receipt that created it.
    init.add_argument(
        "--successor-receipt",
        metavar="SHA",
        help="the predecessor's `escalate pivot` object sha this study succeeds through",
    )
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
        choices=CHECKPOINT_CHOICES,
        metavar="CHECKPOINT",
        help="the checkpoint: " + " | ".join(CHECKPOINT_CHOICES),
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


def _state_or_problem(study: Path, contract: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """``(state, why it could not be read)`` — an unreadable state is not empty.

    ``check`` needs the difference: ``final_holdout_access`` lives in
    ``study_state.json``, so treating an unreadable file as ``{}`` would admit a
    second sealed run on a track that already spent its one look.
    """
    from ...state import load_state

    try:
        return load_state(study, contract), None
    except WorkflowError as exc:
        return {}, str(exc)


def _opted_in(study: Path) -> bool:
    """Did this study ever opt in?  The manifest OR a chain is enough.

    Both are checked so a deleted or hand-edited manifest still meets the FAIL
    path rather than the "never opted in" path — losing the opt-in is a
    finding, not an exemption.
    """
    directory = study / "generation"
    return (directory / "manifest.yaml").is_file() or (directory / "events.jsonl").is_file()


def _run_init(args: argparse.Namespace) -> int:
    from ...primitives import atomic_write_text
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import gate_events, git_head, read_core_events, repo_for
    from ..ledger import append_event, commit_generation, write_object

    try:
        study, contract = _load(args)
    except WorkflowError as exc:
        return _error(str(exc))
    if gm.manifest_path(study).is_file():
        return _error(
            "generation/manifest.yaml already exists — the opt-in is immutable. "
            "Capability additions after opt-in are not available in this release; "
            "declare the full set at init, or start a successor study."
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
        {
            "study_id": args.predecessor,
            # The pivot receipt this study succeeds through, when there is one.
            "successor_receipt": getattr(args, "successor_receipt", None),
            "inherited_exposure": [],
        }
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
        protocols=gm.protocol_hashes(repo, list(args.capability)),
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
    from ...contract import normalize_tracks
    from .. import manifest as gm
    from ..admission import (
        Context,
        build_receipt,
        core_anchor,
        declared_capabilities,
        outstanding_receipt,
    )
    from ..chronology import git_head, repo_for
    from ..ledger import append_event, commit_generation, read_events, write_object

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
    state, state_problem = _state_or_problem(study, contract)
    context = Context(
        study_dir=study,
        repo=repo,
        contract=contract,
        state=state,
        state_problem=state_problem,
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
        protocol_hashes=gm.protocol_hashes(repo, declared_capabilities(manifest)),
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
    from ..verify import write_receipt

    try:
        study, contract = _load(args)
    except WorkflowError as exc:
        return _error(str(exc))
    if not _opted_in(study):
        return _error(
            "this study never opted in to the generation layer (no generation/manifest.yaml "
            "and no generation/events.jsonl) — nothing was written. `klein generation init` "
            "opts in, and it must be anchored BEFORE the CONSULT gate."
        )
    try:
        checks, path = write_receipt(study, contract)
    except WorkflowError as exc:
        return _error(str(exc))
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
    from ...primitives import atomic_write_json
    from .. import label as gl
    from ..admission import core_anchor
    from ..chronology import git_head, repo_for
    from ..ledger import append_event, commit_generation, write_object
    from ..manifest import study_id

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

    from ..verify import RECEIPT_NAME

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
    from .. import manifest as gm
    from ..admission import load_receipts, match_runs
    from ..chronology import repo_for
    from ..ledger import orphan_object_shas, read_events

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
    from ..admission import core_anchor
    from ..manifest import study_id
    from ..recover import recover_generation

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


def register_custody(actions: argparse._SubParsersAction) -> None:
    """``klein generation custody attest`` — capability-agnostic on purpose.

    Custody is not one capability's problem: a benchmark custodies a private
    bundle, a temporal-discovery study custodies the later block, a wet-lab study
    custodies a sample chain.  So this verb asks only that the study be
    generation-enabled, and declares no capability of its own.
    """
    custody = actions.add_parser(
        "custody",
        help="record who holds hidden evidence and how — testimony, never verified",
        description=(
            "A hash proves a private bundle was not altered; it proves nothing about who "
            "read it. `custody attest` records a NAMED holder's statement that specific "
            "accounts, containers or machines denied access — and Klein reports it as the "
            "testimony it is. Any generation-enabled study may use it; no capability is "
            "required. Without one, a benchmark outcome reads `unverified`. See "
            ".claude/skills/klein/references/generation/planted-truth-protocol.md."
        ),
    )
    custody_actions = custody.add_subparsers(dest="custody_action", required=True)

    attest = custody_actions.add_parser("attest", help="record one custody attestation")
    _study(attest)
    _testimony(attest)
    attest.add_argument("--holder", required=True, help="the NAMED person or team who holds it")
    attest.add_argument(
        "--mechanism",
        required=True,
        help="accounts, containers or machines — a directory of this checkout is not isolation",
    )
    attest.add_argument(
        "--statement", required=True, help="what was denied, to whom, and for how long"
    )
    attest.add_argument(
        "--subject",
        help="what is custodied (default: this study's own hidden evidence). A benchmark "
        "counts an attestation only when its subject is the default or names the "
        "benchmark's public_bundle, truth_file or custody.holder",
    )
    attest.add_argument(
        "--receipt", metavar="PATH", help="a study-relative document whose bytes are hashed"
    )
    attest.set_defaults(handler=_run_custody_attest)


def _run_custody_attest(args: argparse.Namespace) -> int:
    from .. import custody as gc
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import git_head, repo_for
    from ..ledger import append_event, commit_generation, write_object

    try:
        study, contract = _load(args)
        # Capability-agnostic: an attestation needs the opt-in and nothing else.
        gm.load_manifest(study)
        _require_healthy_ledger(study)
        _require_clean(study, contract)
    except WorkflowError as exc:
        return _error(str(exc))

    # All four read flags: an attestation that cannot be typed is exit 1.
    problems = gc.attestation_problems(
        holder=args.holder, mechanism=args.mechanism, statement=args.statement
    )
    if problems:
        return _error("; ".join(problems))
    try:
        receipt = gc.receipt_reference(study, args.receipt) if args.receipt else None
    except WorkflowError as exc:
        return _error(str(exc))

    study_name = gm.study_id(study, contract)
    obj = gc.attestation_object(
        study=study_name,
        holder=args.holder.strip(),
        mechanism=args.mechanism.strip(),
        statement=args.statement.strip(),
        subject=args.subject,
        receipt=receipt,
    )
    sha = write_object(study, obj)
    repo = repo_for(study)
    event = append_event(
        study,
        gc.ATTEST_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        testimony_fields=_testimony_fields(args),
        holder=args.holder.strip(),
        subject=args.subject or None,
    )
    commit_generation(
        study,
        f"klein: custody attest ({study_name}, {args.holder.strip()})",
        paths=("generation/events.jsonl", "generation/objects"),
    )
    print(f"{event['id']} custody attested by {args.holder.strip()}: object {sha[:12]}…")
    subject = obj["subject"] or "this study's own hidden evidence"
    print(f"  subject:   {subject}")
    print(f"  mechanism: {args.mechanism.strip()}")
    if receipt is not None:
        print(f"  receipt: {receipt['path']} {receipt['sha256'][:12]}…")
    print(
        "recorded as TESTIMONY: nothing here verifies that anyone was denied access, and a "
        "hash is not secrecy"
    )
    return 0
