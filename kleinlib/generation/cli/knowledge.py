"""``klein generation knowledge …`` (the ``knowledge`` capability): cross-study knowledge verbs.
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
    """``klein generation knowledge promote|contest|resolve|query|decide|show``.

    Argparse only — the handlers import ``kleinlib.generation.knowledge`` lazily,
    so a study that never declares ``knowledge`` never loads a line of it.
    """
    knowledge = actions.add_parser(
        "knowledge",
        help="the repo-level knowledge store: promote, contest, resolve, and consult it",
        description=(
            "Cross-study knowledge as transactions over pinned evidence. `promote` "
            "imports a VERIFIED claim (or a method card) into knowledge/objects/ with its "
            "class, strength and evidence roots copied verbatim - a promotion creates "
            "availability, never stronger evidence. `contest` attaches contradicting "
            "evidence; `resolve` adjudicates without deleting either side. `query` records "
            "the consultation receipt CONSULT cites, with complete hits, their contest "
            "closure, and a use/reject reason for each. The markdown under knowledge/ "
            "stays the human surface and is never rewritten. See "
            ".claude/skills/klein/references/generation/knowledge-protocol.md."
        ),
    )
    knowledge_actions = knowledge.add_subparsers(dest="knowledge_action", required=True)

    promote = knowledge_actions.add_parser(
        "promote", help="import one verified claim (or a method card) into the store"
    )
    _study(promote)
    _testimony(promote)
    promote.add_argument("--claim", help="the claim to promote: `Cn` or `<study>#Cn`")
    promote.add_argument(
        "--method",
        action="store_true",
        help="promote this study's method_card.md, pinned with its reference records",
    )
    promote.add_argument(
        "--tags", nargs="*", default=[], metavar="TAG", help="retrieval tags (case-folded)"
    )
    promote.add_argument(
        "--scope",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="scope field (repeatable): population, measurement_regime, intervention, "
        "assumptions, exclusions",
    )
    promote.add_argument(
        "--dependency",
        action="append",
        default=[],
        metavar="K#",
        help="a store object this one rests on (repeatable)",
    )
    promote.add_argument("--rationale", help="why this belongs in the store")
    promote.set_defaults(handler=_run_knowledge_promote)

    contest = knowledge_actions.add_parser(
        "contest", help="attach contradicting evidence to a store object (nothing is deleted)"
    )
    _study(contest)
    _testimony(contest)
    contest.add_argument("--target", required=True, metavar="K#", help="the object contested")
    contest.add_argument(
        "--evidence",
        nargs="+",
        required=True,
        metavar="ID",
        help="ids from THIS study's verified lock; at least one must be a claim",
    )
    contest.add_argument("--rationale", required=True, help="what contradicts the target's scope")
    contest.set_defaults(handler=_run_knowledge_contest)

    resolve = knowledge_actions.add_parser(
        "resolve", help="adjudicate a contested object; the object and the contest both stay"
    )
    _study(resolve)
    _testimony(resolve)
    resolve.add_argument("--target", required=True, metavar="K#", help="the object adjudicated")
    resolve.add_argument(
        "--outcome",
        required=True,
        choices=["upheld", "scoped", "withdrawn"],
        help="upheld | scoped | withdrawn (a withdrawal keeps the object)",
    )
    resolve.add_argument("--rationale", required=True, help="the adjudication, in one sentence")
    resolve.set_defaults(handler=_run_knowledge_resolve)

    query = knowledge_actions.add_parser(
        "query", help="consult the store BEFORE the CONSULT ack and record the receipt"
    )
    _study(query)
    _testimony(query)
    query.add_argument("--tags", nargs="*", default=[], metavar="TAG", help="typed tags to match")
    query.add_argument("--text", help="the typed question, matched by case-folded token overlap")
    query.add_argument(
        "--limit",
        type=int,
        help="truncate the hit list (recorded in the receipt; the default returns EVERY hit)",
    )
    query.add_argument(
        "--use", action="append", default=[], metavar="K#=REASON", help="a hit this study uses"
    )
    query.add_argument(
        "--reject",
        action="append",
        default=[],
        metavar="K#=REASON",
        help="a hit this study rejects, and why",
    )
    query.set_defaults(handler=_run_knowledge_query)

    decide = knowledge_actions.add_parser(
        "decide", help="record use/reject reasons for hits an earlier receipt left open"
    )
    _study(decide)
    _testimony(decide)
    decide.add_argument("--use", action="append", default=[], metavar="K#=REASON")
    decide.add_argument("--reject", action="append", default=[], metavar="K#=REASON")
    decide.set_defaults(handler=_run_knowledge_decide)

    show = knowledge_actions.add_parser("show", help="read-only: objects, contests, resolutions")
    _study(show)
    show.add_argument("--target", metavar="K#", help="one object (default: the whole store)")
    show.set_defaults(handler=_run_knowledge_show)


def _knowledge_setup(args: argparse.Namespace) -> tuple[Path, dict[str, Any], Path, str]:
    """Preconditions shared by every writing knowledge verb."""
    from .. import manifest as gm
    from ..chronology import repo_for
    from ..knowledge import CAPABILITY_NAME

    study, contract = _load(args)
    _require_capability(study, CAPABILITY_NAME)
    _require_healthy_ledger(study)
    _require_clean(study, contract)
    repo = repo_for(study)
    assert repo is not None  # _require_clean already refused a non-repo
    return study, contract, repo, gm.study_id(study, contract)


def _parse_scope(pairs: list[str]) -> tuple[dict[str, Any], list[str]]:
    """``--scope key=value`` pairs into the store's five scope fields."""
    from ..knowledge import SCOPE_FIELDS

    scope: dict[str, Any] = {}
    problems: list[str] = []
    for pair in pairs:
        key, _, value = str(pair).partition("=")
        key, value = key.strip(), value.strip()
        if key not in SCOPE_FIELDS:
            problems.append(f"--scope {pair!r}: {key!r} is not one of {', '.join(SCOPE_FIELDS)}")
            continue
        if not value:
            problems.append(f"--scope {pair!r}: an empty scope value says nothing")
            continue
        if key in ("assumptions", "exclusions"):
            scope.setdefault(key, []).append(value)
        else:
            scope[key] = value
    return scope, problems


