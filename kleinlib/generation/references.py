"""``knowledge/references/<id>.json`` — what a citation actually rests on.

A `references.yaml` row says `verified: true`.  Verified by whom, against what,
and how closely?  A reference RECORD answers that in a form a stranger can
audit: the locator, the one statement the work is cited FOR, the hash of the
bytes that were read, whether those bytes were kept, and — named explicitly —
the **verification basis**, ordered

    read-at-source  >  bibliography  >  abstract-only  >  hash-only

Each basis has a consistency rule, because the honest failure mode here is not
lying, it is *drifting*: "I read it" recorded for a title copied out of another
paper's bibliography.  ``read-at-source`` therefore requires a retained blob
hash, ``hash-only`` requires the hash, ``bibliography`` requires title + year +
identifier, and ``abstract-only`` requires an identifier.  A record that cannot
satisfy its own basis is refused at write time and FAILs at verify time.

**Klein copies no bytes.**  ``source_blob_sha256`` is computed from a file the
driver points at and the file stays where it was; the hash goes into git, the
PDF does not.  ``blob_retained`` is the driver's testimony about whether they
still hold it.  That keeps the store licence-safe and small, and it is the
reason ``hash-only`` exists as a basis at all.

**Records are write-once and live at the REPOSITORY level**, not inside a study:
two studies citing one paper cite one record.  A correction is a NEW id whose
``supersedes`` names the old one — the record that was cited when the claim was
made stays readable forever.

What this does NOT establish: that the ``supported_statement`` is actually
supported by the locator.  Overclaim is a REFEREE obligation
(``references/reference-protocol.md``); no hash can check it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..errors import WorkflowError
from ..primitives import atomic_write_text, canonical_json, sha256_bytes, sha256_file
from .envelope import GENERATION_SCHEMA

__all__ = [
    "ID_RE",
    "RECORD_DIR",
    "VERIFICATION_BASES",
    "build_record",
    "load_record",
    "record_path",
    "record_problems",
    "record_sha256",
    "write_record",
]

#: Repo-relative home of the store.  Repo-level on purpose: a reference is a
#: fact about the literature, not about one study.
RECORD_DIR = "knowledge/references"

#: Record ids are file names, so they are constrained like one.
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

#: Ordered strongest → weakest.  The ORDER is the point: a study may cite a
#: work it only read the abstract of, as long as it says so.
VERIFICATION_BASES: tuple[str, ...] = (
    "read-at-source",
    "bibliography",
    "abstract-only",
    "hash-only",
)


def record_path(repo: Path, record_id: str) -> Path:
    return repo / RECORD_DIR / f"{record_id}.json"


def load_record(repo: Path, record_id: str) -> dict[str, Any] | None:
    """The record, or None when there is no file (an unreadable file raises)."""
    path = record_path(repo, record_id)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"invalid reference record {record_id}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"reference record {record_id} is not an object")
    return value


def record_sha256(repo: Path, record_id: str) -> str | None:
    path = record_path(repo, record_id)
    return sha256_file(path) if path.is_file() else None


def build_record(
    *,
    record_id: str,
    title: str,
    year: Any,
    authors: Sequence[str] = (),
    venue: str | None = None,
    identifier: str | None = None,
    locator: str,
    retrieved_at: str,
    source_blob_sha256: str | None,
    blob_retained: bool,
    supported_statement: str,
    checker: str | None,
    verification_basis: str,
    recorded_by: Mapping[str, Any],
    supersedes: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema": GENERATION_SCHEMA,
        "kind": "reference",
        "id": record_id,
        "bibliographic_metadata": {
            "title": title,
            "authors": list(authors),
            "year": year,
            "venue": venue,
            "identifier": identifier,
        },
        "locator": locator,
        "retrieved_at": retrieved_at,
        "source_blob_sha256": source_blob_sha256,
        "blob_retained": bool(blob_retained),
        "supported_statement": supported_statement,
        "checker": checker,
        "verification_basis": verification_basis,
        "recorded_by": {key: recorded_by.get(key) or None for key in ("actor", "tool", "model", "session")},
    }
    if supersedes:
        record["supersedes"] = supersedes
    return record


def record_problems(record: Mapping[str, Any]) -> list[str]:
    """Every way a record contradicts itself, one line each.

    Checked at ``reference record`` (refusal) and again by the ``expert`` verify
    family (FAIL), because a record can be hand-edited after it was written.
    """
    problems: list[str] = []
    record_id = record.get("id")
    if not isinstance(record_id, str) or not ID_RE.match(record_id):
        problems.append(f"id {record_id!r} must match {ID_RE.pattern}")
    if record.get("schema") != GENERATION_SCHEMA:
        problems.append(f"schema is {record.get('schema')!r}")
    if record.get("kind") != "reference":
        problems.append(f"kind is {record.get('kind')!r}")

    meta = record.get("bibliographic_metadata")
    if not isinstance(meta, Mapping):
        problems.append("bibliographic_metadata must be a mapping")
        meta = {}
    for field in ("locator", "supported_statement"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{field} is required")

    basis = record.get("verification_basis")
    if basis not in VERIFICATION_BASES:
        problems.append(
            f"verification_basis {basis!r} must be one of {', '.join(VERIFICATION_BASES)}"
        )
    blob = record.get("source_blob_sha256")
    retained = record.get("blob_retained")
    if blob is not None and (not isinstance(blob, str) or not re.fullmatch(r"[0-9a-f]{64}", blob)):
        problems.append("source_blob_sha256 must be a sha256 hex digest or null")
    if not isinstance(retained, bool):
        problems.append("blob_retained must be a boolean")

    # The consistency rules — a basis that its own fields cannot support is the
    # citation-laundering failure this record exists to prevent.
    if basis == "read-at-source":
        if not blob:
            problems.append(
                "verification_basis 'read-at-source' requires source_blob_sha256: "
                "reading at the source means there were bytes to hash"
            )
        if retained is not True:
            problems.append(
                "verification_basis 'read-at-source' requires blob_retained: true — "
                "record 'hash-only' instead if the bytes were not kept"
            )
    elif basis == "hash-only" and not blob:
        problems.append("verification_basis 'hash-only' requires source_blob_sha256")
    elif basis == "bibliography":
        for field in ("title", "year", "identifier"):
            if not meta.get(field):
                problems.append(
                    f"verification_basis 'bibliography' requires bibliographic_metadata.{field}"
                )
    elif basis == "abstract-only" and not meta.get("identifier"):
        problems.append(
            "verification_basis 'abstract-only' requires bibliographic_metadata.identifier"
        )
    return problems


def write_record(repo: Path, record: Mapping[str, Any]) -> tuple[Path, str]:
    """Write one record write-once; return its path and sha256.

    Identical bytes under an existing id are a no-op.  DIFFERENT bytes are
    refused: the record that was cited when a claim was made must stay exactly
    what it was, so a correction is a new id whose ``supersedes`` names this one.
    """
    record_id = str(record.get("id"))
    path = record_path(repo, record_id)
    text = canonical_json(record) + "\n"
    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        if existing == text:
            return path, sha256_bytes(text.encode())
        raise WorkflowError(
            f"reference record {record_id!r} already exists with different content — "
            "records are write-once; a correction is a NEW id whose `supersedes` names "
            "this one"
        )
    atomic_write_text(path, text)
    return path, sha256_bytes(text.encode())
