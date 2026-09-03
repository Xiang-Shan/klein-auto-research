"""Internal replication — convergent evidence for a run this study already made.

The normative text is ``.claude/skills/klein/references/replication-protocol.md``.
Two things are called replication and Klein keeps them apart: **internal**
replication (this module) re-executes one of the study's own DEVELOPMENT runs to
show the number was not an accident of one process; **external** replication is a
study *kind* whose question is whether a published result reproduces.  Neither is
a second look at sealed data.

What one ``klein replicate E####`` does:

1. refuses the two runs that must never be replicated — a sealed (``final_test``)
   run, because a replication would be a second look, and a ``crash``, because
   there is nothing to reproduce;
2. checks the run's ``candidate_commit`` out into a detached git worktree in the
   SYSTEM temp directory (:func:`kleinlib.transaction.detached_worktree`), always
   removed and pruned afterwards;
3. copies the prepared data in and ASSERTS its fingerprint against the one the
   original manifest recorded — you cannot replicate a run whose input is gone;
4. re-runs the manifest's own command, in that worktree, with
   ``KLEIN_REPLICATION=1`` and every smoke / sealed-dry-run flag cleared, under
   the same bounded foreground subprocess the loop uses;
5. compares the printed block with the manifest's within a tolerance chosen from
   the ladder in :func:`tolerance_ladder`;
6. writes ``runs/E####/replications/<ts>.json`` plus its log, appends the
   ``run_replicated`` event, refreshes the ``state.replications`` rollup, and
   files them in one state commit.

**The manifest is never touched.**  A replication is new evidence beside the run,
never a revision of it, and ``reproduced: false`` is evidence too: the record is
written and kept either way (the protocol's "never re-run until it passes and
keep only the pass").

``--verify-only`` is the verifier-track shape: no worktree and no search re-run,
just the track's declared verifier re-executed on the pinned artifact in a fresh
process, recorded with ``mode: verify``.  Evidence ids are ``rep:E####@<ts>`` and
``verify:E####@<ts>``.

Import position: this module sits ABOVE ``workflow`` in the dependency order
(``workflow`` imports it for the one ``finalize`` call), so it talks to
``runner.run_logged`` directly rather than to ``workflow.run_subprocess``.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .contract import (
    CONFIRMATION_DEFAULTS,
    confirmation_require,
    load_contract,
    normalize_tracks,
    prepared_data_path,
    track_kind,
    validate_contract,
)
from .decision import _incumbent, parse_metric_log, printed_values
from .errors import WorkflowError
from .events import append_event
from .manifest import RUN_ID_RE, _artifact_path, load_manifests
from .primitives import (
    StudyLock,
    atomic_write_json,
    fingerprint_path,
    sha256_file,
    utc_now,
)
from .runner import run_logged
from .state import load_state, save_state
from .transaction import (
    commit_state_writes,
    detached_worktree,
    environment_fingerprint,
    relative,
    repo_root_for,
)

__all__ = [
    "MODES",
    "confirmation_gaps",
    "evidence_id",
    "list_replications",
    "load_replications",
    "replicate_run",
    "required_confirmation",
    "tolerance_ladder",
]

#: The two record modes and the evidence-id prefix each one stamps.
MODES: dict[str, str] = {"replicate": "rep", "verify": "verify"}

#: Printed keys that measure the MACHINE rather than the result.  A replication
#: run on another day never reproduces a wall time; listing those as mismatches
#: would drown the signal, so they are reported in ``block_differences`` but kept
#: out of ``mismatched_keys``.
_MACHINE_KEY_SUFFIXES = ("_seconds", "_ms", "_bytes")
_MACHINE_KEY_PREFIXES = ("runner_",)


def _is_machine_key(key: str) -> bool:
    return key.startswith(_MACHINE_KEY_PREFIXES) or key.endswith(_MACHINE_KEY_SUFFIXES)


def evidence_id(run_id: str, stamp: str, mode: str) -> str:
    """``rep:E0003@<ts>`` / ``verify:E0003@<ts>`` — the id findings cite."""
    try:
        prefix = MODES[mode]
    except KeyError:  # pragma: no cover - guarded by the callers
        raise WorkflowError(f"unknown replication mode {mode!r}") from None
    return f"{prefix}:{run_id}@{stamp}"


def _finite(value: Any, what: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise WorkflowError(f"{what} must be a number, got {value!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise WorkflowError(f"{what} must be finite and >= 0, got {value!r}")
    return number


def tolerance_ladder(
    track_spec: Mapping[str, Any],
    *,
    override: float | None = None,
    mode: str = "replicate",
) -> tuple[float, str]:
    """The protocol's tolerance ladder, top rung first.

    ``--tolerance`` > (``verifier.tolerance``, in ``verify`` mode) >
    ``metric.exactness: exact`` > the track's ``minimum_delta`` > the measured
    floor's ``std`` > exact.

    One deliberate reading: an ``exactness: exact`` track sits on the EXACT rung
    even when it also declares a ``minimum_delta``.  The protocol lists exactness
    with the last rung, and both readings agree everywhere except that one
    combination — where a `minimum_delta` (a keep threshold) would silently
    admit nondeterminism the contract says cannot exist.  An explicit
    ``--tolerance`` still overrides, so the operator keeps the last word.
    """
    if override is not None:
        return _finite(override, "--tolerance"), "--tolerance"
    metric = track_spec.get("metric")
    metric = metric if isinstance(metric, Mapping) else {}
    if mode == "verify":
        verifier = track_spec.get("verifier")
        if isinstance(verifier, Mapping) and verifier.get("tolerance") is not None:
            return (
                _finite(verifier["tolerance"], "verifier.tolerance"),
                "verifier.tolerance",
            )
    if str(metric.get("exactness", "")).strip() == "exact":
        return 0.0, "exact"
    delta = metric.get("minimum_delta")
    if delta is not None:
        value = _finite(delta, "metric.minimum_delta")
        if value > 0:
            return value, "minimum_delta"
    floor = metric.get("noise_floor")
    if isinstance(floor, Mapping) and floor.get("std") is not None:
        value = _finite(floor["std"], "metric.noise_floor.std")
        if value > 0:
            return value, "floor_std"
    return 0.0, "exact"


def _declared_require(source: Any) -> set[str] | None:
    """``confirmation: {require: [...]}`` as a set, or None when not declared."""
    block = source.get("confirmation") if isinstance(source, Mapping) else None
    if not isinstance(block, Mapping):
        return None
    require = block.get("require")
    if isinstance(require, str):
        return {require}
    if isinstance(require, Sequence) and not isinstance(require, (str, bytes)):
        return {str(item) for item in require}
    return None


def required_confirmation(
    track_spec: Mapping[str, Any], contract: Mapping[str, Any] | None = None
) -> set[str]:
    """What ``confirmed`` costs on ONE track, in order of authority.

    1. the track's own ``confirmation.require`` — the protocols say "its track's",
       and one study can carry two lanes with different bars (study 09 ran a
       registered test beside a known-truth simulation);
    2. the study-level block, read through :func:`contract.confirmation_require`
       so the declared shape has a single source of truth;
    3. the per-kind default from ``contract.CONFIRMATION_DEFAULTS``, keyed by the
       TRACK's kind (its override, else the study's) — ``optimize`` closes on
       ``verify``, everything else that closes at all closes on ``sealed``.

    Without a contract only an explicit track declaration counts: a bare mapping
    carries no kind to take a default from.
    """
    declared = _declared_require(track_spec)
    if declared is not None:
        return declared
    if contract is None:
        return set()
    if _declared_require(contract) is not None:
        return set(confirmation_require(contract))
    kind = track_kind(contract, track_spec)
    return set(CONFIRMATION_DEFAULTS.get(str(kind), ("sealed",)))


# ---------------------------------------------------------------------------
# records on disk
# ---------------------------------------------------------------------------


def _replications_dir(study_dir: Path, run_id: str) -> Path:
    return study_dir / "runs" / run_id / "replications"


def load_replications(study_dir: Path, run_id: str | None = None) -> list[dict[str, Any]]:
    """Every replication record under ``runs/E####/replications/``, oldest first.

    The receipts on disk are the truth; ``state.replications`` is only their
    rollup, so every reader here goes to the files.
    """
    runs = study_dir / "runs"
    records: list[dict[str, Any]] = []
    if not runs.is_dir():
        return records
    run_dirs = (
        [runs / run_id]
        if run_id is not None
        else sorted(p for p in runs.iterdir() if p.is_dir() and RUN_ID_RE.match(p.name))
    )
    for run_dir in run_dirs:
        directory = run_dir / "replications"
        if not directory.is_dir():
            continue
        found: list[tuple[str, str, dict[str, Any]]] = []
        for path in sorted(directory.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise WorkflowError(f"invalid replication record {path}: {exc}") from exc
            if not isinstance(value, dict):
                raise WorkflowError(f"replication record must be an object: {path}")
            value.setdefault("experiment", run_dir.name)
            # The record's own microsecond timestamp orders attempts made inside
            # the same second more reliably than the (second-resolution) filename.
            found.append((str(value.get("timestamp") or ""), path.name, value))
        records.extend(value for _, _, value in sorted(found, key=lambda item: item[:2]))
    return records


def _rollup(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """``state.replications``: per run, what has been attempted and what held."""
    rollup: dict[str, Any] = {}
    for record in records:
        run_id = str(record.get("experiment"))
        entry = rollup.setdefault(
            run_id, {"track": record.get("track"), "attempts": 0, "modes": {}, "records": []}
        )
        entry["attempts"] += 1
        if record.get("track"):
            entry["track"] = record["track"]
        mode = str(record.get("mode"))
        per_mode = entry["modes"].setdefault(mode, {"attempts": 0, "reproduced": False})
        per_mode["attempts"] += 1
        per_mode["reproduced"] = bool(per_mode["reproduced"] or record.get("reproduced") is True)
        entry["records"].append(
            {
                "evidence_id": record.get("evidence_id"),
                "timestamp": record.get("timestamp"),
                "mode": mode,
                "reproduced": bool(record.get("reproduced")),
                "difference": record.get("difference"),
                "tolerance": record.get("tolerance"),
            }
        )
    return rollup


def list_replications(study_dir: Path) -> list[dict[str, Any]]:
    """The ``--list`` view: one flat row per record, newest last."""
    return [
        {
            "experiment": str(record.get("experiment")),
            "timestamp": record.get("timestamp"),
            "mode": record.get("mode"),
            "reproduced": bool(record.get("reproduced")),
            "difference": record.get("difference"),
            "tolerance": record.get("tolerance"),
            "tolerance_source": record.get("tolerance_source"),
            "evidence_id": record.get("evidence_id"),
            "note": record.get("failure_reason"),
        }
        for record in load_replications(study_dir)
    ]


def _stamp(directory: Path) -> str:
    """A filesystem-safe, lexicographically sortable, unique timestamp token.

    No colons: the token is both the record's filename and the tail of its
    evidence id, and ``rep:E0003@2026-09-02T10:11:12Z.json`` is not a filename
    Windows will accept.  A second attempt inside the same second takes an
    ``_NN`` suffix, zero-padded and after ``.`` in ASCII so the plain filename
    still sorts oldest-first.
    """
    base = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    stamp, suffix = base, 1
    while (directory / f"{stamp}.json").exists() or (directory / f"{stamp}.log").exists():
        suffix += 1
        stamp = f"{base}_{suffix:02d}"
    return stamp


# ---------------------------------------------------------------------------
# the run itself
# ---------------------------------------------------------------------------


def _select_manifest(manifests: Sequence[Mapping[str, Any]], run_id: str) -> Mapping[str, Any]:
    if not RUN_ID_RE.match(run_id):
        raise WorkflowError(f"{run_id!r} is not an experiment id (expected E0001-style)")
    for manifest in manifests:
        if str(manifest.get("experiment")) == run_id:
            return manifest
    known = ", ".join(str(m.get("experiment")) for m in manifests) or "none"
    raise WorkflowError(f"no run {run_id} in this study (recorded: {known})")


def _refuse_unreplicable(manifest: Mapping[str, Any], run_id: str) -> None:
    """The protocol's two refusals — neither has an override."""
    if manifest.get("evaluation_kind") == "final_test":
        raise WorkflowError(
            f"{run_id} is the sealed final test: replicating it would be a second look "
            "at the sealed partition, and there is no override. Replicate the "
            "development run the claim actually rests on."
        )
    if manifest.get("disposition") == "crash":
        raise WorkflowError(
            f"{run_id} crashed: there is nothing to reproduce (its primary metric is NA). "
            "Run a new candidate instead — a crash is retained as evidence, not replicated."
        )
    transaction = manifest.get("transaction")
    if not isinstance(transaction, Mapping) or transaction.get("status") != "complete":
        raise WorkflowError(
            f"{run_id} has an interrupted transaction; run `klein recover` before replicating it"
        )
    primary = manifest.get("primary_metric")
    if not isinstance(primary, (int, float)) or isinstance(primary, bool) or not math.isfinite(
        float(primary)
    ):
        raise WorkflowError(f"{run_id} recorded no finite primary metric; nothing to reproduce")


