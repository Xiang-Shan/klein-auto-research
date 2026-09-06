"""The ``knowledge`` capability — cross-study transactions over pinned evidence.

`knowledge/` already held the framework's durable lessons as markdown with typed
claim citations, and **that convention stays exactly what it was**: the human
surface, greppable, written and read by people.  What it cannot do is answer
three machine questions — *did this study look?*, *did it see the refutation?*,
*was the imported claim stronger than the one that was earned?* — and those are
the questions a knowledge store has to answer before "we build on prior work"
means anything.

So this module adds a second, machine surface beside the markdown, at the
REPOSITORY level because knowledge is not a fact about one study:

``knowledge/objects/<sha256>.json``
    Write-once, content-addressed snapshots.  A promoted claim carries the
    source study, the commit whose ``claims.lock`` it was read from, that file's
    hash, and — copied VERBATIM — the claim's ``class``, ``strength`` and
    ``evidence_roots``.  **A promotion never strengthens.**  It creates
    availability, not evidence: the same sentence, reachable from another study,
    at exactly the standing it earned where it was made.

``knowledge/events.jsonl``
    The store's own append-only hash chain — ``promote``, ``contest``,
    ``resolve``.  Nothing is ever deleted.  A refutation is a ``contest`` that
    hangs off the object forever; an adjudication is a ``resolve`` that hangs
    off both.  ``withdrawn`` keeps the object and attaches the withdrawal.

**Retrieval is deterministic and replayable, and that is the whole point.**
``lex-1`` is case-folded token overlap over each object's text, tags and scope
values — no embedding, no model, no ranking service — so ``klein generation
verify`` can re-run the identical query against the store as it stood at the
receipt's ``store_head`` (``git show <head>:knowledge/objects/…``) and compare.
A hit that was reachable and is missing from the receipt, or a contest that was
attached and is missing from the closure, is a FAIL: *suppressed hit or
contest*.  The receipt returns COMPLETE hits — every object with any overlap, no
top-k — unless the driver passes ``--limit``, which is recorded in the receipt
so the truncation is visible rather than convenient.

**Contest closure travels with the hit.**  The buried-refutation failure mode is
not that the refutation is unfindable; it is that the refutation ranks poorly
against the query that found the claim.  So every hit carries the ids of the
contests and resolutions attached to it, whatever they would have scored.

**A failed transfer is not a contest.**  A prediction that did not hold
in a new regime is a prediction verdict, recorded in the citing study's ledger.
A contest requires a CLAIM from the citing study's verified lock that
contradicts the target's scope; ``contest`` refuses evidence made of prediction
ids alone.

**Dedupe by evidence roots, never by citation count.**  Ten studies repeating one
lesson are one piece of evidence; an object whose ``evidence_roots`` already
exist in the store is refused with the id that already holds them.

What this does NOT establish: that the scope tags are honest, that the retrieval
corpus was adequate, that a contest is right, or that a resolution settled
anything.  Applicability, semantic contradiction and adjudication are agent and
reviewer judgement — the mechanism only makes them visible, ordered and hard to
quietly drop.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..errors import WorkflowError
from ..primitives import (
    atomic_write_text,
    canonical_json,
    sha256_bytes,
    utc_now,
)
from ..transaction import git, git_blob, relative
from .envelope import GENERATION_SCHEMA, testimony
from .ledger import read_object
from .registry import Capability, FamilyContext
from .verify import Check

__all__ = [
    "CAPABILITY",
    "CAPABILITY_NAME",
    "DECISION_TYPE",
    "EVENTS_REL",
    "OBJECTS_REL",
    "OPERATIONS",
    "QUERY_TYPE",
    "RESOLUTIONS",
    "RETRIEVER_VERSION",
    "Snapshot",
    "append_store_event",
    "build_object",
    "closure",
    "decision_object",
    "effective_decisions",
    "hits_for",
    "next_object_id",
    "object_problems",
    "promote_source",
    "query_object",
    "queries",
    "snapshot_at",
    "snapshot_on_disk",
    "store_chain_problems",
    "store_is_local",
    "store_problems",
    "tokens",
    "verify_family",
    "write_store_object",
]

CAPABILITY_NAME = "knowledge"

#: Repo-relative homes.  The markdown beside them is untouched by every verb here.
OBJECTS_REL = "knowledge/objects"
EVENTS_REL = "knowledge/events.jsonl"

#: The retrieval algorithm the receipt pins.  A new algorithm is a NEW version
#: string, never an edit to this one: historical receipts replay under the rules
#: they were taken under.
RETRIEVER_VERSION = "lex-1"

#: Extension event types written into the STUDY's chain (not the store's).
QUERY_TYPE = "knowledge_queried"
DECISION_TYPE = "knowledge_decided"

OPERATIONS: tuple[str, ...] = ("promote", "contest", "resolve")
RESOLUTIONS: tuple[str, ...] = ("upheld", "scoped", "withdrawn")
OBJECT_TYPES: tuple[str, ...] = ("claim", "method")
DECISIONS: tuple[str, ...] = ("use", "reject")

ID_RE = re.compile(r"^K(\d+)$")
CLAIM_REF_RE = re.compile(r"^(?P<study>[A-Za-z0-9._-]+)#(?P<claim>C\d+)$")
CLAIM_ID_RE = re.compile(r"^C\d+$")
_TOKEN_RE = re.compile(r"[a-z0-9]+")

#: The scope fields an object carries.  Lists and scalars both allowed; the retriever
#: reads their text, the reader reads their meaning.
SCOPE_FIELDS: tuple[str, ...] = (
    "population",
    "measurement_regime",
    "intervention",
    "assumptions",
    "exclusions",
)


# --------------------------------------------------------------------------
# store paths and the snapshot
# --------------------------------------------------------------------------


def objects_dir(repo: Path) -> Path:
    return repo / OBJECTS_REL


def events_path(repo: Path) -> Path:
    return repo / EVENTS_REL


@dataclass(frozen=True)
class Snapshot:
    """The store as it stood somewhere: on disk, or at one commit.

    ``objects`` is keyed by the object's ``K`` id; ``shas`` gives each id's
    content address.  ``events`` is the store chain in order.  Everything the
    retriever and the replay need, and nothing that depends on a clock.
    """

    objects: dict[str, dict[str, Any]] = field(default_factory=dict)
    shas: dict[str, str] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ids(self) -> list[str]:
        return sorted(self.objects, key=_id_number)


def _id_number(object_id: str) -> int:
    match = ID_RE.match(str(object_id))
    return int(match.group(1)) if match else 0


def _parse_object(text: str, where: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except ValueError as exc:
        raise WorkflowError(f"invalid knowledge object {where}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"knowledge object {where} is not an object")
    return value


def _parse_events(text: str, where: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except ValueError as exc:
            raise WorkflowError(f"{where} line {lineno} is invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise WorkflowError(f"{where} line {lineno} is not an object")
        events.append(value)
    return events


def snapshot_on_disk(repo: Path) -> Snapshot:
    """The store in the working tree.  An empty store is a valid store."""
    objects: dict[str, dict[str, Any]] = {}
    shas: dict[str, str] = {}
    directory = objects_dir(repo)
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            obj = _parse_object(path.read_text(encoding="utf-8"), path.name)
            object_id = str(obj.get("id"))
            objects[object_id] = obj
            shas[object_id] = path.stem
    events: list[dict[str, Any]] = []
    path = events_path(repo)
    if path.is_file():
        events = _parse_events(path.read_text(encoding="utf-8"), EVENTS_REL)
    return Snapshot(objects, shas, events)


def snapshot_at(repo: Path, commit: str) -> Snapshot | None:
    """The store as of one commit, or None when the commit does not resolve.

    Read through ``git show`` rather than a checkout: verification must be able
    to replay a query against a store head that HEAD has long since moved past,
    without touching the working tree.
    """
    resolved = git(repo, ["cat-file", "-e", f"{commit}^{{commit}}"], check=False)
    if resolved.returncode:
        return None
    listing = git(
        repo, ["ls-tree", "-r", "--name-only", commit, "--", OBJECTS_REL], check=False
    )
    objects: dict[str, dict[str, Any]] = {}
    shas: dict[str, str] = {}
    if listing.returncode == 0:
        for line in listing.stdout.splitlines():
            rel = line.strip()
            if not rel.endswith(".json"):
                continue
            blob = git_blob(repo, commit, rel)
            if blob is None:
                continue
            obj = _parse_object(blob.decode("utf-8"), rel)
            object_id = str(obj.get("id"))
            objects[object_id] = obj
            shas[object_id] = Path(rel).stem
    blob = git_blob(repo, commit, EVENTS_REL)
    events = _parse_events(blob.decode("utf-8"), EVENTS_REL) if blob is not None else []
    return Snapshot(objects, shas, events)


# --------------------------------------------------------------------------
# the store chain
# --------------------------------------------------------------------------


def _event_hash(body: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in body.items() if key != "event_hash"}
    return sha256_bytes(canonical_json(payload).encode())


def store_chain_problems(events: Sequence[Mapping[str, Any]]) -> list[str]:
    """Every way the store's chain can be broken, one line each."""
    problems: list[str] = []
    previous: str | None = None
    for index, event in enumerate(events, start=1):
        label = f"event {index}"
        if event.get("schema") != GENERATION_SCHEMA:
            problems.append(f"{label}: schema is {event.get('schema')!r}")
        if event.get("sequence") != index:
            problems.append(f"{label}: sequence is {event.get('sequence')!r}")
        if event.get("id") != f"KE{index:04d}":
            problems.append(f"{label}: id is {event.get('id')!r}")
        if event.get("previous_hash") != previous:
            problems.append(f"{label}: previous_hash does not match")
        if event.get("operation") not in OPERATIONS:
            problems.append(f"{label}: unknown operation {event.get('operation')!r}")
        given = event.get("event_hash")
        if given != _event_hash(event):
            problems.append(f"{label}: event_hash does not match content")
        previous = given if isinstance(given, str) else None
    return problems


