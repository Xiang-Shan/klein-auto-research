"""``<study>/generation/`` — the extension chain and the write-once object store.

Two files and one directory:

``generation/events.jsonl``
    The extension's own hash chain, appended exactly the way
    :func:`kleinlib.events.append_event` appends the core's (canonical JSON, one
    line, flush + fsync).  It is re-implemented here rather than reused because
    the envelope differs (see :mod:`kleinlib.generation.envelope`) and because
    ``kleinlib/events.py`` must not change.

``generation/objects/<sha256>.json``
    Write-once snapshots.  The file name IS the sha256 of the object's canonical
    JSON bytes, so re-writing an identical object is a no-op and two different
    objects can never collide on one name.

An object no event references by ``payload_sha256`` is an **orphan** — the
signature of a verb that died between step 2 and step 3.  An event whose object
is missing is the opposite failure.  Both are detected; neither is ever repaired
by deleting anything (``klein generation recover`` appends a ``recovered`` event
that VOIDS the orphan and leaves the bytes on disk).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ..errors import WorkflowError
from ..primitives import atomic_write_text, canonical_json, sha256_bytes, utc_now
from ..transaction import commit_state_writes
from .envelope import build_event, event_id

__all__ = [
    "COMMIT_PATHS",
    "GENERATION_DIRNAME",
    "append_event",
    "chain_problems",
    "commit_generation",
    "events_path",
    "generation_dir",
    "mislabelled_object_shas",
    "missing_object_shas",
    "object_path",
    "objects_dir",
    "orphan_object_shas",
    "read_events",
    "read_object",
    "referenced_object_shas",
    "stored_object_shas",
    "voided_object_shas",
    "write_object",
]

GENERATION_DIRNAME = "generation"

#: Every study-relative path a generation verb may commit.  Nothing else — the
#: layer owns this subtree and no other byte of the study.
COMMIT_PATHS: tuple[str, ...] = (
    "generation/manifest.yaml",
    "generation/events.jsonl",
    "generation/objects",
    "generation/verify_receipt.json",
    "generation/label.json",
)


def generation_dir(study_dir: Path) -> Path:
    return study_dir / GENERATION_DIRNAME


def events_path(study_dir: Path) -> Path:
    return generation_dir(study_dir) / "events.jsonl"


def objects_dir(study_dir: Path) -> Path:
    return generation_dir(study_dir) / "objects"


def object_path(study_dir: Path, sha: str) -> Path:
    return objects_dir(study_dir) / f"{sha}.json"


# --------------------------------------------------------------------------
# the chain
# --------------------------------------------------------------------------


def read_events(study_dir: Path) -> list[dict[str, Any]]:
    path = events_path(study_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkflowError(
                f"generation/events.jsonl line {lineno} is invalid JSON: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise WorkflowError(f"generation/events.jsonl line {lineno} is not an object")
        events.append(value)
    return events


def chain_problems(events: Sequence[Mapping[str, Any]]) -> list[str]:
    """Every way the extension chain can be broken, as one line each."""
    from .envelope import GENERATION_SCHEMA, body_hash

    problems: list[str] = []
    previous: str | None = None
    for index, event in enumerate(events, start=1):
        label = f"event {index}"
        if event.get("schema") != GENERATION_SCHEMA:
            problems.append(f"{label}: schema is {event.get('schema')!r}")
        if event.get("sequence") != index:
            problems.append(f"{label}: sequence is {event.get('sequence')!r}")
        if event.get("id") != event_id(index):
            problems.append(f"{label}: id is {event.get('id')!r}")
        if event.get("previous_event_hash") != previous:
            problems.append(f"{label}: previous_event_hash does not match")
        given = event.get("event_hash")
        if given != body_hash(event):
            problems.append(f"{label}: event_hash does not match content")
        previous = given if isinstance(given, str) else None
    return problems


def append_event(
    study_dir: Path,
    event_type: str,
    *,
    study: str,
    core_anchor: Mapping[str, Any],
    git_head: str | None,
    payload_sha256: str | None = None,
    parent_ids: Sequence[str] = (),
    testimony_fields: Mapping[str, Any] | None = None,
    **summary: Any,
) -> dict[str, Any]:
    """Seal one envelope onto the tail of the extension chain."""
    events = read_events(study_dir)
    previous = events[-1].get("event_hash") if events else None
    event = build_event(
        sequence=len(events) + 1,
        event_type=event_type,
        study=study,
        created_at=utc_now(),
        core_anchor=core_anchor,
        git_head=git_head,
        previous_event_hash=previous if isinstance(previous, str) else None,
        payload_sha256=payload_sha256,
        parent_ids=list(parent_ids),
        testimony_fields=testimony_fields,
        summary=summary,
    )
    path = events_path(study_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(event) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event


# --------------------------------------------------------------------------
# the object store
# --------------------------------------------------------------------------


def write_object(study_dir: Path, obj: Mapping[str, Any]) -> str:
    """Store one object write-once and return its sha256.

    Identical bytes under an existing name are a no-op; different bytes under
    the same name are impossible by construction, because the name IS the hash.
    """
    text = canonical_json(obj) + "\n"
    sha = sha256_bytes(text.encode())
    path = object_path(study_dir, sha)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return sha
    atomic_write_text(path, text)
    return sha


def read_object(study_dir: Path, sha: str) -> dict[str, Any]:
    path = object_path(study_dir, sha)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid generation object {sha}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"generation object {sha} is not an object")
    return value


def stored_object_shas(study_dir: Path) -> set[str]:
    directory = objects_dir(study_dir)
    if not directory.is_dir():
        return set()
    return {path.stem for path in sorted(directory.glob("*.json"))}


def referenced_object_shas(events: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        str(event["payload_sha256"])
        for event in events
        if isinstance(event.get("payload_sha256"), str)
    }


def voided_object_shas(events: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """``{object sha: the id of the ``recovered`` event that voided it}``."""
    voided: dict[str, str] = {}
    for event in events:
        if event.get("type") != "recovered":
            continue
        for sha in event.get("voided_objects") or ():
            if isinstance(sha, str):
                voided.setdefault(sha, str(event.get("id")))
    return voided


def orphan_object_shas(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> list[str]:
    """Objects on disk that no event references and no ``recovered`` event voided."""
    voided = set(voided_object_shas(events))
    referenced = referenced_object_shas(events)
    return sorted(stored_object_shas(study_dir) - referenced - voided)


def missing_object_shas(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> list[str]:
    """Objects an event references that are not on disk."""
    stored = stored_object_shas(study_dir)
    return sorted(referenced_object_shas(events) - stored)


# ---- content addressing (WP-03) ------------------------------------------
def mislabelled_object_shas(study_dir: Path) -> list[str]:
    """Object files whose CONTENT no longer hashes to their own file name.

    The store is content-addressed by construction — :func:`write_object` names
    each file after the sha256 of its bytes — so this can only be true after
    someone rewrote a stored object in place.  The event that references it still
    carries the old name, so the tamper is otherwise invisible to a reader who
    trusts the name; here it is one FAIL line naming the file.
    """
    directory = objects_dir(study_dir)
    if not directory.is_dir():
        return []
    return sorted(
        path.stem
        for path in directory.glob("*.json")
        if sha256_bytes(path.read_bytes()) != path.stem
    )


# --------------------------------------------------------------------------
# the commit
# --------------------------------------------------------------------------


def commit_generation(
    study_dir: Path, message: str, paths: Sequence[str] = COMMIT_PATHS
) -> str | None:
    """File exactly the generation paths this verb wrote.

    ``scope="own"`` commits ``paths`` plus
    :data:`kleinlib.transaction.OWN_WRITE_PATHS` and nothing else, so an
    operator's in-flight surface edit stays theirs.  Generation verbs never
    modify ``study_state.json`` or the core ``events.jsonl``, so in practice the
    commit carries ``generation/**`` alone — which
    ``test_generation_spine.py`` asserts with ``git show --name-only``.
    """
    unknown = [name for name in paths if name not in COMMIT_PATHS]
    if unknown:
        raise WorkflowError(
            "a generation verb may only commit generation/** paths; refused: "
            + ", ".join(unknown)
        )
    return commit_state_writes(study_dir, message, paths=list(paths), scope="own")
