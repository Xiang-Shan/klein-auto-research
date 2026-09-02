"""``study_state.json``: the machine state of a study, and the gate records.

Extracted verbatim from :mod:`kleinlib.workflow`.  The state file is a receipt,
never a hand-edited input: :func:`initial_state` shapes it, :func:`load_state`
reads it and tops up contract-derived per-track maps in memory,
:func:`record_gate` and :func:`acknowledge_headroom` are the only writers that
add acknowledgements, and every one of them files its own state commit.

Note the direction of the dependency: this module calls
:func:`kleinlib.transaction.commit_state_writes` directly rather than through
``workflow``'s thin wrapper — a gate record is not part of a run transaction and
has no committer to inject.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .contract import (
    GATE_ARTIFACTS,
    PLACEHOLDER_RE,
    SUPPORTED_SCHEMA_VERSIONS,
    _phase_ids,
    load_contract,
    normalize_tracks,
    prepared_data_path,
    schema_version,
    split_fingerprint,
)
from .decision import _headroom_context, _incumbent
from .errors import WorkflowError
from .events import append_event
from .manifest import load_manifests
from .primitives import (
    StudyLock,
    atomic_write_json,
    fingerprint_path,
    sha256_file,
    utc_now,
)
from .transaction import commit_state_writes

__all__ = [
    "acknowledge_headroom",
    "initial_state",
    "load_state",
    "reconcile_state",
    "record_gate",
    "registered_partition_fingerprints",
    "save_state",
    "split_policy_hash",
    "state_path",
    "verifier_script_hashes",
]

def initial_state(study_dir: Path, contract: Mapping[str, Any]) -> dict[str, Any]:
    tracks = normalize_tracks(contract)
    phase_ids = _phase_ids(contract)
    return {
        "schema_version": schema_version(contract),
        "study_id": contract.get("study_id", study_dir.name),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "active",
        "current_phase": phase_ids[0] if phase_ids else None,
        "phase_acknowledgements": {},
        "gates": {
            name: {"status": "pending", "acknowledged_at": None, "acknowledged_by": None}
            for name in GATE_ARTIFACTS
        },
        "artifact_hashes": {},
        "acknowledgements": {},
        "overrides": [],
        "fingerprints": {"data": None, "split": split_fingerprint(contract)},
        "prepared_data": {"path": str(prepared_data_path(study_dir, contract)), "sha256": None},
        "final_holdout_access": {
            name: _sealed_access_zero()
            for name in tracks
        },
        "last_experiment": 0,
    }


def _sealed_access_zero() -> dict[str, Any]:
    """The unused-seal entry `initial_state` generates."""
    return {"count": 0, "accessed_at": None, "experiment": None}


def reconcile_state(state: dict[str, Any], contract: Mapping[str, Any]) -> list[str]:
    """Top up contract-derived per-track maps for tracks added after scaffolding.

    `initial_state` keys `final_holdout_access` by the tracks declared AT
    SCAFFOLD TIME. A track added to study.yaml afterwards — today the only
    way to build a multi-track study — otherwise leaves that map stale and
    `run-one --final-test` refuses with "sealed final-test state is missing
    for track ..." (study 05, E0012; hand-patched again in study 06).

    Adds an unused-seal entry for every contract track that has none. NEVER
    deletes, renames, or overwrites an existing entry: a track dropped from
    the contract keeps its recorded access, a spent seal stays spent, and a
    corrupt non-mapping entry is left to fail the sealed gate rather than
    being silently repaired. In-memory only; callers that persist state
    carry the top-up into their own commit. Returns the track names added.
    """
    added: list[str] = []
    holdout = state.get("final_holdout_access")
    if holdout is None:
        holdout = {}
        state["final_holdout_access"] = holdout
    elif not isinstance(holdout, dict):
        # A corrupt CONTAINER is left exactly as found — replacing it with a
        # fresh zero map would silently re-arm every seal; the sealed gate's
        # isinstance check refuses loudly instead.
        return added
    for track in normalize_tracks(contract):
        if track not in holdout:
            holdout[track] = _sealed_access_zero()
            added.append(track)
    return added


def state_path(study_dir: Path) -> Path:
    return study_dir / "study_state.json"


def load_state(study_dir: Path, contract: Mapping[str, Any], *, create: bool = False) -> dict[str, Any]:
    path = state_path(study_dir)
    if not path.exists():
        if not create:
            raise WorkflowError("study_state.json is missing; create the study with `klein new`")
        state = initial_state(study_dir, contract)
        atomic_write_json(path, state)
        return state
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid study_state.json: {exc}") from exc
    declared = schema_version(contract)
    if not isinstance(value, dict) or value.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
        raise WorkflowError("study_state.json must be a schema_version 2 or 3 object")
    recorded = value.get("schema_version")
    if declared != recorded:
        # A contract that says 3 over state written under 2 would run schema-3
        # rules against schema-2 receipts.  Nothing notarized is ever rewritten
        # in place, so this is a migration, not a load.
        raise WorkflowError(
            f"study.yaml declares schema_version {declared} but study_state.json was "
            f"written at schema_version {recorded} — a study is not migrated by editing "
            "its contract; see docs/migration-schema2-to-3.md"
        )
    reconcile_state(value, contract)
    return value


def save_state(study_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    atomic_write_json(state_path(study_dir), state)


def _method_card_triad(text: str) -> dict[str, bool] | None:
    """Parse the method card's optional ``triad:`` frontmatter (Theory + Papers +
    Practice legs). Returns None when the card declares no triad — older cards
    stay valid; the contract is opt-in via the template."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    try:
        meta = yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return None
    triad = meta.get("triad") if isinstance(meta, dict) else None
    if not isinstance(triad, Mapping):
        return None
    return {leg: bool(triad.get(leg)) for leg in ("theory", "papers", "practice")}


