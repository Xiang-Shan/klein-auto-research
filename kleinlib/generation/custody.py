"""Custody attestations — the one thing in this package that is pure testimony.

Every other receipt here is arithmetic on bytes: a hash matches or it does not,
a commit is an ancestor or it is not.  This module records a claim that no
arithmetic can check, and is written so that a reader can never mistake the two.

**A hash is not secrecy.**  Hashing a private bundle proves it was not altered
afterwards.  It proves nothing about who read it in the meantime.  A planted
truth sitting in another directory of the same readable worktree is a hash away
from an honest-looking commitment and no distance at all from the participant.

So "hidden" is an ATTESTATION: a named holder states, in their own words, which
accounts, containers or machines denied access to whom, and optionally points at
a receipt document (an access log export, a signed statement) whose bytes are
hashed.  ``klein generation custody attest`` records that statement, and
``klein generation verify`` reports it as what it is.  A study with no
attestation is not accused of anything — its benchmark outcome is simply
``unverified``, which is the honest word for "nobody said".

**Capability-agnostic on purpose.**  Custody is not one capability's problem: a
planted-truth benchmark custodies a private bundle, a temporal-discovery study
custodies the later block, a wet-lab study custodies a sample chain.  So this
module registers no :class:`~kleinlib.generation.registry.Capability` and appears
in no ``MODULES`` list; the verb needs the generation manifest and nothing else,
and any generation-enabled study may use it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..errors import WorkflowError
from ..primitives import sha256_file
from .envelope import GENERATION_SCHEMA
from .ledger import read_object

__all__ = [
    "ATTEST_TYPE",
    "CUSTODIED",
    "UNVERIFIED",
    "attestation_object",
    "attestation_problems",
    "attestations",
    "custody_state",
    "holders",
]

ATTEST_TYPE = "custody_attested"

#: The two words the record may use.  ``custodied`` means a named holder said
#: so; it never means the mechanism was checked.
CUSTODIED = "custodied"
UNVERIFIED = "unverified"


def attestation_problems(
    *, holder: str | None, mechanism: str | None, statement: str | None
) -> list[str]:
    """The three fields that make an attestation worth recording at all."""
    problems: list[str] = []
    for value, label, note in (
        (holder, "--holder", "a NAMED person or team; 'the team' attests nothing"),
        (
            mechanism,
            "--mechanism",
            "accounts, containers or machines — a directory in the same checkout is not "
            "isolation",
        ),
        (
            statement,
            "--statement",
            "what was denied, to whom, and for how long, in the holder's own words",
        ),
    ):
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{label} is required ({note})")
    return problems


def attestation_object(
    *,
    study: str,
    holder: str,
    mechanism: str,
    statement: str,
    subject: str | None,
    receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """The stored testimony.  ``testimony: true`` is part of the object.

    The flag is not decoration: a reader (or a later tool) that walks the object
    store must be able to separate what was computed from what was said without
    knowing this module's name.
    """
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "custody_attestation",
        "study": study,
        "subject": subject or None,
        "holder": holder,
        "mechanism": mechanism,
        "statement": statement,
        "receipt": dict(receipt) if receipt else None,
        "testimony": True,
    }


def attestations(
    study_dir: Path, events: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    """``[(event, object)]`` for every recorded attestation, in chain order."""
    rows: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    for event in events:
        if event.get("type") != ATTEST_TYPE:
            continue
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            rows.append((event, read_object(study_dir, sha)))
        except WorkflowError:  # reported by the spine's `generation orphans`
            continue
    return rows


def holders(rows: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]]) -> list[str]:
    """The named holders, oldest first, without duplicates."""
    names: list[str] = []
    for _event, obj in rows:
        name = obj.get("holder")
        if isinstance(name, str) and name.strip() and name.strip() not in names:
            names.append(name.strip())
    return names


def custody_state(
    rows: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> str:
    """``custodied`` when someone attested; ``unverified`` when nobody did."""
    return CUSTODIED if holders(rows) else UNVERIFIED


def receipt_reference(study_dir: Path, relpath: str) -> dict[str, Any]:
    """``{path, sha256}`` for a receipt document that must live in the study.

    A receipt on the custodian's own machine cannot be hashed by a reader of
    this repository, so it is not accepted: either the document is in the record
    or the attestation stands on the statement alone (``--receipt`` omitted).
    """
    candidate = Path(relpath)
    resolved = candidate if candidate.is_absolute() else (study_dir / candidate)
    try:
        rel = resolved.resolve().relative_to(study_dir.resolve()).as_posix()
    except ValueError as exc:
        raise WorkflowError(
            f"--receipt {relpath!r} is outside the study; a receipt nobody in this "
            "repository can hash is not a receipt this record can carry"
        ) from exc
    if not resolved.is_file():
        raise WorkflowError(f"--receipt {rel!r} does not exist")
    return {"path": rel, "sha256": sha256_file(resolved)}
