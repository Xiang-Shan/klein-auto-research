"""``klein generation design lock`` (the ``design`` capability).

The `design` capability's verb.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ...errors import WorkflowError
from ._shared import (
    _error,
    _load,
    _refuse,
    _require_clean,
    _require_healthy_ledger,
    _study,
    _testimony,
    _testimony_fields,
)


def register(actions: argparse._SubParsersAction) -> None:
    """Add the ``design`` sub-group to ``klein generation``."""
    design = actions.add_parser(
        "design",
        help="the evidence design: what the evidence is FOR, locked before the DATA gate",
        description=(
            "Lock evidence_design.yaml before the DATA gate: the estimand and its "
            "population, the uncertainty method and the validity conditions (each "
            "naming a registered prediction whose rule can actually fire it), the "
            "evidence representations and their acquisition custody, the warrant that "
            "carries the evidence to a claim, and the typed continuation. See the "
            "'Evidence design' section of "
            ".claude/skills/klein/references/generation-protocol.md."
        ),
    )
    design_actions = design.add_subparsers(dest="design_action", required=True)

    lock = design_actions.add_parser(
        "lock", help="freeze evidence_design.yaml (before the DATA gate is recorded)"
    )
    _study(lock)
    _testimony(lock)
    lock.add_argument(
        "--allow-late",
        action="store_true",
        help="lock AFTER the data gate: recorded as late and permanently FAILs `design lock`",
    )
    lock.set_defaults(handler=_run_design_lock)


def _design_setup(
    args: argparse.Namespace, *, extra: tuple[str, ...] = ()
) -> tuple[Path, dict[str, Any], dict[str, Any], Path, list[dict[str, Any]]]:
    """Preconditions shared by every design verb.  Raises ``WorkflowError``."""
    from .. import manifest as gm
    from ..admission import declared_capabilities
    from ..chronology import repo_for
    from ..design import CAPABILITY_NAME
    from ..ledger import read_events

    study, contract = _load(args)
    manifest = gm.load_manifest(study)
    if CAPABILITY_NAME not in declared_capabilities(manifest):
        raise WorkflowError(
            f"this study did not declare the {CAPABILITY_NAME!r} capability — "
            "`klein generation init --capability design` does, and the opt-in is "
            "immutable, so an existing study needs a successor rather than an edit"
        )
    _require_healthy_ledger(study)
    _require_clean(study, contract, *extra)
    repo = repo_for(study)
    assert repo is not None  # _require_clean already refused a non-repo
    return study, contract, manifest, repo, read_events(study)


def _run_design_lock(args: argparse.Namespace) -> int:
    """``design lock`` — one transaction: validate, hash, anchor, commit."""
    from ...primitives import sha256_file
    from .. import design as gd
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import gate_events, git_head, read_core_events
    from ..ledger import append_event, commit_artifacts, write_object

    try:
        study, contract, _manifest, repo, events = _design_setup(args, extra=(gd.DESIGN_NAME,))
    except WorkflowError as exc:
        return _error(str(exc))

    if gd.locks(study, events):
        return _error(
            f"{gd.DESIGN_NAME} is already locked — the design is locked once; a change "
            "of estimand, validity condition or warrant is a successor study"
        )
    path = study / gd.DESIGN_NAME
    if not path.is_file():
        return _error(
            f"{gd.DESIGN_NAME} is missing — copy assets/evidence-design-template.yaml "
            "into the study and fill its five blocks"
        )
    try:
        document = gd.parse_design(path)
    except WorkflowError as exc:
        return _error(str(exc))

    study_name = gm.study_id(study, contract)
    problems = gd.design_problems(contract, document, study=study_name)
    if problems:
        return _refuse("; ".join(problems))

    late = bool(gate_events(read_core_events(study), "data"))
    if late and not args.allow_late:
        return _refuse(
            "the data gate is already recorded: the evidence design must be locked "
            "BEFORE the DATA gate, so the estimand and the validity conditions precede "
            "the first look at the evidence. `--allow-late` records the lock anyway; "
            "`generation verify` then FAILs `design lock` permanently."
        )

    design_sha = sha256_file(path)
    warrant = (document.get("claim") or {}).get("warrant")
    obj = gd.lock_object(
        study=study_name, document=document, design_sha256=design_sha, late=late
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gd.LOCK_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        testimony_fields=_testimony_fields(args),
        design_sha256=design_sha,
        warrant=warrant,
        **({"late": True} if late else {}),
    )
    commit_artifacts(
        study,
        f"klein: design lock ({study_name})",
        paths=[gd.DESIGN_NAME, "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} design lock: {gd.DESIGN_NAME} {design_sha[:12]}…, warrant "
        f"{warrant!r}, object {sha[:12]}…"
    )
    for item in (document.get("prediction") or {}).get("validity_conditions") or []:
        if isinstance(item, dict):
            print(f"  - {item.get('rule_ref')}: {item.get('condition')}")
    for entry in (document.get("evidence") or {}).get("acquisition") or []:
        if isinstance(entry, dict) and entry.get("kind") == "acquisition":
            print(
                f"  - acquired {entry.get('source')!r} at {entry.get('acquired_at')}, "
                f"custody attested by {entry.get('attested_by')!r} "
                "(testimony, never verified)"
            )
    if late:
        print(
            "WARNING: late lock recorded — `klein generation verify` will FAIL "
            "`design lock` for the life of this study"
        )
    return 0