def _assert_prepared_source(
    study_dir: Path, contract: Mapping[str, Any], expected: Any
) -> Path:
    """Refuse a missing or changed input BEFORE a worktree is created.

    ``fingerprint_path`` hashes the name and the bytes, so the source and the
    copy inside the worktree share a digest — checking here costs nothing and
    makes the refusal free.  The post-copy check in :func:`_copy_prepared_data`
    stays as proof that the copy actually landed.
    """
    source = prepared_data_path(study_dir, contract)
    if not source.exists():
        raise WorkflowError(
            f"prepared data is absent ({source}); a replication re-runs on the SAME "
            "input — re-run prepare.py first"
        )
    _assert_fingerprint(fingerprint_path(source), expected)
    return source


def _assert_fingerprint(actual: str, expected: Any) -> None:
    if isinstance(expected, str) and actual != expected:
        raise WorkflowError(
            "prepared-data fingerprint differs from the one the original run recorded "
            f"(manifest {expected[:12]}…, on disk {actual[:12]}…): this would replicate a "
            "different experiment. Restore the original prepared data first."
        )


def _copy_prepared_data(
    study_dir: Path, worktree_study: Path, contract: Mapping[str, Any], expected: Any
) -> tuple[Path, str]:
    """Put the study's prepared data into the worktree and assert its fingerprint."""
    source = _assert_prepared_source(study_dir, contract, expected)
    try:
        rel = source.relative_to(study_dir.resolve())
    except ValueError:
        # An absolute prepared_path outside the study is already shared with the
        # worktree; there is nothing to copy, only a fingerprint to assert.
        destination = source
    else:
        destination = worktree_study / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        elif destination.exists() or destination.is_symlink():
            destination.unlink()
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
    actual = fingerprint_path(destination)
    _assert_fingerprint(actual, expected)
    return destination, actual


