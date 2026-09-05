"""``klein generation recover`` — the append-only repair for an interrupted write.

A generation verb writes an object, appends an event, and commits.  Dying
between those steps leaves exactly two possible states, and both are detectable:

**An orphan object** (written, never referenced).  ``recover`` appends ONE
``recovered`` event listing the orphan shas in ``voided_objects``.  Nothing is
deleted — the bytes stay on disk and ``generation verify`` reports them as a
WARN naming the event that voided them.  Deleting would be the one operation an
append-only ledger cannot audit.

**An uncommitted ledger** (event appended, never committed).  ``recover``
commits the ``generation/**`` paths, because until they are committed the
receipt has no introducing commit and cannot be resolved by ancestry — and
because the next verb refuses a dirty tree.

``recover`` never invents, retries or re-runs anything.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .chronology import git_head, repo_for
from .ledger import (
    append_event,
    commit_generation,
    orphan_object_shas,
    read_events,
)

__all__ = ["recover_generation"]


def recover_generation(
    study_dir: Path,
    *,
    study: str,
    core_anchor: Mapping[str, Any],
    testimony_fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Void every orphan, file every uncommitted generation write.

    Returns ``{"voided": [...], "commit": <sha|None>}``.
    """
    repo = repo_for(study_dir)
    events = read_events(study_dir)
    orphans = orphan_object_shas(study_dir, events)
    if orphans:
        append_event(
            study_dir,
            "recovered",
            study=study,
            core_anchor=core_anchor,
            git_head=git_head(repo),
            testimony_fields=testimony_fields,
            voided_objects=list(orphans),
            reason="objects written without an event (interrupted write)",
        )
    commit = commit_generation(
        study_dir,
        "klein: generation recover ("
        + (f"{len(orphans)} object(s) voided" if orphans else "ledger filed")
        + ")",
    )
    return {"voided": orphans, "commit": commit}
