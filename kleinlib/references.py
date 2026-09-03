"""``references.yaml`` — the citations a ``ref:<key>`` evidence id resolves to.

The METHOD gate writes the file and it grows through the study
(``references/defaults-and-scaffolding.md``); the claims law resolves every
``ref:<key>`` a claim cites against it (``references/claims-protocol.md`` check 4)
and the referee's check 8 refuses an unverified reference behind a ``confirmed``
claim.  This module is the loader and the shape checker — nothing here touches
the network: DOI liveness is the referee's job, never a verify-time fetch.

Shape (either a top-level ``references:`` mapping or the bare mapping itself)::

    references:
      fisher1936:
        title: "The use of multiple measurements in taxonomic problems"
        authors: "Fisher, R. A."
        year: 1936
        venue: "Annals of Eugenics 7(2)"
        doi: "10.1111/j.1469-1809.1936.tb02137.x"
        verified: true
        verified_by: "klein-method-scholar"
        verified_at: "2026-08-25"

``verified`` is required and boolean; at least one locator (``doi``, ``arxiv``,
``url``) must be present; ``title`` is required.  Everything else is free-form.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .errors import WorkflowError

__all__ = [
    "LOCATOR_FIELDS",
    "REFERENCES_NAME",
    "is_verified",
    "load_references",
    "reference_problems",
    "references_path",
]

#: The file every ``ref:<key>`` resolves against, study-relative.
REFERENCES_NAME = "references.yaml"

#: At least one of these must identify the work.  ``arxiv`` is spelled the way
#: the inquiry model spells it (``doi / arXiv / url``), lowercased as a key.
LOCATOR_FIELDS = ("doi", "arxiv", "url")

#: Required on every entry.
REQUIRED_FIELDS = ("title", "verified")


def references_path(study_dir: Path) -> Path:
    return study_dir / REFERENCES_NAME


def load_references(study_dir: Path) -> dict[str, Any]:
    """The study's reference entries keyed by citation key ({} when absent).

    Accepts both the wrapped form (``references:`` at the top) and a bare
    mapping of key -> entry, because both spellings appear in the wild.
    """
    path = references_path(study_dir)
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"could not read {REFERENCES_NAME}: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise WorkflowError(f"{REFERENCES_NAME} must contain a top-level mapping")
    inner = raw.get("references", raw)
    if not isinstance(inner, Mapping):
        raise WorkflowError(f"{REFERENCES_NAME}: 'references' must be a mapping of key -> entry")
    return {str(key): value for key, value in inner.items()}


def is_verified(entry: Any) -> bool:
    """True only for an entry that says ``verified: true`` in so many words."""
    return isinstance(entry, Mapping) and entry.get("verified") is True


def reference_problems(references: Mapping[str, Any]) -> list[str]:
    """Shape problems, one string each — never raised, always returned."""
    problems: list[str] = []
    for key, entry in references.items():
        if not isinstance(entry, Mapping):
            problems.append(f"{key}: entry must be a mapping")
            continue
        for field in REQUIRED_FIELDS:
            if field not in entry:
                problems.append(f"{key}: missing required field {field!r}")
        verified = entry.get("verified")
        if "verified" in entry and not isinstance(verified, bool):
            problems.append(f"{key}: 'verified' must be a boolean, got {verified!r}")
        if not any(entry.get(field) for field in LOCATOR_FIELDS):
            problems.append(
                f"{key}: needs at least one locator ({', '.join(LOCATOR_FIELDS)}) — "
                "a citation a reader cannot follow is not a reference"
            )
    return problems