def _child_env(manifest: Mapping[str, Any], run_id: str, track: str, **extra: str) -> dict[str, str]:
    """The replication child's environment: replication on, smoke/dry-run off."""
    env = {
        "KLEIN_REPLICATION": "1",
        "KLEIN_EXPERIMENT_ID": run_id,
        "KLEIN_TRACK": track,
        "KLEIN_EVALUATION_KIND": str(manifest.get("evaluation_kind") or "development"),
        # Ambient smoke or sealed-dry-run mode in the driving shell must never
        # turn a replication into a no-op that "reproduces" by printing nothing.
        "KLEIN_SMOKE": "",
        "KLEIN_SEALED_DRYRUN": "",
    }
    env.update(extra)
    return env


def _compare(
    original: Mapping[str, Any], replicate: Mapping[str, float], tolerance: float
) -> dict[str, Any]:
    """Primary-metric verdict plus the whole block, key by key.

    ``reproduced`` is decided on the PRIMARY metric — that is what a claim rests
    on, and the block also carries wall times, which no re-run reproduces to
    six decimals.  Everything else is disclosed in ``block_differences`` and,
    for the result-bearing keys, summarized in ``mismatched_keys``.
    """
    differences: dict[str, Any] = {}
    mismatched: list[str] = []
    for key in sorted(set(original) | set(replicate)):
        before, after = original.get(key), replicate.get(key)
        if before is None or after is None:
            differences[key] = {"original": before, "replicate": after, "difference": None}
            if not _is_machine_key(key):
                mismatched.append(key)
            continue
        delta = abs(float(after) - float(before))
        differences[key] = {
            "original": float(before),
            "replicate": float(after),
            "difference": delta,
        }
        if delta > tolerance and not _is_machine_key(key):
            mismatched.append(key)
    return {"block_differences": differences, "mismatched_keys": mismatched}


