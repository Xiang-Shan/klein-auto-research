"""Machine-enforced Klein v0.2 study workflow — the coordinator and its facade.

The v1 project deliberately kept its research loop human-readable.  Version 2 keeps
that property, but moves the invariants which must never depend on prose into this
package: gate acknowledgements, data/split fingerprints, sealed-test access, bounded
subprocess execution, immutable per-run manifests, and a derived results view.

This is intentionally a single-machine coordinator.  It takes an advisory lock for
every state mutation and refuses concurrent or nested runs.

The pieces live in focused modules, each importing only the ones above it:

    errors -> primitives -> contract -> events -> manifest -> decision
           -> transaction -> state -> checks -> workflow

What stays HERE is the coordination those modules cannot own: ``run_subprocess``
(one bounded child), ``run_one`` (one candidate transaction), ``recover``,
``finalize`` and ``status_summary``, plus the two thin wrappers
``_complete_evidence_transaction`` / ``_commit_state_writes`` whose call-time
``_git_commit`` lookup is the seam the interrupted-transaction tests inject at.

``kleinlib.workflow`` also remains the stable import surface for the rest of the
repository: every name in ``__all__`` below (and every private helper that used to
live here) is re-exported explicitly, as the SAME object its home module defines.
``kleinlib/tests/test_module_split.py`` freezes that contract.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import transaction
from .checks import (
    Check,
    _artifact_hash_problems,
    _headroom_check,  # noqa: F401  (re-exported as workflow._headroom_check)
    _legacy_results_problems,  # noqa: F401  (re-exported)
    _study_python_sources,  # noqa: F401  (re-exported)
    _v2_ledger_problems,  # noqa: F401  (re-exported)
    preflight_checks,
    verify_study,
)
from .contract import (
    GATE_ARTIFACTS,
    IDENTIFIER_RE,
    PLACEHOLDER_RE,
    SCHEMA_VERSION,
    STUDY_ID_RE,
    VALID_DISPOSITIONS,
    VALID_GOALS,
    _guardrail_contract_problems,  # noqa: F401  (re-export)
    _guardrail_entries,  # noqa: F401  (re-export)
    _noise_floor_problems,  # noqa: F401  (re-export)
    _phase_ids,
    _phase_spec,
    _placeholder_locations,  # noqa: F401  (re-export)
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
    _guardrails_pass,  # noqa: F401  (re-export)
    _headroom_ack,  # noqa: F401  (re-export)
    _headroom_context,  # noqa: F401  (re-export)
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
    _artifact_path,  # noqa: F401  (re-export)
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
from .state import (
    _method_card_triad,  # noqa: F401  (re-exported as workflow._method_card_triad)
    _sealed_access_zero,  # noqa: F401  (re-exported as workflow._sealed_access_zero)
    acknowledge_headroom,
    initial_state,
    load_state,
    reconcile_state,
    record_gate,
    save_state,
    state_path,
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
class ProcessResult:
    command: tuple[str, ...]
    exit_code: int
    timed_out: bool
    started_at: str
    ended_at: str
    wall_seconds: float


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