def _origin_repo(repo: Path) -> str:
    """The remote this store belongs to, or ``local`` — provenance, not identity."""
    from ...transaction import git

    result = git(repo, ["remote", "get-url", "origin"], check=False)
    url = result.stdout.strip() if result.returncode == 0 else ""
    return url or "local"


def _commit_store(repo: Path, message: str, *paths: Path) -> None:
    """File exactly the store paths this verb wrote — never ``git add -A``."""
    from ...transaction import git, git_commit, relative

    rels = [relative(repo, path) for path in paths if path.exists()]
    if not rels:
        return
    git(repo, ["add", "--", *rels])
    if git(repo, ["diff", "--cached", "--quiet", "--", *rels], check=False).returncode != 0:
        git_commit(repo, message, only=rels)


def _lock_verification_problem(study: Path) -> str | None:
    """Why ``klein claims verify`` does not PASS on this study right now."""
    from ...claims import verify_lock

    try:
        checks = verify_lock(study)
    except WorkflowError as exc:
        return str(exc)
    failed = [check for check in checks if not check.ok]
    if not failed:
        return None
    return "; ".join(f"{check.name}: {check.message}" for check in failed[:3])


def _method_roots(study: Path, repo: Path) -> list[str]:
    """``ref:<key>`` for every references.yaml row with a resolvable record."""
    from ...references import load_references
    from ..references import record_path

    roots: list[str] = []
    for key, entry in load_references(study).items():
        record_id = entry.get("record_id") if isinstance(entry, dict) else None
        if isinstance(record_id, str) and record_path(repo, record_id).is_file():
            roots.append(f"ref:{key}")
    return sorted(roots)


