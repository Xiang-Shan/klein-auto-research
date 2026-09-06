"""The extension event envelope and the bytes it hashes.

One envelope shape for every generation event, mirroring
:mod:`kleinlib.events` without touching it: the core chain stays exactly what it
was, and this chain is a second, independent one under ``generation/``.

The hash rule is the core's rule: ``event_hash =
sha256(canonical_json(body without event_hash))``.  Two fields deserve a warning
label:

``created_at``
    Informational.  Nothing in this package decides anything from a timestamp;
    order is established by the three witnesses in
    :mod:`kleinlib.generation.chronology`.

``actor`` / ``tool`` / ``model`` / ``session``
    TESTIMONY.  They are self-reported strings from optional CLI flags and are
    never authenticated.  "This model wrote this receipt" is a claim the record
    carries, not a fact the record establishes.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..primitives import canonical_json, sha256_bytes

__all__ = [
    "GENERATION_SCHEMA",
    "TESTIMONY_FIELDS",
    "body_hash",
    "build_event",
    "event_id",
    "testimony",
]

#: The schema tag every generation event, object and receipt carries.
GENERATION_SCHEMA = "klein-generation/1"

#: The self-reported provenance fields.  Recorded, never verified.
TESTIMONY_FIELDS: tuple[str, ...] = ("actor", "tool", "model", "session")


def event_id(sequence: int) -> str:
    """``G0001`` for sequence 1 — the extension's id grammar."""
    return f"G{sequence:04d}"


def testimony(source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The four testimony fields, defaulted to ``None``.

    ``source`` is normally an ``argparse`` namespace's ``vars()``; anything the
    caller did not supply is recorded as null rather than omitted, so the
    envelope's key set never varies.
    """
    values = source or {}
    return {field: values.get(field) or None for field in TESTIMONY_FIELDS}


def body_hash(body: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in body.items() if key != "event_hash"}
    return sha256_bytes(canonical_json(payload).encode())


def build_event(
    *,
    sequence: int,
    event_type: str,
    study: str,
    created_at: str,
    core_anchor: Mapping[str, Any],
    git_head: str | None,
    previous_event_hash: str | None,
    payload_sha256: str | None = None,
    parent_ids: tuple[str, ...] | list[str] = (),
    testimony_fields: Mapping[str, Any] | None = None,
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One sealed envelope.

    ``summary`` carries the small, type-specific keys a reader needs without
    opening the object (``checkpoint``, ``track``, ``verdict``, ``capability``,
    ``run``).  It may not shadow an envelope field: the envelope is the
    contract, and a summary key that overwrote ``core_anchor`` would make the
    chain lie.
    """
    body: dict[str, Any] = {
        "schema": GENERATION_SCHEMA,
        "id": event_id(sequence),
        "sequence": sequence,
        "type": event_type,
        "study": study,
        **testimony(testimony_fields),
        "created_at": created_at,
        "parent_ids": list(parent_ids),
        "payload_sha256": payload_sha256,
        "core_anchor": dict(core_anchor),
        "git_head": git_head,
        "previous_event_hash": previous_event_hash,
    }
    for key, value in (summary or {}).items():
        if key in body or key == "event_hash":
            raise ValueError(f"summary key {key!r} shadows an envelope field")
        body[key] = value
    body["event_hash"] = body_hash(body)
    return body