def append_store_event(
    repo: Path,
    operation: str,
    *,
    target: str,
    study: str,
    object_sha: str | None = None,
    evidence_ids: Sequence[str] = (),
    rationale: str | None = None,
    resolution: str | None = None,
    testimony_fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Seal one transaction onto the tail of the store's chain."""
    snapshot = snapshot_on_disk(repo)
    sequence = len(snapshot.events) + 1
    previous = snapshot.events[-1].get("event_hash") if snapshot.events else None
    body: dict[str, Any] = {
        "schema": GENERATION_SCHEMA,
        "id": f"KE{sequence:04d}",
        "sequence": sequence,
        "operation": operation,
        "target": target,
        "study": study,
        "object_sha": object_sha,
        "evidence_ids": list(evidence_ids),
        "rationale": rationale,
        "resolution": resolution,
        **testimony(testimony_fields),
        "created_at": utc_now(),
        "previous_hash": previous if isinstance(previous, str) else None,
    }
    body["event_hash"] = _event_hash(body)
    path = events_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(body) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return body


def write_store_object(repo: Path, obj: Mapping[str, Any]) -> str:
    """Store one object write-once; the file name IS its sha256."""
    text = canonical_json(obj) + "\n"
    sha = sha256_bytes(text.encode())
    path = objects_dir(repo) / f"{sha}.json"
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return sha
    atomic_write_text(path, text)
    return sha


def next_object_id(snapshot: Snapshot) -> str:
    """``K<n>``, monotonic across the whole store — ids are never recycled."""
    highest = max((_id_number(object_id) for object_id in snapshot.objects), default=0)
    return f"K{highest + 1}"


# --------------------------------------------------------------------------
# objects
# --------------------------------------------------------------------------


def build_object(
    *,
    object_id: str,
    object_type: str,
    origin_repo: str,
    study: str,
    commit: str | None,
    lock_git_head: str | None,
    source_path: str,
    source_hash: str,
    claim_id: str | None,
    text: str,
    claim_class: str | None,
    strength: str | None,
    scope: Mapping[str, Any],
    tags: Sequence[str],
    evidence_roots: Sequence[str],
    dependencies: Sequence[str] = (),
) -> dict[str, Any]:
    """One store object.  ``class``/``strength``/``evidence_roots`` are copies."""
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "knowledge",
        "id": object_id,
        "type": object_type,
        "origin_repo": origin_repo,
        "study": study,
        "commit": commit,
        "lock_git_head": lock_git_head,
        "source_path": source_path,
        "source_hash": source_hash,
        "claim_id": claim_id,
        "text": text,
        "class": claim_class,
        "strength": strength,
        "scope": {key: scope.get(key) for key in SCOPE_FIELDS},
        "tags": sorted({str(tag).strip().casefold() for tag in tags if str(tag).strip()}),
        "evidence_roots": list(evidence_roots),
        "dependencies": list(dependencies),
    }