def _run_knowledge_promote(args: argparse.Namespace) -> int:
    from .. import knowledge as gk
    from ..chronology import git_head

    try:
        study, _contract, repo, study_name = _knowledge_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    if bool(args.method) == bool(args.claim):
        return _error("promote takes exactly one of --claim <id> and --method")
    scope, problems = _parse_scope(list(args.scope))
    if problems:
        return _error("; ".join(problems))

    if not args.method:
        problem = _lock_verification_problem(study)
        if problem is not None:
            return _refuse(
                "a promotion imports a VERIFIED claim, and `klein claims verify` does not "
                f"pass on {study_name} right now: {problem}"
            )
    try:
        # Every failure here is `--claim` malformed, `--claim` naming a claim the
        # lock does not carry, or a missing method_card.md: exit 1, nothing said.
        source = gk.promote_source(study, repo, claim=args.claim, method=bool(args.method))
    except WorkflowError as exc:
        return _error(str(exc))

    roots = list(source.evidence_roots)
    if args.method:
        roots = _method_roots(study, repo)
        if not roots:
            return _refuse(
                "a method promotion pins its reference records: no references.yaml row names "
                "a record_id with a record under knowledge/references/ "
                "(`klein generation reference record`)"
            )

    snapshot = gk.snapshot_on_disk(repo)
    duplicate = gk.duplicate_of(snapshot, roots)
    if duplicate is not None:
        return _refuse(
            f"already promoted as {duplicate}: the store deduplicates by EVIDENCE ROOTS, "
            "never by citation count — repeating one lesson is not a second piece of evidence"
        )

    object_id = gk.next_object_id(snapshot)
    obj = gk.build_object(
        object_id=object_id,
        object_type=source.object_type,
        origin_repo=_origin_repo(repo),
        study=study_name,
        commit=git_head(repo),
        lock_git_head=source.lock_git_head,
        source_path=source.source_path,
        source_hash=source.source_hash,
        claim_id=source.claim_id,
        text=source.text,
        claim_class=source.claim_class,
        strength=source.strength,
        scope=scope,
        tags=list(args.tags),
        evidence_roots=roots,
        dependencies=list(args.dependency),
    )
    problems = gk.object_problems(obj)
    if problems:
        return _refuse("; ".join(problems))

    sha = gk.write_store_object(repo, obj)
    event = gk.append_store_event(
        repo,
        "promote",
        target=object_id,
        study=study_name,
        object_sha=sha,
        evidence_ids=roots,
        rationale=args.rationale,
        testimony_fields=_testimony_fields(args),
    )
    _commit_store(
        repo,
        f"klein: knowledge promote {object_id} ({study_name})",
        gk.objects_dir(repo) / f"{sha}.json",
        gk.events_path(repo),
    )
    print(
        f"{event['id']} promoted {object_id} ({source.object_type}) from "
        f"{source.claim_id or source.source_path} — object {sha[:12]}…"
    )
    print(f"  class {obj['class']!r}, strength {obj['strength']!r} — copied, never raised")
    print("  evidence roots: " + (", ".join(roots) or "none"))
    return 0


def _run_knowledge_contest(args: argparse.Namespace) -> int:
    from .. import knowledge as gk

    try:
        study, _contract, repo, study_name = _knowledge_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    snapshot = gk.snapshot_on_disk(repo)
    target = str(args.target)
    if target not in snapshot.objects:
        return _error(f"no object {target} in the store (`klein generation knowledge show`)")
    problem = _lock_verification_problem(study)
    if problem is not None:
        return _refuse(
            "a contest rests on evidence this study earned, and `klein claims verify` does "
            f"not pass on {study_name} right now: {problem}"
        )
    problems = gk.contest_evidence_problems(study, list(args.evidence))
    if problems:
        return _refuse("; ".join(problems))

    event = gk.append_store_event(
        repo,
        "contest",
        target=target,
        study=study_name,
        evidence_ids=list(args.evidence),
        rationale=str(args.rationale),
        testimony_fields=_testimony_fields(args),
    )
    _commit_store(
        repo,
        f"klein: knowledge contest {target} ({study_name})",
        gk.events_path(repo),
    )
    print(f"{event['id']} contested {target} with {', '.join(args.evidence)}")
    print("  the object stays, the contest stays, and every later query carries both")
    return 0


