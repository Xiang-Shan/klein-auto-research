"""The three local witnesses that put "before" on the record — without a clock.

A generation receipt is worth nothing unless it can be shown to PRECEDE the
action it admits.  Klein has no trusted timestamp and does not pretend to: every
extension event carries three independent order witnesses, and
``klein generation verify`` requires all three to agree.

1. **The extension chain.**  ``previous_event_hash`` links each event to the one
   before it, so a receipt cannot be inserted into the middle of the ledger
   without rewriting every event after it.
2. **The core anchor.**  ``core_anchor = {sequence, event_hash}`` is the tip of
   the study's own ``events.jsonl`` when the receipt was written.  It resolves
   to a real core event, and a receipt whose anchor sequence is at or after a
   run's ``run_started`` sequence did not precede that run.
3. **Git ancestry.**  The commit that INTRODUCED the receipt's object file must
   be an ancestor of the run's ``candidate_commit``.  ``run-one`` refuses a dirty
   tree, so a receipt that was committed before the run is an ancestor by
   construction; one that was not, is not.

What this does NOT establish is spelled out in the protocol and repeated here
because it is the most likely thing to be over-read: local ordering is not
independently established chronology.  A party who rewrites both the core chain
and git history wholesale is not detected.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..errors import WorkflowError
from ..events import read_events as read_core_events
from ..transaction import git, git_blob, relative, repo_root_for

__all__ = [
    "changed_paths_between",
    "core_anchor_problem",
    "core_tip",
    "gate_events",
    "git_head",
    "introducing_commit",
    "is_ancestor",
    "read_core_events",
    "repo_for",
    "run_started_events",
    "study_event_commit",
]


def repo_for(study_dir: Path) -> Path | None:
    """The repository the study lives in, or None outside one."""
    try:
        return repo_root_for(study_dir)
    except WorkflowError:
        return None


def git_head(repo: Path | None) -> str | None:
    if repo is None:
        return None
    result = git(repo, ["rev-parse", "HEAD"], check=False)
    return result.stdout.strip() or None if result.returncode == 0 else None


def core_tip(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The core chain's tip as an anchor; ``{sequence: 0, event_hash: null}`` when empty."""
    if not events:
        return {"sequence": 0, "event_hash": None}
    last = events[-1]
    return {"sequence": int(last.get("sequence") or len(events)), "event_hash": last.get("event_hash")}


def core_anchor_problem(
    core: Sequence[Mapping[str, Any]], anchor: Mapping[str, Any] | None
) -> str | None:
    """Why this anchor does not resolve against the core chain — or None."""
    if not isinstance(anchor, Mapping):
        return "core_anchor is missing"
    sequence = anchor.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        return f"core_anchor.sequence is {sequence!r}"
    if sequence == 0:
        if anchor.get("event_hash") is not None:
            return "core_anchor.sequence 0 must carry a null event_hash"
        return None
    if sequence > len(core):
        return f"core_anchor.sequence {sequence} is past the core chain ({len(core)} events)"
    if core[sequence - 1].get("event_hash") != anchor.get("event_hash"):
        return f"core_anchor.event_hash does not match core event {sequence}"
    return None


def gate_events(core: Sequence[Mapping[str, Any]], gate: str) -> list[Mapping[str, Any]]:
    """Core ``gate_recorded`` / ``gate_overridden`` events for one gate, in order."""
    return [
        event
        for event in core
        if event.get("type") in ("gate_recorded", "gate_overridden") and event.get("gate") == gate
    ]


def run_started_events(core: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """``{run id: the first ``run_started`` event for it}``."""
    started: dict[str, Mapping[str, Any]] = {}
    for event in core:
        if event.get("type") != "run_started":
            continue
        run = event.get("experiment")
        if isinstance(run, str):
            started.setdefault(run, event)
    return started


# --------------------------------------------------------------------------
# git ancestry
# --------------------------------------------------------------------------


def introducing_commit(repo: Path, relpath: str) -> str | None:
    """The oldest commit that ADDED *relpath* (write-once files have exactly one)."""
    result = git(repo, ["log", "--diff-filter=A", "--format=%H", "--", relpath], check=False)
    if result.returncode:
        return None
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return commits[-1] if commits else None


def is_ancestor(repo: Path, ancestor: str | None, descendant: str | None) -> bool:
    if not ancestor or not descendant:
        return False
    result = git(repo, ["merge-base", "--is-ancestor", ancestor, descendant], check=False)
    return result.returncode == 0


def study_event_commit(repo: Path, study_dir: Path, event_hash: str) -> str | None:
    """The first commit whose ``events.jsonl`` blob already carries *event_hash*.

    The core journal is one append-only file, so ``--diff-filter=A`` finds only
    its creation; the commit that FILED a particular event has to be found by
    reading the blob.  Commits are walked oldest-first and the first match wins,
    which is the commit that introduced the event.
    """
    relpath = relative(repo, study_dir / "events.jsonl")
    result = git(repo, ["log", "--format=%H", "--reverse", "--", relpath], check=False)
    if result.returncode:
        return None
    needle = event_hash.encode()
    for line in result.stdout.splitlines():
        commit = line.strip()
        if not commit:
            continue
        blob = git_blob(repo, commit, relpath)
        if blob is not None and needle in blob:
            return commit
    return None


def changed_paths_between(repo: Path, base: str, head: str) -> set[str]:
    """Repo-relative paths whose bytes differ between two commits (empty when equal)."""
    if base == head:
        return set()
    result = git(repo, ["diff", "--name-only", f"{base}..{head}"], check=False)
    if result.returncode:
        return {"<unresolvable>"}
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}
