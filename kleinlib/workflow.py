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

from . import replicate, stop, transaction
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
    entrypoint_spec,
    load_contract,
    mutable_surface,
    normalize_tracks,
    prepared_data_path,
    registered_predictions,
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
    parse_printed_lines,  # noqa: F401  (re-export)
    parse_printed_strings,
    printed_values,
    registered_guardrails,
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
from .predictions import (
    counts as prediction_counts,
)
from .predictions import (
    findings_problems as _findings_prediction_problems,
)
from .predictions import (
    ledger as prediction_ledger,
)
from .predictions import (
    open_predictions,
    record_run_adjudications,
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
    registered_partition_fingerprints,
    save_state,
    split_policy_hash,
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
    "ARTIFACT_MISSING",
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
    "SEALED_DRYRUN_UNACKNOWLEDGED",
    "SPLIT_FINGERPRINT_MISMATCH",
    "STRONG_CLAIM_RE",
    "STUDY_ID_RE",
    "StudyLock",
    "UNCERTAINTY_EVIDENCE_RE",
    "UNSAFE_PAYLOAD_SUFFIXES",
    "V2_RESULTS_COLUMNS",
    "VALID_DISPOSITIONS",
    "VALID_GOALS",
    "VERIFIER_DISAGREEMENT",
    "VERIFIER_FAILED",
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
    "parse_printed_lines",
    "parse_printed_strings",
    "preflight_checks",
    "printed_values",
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
    "sealed_dry_run",
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


#: The crash reason a run gets when it measured the wrong rows.
SPLIT_FINGERPRINT_MISMATCH = "split_fingerprint_mismatch"

#: The verifier could not produce a number: no artifact, a crash, an unparsable
#: block.  The search may have found something; nothing checked it.
VERIFIER_FAILED = "verifier_failed"

#: The searcher and the checker disagree by more than the declared tolerance.
#: One of them is wrong and the run says which numbers were compared.
VERIFIER_DISAGREEMENT = "verifier_disagreement"

#: A cell printed ``artifact: <path>`` for a path that does not exist, or that
#: escapes the study.  A cell that cannot produce its table has not measured
#: anything, so this is a crash and never a ``measured`` row.
ARTIFACT_MISSING = "artifact_missing"


def _declared_artifacts(study_dir: Path, log_path: Path) -> dict[str, dict[str, Any]]:
    """Hash every ``artifact:`` line the run printed, as ``role: declared``.

    Registered mode's way of making a TABLE first-class evidence
    (``references/registered-mode.md``): the cell prints the study-relative
    POSIX path of each artifact it produced, the notary hashes the bytes into
    the manifest, and a claim can then cite them.  One cell whose artifact is a
    42-row table is lawful and often better than 42 cells.

    Missing, or escaping the study directory, is a :data:`ARTIFACT_MISSING`
    crash: the alternative — a ``measured`` row whose evidence is not there —
    is exactly the receipt the engine exists to refuse.
    """
    evidence: dict[str, dict[str, Any]] = {}
    for raw in parse_printed_strings(log_path).get("artifact", ()):
        rel = raw.strip()
        if not rel:
            continue
        try:
            path = _artifact_path(study_dir, rel)
        except WorkflowError as exc:
            raise WorkflowError(f"{ARTIFACT_MISSING}: {exc}") from exc
        if not path.is_file():
            raise WorkflowError(
                f"{ARTIFACT_MISSING}: the run declared `artifact: {rel}` but no such "
                "file exists when the child exited — a cell that cannot produce its "
                "table has not measured anything"
            )
        size = path.stat().st_size
        committed = (
            path.suffix.lower() not in UNSAFE_PAYLOAD_SUFFIXES and size <= 10 * 1024 * 1024
        )
        evidence[Path(rel).as_posix()] = {
            "sha256": sha256_file(path),
            "bytes": size,
            "committed": committed,
            "role": "declared",
        }
    return evidence


def _run_declared_verifier(
    study_dir: Path,
    verifier: Mapping[str, Any],
    *,
    run_dir: Path,
    timeout: float,
    run_id: str,
    track: str,
    reported: float,
    reported_metrics: Mapping[str, float],
    manifest: dict[str, Any],
    echo: bool,
) -> tuple[float, dict[str, float]]:
    """Re-score the run's artifact with the declared checker, and decide on IT.

    The searcher reporting its own score is the oldest way to be wrong without
    lying: a construction that scores itself, a training loop that grades its own
    checkpoint, a simulator scoring its own design.  So when a track declares a
    verifier, a SECOND bounded foreground subprocess re-derives the objective
    from the artifact the run produced, under the same rules as the first
    (unbuffered, ``max_run_seconds``, real exit code), with the smoke and
    dry-run flags cleared and ``KLEIN_ARTIFACT`` pointing at the artifact.  Its
    ``primary_metric`` is the one the disposition uses; the reported value is
    kept beside it so the disagreement is on the record either way.

    Returns ``(verified_metric, verified_metrics)``; raises
    :class:`WorkflowError` with a named reason on any failure.
    """
    key = str(verifier.get("artifact_key"))
    log_path = run_dir / "verify.log"
    declared = printed_values(run_dir / "run.log", key)
    if not declared:
        raise WorkflowError(
            f"{VERIFIER_FAILED}: the run printed no `{key}:` line, so there is no "
            "artifact to check — the entrypoint must print the artifact path the "
            "track's verifier.artifact_key names"
        )
    artifact = _artifact_path(study_dir, declared[-1])
    if not artifact.exists():
        raise WorkflowError(
            f"{VERIFIER_FAILED}: the declared artifact does not exist: {declared[-1]}"
        )
    command = tuple(str(item) for item in verifier["command"])
    process = run_subprocess(
        command,
        cwd=study_dir,
        log_path=log_path,
        timeout_seconds=timeout,
        echo=echo,
        env_overrides={
            "KLEIN_ARTIFACT": str(artifact),
            "KLEIN_EXPERIMENT_ID": run_id,
            "KLEIN_TRACK": track,
            # The checker never runs in smoke or rehearsal mode: it is the
            # thing being trusted.
            "KLEIN_SMOKE": "",
            "KLEIN_SEALED_DRYRUN": "",
        },
    )
    scripts = [
        item
        for item in command
        if not item.startswith("-") and (study_dir / item).is_file()
    ]
    manifest["verifier"] = {
        "command": list(command),
        "artifact": declared[-1],
        "sha256": {name: sha256_file(study_dir / name) for name in scripts},
        "wall_seconds": process.wall_seconds,
        "exit_code": process.exit_code,
        "timed_out": process.timed_out,
    }
    if process.exit_code != 0:
        raise WorkflowError(
            f"{VERIFIER_FAILED}: the verifier exited {process.exit_code}"
            + (" (timeout)" if process.timed_out else "")
        )
    try:
        verified, _, _, verified_metrics = parse_metric_log(log_path)
    except WorkflowError as exc:
        raise WorkflowError(f"{VERIFIER_FAILED}: {exc}") from exc

    tolerance = float(verifier.get("tolerance", 0.0))
    manifest["metric"] = {"reported": reported, "verified": verified}
    if abs(verified - reported) > tolerance:
        raise WorkflowError(
            f"{VERIFIER_DISAGREEMENT}: the run reported {reported:.12g} but the "
            f"verifier measured {verified:.12g} (tolerance {tolerance:.12g}) — one of "
            "them is wrong, and the search is not the one to ask"
        )
    # A guardrail the checker printed wins over the searcher's own value.
    merged = {**reported_metrics, **verified_metrics}
    return verified, merged


def _seed_external_incumbent(
    track_spec: Mapping[str, Any], incumbent: Mapping[str, Any] | None
) -> Mapping[str, Any] | None:
    """Start the frontier at the best KNOWN value, not at the first run.

    With ``metric.incumbent_external`` declared, a ``keep`` means "beat the
    literature" rather than "beat yourself".  A first result that merely matches
    the published value is a ``discard`` with the match disclosed — and a search
    that fails is a search limit, never evidence of impossibility.
    """
    if incumbent is not None:
        return incumbent
    external = track_spec.get("metric", {}).get("incumbent_external")
    if not isinstance(external, Mapping):
        return None
    try:
        value = float(external["value"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "experiment": None,
        "primary_metric": value,
        "external": True,
        "source": external.get("source"),
        "verified_on": external.get("verified_on"),
    }


def _assert_registered_partition(
    log_path: Path,
    state: Mapping[str, Any],
    *,
    evaluation_kind: str,
    manifest: dict[str, Any],
    echo: bool,
) -> None:
    """Refuse a number measured on a partition the DATA gate never froze.

    War story 8: an evaluator kept a retired split seed and a whole ledger lane
    silently measured the wrong rows.  A printed fingerprint that disagrees with
    the registered one is therefore a **crash**, not a discard — a number on the
    wrong partition is not evidence of anything, in either direction.

    Absent on either side (an entrypoint that does not call the helper, a gate
    recorded before the prepared data could be read) the run PROCEEDS with a
    printed notice: silence is not a pass, but neither is it a lie.
    """
    registered = registered_partition_fingerprints(state)
    printed = printed_values(log_path, "split_fingerprint")
    expected = registered.get(evaluation_kind)
    if printed:
        manifest.setdefault("fingerprints", {})["split_partition"] = printed[-1]
    if not printed or expected is None:
        if echo:
            missing = "the run printed no split_fingerprint" if not printed else (
                f"no {evaluation_kind} fingerprint is registered"
            )
            print(f"note: partition not verified — {missing}")
        return
    if printed[-1] != expected:
        raise WorkflowError(
            f"{SPLIT_FINGERPRINT_MISMATCH}: the run measured partition "
            f"{printed[-1][:12]}… but the DATA gate registered {expected[:12]}… for "
            f"{evaluation_kind} — a number computed on the wrong rows is not evidence"
        )


def _complete_evidence_transaction(
    repo: Path,
    study_dir: Path,
    manifest: dict[str, Any],
    *,
    restored_train: bool,
    recovery: bool = False,
    surface: Sequence[str] = ("train.py",),
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
        surface=surface,
    )


def _commit_state_writes(
    study_dir: Path, message: str, *, paths: Sequence[str] = ()
) -> str | None:
    """Thin wrapper over :func:`kleinlib.transaction.commit_state_writes`, with
    the same call-time ``_git_commit`` lookup as above."""
    return transaction.commit_state_writes(
        study_dir, message, commit=_git_commit, paths=paths
    )


#: What a sealed dry-run exits with when the child never acknowledged it.
SEALED_DRYRUN_UNACKNOWLEDGED = 3


def _validate_requested_predictions(
    contract: Mapping[str, Any], tests: str | Sequence[str] | None, track: str
) -> list[str]:
    """The ``--tests`` ids, checked against the register before anything is spent.

    An id must exist, belong to this track, and carry an arithmetic rule: a
    prediction the machine cannot decide is adjudicated by
    ``klein predict adjudicate``, on the record, with its evidence pinned —
    never as a side effect of a run.
    """
    if tests is None:
        return []
    ids = [part.strip() for part in (tests.split(",") if isinstance(tests, str) else tests)]
    ids = [part for part in ids if part]
    if not ids:
        return []
    if schema_version(contract) < 3:
        raise WorkflowError(
            "--tests adjudicates registered predictions, which are a schema-3 "
            "contract key; this study is schema 2"
        )
    registered = registered_predictions(contract)
    for name in ids:
        entry = registered.get(name)
        if entry is None:
            raise WorkflowError(
                f"unknown prediction {name!r}; study.yaml registers {sorted(registered) or 'none'}"
            )
        if entry.get("rule") is None:
            raise WorkflowError(
                f"prediction {name!r} has no rule (manual): adjudicate it with "
                "`klein predict adjudicate` and pin its evidence"
            )
        declared_track = entry.get("track")
        if declared_track is not None and str(declared_track) != track:
            raise WorkflowError(
                f"prediction {name!r} belongs to track {declared_track!r}, not {track!r}"
            )
    seen: list[str] = []
    for name in ids:
        if name not in seen:
            seen.append(name)
    return seen


def sealed_dry_run(
    study_dir: Path,
    *,
    track: str | None = None,
    timeout_seconds: float | None = None,
    command: Sequence[str] | None = None,
    echo: bool = True,
) -> int:
    """Rehearse a sealed run without spending anything.  Returns an exit code.

    A study's only sealed access was once spent by a crash before any data was
    read (war story 9).  This is the fix and it is mandatory before every real
    sealed run: the child runs with ``KLEIN_SEALED_DRYRUN=1``, which makes
    :func:`kleinlib.data.load_partition` hand back the DEVELOPMENT partition and
    print ``sealed_dryrun: 1``.  No experiment id is allocated, no commit made,
    no manifest or results row written, and the seal is untouched — the only
    traces are a log under ``sweeps/`` and a ``sealed_dryrun`` event.

    Exit 0 when the child exited 0 AND printed the acknowledgement;
    :data:`SEALED_DRYRUN_UNACKNOWLEDGED` when it exited 0 without it — an
    entrypoint that ignores the flag would have read the sealed rows, so a
    silent success is exactly the outcome that must not be reported as a pass.
    """
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
        configured_timeout = float(contract["max_run_seconds"])
        timeout = configured_timeout if timeout_seconds is None else float(timeout_seconds)
        if timeout <= 0 or timeout > configured_timeout:
            raise WorkflowError(
                f"timeout must be > 0 and <= configured max_run_seconds={configured_timeout:g}"
            )
        stamp = utc_now().replace(":", "").replace("-", "")
        log_path = study_dir / "sweeps" / f"sealed_dryrun.{stamp}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = tuple(
            command
            or (
                tuple(entrypoint_spec(contract)["command"])
                if schema_version(contract) >= 3
                else ("uv", "run", "--locked", "python", "-u", "train.py")
            )
        )
        process = run_subprocess(
            cmd,
            cwd=study_dir,
            log_path=log_path,
            timeout_seconds=timeout,
            echo=echo,
            env_overrides={
                "KLEIN_EVALUATION_KIND": "final_test",
                "KLEIN_EXPERIMENT_ID": "DRYRUN",
                "KLEIN_TRACK": track,
                "KLEIN_SEALED_DRYRUN": "1",
                "KLEIN_SMOKE": "",
            },
        )
        acknowledged = "1" in printed_values(log_path, "sealed_dryrun")
        if process.exit_code != 0:
            exit_code = process.exit_code
        elif not acknowledged:
            exit_code = SEALED_DRYRUN_UNACKNOWLEDGED
        else:
            exit_code = 0
        append_event(
            study_dir,
            "sealed_dryrun",
            track=track,
            command=list(cmd),
            log=str(log_path.relative_to(study_dir).as_posix()),
            exit_code=process.exit_code,
            timed_out=process.timed_out,
            acknowledged=acknowledged,
            wall_seconds=process.wall_seconds,
        )
        _commit_state_writes(study_dir, f"klein: sealed dry-run rehearsal ({track})")
    if echo:
        if exit_code == 0:
            print(f"sealed dry-run OK: {track} rehearsed on development data; nothing spent")
        elif exit_code == SEALED_DRYRUN_UNACKNOWLEDGED:
            print(
                "sealed dry-run FAILED: the entrypoint exited 0 but never printed "
                "`sealed_dryrun: 1` — it ignored KLEIN_SEALED_DRYRUN and would have read "
                "the sealed partition. Route the partition through "
                "kleinlib.data.load_partition before spending the seal."
            )
        else:
            print(f"sealed dry-run FAILED: the entrypoint exited {exit_code}; the seal is intact")
    return exit_code


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
    tests: str | Sequence[str] | None = None,
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
    # Validated BEFORE the lock, so a typo in --tests costs nothing.
    requested_predictions = _validate_requested_predictions(contract, tests, track)
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
        if split_fingerprint(contract) != split_policy_hash(state):
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
        _assert_run_worktree(repo, study_dir, surface=mutable_surface(contract))

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
        # `references/registered-mode.md`: a registered track runs CELLS of a
        # pre-registered measurement program.  It holds no incumbent, so the
        # headroom law (and the stop rule, which asks the same question) has
        # nothing to measure a closed door against.
        registered = str(tracks[track].get("mode", "frontier")) == "registered"
        incumbent = (
            None
            if registered
            else _seed_external_incumbent(tracks[track], _incumbent(manifests, track))
        )
        if not final_test and not registered:
            _enforce_headroom(state, tracks[track], track, incumbent, echo=echo)
            stop.refuse_if_tripped(
                contract, state, manifests, track=track, phase=phase_id, echo=echo
            )
        number = len(manifests) + 1
        run_id = f"E{number:04d}"

        surface = mutable_surface(contract)
        surface_rels = [_relative(repo, study_dir / name) for name in surface]
        surface_names = ", ".join(surface)
        # Schema 2 always ran train.py; schema 3 names its entrypoint by kind
        # (a Hubble regression is not "trained"), so the default command comes
        # from the contract.  ``--command`` still overrides either.
        default_command: tuple[str, ...] = (
            tuple(entrypoint_spec(contract)["command"])
            if schema_version(contract) >= 3
            else ("uv", "run", "--locked", "python", "-u", "train.py")
        )
        # On a REGISTERED track a replication IS evidence: an identical cell
        # re-run to decide a named prediction is exactly the kind of repeat
        # science wants, so `--tests P#` earns the same exemption `--allow-rerun`
        # gives a frontier candidate.
        replication_adjudicates = registered and bool(requested_predictions)
        if (
            not final_test
            and command is None
            and not allow_rerun
            and not replication_adjudicates
            and not _git(repo, ["status", "--porcelain", "--", *surface_rels]).stdout.strip()
        ):
            # Before any E#### is allocated, run dir created, or commit made —
            # a refusal here burns nothing. The sealed final test re-runs the
            # incumbent with an empty diff BY DESIGN and stays exempt, as do
            # declared --command overrides.
            raise WorkflowError(
                f"{surface_names} is unchanged since HEAD — this run would re-execute the "
                f"incumbent configuration and burn a phase slot; edit {surface_names} with "
                "ONE falsifiable change, or pass --allow-rerun for an intentional "
                "identical replication"
                + (
                    " (on a registered track, --tests P# also allows it — a repeat that "
                    "adjudicates a prediction is evidence)"
                    if registered
                    else ""
                )
            )
        base_commit = _git(repo, ["rev-parse", "HEAD"]).stdout.strip()
        _git(repo, ["add", "--", *surface_rels])
        candidate_commit = _git_commit(repo, f"candidate {run_id}: {description or track}", allow_empty=True)
        patch = _git(repo, ["diff", "--binary", base_commit, candidate_commit, "--", *surface_rels]).stdout.encode()
        patch_hash = sha256_bytes(patch)
        empty_diff = patch == b""
        env_hash, env_details = environment_fingerprint(repo)
        run_dir = study_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        log_path = run_dir / "run.log"
        manifest: dict[str, Any] = {
            # The manifest is a receipt of the rule set the run was judged
            # under, so it carries the CONTRACT's version, not a constant.
            "schema_version": schema_version(contract),
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
            "command": list(command or default_command),
            "max_run_seconds": timeout,
            "phase_budget_seconds": phase_budget,
            "phase_experiment_limit": int(phase["max_experiments"]),
            "exit_code": None,
            "timed_out": False,
            "primary_metric": None,
            "metric_name": tracks[track]["metric"]["name"],
            "metric_goal": tracks[track]["metric"]["goal"],
            "metrics": {},
            # Which registered predictions this run was asked to decide.  The
            # verdicts land beside it once the predictions ledger is wired in.
            "predictions_requested": list(requested_predictions),
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

        cmd = tuple(command or default_command)
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
        declared_artifacts: dict[str, dict[str, Any]] = {}
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
                _assert_registered_partition(
                    log_path,
                    state,
                    evaluation_kind=manifest["evaluation_kind"],
                    manifest=manifest,
                    echo=echo,
                )
                if schema_version(contract) >= 3:
                    # Schema-3 only: a schema-2 study never printed `artifact:`
                    # lines, so its manifests keep exactly the artifacts the
                    # before/after inventory diff always recorded.
                    declared_artifacts = _declared_artifacts(study_dir, log_path)
                verifier = tracks[track].get("verifier")
                if isinstance(verifier, Mapping):
                    # The checker is never the searcher: the disposition is
                    # decided on the number a SECOND, immutable process derived
                    # from the artifact this run produced.
                    primary, metrics = _run_declared_verifier(
                        study_dir,
                        verifier,
                        run_dir=run_dir,
                        timeout=timeout,
                        run_id=run_id,
                        track=track,
                        reported=primary,
                        reported_metrics=metrics,
                        manifest=manifest,
                        echo=echo,
                    )
                disposition, reason = choose_disposition(
                    primary_metric=primary,
                    track_spec=tracks[track],
                    metrics=metrics,
                    incumbent=incumbent,
                    final_test=final_test,
                    mode="registered" if registered else "frontier",
                )
                if registered:
                    # A guardrail on a registered cell is DISCLOSED, never
                    # disposition-flipping: the measurement happened either way
                    # and findings must be able to weigh it.
                    guardrails_ok, guardrail_failures = registered_guardrails(
                        tracks[track], metrics
                    )
                    manifest["guardrails_ok"] = guardrails_ok
                    if guardrail_failures:
                        manifest["guardrail_failures"] = guardrail_failures
                if incumbent is not None and incumbent.get("external"):
                    # Found / matched / improved — never "proved". A search that
                    # reaches the published value and stops there says so. The
                    # resolution at which "reached" is decided is the checker's
                    # tolerance where a checker exists, and otherwise the track's
                    # own measured resolution — never a bare float equality.
                    external = float(incumbent["primary_metric"])
                    tolerance = (
                        float(verifier.get("tolerance", 0.0))
                        if isinstance(verifier, Mapping)
                        else float(tracks[track]["metric"].get("minimum_delta", 0.0) or 0.0)
                    )
                    manifest["matched_external"] = abs(primary - external) <= tolerance
                    reason = f"{reason} (external incumbent {external:.12g})"
                manifest.update(
                    primary_metric=primary,
                    metrics=metrics,
                    disposition=disposition,
                    decision_reason=reason,
                )
                # --- predictions ledger hook (WP-E6) -------------------------
                # The ids were validated against the register before the lock;
                # the printed block is in `metrics`.  Adjudication happens HERE,
                # inside the transaction: the verdicts land on the manifest, in
                # `state["predictions"]` (saved with this run's state write and
                # committed with its evidence), and as one
                # `prediction_adjudicated` event each.  A prediction is never
                # decided by prose, and never outside a receipt.
                if requested_predictions:
                    manifest["predictions"] = record_run_adjudications(
                        study_dir,
                        state,
                        requested_predictions,
                        contract=contract,
                        printed=metrics,
                        experiment=run_id,
                    )
                # -------------------------------------------------------------
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
        for rel, meta in declared_artifacts.items():
            # A cell may pin a table the inventory never watches (`sweeps/`,
            # `tables/`) or one it already saw (`figures/`); either way the
            # DECLARED role is what makes it citable evidence.
            manifest["artifacts"].setdefault(rel, {}).update(meta)
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
            _git(repo, ["restore", "--source", base_commit, "--", *surface_rels])
        _complete_evidence_transaction(
            repo, study_dir, manifest, restored_train=restored, surface=surface
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
            surface_rels = [
                _relative(repo, study_dir / name) for name in mutable_surface(contract)
            ]
            restored = manifest.get("disposition") != "keep" or manifest.get("evaluation_kind") == "final_test"
            if restored:
                _git(repo, ["restore", "--source", str(manifest["base_commit"]), "--", *surface_rels])
            save_state(study_dir, state)
            _complete_evidence_transaction(
                repo,
                study_dir,
                manifest,
                restored_train=restored,
                recovery=True,
                surface=mutable_surface(contract),
            )
            recovered.append(run_id)
    _commit_state_writes(study_dir, "klein: recover — state writes filed")
    return recovered


def finalize(
    study_dir: Path,
    *,
    allow_exploratory: bool = False,
    allow_open_predictions: bool = False,
    open_predictions_reason: str = "",
) -> str:
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
        # `confirmation.require` naming `replicate`/`verify` is paid for with a
        # `reproduced: true` record, not with intent: a track missing one is
        # exploratory, and the receipt below names the record it lacks. Empty for
        # every schema-2 study (no track declares confirmation), so this path is
        # unchanged there.
        confirmation_gaps = replicate.confirmation_gaps(study_dir, contract, manifests)
        label = (
            "confirmed"
            if counts
            and all(count == 1 for count in counts.values())
            and all(successful_confirmation.values())
            and not confirmation_gaps
            else "exploratory"
        )
        if label == "exploratory" and not allow_exploratory:
            reason = "not every track has one successful sealed final-test evaluation"
            if confirmation_gaps:
                reason += "; missing confirmation records — " + "; ".join(
                    f"{track}: {'; '.join(missing)}"
                    for track, missing in confirmation_gaps.items()
                )
            raise WorkflowError(
                f"{reason}; use --allow-exploratory to finalize explicitly"
            )
        findings = study_dir / "findings.md"
        if not findings.is_file():
            raise WorkflowError("findings.md is required before finalize")
        text = findings.read_text(encoding="utf-8")
        if not re.search(rf"(?i)\b{label}\b", text):
            raise WorkflowError(f"findings.md must explicitly label the study `{label}`")
        # --- the predictions ledger closes with the study (schema 3) --------
        # A belief written down before the evidence is only worth writing down
        # if the study says, at the end, what became of it.  Two refusals: an
        # OPEN prediction (decided nowhere) and an UNREPORTED one (decided in
        # the ledger, absent from findings §②).
        closure: dict[str, Any] = {}
        if schema_version(contract) >= 3:
            still_open = open_predictions(contract, state)
            if still_open and not allow_open_predictions:
                raise WorkflowError(
                    "cannot finalize with open predictions: "
                    + ", ".join(still_open)
                    + " — adjudicate each (`klein run-one --tests P#`, or "
                    "`klein predict adjudicate P# --verdict … --evidence …`), or "
                    "record why they stay open with --allow-open-predictions "
                    '--reason "<why>"'
                )
            if still_open:
                if not open_predictions_reason.strip():
                    raise WorkflowError(
                        "--allow-open-predictions requires --reason: an unadjudicated "
                        "belief is a finding, and the receipt must say which one"
                    )
                closure["open_predictions"] = {
                    "ids": still_open,
                    "reason": open_predictions_reason,
                }
            problems = _findings_prediction_problems(study_dir, contract, text)
            if problems:
                raise WorkflowError("; ".join(problems))
        # --------------------------------------------------------------------
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
            # keyed only when non-empty: a schema-2 receipt keeps its exact shape
            **({"confirmation_gaps": confirmation_gaps} if confirmation_gaps else {}),
            **closure,
        }
        save_state(study_dir, state)
        append_event(
            study_dir,
            "study_finalized",
            label=label,
            final_holdout_counts=counts,
            successful_confirmation=successful_confirmation,
            **({"confirmation_gaps": confirmation_gaps} if confirmation_gaps else {}),
            **closure,
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
    # A registered track has no keep chain, so `measured` is reported beside
    # keep/discard rather than folded into either.  Shown for every schema-3
    # study and for any ledger that actually holds one; a schema-2 status line
    # is unchanged.
    measured = (
        f" measured={counts['measured']}" if version >= 3 or counts["measured"] else ""
    )
    lines = [
        f"study: {state['study_id']}",
        f"schema: v{version}",
        f"status: {state.get('status')}",
        f"current phase: {state.get('current_phase')}",
        f"experiments: {len(manifests)} (keep={counts['keep']} discard={counts['discard']}"
        f"{measured} crash={counts['crash']})",
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
    if version >= 3:
        # The four numbers the referee's rubric and findings §② are checked
        # against.  `open` is the absence of a record, not a stored verdict.
        tally = prediction_counts(prediction_ledger(contract, state))
        lines.append(
            f"predictions: {tally['supported']} supported, {tally['refuted']} refuted, "
            f"{tally['inconclusive']} inconclusive, {tally['open']} open"
        )
    pending = [m["experiment"] for m in manifests if m.get("transaction", {}).get("status") != "complete"]
    lines.append(f"pending transactions: {', '.join(pending) if pending else 'none'}")
    return "\n".join(lines) + "\n"

