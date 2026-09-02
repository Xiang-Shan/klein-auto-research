"""Per-run manifests, their validation, and the derived results view.

Extracted verbatim from :mod:`kleinlib.workflow`.  ``runs/E####/manifest.json``
is the immutable evidence of one candidate transaction; ``results.tsv`` is only
its rendering.  Also here: the artifact inventory a run snapshots before and
after execution, and the run-log evidence entry every completed transaction
carries.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .contract import VALID_DISPOSITIONS
from .errors import WorkflowError
from .primitives import atomic_write_text, sha256_file
from .schema import V2_RESULTS_COLUMNS

__all__ = [
    "RUN_ID_RE",
    "UNSAFE_PAYLOAD_SUFFIXES",
    "artifact_inventory",
    "derive_results",
    "load_manifests",
    "render_results",
    "validate_manifest",
]

RUN_ID_RE = re.compile(r"^E([0-9]{4,})$")

UNSAFE_PAYLOAD_SUFFIXES = frozenset(
    {".pkl", ".pickle", ".joblib", ".pt", ".pth", ".ckpt", ".onnx", ".npz"}
)


def _manifest_paths(study_dir: Path) -> list[Path]:
    runs = study_dir / "runs"
    if not runs.exists():
        return []
    paths = [p / "manifest.json" for p in runs.iterdir() if p.is_dir() and RUN_ID_RE.match(p.name)]
    return sorted((p for p in paths if p.is_file()), key=lambda p: int(RUN_ID_RE.match(p.parent.name).group(1)))  # type: ignore[union-attr]


def load_manifests(study_dir: Path) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    for path in _manifest_paths(study_dir):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"invalid {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise WorkflowError(f"manifest must be an object: {path}")
        manifests.append(value)
    return manifests


def validate_manifest(manifest: Mapping[str, Any], expected_number: int | None = None) -> list[str]:
    problems: list[str] = []
    run_id = manifest.get("experiment")
    match = RUN_ID_RE.match(str(run_id))
    if not match:
        problems.append("experiment must be E followed by at least four digits")
    elif expected_number is not None and int(match.group(1)) != expected_number:
        problems.append(f"experiment sequence expected E{expected_number:04d}, got {run_id}")
    if not manifest.get("track"):
        problems.append("track is required")
    disposition = manifest.get("disposition")
    if disposition not in VALID_DISPOSITIONS:
        problems.append(f"disposition must be one of {sorted(VALID_DISPOSITIONS)}")
    for field in ("base_commit", "candidate_commit", "code_patch_hash"):
        value = manifest.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40,64}", value):
            problems.append(f"{field} must be a full hex digest")
    metric = manifest.get("primary_metric")
    if disposition == "crash":
        if metric is not None:
            problems.append("crash primary_metric must be null")
    elif not isinstance(metric, (int, float)) or not math.isfinite(float(metric)):
        problems.append("non-crash primary_metric must be finite")
    transaction = manifest.get("transaction", {})
    transaction_complete = isinstance(transaction, Mapping) and transaction.get("status") == "complete"
    if not isinstance(transaction, Mapping) or transaction.get("status") not in {
        "pending",
        "complete",
    }:
        problems.append("transaction.status must be pending or complete")
    elif transaction_complete:
        evidence_commit = transaction.get("evidence_commit", transaction.get("prepared_commit"))
        if not isinstance(evidence_commit, str) or not re.fullmatch(
            r"[0-9a-f]{40,64}", evidence_commit
        ):
            problems.append("complete transaction requires a full evidence_commit")
    fingerprints = manifest.get("fingerprints")
    if not isinstance(fingerprints, Mapping):
        problems.append("fingerprints mapping is required")
    else:
        for field in ("data", "split", "environment"):
            if not isinstance(fingerprints.get(field), str):
                problems.append(f"fingerprints.{field} is required")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        problems.append("artifacts mapping is required")
    else:
        for rel, meta in artifacts.items():
            path = Path(str(rel))
            if path.is_absolute() or ".." in path.parts:
                problems.append(f"artifact path must stay inside the study: {rel}")
            if not isinstance(meta, Mapping):
                problems.append(f"artifact metadata must be a mapping: {rel}")
                continue
            if not isinstance(meta.get("sha256"), str) or not re.fullmatch(
                r"[0-9a-f]{64}", str(meta.get("sha256"))
            ):
                problems.append(f"artifact sha256 is invalid: {rel}")
            if not isinstance(meta.get("bytes"), int) or int(meta.get("bytes", -1)) < 0:
                problems.append(f"artifact byte count is invalid: {rel}")
            if not isinstance(meta.get("committed"), bool):
                problems.append(f"artifact committed flag is invalid: {rel}")
            availability = meta.get("availability")
            if availability not in {"local", "recorded", "missing"}:
                problems.append(f"artifact availability is invalid: {rel}")
            if meta.get("committed") is True and availability != "recorded":
                problems.append(
                    f"committed artifact availability must be recorded: {rel}"
                )
        log_rel = f"runs/{run_id}/run.log"
        if transaction_complete and log_rel not in artifacts:
            problems.append(f"completed transaction is missing run-log evidence: {log_rel}")
    return problems



def _evidence_commit(manifest: Mapping[str, Any]) -> str | None:
    transaction = manifest.get("transaction", {})
    if not isinstance(transaction, Mapping):
        return None
    value = transaction.get("evidence_commit", transaction.get("prepared_commit"))
    return value if isinstance(value, str) else None


def _artifact_path(study_dir: Path, rel: str) -> Path:
    relative = Path(rel)
    if relative.is_absolute() or ".." in relative.parts:
        raise WorkflowError(f"artifact path must stay inside the study: {rel}")
    path = (study_dir / relative).resolve()
    try:
        path.relative_to(study_dir.resolve())
    except ValueError as exc:
        raise WorkflowError(f"artifact path escapes the study: {rel}") from exc
    return path



def render_results(manifests: Iterable[Mapping[str, Any]]) -> str:
    rows: list[list[str]] = []
    for manifest in manifests:
        status = str(manifest.get("disposition", "crash"))
        metric = "NA" if status == "crash" else format(float(manifest["primary_metric"]), ".12g")
        description = str(manifest.get("description", "")).replace("\t", " ").replace("\r", " ").replace("\n", " ")
        rows.append(
            [
                str(manifest.get("experiment", "")),
                str(manifest.get("track", "")),
                metric,
                status,
                str(manifest.get("candidate_commit", "")),
                description,
            ]
        )
    output = ["\t".join(V2_RESULTS_COLUMNS)]
    output.extend("\t".join(row) for row in rows)
    return "\n".join(output) + "\n"


def derive_results(study_dir: Path) -> str:
    text = render_results(load_manifests(study_dir))
    atomic_write_text(study_dir / "results.tsv", text)
    return text



def artifact_inventory(study_dir: Path) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    candidates: list[Path] = []
    for dirname in ("models", "figures"):
        root = study_dir / dirname
        if root.exists():
            candidates.extend(p for p in root.rglob("*") if p.is_file())
    aux = study_dir / "aux_metrics.tsv"
    if aux.is_file():
        candidates.append(aux)
    for path in sorted(set(candidates)):
        rel = path.relative_to(study_dir).as_posix()
        size = path.stat().st_size
        safe = path.suffix.lower() not in UNSAFE_PAYLOAD_SUFFIXES and size <= 10 * 1024 * 1024
        inventory[rel] = {
            "availability": "recorded" if rel in {"aux_metrics.tsv", "models/manifest.tsv"} else "local",
            "sha256": sha256_file(path),
            "bytes": size,
            "committed": safe,
        }
    return inventory


def _run_log_evidence(study_dir: Path, run_id: str) -> dict[str, Any]:
    log_path = study_dir / "runs" / run_id / "run.log"
    if not log_path.is_file():
        raise WorkflowError(f"run log is missing for {run_id}")
    return {
        "availability": "recorded",
        "sha256": sha256_file(log_path),
        "bytes": log_path.stat().st_size,
        "committed": True,
    }
