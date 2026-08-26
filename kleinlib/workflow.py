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
import datetime as dt
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .runner import run_logged
from .schema import (
    AUTO_PRINTED_METRIC_KEYS,
    EVALUATOR_PRINTED_KEYS,
    V2_RESULTS_COLUMNS,
)

SCHEMA_VERSION = 2
RUN_ID_RE = re.compile(r"^E([0-9]{4,})$")
STUDY_ID_RE = re.compile(r"^\d{2}-[a-z0-9][a-z0-9-]*$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")
METRIC_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$")
VALID_GOALS = frozenset({"higher", "lower"})
VALID_DISPOSITIONS = frozenset({"keep", "discard", "crash"})
STRONG_CLAIM_RE = re.compile(r"(?i)\b(?:real|decisive)\b")
UNCERTAINTY_EVIDENCE_RE = re.compile(
    r"(?i)\b(?:bootstrap(?:ped|ping)?|confidence interval|credible interval|"
    r"standard error|error bars?|uncertainty (?:estimate|interval|quantification)|"
    # Klein's own Phase-0 vocabulary: deltas stated against a measured floor
    # ARE uncertainty-qualified claims.
    r"noise[- ]floor|floor std|seed[- ]block std)\b"
)
GATE_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "consult": ("study.yaml", "research_plan.md", "program.md"),
    "data": ("data_card.md",),
    "method": ("method_card.md",),
}
UNSAFE_PAYLOAD_SUFFIXES = frozenset(
    {".pkl", ".pickle", ".joblib", ".pt", ".pth", ".ckpt", ".onnx", ".npz"}
)


