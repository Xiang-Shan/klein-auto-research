"""Helpers shared by more than one ``klein generation`` verb group.

Study loading, the clean-tree / healthy-ledger preconditions, the provenance
flags, the common argparse arguments and the error/refusal printers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from ...contract import resolve_study
from ...errors import WorkflowError


def _study(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--study", default=".", help="study directory (default: .)")


def _testimony(parser: argparse.ArgumentParser) -> None:
    """The four self-reported provenance flags.  Recorded, never authenticated."""
    parser.add_argument("--actor", help="who is driving (testimony, not authenticated)")
    parser.add_argument("--tool", help="which agent/CLI is driving (testimony)")
    parser.add_argument("--model", help="which model is driving (testimony)")
    parser.add_argument("--session", help="a session identifier (testimony)")


def _error(message: str) -> int:
    print(f"klein: error: {message}", file=sys.stderr)
    return 1


def _load(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    """The study directory and its contract."""
    from ...contract import load_contract

    study = resolve_study(args.study)
    return study, load_contract(study)


def _state(study: Path, contract: dict[str, Any]) -> dict[str, Any]:
    from ...state import load_state

    try:
        return load_state(study, contract)
    except WorkflowError:
        return {}


def _require_clean(study: Path, contract: dict[str, Any], *extra: str) -> None:
    """A clean tree except the mutable surface, and ``extra`` on top of it.

    ``extra`` is what THIS verb is about to file and therefore cannot already be
    committed: the authored artifact a lock hashes (``domain_card.md``,
    ``slates/<phase>.yaml``, the contribution ledger), or a repair's changed
    files.  Everything else in the tree must still be committed — the operator's
    other edits stay the operator's problem, exactly as at ``run-one``.
    """
    from ...contract import mutable_surface
    from ...transaction import assert_run_worktree
    from ..chronology import repo_for

    repo = repo_for(study)
    if repo is None:
        raise WorkflowError(
            "a generation verb needs a git repository: git ancestry is one of the "
            "three chronology witnesses"
        )
    assert_run_worktree(repo, study, surface=(*mutable_surface(contract), *extra))


def _require_healthy_ledger(study: Path) -> None:
    from ..ledger import (
        chain_problems,
        mislabelled_object_shas,
        missing_object_shas,
        orphan_object_shas,
        read_events,
    )

    events = read_events(study)
    problems = chain_problems(events)
    if problems:
        raise WorkflowError(
            "the generation chain is broken: " + "; ".join(problems[:5])
        )
    orphans = orphan_object_shas(study, events)
    if orphans:
        raise WorkflowError(
            "orphan generation objects (written without an event): "
            + ", ".join(sha[:12] for sha in orphans)
            + " — run `klein generation recover` to void them"
        )
    missing = missing_object_shas(study, events)
    if missing:
        raise WorkflowError(
            "generation events whose object is missing: "
            + ", ".join(sha[:12] for sha in missing)
        )
    mislabelled = mislabelled_object_shas(study)
    if mislabelled:
        raise WorkflowError(
            "stored generation object(s) that are not the object they name: "
            + "; ".join(f"{sha[:12]} ({why})" for sha, why in sorted(mislabelled.items()))
            + " — the store is content-addressed and write-once, so restore the file by "
            "hand (`git checkout -- <path>`); `klein generation recover` never rewrites "
            "an object, and every writing verb refuses until the store is itself again"
        )


def _testimony_fields(args: argparse.Namespace) -> dict[str, Any]:
    return {
        field: getattr(args, field, None)
        for field in ("actor", "tool", "model", "session")
    }


def _refuse(message: str) -> int:
    """Exit 2: the question was asked and a rule answered no.

    On STDOUT, like ``check``'s reasons and like the multi-line refusal blocks:
    the reasons are the answer to the question the verb was asked, not a
    diagnostic about the verb's own failure to run.  Exit 1 (:func:`_error`) is
    the stderr side.
    """
    print(f"klein: refused: {message}")
    return 2


def _require_capability(study: Path, name: str) -> dict[str, Any]:
    """The manifest, once it is confirmed to DECLARE the capability being used."""
    from .. import manifest as gm
    from ..admission import declared_capabilities

    manifest = gm.load_manifest(study)
    if name not in declared_capabilities(manifest):
        raise WorkflowError(
            f"this study did not declare the {name!r} capability; the opt-in is immutable, "
            "so a study that wants it declares it at `klein generation init`"
        )
    return manifest


def _number(value: Any) -> str:
    return "n/a" if value is None else format(float(value), ".6g")


def _study_relative_file(study: Path, raw: str, *, label: str) -> tuple[str, str]:
    """``(study-relative POSIX path, sha256)`` for a file that must exist inside the study."""
    from ...primitives import sha256_file

    candidate = Path(raw)
    resolved = candidate if candidate.is_absolute() else (study / candidate)
    try:
        rel = resolved.resolve().relative_to(study.resolve()).as_posix()
    except ValueError as exc:
        raise WorkflowError(f"{label} {raw!r} is outside the study directory") from exc
    if not resolved.is_file():
        raise WorkflowError(f"{label} {rel!r} does not exist")
    return rel, sha256_file(resolved)