def _verifier_spec(track_spec: Mapping[str, Any], track: str) -> tuple[list[str], str]:
    verifier = track_spec.get("verifier")
    if not isinstance(verifier, Mapping):
        raise WorkflowError(
            f"--verify-only needs track {track!r} to declare a `verifier:` block "
            "(command, tolerance, artifact_key); this track declares none. Replicate "
            "the run itself instead (drop --verify-only)."
        )
    command = verifier.get("command")
    if (
        not isinstance(command, Sequence)
        or isinstance(command, (str, bytes))
        or not command
        or any(not str(part).strip() for part in command)
    ):
        raise WorkflowError(f"tracks.{track}.verifier.command must be a non-empty list of strings")
    artifact_key = verifier.get("artifact_key")
    if not isinstance(artifact_key, str) or not artifact_key.strip():
        raise WorkflowError(f"tracks.{track}.verifier.artifact_key is required")
    return [str(part) for part in command], artifact_key.strip()


def _resolve_artifact(
    study_dir: Path, manifest: Mapping[str, Any], artifact_key: str, run_id: str
) -> str:
    """Which study-relative file the verifier judges, in order of authority.

    1. ``manifest.verifier.artifact`` — what ``run-one``'s own verifier checked;
    2. the last ``<artifact_key>:`` line the run PRINTED (``run-one`` resolves
       the artifact the same way, so a re-verification judges the same object);
    3. ``artifact_key`` read as a study-relative path, or as the basename of one
       entry in the manifest's artifact inventory — for a track that names the
       file directly instead of printing it.
    """
    verifier = manifest.get("verifier")
    if isinstance(verifier, Mapping) and isinstance(verifier.get("artifact"), str):
        return verifier["artifact"]
    printed = printed_values(study_dir / "runs" / run_id / "run.log", artifact_key)
    if printed:
        return printed[-1]
    artifacts = manifest.get("artifacts")
    artifacts = artifacts if isinstance(artifacts, Mapping) else {}
    if artifact_key in artifacts:
        return artifact_key
    matches = [str(key) for key in artifacts if Path(str(key)).name == artifact_key]
    if len(matches) == 1:
        return matches[0]
    return artifact_key