class WorkflowError(RuntimeError):
    """A user-correctable workflow contract violation."""


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


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_path(path: Path) -> str:
    """Hash a file or a directory tree without embedding its absolute location."""
    if not path.exists():
        raise WorkflowError(f"prepared data does not exist: {path}")
    if path.is_symlink():
        raise WorkflowError(f"prepared data must not be a symlink: {path}")
    if path.is_file():
        digest = hashlib.sha256(b"file\0" + path.name.encode() + b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    digest = hashlib.sha256(b"tree\0")
    entries = sorted(path.rglob("*"))
    symlinks = [entry for entry in entries if entry.is_symlink()]
    if symlinks:
        raise WorkflowError(
            "prepared data trees must not contain symlinks: "
            + ", ".join(str(item.relative_to(path)) for item in symlinks[:5])
        )
    files = [entry for entry in entries if entry.is_file()]
    if not files:
        raise WorkflowError(f"prepared data directory is empty: {path}")
    for item in files:
        rel = item.relative_to(path).as_posix().encode()
        digest.update(rel + b"\0")
        digest.update(bytes.fromhex(sha256_file(item)))
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


class StudyLock:
    """Portable single-process lock using exclusive file creation."""

    def __init__(self, study_dir: Path) -> None:
        self.path = study_dir / ".klein.lock"
        self.fd: int | None = None

    def __enter__(self) -> StudyLock:
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise WorkflowError(
                f"another Klein operation is active ({self.path}); remove a stale lock "
                "only after confirming no run is alive"
            ) from exc
        os.write(self.fd, f"pid={os.getpid()} started={utc_now()}\n".encode())
        return self

    def __exit__(self, *_: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
        self.path.unlink(missing_ok=True)


def resolve_study(path: str | Path) -> Path:
    study = Path(path).expanduser().resolve()
    if study.is_file() and study.name == "study.yaml":
        study = study.parent
    if not study.is_dir():
        raise WorkflowError(f"study directory not found: {study}")
    if not (study / "study.yaml").is_file():
        raise WorkflowError(f"study.yaml not found under {study}")
    return study


def load_contract(study_dir: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load((study_dir / "study.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"could not read study.yaml: {exc}") from exc
    if not isinstance(raw, dict):
        raise WorkflowError("study.yaml must contain a top-level mapping")
    return raw


def schema_version(contract: Mapping[str, Any]) -> int:
    value = contract.get("schema_version", 1)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise WorkflowError(f"invalid schema_version: {value!r}") from exc


def _placeholder_locations(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, str) and PLACEHOLDER_RE.search(value):
        found.append(prefix or "<root>")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(_placeholder_locations(child, f"{prefix}.{key}".strip(".")))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_placeholder_locations(child, f"{prefix}[{index}]"))
    return found


def normalize_tracks(contract: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = contract.get("tracks")
    output: dict[str, dict[str, Any]] = {}
    if isinstance(raw, Mapping):
        for key, value in raw.items():
            if isinstance(value, Mapping):
                output[str(key)] = dict(value)
    elif isinstance(raw, list):
        for value in raw:
            if isinstance(value, Mapping) and value.get("id"):
                item = dict(value)
                output[str(item.pop("id"))] = item
    for track, spec in output.items():
        metric = spec.get("metric")
        if not isinstance(metric, Mapping):
            metric = {
                "name": spec.get("metric_name"),
                "goal": spec.get("metric_goal"),
                "minimum_delta": spec.get("minimum_delta", 0.0),
            }
        spec["metric"] = dict(metric)
        spec.setdefault("guardrails", {})
        output[track] = spec
    return output


def _guardrail_entries(
    guardrails: Mapping[str, Any] | list[Any],
) -> tuple[list[tuple[str, Mapping[str, Any]]], list[str]]:
    """Normalize guardrails and return structural problems without coercion."""
    entries: list[tuple[str, Mapping[str, Any]]] = []
    problems: list[str] = []
    if isinstance(guardrails, Mapping):
        for name, raw in guardrails.items():
            entries.append(
                (str(name), raw if isinstance(raw, Mapping) else {"max": raw})
            )
    elif isinstance(guardrails, list):
        for index, raw in enumerate(guardrails):
            if not isinstance(raw, Mapping) or not (raw.get("metric") or raw.get("name")):
                problems.append(
                    f"guardrail {index}: list entries require a metric or name"
                )
                continue
            entries.append((str(raw.get("metric", raw.get("name"))), raw))
    else:
        problems.append("guardrails must be a mapping or list")
    return entries, problems


def _guardrail_contract_problems(guardrails: Any) -> list[str]:
    if not isinstance(guardrails, (Mapping, list)):
        return ["guardrails must be a mapping or list"]
    entries, problems = _guardrail_entries(guardrails)
    allowed = {"metric", "name", "min", "max", "maximum_degradation", "goal"}
    for name, spec in entries:
        if not name.strip():
            problems.append("guardrail metric names must be non-empty")
        unknown = set(spec) - allowed
        if unknown:
            problems.append(f"guardrail {name!r}: unknown keys {sorted(unknown)}")
        limits: dict[str, float] = {}
        for field in ("min", "max", "maximum_degradation"):
            if field not in spec:
                continue
            try:
                value = float(spec[field])
                if not math.isfinite(value):
                    raise ValueError
                if field == "maximum_degradation" and value < 0:
                    raise ValueError
            except (TypeError, ValueError):
                qualifier = "finite and >= 0" if field == "maximum_degradation" else "finite"
                problems.append(f"guardrail {name!r}: {field} must be {qualifier}")
            else:
                limits[field] = value
        if not any(field in spec for field in ("min", "max", "maximum_degradation")):
            problems.append(f"guardrail {name!r}: at least one limit is required")
        if "min" in limits and "max" in limits and limits["min"] > limits["max"]:
            problems.append(f"guardrail {name!r}: min must be <= max")
        if "goal" in spec and spec.get("goal") not in VALID_GOALS:
            problems.append(f"guardrail {name!r}: goal must be higher or lower")
    return problems


def validate_contract(contract: Mapping[str, Any], study_dir: Path | None = None) -> list[str]:
    from .eval import get_metric_spec

    problems: list[str] = []
    try:
        version = schema_version(contract)
    except WorkflowError as exc:
        return [str(exc)]
    if version != SCHEMA_VERSION:
        return [f"schema_version must be {SCHEMA_VERSION} for the v0.2 workflow"]
    study_id = contract.get("study_id")
    if not isinstance(study_id, str) or not study_id.strip():
        problems.append("study_id is required")
    else:
        if not STUDY_ID_RE.fullmatch(study_id):
            problems.append("study_id must match NN-lowercase-slug")
        if study_dir is not None and study_id != study_dir.name:
            problems.append(
                f"study_id {study_id!r} must equal directory name {study_dir.name!r}"
            )
    if contract.get("method_depth") not in {"brief", "full"}:
        problems.append("method_depth must be brief or full")
    if contract.get("task_type") not in {"classification", "regression", "simulation"}:
        problems.append("task_type must be classification, regression, or simulation")
    try:
        max_run_seconds = float(contract.get("max_run_seconds", 0))
        if not math.isfinite(max_run_seconds) or max_run_seconds <= 0:
            raise ValueError
    except (TypeError, ValueError):
        problems.append("max_run_seconds must be a positive number")

    tracks = normalize_tracks(contract)
    if not tracks:
        problems.append("at least one track is required")
    for name, spec in tracks.items():
        if not IDENTIFIER_RE.fullmatch(name):
            problems.append(
                f"track id {name!r} must contain only letters, digits, dot, underscore, or hyphen"
            )
        metric = spec["metric"]
        metric_name = metric.get("name")
        metric_goal = metric.get("goal")
        if not isinstance(metric_name, str) or not metric_name:
            problems.append(f"track {name!r}: metric.name is required")
        if metric_goal not in VALID_GOALS:
            problems.append(f"track {name!r}: metric.goal must be higher or lower")
        if isinstance(metric_name, str) and metric_name and metric_goal in VALID_GOALS:
            simulation = contract.get("task_type") == "simulation"
            try:
                get_metric_spec(
                    metric_name,
                    goal=str(metric_goal),
                    task="scalar" if simulation else str(contract.get("task_type")),
                    allow_custom=simulation,
                )
            except ValueError as exc:
                problems.append(f"track {name!r}: {exc}")
        power = metric.get("power")
        if metric_name == "val_tweedie_deviance":
            try:
                power_value = float(power)
                if not math.isfinite(power_value) or not 1.0 < power_value < 2.0:
                    raise ValueError
            except (TypeError, ValueError):
                problems.append(
                    f"track {name!r}: val_tweedie_deviance requires metric.power with "
                    "1 < power < 2 (use val_poisson_deviance or val_gamma_deviance "
                    "for the endpoints)"
                )
        elif power is not None:
            problems.append(
                f"track {name!r}: metric.power applies only to val_tweedie_deviance"
            )
        try:
            minimum_delta = float(metric.get("minimum_delta", 0))
            if not math.isfinite(minimum_delta) or minimum_delta < 0:
                raise ValueError
        except (TypeError, ValueError):
            problems.append(f"track {name!r}: metric.minimum_delta must be finite and >= 0")
        if metric.get("noise_floor") is not None:
            problems.extend(
                f"track {name!r}: {problem}"
                for problem in _noise_floor_problems(metric.get("noise_floor"))
            )
        bound = metric.get("bound")
        if bound is not None:
            if not isinstance(bound, Mapping):
                problems.append(f"track {name!r}: metric.bound must be a mapping")
            else:
                unknown_bound = set(bound) - {"ideal", "on_infeasible"}
                if unknown_bound:
                    problems.append(
                        f"track {name!r}: metric.bound has unknown keys: {sorted(unknown_bound)}"
                    )
                try:
                    ideal_value = float(bound.get("ideal"))
                    if not math.isfinite(ideal_value):
                        raise ValueError
                except (TypeError, ValueError):
                    problems.append(
                        f"track {name!r}: metric.bound.ideal must be a finite number"
                    )
                if bound.get("on_infeasible", "ack") not in {"ack", "warn", "block"}:
                    problems.append(
                        f"track {name!r}: metric.bound.on_infeasible must be ack, warn, or block"
                    )
                floor_block = metric.get("noise_floor")
                if isinstance(floor_block, Mapping) and floor_block.get("estimand") is None:
                    problems.append(
                        f"track {name!r}: metric.bound requires noise_floor.estimand "
                        "(marginal-resplit | paired-comparison) — name which question "
                        "the floor answers before arming the headroom audit"
                    )
        for problem in _guardrail_contract_problems(spec.get("guardrails")):
            problems.append(f"track {name!r}: {problem}")

    data = contract.get("data")
    split = data.get("split") if isinstance(data, Mapping) else None
    if not isinstance(split, Mapping):
        problems.append("data.split is required")
    else:
        split_kind = split.get("kind")
        simulation = contract.get("task_type") == "simulation"
        allowed_kinds = {"stratified", "random", "group", "time"}
        if simulation:
            allowed_kinds = allowed_kinds | {"none"}
        if split_kind not in allowed_kinds:
            problems.append(
                "data.split.kind must be stratified, random, group, or time"
                + (" (or none)" if simulation else "")
            )
        if split_kind == "none" and not simulation:
            problems.append("data.split.kind none is valid only for simulation studies")
        if split_kind == "stratified" and contract.get("task_type") == "regression":
            problems.append("regression studies cannot use a stratified split")
        if split_kind == "group" and not split.get("group_column"):
            problems.append("data.split.group_column is required for a group split")
        if split_kind == "time" and not split.get("time_column"):
            problems.append("data.split.time_column is required for a time split")
        if split_kind != "none":
            try:
                dev = float(split.get("development_size"))
                test = float(split.get("test_size"))
                if not (0 < dev < 1 and 0 < test < 1 and dev + test < 1):
                    raise ValueError
            except (TypeError, ValueError):
                problems.append(
                    "data.split development_size and test_size must be positive and sum to < 1"
                )

    phases = contract.get("phases")
    if not isinstance(phases, list) or len(phases) < 2:
        problems.append(
            "at least two phases are required (adaptive work and final confirmation)"
        )
    else:
        ids: set[str] = set()
        for index, phase in enumerate(phases):
            if not isinstance(phase, Mapping):
                problems.append(f"phase {index}: must be a mapping")
                continue
            raw_phase_id = phase.get("id")
            phase_id = raw_phase_id if isinstance(raw_phase_id, str) else ""
            if not IDENTIFIER_RE.fullmatch(phase_id) or phase_id in ids:
                problems.append(
                    f"phase {index}: id is required, must be a valid identifier, "
                    "and must be unique"
                )
            ids.add(phase_id)
            try:
                budget_seconds = float(phase.get("budget_seconds", 0))
                if not math.isfinite(budget_seconds) or budget_seconds <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                problems.append(f"phase {phase_id or index}: budget_seconds must be positive")
            try:
                raw_max_experiments = phase.get("max_experiments", 0)
                max_experiments = int(raw_max_experiments)
                if (
                    isinstance(raw_max_experiments, bool)
                    or max_experiments <= 0
                    or float(raw_max_experiments) != max_experiments
                ):
                    raise ValueError
            except (TypeError, ValueError):
                problems.append(f"phase {phase_id or index}: max_experiments must be positive")
        final_phase = phases[-1]
        if isinstance(final_phase, Mapping) and tracks:
            try:
                final_capacity = int(final_phase.get("max_experiments", 0))
            except (TypeError, ValueError):
                final_capacity = 0
            if final_capacity < len(tracks):
                problems.append(
                    "final phase max_experiments must be at least the number of tracks "
                    f"({len(tracks)})"
                )
    locations = _placeholder_locations(contract)
    if locations:
        problems.append("unresolved placeholders at " + ", ".join(locations))
    return problems


def _noise_floor_problems(floor: Any) -> list[str]:
    from .noise_floor import ALLOWED_KEYS

    if not isinstance(floor, Mapping):
        return ["metric.noise_floor must be a mapping"]
    problems: list[str] = []
    unknown = set(floor) - ALLOWED_KEYS
    if unknown:
        problems.append(f"metric.noise_floor has unknown keys: {sorted(unknown)}")
    method = floor.get("method")
    if method is not None and (not isinstance(method, str) or not method.strip()):
        problems.append("metric.noise_floor.method must be a non-empty string")
    estimand = floor.get("estimand")
    if estimand is not None and estimand not in {"marginal-resplit", "paired-comparison"}:
        problems.append(
            "metric.noise_floor.estimand must be marginal-resplit or paired-comparison"
        )
    try:
        k = int(floor.get("k", 0))
        if k < 3:
            raise ValueError
    except (TypeError, ValueError):
        problems.append("metric.noise_floor.k must be an integer >= 3")
        k = None
    for key in ("std", "range"):
        try:
            value = float(floor.get(key))
            if not math.isfinite(value) or value < 0:
                raise ValueError
        except (TypeError, ValueError):
            problems.append(f"metric.noise_floor.{key} must be finite and >= 0")
    values = floor.get("values")
    if values is not None:
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            problems.append("metric.noise_floor.values must be a list of numbers")
        else:
            try:
                floats = [float(v) for v in values]
                if any(not math.isfinite(v) for v in floats):
                    raise ValueError
                if k is not None and len(floats) != k:
                    problems.append("metric.noise_floor.values length must equal k")
            except (TypeError, ValueError):
                problems.append("metric.noise_floor.values must all be finite numbers")
    return problems


def prepared_data_path(study_dir: Path, contract: Mapping[str, Any]) -> Path:
    data = contract.get("data")
    if not isinstance(data, Mapping):
        raise WorkflowError("study.yaml:data must be a mapping")
    raw = data.get("prepared_path", data.get("path"))
    if not isinstance(raw, str) or not raw.strip():
        raise WorkflowError("study.yaml:data.prepared_path is required")
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (study_dir / path).resolve()


def split_fingerprint(contract: Mapping[str, Any]) -> str:
    data = contract.get("data")
    split = data.get("split") if isinstance(data, Mapping) else None
    if not isinstance(split, Mapping):
        raise WorkflowError("study.yaml:data.split is required")
    return sha256_bytes(canonical_json(split).encode())


def environment_fingerprint(repo_root: Path) -> tuple[str, dict[str, Any]]:
    lock = repo_root / "uv.lock"
    details = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "uv_lock_sha256": sha256_file(lock) if lock.is_file() else None,
    }
    return sha256_bytes(canonical_json(details).encode()), details


def _phase_ids(contract: Mapping[str, Any]) -> list[str]:
    phases = contract.get("phases", [])
    return [str(p["id"]) for p in phases if isinstance(p, Mapping) and "id" in p]


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


def events_path(study_dir: Path) -> Path:
    return study_dir / "events.jsonl"


def read_events(study_dir: Path) -> list[dict[str, Any]]:
    path = events_path(study_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"events.jsonl line {lineno} is invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise WorkflowError(f"events.jsonl line {lineno} is not an object")
        events.append(value)
    return events


def verify_event_chain(study_dir: Path) -> list[str]:
    problems: list[str] = []
    previous: str | None = None
    try:
        events = read_events(study_dir)
    except WorkflowError as exc:
        return [str(exc)]
    for index, event in enumerate(events, start=1):
        given = event.get("event_hash")
        body = dict(event)
        body.pop("event_hash", None)
        expected = sha256_bytes(canonical_json(body).encode())
        if event.get("sequence") != index:
            problems.append(f"event {index}: sequence is {event.get('sequence')!r}")
        if event.get("previous_hash") != previous:
            problems.append(f"event {index}: previous_hash does not match")
        if given != expected:
            problems.append(f"event {index}: event_hash does not match content")
        previous = given if isinstance(given, str) else None
    return problems


def append_event(study_dir: Path, event_type: str, **payload: Any) -> dict[str, Any]:
    events = read_events(study_dir)
    previous = events[-1].get("event_hash") if events else None
    event: dict[str, Any] = {
        "sequence": len(events) + 1,
        "timestamp": utc_now(),
        "type": event_type,
        "previous_hash": previous,
        **payload,
    }
    event["event_hash"] = sha256_bytes(canonical_json(event).encode())
    path = events_path(study_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(event) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event


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


def _git(repo: Path, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise WorkflowError(f"git {' '.join(args)} failed: {detail}")
    return result


def repo_root_for(study_dir: Path) -> Path:
    result = _git(study_dir, ["rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip()).resolve()


def current_branch(repo_root: Path) -> str:
    result = _git(repo_root, ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
    if result.returncode:
        raise WorkflowError("detached HEAD is not allowed for a study run")
    return result.stdout.strip()


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


def _git_blob(repo: Path, commit: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


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


def parse_metric_log(path: Path) -> tuple[float, str | None, str | None, dict[str, float]]:
    primary: float | None = None
    metric_name: str | None = None
    metric_goal: str | None = None
    metrics: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = METRIC_LINE_RE.match(line)
        if not match:
            continue
        key, raw = match.groups()
        if key == "metric_name":
            metric_name = raw
            continue
        if key == "metric_goal":
            metric_goal = raw
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if not math.isfinite(value):
            raise WorkflowError(f"non-finite metric in run output: {key}={raw}")
        metrics[key] = value
        if key == "primary_metric":
            primary = value
    if primary is None:
        raise WorkflowError("run completed without a finite `primary_metric:` line")
    return primary, metric_name, metric_goal, metrics


def _incumbent(manifests: Sequence[Mapping[str, Any]], track: str) -> Mapping[str, Any] | None:
    keeps = [
        m
        for m in manifests
        if m.get("track") == track
        and m.get("disposition") == "keep"
        and m.get("evaluation_kind", "development") == "development"
    ]
    return keeps[-1] if keeps else None


def _guardrails_pass(
    guardrails: Mapping[str, Any] | list[Any],
    metrics: Mapping[str, float],
    incumbent: Mapping[str, Any] | None,
) -> tuple[bool, list[str]]:
    entries, failures = _guardrail_entries(guardrails)
    old_metrics = incumbent.get("metrics", {}) if incumbent else {}
    for name, spec in entries:
        value = metrics.get(name)
        if value is None:
            failures.append(
                f"guardrail metric {name!r} missing from the printed block — "
                f"print it from train.py via evaluate*(..., extra={{{name!r}: ...}})"
            )
            continue
        if "min" in spec and value < float(spec["min"]):
            failures.append(f"{name}={value} < min {spec['min']}")
        if "max" in spec and value > float(spec["max"]):
            failures.append(f"{name}={value} > max {spec['max']}")
        if "maximum_degradation" in spec and name in old_metrics:
            goal = spec.get("goal", "higher")
            degradation = (old_metrics[name] - value) if goal == "higher" else (value - old_metrics[name])
            if degradation > float(spec["maximum_degradation"]):
                failures.append(
                    f"{name} degradation {degradation:.12g} > {spec['maximum_degradation']}"
                )
    return not failures, failures


def choose_disposition(
    *,
    primary_metric: float,
    track_spec: Mapping[str, Any],
    metrics: Mapping[str, float],
    incumbent: Mapping[str, Any] | None,
    final_test: bool,
) -> tuple[str, str]:
    if final_test:
        return "discard", "sealed final-test evidence; excluded from the adaptive frontier"
    guard_ok, guard_failures = _guardrails_pass(track_spec.get("guardrails", {}), metrics, incumbent)
    if not guard_ok:
        return "discard", "guardrails failed: " + "; ".join(guard_failures)
    if incumbent is None:
        return "keep", "first valid result on this track"
    old = float(incumbent["primary_metric"])
    metric = track_spec["metric"]
    delta = float(metric.get("minimum_delta", 0))
    improved = primary_metric >= old + delta if metric["goal"] == "higher" else primary_metric <= old - delta
    if improved:
        return "keep", f"frontier improvement over {old:.12g} with minimum_delta={delta:.12g}"
    return "discard", f"did not improve track frontier {old:.12g} by minimum_delta={delta:.12g}"


def track_headroom(
    incumbent_score: float | None,
    *,
    ideal: float,
    minimum_delta: float,
    goal: str,
) -> float | None:
    """Distance from the incumbent to the metric's ideal, in minimum_delta units.

    ``h < 1`` means no keep is arithmetically possible on this frontier: not
    even a perfect score clears ``minimum_delta`` (the study-07 lesson —
    anchor Brier 0.026744 against delta 0.033 put the keep bar below zero).
    ``h >= 1`` says only that a keep is not arithmetically excluded, never
    that one is plausible: the attainable ceiling may sit well short of the
    ideal (irreducible Bayes risk — study 08 stood at h = 1.015 and twenty-one
    challengers produced zero keeps). Signed on purpose: an incumbent past the
    declared ideal reports h <= 0 (a mis-declared bound reads as infeasible,
    never as spare room).
    """
    if incumbent_score is None or minimum_delta <= 0:
        return None
    distance = (
        (incumbent_score - ideal) if goal == "lower" else (ideal - incumbent_score)
    )
    return distance / minimum_delta


def _headroom_context(
    track_spec: Mapping[str, Any],
    incumbent: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve (h, posture, numbers) for a track, or None when not armed."""
    metric = track_spec["metric"]
    bound = metric.get("bound")
    if not isinstance(bound, Mapping) or incumbent is None:
        return None
    try:
        ideal = float(bound.get("ideal"))
        minimum_delta = float(metric.get("minimum_delta", 0))
    except (TypeError, ValueError):
        return None
    h = track_headroom(
        float(incumbent["primary_metric"]),
        ideal=ideal,
        minimum_delta=minimum_delta,
        goal=str(metric.get("goal")),
    )
    if h is None:
        return None
    return {
        "h": h,
        "ideal": ideal,
        "minimum_delta": minimum_delta,
        "incumbent": float(incumbent["primary_metric"]),
        "posture": str(bound.get("on_infeasible", "ack")),
    }


def _headroom_ack(state: Mapping[str, Any], track: str) -> Mapping[str, Any] | None:
    entry = state.get("headroom", {})
    entry = entry.get(track) if isinstance(entry, Mapping) else None
    if isinstance(entry, Mapping) and entry.get("acknowledged_at"):
        return entry
    return None


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


def _enforce_headroom(
    state: Mapping[str, Any],
    track_spec: Mapping[str, Any],
    track: str,
    incumbent: Mapping[str, Any] | None,
    *,
    echo: bool,
) -> None:
    """Development-run gate on a keep-infeasible frontier (posture-controlled).

    Sealed final tests are exempt by construction (the caller gates on
    ``not final_test``): confirmation evidence is not a frontier attempt.
    """
    context = _headroom_context(track_spec, incumbent)
    if context is None or context["h"] >= 1:
        return
    detail = (
        f"track {track!r}: headroom ({context['incumbent']:.6g} - {context['ideal']:g})"
        f" / {context['minimum_delta']:.6g} = {context['h']:.3f} < 1 — no keep is "
        "arithmetically possible on this frontier (not even a perfect score clears "
        "minimum_delta)"
    )
    posture = context["posture"]
    if posture == "block":
        raise WorkflowError(
            detail
            + "; on_infeasible: block — re-scope the contract (minimum_delta, "
            "estimand, or data) before further transactions"
        )
    ack = _headroom_ack(state, track)
    if posture == "ack" and not ack:
        raise WorkflowError(
            detail
            + "; register awareness first: klein headroom ack --track "
            + str(track)
            + ' --acknowledged-by <you> --note "re-scope: ... | run-anyway: '
            '<pre-committed door-closed sentence>"'
        )
    if echo:
        suffix = (
            f"; acknowledged by {ack.get('acknowledged_by')}"
            if ack
            else "; on_infeasible: warn"
        )
        print(f"[headroom] {detail}{suffix}")


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


def _git_commit(repo: Path, message: str, *, allow_empty: bool = False, amend: bool = False) -> str:
    args = ["-c", "user.name=Klein Workflow", "-c", "user.email=klein@localhost", "commit", "-q"]
    if amend:
        args.extend(["--amend", "--no-edit"])
    else:
        if allow_empty:
            args.append("--allow-empty")
        args.extend(["-m", message])
    _git(repo, args)
    return _git(repo, ["rev-parse", "HEAD"]).stdout.strip()


def _relative(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo).as_posix()
    except ValueError as exc:
        raise WorkflowError(f"path is outside git repository: {path}") from exc


#: Study files a CLI verb may (re)write outside a run transaction: contract and
#: narrative docs, machine state, regenerable derived views, and sweep sidecars
#: (measurement evidence the next state commit must file). Never train.py —
#: committing it here would silently move run-one's restore anchor.
_STATE_WRITE_PATHS = (
    "study.yaml",
    "playbook.md",
    "study_state.json",
    "events.jsonl",
    "research_plan.md",
    "program.md",
    "data_card.md",
    "method_card.md",
    "findings.md",
    "results_summary.md",
    "progress.svg",
    "figures",
    "sweeps",
)


def _commit_state_writes(study_dir: Path, message: str) -> str | None:
    """Commit the state/derived files a CLI verb just wrote.

    The loop contract requires a clean tree at ``run-one``; the receipts the CLI
    itself generates must therefore be filed by the CLI, not hand-committed by
    the operator. No-op outside a git repository (unit fixtures scaffold studies
    in bare temp dirs) and when nothing actually changed.
    """
    probe = _git(study_dir, ["rev-parse", "--show-toplevel"], check=False)
    if probe.returncode:
        return None
    repo = Path(probe.stdout.strip()).resolve()
    existing = [
        _relative(repo, study_dir / name)
        for name in _STATE_WRITE_PATHS
        if (study_dir / name).exists()
    ]
    if not existing:
        return None
    _git(repo, ["add", "--", *existing])
    if _git(repo, ["diff", "--cached", "--quiet"], check=False).returncode == 0:
        return None
    return _git_commit(repo, message)


def _stage_evidence(repo: Path, study_dir: Path, manifest: Mapping[str, Any]) -> None:
    core = [
        study_dir / "study_state.json",
        study_dir / "events.jsonl",
        study_dir / "results.tsv",
        study_dir / "playbook.md",
        study_dir / "runs" / str(manifest["experiment"]) / "manifest.json",
        study_dir / "runs" / str(manifest["experiment"]) / "run.log",
    ]
    for rel, meta in manifest.get("artifacts", {}).items():
        if meta.get("committed"):
            core.append(study_dir / rel)
    existing = [_relative(repo, p) for p in core if p.exists()]
    if existing:
        _git(repo, ["add", "-f", "--", *existing])


def _complete_evidence_transaction(
    repo: Path,
    study_dir: Path,
    manifest: dict[str, Any],
    *,
    restored_train: bool,
    recovery: bool = False,
) -> str:
    run_id = str(manifest["experiment"])
    derive_results(study_dir)
    if restored_train:
        train_rel = _relative(repo, study_dir / "train.py")
        _git(repo, ["add", "--", train_rel])
    _stage_evidence(repo, study_dir, manifest)
    first_commit = _git_commit(
        repo,
        f"evidence {run_id}: {manifest['disposition']}",
        allow_empty=False,
    )
    manifest["transaction"] = {
        "status": "complete",
        "committed_at": utc_now(),
        "evidence_commit": first_commit,
        "recovered": recovery,
    }
    atomic_write_json(study_dir / "runs" / run_id / "manifest.json", manifest)
    append_event(
        study_dir,
        "transaction_recovered" if recovery else "transaction_committed",
        experiment=run_id,
        disposition=manifest["disposition"],
        evidence_commit=first_commit,
    )
    _stage_evidence(repo, study_dir, manifest)
    return _git_commit(repo, f"transaction {run_id}: finalize evidence")


def _assert_run_worktree(repo: Path, study_dir: Path) -> None:
    status = _git(repo, ["status", "--porcelain", "--untracked-files=all"]).stdout.splitlines()
    train_rel = _relative(repo, study_dir / "train.py")
    # The lock is ephemeral state; a foreign repo has no .gitignore for it, so
    # it must be exempt here rather than rely on ignore rules. Derived views
    # (summary, progress, figures) are regenerable at any time and are swept
    # into the next state commit by a gate record — they never gate a run.
    lock_rel = _relative(repo, study_dir / ".klein.lock")
    playbook_rel = _relative(repo, study_dir / "playbook.md")
    summary_rel = _relative(repo, study_dir / "results_summary.md")
    progress_rel = _relative(repo, study_dir / "progress.svg")
    figures_prefix = _relative(repo, study_dir / "figures") + "/"
    allowed = {train_rel, lock_rel, playbook_rel, summary_rel, progress_rel}
    bad: list[str] = []
    for line in status:
        path = line[3:].split(" -> ")[-1]
        if path not in allowed and not path.startswith(figures_prefix):
            bad.append(line)
    if bad:
        raise WorkflowError(
            "run-one requires a clean tree except for train.py and derived views; found: "
            + ", ".join(bad)
            + " — commit these first (gate records, finalize, and recover file their own "
            "state writes automatically; for manual edits: git add <files> && git commit)"
        )


def _phase_spec(contract: Mapping[str, Any], phase_id: str) -> Mapping[str, Any]:
    for phase in contract.get("phases", []):
        if isinstance(phase, Mapping) and str(phase.get("id")) == phase_id:
            return phase
    raise WorkflowError(f"current phase {phase_id!r} is not configured")


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

