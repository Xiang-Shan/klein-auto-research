"""The ``stop:`` rule — ending a losing phase on the record, not on a hunch.

"Pre-script the branch you think will not fire" (``research-discipline.md``
lesson 7).  A study that keeps spending challengers after the evidence has
stopped moving is not being persistent; it is deciding when to quit AFTER
seeing the outcomes, which is exactly the degree of freedom the ledger exists
to remove.  An optional schema-3 contract block::

    stop:
      max_consecutive_discards: 5
      scope: track            # track (default) | study | phase

pre-registers the number.  When the run of consecutive discards reaches it,
``klein run-one`` refuses BEFORE an experiment id is allocated — a refusal
there burns nothing — until::

    klein stop ack --study <dir> --track <t> --acknowledged-by <you> --note "..."

puts the decision on the record.  The acknowledgement is valid for THAT COUNT
only: the next discard trips the rule again, so "one more idea" is a decision
taken once per idea, in writing.

The counting rule, deliberately narrow:

- a ``discard`` increments the run;
- a ``keep`` (frontier mode) or a ``measured`` cell (registered mode) resets it
  to zero — the study moved;
- a ``crash`` does NEITHER: a crash is evidence, not a verdict, and neither
  proves the direction is dead nor that it lives (``research-discipline.md``
  lesson 8, "keep the crash rows");
- a sealed final test is recorded as ``discard`` by law but is confirmation
  evidence, excluded from the adaptive frontier — and so from this count.

This module mirrors ``kleinlib.decision._enforce_headroom`` /
``kleinlib.state.acknowledge_headroom``: one pure counter, one refusal, one
self-committing acknowledgement.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .contract import load_contract, normalize_tracks, schema_version
from .errors import WorkflowError
from .events import append_event
from .manifest import load_manifests
from .primitives import StudyLock, utc_now
from .state import load_state, save_state
from .transaction import commit_state_writes

__all__ = [
    "acknowledge_stop",
    "consecutive_discards",
    "refuse_if_tripped",
    "stop_scope_key",
    "stop_spec",
]

#: Dispositions that reset the run to zero — the study moved.
_RESETTING = frozenset({"keep", "measured"})

#: Dispositions that neither count nor reset.
_NEUTRAL = frozenset({"crash"})


def stop_spec(contract: Mapping[str, Any]) -> dict[str, Any] | None:
    """The validated ``stop:`` block, or None when the study declared none.

    Schema-3 only: a schema-2 study never negotiated a stop rule mid-flight and
    is not going to start now.
    """
    if schema_version(contract) < 3:
        return None
    block = contract.get("stop")
    if not isinstance(block, Mapping):
        return None
    try:
        maximum = int(block.get("max_consecutive_discards"))
    except (TypeError, ValueError):
        return None  # validate_contract already reported the malformed block
    if maximum <= 0:
        return None
    return {"max_consecutive_discards": maximum, "scope": str(block.get("scope", "track"))}


def stop_scope_key(scope: str, *, track: str, phase: str | None) -> str:
    """The state key a scope's counter and acknowledgement live under.

    Scope-qualified on purpose: a study that widens ``scope`` from ``track`` to
    ``study`` mid-flight must not inherit the narrower scope's acknowledgement.
    """
    if scope == "study":
        return "study"
    if scope == "phase":
        return f"phase:{phase}"
    return f"track:{track}"


def _in_scope(
    manifest: Mapping[str, Any], scope: str, *, track: str, phase: str | None
) -> bool:
    if manifest.get("evaluation_kind", "development") != "development":
        return False  # sealed confirmation evidence is not an adaptive attempt
    if scope == "study":
        return True
    if scope == "phase":
        return str(manifest.get("phase")) == str(phase)
    return str(manifest.get("track")) == track


def consecutive_discards(
    manifests: Sequence[Mapping[str, Any]],
    *,
    scope: str = "track",
    track: str,
    phase: str | None = None,
) -> int:
    """Length of the trailing run of discards in *scope*.

    Walks backwards from the newest manifest: a ``keep`` or ``measured`` stops
    the count, a ``crash`` is stepped over, and everything else in scope with
    disposition ``discard`` adds one.
    """
    run = 0
    for manifest in reversed(list(manifests)):
        if not _in_scope(manifest, scope, track=track, phase=phase):
            continue
        disposition = str(manifest.get("disposition"))
        if disposition in _NEUTRAL:
            continue
        if disposition in _RESETTING:
            break
        if disposition == "discard":
            run += 1
            continue
        break
    return run


def _ack(state: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    entry = state.get("stop")
    entry = entry.get(key) if isinstance(entry, Mapping) else None
    if isinstance(entry, Mapping) and entry.get("acknowledged_at"):
        return entry
    return None


def refuse_if_tripped(
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    manifests: Sequence[Mapping[str, Any]],
    *,
    track: str,
    phase: str | None,
    echo: bool = True,
) -> None:
    """Refuse a development run once the pre-registered stop count is reached.

    Called from ``run_one`` beside the headroom refusal, BEFORE an experiment id
    is allocated: a refusal here spends no slot, no commit and no budget.  Does
    nothing when the study declared no ``stop:`` block, when the run is short of
    the registered number, or when the CURRENT count carries an
    acknowledgement.
    """
    spec = stop_spec(contract)
    if spec is None:
        return
    maximum = spec["max_consecutive_discards"]
    scope = spec["scope"]
    count = consecutive_discards(manifests, scope=scope, track=track, phase=phase)
    if count < maximum:
        return
    key = stop_scope_key(scope, track=track, phase=phase)
    ack = _ack(state, key)
    if ack is not None and int(ack.get("count", -1)) == count:
        if echo:
            print(
                f"[stop] {key}: {count} consecutive discards (registered limit "
                f"{maximum}) — acknowledged by {ack.get('acknowledged_by')}: "
                f"{ack.get('note')}"
            )
        return
    raise WorkflowError(
        f"stop rule: {count} consecutive discards on {key} reached the registered "
        f"limit of {maximum} (scope: {scope}) — this branch was pre-scripted, so "
        "the decision to keep spending is made on the record, not in the moment. "
        f"Register it: klein stop ack --track {track} --acknowledged-by <you> "
        '--note "continue: <what new information the next run buys> | '
        'stop: <the phase is closed>". The acknowledgement covers this count '
        "only; the next discard asks again."
    )


def acknowledge_stop(
    study_dir: Path,
    *,
    track: str,
    acknowledged_by: str,
    note: str,
) -> dict[str, Any]:
    """Record that the stop rule fired and the study chose its branch anyway.

    Mirrors :func:`kleinlib.state.acknowledge_headroom`: the entry is the
    ledger's proof that the closed door was SEEN before more transactions were
    spent, and it is valid for the count it was taken at.
    """
    contract = load_contract(study_dir)
    spec = stop_spec(contract)
    if spec is None:
        raise WorkflowError(
            "this study declares no schema-3 stop: block — there is no stop rule "
            "to acknowledge (declare stop.max_consecutive_discards at CONSULT)"
        )
    if not acknowledged_by.strip():
        raise WorkflowError("--acknowledged-by is required")
    if not note.strip():
        raise WorkflowError(
            "--note is required and must name the branch: "
            "'continue: <what the next run buys>' or 'stop: <the phase is closed>'"
        )
    tracks = normalize_tracks(contract)
    if track not in tracks:
        raise WorkflowError(f"unknown track {track!r}; choose one of {sorted(tracks)}")

    with StudyLock(study_dir):
        state = load_state(study_dir, contract)
        phase = state.get("current_phase")
        scope = spec["scope"]
        manifests = load_manifests(study_dir)
        count = consecutive_discards(manifests, scope=scope, track=track, phase=phase)
        if count < spec["max_consecutive_discards"]:
            raise WorkflowError(
                f"stop rule has not fired: {count} consecutive discards on "
                f"{stop_scope_key(scope, track=track, phase=phase)} is below the "
                f"registered limit of {spec['max_consecutive_discards']} — nothing "
                "to acknowledge"
            )
        key = stop_scope_key(scope, track=track, phase=phase)
        entry = {
            "scope": scope,
            "count": count,
            "max_consecutive_discards": spec["max_consecutive_discards"],
            "acknowledged_at": utc_now(),
            "acknowledged_by": acknowledged_by,
            "note": note,
        }
        state.setdefault("stop", {})[key] = entry
        append_event(
            study_dir,
            "stop_acknowledged",
            key=key,
            scope=scope,
            count=count,
            max_consecutive_discards=spec["max_consecutive_discards"],
            acknowledged_by=acknowledged_by,
            note=note,
        )
        save_state(study_dir, state)
        commit_state_writes(study_dir, f"klein: stop rule acknowledged ({key} at {count})")
        return entry