def object_problems(obj: Mapping[str, Any]) -> list[str]:
    """Every way an object contradicts itself.  Checked at write and at verify."""
    problems: list[str] = []
    if obj.get("schema") != GENERATION_SCHEMA:
        problems.append(f"schema is {obj.get('schema')!r}")
    if obj.get("kind") != "knowledge":
        problems.append(f"kind is {obj.get('kind')!r}")
    if not ID_RE.match(str(obj.get("id"))):
        problems.append(f"id {obj.get('id')!r} must match {ID_RE.pattern}")
    if obj.get("type") not in OBJECT_TYPES:
        problems.append(f"type {obj.get('type')!r} must be one of {', '.join(OBJECT_TYPES)}")
    for name in ("study", "source_path", "source_hash", "text"):
        value = obj.get(name)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{name} is required")
    scope = obj.get("scope")
    if not isinstance(scope, Mapping):
        problems.append("scope must be a mapping")
    for name in ("tags", "evidence_roots", "dependencies"):
        value = obj.get(name)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            problems.append(f"{name} must be a list of strings")
    if obj.get("type") == "claim" and not obj.get("evidence_roots"):
        problems.append(
            "a promoted claim carries the evidence roots it was earned with — "
            "dedupe is by roots, never by citation count"
        )
    return problems


def evidence_key(roots: Iterable[str]) -> tuple[str, ...]:
    """The dedupe key: the evidence roots as a set, order-insensitive."""
    return tuple(sorted({str(root) for root in roots}))


def duplicate_of(snapshot: Snapshot, roots: Iterable[str]) -> str | None:
    """The id that already holds these evidence roots, if any."""
    key = evidence_key(roots)
    if not key:
        return None
    for object_id in snapshot.ids:
        obj = snapshot.objects[object_id]
        if evidence_key(obj.get("evidence_roots") or ()) == key:
            return object_id
    return None


# --------------------------------------------------------------------------
# lex-1: deterministic retrieval
# --------------------------------------------------------------------------


def tokens(value: Any) -> set[str]:
    """Case-folded alphanumeric tokens of any scalar or nested list of scalars."""
    if value is None:
        return set()
    if isinstance(value, str):
        return set(_TOKEN_RE.findall(value.casefold()))
    if isinstance(value, Mapping):
        found: set[str] = set()
        for item in value.values():
            found |= tokens(item)
        return found
    if isinstance(value, Sequence):
        found = set()
        for item in value:
            found |= tokens(item)
        return found
    return set(_TOKEN_RE.findall(str(value).casefold()))


def object_tokens(obj: Mapping[str, Any]) -> set[str]:
    """What ``lex-1`` matches against: text, tags and scope values.

    Deliberately NOT the study id, the commit, or the evidence roots: those are
    provenance, and matching on them would let a query find an object by naming
    where it came from rather than what it says.
    """
    return tokens(obj.get("text")) | tokens(obj.get("tags")) | tokens(obj.get("scope"))


def query_tokens(tags: Sequence[str], text: str | None) -> set[str]:
    return tokens(list(tags)) | tokens(text)


def closure(snapshot: Snapshot, object_id: str) -> tuple[list[str], list[str]]:
    """``(contest event ids, resolution event ids)`` attached to one object.

    Whatever they would have SCORED.  A refutation that ranks poorly against the
    query that found the claim is exactly the failure this exists to prevent.
    """
    contests = [
        str(event.get("id"))
        for event in snapshot.events
        if event.get("operation") == "contest" and event.get("target") == object_id
    ]
    resolutions = [
        str(event.get("id"))
        for event in snapshot.events
        if event.get("operation") == "resolve" and event.get("target") == object_id
    ]
    return contests, resolutions


