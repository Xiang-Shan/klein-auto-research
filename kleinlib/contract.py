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
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .errors import WorkflowError
from .primitives import canonical_json, sha256_bytes

__all__ = [
    "CONFIRMATION_DEFAULTS",
    "ENTRYPOINT_BY_KIND",
    "GATE_ARTIFACTS",
    "IDENTIFIER_RE",
    "KNOWN_KINDS",
    "MODELING_GATES",
    "PLACEHOLDER_RE",
    "PREDICTION_ID_RE",
    "SCHEMA_VERSION",
    "SOURCE_TAG_RE",
    "STUDY_ID_RE",
    "SUPPORTED_SCHEMA_VERSIONS",
    "VALID_CONFIRMATION",
    "VALID_DISPOSITIONS",
    "VALID_EXACTNESS",
    "VALID_GOALS",
    "VALID_TRACK_MODES",
    "confirmation_require",
    "entrypoint_spec",
    "load_contract",
    "mutable_surface",
    "normalize_tracks",
    "prepared_data_path",
    "registered_predictions",
    "resolve_study",
    "schema_version",
    "split_fingerprint",
    "study_kind",
    "task_family",
    "track_kind",
    "validate_contract",
]

SCHEMA_VERSION = 2

#: Both rule sets the engine enforces.  ``schema_version`` SELECTS one; a
#: schema-2 study is validated by exactly the checks it was notarized under and
#: never retro-fails, and every schema-3 addition lives behind ``version >= 3``.
SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({2, 3})

STUDY_ID_RE = re.compile(r"^\d{2}-[a-z0-9][a-z0-9-]*$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")
PREDICTION_ID_RE = re.compile(r"^P\d+$")

#: The eight source schemes ``data.source`` may name.  Only the SHAPE is checked
#: here: resolution (and the offline / cache / pin machinery behind it) belongs
#: to ``kleinlib.sources`` and ``references/data-sources.md``.
SOURCE_TAG_RE = re.compile(
    r"^(csv|parquet|synthetic|bundled|hub|sklearn|openml|url):\s*(?P<rest>\S.*)$"
)

#: The schemes whose bytes can change under you — those need ``data.sha256``.
PINNED_SOURCE_SCHEMES: frozenset[str] = frozenset({"openml", "url"})

VALID_GOALS = frozenset({"higher", "lower"})

#: What one run transaction may conclude.  ``keep``/``discard`` belong to a
#: frontier track; ``measured`` to a registered one (schema 3,
#: ``references/registered-mode.md``) — a cell of a pre-registered measurement
#: program has nothing to beat, so it is neither kept nor discarded; ``crash``
#: belongs to both.
VALID_DISPOSITIONS = frozenset({"keep", "discard", "measured", "crash"})

#: The seven question shapes (``references/inquiry-model.md``).
KNOWN_KINDS: tuple[str, ...] = (
    "predict",
    "estimate",
    "test",
    "simulate",
    "replicate",
    "discover",
    "optimize",
)

VALID_TRACK_MODES: frozenset[str] = frozenset({"frontier", "registered"})
VALID_EXACTNESS: frozenset[str] = frozenset({"exact", "stochastic"})
VALID_CONFIRMATION: frozenset[str] = frozenset({"sealed", "replicate", "verify"})

#: What ``confirmation.require`` means when the contract leaves it out, per the
#: kind table in ``references/inquiry-model.md``.  ``discover`` closes nothing:
#: a discovery is a hypothesis, and its promotion is a follow-up ``test`` study.
CONFIRMATION_DEFAULTS: dict[str, tuple[str, ...]] = {
    "predict": ("sealed",),
    "estimate": ("sealed",),
    "test": ("sealed",),
    "simulate": ("sealed",),
    "replicate": ("sealed",),
    "discover": (),
    "optimize": ("verify",),
}

#: The mutable surface a scaffold writes for each kind.  Normative text says
#: "the entrypoint"; ``train.py`` is only the ``predict`` default (a Hubble
#: regression is not "trained").
ENTRYPOINT_BY_KIND: dict[str, str] = {
    "predict": "train.py",
    "estimate": "analyze.py",
    "test": "analyze.py",
    "replicate": "analyze.py",
    "discover": "analyze.py",
    "simulate": "simulate.py",
    "optimize": "search.py",
}

