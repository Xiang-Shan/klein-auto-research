"""Machine-enforced Klein v0.2 study workflow.

The v1 project deliberately kept its research loop human-readable.  Version 2 keeps
that property, but moves the invariants which must never depend on prose into this
module: gate acknowledgements, data/split fingerprints, sealed-test access, bounded
subprocess execution, immutable per-run manifests, and a derived results view.

This is intentionally a single-machine coordinator.  It takes an advisory lock for
every state mutation and refuses concurrent or nested runs.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from . import transaction
from .contract import (
    GATE_ARTIFACTS,
    IDENTIFIER_RE,
    PLACEHOLDER_RE,
    SCHEMA_VERSION,
    STUDY_ID_RE,
    VALID_DISPOSITIONS,
    VALID_GOALS,
    _guardrail_entries,
    _phase_ids,
    _phase_spec,
    load_contract,
    normalize_tracks,
    prepared_data_path,
    resolve_study,
    schema_version,
    split_fingerprint,
    validate_contract,
)
from .decision import (
    METRIC_LINE_RE,
    _enforce_headroom,
    _guardrails_pass,  # noqa: F401  (re-exported as workflow._guardrails_pass)
    _headroom_ack,
    _headroom_context,
    _incumbent,
    choose_disposition,
    parse_metric_log,
    track_headroom,
)
from .errors import WorkflowError
from .events import append_event, events_path, read_events, verify_event_chain
from .manifest import (
    RUN_ID_RE,
    UNSAFE_PAYLOAD_SUFFIXES,
    _artifact_path,
    _evidence_commit,
    _manifest_paths,
    _run_log_evidence,
    artifact_inventory,
    derive_results,
    load_manifests,
    render_results,
    validate_manifest,
)
from .primitives import (
    StudyLock,
    atomic_write_json,
    atomic_write_text,
    canonical_json,
    fingerprint_path,
    sha256_bytes,
    sha256_file,
    utc_now,
)
from .runner import run_logged
from .schema import (
    AUTO_PRINTED_METRIC_KEYS,
    EVALUATOR_PRINTED_KEYS,
    V2_RESULTS_COLUMNS,
)
from .transaction import (
    STATE_WRITE_PATHS as _STATE_WRITE_PATHS,  # noqa: F401  (re-export)
)
from .transaction import (
    assert_run_worktree as _assert_run_worktree,
)
from .transaction import (
    current_branch,
    environment_fingerprint,
    repo_root_for,
)
from .transaction import (
    git as _git,
)
from .transaction import (
    git_blob as _git_blob,  # noqa: F401  (re-export)
)
from .transaction import (
    git_commit as _git_commit,
)
from .transaction import (
    relative as _relative,
)
from .transaction import (
    stage_evidence as _stage_evidence,
)

#: The public workflow surface. Every name below is importable from
#: ``kleinlib.workflow`` and is the SAME object as the one its home module
#: defines (see kleinlib/tests/test_module_split.py, which freezes this list).
__all__ = [
    "AUTO_PRINTED_METRIC_KEYS",
    "Check",
    "EVALUATOR_PRINTED_KEYS",
    "GATE_ARTIFACTS",
    "IDENTIFIER_RE",
    "METRIC_LINE_RE",
    "PLACEHOLDER_RE",
    "ProcessResult",
    "RUN_ID_RE",
    "SCHEMA_VERSION",
    "STRONG_CLAIM_RE",
    "STUDY_ID_RE",
    "StudyLock",
    "UNCERTAINTY_EVIDENCE_RE",
    "UNSAFE_PAYLOAD_SUFFIXES",
    "V2_RESULTS_COLUMNS",
    "VALID_DISPOSITIONS",
    "VALID_GOALS",
    "WorkflowError",
    "acknowledge_headroom",
    "append_event",
    "artifact_inventory",
    "atomic_write_json",
    "atomic_write_text",
    "canonical_json",
    "choose_disposition",
    "current_branch",
    "derive_results",
    "environment_fingerprint",
    "events_path",
    "finalize",
    "fingerprint_path",
    "initial_state",
    "load_contract",
    "load_manifests",
    "load_state",
    "normalize_tracks",
    "parse_metric_log",
    "preflight_checks",
    "prepared_data_path",
    "read_events",
    "reconcile_state",
    "record_gate",
    "recover",
    "render_results",
    "repo_root_for",
    "resolve_study",
    "run_one",
    "run_subprocess",
    "save_state",
    "schema_version",
    "sha256_bytes",
    "sha256_file",
    "split_fingerprint",
    "state_path",
    "status_summary",
    "track_headroom",
    "utc_now",
    "validate_contract",
    "validate_manifest",
    "verify_event_chain",
    "verify_study",
]

STRONG_CLAIM_RE = re.compile(r"(?i)\b(?:real|decisive)\b")
UNCERTAINTY_EVIDENCE_RE = re.compile(
    r"(?i)\b(?:bootstrap(?:ped|ping)?|confidence interval|credible interval|"
    r"standard error|error bars?|uncertainty (?:estimate|interval|quantification)|"
    # Klein's own Phase-0 vocabulary: deltas stated against a measured floor
    # ARE uncertainty-qualified claims.
    r"noise[- ]floor|floor std|seed[- ]block std)\b"
)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    message: str


@dataclass(frozen=True)
class ProcessResult:
    command: tuple[str, ...]
    exit_code: int
    timed_out: bool
    started_at: str
    ended_at: str
    wall_seconds: float


def initial_state(study_dir: Path, contract: Mapping[str, Any]) -> dict[str, Any]:
    tracks = normalize_tracks(contract)
    phase_ids = _phase_ids(contract)
    return {
        "schema_version": SCHEMA_VERSION,
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
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise WorkflowError("study_state.json must be a schema_version 2 object")
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
    if schema_version(contract) != SCHEMA_VERSION:
        raise WorkflowError("gate state is available only for schema_version 2 studies")
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
            _commit_state_writes(study_dir, f"klein: phase {phase} acknowledged")
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
        _commit_state_writes(study_dir, f"klein: {gate} gate {status}")
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
    if schema_version(contract) != SCHEMA_VERSION:
        raise WorkflowError("headroom state is available only for schema_version 2 studies")
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
        _commit_state_writes(
            study_dir, f"klein: headroom infeasibility acknowledged ({track})"
        )
        return entry


def _v2_ledger_problems(study_dir: Path) -> list[str]:
    problems: list[str] = []
    try:
        manifests = load_manifests(study_dir)
    except WorkflowError as exc:
        return [str(exc)]
    for index, manifest in enumerate(manifests, start=1):
        problems.extend(f"{manifest.get('experiment', index)}: {p}" for p in validate_manifest(manifest, index))
    try:
        repo = repo_root_for(study_dir)
        train_rel = _relative(repo, study_dir / "train.py")
    except WorkflowError as exc:
        problems.append(str(exc))
        repo = None
        train_rel = ""
    if repo is not None:
        for manifest_path, manifest in zip(
            _manifest_paths(study_dir), manifests, strict=True
        ):
            run_id = str(manifest.get("experiment", "?"))
            manifest_rel = _relative(repo, manifest_path)
            committed_manifest = _git_blob(repo, "HEAD", manifest_rel)
            if committed_manifest is None:
                problems.append(f"{run_id}: manifest is not tracked at HEAD")
            elif committed_manifest != manifest_path.read_bytes():
                problems.append(f"{run_id}: manifest differs from its HEAD blob")
            for field in ("base_commit", "candidate_commit"):
                commit = manifest.get(field)
                if isinstance(commit, str):
                    resolved = _git(repo, ["cat-file", "-e", f"{commit}^{{commit}}"], check=False)
                    if resolved.returncode:
                        problems.append(f"{run_id}: {field} does not resolve")
            evidence = _evidence_commit(manifest)
            if evidence is not None:
                resolved = _git(repo, ["cat-file", "-e", f"{evidence}^{{commit}}"], check=False)
                if resolved.returncode:
                    problems.append(f"{run_id}: evidence_commit does not resolve")
            base = manifest.get("base_commit")
            candidate = manifest.get("candidate_commit")
            if isinstance(base, str) and isinstance(candidate, str):
                patch = _git(
                    repo,
                    ["diff", "--binary", base, candidate, "--", train_rel],
                    check=False,
                )
                if patch.returncode or sha256_bytes(patch.stdout.encode()) != manifest.get("code_patch_hash"):
                    problems.append(f"{run_id}: code_patch_hash does not match commits")
            artifacts = manifest.get("artifacts", {})
            if isinstance(artifacts, Mapping):
                for rel, meta in artifacts.items():
                    if not isinstance(meta, Mapping):
                        problems.append(f"{run_id}: invalid artifact metadata for {rel}")
                        continue
                    try:
                        path = _artifact_path(study_dir, str(rel))
                    except WorkflowError as exc:
                        problems.append(f"{run_id}: {exc}")
                        continue
                    expected_hash = meta.get("sha256")
                    committed = meta.get("committed") is True
                    if committed and evidence is not None:
                        repo_rel = _relative(repo, path)
                        content = _git_blob(repo, evidence, repo_rel)
                        if content is None:
                            problems.append(
                                f"{run_id}: committed artifact missing from evidence commit: {rel}"
                            )
                        elif sha256_bytes(content) != expected_hash:
                            problems.append(
                                f"{run_id}: committed artifact hash mismatch: {rel}"
                            )
                        if str(rel) == f"runs/{run_id}/run.log":
                            if not path.is_file():
                                problems.append(f"{run_id}: run log is missing: {rel}")
                            elif sha256_file(path) != expected_hash:
                                problems.append(f"{run_id}: run-log hash mismatch: {rel}")
                    elif not path.is_file():
                        problems.append(f"{run_id}: local artifact missing: {rel}")
                    elif sha256_file(path) != expected_hash:
                        problems.append(f"{run_id}: local artifact hash mismatch: {rel}")
    try:
        expected = render_results(manifests)
    except (KeyError, TypeError, ValueError) as exc:
        problems.append(f"could not derive results view from manifests: {exc}")
        expected = None
    path = study_dir / "results.tsv"
    if not path.is_file():
        problems.append("results.tsv is missing")
    elif expected is not None and path.read_text(encoding="utf-8") != expected:
        problems.append("results.tsv is not the exact derived view of runs/*/manifest.json")
    return problems


def _artifact_hash_problems(study_dir: Path, state: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    hashes = state.get("artifact_hashes", {})
    if not isinstance(hashes, Mapping):
        return ["study_state artifact_hashes is invalid"]
    for name, expected in hashes.items():
        path = study_dir / str(name)
        if not path.is_file():
            problems.append(f"recorded gate artifact is missing: {name}")
        elif sha256_file(path) != expected:
            problems.append(f"recorded gate artifact changed after acknowledgement: {name}")
    return problems


def _legacy_results_problems(path: Path) -> list[str]:
    from . import schema

    if not path.is_file():
        return ["results.tsv is missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        rows = list(reader)
    if not rows or not schema.is_valid_header("\t".join(rows[0])):
        return ["v1 results.tsv header is incompatible"]
    problems: list[str] = []
    for index, row in enumerate(rows[1:], start=2):
        problems.extend(f"line {index}: {p}" for p in schema.validate_row(row, n_columns=len(rows[0])))
    return problems


def preflight_checks(
    study_dir: Path,
    *,
    require_clean: bool = True,
    require_branch: bool = True,
) -> list[Check]:
    checks: list[Check] = []
    try:
        contract = load_contract(study_dir)
    except WorkflowError as exc:
        return [Check("study contract", False, str(exc))]
    version = schema_version(contract)
    if version == 1:
        checks.append(Check("schema", True, "v1 compatibility mode (deprecated, explicit warning)"))
        problems = _legacy_results_problems(study_dir / "results.tsv")
        checks.append(Check("legacy ledger", not problems, "; ".join(problems) or "valid five-column ledger"))
        return checks

    contract_problems = validate_contract(contract, study_dir)
    checks.append(Check("study contract", not contract_problems, "; ".join(contract_problems) or "schema_version 2 contract valid"))
    for track_name, track_spec in normalize_tracks(contract).items():
        metric = track_spec["metric"]
        floor = metric.get("noise_floor")
        if not isinstance(floor, Mapping):
            checks.append(
                Check(
                    "noise floor",
                    True,
                    f"track {track_name!r}: not measured — Phase 0 protocol expects a "
                    "k-seed measurement (see consult-protocol.md)",
                )
            )
            continue
        try:
            floor_std = float(floor.get("std"))
            minimum_delta = float(metric.get("minimum_delta", 0))
        except (TypeError, ValueError):
            continue  # validate_contract already reported the malformed block
        checks.append(
            Check(
                "noise floor",
                minimum_delta >= floor_std,
                f"track {track_name!r}: minimum_delta {minimum_delta:.6g} vs measured "
                f"seed std {floor_std:.6g}"
                + (
                    ""
                    if minimum_delta >= floor_std
                    else " — declaring a floor then keeping inside it is the exact "
                    "dishonesty the measurement exists to prevent"
                ),
            )
        )
    try:
        state = load_state(study_dir, contract)
    except WorkflowError as exc:
        checks.append(Check("study state", False, str(exc)))
        return checks
    checks.append(Check("study state", True, "study_state.json loaded"))

    try:
        repo = repo_root_for(study_dir)
        checks.append(Check("git repository", True, str(repo)))
        if require_branch:
            expected = f"experiments/{contract.get('study_id')}"
            branch = current_branch(repo)
            checks.append(Check("git branch", branch == expected, f"current={branch!r}; required={expected!r}"))
        if require_clean:
            dirty = _git(repo, ["status", "--porcelain", "--untracked-files=all"]).stdout.strip()
            checks.append(Check("working tree", not dirty, dirty or "clean"))
    except WorkflowError as exc:
        checks.append(Check("git repository", False, str(exc)))

    phase_ids = _phase_ids(contract)
    current_phase = state.get("current_phase")
    if current_phase not in phase_ids:
        checks.append(
            Check(
                "phase ladder",
                False,
                f"state current_phase {current_phase!r} is not in the contract's "
                f"phases {phase_ids} — phases were renamed/removed after "
                "initialization; amend the contract to match the recorded state",
            )
        )
    else:
        acked = set(state.get("phase_acknowledgements", {}))
        earlier_unacked = [
            pid for pid in phase_ids[: phase_ids.index(current_phase)] if pid not in acked
        ]
        checks.append(
            Check(
                "phase ladder",
                not earlier_unacked,
                (
                    f"contract declares phases before the current one that were never "
                    f"acknowledged: {earlier_unacked} — phases cannot be inserted "
                    "retroactively; fold them into the ladder the machine actually ran"
                )
                if earlier_unacked
                else f"current={current_phase!r}; ladder consistent",
            )
        )

    gates = state.get("gates", {})
    for gate in GATE_ARTIFACTS:
        entry = gates.get(gate, {}) if isinstance(gates, Mapping) else {}
        valid = (
            isinstance(entry, Mapping)
            and entry.get("status") in {"recorded", "overridden"}
            and bool(entry.get("acknowledged_at"))
            and bool(entry.get("acknowledged_by"))
        )
        status = entry.get("status", "missing") if isinstance(entry, Mapping) else "invalid"
        checks.append(Check(f"gate {gate}", valid, f"status={status}"))

    artifact_problems = _artifact_hash_problems(study_dir, state)
    checks.append(Check("gate artifact hashes", not artifact_problems, "; ".join(artifact_problems) or "match"))
    event_problems = verify_event_chain(study_dir)
    checks.append(Check("event chain", not event_problems, "; ".join(event_problems) or "valid"))

    try:
        current_data = fingerprint_path(prepared_data_path(study_dir, contract))
        recorded_data = state.get("fingerprints", {}).get("data")
        checks.append(Check("prepared-data fingerprint", current_data == recorded_data, f"current={current_data}; recorded={recorded_data}"))
    except WorkflowError as exc:
        checks.append(Check("prepared-data fingerprint", False, str(exc)))
    current_split = split_fingerprint(contract)
    recorded_split = state.get("fingerprints", {}).get("split")
    checks.append(Check("split fingerprint", current_split == recorded_split, f"current={current_split}; recorded={recorded_split}"))

    ledger_problems = _v2_ledger_problems(study_dir)
    checks.append(Check("ledger integrity", not ledger_problems, "; ".join(ledger_problems) or "derived view matches manifests"))
    try:
        manifests = load_manifests(study_dir)
    except WorkflowError as exc:
        checks.append(Check("transactions", False, str(exc)))
    else:
        pending = [
            m.get("experiment")
            for m in manifests
            if not isinstance(m.get("transaction"), Mapping)
            or m.get("transaction", {}).get("status") != "complete"
        ]
        checks.append(
            Check("transactions", not pending, f"pending={pending}" if pending else "none pending")
        )
        for headroom_track, headroom_spec in normalize_tracks(contract).items():
            checks.append(
                _headroom_check(headroom_track, headroom_spec, manifests, state)
            )
    train = study_dir / "train.py"
    if not train.is_file():
        checks.append(Check("train.py", False, "missing"))
    else:
        try:
            compile(train.read_text(encoding="utf-8"), str(train), "exec")
        except SyntaxError as exc:
            checks.append(Check("train.py", False, f"syntax error: {exc}"))
        else:
            source = train.read_text(encoding="utf-8")
            if "NotImplementedError" in source:
                checks.append(
                    Check(
                        "train.py",
                        True,
                        "[WARN] syntax valid but scaffold stubs remain "
                        "(NotImplementedError) — fill load_split/build_model "
                        "before the loop; run-one would record the stub as a crash",
                    )
                )
            else:
                checks.append(Check("train.py", True, "syntax valid"))

    # Guardrail visibility (the study-05 F1 lesson): `klein run-one` reads
    # guardrails off the PRINTED metric block, so a declared key the run
    # never prints scores "missing" and discards the candidate. A key is
    # considered visible when the framework auto-prints it, or when it
    # appears textually anywhere in the study's Python sources (the
    # escape hatch for keys printed via `extra=` — naming it in a comment
    # is enough). Advisory only: ok stays True, the message carries [WARN].
    tracks = normalize_tracks(contract)
    sources = _study_python_sources(study_dir)
    # Universal keys plus the aux keys of exactly the evaluator(s) this
    # study's sources actually call — a flat union would bless keys the
    # calling evaluator prints as NA (or not at all), turning this check
    # into a false all-clear on the very failure it exists to catch.
    visible = set(AUTO_PRINTED_METRIC_KEYS)
    for evaluator, keys in EVALUATOR_PRINTED_KEYS.items():
        pattern = re.compile(rf"\b{evaluator}\s*\(")
        if any(pattern.search(text) for text in sources.values()):
            visible |= keys
    invisible: list[str] = []
    for track_name, track_spec in tracks.items():
        entries, _ = _guardrail_entries(track_spec.get("guardrails", {}))
        for key, _spec in entries:
            if key in visible:
                continue
            if any(key in text for text in sources.values()):
                continue
            invisible.append(f"track {track_name!r} declares {key!r}")
    if invisible:
        named = ", ".join(sorted(sources)) if sources else "no study .py files found"
        checks.append(
            Check(
                "guardrail visibility",
                True,
                "[WARN] "
                + "; ".join(invisible)
                + f" — not auto-printed by the evaluator and not named in {named}. "
                "`klein run-one` reads guardrails off the PRINTED block, so an "
                "unprinted guardrail scores \"missing\" and discards the candidate. "
                "Print it via evaluate*(..., extra={<key>: value}).",
            )
        )
    else:
        checks.append(
            Check(
                "guardrail visibility",
                True,
                "every declared guardrail metric is printed by the evaluator "
                "or named in the study's Python sources",
            )
        )
    return checks


def _study_python_sources(study_dir: Path) -> dict[str, str]:
    """The study's Python sources (top level + lib/), for textual scans.

    Wider than train.py on purpose: study 06 declares guardrail keys that
    are computed in analysis.py and only routed through train.py's `extra=`.
    """
    sources: dict[str, str] = {}
    for path in sorted(study_dir.glob("*.py")) + sorted(study_dir.glob("lib/**/*.py")):
        try:
            # errors="replace": a non-UTF-8 study file must degrade to a
            # weaker textual scan, never abort the whole preflight report.
            sources[str(path.relative_to(study_dir))] = path.read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue
    return sources


def run_subprocess(
    command: Sequence[str],
    *,
    cwd: Path,
    log_path: Path,
    timeout_seconds: float,
    echo: bool = True,
    env_overrides: Mapping[str, str] | None = None,
) -> ProcessResult:
    """Run once, stream stdout/stderr to one log, and preserve the real exit code."""
    if timeout_seconds <= 0:
        raise WorkflowError("timeout_seconds must be positive")
    started_at = utc_now()
    result = run_logged(
        command,
        cwd=cwd,
        log_path=log_path,
        timeout_seconds=timeout_seconds,
        echo=echo,
        env_overrides=env_overrides,
    )
    return ProcessResult(
        command=tuple(command),
        exit_code=result.exit_code,
        timed_out=result.timed_out,
        started_at=started_at,
        ended_at=utc_now(),
        wall_seconds=result.wall_seconds,
    )


def _headroom_check(
    track_name: str,
    track_spec: Mapping[str, Any],
    manifests: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any],
) -> Check:
    """Detection-limit disclosure. Always ``ok=True`` — a FAIL here would
    retro-fail ``klein verify`` on finalized studies (verify == preflight);
    enforcement belongs to run-one, where a refusal burns nothing."""
    from .eval import KNOWN_IDEALS

    metric = track_spec["metric"]
    name = metric.get("name")
    if not isinstance(metric.get("bound"), Mapping):
        known = KNOWN_IDEALS.get(name) if isinstance(name, str) else None
        if known is not None:
            return Check(
                "headroom",
                True,
                f"track {track_name!r}: metric {name!r} has a known ideal ({known:g}) "
                "but no metric.bound declared — headroom not audited (HINT: declare "
                "metric.bound.ideal to arm the detection-limit check)",
            )
        return Check(
            "headroom",
            True,
            f"track {track_name!r}: no metric.bound declared — not audited",
        )
    context = _headroom_context(track_spec, _incumbent(manifests, track_name))
    if context is None:
        return Check(
            "headroom",
            True,
            f"track {track_name!r}: bound declared; no incumbent yet (or no measured "
            "minimum_delta) — audited at first keep",
        )
    h = context["h"]
    arithmetic = (
        f"h = ({context['incumbent']:.6g} - {context['ideal']:g}) / "
        f"{context['minimum_delta']:.6g} = {h:.3f}"
    )
    if h >= 1:
        return Check(
            "headroom",
            True,
            f"track {track_name!r}: {arithmetic} — a keep is arithmetically possible "
            "(h >= 1 means not excluded, NOT plausible: the attainable ceiling may "
            "sit short of the ideal)",
        )
    ack = _headroom_ack(state, track_name)
    if ack:
        return Check(
            "headroom",
            True,
            f"track {track_name!r}: {arithmetic} < 1 — infeasible, acknowledged by "
            f"{ack.get('acknowledged_by')} at {ack.get('acknowledged_at')}: "
            f"{ack.get('note')}",
        )
    return Check(
        "headroom",
        True,
        f"track {track_name!r}: [WARN] {arithmetic} < 1 — NO keep is arithmetically "
        "possible: not even a perfect score clears minimum_delta "
        f"(on_infeasible: {context['posture']}). Register awareness with "
        "`klein headroom ack` or re-scope the contract",
    )


def _complete_evidence_transaction(
    repo: Path,
    study_dir: Path,
    manifest: dict[str, Any],
    *,
    restored_train: bool,
    recovery: bool = False,
) -> str:
    """Thin wrapper over :func:`kleinlib.transaction.complete_evidence_transaction`.

    Keeps the private name ``run_one``/``recover`` call, and — critically —
    resolves ``_git_commit`` as a MODULE GLOBAL at call time, so a test that
    patches ``workflow._git_commit`` sees its injected failure fire INSIDE the
    transaction, exactly as it did before the split.
    """
    return transaction.complete_evidence_transaction(
        repo,
        study_dir,
        manifest,
        restored_train=restored_train,
        recovery=recovery,
        commit=_git_commit,
    )


def _commit_state_writes(
    study_dir: Path, message: str, *, paths: Sequence[str] = ()
) -> str | None:
    """Thin wrapper over :func:`kleinlib.transaction.commit_state_writes`, with
    the same call-time ``_git_commit`` lookup as above."""
    return transaction.commit_state_writes(
        study_dir, message, commit=_git_commit, paths=paths
    )


def run_one(
    study_dir: Path,
    *,
    track: str | None = None,
    description: str = "",
    timeout_seconds: float | None = None,
    final_test: bool = False,
    command: Sequence[str] | None = None,
    echo: bool = True,
    allow_rerun: bool = False,
) -> dict[str, Any]:
    contract = load_contract(study_dir)
    problems = validate_contract(contract, study_dir)
    if problems:
        raise WorkflowError("invalid study contract: " + "; ".join(problems))
    tracks = normalize_tracks(contract)
    if track is None:
        if len(tracks) != 1:
            raise WorkflowError("--track is required when study.yaml declares multiple tracks")
        track = next(iter(tracks))
    if track not in tracks:
        raise WorkflowError(f"unknown track {track!r}; choose one of {sorted(tracks)}")
    repo = repo_root_for(study_dir)
    expected_branch = f"experiments/{contract['study_id']}"
    if current_branch(repo) != expected_branch:
        raise WorkflowError(f"run-one requires exact branch {expected_branch!r}")

    with StudyLock(study_dir):
        state = load_state(study_dir, contract)
        gates = state.get("gates")
        for gate in GATE_ARTIFACTS:
            entry = gates.get(gate) if isinstance(gates, Mapping) else None
            if (
                not isinstance(entry, Mapping)
                or entry.get("status") not in {"recorded", "overridden"}
                or not entry.get("acknowledged_at")
                or not entry.get("acknowledged_by")
            ):
                raise WorkflowError(f"gate {gate} is not recorded or overridden")
        if _artifact_hash_problems(study_dir, state):
            raise WorkflowError("a gate artifact changed after acknowledgement; record it again")
        if verify_event_chain(study_dir):
            raise WorkflowError("events.jsonl hash chain is invalid")
        data_hash = fingerprint_path(prepared_data_path(study_dir, contract))
        fingerprints = state.get("fingerprints")
        if not isinstance(fingerprints, Mapping) or data_hash != fingerprints.get("data"):
            raise WorkflowError("prepared-data fingerprint differs from the recorded DATA gate")
        if split_fingerprint(contract) != fingerprints.get("split"):
            raise WorkflowError("split policy differs from the recorded fingerprint")
        ledger = load_manifests(study_dir)
        if any(
            not isinstance(m.get("transaction"), Mapping)
            or m.get("transaction", {}).get("status") != "complete"
            for m in ledger
        ):
            raise WorkflowError("an interrupted transaction exists; run `klein recover` first")

        phase_id = str(state.get("current_phase"))
        phase = _phase_spec(contract, phase_id)
        final_phase_id = _phase_ids(contract)[-1]
        if final_test:
            # The ledger is the tamper-evident record (manifests are
            # hash-committed; study_state.json is not): a sealed access
            # recorded there refuses a second one even if the state map was
            # edited or a topped-up entry re-zeroed the counter.
            spent = [
                m for m in ledger
                if str(m.get("track")) == track
                and m.get("evaluation_kind") == "final_test"
            ]
            if spent:
                raise WorkflowError(
                    f"sealed final test for track {track!r} has already been accessed by "
                    f"{spent[0].get('experiment')} (recorded in the ledger)"
                )
            holdout = state.get("final_holdout_access")
            access = holdout.get(track) if isinstance(holdout, Mapping) else None
            if not isinstance(access, Mapping):
                raise WorkflowError(f"sealed final-test state is missing for track {track!r}")
            if int(access.get("count", 0)) >= 1:
                raise WorkflowError(f"sealed final test for track {track!r} has already been accessed")
            if phase_id != final_phase_id:
                raise WorkflowError(
                    f"sealed final test is allowed only in final phase {final_phase_id!r}; "
                    f"current phase is {phase_id!r}"
                )
        elif phase_id == final_phase_id:
            raise WorkflowError(
                f"development runs are forbidden in final phase {final_phase_id!r}; "
                "use --final-test"
            )
        _assert_run_worktree(repo, study_dir)

        phase_runs = [m for m in load_manifests(study_dir) if str(m.get("phase")) == phase_id]
        if len(phase_runs) >= int(phase["max_experiments"]):
            raise WorkflowError(f"phase {phase_id} reached max_experiments; record its acknowledgement")
        spent = sum(float(m.get("wall_seconds", 0)) for m in phase_runs)
        phase_budget = float(phase["budget_seconds"])
        remaining_budget = phase_budget - spent
        if remaining_budget <= 0:
            raise WorkflowError(f"phase {phase_id} exhausted budget_seconds")

        configured_timeout = float(contract["max_run_seconds"])
        timeout = configured_timeout if timeout_seconds is None else float(timeout_seconds)
        if timeout <= 0 or timeout > configured_timeout:
            raise WorkflowError(
                f"timeout must be > 0 and <= configured max_run_seconds={configured_timeout:g}"
            )
        timeout = min(timeout, remaining_budget)
        manifests = load_manifests(study_dir)
        incumbent = _incumbent(manifests, track)
        if not final_test:
            _enforce_headroom(state, tracks[track], track, incumbent, echo=echo)
        number = len(manifests) + 1
        run_id = f"E{number:04d}"

        train_rel = _relative(repo, study_dir / "train.py")
        if (
            not final_test
            and command is None
            and not allow_rerun
            and not _git(repo, ["status", "--porcelain", "--", train_rel]).stdout.strip()
        ):
            # Before any E#### is allocated, run dir created, or commit made —
            # a refusal here burns nothing. The sealed final test re-runs the
            # incumbent with an empty diff BY DESIGN and stays exempt, as do
            # declared --command overrides.
            raise WorkflowError(
                "train.py is unchanged since HEAD — this run would re-execute the "
                "incumbent configuration and burn a phase slot; edit train.py with "
                "ONE falsifiable change, or pass --allow-rerun for an intentional "
                "identical replication"
            )
        base_commit = _git(repo, ["rev-parse", "HEAD"]).stdout.strip()
        _git(repo, ["add", "--", train_rel])
        candidate_commit = _git_commit(repo, f"candidate {run_id}: {description or track}", allow_empty=True)
        patch = _git(repo, ["diff", "--binary", base_commit, candidate_commit, "--", train_rel]).stdout.encode()
        patch_hash = sha256_bytes(patch)
        empty_diff = patch == b""
        env_hash, env_details = environment_fingerprint(repo)
        run_dir = study_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        log_path = run_dir / "run.log"
        manifest: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "experiment": run_id,
            "track": track,
            "phase": phase_id,
            "incumbent": (incumbent or {}).get("experiment"),
            "evaluation_kind": "final_test" if final_test else "development",
            "started_at": utc_now(),
            "ended_at": None,
            "base_commit": base_commit,
            "candidate_commit": candidate_commit,
            "code_patch_hash": patch_hash,
            "command": list(command or ("uv", "run", "--locked", "python", "-u", "train.py")),
            "max_run_seconds": timeout,
            "phase_budget_seconds": phase_budget,
            "phase_experiment_limit": int(phase["max_experiments"]),
            "exit_code": None,
            "timed_out": False,
            "primary_metric": None,
            "metric_name": tracks[track]["metric"]["name"],
            "metric_goal": tracks[track]["metric"]["goal"],
            "metrics": {},
            "fingerprints": {
                "data": data_hash,
                "split": split_fingerprint(contract),
                "environment": env_hash,
            },
            "environment": env_details,
            "artifacts": {},
            "disposition": "crash",
            "description": description or f"{track} candidate {run_id}",
            "decision_reason": "run transaction started",
            "transaction": {"status": "pending", "started_at": utc_now()},
        }
        if empty_diff:
            manifest["empty_candidate_diff"] = True
        atomic_write_json(run_dir / "manifest.json", manifest)
        append_event(
            study_dir,
            "run_started",
            experiment=run_id,
            track=track,
            phase=manifest["phase"],
            candidate_commit=candidate_commit,
            **({"empty_diff": True} if empty_diff else {}),
        )
        artifacts_before = artifact_inventory(study_dir)
        if final_test:
            state["final_holdout_access"][track] = {
                "count": 1,
                "accessed_at": utc_now(),
                "experiment": run_id,
            }
            save_state(study_dir, state)

        cmd = tuple(command or ("uv", "run", "--locked", "python", "-u", "train.py"))
        process = run_subprocess(
            cmd,
            cwd=study_dir,
            log_path=log_path,
            timeout_seconds=timeout,
            echo=echo,
            env_overrides={
                "KLEIN_EVALUATION_KIND": "final_test" if final_test else "development",
                "KLEIN_EXPERIMENT_ID": run_id,
                "KLEIN_TRACK": track,
                # A real run force-clears ambient smoke mode: an exported
                # KLEIN_SMOKE=1 in the driving shell must never silently
                # suppress evidence writes.
                "KLEIN_SMOKE": "",
            },
        )
        manifest.update(
            {
                "started_at": process.started_at,
                "ended_at": process.ended_at,
                "wall_seconds": process.wall_seconds,
                "exit_code": process.exit_code,
                "timed_out": process.timed_out,
            }
        )
        if process.exit_code == 0:
            try:
                primary, printed_name, printed_goal, metrics = parse_metric_log(log_path)
                expected_metric = tracks[track]["metric"]
                if printed_name != expected_metric["name"]:
                    raise WorkflowError(
                        f"evaluator metric_name={printed_name!r}; track requires {expected_metric['name']!r}"
                    )
                if printed_goal != expected_metric["goal"]:
                    raise WorkflowError(
                        f"evaluator metric_goal={printed_goal!r}; track requires {expected_metric['goal']!r}"
                    )
                disposition, reason = choose_disposition(
                    primary_metric=primary,
                    track_spec=tracks[track],
                    metrics=metrics,
                    incumbent=incumbent,
                    final_test=final_test,
                )
                manifest.update(
                    primary_metric=primary,
                    metrics=metrics,
                    disposition=disposition,
                    decision_reason=reason,
                )
            except WorkflowError as exc:
                manifest["decision_reason"] = str(exc)
        else:
            manifest["decision_reason"] = (
                f"timeout after {timeout:g}s" if process.timed_out else f"process exit code {process.exit_code}"
            )
        artifacts_after = artifact_inventory(study_dir)
        manifest["artifacts"] = {
            rel: meta
            for rel, meta in artifacts_after.items()
            if rel not in artifacts_before
            or meta.get("sha256") != artifacts_before[rel].get("sha256")
        }
        for meta in manifest["artifacts"].values():
            meta["availability"] = "recorded" if meta.get("committed") else "local"
        manifest["artifacts"][f"runs/{run_id}/run.log"] = _run_log_evidence(
            study_dir, run_id
        )
        manifest["transaction"] = {"status": "pending", "ready_at": utc_now()}
        if manifest["decision_reason"] and description:
            manifest["description"] = f"{description}; {manifest['decision_reason']}"
        elif manifest["decision_reason"]:
            manifest["description"] = manifest["decision_reason"]
        atomic_write_json(run_dir / "manifest.json", manifest)
        append_event(
            study_dir,
            "run_finished",
            experiment=run_id,
            exit_code=process.exit_code,
            timed_out=process.timed_out,
            disposition=manifest["disposition"],
            primary_metric=manifest["primary_metric"],
        )
        state["last_experiment"] = number
        save_state(study_dir, state)

        restored = manifest["disposition"] != "keep" or final_test
        if restored:
            _git(repo, ["restore", "--source", base_commit, "--", train_rel])
        _complete_evidence_transaction(
            repo, study_dir, manifest, restored_train=restored
        )
        return manifest


def recover(study_dir: Path) -> list[str]:
    contract = load_contract(study_dir)
    repo = repo_root_for(study_dir)
    recovered: list[str] = []
    with StudyLock(study_dir):
        state = load_state(study_dir, contract)
        for manifest_path in _manifest_paths(study_dir):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            run_id = str(manifest["experiment"])
            manifest_rel = _relative(repo, manifest_path)
            transaction = manifest.get("transaction", {})
            dirty_manifest = bool(
                _git(
                    repo,
                    ["status", "--porcelain", "--untracked-files=all", "--", manifest_rel],
                ).stdout.strip()
            )
            head = _git(repo, ["rev-parse", "HEAD"]).stdout.strip()
            head_subject = _git(repo, ["log", "-1", "--format=%s"]).stdout.strip()
            if transaction.get("status") == "complete":
                if not dirty_manifest:
                    continue
                evidence = _evidence_commit(manifest)
                expected_subject = f"evidence {run_id}: {manifest.get('disposition')}"
                if head != evidence or head_subject != expected_subject:
                    raise WorkflowError(
                        f"refusing to recover modified complete manifest {run_id}; "
                        "HEAD is not its recorded evidence-commit window"
                    )
                # The prepare commit succeeded and the finalization commit did not.
                # Complete it without manufacturing a second prepare commit.
                derive_results(study_dir)
                _stage_evidence(repo, study_dir, manifest)
                _git_commit(repo, f"transaction {run_id}: recover finalization")
                recovered.append(run_id)
                continue

            parent = _git(repo, ["rev-parse", "HEAD^"], check=False).stdout.strip()
            prepared_already = (
                head_subject == f"evidence {run_id}: {manifest.get('disposition')}"
                and parent == manifest.get("candidate_commit")
            )
            if prepared_already:
                # Recover the narrow interruption window after the prepare commit but
                # before its manifest was marked complete.
                manifest["transaction"] = {
                    "status": "complete",
                    "committed_at": utc_now(),
                    "evidence_commit": head,
                    "recovered": True,
                }
                atomic_write_json(manifest_path, manifest)
                append_event(
                    study_dir,
                    "transaction_recovered",
                    experiment=run_id,
                    disposition=manifest["disposition"],
                    evidence_commit=head,
                )
                derive_results(study_dir)
                _stage_evidence(repo, study_dir, manifest)
                _git_commit(repo, f"transaction {run_id}: recover finalization")
                recovered.append(run_id)
                continue
            if head != manifest.get("candidate_commit"):
                raise WorkflowError(
                    f"refusing to recover {run_id}: HEAD is neither its candidate "
                    "nor its recorded evidence commit"
                )
            if manifest.get("ended_at") is None:
                manifest.update(
                    ended_at=utc_now(),
                    exit_code=125,
                    timed_out=False,
                    primary_metric=None,
                    disposition="crash",
                    decision_reason="recovered interrupted run with no terminal record",
                    description="recovered interrupted run with no terminal record",
                )
            match = RUN_ID_RE.match(run_id)
            if match:
                state["last_experiment"] = max(
                    int(state.get("last_experiment", 0)), int(match.group(1))
                )
            if manifest.get("evaluation_kind") == "final_test":
                track = str(manifest.get("track"))
                access = state.setdefault("final_holdout_access", {}).setdefault(track, {})
                access.update(
                    count=1,
                    accessed_at=access.get("accessed_at") or utc_now(),
                    experiment=run_id,
                )
            log_path = manifest_path.parent / "run.log"
            if not log_path.exists():
                atomic_write_text(log_path, "[KLEIN] recovered interrupted transaction\n")
            manifest["artifacts"] = artifact_inventory(study_dir)
            for meta in manifest["artifacts"].values():
                meta["availability"] = "recorded" if meta.get("committed") else "local"
            manifest["artifacts"][f"runs/{run_id}/run.log"] = _run_log_evidence(
                study_dir, run_id
            )
            atomic_write_json(manifest_path, manifest)
            train_rel = _relative(repo, study_dir / "train.py")
            restored = manifest.get("disposition") != "keep" or manifest.get("evaluation_kind") == "final_test"
            if restored:
                _git(repo, ["restore", "--source", str(manifest["base_commit"]), "--", train_rel])
            save_state(study_dir, state)
            _complete_evidence_transaction(
                repo, study_dir, manifest, restored_train=restored, recovery=True
            )
            recovered.append(run_id)
    _commit_state_writes(study_dir, "klein: recover — state writes filed")
    return recovered


def verify_study(study_dir: Path) -> list[Check]:
    contract = load_contract(study_dir)
    if schema_version(contract) == 1:
        problems = _legacy_results_problems(study_dir / "results.tsv")
        return [
            Check(
                "legacy warning",
                True,
                "schema_version missing means v1; readable through the deprecated v1 adapter"
                " — no study evidence is rewritten",
            ),
            Check(
                "legacy errata",
                True,
                "v1 discard/crash rows may use `-` because exact candidate commits were not retained",
            ),
            Check(
                "legacy errata",
                True,
                "v1 has no machine-recorded gates, split fingerprint, track frontier, or sealed test count",
            ),
            Check(
                "legacy migration",
                True,
                "create a new v2 study; preserve this directory as immutable legacy evidence",
            ),
            Check("legacy ledger", not problems, "; ".join(problems) or "valid"),
        ]
    return preflight_checks(study_dir, require_clean=False, require_branch=False)


def finalize(study_dir: Path, *, allow_exploratory: bool = False) -> str:
    contract = load_contract(study_dir)
    tracks = normalize_tracks(contract)
    with StudyLock(study_dir):
        state = load_state(study_dir, contract)
        manifests = load_manifests(study_dir)
        pending = [
            m["experiment"]
            for m in manifests
            if m.get("transaction", {}).get("status") != "complete"
        ]
        if pending:
            raise WorkflowError(f"cannot finalize with pending transactions: {pending}")
        counts = {
            track: int(state.get("final_holdout_access", {}).get(track, {}).get("count", 0))
            for track in tracks
        }
        if any(count > 1 for count in counts.values()):
            raise WorkflowError("sealed final-test access count exceeds one")
        successful_confirmation: dict[str, str | None] = {}
        for track in tracks:
            successful = next(
                (
                    str(manifest.get("experiment"))
                    for manifest in manifests
                    if manifest.get("track") == track
                    and manifest.get("evaluation_kind") == "final_test"
                    and manifest.get("exit_code") == 0
                    and isinstance(manifest.get("primary_metric"), (int, float))
                    and math.isfinite(float(manifest["primary_metric"]))
                ),
                None,
            )
            successful_confirmation[track] = successful
        label = (
            "confirmed"
            if counts
            and all(count == 1 for count in counts.values())
            and all(successful_confirmation.values())
            else "exploratory"
        )
        if label == "exploratory" and not allow_exploratory:
            raise WorkflowError(
                "not every track has one successful sealed final-test evaluation; "
                "use --allow-exploratory to finalize explicitly"
            )
        findings = study_dir / "findings.md"
        if not findings.is_file():
            raise WorkflowError("findings.md is required before finalize")
        text = findings.read_text(encoding="utf-8")
        if not re.search(rf"(?i)\b{label}\b", text):
            raise WorkflowError(f"findings.md must explicitly label the study `{label}`")
        if STRONG_CLAIM_RE.search(text) and not UNCERTAINTY_EVIDENCE_RE.search(text):
            # Loud warning, not a hard stop: prose like "the real dataset" is a
            # false positive; the enforceable epistemics live in the label check
            # above and the sealed-access counts. See synthesis-protocol quality bar.
            print(
                "klein: warning: findings.md uses 'real'/'decisive' language without "
                "explicit uncertainty evidence (confidence interval, bootstrap, or "
                "standard error) — soften the claim or add the evidence",
                file=sys.stderr,
            )
        state["status"] = "finalized"
        state["finalization"] = {
            "label": label,
            "timestamp": utc_now(),
            "final_holdout_counts": counts,
            "successful_confirmation": successful_confirmation,
        }
        save_state(study_dir, state)
        append_event(
            study_dir,
            "study_finalized",
            label=label,
            final_holdout_counts=counts,
            successful_confirmation=successful_confirmation,
        )
        _commit_state_writes(study_dir, f"klein: finalized {label}")
        return label


def status_summary(study_dir: Path) -> str:
    contract = load_contract(study_dir)
    version = schema_version(contract)
    if version == 1:
        rows = max(0, len((study_dir / "results.tsv").read_text(encoding="utf-8").splitlines()) - 1)
        return f"study: {study_dir.name}\nschema: v1 (deprecated compatibility)\nexperiments: {rows}\n"
    state = load_state(study_dir, contract)
    manifests = load_manifests(study_dir)
    counts = {key: 0 for key in VALID_DISPOSITIONS}
    for manifest in manifests:
        counts[str(manifest.get("disposition"))] = counts.get(str(manifest.get("disposition")), 0) + 1
    lines = [
        f"study: {state['study_id']}",
        "schema: v2",
        f"status: {state.get('status')}",
        f"current phase: {state.get('current_phase')}",
        f"experiments: {len(manifests)} (keep={counts['keep']} discard={counts['discard']} crash={counts['crash']})",
        "gates: " + ", ".join(f"{k}={v.get('status')}" for k, v in state.get("gates", {}).items()),
        "final holdout: " + ", ".join(f"{k}={v.get('count', 0)}/1" for k, v in state.get("final_holdout_access", {}).items()),
    ]
    confirmed_runs = {
        str(manifest.get("track")): str(manifest.get("experiment"))
        for manifest in manifests
        if manifest.get("evaluation_kind") == "final_test"
        and manifest.get("exit_code") == 0
        and isinstance(manifest.get("primary_metric"), (int, float))
        and math.isfinite(float(manifest["primary_metric"]))
    }
    lines.append(
        "successful confirmation: "
        + ", ".join(
            f"{track}={confirmed_runs.get(track, 'none')}"
            for track in normalize_tracks(contract)
        )
    )
    pending = [m["experiment"] for m in manifests if m.get("transaction", {}).get("status") != "complete"]
    lines.append(f"pending transactions: {', '.join(pending) if pending else 'none'}")
    return "\n".join(lines) + "\n"

