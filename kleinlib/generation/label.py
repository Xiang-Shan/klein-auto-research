"""``klein generation label`` — the dual-pass label, and what it does not mean.

The label is issued only when BOTH audits pass at the same point in history: the
core ``verify_receipt.json`` with ``summary.failed == 0``, and
``generation/verify_receipt.json`` with ``summary.failed == 0``, both still
current (see :func:`kleinlib.generation.verify.receipt_is_current`), on a clean
tree.  Neither pass is sufficient alone: a study with a perfect generation
ledger and a failing core audit has recorded its commitments beautifully and
proved nothing, and the reverse is a lawful study with no commitment record.

**Integrity is not outcome.**  ``generation-verified`` says the record is intact
and every action was admitted before it ran.  It says nothing about whether the
research succeeded — an honestly stopped study with every capability outcome
``incomplete`` can carry it, and a spectacular result with one unadmitted run
cannot.

**The rung is ``local-order``.**  Order is established against this study's own
chains and this repository's own history (see
:mod:`kleinlib.generation.chronology`).  A custody attestation for a pushed,
protected remote ref would raise the rung; the spine never issues that.

``findings.md`` must quote the label line, exactly as ``finalize`` requires its
own label to appear — a machine-checked label nobody wrote down is a label the
reader never sees.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..errors import WorkflowError
from ..primitives import sha256_file
from .envelope import GENERATION_SCHEMA
from .manifest import KNOWN_CAPABILITIES, study_id

__all__ = ["LABEL_NAME", "LABEL_VALUE", "build_label", "findings_line", "label_problems"]

LABEL_NAME = "generation/label.json"
LABEL_VALUE = "generation-verified"

CORE_RECEIPT = "verify_receipt.json"


def findings_line(label: Mapping[str, Any]) -> str:
    """The exact sentence ``findings.md`` has to carry."""
    head = str(label.get("git_head") or "")
    return f"Generation label: {label.get('label')} @ {head[:12]}"


def _receipt(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def label_problems(study_dir: Path, repo: Path | None, head: str | None) -> list[str]:
    """Why the label cannot be issued right now — empty means it can."""
    from .verify import RECEIPT_NAME, receipt_is_current

    problems: list[str] = []
    core = _receipt(study_dir / CORE_RECEIPT)
    extension = _receipt(study_dir / RECEIPT_NAME)
    if core is None:
        problems.append(f"{CORE_RECEIPT} is missing or unreadable — run `klein verify` first")
    else:
        if int(core.get("summary", {}).get("failed", 1)) != 0:
            problems.append(
                f"{CORE_RECEIPT} reports "
                f"{core.get('summary', {}).get('failed')} failed check(s)"
            )
        if not receipt_is_current(repo, core, head):
            problems.append(
                f"{CORE_RECEIPT} is stale: it was written at "
                f"{str(core.get('git_head'))[:12]} and the study has changed since — re-run "
                "`klein verify`"
            )
    if extension is None:
        problems.append(
            f"{RECEIPT_NAME} is missing or unreadable — run `klein generation verify` first"
        )
    else:
        if int(extension.get("summary", {}).get("failed", 1)) != 0:
            problems.append(
                f"{RECEIPT_NAME} reports "
                f"{extension.get('summary', {}).get('failed')} failed check(s)"
            )
        if not receipt_is_current(repo, extension, head):
            problems.append(
                f"{RECEIPT_NAME} is stale: it was written at "
                f"{str(extension.get('git_head'))[:12]} and the study has changed since — "
                "re-run `klein generation verify`"
            )
    return problems


def build_label(
    study_dir: Path, contract: Mapping[str, Any], head: str | None
) -> dict[str, Any]:
    from .verify import RECEIPT_NAME

    core = study_dir / CORE_RECEIPT
    extension = study_dir / RECEIPT_NAME
    if not core.is_file() or not extension.is_file():
        raise WorkflowError("both verify receipts must exist before a label is issued")
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "label",
        "study": study_id(study_dir, contract),
        "label": LABEL_VALUE,
        "git_head": head,
        "core_receipt_sha256": sha256_file(core),
        "generation_receipt_sha256": sha256_file(extension),
        # Every capability this vocabulary will ever hold, declared `n/a` until
        # a later work package can actually score it.  Listing them all keeps
        # the label's key set stable across releases.
        "capabilities": dict.fromkeys(KNOWN_CAPABILITIES, "n/a"),
        "rung": "local-order",
    }