def _pinned_artifact(
    study_dir: Path, manifest: Mapping[str, Any], artifact_key: str, run_id: str
) -> tuple[str, Path]:
    """Resolve, locate, and hash-check the artifact the verifier judges."""
    rel = _resolve_artifact(study_dir, manifest, artifact_key, run_id)
    path = _artifact_path(study_dir, rel)
    if not path.is_file():
        raise WorkflowError(
            f"the pinned artifact {rel} recorded by {run_id} is absent from disk; a "
            "verification must judge the SAME object (the manifest records its sha256)"
        )
    artifacts = manifest.get("artifacts")
    meta = artifacts.get(rel) if isinstance(artifacts, Mapping) else None
    if isinstance(meta, Mapping) and isinstance(meta.get("sha256"), str):
        actual = sha256_file(path)
        if actual != meta["sha256"]:
            raise WorkflowError(
                f"the pinned artifact {rel} changed since {run_id} (manifest "
                f"{str(meta['sha256'])[:12]}…, on disk {actual[:12]}…); verifying it "
                "would judge a different object"
            )
    return rel, path


def _assert_same_checker(study_dir: Path, manifest: Mapping[str, Any], run_id: str) -> None:
    """The re-verification must use the SAME checker the run was judged by.

    ``run-one`` records a sha256 per verifier script it could see on disk; a
    changed script means the number would come from a different program, which
    is a new measurement, not a reproduction of the old one.
    """
    verifier = manifest.get("verifier")
    hashes = verifier.get("sha256") if isinstance(verifier, Mapping) else None
    if not isinstance(hashes, Mapping):
        return
    for name, expected in hashes.items():
        path = study_dir / str(name)
        if not path.is_file():
            raise WorkflowError(
                f"the verifier script {name} recorded by {run_id} is missing; "
                "a re-verification must run the same checker"
            )
        actual = sha256_file(path)
        if isinstance(expected, str) and actual != expected:
            raise WorkflowError(
                f"the verifier script {name} changed since {run_id} (manifest "
                f"{expected[:12]}…, on disk {actual[:12]}…); re-running it would be a "
                "new measurement, not a re-verification"
            )


def _verified_baseline(manifest: Mapping[str, Any]) -> tuple[float, str]:
    """What ``--verify-only`` compares against: the verified metric when the
    manifest carries one (schema-3 verifier tracks), else the primary metric."""
    metric = manifest.get("metric")
    if isinstance(metric, Mapping):
        for key in ("verified", "reported"):
            value = metric.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if math.isfinite(float(value)):
                    return float(value), f"manifest.metric.{key}"
    return float(manifest["primary_metric"]), "manifest.primary_metric"


