"""The sealed-run rehearsal rule (war stories 9 and 11).

A track may look at its sealed evidence once. A crash, a time-out or a stale
entrypoint on that one look cannot be taken back, so the look is rehearsed first:
``klein run-one --final-test --dry-run`` runs the real entrypoint on development
data and records a ``sealed_dryrun`` event.

This module is the ONE definition of "rehearsed". The notary refuses a sealed run
on it (:func:`kleinlib.workflow.run_one`) and ``klein next`` reports it
(:mod:`kleinlib.next_step`), so the two cannot disagree. The rule is about the run
that is about to happen, not about history. The track's LATEST rehearsal must:

* have exited 0, without timing out, and printed its acknowledgement;
* have printed a metric the notary can judge (unless a declared verifier produces it);
* have run the same command, over the same mutable surface and the same scripts
  that command names, byte for byte;
* have taken no longer than the sealed run is allowed (per seed, when the contract
  declares a seed array).

What it does NOT cover, stated so nobody assumes it:

* library code outside the mutable surface that the command does not name
  (``kleinlib/``, a study's ``lib/``, ``prepare.py``) — a change there is visible
  in git, not refused here;
* a declared verifier — the rehearsal runs the entrypoint, not the checker;
* a detached host — the rehearsal runs here, a ``--detach`` run elsewhere;
* tampering — the rule reads the study's event chain, which is tamper-evident,
  not tamper-proof: a rehearsal event appended by hand, or a failed one cut from
  the end of the chain and committed, satisfies it. The guard is against a hurried
  honest run, not a forger; a referee reads the git history for the rest.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .contract import entrypoint_spec, mutable_surface
from .events import read_events
from .primitives import canonical_json, sha256_bytes
from .transaction import git_blob, relative

__all__ = [
    "command_files_digest",
    "latest_rehearsal",
    "rehearsal_command",
    "rehearsal_problem",
    "surface_digest",
    "surface_digest_at",
]


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


def command_files_digest(study_dir: Path, command: Sequence[str]) -> tuple[str, list[list[Any]]]:
    """The study files a command names: ``(digest, [[path, sha256], …])``.

    ``--command python -u other.py`` runs ``other.py``, which the mutable surface
    need not contain. Hashing what the command names closes that door: a script
    edited after its rehearsal is a different script.
    """
    root = study_dir.resolve()
    entries: dict[str, str] = {}
    for argument in command:
        # An argument is usually not a path at all (`-c "<a whole program>"`): one the
        # filesystem cannot even look up names no file.
        try:
            candidate = Path(argument) if Path(argument).is_absolute() else study_dir / argument
            resolved = candidate.resolve()
            if not resolved.is_file() or root not in resolved.parents:
                continue
            entries[resolved.relative_to(root).as_posix()] = sha256_bytes(resolved.read_bytes())
        except (OSError, ValueError):
            continue
    listed = [[name, entries[name]] for name in sorted(entries)]
    return _digest(listed), listed


def rehearsal_command(study_dir: Path, track: str, command: Sequence[str] | None = None) -> str:
    """The exact rehearsal that would cover a sealed run of ``command`` (for messages)."""
    import shlex

    parts = ["klein", "run-one", "--study", str(study_dir), "--track", track, "--final-test", "--dry-run"]
    if command:
        parts += ["--command", *command]
    return shlex.join(parts)


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
    budget_seconds: float | None = None,
    runs: int = 1,
) -> str | None:
    """Why ``track``'s sealed run is NOT rehearsed — or ``None`` when it is.

    ``command`` is the command the sealed run will execute (default: the contract's
    entrypoint); ``budget_seconds`` the time it will be allowed in total and ``runs``
    how many times the command runs inside that time (the seed array). A later
    rehearsal replaces an earlier one: a pass followed by a failure is a failure,
    because the failure is the newer fact.
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
    if event.get("metric_parsed") is False:
        return (
            f"{where} printed no finite `primary_metric:` line — the sealed run would be "
            "recorded as a crash and the seal spent"
        )
    expected = list(command or entrypoint_spec(contract)["command"])
    if list(event.get("command") or []) != expected:
        return f"{where} ran a different command ({' '.join(map(str, event.get('command') or []))})"
    if not event.get("surface_digest") or not event.get("command_files"):
        return f"{where} predates the surface digest, so it cannot show what it ran"
    if event["surface_digest"] != surface_digest(study_dir, contract)[0]:
        return (
            f"{where} ran an earlier version of {', '.join(sorted(mutable_surface(contract)))} "
            "— the code changed afterwards"
        )
    digest, listed = command_files_digest(study_dir, expected)
    if event["command_files"] != digest:
        names = ", ".join(name for name, _sha in listed) or "the files its command named"
        return f"{where} ran an earlier version of {names} — a script the command names changed afterwards"
    if budget_seconds is not None:
        took = float(event.get("wall_seconds") or 0.0)
        needed = took * max(int(runs), 1)
        if needed > float(budget_seconds):
            per = f" × {runs} seeds" if runs > 1 else ""
            return (
                f"{where} took {took:.3g} s{per}, and the sealed run is allowed "
                f"{float(budget_seconds):.3g} s (the smaller of the per-run limit and what is "
                "left of the phase budget) — it would time out and spend the seal; shorten "
                "the run or amend the phase budget, then rehearse again"
            )
    return None