def verifier_script_hashes(study_dir: Path, contract: Mapping[str, Any]) -> dict[str, str]:
    """``{script path: sha256}`` for every declared verifier in the contract.

    Hashed at the METHOD gate and never again: the checker's job is to be the
    fixed thing the search is measured against, so a change to it after E0001 is
    refused exactly like a split-policy change.
    """
    hashes: dict[str, str] = {}
    for spec in normalize_tracks(contract).values():
        verifier = spec.get("verifier")
        if not isinstance(verifier, Mapping):
            continue
        for item in verifier.get("command") or ():
            if not isinstance(item, str) or item.startswith("-"):
                continue
            path = study_dir / item
            if (item.endswith((".py", ".sh")) or "/" in item) and path.is_file():
                hashes[item] = sha256_file(path)
    return hashes


def split_policy_hash(state: Mapping[str, Any]) -> Any:
    """The declared-policy hash, whichever shape ``fingerprints.split`` has.

    Schema 2 stores the policy hash as a bare string; schema 3 stores a mapping
    that also carries the REALIZED ``development`` / ``final_test`` fingerprints
    frozen at the DATA gate.  Readers that only want the policy use this.
    """
    recorded = state.get("fingerprints", {}).get("split")
    return recorded.get("policy") if isinstance(recorded, Mapping) else recorded


def registered_partition_fingerprints(state: Mapping[str, Any]) -> dict[str, str]:
    """``{"development": ..., "final_test": ...}`` as frozen at the DATA gate."""
    recorded = state.get("fingerprints", {}).get("split")
    if not isinstance(recorded, Mapping):
        return {}
    return {
        kind: str(recorded[kind])
        for kind in ("development", "final_test")
        if isinstance(recorded.get(kind), str)
    }


def _freeze_split(study_dir: Path, contract: Mapping[str, Any], state: dict[str, Any]) -> None:
    """Record the policy hash AND what the split actually realizes (schema 3).

    Realizing the partitions means reading the prepared data, which can fail for
    reasons that must not block a gate (a modality with no dataframe, a target
    the card has not settled yet).  So the failure is a note on the record, not
    a refusal — and the run-time check treats an unregistered fingerprint as
    "proceed with a notice", never as a pass.

    A policy change once evidence exists is refused outright: every recorded
    number was measured on the old partitions.
    """
    policy = split_fingerprint(contract)
    previous = split_policy_hash(state)
    if previous is not None and previous != policy and load_manifests(study_dir):
        raise WorkflowError(
            "data.split changed after evidence exists: every recorded number was "
            f"measured on the previous partitions (policy {previous} -> {policy}). "
            "Start a new study, or re-scope this one on the record."
        )
    frozen: dict[str, Any] = {"policy": policy}
    try:
        from .data import partition_fingerprints

        frozen.update(partition_fingerprints(study_dir))
    except Exception as exc:  # noqa: BLE001 — any prepare-side failure is a note
        frozen["note"] = (
            f"[WARN] realized split fingerprints not recorded ({type(exc).__name__}: {exc}); "
            "run-one will proceed with a printed notice instead of comparing"
        )
    state["fingerprints"]["split"] = frozen