def replicate_run(
    study_dir: Path,
    run_id: str,
    *,
    tolerance: float | None = None,
    verify_only: bool = False,
    timeout_seconds: float | None = None,
    echo: bool = True,
) -> dict[str, Any]:
    """Replicate one development run (or re-verify its pinned artifact).

    Returns the record it wrote.  Raises :class:`WorkflowError` for the
    refusals — a sealed run, a crash, a missing input — which happen BEFORE any
    record exists; a run that executed and simply did not reproduce returns a
    record with ``reproduced: false``.
    """
    contract = load_contract(study_dir)
    problems = validate_contract(contract, study_dir)
    if problems:
        raise WorkflowError("invalid study contract: " + "; ".join(problems))
    tracks = normalize_tracks(contract)
    manifests = load_manifests(study_dir)
    manifest = _select_manifest(manifests, run_id)
    _refuse_unreplicable(manifest, run_id)
    track = str(manifest.get("track"))
    track_spec = tracks.get(track)
    if track_spec is None:
        raise WorkflowError(
            f"{run_id} ran on track {track!r}, which study.yaml no longer declares"
        )
    mode = "verify" if verify_only else "replicate"
    limit = float(
        timeout_seconds
        if timeout_seconds is not None
        else manifest.get("max_run_seconds") or contract.get("max_run_seconds") or 600
    )
    if limit <= 0:
        raise WorkflowError("timeout must be greater than zero")
    tolerance_value, tolerance_source = tolerance_ladder(
        track_spec, override=tolerance, mode=mode
    )

    with StudyLock(study_dir):
        directory = _replications_dir(study_dir, run_id)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = _stamp(directory)
        log_path = directory / f"{stamp}.log"
        record: dict[str, Any] = {
            "schema_version": 1,
            "experiment": run_id,
            "track": track,
            "mode": mode,
            "evidence_id": evidence_id(run_id, stamp, mode),
            "timestamp": utc_now(),
            "stamp": stamp,
            "metric_name": manifest.get("metric_name"),
            "tolerance": tolerance_value,
            "tolerance_source": tolerance_source,
            "candidate_commit": manifest.get("candidate_commit"),
            "original_environment_fingerprint": (manifest.get("fingerprints") or {}).get(
                "environment"
            ),
            "log": f"runs/{run_id}/replications/{stamp}.log",
            "record": f"runs/{run_id}/replications/{stamp}.json",
        }
        if mode == "verify":
            record.update(_run_verify(study_dir, manifest, track_spec, run_id, log_path, limit, echo))
        else:
            record.update(
                _run_replicate(study_dir, contract, manifest, run_id, log_path, limit, echo)
            )

        baseline = float(record.pop("_baseline", manifest["primary_metric"]))
        replicate_primary = record.pop("_replicate_primary", None)
        if replicate_primary is None:
            record["reproduced"] = False
            record["difference"] = None
            record.setdefault("failure_reason", "the run produced no `primary_metric:` line")
        else:
            difference = abs(float(replicate_primary) - baseline)
            record["difference"] = difference
            record["reproduced"] = difference <= tolerance_value
        record["baseline"] = baseline
        record["replicate_primary_metric"] = replicate_primary
        record["original_primary_metric"] = float(manifest["primary_metric"])
        record.update(
            _compare(record["original_block"], record["replicate_block"], tolerance_value)
        )

        atomic_write_json(directory / f"{stamp}.json", record)
        append_event(
            study_dir,
            "run_replicated",
            experiment=run_id,
            track=track,
            mode=mode,
            evidence_id=record["evidence_id"],
            reproduced=bool(record["reproduced"]),
            difference=record["difference"],
            tolerance=tolerance_value,
            tolerance_source=tolerance_source,
        )
        state = load_state(study_dir, contract)
        state["replications"] = _rollup(load_replications(study_dir))
        save_state(study_dir, state)

    verdict = "reproduced" if record["reproduced"] else "NOT reproduced"
    commit_state_writes(
        study_dir,
        f"klein: {mode} {run_id} — {verdict} ({record['evidence_id']})",
        paths=(f"runs/{run_id}/replications",),
    )
    return record