#: Every recordable gate and the artifact(s) it hashes.  ``referee`` is Gate 3
#: (``references/referee-protocol.md``) and sits AFTER synthesize, so it is not
#: one of the gates a run is blocked on — see :data:`MODELING_GATES`.
GATE_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "consult": ("study.yaml", "research_plan.md", "program.md"),
    "data": ("data_card.md",),
    "method": ("method_card.md",),
    "referee": ("referee_report.md",),
}

#: The gates that must be recorded or overridden BEFORE any modeling: the
#: hard-block rule of ``AGENTS.md``.  ``klein run-one``, ``preflight``/``verify``
#: and ``initial_state`` all read this list, never :data:`GATE_ARTIFACTS` — a
#: study cannot be refereed before it has run, and a schema-2 study never has a
#: referee gate at all.
MODELING_GATES: tuple[str, ...] = ("consult", "data", "method")


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
    schema_3 = contract.get("schema_version", 1) not in (1, 2)
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
        if schema_3:
            # Schema 3 only: a track that does not say otherwise climbs a
            # frontier, exactly as every schema-2 track always did.  Setting
            # the key on a schema-2 contract would change what schema-2 code
            # sees, so it is guarded.
            spec.setdefault("mode", "frontier")
        output[track] = spec
    return output


def study_kind(contract: Mapping[str, Any]) -> str | None:
    """The study-level ``kind``, or None when the contract does not type itself."""
    kind = contract.get("kind")
    return kind if isinstance(kind, str) and kind.strip() else None


def track_kind(contract: Mapping[str, Any], track_spec: Mapping[str, Any]) -> str | None:
    """A track's kind: its own override, else the study's.

    One study may carry two lanes — study 09 ran a registered test beside a
    known-truth simulation — so the override is per track, not per study.
    """
    kind = track_spec.get("kind")
    if isinstance(kind, str) and kind.strip():
        return kind
    return study_kind(contract)


def task_family(contract: Mapping[str, Any]) -> str:
    """The METRIC family ``task_type`` names, with ``simulation`` -> ``scalar``.

    ``task_type`` says which evaluator shape prints the block; the INQUIRY's
    shape is ``kind``.  Schema 3 spells the scalar family ``scalar`` and keeps
    ``simulation`` as a readable alias so no schema-2 contract has to change.
    """
    task = contract.get("task_type")
    return "scalar" if task in {"simulation", "scalar"} else str(task)


def mutable_surface(contract: Mapping[str, Any]) -> tuple[str, ...]:
    """The study-relative files ONE candidate may change.

    Schema 2 has exactly one, by construction and forever: ``train.py``.  Schema
    3 declares it (``entrypoint.mutable``) because the entrypoint is named by
    kind — a Hubble regression is not "trained" — and a study may keep its
    per-experiment surface in more than one file.  Everything else (``lib/``,
    ``prepare.py``, the declared verifier) is outside it by definition.
    """
    if schema_version(contract) < 3:
        return ("train.py",)
    mutable = entrypoint_spec(contract)["mutable"]
    return tuple(str(item) for item in mutable) or ("train.py",)


def entrypoint_spec(contract: Mapping[str, Any]) -> dict[str, Any]:
    """The declared entrypoint, defaulted to the schema-2 ``train.py`` surface."""
    raw = contract.get("entrypoint")
    if not isinstance(raw, Mapping):
        return {"command": ["uv", "run", "--locked", "python", "-u", "train.py"], "mutable": ["train.py"]}
    command = raw.get("command")
    mutable = raw.get("mutable")
    return {
        "command": list(command) if isinstance(command, Sequence) and not isinstance(command, str) else [],
        "mutable": list(mutable) if isinstance(mutable, Sequence) and not isinstance(mutable, str) else [],
    }


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
    """Every problem in a study contract, under the rule set its version selects.

    ``schema_version`` is the switch: 2 gets exactly the checks it was notarized
    under (frozen — the shipped studies must keep verifying forever), 3 gets
    those plus :func:`_schema3_problems`.
    """
    try:
        version = schema_version(contract)
    except WorkflowError as exc:
        return [str(exc)]
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        return [
            f"schema_version must be {SCHEMA_VERSION} or 3 "
            f"(got {version}; version-1 studies are readable at tag v1.3.0)"
        ]
    problems = _common_problems(contract, study_dir, version)
    if version >= 3:
        problems.extend(_schema3_problems(contract, study_dir))
    return problems