def record_gate(
    study_dir: Path,
    gate: str,
    *,
    acknowledged_by: str,
    note: str = "",
    override_reason: str | None = None,
    phase: str | None = None,
) -> dict[str, Any]:
    contract = load_contract(study_dir)
    if schema_version(contract) not in SUPPORTED_SCHEMA_VERSIONS:
        raise WorkflowError("gate state is available only for schema_version 2 or 3 studies")
    if not acknowledged_by.strip():
        raise WorkflowError("--acknowledged-by is required")
    with StudyLock(study_dir):
        state = load_state(study_dir, contract)
        now = utc_now()
        if gate == "phase":
            if override_reason is not None:
                raise WorkflowError(
                    "phase-boundary acknowledgement cannot be overridden; record an explicit acknowledgement"
                )
            if not phase or phase not in _phase_ids(contract):
                raise WorkflowError("--phase must name a configured phase")
            if phase in state.setdefault("phase_acknowledgements", {}):
                raise WorkflowError(f"phase {phase!r} has already been acknowledged")
            current_phase = state.get("current_phase")
            if phase != current_phase:
                raise WorkflowError(
                    f"can acknowledge only the current phase {current_phase!r}, got {phase!r}"
                )
            playbook = study_dir / "playbook.md"
            if not playbook.is_file():
                raise WorkflowError(
                    "phase acknowledgement requires playbook.md — the rolling state of "
                    "play must be refreshed at every phase boundary (see "
                    "references/phase-ritual.md)"
                )
            if PLACEHOLDER_RE.search(playbook.read_text(encoding="utf-8")):
                raise WorkflowError(
                    "playbook.md still contains unresolved placeholders — refresh it "
                    "before acknowledging the phase"
                )
            state.setdefault("phase_acknowledgements", {})[phase] = {
                "acknowledged_at": now,
                "acknowledged_by": acknowledged_by,
                "note": note,
                "playbook_sha256": sha256_file(playbook),
            }
            ids = _phase_ids(contract)
            next_index = ids.index(phase) + 1
            if next_index < len(ids):
                state["current_phase"] = ids[next_index]
            append_event(
                study_dir,
                "phase_acknowledged",
                phase=phase,
                acknowledged_by=acknowledged_by,
                note=note,
                playbook_sha256=state["phase_acknowledgements"][phase]["playbook_sha256"],
            )
            save_state(study_dir, state)
            commit_state_writes(study_dir, f"klein: phase {phase} acknowledged")
            return state
        if gate not in GATE_ARTIFACTS:
            raise WorkflowError(f"unknown gate {gate!r}")
        verb = "override" if override_reason is not None else "record"
        override_hint = (
            " — an override still requires the artifact to exist: it records that the"
            " artifact's conclusion was not met, not that the artifact is skippable"
        )
        artifact_hashes: dict[str, str] = {}
        for name in GATE_ARTIFACTS[gate]:
            path = study_dir / name
            if not path.is_file():
                raise WorkflowError(
                    f"cannot {verb} {gate}: missing {name}"
                    + (override_hint if override_reason is not None else "")
                )
            text = path.read_text(encoding="utf-8")
            if PLACEHOLDER_RE.search(text):
                raise WorkflowError(f"cannot {verb} {gate}: unresolved placeholder in {name}")
            artifact_hashes[name] = sha256_file(path)
        if gate == "method" and schema_version(contract) >= 3:
            state["fingerprints"]["verifier"] = verifier_script_hashes(study_dir, contract)
        if gate == "method" and override_reason is None:
            triad = _method_card_triad(
                (study_dir / "method_card.md").read_text(encoding="utf-8")
            )
            if triad is not None:
                missing = [leg for leg, ok in triad.items() if not ok]
                unnamed = [leg for leg in missing if leg not in note.lower()]
                if missing and unnamed:
                    raise WorkflowError(
                        "method card triad incomplete — "
                        + ", ".join(f"{leg}: false" for leg in missing)
                        + ". Complete the leg(s), or name each missing leg in --note "
                        "with why that is acceptable (the assertion is yours; the "
                        "gate only makes it explicit)."
                    )
        if gate == "data":
            if override_reason is None:
                text = (study_dir / "data_card.md").read_text(encoding="utf-8")
                plain = re.sub(r"[>*_`#]", "", text)
                if not re.search(
                    r"(?im)^\s*(?:decision|status|verdict)\s*:\s*"
                    r"go(?:-with-cautions)?\s*$",
                    plain,
                ):
                    raise WorkflowError(
                        "data_card.md must contain an exact GO or GO-WITH-CAUTIONS decision "
                        "line, e.g. '> **Decision:** GO' or '## Decision: GO-WITH-CAUTIONS' "
                        "(NO-GO blocks by design; use 'klein gate override data --reason ...' "
                        "to proceed against it)"
                    )
            data_path = prepared_data_path(study_dir, contract)
            data_hash = fingerprint_path(data_path)
            state["fingerprints"]["data"] = data_hash
            state["prepared_data"] = {"path": str(data_path), "sha256": data_hash}
            if schema_version(contract) >= 3:
                _freeze_split(study_dir, contract, state)
        status = "overridden" if override_reason is not None else "recorded"
        gate_state = {
            "status": status,
            "acknowledged_at": now,
            "acknowledged_by": acknowledged_by,
            "note": note,
            "artifacts": artifact_hashes,
        }
        if override_reason is not None:
            if not override_reason.strip():
                raise WorkflowError("override requires a non-empty --reason")
            gate_state["reason"] = override_reason
            state.setdefault("overrides", []).append(
                {
                    "gate": gate,
                    "reason": override_reason,
                    "acknowledged_at": now,
                    "acknowledged_by": acknowledged_by,
                }
            )
        state["gates"][gate] = gate_state
        state.setdefault("acknowledgements", {})[gate] = {
            "timestamp": now,
            "by": acknowledged_by,
        }
        # The journal is not a frozen artifact: program.md is REQUIRED to change
        # as the study runs ("living lab notebook"), so its hash lives only in
        # the point-in-time gate record above — live enforcement tracks the
        # contract-like docs.
        enforced_hashes = {k: v for k, v in artifact_hashes.items() if k != "program.md"}
        state.setdefault("artifact_hashes", {}).update(enforced_hashes)
        state["artifact_hashes"].pop("program.md", None)
        append_event(
            study_dir,
            "gate_overridden" if override_reason is not None else "gate_recorded",
            gate=gate,
            acknowledged_by=acknowledged_by,
            note=note,
            reason=override_reason,
            artifact_hashes=artifact_hashes,
        )
        save_state(study_dir, state)
        commit_state_writes(study_dir, f"klein: {gate} gate {status}")
        return state