def hits_for(
    snapshot: Snapshot,
    *,
    tags: Sequence[str] = (),
    text: str | None = None,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """``(hits, truncated)`` — COMPLETE unless ``limit`` says otherwise.

    Score is the size of the token overlap; ties break by object id, ascending,
    so two runs of the same query produce the same list forever.
    """
    wanted = query_tokens(tags, text)
    scored: list[tuple[int, int, str]] = []
    for object_id in snapshot.ids:
        overlap = wanted & object_tokens(snapshot.objects[object_id])
        if overlap:
            scored.append((-len(overlap), _id_number(object_id), object_id))
    scored.sort()
    truncated = limit is not None and len(scored) > limit
    if limit is not None:
        scored = scored[:limit]
    hits: list[dict[str, Any]] = []
    for negative, _number, object_id in scored:
        contests, resolutions = closure(snapshot, object_id)
        hits.append(
            {
                "id": object_id,
                "score": -negative,
                "object_sha": snapshot.shas.get(object_id),
                "contests": contests,
                "resolutions": resolutions,
            }
        )
    return hits, truncated


# --------------------------------------------------------------------------
# the query receipt
# --------------------------------------------------------------------------


def query_object(
    *,
    study: str,
    contract_draft_sha256: str | None,
    store_head: str | None,
    typed_query: Mapping[str, Any],
    hits: Sequence[Mapping[str, Any]],
    decision: Sequence[Mapping[str, Any]],
    limit: int | None,
    truncated: bool,
) -> dict[str, Any]:
    """The consultation receipt.  ``no_match`` is a RESULT, never an omission."""
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "knowledge_query",
        "study": study,
        "contract_draft_sha256": contract_draft_sha256,
        "store_head": store_head,
        "retriever_version": RETRIEVER_VERSION,
        "typed_query": {
            "tags": sorted({str(tag).strip().casefold() for tag in typed_query.get("tags") or () if str(tag).strip()}),
            "text": typed_query.get("text") or "",
        },
        "hits": [dict(hit) for hit in hits],
        "decision": [dict(entry) for entry in decision],
        "limit": limit,
        "truncated": bool(truncated),
        "no_match": not hits,
    }


def decision_object(
    *, study: str, receipt_sha: str, decision: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """A later decision on hits an earlier receipt left open.  Append-only."""
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "knowledge_decision",
        "study": study,
        "receipt_sha256": receipt_sha,
        "decision": [dict(entry) for entry in decision],
    }


