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
from .envelope import build_event, event_id

__all__ = [
    "COMMIT_PATHS",
    "CORE_STATE_PATHS",
    "CORE_STATE_PREFIXES",
    "GENERATION_DIRNAME",
    "append_event",
    "chain_problems",
    "commit_artifacts",
    "commit_generation",
    "core_state_dirt",
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

#: Core state and evidence.  A generation verb never writes these and never
#: files them: ``run-one``, ``klein recover``, ``klein verify``, ``klein claims``
#: and the gate records own them, and a layer that quietly swept them into its
#: own transaction would make its receipts look like the core's.
CORE_STATE_PATHS: frozenset[str] = frozenset(
    {
        "study.yaml",
        "study_state.json",
        "events.jsonl",
        "claims.lock",
        "verify_receipt.json",
    }
)

#: The same rule for whole subtrees.
CORE_STATE_PREFIXES: tuple[str, ...] = ("runs/",)

#: The two core files whose UNCOMMITTED state stops a generation verb: an
#: unfiled core chain has no introducing commit, so a receipt anchored to it
#: cannot be resolved by ancestry afterwards.
_CORE_DIRT_PATHS: tuple[str, ...] = ("study_state.json", "events.jsonl")


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

    Identical bytes under an existing name are a no-op.  DIFFERENT bytes under
    the same name are impossible by construction — the name IS the hash — so
    meeting them means the stored file was rewritten in place, and the write is
    refused rather than completing the tamper by overwriting it back.  Undoing
    the rewrite is the operator's (``git checkout -- <file>``); ``klein
    generation recover`` never rewrites an object.
    """
    text = canonical_json(obj) + "\n"
    sha = sha256_bytes(text.encode())
    path = object_path(study_dir, sha)
    if path.is_file():
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise WorkflowError(f"generation object {sha[:12]}… is unreadable: {exc}") from exc
        if existing == text:
            return sha
        raise WorkflowError(
            f"generation object {sha[:12]}… already exists on disk with DIFFERENT bytes — "
            "the store is content-addressed and write-once, so that file was rewritten in "
            "place. Restore it by hand (`git checkout -- "
            f"{object_path(study_dir, sha).name}`); recover never rewrites objects."
        )
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


# ---- content addressing ---------------------------------------------------
def mislabelled_object_shas(study_dir: Path) -> dict[str, str]:
    """``{file name: why it is not the object it claims to be}``.

    The store is content-addressed by construction — :func:`write_object` names
    each file after the sha256 of its bytes — so a content mismatch can only be
    true after someone rewrote a stored object in place.  The event that
    references it still carries the old name, so the tamper is otherwise
    invisible to a reader who trusts the name; here it is one FAIL line naming
    the file.

    A file that cannot be READ is reported the same way rather than raised:
    ``generation verify`` never raises on a broken study, and "the object is
    unreadable" is exactly as disqualifying as "the object is not itself".
    """
    directory = objects_dir(study_dir)
    if not directory.is_dir():
        return {}
    problems: dict[str, str] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            data = path.read_bytes()
        except OSError as exc:
            problems[path.stem] = f"unreadable ({exc.strerror or exc})"
            continue
        if sha256_bytes(data) != path.stem:
            problems[path.stem] = "content does not hash to its file name"
    return problems


# --------------------------------------------------------------------------
# the commit
# --------------------------------------------------------------------------


def _is_core_state(name: str) -> bool:
    posix = Path(name).as_posix().lstrip("./")
    return posix in CORE_STATE_PATHS or posix.startswith(CORE_STATE_PREFIXES)


def core_state_dirt(repo: Path, study_dir: Path) -> list[str]:
    """Uncommitted core state, repo-relative — empty when there is none.

    ``study_state.json`` and the core ``events.jsonl`` are the two files whose
    unfiled state makes a generation receipt unresolvable afterwards: the
    receipt anchors to a core event that no commit yet carries, so the third
    chronology witness has nothing to read.
    """
    from ..transaction import git, relative

    names = [relative(repo, study_dir / name) for name in _CORE_DIRT_PATHS]
    result = git(repo, ["status", "--porcelain", "--untracked-files=all", "--", *names],
                 check=False)
    if result.returncode:
        return []
    return [line[3:].split(" -> ")[-1].strip() for line in result.stdout.splitlines() if line.strip()]


def commit_artifacts(study_dir: Path, message: str, paths: Sequence[str]) -> str | None:
    """File exactly ``paths`` — the ledger, and the human artifact a verb hashed.

    ``git commit --only -- <paths>`` builds the commit from HEAD plus the named
    paths alone, so nothing else staged or modified is taken: the operator's
    in-flight edits stay the operator's, exactly as at ``run-one``.  New files
    are staged first, because ``--only`` cannot name a path git has never seen.

    Two refusals, and both are the point.  A path that is core state or core
    evidence is refused outright — the layer writes under ``generation/`` and
    the artifacts a capability names, never ``study_state.json``,
    ``events.jsonl``, ``study.yaml``, ``claims.lock``, ``verify_receipt.json``
    or ``runs/``.  And a DIRTY core state stops the commit before it happens:
    filing around unfiled core state would leave a receipt anchored to an event
    no commit carries.  (This is why ``scope="own"`` is not used here: it
    prepends :data:`kleinlib.transaction.OWN_WRITE_PATHS`, which would sweep a
    dirty ``study_state.json`` into a generation transaction.)

    No-op outside a git repository — unit fixtures scaffold studies in bare
    temp dirs — and when nothing the verb named actually changed.
    """
    from ..transaction import git, git_commit, relative

    forbidden = sorted({name for name in paths if _is_core_state(name)})
    if forbidden:
        raise WorkflowError(
            "a generation verb may not commit core state or core evidence; refused: "
            + ", ".join(forbidden)
            + " — that is run-one's, `klein recover`'s or `klein verify`'s to file"
        )
    probe = git(study_dir, ["rev-parse", "--show-toplevel"], check=False)
    if probe.returncode:
        return None
    repo = Path(probe.stdout.strip()).resolve()
    dirt = core_state_dirt(repo, study_dir)
    if dirt:
        raise WorkflowError(
            "core state is dirty (" + ", ".join(sorted(dirt)) + "); that is run-one's or "
            "`klein recover`'s to file, not a generation verb's"
        )
    existing = [relative(repo, study_dir / name) for name in paths if (study_dir / name).exists()]
    if not existing:
        return None
    git(repo, ["add", "--", *existing])
    if git(repo, ["diff", "--cached", "--quiet", "--", *existing], check=False).returncode == 0:
        return None
    return git_commit(repo, message, only=existing)


def commit_generation(
    study_dir: Path, message: str, paths: Sequence[str] = COMMIT_PATHS
) -> str | None:
    """File exactly the generation paths this verb wrote — and nothing else.

    The narrower half of :func:`commit_artifacts`: the whitelist is
    :data:`COMMIT_PATHS`, so the spine's own verbs cannot file a study artifact
    even by mistake.  ``test_generation_spine.py`` asserts the resulting commit
    with ``git show --name-only``.
    """
    unknown = [name for name in paths if name not in COMMIT_PATHS]
    if unknown:
        raise WorkflowError(
            "a generation verb may only commit generation/** paths; refused: "
            + ", ".join(unknown)
        )
    return commit_artifacts(study_dir, message, list(paths))