def _run_knowledge_resolve(args: argparse.Namespace) -> int:
    from .. import knowledge as gk

    try:
        _study_dir, _contract, repo, study_name = _knowledge_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    snapshot = gk.snapshot_on_disk(repo)
    target = str(args.target)
    if target not in snapshot.objects:
        return _error(f"no object {target} in the store (`klein generation knowledge show`)")
    contests, _resolutions = gk.closure(snapshot, target)

    event = gk.append_store_event(
        repo,
        "resolve",
        target=target,
        study=study_name,
        rationale=str(args.rationale),
        resolution=str(args.outcome),
        testimony_fields=_testimony_fields(args),
    )
    _commit_store(
        repo,
        f"klein: knowledge resolve {target} ({args.outcome})",
        gk.events_path(repo),
    )
    print(f"{event['id']} resolved {target}: {args.outcome}")
    if not contests:
        print("  note: nothing had contested this object")
    if args.outcome == "withdrawn":
        print("  withdrawn keeps the object and attaches the withdrawal — nothing is deleted")
    return 0


def _run_knowledge_query(args: argparse.Namespace) -> int:
    from ...primitives import sha256_file
    from .. import knowledge as gk
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, commit_generation, write_object

    try:
        study, _contract, repo, study_name = _knowledge_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    if args.limit is not None and args.limit < 1:
        return _error("--limit is a positive count")
    head = git_head(repo)
    snapshot = gk.snapshot_at(repo, head) if head else None
    if snapshot is None:
        snapshot = gk.snapshot_on_disk(repo)
    hits, truncated = gk.hits_for(
        snapshot, tags=list(args.tags), text=args.text, limit=args.limit
    )
    known = [str(hit["id"]) for hit in hits]
    decision: list[dict[str, Any]] = []
    problems: list[str] = []
    for pairs, verdict in ((list(args.use), "use"), (list(args.reject), "reject")):
        rows, bad = gk.parse_decisions(pairs, verdict, known)
        decision.extend(rows)
        problems.extend(bad)
    if problems:
        return _error("; ".join(problems))

    contract_path = study / "study.yaml"
    receipt = gk.query_object(
        study=study_name,
        contract_draft_sha256=sha256_file(contract_path) if contract_path.is_file() else None,
        store_head=head,
        typed_query={"tags": list(args.tags), "text": args.text},
        hits=hits,
        decision=decision,
        limit=args.limit,
        truncated=truncated,
    )
    sha = write_object(study, receipt)
    event = append_event(
        study,
        gk.QUERY_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=head,
        payload_sha256=sha,
        testimony_fields=_testimony_fields(args),
        hits=len(hits),
        no_match=not hits,
    )
    commit_generation(
        study,
        f"klein: knowledge query ({study_name})",
        paths=("generation/events.jsonl", "generation/objects"),
    )
    print(
        f"{event['id']} knowledge query at store head {str(head or '')[:12] or 'none'} "
        f"({gk.RETRIEVER_VERSION}) — object {sha[:12]}…"
    )
    if not hits:
        print(
            "  no match: the store holds nothing that overlaps this query — CONSULT cites "
            "this receipt as the explicit no-match"
        )
        return 0
    decided = {row["id"] for row in decision}
    for hit in hits:
        obj = snapshot.objects.get(str(hit["id"]), {})
        print(
            f"  {hit['id']} (score {hit['score']}) {obj.get('study')}: {obj.get('text')} "
            f"[{obj.get('strength')}]"
        )
        if hit["contests"]:
            print("    contested by " + ", ".join(hit["contests"]))
        if hit["resolutions"]:
            print("    resolved by " + ", ".join(hit["resolutions"]))
    if truncated:
        print(f"  --limit {args.limit} truncated the hit list; the receipt records that")
    undecided = [hit["id"] for hit in hits if hit["id"] not in decided]
    if undecided:
        print(
            "  undecided: "
            + ", ".join(undecided)
            + " — `klein generation knowledge decide --use <id>=<why> --reject <id>=<why>` "
            "before the CONSULT ack, or `generation verify` FAILs"
        )
    return 0


