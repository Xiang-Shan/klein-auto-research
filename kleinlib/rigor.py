"""Proportional rigor: what a study's RECORD must look like to be a quick look.

``policy.rigor: quick`` (Klein 3.1, ``docs/design/klein-3.1-quick-look.md``) asks
for less — two gates, no sealed look, no referee — and may claim less. The tier is
a line in a contract, and a contract can be edited. So the engine never takes the
line alone: a study that has spent sealed evidence, or closed ``confirmed``, is
not a quick look whatever its contract now says. Without this, a full study could
take its sealed look, edit itself down to ``quick``, and close with no referee and
no word about it (the independent review of 3.1 did exactly that).

One function, called by every verb that acts on the tier — the gates, the notary,
``finalize`` and ``verify`` — so they cannot disagree.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .contract import rigor
from .manifest import load_manifests

__all__ = ["quick_record_problems", "refuse_if_not_a_quick_look"]


def quick_record_problems(
    study_dir: Path, contract: Mapping[str, Any], state: Mapping[str, Any] | None
) -> list[str]:
    """Why this study's record contradicts ``policy.rigor: quick``.

    Empty for a full study, and for a quick look whose record is one.
    """
    if rigor(contract) != "quick":
        return []
    problems: list[str] = []
    sealed = sorted(
        str(m.get("experiment"))
        for m in load_manifests(study_dir)
        if m.get("evaluation_kind") == "final_test"
    )
    access = state.get("final_holdout_access") if isinstance(state, Mapping) else None
    counted = sorted(
        str(track)
        for track, entry in (access.items() if isinstance(access, Mapping) else ())
        if isinstance(entry, Mapping) and int(entry.get("count", 0) or 0) >= 1
    )
    if sealed or counted:
        spent = ", ".join(sealed) if sealed else "track " + ", ".join(counted)
        problems.append(
            f"sealed evidence has been spent ({spent}): a study that took its sealed look is "
            "judged at full rigor"
        )
    closed = state.get("finalization") if isinstance(state, Mapping) else None
    if isinstance(closed, Mapping) and closed.get("label") == "confirmed":
        problems.append("the study is finalized `confirmed`: a quick look closes `exploratory`")
    return problems


def refuse_if_not_a_quick_look(
    study_dir: Path, contract: Mapping[str, Any], state: Mapping[str, Any] | None, *, verb: str
) -> None:
    """Raise when the contract says ``quick`` and the record says otherwise."""
    from .errors import WorkflowError

    problems = quick_record_problems(study_dir, contract, state)
    if problems:
        raise WorkflowError(
            f"{verb}: the contract declares a quick look (policy.rigor: quick) but "
            + "; ".join(problems)
            + ". Set policy.rigor back to full and record the consult gate again"
        )
