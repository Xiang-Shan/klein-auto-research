"""The sealed-run rehearsal rule (war stories 9 and 11).

A track may look at its sealed evidence once. A crash, a time-out or a stale
entrypoint on that one look cannot be taken back, so the look is rehearsed first:
``klein run-one --final-test --dry-run`` runs the real entrypoint on development
data and records a ``sealed_dryrun`` event.

This module is the ONE definition of "rehearsed". The notary refuses a sealed run
on it (:func:`kleinlib.workflow.run_one`) and ``klein next`` reports it
(:mod:`kleinlib.next_step`), so the two cannot disagree. The rule is deliberately
about the run that is about to happen, not about history: the track's LATEST
rehearsal must have passed, and must have run the same command over the same
mutable surface, byte for byte.

What it does not cover, stated so nobody assumes it: library code outside the
mutable surface (``kleinlib/``, a study's ``lib/``, ``prepare.py``). That code
changes rarely and deliberately, and a change to it between rehearsal and sealed
run is visible in git, not refused here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .contract import entrypoint_spec, mutable_surface
from .events import read_events
from .primitives import canonical_json, sha256_bytes
from .transaction import git_blob, relative

__all__ = ["latest_rehearsal", "rehearsal_problem", "surface_digest", "surface_digest_at"]


def _digest(entries: Sequence[Sequence[Any]]) -> str:
    return sha256_bytes(canonical_json([list(entry) for entry in entries]).encode())


def surface_digest(study_dir: Path, contract: Mapping[str, Any]) -> tuple[str, list[list[Any]]]:
    """The mutable surface AS ON DISK: ``(digest, [[path, sha256|null], …])``.

    Sorted by path; a declared file that does not exist hashes as null, so
    "the file was deleted" and "the file was empty" are different digests.
    """
    entries: list[list[Any]] = []
    for name in sorted(mutable_surface(contract)):
        path = study_dir / name
        entries.append([name, sha256_bytes(path.read_bytes()) if path.is_file() else None])
    return _digest(entries), entries


def surface_digest_at(
    repo: Path, study_dir: Path, contract: Mapping[str, Any], commit: str
) -> tuple[str, list[list[Any]]]:
    """The same digest, read out of a commit rather than the working tree."""
    entries: list[list[Any]] = []
    for name in sorted(mutable_surface(contract)):
        blob = git_blob(repo, commit, relative(repo, study_dir / name))
        entries.append([name, sha256_bytes(blob) if blob is not None else None])
    return _digest(entries), entries


def latest_rehearsal(events: Iterable[Mapping[str, Any]], track: str) -> Mapping[str, Any] | None:
    """The track's most recent ``sealed_dryrun`` event, or ``None``."""
    found: Mapping[str, Any] | None = None
    for event in events:
        if event.get("type") == "sealed_dryrun" and str(event.get("track")) == track:
            found = event
    return found


def rehearsal_problem(
    study_dir: Path,
    contract: Mapping[str, Any],
    track: str,
    *,
    command: Sequence[str] | None = None,
    events: Iterable[Mapping[str, Any]] | None = None,
) -> str | None:
    """Why ``track``'s sealed run is NOT rehearsed — or ``None`` when it is.

    ``command`` is the command the sealed run will execute (default: the contract's
    entrypoint). A later rehearsal replaces an earlier one: a pass followed by a
    failure is a failure, because the failure is the newer fact.
    """
    event = latest_rehearsal(read_events(study_dir) if events is None else events, track)
    if event is None:
        return "no rehearsal is on record"
    where = f"the latest rehearsal (event {event.get('sequence')})"
    if event.get("timed_out"):
        return f"{where} timed out"
    if event.get("exit_code") != 0:
        return f"{where} failed with exit code {event.get('exit_code')}"
    if not event.get("acknowledged"):
        return (
            f"{where} never printed `sealed_dryrun: 1` — the entrypoint ignored the "
            "rehearsal flag and would have read the sealed evidence"
        )
    expected = list(command or entrypoint_spec(contract)["command"])
    if list(event.get("command") or []) != expected:
        return f"{where} ran a different command ({' '.join(map(str, event.get('command') or []))})"
    recorded = event.get("surface_digest")
    if not recorded:
        return f"{where} predates the surface digest, so it cannot show what it ran"
    if recorded != surface_digest(study_dir, contract)[0]:
        return (
            f"{where} ran an earlier version of {', '.join(sorted(mutable_surface(contract)))} "
            "— the code changed afterwards"
        )
    return None
