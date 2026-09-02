"""The study contract: study.yaml loading, normalization, and validation.

Extracted verbatim from :mod:`kleinlib.workflow`. Everything here reads the
declared contract — the schema version, the track/metric/guardrail grammar, the
noise-floor block, the split policy and its fingerprint, the phase ladder, and
the gate artifacts each gate record must hash. No git, no state, no I/O beyond
reading ``study.yaml`` and the prepared-data path it names.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from .errors import WorkflowError
from .primitives import canonical_json, sha256_bytes

__all__ = [
    "GATE_ARTIFACTS",
    "IDENTIFIER_RE",
    "PLACEHOLDER_RE",
    "SCHEMA_VERSION",
    "STUDY_ID_RE",
    "VALID_DISPOSITIONS",
    "VALID_GOALS",
    "load_contract",
    "normalize_tracks",
    "prepared_data_path",
    "resolve_study",
    "schema_version",
    "split_fingerprint",
    "validate_contract",
]

SCHEMA_VERSION = 2
STUDY_ID_RE = re.compile(r"^\d{2}-[a-z0-9][a-z0-9-]*$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")

VALID_GOALS = frozenset({"higher", "lower"})
VALID_DISPOSITIONS = frozenset({"keep", "discard", "crash"})

GATE_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "consult": ("study.yaml", "research_plan.md", "program.md"),
    "data": ("data_card.md",),
    "method": ("method_card.md",),
}


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



def _phase_ids(contract: Mapping[str, Any]) -> list[str]:
    phases = contract.get("phases", [])
    return [str(p["id"]) for p in phases if isinstance(p, Mapping) and "id" in p]



def _phase_spec(contract: Mapping[str, Any], phase_id: str) -> Mapping[str, Any]:
    for phase in contract.get("phases", []):
        if isinstance(phase, Mapping) and str(phase.get("id")) == phase_id:
            return phase
    raise WorkflowError(f"current phase {phase_id!r} is not configured")