def _run_replicate(
    study_dir: Path,
    contract: Mapping[str, Any],
    manifest: Mapping[str, Any],
    run_id: str,
    log_path: Path,
    limit: float,
    echo: bool,
) -> dict[str, Any]:
    """Re-execute the run in a detached worktree at its candidate commit."""
    repo = repo_root_for(study_dir)
    study_rel = relative(repo, study_dir)
    commit = str(manifest.get("candidate_commit") or "")
    if not commit:
        raise WorkflowError(f"{run_id} records no candidate_commit to check out")
    command = manifest.get("command")
    if not isinstance(command, Sequence) or isinstance(command, (str, bytes)) or not command:
        raise WorkflowError(f"{run_id} records no command to re-run")
    command = [str(part) for part in command]
    data_expected = (manifest.get("fingerprints") or {}).get("data")
    # Refuse a missing or changed input before a worktree is created: an early
    # refusal costs nothing and leaves nothing to clean up.
    _assert_prepared_source(study_dir, contract, data_expected)

    out: dict[str, Any] = {"command": command}
    with detached_worktree(repo, commit, prefix="klein-replicate-") as worktree:
        worktree_study = worktree / study_rel
        if not (worktree_study / "study.yaml").is_file():
            raise WorkflowError(
                f"the study directory {study_rel} does not exist at {commit[:12]}; "
                f"{run_id} cannot be replicated from its own candidate commit"
            )
        _, data_fingerprint = _copy_prepared_data(
            study_dir, worktree_study, contract, data_expected
        )
        environment, environment_details = environment_fingerprint(worktree)
        started_at = utc_now()
        process = run_logged(
            command,
            cwd=worktree_study,
            log_path=log_path,
            timeout_seconds=limit,
            echo=echo,
            env_overrides=_child_env(manifest, run_id, str(manifest.get("track"))),
        )
        out.update(
            worktree_prepared=True,
            data_fingerprint=data_fingerprint,
            environment_fingerprint=environment,
            environment=environment_details,
            started_at=started_at,
            ended_at=utc_now(),
            wall_seconds=process.wall_seconds,
            exit_code=process.exit_code,
            timed_out=process.timed_out,
            max_run_seconds=limit,
        )
    out["environment_match"] = (
        out["environment_fingerprint"] == (manifest.get("fingerprints") or {}).get("environment")
    )
    original_block = manifest.get("metrics")
    original_block = dict(original_block) if isinstance(original_block, Mapping) else {}
    out["original_block"] = original_block
    out["_baseline"] = float(manifest["primary_metric"])
    if process.exit_code != 0:
        out["replicate_block"] = {}
        out["failure_reason"] = (
            f"timeout after {limit:g}s"
            if process.timed_out
            else f"process exit code {process.exit_code}"
        )
        return out
    try:
        primary, _name, _goal, metrics = parse_metric_log(log_path)
    except WorkflowError as exc:
        out["replicate_block"] = {}
        out["failure_reason"] = str(exc)
        return out
    out["replicate_block"] = metrics
    out["_replicate_primary"] = primary
    return out


def _run_verify(
    study_dir: Path,
    manifest: Mapping[str, Any],
    track_spec: Mapping[str, Any],
    run_id: str,
    log_path: Path,
    limit: float,
    echo: bool,
) -> dict[str, Any]:
    """Re-run only the declared verifier on the pinned artifact — no worktree.

    A minimal runner kept local to this module while Package A's declared-verifier
    execution inside ``run-one`` lands: same contract shape
    (``verifier {command, tolerance, artifact_key}``), same printed-block parser,
    same bounded foreground subprocess.
    """
    track = str(manifest.get("track"))
    command, artifact_key = _verifier_spec(track_spec, track)
    _assert_same_checker(study_dir, manifest, run_id)
    artifact_rel, artifact_path = _pinned_artifact(study_dir, manifest, artifact_key, run_id)
    baseline, baseline_source = _verified_baseline(manifest)
    # A verification needs no worktree, so it needs no repository either: fall
    # back to the study directory when the study is not (yet) inside one.
    try:
        root = repo_root_for(study_dir)
    except WorkflowError:
        root = study_dir
    environment, environment_details = environment_fingerprint(root)
    started_at = utc_now()
    process = run_logged(
        command,
        cwd=study_dir,
        log_path=log_path,
        timeout_seconds=limit,
        echo=echo,
        env_overrides=_child_env(
            manifest, run_id, track, KLEIN_ARTIFACT=str(artifact_path)
        ),
    )
    out: dict[str, Any] = {
        "command": command,
        "worktree_prepared": False,
        "artifact": artifact_rel,
        "artifact_sha256": sha256_file(artifact_path),
        "baseline_source": baseline_source,
        "environment_fingerprint": environment,
        "environment": environment_details,
        "environment_match": environment
        == (manifest.get("fingerprints") or {}).get("environment"),
        "started_at": started_at,
        "ended_at": utc_now(),
        "wall_seconds": process.wall_seconds,
        "exit_code": process.exit_code,
        "timed_out": process.timed_out,
        "max_run_seconds": limit,
        "original_block": {"primary_metric": baseline},
        "_baseline": baseline,
    }
    if process.exit_code != 0:
        out["replicate_block"] = {}
        out["failure_reason"] = (
            f"verifier timed out after {limit:g}s"
            if process.timed_out
            else f"verifier exit code {process.exit_code}"
        )
        return out
    try:
        primary, _name, _goal, metrics = parse_metric_log(log_path)
    except WorkflowError as exc:
        out["replicate_block"] = {}
        out["failure_reason"] = str(exc)
        return out
    out["replicate_block"] = metrics
    out["_replicate_primary"] = primary
    return out


# ---------------------------------------------------------------------------
# what `klein finalize` asks
# ---------------------------------------------------------------------------