def acknowledge_headroom(
    study_dir: Path,
    *,
    track: str,
    acknowledged_by: str,
    note: str,
) -> dict[str, Any]:
    """Register that a track's frontier is keep-infeasible (headroom h < 1).

    The acknowledgement is the ledger's record that the closed door was seen
    BEFORE further transactions were spent — the note must name the registered
    branch: 're-scope: ...' (change delta/estimand/data) or 'run-anyway: ...'
    (a pre-committed door-closed sentence, study-08 style).
    """
    contract = load_contract(study_dir)
    if schema_version(contract) not in SUPPORTED_SCHEMA_VERSIONS:
        raise WorkflowError("headroom state is available only for schema_version 2 or 3 studies")
    if not acknowledged_by.strip():
        raise WorkflowError("--acknowledged-by is required")
    if not note.strip():
        raise WorkflowError(
            "--note is required and must name the registered branch: "
            "'re-scope: ...' or 'run-anyway: <pre-committed door-closed sentence>'"
        )
    tracks = normalize_tracks(contract)
    if track not in tracks:
        raise WorkflowError(f"unknown track {track!r}; choose one of {sorted(tracks)}")
    metric = tracks[track]["metric"]
    if not isinstance(metric.get("bound"), Mapping):
        raise WorkflowError(
            f"track {track!r} declares no metric.bound — declare bound.ideal first; "
            "there is nothing to acknowledge"
        )
    with StudyLock(study_dir):
        state = load_state(study_dir, contract)
        context = _headroom_context(
            tracks[track], _incumbent(load_manifests(study_dir), track)
        )
        if context is None:
            raise WorkflowError(
                f"track {track!r}: headroom is undefined — it needs a first keep "
                "(incumbent) and a measured minimum_delta > 0"
            )
        if context["h"] >= 1:
            raise WorkflowError(
                f"track {track!r}: h = {context['h']:.3f} >= 1 — a keep is "
                "arithmetically possible; nothing to acknowledge"
            )
        now = utc_now()
        entry = {
            "h": context["h"],
            "incumbent": context["incumbent"],
            "ideal": context["ideal"],
            "minimum_delta": context["minimum_delta"],
            "infeasible": True,
            "acknowledged_at": now,
            "acknowledged_by": acknowledged_by,
            "note": note,
        }
        state.setdefault("headroom", {})[track] = entry
        append_event(
            study_dir,
            "headroom_acknowledged",
            track=track,
            h=context["h"],
            incumbent=context["incumbent"],
            ideal=context["ideal"],
            minimum_delta=context["minimum_delta"],
            acknowledged_by=acknowledged_by,
            note=note,
        )
        save_state(study_dir, state)
        commit_state_writes(
            study_dir, f"klein: headroom infeasibility acknowledged ({track})"
        )
        return entry