def _run_knowledge_decide(args: argparse.Namespace) -> int:
    from .. import knowledge as gk
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, commit_generation, read_events, write_object

    try:
        study, _contract, repo, study_name = _knowledge_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    events = read_events(study)
    rows = gk.queries(study, events, gk.QUERY_TYPE)
    if not rows:
        return _error("no knowledge_queried receipt to decide on — run `knowledge query` first")
    query_event, receipt = rows[0]
    known = [str(hit.get("id")) for hit in receipt.get("hits") or []]
    decision: list[dict[str, Any]] = []
    problems: list[str] = []
    for pairs, verdict in ((list(args.use), "use"), (list(args.reject), "reject")):
        parsed, bad = gk.parse_decisions(pairs, verdict, known)
        decision.extend(parsed)
        problems.extend(bad)
    if problems:
        return _error("; ".join(problems))
    if not decision:
        return _error("decide records at least one --use K#=reason or --reject K#=reason")

    obj = gk.decision_object(
        study=study_name,
        receipt_sha=str(query_event.get("payload_sha256")),
        decision=decision,
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gk.DECISION_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[str(query_event.get("id"))],
        testimony_fields=_testimony_fields(args),
        decided=len(decision),
    )
    commit_generation(
        study,
        f"klein: knowledge decide ({study_name})",
        paths=("generation/events.jsonl", "generation/objects"),
    )
    print(f"{event['id']} recorded {len(decision)} decision(s) — object {sha[:12]}…")
    for row in decision:
        print(f"  {row['id']}: {row['decision']} — {row['reason']}")
    return 0


def _run_knowledge_show(args: argparse.Namespace) -> int:
    from .. import knowledge as gk
    from ..chronology import repo_for

    try:
        study, _contract = _load(args)
    except WorkflowError as exc:
        return _error(str(exc))
    repo = repo_for(study)
    if repo is None:
        return _error("the knowledge store is repo-level and this study is not in a repository")
    snapshot = gk.snapshot_on_disk(repo)
    if not snapshot.objects:
        print("the knowledge store is empty — a query against it records an explicit no-match")
        return 0
    wanted = [str(args.target)] if args.target else snapshot.ids
    for object_id in wanted:
        obj = snapshot.objects.get(object_id)
        if obj is None:
            return _error(f"no object {object_id} in the store")
        contests, resolutions = gk.closure(snapshot, object_id)
        print(
            f"{object_id} [{obj.get('type')}] {obj.get('study')} — {obj.get('text')} "
            f"({obj.get('class')}, {obj.get('strength')})"
        )
        print(f"  tags: {', '.join(obj.get('tags') or []) or 'none'}")
        print(f"  evidence roots: {', '.join(obj.get('evidence_roots') or []) or 'none'}")
        for key, value in (obj.get("scope") or {}).items():
            if value:
                printable = ", ".join(value) if isinstance(value, list) else value
                print(f"  scope.{key}: {printable}")
        for event in snapshot.events:
            if event.get("target") != object_id or event.get("operation") == "promote":
                continue
            label = event.get("operation")
            if event.get("resolution"):
                label = f"{label} ({event.get('resolution')})"
            print(f"  {event.get('id')} {label} by {event.get('study')}: {event.get('rationale')}")
        if resolutions and not contests:
            print("  resolved without a contest on the record")
    return 0
