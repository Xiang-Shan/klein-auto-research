"""Best-model snapshotting for Klein Auto Research studies.

Each study keeps a `models/manifest.tsv` ledger (created on first use) tracking every "new
best" checkpoint saved during the experiment loop, so the winning model is
always on disk under a name that encodes which experiment and what metric it
scored — no separate bookkeeping needed. `kleinlib.eval.evaluate` and
`evaluate_regression` call :func:`maybe_save_best` automatically whenever a
`study_dir` is given.

New manifests record relative paths, metric identity/direction, SHA-256, and
write-time availability; legacy four-column manifests remain readable.
History is append-only: superseded checkpoints are never deleted from disk
(only from "current best" status), matching the project's single-source
audit-trail ethos. New manifests carry a research track, so unrelated metric
frontiers cannot compete; legacy four-column manifests map to the `primary`
track and remain readable.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np

#: Manifest filename, under `<study_dir>/models/`.
MANIFEST_NAME = "manifest.tsv"

#: Column order for the manifest.
MANIFEST_COLUMNS = (
    "experiment",
    "track",
    "path",
    "metric",
    "primary_name",
    "metric_goal",
    "sha256",
    "available",
    "created_utc",
)

_LEGACY_MANIFEST_COLUMNS = ("experiment", "path", "metric", "created_utc")
_V2_PRE_TRACK_COLUMNS = (
    "experiment",
    "path",
    "metric",
    "primary_name",
    "metric_goal",
    "sha256",
    "available",
    "created_utc",
)

_VALID_GOALS = ("higher", "lower")


@dataclass(frozen=True)
class BestRecord:
    """One row of `models/manifest.tsv`."""

    experiment: str
    path: str
    metric: float
    created_utc: str
    track: str = "primary"
    primary_name: str = ""
    metric_goal: str = ""
    sha256: str = ""
    available: bool = True


@dataclass(frozen=True)
class SnapshotStatus:
    """Resolved availability and integrity of the current best artifact."""

    record: BestRecord | None
    resolved_path: Path | None
    available: bool
    hash_matches: bool | None
    reason: str


def _models_dir(study_dir: str | Path) -> Path:
    d = Path(study_dir) / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manifest_path(study_dir: str | Path) -> Path:
    return _models_dir(study_dir) / MANIFEST_NAME


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_path(study_dir: str | Path, recorded_path: str) -> Path:
    path = Path(recorded_path)
    return path if path.is_absolute() else Path(study_dir) / path


def _record_from_row(row: dict[str, str]) -> BestRecord:
    available_text = row.get("available", "true").strip().lower()
    return BestRecord(
        experiment=row["experiment"],
        path=row["path"],
        metric=float(row["metric"]),
        created_utc=row["created_utc"],
        track=row.get("track", "primary") or "primary",
        primary_name=row.get("primary_name", ""),
        metric_goal=row.get("metric_goal", ""),
        sha256=row.get("sha256", ""),
        available=available_text in ("true", "1", "yes"),
    )


def _read_records(study_dir: str | Path) -> list[BestRecord]:
    path = _manifest_path(study_dir)
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames not in (
            list(MANIFEST_COLUMNS),
            list(_V2_PRE_TRACK_COLUMNS),
            list(_LEGACY_MANIFEST_COLUMNS),
        ):
            raise ValueError(
                f"unsupported snapshot manifest header in {path}: {reader.fieldnames}"
            )
        return [_record_from_row(row) for row in reader if any(row.values())]


def _record_row(record: BestRecord) -> str:
    values = (
        record.experiment,
        record.track,
        record.path,
        f"{record.metric:.17g}",
        record.primary_name,
        record.metric_goal,
        record.sha256,
        "true" if record.available else "false",
        record.created_utc,
    )
    if any("\t" in value or "\n" in value or "\r" in value for value in values):
        raise ValueError("snapshot manifest values must not contain tabs or newlines")
    return "\t".join(values)


def _atomic_write_manifest(study_dir: str | Path, records: list[BestRecord]) -> None:
    path = _manifest_path(study_dir)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    payload = "\n".join(
        ["\t".join(MANIFEST_COLUMNS), *[_record_row(record) for record in records]]
    ) + "\n"
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_model_atomic(model: Any, destination: Path) -> str:
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        joblib.dump(model, temporary)
        digest = _sha256(temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return digest


def _safe_component(value: int | str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-.")
    return safe or "experiment"


def read_current_best(
    study_dir: str | Path, *, track: str | None = None
) -> BestRecord | None:
    """Return the latest best record, optionally scoped to one research track.

    ``track=None`` preserves the v1 API and returns the manifest's last row. New
    schema-v2 callers pass a track so unrelated metric frontiers never interact.
    """
    records = _read_records(study_dir)
    if track is not None:
        records = [record for record in records if record.track == track]
    return records[-1] if records else None


def snapshot_status(
    study_dir: str | Path, *, track: str | None = None
) -> SnapshotStatus:
    """Report whether the current best exists and matches its recorded hash."""
    record = read_current_best(study_dir, track=track)
    if record is None:
        return SnapshotStatus(None, None, False, None, "no best model recorded")
    resolved = _resolve_path(study_dir, record.path)
    if not record.available:
        return SnapshotStatus(
            record, resolved, False, None, "manifest marks model artifact unavailable"
        )
    if not resolved.is_file():
        return SnapshotStatus(
            record, resolved, False, None, "recorded model artifact is missing"
        )
    if not record.sha256:
        return SnapshotStatus(
            record, resolved, True, None, "legacy manifest has no SHA-256"
        )
    matches = _sha256(resolved) == record.sha256
    return SnapshotStatus(
        record,
        resolved,
        True,
        matches,
        "ok" if matches else "model artifact SHA-256 mismatch",
    )


def maybe_save_best(
    model: Any,
    *,
    exp_id: int | str,
    metric_value: float,
    metric_goal: str,
    study_dir: str | Path,
    primary_name: str,
    track: str = "primary",
) -> str | None:
    """Pickle `model` as the new best-so-far if it beats the manifest's best.

    Atomically writes a collision-proof joblib artifact and an integrity-aware
    manifest record when ``model`` is a new best. ``metric_goal`` must be
    ``"higher"`` or ``"lower"`` and may not change direction/name within one
    track.

    Returns the saved path as a string if a new best was written, else None.
    """
    if metric_goal not in _VALID_GOALS:
        raise ValueError(
            f"metric_goal must be one of {_VALID_GOALS}, got {metric_goal!r}"
        )
    if not track or any(char.isspace() for char in track):
        raise ValueError("track must be a non-empty token without whitespace")

    try:
        numeric_metric = float(metric_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"metric_value must be numeric, got {metric_value!r}") from exc
    if not np.isfinite(numeric_metric):
        raise ValueError(f"metric_value must be finite, got {numeric_metric!r}")
    if not primary_name or any(char.isspace() for char in primary_name):
        raise ValueError("primary_name must be a non-empty token without whitespace")

    current = read_current_best(study_dir, track=track)
    if current is not None:
        if current.primary_name and current.primary_name != primary_name:
            raise ValueError(
                f"snapshot metric changed from {current.primary_name!r} to "
                f"{primary_name!r}; use a separate study/track"
            )
        if current.metric_goal and current.metric_goal != metric_goal:
            raise ValueError(
                f"snapshot metric goal changed from {current.metric_goal!r} to "
                f"{metric_goal!r}"
            )
    is_better = current is None or (
        numeric_metric > current.metric
        if metric_goal == "higher"
        else numeric_metric < current.metric
    )
    if not is_better:
        return None

    models_dir = _models_dir(study_dir)
    unique = uuid.uuid4().hex[:12]
    out_path = models_dir / (
        f"best_{_safe_component(track)}_{_safe_component(exp_id)}_"
        f"{numeric_metric:.6g}_{unique}.joblib"
    )
    digest = _write_model_atomic(model, out_path)

    relative_path = out_path.relative_to(Path(study_dir)).as_posix()
    created = datetime.now(UTC).isoformat()
    record = BestRecord(
        experiment=str(exp_id),
        path=relative_path,
        metric=numeric_metric,
        created_utc=created,
        track=track,
        primary_name=primary_name,
        metric_goal=metric_goal,
        sha256=digest,
        available=True,
    )
    _atomic_write_manifest(study_dir, [*_read_records(study_dir), record])

    return relative_path


def rebuild_missing(
    model: Any, study_dir: str | Path, *, track: str | None = None
) -> str:
    """Rebuild a missing/corrupt current-best artifact without changing its score."""
    status = snapshot_status(study_dir, track=track)
    if status.record is None:
        raise FileNotFoundError("cannot rebuild: no best model is recorded")
    if status.available and status.hash_matches is not False:
        raise FileExistsError(f"current best artifact is already available: {status.resolved_path}")

    record = status.record
    models_dir = _models_dir(study_dir)
    destination = models_dir / (
        f"rebuilt_{_safe_component(record.track)}_{_safe_component(record.experiment)}_"
        f"{uuid.uuid4().hex[:12]}.joblib"
    )
    digest = _write_model_atomic(model, destination)
    rebuilt = BestRecord(
        experiment=record.experiment,
        path=destination.relative_to(Path(study_dir)).as_posix(),
        metric=record.metric,
        created_utc=datetime.now(UTC).isoformat(),
        track=record.track,
        primary_name=record.primary_name,
        metric_goal=record.metric_goal,
        sha256=digest,
        available=True,
    )
    _atomic_write_manifest(study_dir, [*_read_records(study_dir), rebuilt])
    return rebuilt.path


def load_best(study_dir: str | Path, *, track: str | None = None) -> Any:
    """Load and return the current best model.

    Raises `FileNotFoundError` if no best model has been recorded yet.
    """
    status = snapshot_status(study_dir, track=track)
    if status.record is None:
        raise FileNotFoundError(
            f"no best model recorded yet under {Path(study_dir) / 'models' / MANIFEST_NAME}"
        )
    if not status.available:
        raise FileNotFoundError(
            f"best model artifact is missing at {status.resolved_path}; "
            "call rebuild_missing(model, study_dir) with a reconstructed model"
        )
    if status.hash_matches is False:
        raise OSError(
            f"best model artifact failed SHA-256 verification at {status.resolved_path}; "
            "call rebuild_missing(model, study_dir) with a trusted reconstructed model"
        )
    return joblib.load(status.resolved_path)