def _confirmed_evidence_ids(study_dir: Path) -> set[str] | None:
    """The ``E####`` ids that ``confirmed`` claims cite, or ``None`` with no lock.

    ``claims.lock`` is the claim→evidence index the replication protocol means by
    "every cell a confirmed claim cites".  Returns ``None`` — not an empty set —
    when the study has no lock or the lock cannot be read, so the caller can tell
    "no index exists" (fall back to every measured cell) apart from "the index
    exists and names nothing" (nothing is confirmed, so nothing is required).
    A lock-schema-1 legacy ledger has no ``claims`` entries at all and also
    reads as ``None``.
    """
    from .claims import claims_map, detect_lock_schema, load_lock, lock_path

    if not lock_path(study_dir).is_file():
        return None
    try:
        lock = load_lock(study_dir)
        if detect_lock_schema(lock) < 2:
            return None
        claims = claims_map(lock)
    except WorkflowError:
        return None
    cited: set[str] = set()
    for entry in claims.values():
        if not isinstance(entry, Mapping) or entry.get("strength") != "confirmed":
            continue
        evidence = entry.get("evidence")
        if not isinstance(evidence, Sequence) or isinstance(evidence, str):
            continue
        for item in evidence:
            text = str(item)
            if RUN_ID_RE.match(text):
                cited.add(text)
    return cited


def _confirmation_targets(
    manifests: Sequence[Mapping[str, Any]],
    track: str,
    track_mode: str,
    cited: set[str] | None = None,
) -> list[str]:
    """Which runs must carry a record for this track's confirmation to hold.

    * ``frontier`` — the final incumbent: the claim rests on that one number.
    * ``registered`` — the measured development cells that ``confirmed`` claims
      cite, read from ``claims.lock``'s ``evidence[]`` (``cited``).  With no
      lock (``cited is None``) it falls back to EVERY measured development cell
      of the track: a strict superset, which can only under-confirm a study,
      never over-confirm it.
    """
    if track_mode == "registered":
        cells = [
            str(manifest.get("experiment"))
            for manifest in manifests
            if str(manifest.get("track")) == track
            and manifest.get("evaluation_kind", "development") == "development"
            and manifest.get("disposition") != "crash"
        ]
        return cells if cited is None else [cell for cell in cells if cell in cited]
    incumbent = _incumbent(manifests, track)
    return [str(incumbent.get("experiment"))] if incumbent else []


def confirmation_gaps(
    study_dir: Path,
    contract: Mapping[str, Any],
    manifests: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    """Per track, the ``replicate`` / ``verify`` records ``finalize`` is missing.

    Empty when no track REQUIRES ``replicate`` or ``verify`` — which is every
    schema-2 study (an untyped contract takes the ``sealed`` default), so the
    schema-2 ``finalize`` path is untouched: the function returns before it
    reads a single file.  ``sealed`` is deliberately not handled here —
    ``finalize`` already enforces it through the holdout counts.

    On a REGISTERED track the targets are the cells that ``confirmed`` claims
    cite in ``claims.lock``; with no lock every measured development cell is
    required instead.
    """
    tracks = normalize_tracks(contract)
    wanted = {
        track: sorted(required_confirmation(spec, contract) & set(MODES))
        for track, spec in tracks.items()
    }
    if not any(wanted.values()):
        return {}
    reproduced: dict[str, set[str]] = {mode: set() for mode in MODES}
    for record in load_replications(study_dir):
        if record.get("reproduced") is True and str(record.get("mode")) in reproduced:
            reproduced[str(record["mode"])].add(str(record.get("experiment")))
    cited = _confirmed_evidence_ids(study_dir)
    gaps: dict[str, list[str]] = {}
    for track, modes in wanted.items():
        if not modes:
            continue
        track_mode = str(tracks[track].get("mode", "frontier"))
        targets = _confirmation_targets(manifests, track, track_mode, cited)
        if track_mode == "registered" and cited is not None and not targets:
            # The lock exists and no `confirmed` claim cites a cell of this
            # track: there is nothing to confirm, which is not the same as
            # "the track has no development run".
            continue
        missing: list[str] = []
        for mode in modes:
            if not targets:
                missing.append(
                    f"{mode}: track {track!r} has no development run to reproduce "
                    f"(confirmation.require names {mode})"
                )
                continue
            lacking = [run_id for run_id in targets if run_id not in reproduced[mode]]
            if lacking:
                noun = "record" if len(lacking) == 1 else "records"
                missing.append(
                    f"{mode}: no `reproduced: true` {mode} {noun} for "
                    + ", ".join(lacking)
                    + f" (run `klein replicate {lacking[0]}"
                    + (" --verify-only" if mode == "verify" else "")
                    + "`)"
                )
        if missing:
            gaps[track] = missing
    return gaps