def parse_decisions(
    pairs: Sequence[str], verdict: str, known: Sequence[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """``K1=reason`` pairs into decision rows, plus the problems they carry."""
    rows: list[dict[str, Any]] = []
    problems: list[str] = []
    for pair in pairs:
        object_id, _, reason = str(pair).partition("=")
        object_id = object_id.strip()
        reason = reason.strip()
        if not ID_RE.match(object_id):
            problems.append(f"--{verdict} {pair!r}: {object_id!r} is not a K id")
            continue
        if not reason:
            problems.append(
                f"--{verdict} {pair!r}: a decision carries a reason "
                f"(`--{verdict} {object_id}=<why>`)"
            )
            continue
        if known and object_id not in known:
            problems.append(f"--{verdict} {object_id}: not among the hits {', '.join(known)}")
            continue
        rows.append({"id": object_id, "decision": verdict, "reason": reason})
    return rows, problems


def queries(
    study_dir: Path, events: Sequence[Mapping[str, Any]], event_type: str = QUERY_TYPE
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    """``[(event, object)]`` for one extension event type, in chain order."""
    rows: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    for event in events:
        if event.get("type") != event_type:
            continue
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            rows.append((event, read_object(study_dir, sha)))
        except WorkflowError:
            continue
    return rows


def effective_decisions(
    study_dir: Path, events: Sequence[Mapping[str, Any]], receipt_sha: str | None
) -> dict[str, dict[str, Any]]:
    """``{object id: decision row}`` — the receipt's own, then later decisions.

    A decision recorded afterwards is an ADDITION to the record, never an edit
    of it: the receipt keeps whatever it said, and `knowledge decide` files the
    rest under its own event.
    """
    merged: dict[str, dict[str, Any]] = {}
    for _event, obj in queries(study_dir, events, QUERY_TYPE):
        for row in obj.get("decision") or ():
            if isinstance(row, Mapping) and isinstance(row.get("id"), str):
                merged[row["id"]] = dict(row)
    for _event, obj in queries(study_dir, events, DECISION_TYPE):
        if receipt_sha is not None and obj.get("receipt_sha256") != receipt_sha:
            continue
        for row in obj.get("decision") or ():
            if isinstance(row, Mapping) and isinstance(row.get("id"), str):
                merged[row["id"]] = dict(row)
    return merged


# --------------------------------------------------------------------------
# promotion sources (read-only over claims.lock / method_card.md)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Source:
    """What a promotion copies from, and the standing it may not exceed."""

    object_type: str
    source_path: str
    source_hash: str
    claim_id: str | None
    text: str
    claim_class: str | None
    strength: str | None
    evidence_roots: tuple[str, ...]
    lock_git_head: str | None


def promote_source(
    study_dir: Path, repo: Path, *, claim: str | None, method: bool
) -> Source:
    """The verbatim source of a promotion — or the reason there is none.

    The claim's ``class``, ``strength`` and ``evidence`` are read straight out of
    the lock and copied without interpretation.  Nothing here can raise them,
    because nothing here writes them.
    """
    from ..claims import claims_map, detect_lock_schema, load_lock
    from ..primitives import sha256_file

    if method:
        path = study_dir / "method_card.md"
        if not path.is_file():
            raise WorkflowError("method promotion needs method_card.md in the study")
        text = path.read_text(encoding="utf-8")
        heading = next(
            (line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")),
            study_dir.name,
        )
        return Source(
            object_type="method",
            source_path=relative(repo, path),
            source_hash=sha256_file(path),
            claim_id=None,
            text=heading,
            claim_class=None,
            strength=None,
            evidence_roots=(),
            lock_git_head=None,
        )

    lock = load_lock(study_dir)
    schema = detect_lock_schema(lock)
    entries = claims_map(lock, schema)
    study_name = str(lock.get("study_id") or study_dir.name)
    wanted = str(claim)
    match = CLAIM_REF_RE.match(wanted)
    local = match.group("claim") if match else wanted
    if match and match.group("study") != study_name:
        raise WorkflowError(
            f"--claim {wanted!r} names {match.group('study')!r}, but --study is {study_name!r}: "
            "a study promotes the claims IT earned"
        )
    if not CLAIM_ID_RE.match(local):
        raise WorkflowError(f"--claim {wanted!r} is neither `Cn` nor `<study>#Cn`")
    entry = entries.get(local)
    if not isinstance(entry, Mapping):
        raise WorkflowError(
            f"claim {local} is not in {study_dir.name}'s claims.lock "
            "(a promotion imports a claim that was actually made)"
        )
    return Source(
        object_type="claim",
        source_path=relative(repo, study_dir / "claims.lock"),
        source_hash=sha256_file(study_dir / "claims.lock"),
        claim_id=f"{lock.get('study_id') or study_dir.name}#{local}",
        text=str(entry.get("claim") or ""),
        claim_class=entry.get("class"),
        strength=entry.get("strength"),
        evidence_roots=tuple(str(item) for item in (entry.get("evidence") or [])),
        lock_git_head=lock.get("git_head") if isinstance(lock.get("git_head"), str) else None,
    )


def lock_claim_at(
    repo: Path, commit: str, source_path: str, claim_id: str | None
) -> Mapping[str, Any] | None:
    """One claim entry read out of a lock blob at a commit, or None."""
    if claim_id is None:
        return None
    blob = git_blob(repo, commit, source_path)
    return None if blob is None else _claim_from_lock(blob, claim_id)


def _claim_from_lock(blob: bytes, claim_id: str) -> dict[str, Any] | None:
    """One claim entry out of the bytes of a ``claims.lock``, or None."""
    try:
        lock = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(lock, Mapping):
        return None
    claims = lock.get("claims")
    local = claim_id.split("#")[-1]
    entry = claims.get(local) if isinstance(claims, Mapping) else None
    return dict(entry) if isinstance(entry, Mapping) else None


def contest_evidence_problems(
    study_dir: Path, evidence_ids: Sequence[str]
) -> list[str]:
    """Why this evidence cannot carry a contest.

    Every id must resolve in the citing study's own verified lock, and at least
    one must be a CLAIM: a prediction that did not transfer is a prediction
    verdict in that study's ledger, not a refutation of somebody else's claim.
    """
    from ..claims import claims_map, detect_lock_schema, load_lock

    if not evidence_ids:
        return ["a contest cites the evidence that contradicts the target"]
    lock = load_lock(study_dir)
    schema = detect_lock_schema(lock)
    claims = claims_map(lock, schema)
    study_name = str(lock.get("study_id") or study_dir.name)
    artifacts = lock.get("artifacts") if isinstance(lock.get("artifacts"), Mapping) else {}
    cited: set[str] = set()
    for entry in claims.values():
        if isinstance(entry, Mapping):
            cited |= {str(item) for item in (entry.get("evidence") or [])}

    problems: list[str] = []
    claim_ids: list[str] = []
    for raw in evidence_ids:
        item = str(raw)
        match = CLAIM_REF_RE.match(item)
        local = match.group("claim") if match else item
        if CLAIM_ID_RE.match(local):
            if match and match.group("study") != study_name:
                problems.append(
                    f"evidence {item!r}: a contest rests on a claim THIS study earned, and "
                    f"this study is {study_name!r}"
                )
            elif local not in claims:
                problems.append(f"evidence {item!r}: no such claim in this study's claims.lock")
            else:
                claim_ids.append(local)
            continue
        if item.startswith("art:"):
            if item[len("art:") :] not in artifacts:
                problems.append(f"evidence {item!r}: not a pinned artifact alias in the lock")
            continue
        if item in cited:
            continue
        problems.append(
            f"evidence {item!r}: no claim in this study's lock cites it — a contest rests "
            "on evidence this study actually earned"
        )
    if not claim_ids:
        problems.append(
            "a contest needs at least one CLAIM from this study's verified lock that "
            "contradicts the target's scope; a prediction that failed to transfer is a "
            "prediction verdict, not a contest"
        )
    return problems


# --------------------------------------------------------------------------
# the verify family
# --------------------------------------------------------------------------


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


def _warn(name: str, detail: str) -> Check:
    return Check(name, "WARN", detail)


def _pass(name: str, detail: str) -> Check:
    return Check(name, "PASS", detail)


def _query_order_problems(
    ctx: FamilyContext, first: tuple[Mapping[str, Any], dict[str, Any]]
) -> list[str]:
    """The consultation must precede the CONSULT ack, by sequence and ancestry.

    A store read AFTER the contract was acknowledged is a bibliography, not a
    consultation: it cannot have changed the question it was supposed to inform.
    """
    from .chronology import gate_events, introducing_commit, is_ancestor, study_event_commit

    gates = gate_events(ctx.core, "consult")
    if not gates:
        return []
    event, _obj = first
    anchor = event.get("core_anchor")
    anchor_sequence = anchor.get("sequence") if isinstance(anchor, Mapping) else None
    gate_sequence = gates[0].get("sequence")
    problems: list[str] = []
    if not isinstance(anchor_sequence, int) or not isinstance(gate_sequence, int):
        return ["the query receipt anchor or the consult gate record has no sequence"]
    if anchor_sequence >= gate_sequence:
        problems.append(
            f"the query receipt is anchored at core sequence {anchor_sequence}, at or after "
            f"the consult gate record (sequence {gate_sequence})"
        )
    repo = ctx.repo
    sha = event.get("payload_sha256")
    if repo is not None and isinstance(sha, str):
        query_commit = introducing_commit(
            repo, relative(repo, ctx.study_dir / "generation" / "objects" / f"{sha}.json")
        )
        gate_hash = gates[0].get("event_hash")
        gate_commit = (
            study_event_commit(repo, ctx.study_dir, str(gate_hash))
            if isinstance(gate_hash, str)
            else None
        )
        if query_commit is None:
            problems.append("the query receipt object is not committed, so ancestry cannot be read")
        elif gate_commit is not None and not is_ancestor(repo, query_commit, gate_commit):
            problems.append(
                f"the receipt commit {query_commit[:12]} is not an ancestor of the consult "
                f"gate commit {gate_commit[:12]}"
            )
    return problems


def _query_checks(
    ctx: FamilyContext, rows: list[tuple[Mapping[str, Any], dict[str, Any]]]
) -> list[Check]:
    name = "knowledge query"
    if not rows:
        return [
            _fail(
                name,
                "no knowledge_queried receipt — a study that declares `knowledge` consults "
                "the store BEFORE the CONSULT ack, and an empty store answers with an "
                "explicit no-match receipt (`klein generation knowledge query`)",
            )
        ]
    problems = _query_order_problems(ctx, rows[0])
    if problems:
        return [_fail(name, "; ".join(problems))]
    event, obj = rows[0]
    anchor = event.get("core_anchor")
    sequence = anchor.get("sequence") if isinstance(anchor, Mapping) else "?"
    hits = obj.get("hits") or []
    head = str(obj.get("store_head") or "")
    return [
        _pass(
            name,
            f"{len(hits)} hit(s) at core sequence {sequence}, before the consult gate, "
            f"over store head {head[:12] or 'none'} ({obj.get('retriever_version')})",
        )
    ]


def _decision_checks(
    ctx: FamilyContext, rows: list[tuple[Mapping[str, Any], dict[str, Any]]]
) -> list[Check]:
    name = "knowledge decisions"
    if not rows:
        return []
    event, obj = rows[0]
    hits = [str(hit.get("id")) for hit in obj.get("hits") or [] if isinstance(hit, Mapping)]
    if not hits:
        return [_pass(name, "no-match receipt: there was nothing to decide")]
    decisions = effective_decisions(
        ctx.study_dir, list(ctx.events), str(event.get("payload_sha256"))
    )
    problems: list[str] = []
    undecided = [object_id for object_id in hits if object_id not in decisions]
    if undecided:
        problems.append(
            "hits nobody decided: "
            + ", ".join(undecided)
            + " — record `--use <id>=<why>` or `--reject <id>=<why>` "
            "(`klein generation knowledge decide`)"
        )
    for object_id in hits:
        row = decisions.get(object_id)
        if row is None:
            continue
        if row.get("decision") not in DECISIONS:
            problems.append(f"{object_id}: decision {row.get('decision')!r} is not use/reject")
        elif not str(row.get("reason") or "").strip():
            problems.append(f"{object_id}: decided without a reason")
    if problems:
        return [_fail(name, "; ".join(problems))]
    used = sum(1 for row in decisions.values() if row.get("decision") == "use")
    return [
        _pass(
            name,
            f"every one of {len(hits)} hit(s) carries a use/reject reason ({used} used)",
        )
    ]


def store_is_local(repo: Path | None) -> bool:
    """Does the store this study consulted live in THIS repository?

    The distinction decides whether an unreplayable receipt is a broken record
    or an unreadable one.  A study carried to a clone that has no ``knowledge/``
    tree genuinely cannot replay its consultation, and saying FAIL there would
    punish a reader for standing in the wrong directory.  When the store IS
    here, the same symptom means the receipt does not describe it.
    """
    return repo is not None and (events_path(repo).is_file() or objects_dir(repo).is_dir())


def _replay_checks(
    ctx: FamilyContext, rows: list[tuple[Mapping[str, Any], dict[str, Any]]]
) -> list[Check]:
    """Re-run the recorded query against the store as it stood at ``store_head``."""
    name = "knowledge replay"
    if not rows or ctx.repo is None:
        return []
    local = store_is_local(ctx.repo)
    unreplayable = _fail if local else _warn
    foreign = (
        ""
        if local
        else " (this checkout carries no knowledge/ store, so the receipt cannot be read here)"
    )
    checks: list[Check] = []
    for _event, obj in rows:
        head = obj.get("store_head")
        if not isinstance(head, str) or not head:
            checks.append(
                unreplayable(
                    name,
                    "the receipt pins no store head; retrieval cannot be replayed, so "
                    "nothing establishes that these were the hits the store held" + foreign,
                )
            )
            continue
        if obj.get("retriever_version") != RETRIEVER_VERSION:
            checks.append(
                unreplayable(
                    name,
                    f"receipt taken under retriever {obj.get('retriever_version')!r}; this "
                    f"version replays {RETRIEVER_VERSION!r} only" + foreign,
                )
            )
            continue
        snapshot = snapshot_at(ctx.repo, head)
        if snapshot is None:
            checks.append(
                unreplayable(
                    name,
                    f"store head {head[:12]} does not resolve here — the receipt pins a "
                    "commit this repository does not have" + foreign,
                )
            )
            continue
        typed = obj.get("typed_query") or {}
        limit = obj.get("limit")
        expected, truncated = hits_for(
            snapshot,
            tags=list(typed.get("tags") or ()),
            text=typed.get("text"),
            limit=limit if isinstance(limit, int) else None,
        )
        recorded = [dict(hit) for hit in obj.get("hits") or []]
        if recorded != expected or bool(obj.get("truncated")) != truncated:
            checks.append(
                _fail(
                    name,
                    "suppressed hit or contest: replaying the recorded query at store head "
                    f"{head[:12]} returns {_summarise(expected)}, the receipt records "
                    f"{_summarise(recorded)}",
                )
            )
            continue
        if bool(obj.get("no_match")) != (not expected):
            checks.append(_fail(name, f"no_match is {obj.get('no_match')!r} but the replay found {len(expected)} hit(s)"))
            continue
        checks.append(
            _pass(
                name,
                f"{len(expected)} hit(s) and their contest closure reproduce at store head "
                f"{head[:12]}",
            )
        )
    return checks


def _summarise(hits: Sequence[Mapping[str, Any]]) -> str:
    if not hits:
        return "no hits"
    return "; ".join(
        f"{hit.get('id')}(score {hit.get('score')}, contests "
        f"{','.join(str(item) for item in hit.get('contests') or []) or 'none'})"
        for hit in hits
    )


def store_problems(snapshot: Snapshot) -> list[str]:
    """The store's own integrity, independent of any one study."""
    problems = store_chain_problems(snapshot.events)
    seen: dict[str, str] = {}
    for object_id in snapshot.ids:
        obj = snapshot.objects[object_id]
        sha = snapshot.shas.get(object_id)
        recomputed = sha256_bytes((canonical_json(obj) + "\n").encode())
        if sha is not None and sha != recomputed:
            problems.append(
                f"{object_id}: object bytes hash to {recomputed[:12]} but are stored as "
                f"{sha[:12]} — a store object is write-once and content-addressed"
            )
        if object_id in seen:
            problems.append(f"{object_id}: two objects claim this id")
        seen[object_id] = sha or ""
        problems.extend(f"{object_id}: {problem}" for problem in object_problems(obj))
    for event in snapshot.events:
        target = str(event.get("target"))
        if target not in snapshot.objects:
            problems.append(
                f"{event.get('id')}: target {target} is not in the store — transactions are "
                "append-only and objects are never deleted"
            )
        sha = event.get("object_sha")
        if isinstance(sha, str) and sha not in set(snapshot.shas.values()):
            problems.append(f"{event.get('id')}: object {sha[:12]} referenced but not stored")
        if event.get("operation") == "resolve" and event.get("resolution") not in RESOLUTIONS:
            problems.append(
                f"{event.get('id')}: resolution {event.get('resolution')!r} must be one of "
                + ", ".join(RESOLUTIONS)
            )
    return problems


def _chain_hashes(events: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(event.get("event_hash")) for event in events]


def _prefix_problem(earlier: Sequence[Mapping[str, Any]], current: Sequence[Mapping[str, Any]], where: str) -> str | None:
    """Is *earlier* still the beginning of *current*? — the append-only question.

    A chain that GREW is fine, and a chain that changed under an existing
    position or lost its tail is not: both mean a transaction that was on the
    record is no longer on it.  The hash chain catches an edit in the middle,
    but nothing in it notices the last line simply being deleted — every
    remaining event still verifies — so the previous states of the file are what
    the tip is measured against.
    """
    before = _chain_hashes(earlier)
    now = _chain_hashes(current)
    if len(before) > len(now):
        return (
            f"{where} carried {len(before)} transaction(s) and the store now has "
            f"{len(now)}: events removed from the tip. The chain still verifies — a "
            "deleted last line always does — so the store's own history is the witness"
        )
    if before != now[: len(before)]:
        return f"{where} is not a prefix of the store on disk: a recorded transaction was rewritten"
    return None


def _append_only_problems(ctx: FamilyContext, snapshot: Snapshot, rows: Sequence[tuple[Mapping[str, Any], dict[str, Any]]]) -> list[str]:
    """The store's tip, checked against every state a witness remembers it in."""
    repo = ctx.repo
    if repo is None:
        return []
    problems: list[str] = []
    result = git(repo, ["log", "--format=%H", "--reverse", "--", EVENTS_REL], check=False)
    commits = (
        [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if result.returncode == 0
        else []
    )
    for commit in commits:
        blob = git_blob(repo, commit, EVENTS_REL)
        if blob is None:
            continue
        try:
            events = _parse_events(blob.decode("utf-8"), f"{EVENTS_REL}@{commit[:12]}")
        except (UnicodeDecodeError, WorkflowError) as exc:
            problems.append(f"{EVENTS_REL} at {commit[:12]} is unreadable ({exc})")
            continue
        problem = _prefix_problem(events, snapshot.events, f"{EVENTS_REL} at commit {commit[:12]}")
        if problem is not None:
            problems.append(problem)
    for _event, obj in rows:
        head = obj.get("store_head")
        if not isinstance(head, str) or not head:
            continue
        pinned = snapshot_at(repo, head)
        if pinned is None:
            continue
        problem = _prefix_problem(pinned.events, snapshot.events, f"the store at pinned head {head[:12]}")
        if problem is not None:
            problems.append(problem)
    return problems


def _store_checks(
    ctx: FamilyContext, rows: Sequence[tuple[Mapping[str, Any], dict[str, Any]]] = ()
) -> tuple[list[Check], Snapshot]:
    name = "knowledge store"
    if ctx.repo is None:
        return [_warn(name, "not a git repository — the repo-level store cannot be read")], Snapshot()
    try:
        snapshot = snapshot_on_disk(ctx.repo)
    except WorkflowError as exc:
        return [_fail(name, str(exc))], Snapshot()
    problems = store_problems(snapshot)
    problems.extend(_append_only_problems(ctx, snapshot, rows))
    if problems:
        return [_fail(name, "; ".join(problems[:6]))], snapshot
    return (
        [
            _pass(
                name,
                f"{len(snapshot.objects)} object(s) and {len(snapshot.events)} transaction(s), "
                "chain intact, nothing deleted, and every earlier state of the ledger is "
                "still a prefix of it",
            )
        ],
        snapshot,
    )


def _promotion_checks(ctx: FamilyContext, snapshot: Snapshot) -> list[Check]:
    """This study's own promotions: do their sources resolve, and did they hold?"""
    name = "knowledge promotions"
    from .manifest import study_id

    study = study_id(ctx.study_dir, ctx.contract)
    mine = [
        snapshot.objects[object_id]
        for object_id in snapshot.ids
        if snapshot.objects[object_id].get("study") == study
    ]
    if not mine:
        return [_pass(name, "this study promoted nothing")]
    if ctx.repo is None:
        return [_warn(name, "not a git repository — promotion sources cannot be resolved")]
    checks: list[Check] = []
    for obj in mine:
        checks.append(_one_promotion_check(ctx, obj, name))
    return checks


def _promotion_is_foreign(repo: Path, obj: Mapping[str, Any]) -> bool:
    """Does this object say it was promoted somewhere else?

    ``origin_repo`` is the store's own record of where the source lock lived.
    ``local`` and this checkout's own remote both mean "here", and only an
    object from a genuinely different repository is exempt from resolving —
    otherwise an unresolvable commit (or none at all) would buy silence just by
    being unresolvable, which is the shape of every hole worth closing.
    """
    origin = obj.get("origin_repo")
    if not isinstance(origin, str) or not origin.strip() or origin.strip() == "local":
        return False
    result = git(repo, ["remote", "get-url", "origin"], check=False)
    mine = result.stdout.strip() if result.returncode == 0 else ""
    return origin.strip() != mine


def _one_promotion_check(ctx: FamilyContext, obj: Mapping[str, Any], name: str) -> Check:
    from ..primitives import sha256_bytes as _sha
    from ..primitives import sha256_file as _sha_file

    repo = ctx.repo
    assert repo is not None  # the caller returned early without one
    object_id = str(obj.get("id"))
    commit = obj.get("commit")
    source_path = str(obj.get("source_path") or "")
    blob = git_blob(repo, str(commit), source_path) if isinstance(commit, str) else None
    where = f"at {str(commit)[:12]}" if blob is not None else "in the working tree"
    if blob is None and _promotion_is_foreign(repo, obj):
        return _warn(
            name,
            f"{object_id}: foreign origin, unverifiable here "
            f"({obj.get('origin_repo')} {str(commit or '')[:12]}:{source_path})",
        )
    problems: list[str] = []
    entry: Mapping[str, Any] | None = None
    if blob is not None:
        actual = _sha(blob)
        entry = lock_claim_at(repo, str(commit), source_path, obj.get("claim_id"))
    else:
        # The object is this repository's own and names no resolvable commit —
        # a seeding run that predates commit recording, or a commit that was
        # rewritten away.  The source is still here, so it is still checkable.
        path = repo / source_path
        if not path.is_file():
            return _fail(
                name,
                f"{object_id}: {source_path} resolves neither at "
                f"{str(commit or 'no commit')[:12]} nor in the working tree — a promotion "
                "that cannot be traced back to the lock it copied is not a promotion",
            )
        actual = _sha_file(path)
        entry = _lock_claim_on_disk(path, obj.get("claim_id"))
    if actual != obj.get("source_hash"):
        problems.append(
            f"{source_path} {where} hashes to {actual[:12]}, the object records "
            f"{str(obj.get('source_hash'))[:12]}"
        )
    if entry is not None:
        for field_name in ("class", "strength"):
            if obj.get(field_name) != entry.get(field_name):
                problems.append(
                    f"{field_name} is {obj.get(field_name)!r} in the store but "
                    f"{entry.get(field_name)!r} in the source lock — a promotion copies "
                    "the standing a claim earned; it never strengthens it"
                )
        roots = evidence_key(obj.get("evidence_roots") or ())
        if roots != evidence_key(entry.get("evidence") or ()):
            problems.append("evidence_roots differ from the source claim's evidence")
    elif obj.get("claim_id"):
        problems.append(f"claim {obj.get('claim_id')} is not in {source_path} {where}")
    if problems:
        return _fail(name, f"{object_id}: " + "; ".join(problems))
    return _pass(
        name,
        f"{object_id}: {obj.get('claim_id') or source_path} resolves {where} with class "
        f"{obj.get('class')!r} / strength {obj.get('strength')!r} unchanged",
    )


def _lock_claim_on_disk(path: Path, claim_id: Any) -> dict[str, Any] | None:
    """The same claim lookup :func:`lock_claim_at` does, against a file on disk."""
    if not isinstance(claim_id, str) or not claim_id:
        return None
    try:
        return _claim_from_lock(path.read_bytes(), claim_id)
    except OSError:  # pragma: no cover - is_file() was just true
        return None


def verify_family(ctx: FamilyContext) -> tuple[list[Check], dict[str, Any]]:
    """The ``knowledge`` family: was the store consulted, and is it intact?"""
    rows = queries(ctx.study_dir, list(ctx.events), QUERY_TYPE)
    checks = _query_checks(ctx, rows)
    checks += _decision_checks(ctx, rows)
    checks += _replay_checks(ctx, rows)
    store_checks, snapshot = _store_checks(ctx, rows)
    checks += store_checks
    checks += _promotion_checks(ctx, snapshot)

    integrity = "FAIL" if any(check.status == "FAIL" for check in checks) else "PASS"
    hits: list[str] = []
    if rows:
        hits = [str(hit.get("id")) for hit in rows[0][1].get("hits") or [] if isinstance(hit, Mapping)]
    decisions = (
        effective_decisions(ctx.study_dir, list(ctx.events), str(rows[0][0].get("payload_sha256")))
        if rows
        else {}
    )
    if not rows:
        outcome = "unconsulted"
    elif not hits:
        outcome = "no-match"
    else:
        outcome = "consulted"
    return checks, {
        "integrity": integrity,
        "outcome": outcome,
        "hits": len(hits),
        "used": sum(1 for row in decisions.values() if row.get("decision") == "use"),
        "rejected": sum(1 for row in decisions.values() if row.get("decision") == "reject"),
    }


#: The registration.  Everything above is reachable only through this object.
#:
#: No admission rule: consulting the store is a CONSULT-time obligation, not a
#: per-action one, so the coupling lives in the verify family (a declaring study
#: whose consult gate precedes its query receipt FAILs `knowledge query`) rather
#: than in a refusal at every `check`.
CAPABILITY = Capability(
    name=CAPABILITY_NAME,
    admission_rules=(),
    verify_family=verify_family,
)
