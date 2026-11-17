"""``klein generation expert …`` and ``klein generation reference …`` (the ``expertise`` capability).

The `expertise` capability's verbs.  Argparse only at import; the handlers import
``kleinlib.generation.expert`` lazily.
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
    _require_clean,
    _require_healthy_ledger,
    _study,
    _testimony,
    _testimony_fields,
)


def register(actions: argparse._SubParsersAction) -> None:
    """Add the ``expert`` and ``reference`` sub-groups to ``klein generation``."""
    expert = actions.add_parser(
        "expert",
        help="the expertise obligation: lock the domain card, reproduce its baseline, bind it",
        description=(
            "Lock domain_card.md before CONSULT, execute its baseline recipe as an "
            "ordinary run-one transaction after METHOD, and bind that run to the "
            "targets frozen at the lock. Targets never move: a repair changes the "
            "IMPLEMENTATION, never the bar. See "
            ".claude/skills/klein/references/generation/expert-protocol.md."
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
            ".claude/skills/klein/references/generation/reference-protocol.md."
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


def _expert_setup(
    args: argparse.Namespace, *, extra: tuple[str, ...] = ()
) -> tuple[Path, dict[str, Any], dict[str, Any], Path, list[dict[str, Any]]]:
    """Preconditions shared by every expertise verb.  Raises ``WorkflowError``."""
    from .. import manifest as gm
    from ..admission import declared_capabilities
    from ..chronology import repo_for
    from ..expert import CAPABILITY_NAME
    from ..ledger import read_events

    study, contract = _load(args)
    manifest = gm.load_manifest(study)
    if CAPABILITY_NAME not in declared_capabilities(manifest):
        raise WorkflowError(
            f"this study did not declare the {CAPABILITY_NAME!r} capability — "
            "`klein generation init --capability expertise` does, and the opt-in is "
            "immutable, so an existing study needs a successor rather than an edit"
        )
    _require_healthy_ledger(study)
    _require_clean(study, contract, *extra)
    repo = repo_for(study)
    assert repo is not None  # _require_clean already refused a non-repo
    return study, contract, manifest, repo, read_events(study)


#: What a repair may NEVER name.  A repair changes the recipe — the
#: implementation, the fixture, a helper in ``lib/`` — never the study's
#: contract, its state, its evidence or its conclusions.  Naming one of these
#: would also exempt it from the clean-tree check, which is how a hand-edited
#: ``study_state.json`` could ride into a generation commit.
REPAIR_FORBIDDEN_PATHS: frozenset[str] = frozenset(
    {
        "study.yaml",
        "study_state.json",
        "events.jsonl",
        "claims.lock",
        "verify_receipt.json",
        "findings.md",
        "results.tsv",
        "aux_metrics.tsv",
    }
)


#: The same rule for whole subtrees: run evidence, and the generation ledger
#: itself (a repair that "changed" a receipt is a rewritten receipt).
REPAIR_FORBIDDEN_PREFIXES: tuple[str, ...] = ("runs/", "generation/")


def _repair_path_problem(changed: list[str]) -> str | None:
    """Why these ``--changed`` paths cannot be a repair — one message, or None."""
    for name in changed:
        if Path(name).is_absolute() or ".." in Path(name).parts:
            return f"--changed {name!r} must be a study-relative path inside the study"
        posix = Path(name).as_posix()
        if posix in REPAIR_FORBIDDEN_PATHS or posix.startswith(REPAIR_FORBIDDEN_PREFIXES):
            return (
                f"--changed {name!r} is core state, core evidence or the generation ledger — "
                "a repair changes the RECIPE, never the contract, the state, the runs, the "
                "receipts or the conclusions"
            )
    return None


def _run_expert_lock(args: argparse.Namespace) -> int:
    """``expert lock`` and ``expert amend`` — one transaction, two entry points."""
    from ...contract import mutable_surface
    from ...primitives import canonical_json, sha256_file
    from .. import expert as ge
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import gate_events, git_head, read_core_events
    from ..ledger import append_event, commit_artifacts, write_object

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
            f"{ge.CARD_NAME} is missing — copy assets/generation/domain-card-template.md into the "
            "study and fill its frontmatter"
        )
    try:
        front, _body = ge.parse_card(card)
    except WorkflowError as exc:
        return _error(str(exc))

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
    recipe = ge.baseline_hashes(study, front)
    obj = ge.lock_object(
        study=study_name,
        version=version,
        frontmatter=front,
        card_sha256=card_sha,
        parent_ids=parents,
        late=late,
        baseline_hashes=recipe,
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
    commit_artifacts(
        study,
        f"klein: expert {'amend' if amend else 'lock'} v{version} ({study_name})",
        paths=[ge.CARD_NAME, "generation/events.jsonl", "generation/objects"],
    )
    targets = ge.lock_targets(obj)
    print(
        f"{event['id']} expert lock v{version}: {ge.CARD_NAME} {card_sha[:12]}…, "
        f"{len(targets)} target(s) frozen, object {sha[:12]}…"
    )
    for target in targets:
        limit = "×|value|" if target["rel"] else ""
        print(f"  - {target['key']} = {target['value']:.12g} ± {target['tol']:.12g}{limit}")
    surface = set(mutable_surface(contract))
    for name, file_sha in sorted(recipe.items()):
        where = "in the mutable surface, not frozen" if name in surface else "frozen"
        print(f"  - recipe {name} {str(file_sha)[:12]}… ({where})")
    if late:
        print(
            "WARNING: late lock recorded — `klein generation verify` will FAIL "
            "`expert card` for the life of this study"
        )
    return 0


def _run_expert_bind(args: argparse.Namespace) -> int:
    from ...manifest import load_manifests
    from .. import expert as ge
    from .. import manifest as gm
    from ..admission import core_anchor, load_receipts, match_runs
    from ..chronology import git_head
    from ..ledger import append_event, commit_generation, write_object

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
    from ...contract import mutable_surface
    from ...primitives import sha256_file
    from .. import expert as ge
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, commit_artifacts, write_object

    changed = [str(name) for name in (args.changed or [])]
    if not changed:
        return _error("a repair must name at least one changed file with --changed")
    # Shape and ownership are validated BEFORE `_expert_setup`, because that call
    # EXEMPTS every named path from the clean-tree check: a `--changed
    # study_state.json` validated afterwards would already have been licensed to
    # be dirty by the check meant to catch it.
    problem = _repair_path_problem(changed)
    if problem:
        return _error(problem)
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
        if name in verifiers:
            return _error(
                f"--changed {name!r} is a declared verifier — the checker is never the "
                "searcher, and it is never the repair either"
            )
        if not path.is_file():
            return _error(f"--changed {name!r} does not exist in the study")
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
    commit_artifacts(
        study,
        f"klein: expert repair v{version} ({study_name})",
        paths=[*filed, "generation/events.jsonl", "generation/objects"],
    )
    print(f"{event['id']} expert repair v{version}: {len(entries)} file(s) — object {sha[:12]}…")
    for name, file_sha in entries:
        where = "filed" if name in filed else "left in the surface for run-one"
        print(f"  - {name} {file_sha[:12]}… ({where})")
    print("next: `klein generation check --action repair`, then run it, then bind again")
    return 0


def _run_expert_review(args: argparse.Namespace) -> int:
    from ...primitives import sha256_file
    from .. import expert as ge
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, commit_generation, write_object

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
    from ...primitives import sha256_file, utc_now
    from ...transaction import git, git_commit, relative
    from .. import expert as ge
    from .. import manifest as gm
    from .. import references as gr
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, write_object

    try:
        study, contract, _manifest, repo, _events = _expert_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    record_id = str(args.record_id)
    if not gr.ID_RE.match(record_id):
        return _error(f"--id {record_id!r} must match {gr.ID_RE.pattern}")
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