def _common_problems(
    contract: Mapping[str, Any], study_dir: Path | None, version: int
) -> list[str]:
    from .eval import get_metric_spec

    problems: list[str] = []
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
    # ``task_type`` names the METRIC family, not the inquiry — schema 3 spells
    # the scalar family ``scalar`` and keeps ``simulation`` as a readable alias
    # (the inquiry's shape is ``kind``).  Schema 2 knows only the three names it
    # was notarized with.
    task_names = {"classification", "regression", "simulation"}
    if version >= 3:
        task_names = task_names | {"scalar"}
    if contract.get("task_type") not in task_names:
        problems.append(
            "task_type must be classification, regression, or simulation"
            + (" (or scalar, its schema-3 spelling)" if version >= 3 else "")
        )
    # A schema-2 contract that misspells task_type as ``scalar`` keeps failing
    # exactly as it did; only a schema-3 contract earns the scalar family here.
    scalar_family = contract.get("task_type") == "simulation" or (
        version >= 3 and contract.get("task_type") == "scalar"
    )
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
            try:
                get_metric_spec(
                    metric_name,
                    goal=str(metric_goal),
                    task="scalar" if scalar_family else str(contract.get("task_type")),
                    allow_custom=scalar_family,
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
        allowed_kinds = {"stratified", "random", "group", "time"}
        if scalar_family:
            allowed_kinds = allowed_kinds | {"none"}
        if split_kind not in allowed_kinds:
            problems.append(
                "data.split.kind must be stratified, random, group, or time"
                + (" (or none)" if scalar_family else "")
            )
        if split_kind == "none" and not scalar_family:
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


# ---------------------------------------------------------------------------
# Schema 3 — the typed inquiry (references/inquiry-model.md)
# ---------------------------------------------------------------------------


def _repo_root_hint(study_dir: Path) -> Path:
    """The repository root a ``profile_doc:`` path is relative to.

    Filesystem-only (this module owns no git): walk up for the marker a Klein
    checkout always has, and fall back to ``studies/<slug>``'s grandparent.
    """
    for candidate in (study_dir, *study_dir.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").is_file():
            return candidate
    return study_dir.parent.parent if len(study_dir.parents) >= 2 else study_dir


def _relative_study_path_problem(raw: Any, label: str) -> str | None:
    """None when *raw* is a safe study-relative POSIX path, else the problem."""
    if not isinstance(raw, str) or not raw.strip():
        return f"{label} must be a non-empty study-relative POSIX path"
    if raw != raw.strip():
        return f"{label} must not be padded with whitespace: {raw!r}"
    if "\\" in raw:
        return f"{label} must use POSIX separators: {raw!r}"
    path = PurePosixPath(raw)
    if path.is_absolute() or raw.startswith("/") or ".." in path.parts:
        return f"{label} must stay inside the study (no absolute path, no '..'): {raw!r}"
    return None


def _script_paths(command: Sequence[Any]) -> list[str]:
    """The command elements that name a file in the study (not flags or words)."""
    scripts: list[str] = []
    for item in command:
        if not isinstance(item, str) or item.startswith("-"):
            continue
        if item.endswith((".py", ".sh")) or "/" in item:
            scripts.append(item)
    return scripts


def _entrypoint_problems(contract: Mapping[str, Any], study_dir: Path | None) -> list[str]:
    problems: list[str] = []
    raw = contract.get("entrypoint")
    if not isinstance(raw, Mapping):
        return ["entrypoint is required: {command: [...], mutable: [...]}"]
    unknown = set(raw) - {"command", "mutable"}
    if unknown:
        problems.append(f"entrypoint has unknown keys: {sorted(unknown)}")
    command = raw.get("command")
    if (
        not isinstance(command, Sequence)
        or isinstance(command, str)
        or not command
        or not all(isinstance(item, str) and item.strip() for item in command)
    ):
        problems.append("entrypoint.command must be a non-empty list of strings")
    else:
        for script in _script_paths(command):
            problem = _relative_study_path_problem(script, "entrypoint.command")
            if problem:
                problems.append(problem)
    mutable = raw.get("mutable")
    if (
        not isinstance(mutable, Sequence)
        or isinstance(mutable, str)
        or not mutable
    ):
        problems.append(
            "entrypoint.mutable must be a non-empty list — name the per-experiment surface"
        )
    else:
        for item in mutable:
            problem = _relative_study_path_problem(item, "entrypoint.mutable")
            if problem:
                problems.append(problem)
            elif study_dir is not None and not (study_dir / item).is_file():
                problems.append(f"entrypoint.mutable names a missing file: {item}")
    return problems


def _verifier_problems(
    label: str, verifier: Any, mutable: set[str], study_dir: Path | None
) -> list[str]:
    """Shape-check one declared verifier — the checker is never the searcher."""
    if not isinstance(verifier, Mapping):
        return [f"{label}: verifier must be a mapping"]
    problems: list[str] = []
    unknown = set(verifier) - {"command", "tolerance", "artifact_key"}
    if unknown:
        problems.append(f"{label}: verifier has unknown keys: {sorted(unknown)}")
    command = verifier.get("command")
    if (
        not isinstance(command, Sequence)
        or isinstance(command, str)
        or not command
        or not all(isinstance(item, str) and item.strip() for item in command)
    ):
        problems.append(f"{label}: verifier.command must be a non-empty list of strings")
    else:
        scripts = _script_paths(command)
        if not scripts:
            problems.append(
                f"{label}: verifier.command must name the checker script "
                "(a study-relative .py or .sh path)"
            )
        for script in scripts:
            problem = _relative_study_path_problem(script, f"{label}: verifier.command")
            if problem:
                problems.append(problem)
                continue
            if script in mutable:
                problems.append(
                    f"{label}: verifier.command names {script!r}, which is in "
                    "entrypoint.mutable — the checker is never the searcher"
                )
            if study_dir is not None and not (study_dir / script).is_file():
                problems.append(f"{label}: verifier script does not exist: {script}")
    tolerance = verifier.get("tolerance")
    try:
        value = float(tolerance)
        if isinstance(tolerance, bool) or not math.isfinite(value) or value < 0:
            raise ValueError
    except (TypeError, ValueError):
        problems.append(f"{label}: verifier.tolerance must be finite and >= 0")
    artifact_key = verifier.get("artifact_key")
    if not isinstance(artifact_key, str) or not IDENTIFIER_RE.fullmatch(artifact_key or ""):
        problems.append(
            f"{label}: verifier.artifact_key must name the printed key that carries "
            "the artifact path"
        )
    return problems


def _incumbent_external_problems(label: str, block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        return [f"{label}: metric.incumbent_external must be a mapping"]
    problems: list[str] = []
    unknown = set(block) - {"value", "source", "verified_on"}
    if unknown:
        problems.append(f"{label}: metric.incumbent_external has unknown keys: {sorted(unknown)}")
    try:
        value = float(block.get("value"))
        if isinstance(block.get("value"), bool) or not math.isfinite(value):
            raise ValueError
    except (TypeError, ValueError):
        problems.append(f"{label}: metric.incumbent_external.value must be a finite number")
    for field in ("source", "verified_on"):
        raw = block.get(field)
        if not isinstance(raw, str) or not raw.strip():
            problems.append(
                f"{label}: metric.incumbent_external.{field} is required — a literature "
                "incumbent without a citation and a date is a rumour"
            )
    return problems


def _predictions_problems(contract: Mapping[str, Any]) -> list[str]:
    from .decision import validate_rule

    problems: list[str] = []
    predictions = contract.get("predictions")
    legacy = contract.get("predictions_to_falsify")
    if predictions is not None and legacy is not None:
        problems.append(
            "give predictions: or predictions_to_falsify:, never both — the alias "
            "normalizes to manual predictions and two sources cannot both be the register"
        )
    if predictions is None:
        return problems
    if not isinstance(predictions, list) or not predictions:
        return problems + ["predictions must be a non-empty list"]
    tracks = set(normalize_tracks(contract))
    seen: set[str] = set()
    for index, entry in enumerate(predictions):
        label = f"prediction {index}"
        if not isinstance(entry, Mapping):
            problems.append(f"{label}: must be a mapping")
            continue
        raw_id = entry.get("id")
        if not isinstance(raw_id, str) or not PREDICTION_ID_RE.fullmatch(raw_id):
            problems.append(f"{label}: id is required and must match P<number>")
        else:
            label = f"prediction {raw_id}"
            if raw_id in seen:
                problems.append(f"{label}: duplicate prediction id")
            seen.add(raw_id)
        unknown = set(entry) - {
            "id",
            "track",
            "statement",
            "rule",
            "manual",
            "inconclusive_if",
        }
        if unknown:
            problems.append(f"{label}: unknown keys {sorted(unknown)}")
        statement = entry.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            problems.append(f"{label}: statement is required")
        track = entry.get("track")
        if track is not None:
            if not isinstance(track, str) or (tracks and track not in tracks):
                problems.append(f"{label}: track {track!r} is not a declared track")
        has_rule = entry.get("rule") is not None
        manual = entry.get("manual")
        if manual is not None and not isinstance(manual, bool):
            problems.append(f"{label}: manual must be true or false")
        if has_rule and manual is True:
            problems.append(
                f"{label}: give a rule OR manual: true — a prediction the machine can "
                "decide is never adjudicated by hand"
            )
        elif not has_rule and manual is not True:
            problems.append(
                f"{label}: exactly one of rule or manual: true is required "
                "('tuning helps' is not a prediction)"
            )
        if has_rule:
            problems.extend(validate_rule(entry.get("rule"), where=f"{label}: rule"))
        inconclusive = entry.get("inconclusive_if")
        if inconclusive is not None:
            problems.extend(
                validate_rule(inconclusive, where=f"{label}: inconclusive_if")
                if isinstance(inconclusive, Mapping)
                else (
                    []
                    if isinstance(inconclusive, str) and inconclusive.strip()
                    else [f"{label}: inconclusive_if must be a rule or a non-empty sentence"]
                )
            )
    return problems


def _stop_problems(block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        return ["stop must be a mapping"]
    problems: list[str] = []
    unknown = set(block) - {"max_consecutive_discards", "scope"}
    if unknown:
        problems.append(f"stop has unknown keys: {sorted(unknown)}")
    raw = block.get("max_consecutive_discards")
    try:
        count = int(raw)
        if isinstance(raw, bool) or count <= 0 or float(raw) != count:
            raise ValueError
    except (TypeError, ValueError):
        problems.append("stop.max_consecutive_discards must be a positive integer")
    scope = block.get("scope", "track")
    if scope not in {"track", "study", "phase"}:
        problems.append("stop.scope must be track, study, or phase")
    return problems


def _materiality_problems(block: Any) -> list[str]:
    """Materiality is priced or absent — never inferred from a p-value."""
    if not isinstance(block, Mapping):
        return ["materiality must be a mapping"]
    problems: list[str] = []
    required = ("currency", "unit", "threshold", "priced_by", "priced_on", "basis", "applies_to")
    unknown = set(block) - set(required)
    if unknown:
        problems.append(f"materiality has unknown keys: {sorted(unknown)}")
    for field in required:
        if field == "threshold":
            continue
        raw = block.get(field)
        if not isinstance(raw, str) or not raw.strip():
            problems.append(f"materiality.{field} is required")
    raw_threshold = block.get("threshold")
    try:
        threshold = float(raw_threshold)
        if isinstance(raw_threshold, bool) or not math.isfinite(threshold):
            raise ValueError
    except (TypeError, ValueError):
        problems.append("materiality.threshold must be a finite number")
    basis = block.get("basis")
    if isinstance(basis, str) and 0 < len(basis.strip()) < 40:
        problems.append(
            "materiality.basis must be at least 40 characters — say what was priced, "
            "on what data, under which assumptions"
        )
    return problems


def _data_source_problems(data: Mapping[str, Any]) -> list[str]:
    """SHAPE only — resolution, caching and the offline rule live in sources.

    The scheme vocabulary has ONE owner, :func:`kleinlib.sources.parse_source`
    (``SourceKind``); :data:`SOURCE_TAG_RE` stays as the cheap pre-check that
    keeps the common failure ("not a tag at all") a fast local message, and the
    parser then produces the scheme, so a scheme added to ``sources`` is
    accepted here without a second list to keep in step.
    """
    from .sources import parse_source

    problems: list[str] = []
    source = data.get("source")
    if not isinstance(source, str) or not source.strip():
        return ["data.source is required — name the source tag"]
    tag = source.strip()
    if SOURCE_TAG_RE.match(tag) is None:
        return [
            "data.source must be a source tag: csv: | parquet: | synthetic: | bundled: "
            f"| hub: | sklearn: | openml: | url: (got {source!r})"
        ]
    try:
        scheme = str(parse_source(tag).kind)
    except WorkflowError as exc:
        return [f"data.source: {exc}"]
    sha256 = data.get("sha256")
    pinned = isinstance(sha256, str) and re.fullmatch(r"[0-9a-f]{64}", sha256.strip()) is not None
    if scheme in PINNED_SOURCE_SCHEMES and not pinned:
        problems.append(
            f"data.sha256 (64 hex chars) is mandatory for a {scheme}: source — bytes that "
            "can change under you are pinned or they are not evidence"
        )
    elif sha256 is not None and not pinned:
        problems.append("data.sha256 must be 64 lowercase hex characters")
    return problems


def _schema3_problems(contract: Mapping[str, Any], study_dir: Path | None) -> list[str]:
    """Everything schema 3 adds on top of the frozen schema-2 rule set."""
    from .schema import KNOWN_MODALITIES, KNOWN_PROFILES

    problems: list[str] = []

    kind = contract.get("kind")
    if kind not in KNOWN_KINDS:
        problems.append(f"kind must be one of {list(KNOWN_KINDS)}")

    profile = contract.get("profile")
    profile_doc = contract.get("profile_doc")
    if profile is None and profile_doc is None:
        problems.append(
            f"profile must be one of {list(KNOWN_PROFILES)}, or profile_doc must name a "
            "repo-relative .md profile"
        )
    if profile is not None and profile not in KNOWN_PROFILES:
        problems.append(f"profile must be one of {list(KNOWN_PROFILES)} (got {profile!r})")
    if profile_doc is not None:
        if not isinstance(profile_doc, str) or not profile_doc.strip().endswith(".md"):
            problems.append("profile_doc must be a repo-relative path to a .md file")
        elif study_dir is not None:
            root = _repo_root_hint(study_dir)
            if not (root / profile_doc).is_file() and not (study_dir / profile_doc).is_file():
                problems.append(f"profile_doc does not exist: {profile_doc}")
    audience = contract.get("audience")
    if audience is not None and (not isinstance(audience, str) or not audience.strip()):
        problems.append("audience must be a non-empty sentence naming who reads this study")

    problems.extend(_entrypoint_problems(contract, study_dir))
    mutable = set(entrypoint_spec(contract)["mutable"])

    data = contract.get("data")
    if isinstance(data, Mapping):
        modality = data.get("modality")
        if modality not in KNOWN_MODALITIES:
            problems.append(f"data.modality is required and must be one of {list(KNOWN_MODALITIES)}")
        problems.extend(_data_source_problems(data))

    for name, spec in normalize_tracks(contract).items():
        label = f"track {name!r}"
        mode = spec.get("mode")
        if mode not in VALID_TRACK_MODES:
            problems.append(f"{label}: mode must be frontier or registered")
        override = spec.get("kind")
        if override is not None and override not in KNOWN_KINDS:
            problems.append(f"{label}: kind override must be one of {list(KNOWN_KINDS)}")
        this_kind = track_kind(contract, spec)

        verifier = spec.get("verifier")
        if verifier is not None:
            problems.extend(_verifier_problems(label, verifier, mutable, study_dir))
        elif this_kind == "optimize":
            problems.append(
                f"{label}: kind 'optimize' requires a declared verifier — the objective "
                "is computed by the checker, never reported by the search"
            )

        metric = spec.get("metric", {})
        if isinstance(metric, Mapping):
            exactness = metric.get("exactness", "stochastic")
            if exactness not in VALID_EXACTNESS:
                problems.append(f"{label}: metric.exactness must be exact or stochastic")
            elif exactness == "exact":
                note = metric.get("exactness_note")
                if not isinstance(note, str) or not note.strip():
                    problems.append(
                        f"{label}: metric.exactness 'exact' requires metric.exactness_note — "
                        "a measured floor is meaningless for a deterministic objective, so "
                        "say what the objective's resolution is instead"
                    )
            elif metric.get("exactness_note") is not None:
                problems.append(f"{label}: metric.exactness_note applies to exact metrics only")
            if metric.get("incumbent_external") is not None:
                problems.extend(
                    _incumbent_external_problems(label, metric.get("incumbent_external"))
                )
            if metric.get("fit_noise") is not None:
                problems.extend(
                    f"{label}: metric.fit_noise: {problem.removeprefix('metric.noise_floor')}"
                    for problem in _noise_floor_problems(
                        metric.get("fit_noise"), fit_noise=True
                    )
                )

    problems.extend(_predictions_problems(contract))

    if contract.get("stop") is not None:
        problems.extend(_stop_problems(contract.get("stop")))
    if contract.get("materiality") is not None:
        problems.extend(_materiality_problems(contract.get("materiality")))

    confirmation = contract.get("confirmation")
    if confirmation is not None:
        if not isinstance(confirmation, Mapping):
            problems.append("confirmation must be a mapping with a require: list")
        else:
            unknown = set(confirmation) - {"require"}
            if unknown:
                problems.append(f"confirmation has unknown keys: {sorted(unknown)}")
            require = confirmation.get("require", [])
            if not isinstance(require, list) or isinstance(require, str):
                problems.append("confirmation.require must be a list")
            else:
                bad = [item for item in require if item not in VALID_CONFIRMATION]
                if bad:
                    problems.append(
                        f"confirmation.require may only contain {sorted(VALID_CONFIRMATION)} "
                        f"(got {bad})"
                    )
    return problems


def registered_predictions(contract: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """``{P#: entry}`` for the contract's registered predictions, in order.

    The legacy readable alias ``predictions_to_falsify`` normalizes to manual
    predictions (``P1``, ``P2``, ...): they are still registered beliefs, they
    just cannot be adjudicated by arithmetic.
    """
    raw = contract.get("predictions")
    if isinstance(raw, list):
        return {
            str(entry["id"]): dict(entry)
            for entry in raw
            if isinstance(entry, Mapping) and isinstance(entry.get("id"), str)
        }
    legacy = contract.get("predictions_to_falsify")
    if not isinstance(legacy, list):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(legacy, start=1):
        if not isinstance(entry, Mapping):
            continue
        lever = str(entry.get("lever", "")).strip()
        delta = str(entry.get("predicted_delta", "")).strip()
        normalized[f"P{index}"] = {
            "id": f"P{index}",
            "statement": f"{lever}: {delta}".strip(": "),
            "manual": True,
        }
    return normalized


def confirmation_require(contract: Mapping[str, Any]) -> tuple[str, ...]:
    """What ``confirmed`` needs for this study — declared, else the kind default."""
    confirmation = contract.get("confirmation")
    if isinstance(confirmation, Mapping):
        require = confirmation.get("require")
        if isinstance(require, list):
            return tuple(str(item) for item in require)
    return CONFIRMATION_DEFAULTS.get(str(study_kind(contract)), ("sealed",))


def _noise_floor_problems(floor: Any, *, fit_noise: bool = False) -> list[str]:
    """Validate one measured-floor block.

    Both blocks have the same shape and differ in exactly one field: which
    estimand may appear in them.  ``noise_floor:`` carries a BAR estimand
    (``marginal-resplit`` / ``paired-comparison``); ``fit_noise:`` carries
    ``fit-noise`` and nothing else — that separation is the whole reason
    :func:`kleinlib.noise_floor.block_key` writes the two under different
    keys, and it is what stops a seed-only spread from being defended as a
    keep bar.  Messages keep the ``metric.noise_floor`` prefix the
    ``fit_noise`` caller rewrites, so a schema-2 study's wording is unchanged.
    """
    from .noise_floor import ALLOWED_KEYS, FIT_NOISE

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
    if fit_noise:
        if estimand is not None and estimand != FIT_NOISE:
            problems.append(
                f"metric.noise_floor.estimand must be {FIT_NOISE} in a fit_noise block — "
                "a bar estimand recorded there is the exact confusion the separate block "
                "exists to prevent"
            )
    elif estimand is not None and estimand not in {"marginal-resplit", "paired-comparison"}:
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
