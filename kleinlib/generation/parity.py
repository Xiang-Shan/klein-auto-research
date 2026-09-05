"""The ``parity`` capability — one registered vector comparison, decided once.

"The AI matched the expert" is the claim this capability exists to make hard.
Made loosely it is almost free: pick the metric that moved, quote the one that
did not, call a non-significant loss "no difference", and measure both pipelines
under whichever budget flatters the newer one.  Every one of those routes is
closed by an artifact locked before the evidence exists.

Four moves, in this order and no other:

1. **Lock** ``parity.yaml`` at CONSULT, before the consult gate.  It names the
   comparison track, the sampling unit, the dependence block, BOTH pipelines and
   their selection rules, the matched budget rule, and — the load-bearing part —
   every metric with its direction, estimand, units, a ``floor_ref`` saying
   where its measured floor ``δ`` will come from, a noninferiority margin ``ε``
   and a WRITTEN RATIONALE for that margin.  A margin without a rationale is
   refused: resolution is not a licence to widen a margin (R-INV-4).  The
   margins are set by someone who is not the roster's experimenter, and each
   metric names the registered prediction that will adjudicate it — whose rule
   must be exactly ``{key: L_<key>, op: ">=", value: -margin}``, so the notary
   decides the same inequality this module does.
2. **Bind** after METHOD: pin the scorer's hash, both pipelines' frozen
   snapshots, and every metric's MEASURED floor.  The bind must precede EVERY
   sealed access on EVERY track (deferral D-2): a study that spends a frontier
   seal before freezing the comparison cannot earn the parity outcome, and the
   registered admission rule below refuses ``--action sealed`` until the bind
   exists.
3. **Measure** in ONE sealed cell — an ordinary ``klein run-one --final-test
   --tests P…`` on the registered comparison track, whose entrypoint calls the
   study's ``lib/parity_score.py``.  The cell prints the whole metric table and
   pins ``tables/parity_units.tsv``, one row per sampling unit.
4. **Assess**: recompute ``d``, ``L`` and ``U`` from the pinned table and apply
   the decision rule.  ``generation verify`` recomputes the same numbers from
   the same bytes and FAILs on any disagreement.

**The decision rule** (plan §A.4; A3 §6; B §3).  With ``D_j = sign_j × (AI_j −
expert_j)`` and simultaneous bounds ``[L_j, U_j]``:

* **exceeds** — every ``L_j ≥ 0`` and some ``L_j ≥ δ_j``;
* **parity** — every ``L_j ≥ −ε_j`` (noninferiority, never equality);
* **refuted** — some ``U_j < −ε_j``;
* **inconclusive** — otherwise.

They are mutually exclusive by construction: ``U_j < −ε_j`` contradicts
``L_j ≥ −ε_j`` on that same ``j``.  An UNDEFINED metric — A4 §7's top-to-bottom
ratio on a zero-loss bottom decile — can never pass: the verdict is ``refuted``
when some other metric refutes and ``inconclusive`` otherwise, and it is never
quietly dropped from the conjunction.

**The by-δ rule is not parity.**  A4 §7's agreement check — every ``|d_j| ≤
δ_j`` — is computed and reported under its own name,
``agreement_within_floor``.  It is a statement about resolution, and selling it
as parity is exactly the "non-significance as equivalence" move the plan's N-4
rejects.

**What passing establishes.**  That on this population, at this sampling unit,
under this budget rule, these metrics did not fall below their preregistered
margins in one sealed evaluation.  Not that the AI pipeline is as good as the
expert in general, and not that the AI CAUSED the difference — a causal AI-value
claim needs a matched frozen-2.0 ablation arm; the contribution ledger
(:mod:`kleinlib.generation.contribution`) establishes recorded attribution and
outcomes, which is a different and smaller thing.

Registered, not wired in: this module exports one
:class:`~kleinlib.generation.registry.Capability`, and the spine finds it through
:data:`kleinlib.generation.capabilities.MODULES`.  It imports ``_plain``,
``joined``, ``latest``, ``roster_experimenter`` and ``same_actor`` from
:mod:`kleinlib.generation.expert` — the package's ledger-join, YAML-coercion and
roster helpers, which live in the first capability module that needed them.
``parity`` requires ``expertise`` (``CAPABILITY_DEPENDENCIES``), so that import
adds no edge the manifest does not already demand, and one implementation of
"who is the roster's experimenter" is better than two that drift.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import yaml

from ..contract import normalize_tracks, registered_predictions
from ..decision import OPERATOR_ALIASES
from ..errors import WorkflowError
from ..manifest import load_manifests
from ..primitives import canonical_json, sha256_bytes, sha256_file
from ..transaction import git_blob, relative
from . import stats
from .chronology import run_started_events
from .envelope import GENERATION_SCHEMA
from .expert import _plain, joined, latest, roster_experimenter, same_actor
from .ledger import read_events
from .registry import Capability
from .verify import Check

if TYPE_CHECKING:  # pragma: no cover - types only
    from .admission import Context
    from .registry import FamilyContext

__all__ = [
    "AGGREGATIONS",
    "ASSESS_TYPE",
    "BIND_TYPE",
    "CAPABILITY",
    "CAPABILITY_NAME",
    "DIRECTIONS",
    "FROZEN_LOCK_KEYS",
    "LOCK_TYPE",
    "PARITY_NAME",
    "UNCERTAINTY_METHOD",
    "UNDEFINED_HANDLING",
    "UNITS_TABLE",
    "VERDICTS",
    "bind_object",
    "build_assessment",
    "decide",
    "experimenter_of",
    "lock_object",
    "locks",
    "metric_keys",
    "metric_rows",
    "parity_family",
    "parity_path",
    "read_parity_file",
    "read_units",
    "sign_of",
    "validation_problems",
]

CAPABILITY_NAME = "parity"

#: The human artifact.  Study root, beside ``study.yaml``: the comparison's
#: criteria are meant to be READ by the reviewer who sets the margins.
PARITY_NAME = "parity.yaml"

#: The pinned per-unit table the sealed cell prints and ``assess`` recomputes
#: from.  Fixed by convention so a reader always knows where to look.
UNITS_TABLE = "tables/parity_units.tsv"

LOCK_TYPE = "parity_locked"
AMEND_TYPE = "parity_amended"
BIND_TYPE = "parity_bound"
ASSESS_TYPE = "parity_assessed"
LOCK_TYPES: tuple[str, ...] = (LOCK_TYPE, AMEND_TYPE)

DIRECTIONS: tuple[str, ...] = ("higher", "lower")

#: The four outcomes, in the order the rule tries them.  They are mutually
#: exclusive; the order is the literal reading of A3 §6, not a precedence.
VERDICTS: tuple[str, ...] = ("exceeds", "parity", "refuted", "inconclusive")

#: The only undefined-metric policy this version knows.  It is preregistered in
#: the lock rather than decided when the metric turns out to be undefined.
UNDEFINED_HANDLING: tuple[str, ...] = ("cannot_pass",)

#: The only aggregation this version knows.  A conjunction is what makes three
#: metrics describe ONE model on ONE population (A4 §7).
AGGREGATIONS: tuple[str, ...] = ("conjunction",)

UNCERTAINTY_METHOD = "block_bootstrap_maxt"

#: What an amendment may NOT change.  Everything here is a criterion the
#: evidence is measured against; moving one after the lock is re-registering.
FROZEN_LOCK_KEYS: tuple[str, ...] = (
    "comparison_track",
    "sampling_unit",
    "block_column",
    "aggregation",
    "uncertainty",
)

#: The per-metric fields an amendment may not change either.
FROZEN_METRIC_KEYS: tuple[str, ...] = (
    "key",
    "direction",
    "margin",
    "undefined_handling",
    "estimand",
)

_PIPELINES: tuple[str, ...] = ("ai", "expert")
_PIPELINE_FIELDS: tuple[str, ...] = ("name", "description", "owner", "selection_rule")


# --------------------------------------------------------------------------
# the file
# --------------------------------------------------------------------------


def parity_path(study_dir: Path) -> Path:
    return study_dir / PARITY_NAME


def read_parity_file(study_dir: Path) -> dict[str, Any]:
    path = parity_path(study_dir)
    if not path.is_file():
        raise WorkflowError(
            f"{PARITY_NAME} does not exist — author it first "
            "(`.claude/skills/klein/assets/parity-template.yaml`)"
        )
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"could not read {PARITY_NAME}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{PARITY_NAME} must contain a top-level mapping")
    return value


def metric_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("metrics")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def metric_keys(payload: Mapping[str, Any]) -> list[str]:
    return [str(row.get("key")) for row in metric_rows(payload)]


def sign_of(direction: Any) -> float:
    """``+1`` for ``higher``, ``−1`` for ``lower`` — positive always favours AI."""
    return 1.0 if str(direction) == "higher" else -1.0


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


def _text_problem(value: Any, label: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{label} is required"]
    return []


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(float(value)) else None


def validation_problems(
    payload: Mapping[str, Any],
    *,
    study: str,
    contract: Mapping[str, Any],
    experimenter: str | None,
    previous: Mapping[str, Any] | None = None,
) -> list[str]:
    """Everything wrong with an authored ``parity.yaml``, one line each."""
    problems: list[str] = []
    if payload.get("type") not in (None, "parity"):
        problems.append(f"type is {payload.get('type')!r}, expected 'parity'")
    declared_study = payload.get("study")
    if declared_study is not None and str(declared_study) != study:
        problems.append(f"study is {declared_study!r}, expected {study!r}")

    tracks = normalize_tracks(contract)
    track = payload.get("comparison_track")
    spec = tracks.get(str(track)) if isinstance(track, str) else None
    if spec is None:
        problems.append(
            f"comparison_track {track!r} is not declared in study.yaml "
            f"(declared: {', '.join(sorted(tracks)) or 'none'})"
        )
    elif str(spec.get("mode", "frontier")) != "registered":
        problems.append(
            f"comparison_track {track!r} is a {spec.get('mode', 'frontier')!r} track; the "
            "comparison is a registered cell, not a frontier candidate "
            "(`references/registered-mode.md`)"
        )

    problems.extend(_text_problem(payload.get("sampling_unit"), "sampling_unit"))
    if "block_column" not in payload:
        problems.append(
            "block_column is required (a column name, or null for iid sampling units) — "
            "the dependence structure is preregistered, not chosen when the bounds are seen"
        )
    elif payload.get("block_column") is not None and not isinstance(
        payload.get("block_column"), str
    ):
        problems.append("block_column must be a column name or null")
    problems.extend(_text_problem(payload.get("budget_rule"), "budget_rule"))

    pipelines = payload.get("pipelines")
    if not isinstance(pipelines, Mapping):
        problems.append("pipelines must name both 'ai' and 'expert'")
    else:
        for side in _PIPELINES:
            entry = pipelines.get(side)
            if not isinstance(entry, Mapping):
                problems.append(f"pipelines.{side} is required")
                continue
            for field in _PIPELINE_FIELDS:
                problems.extend(_text_problem(entry.get(field), f"pipelines.{side}.{field}"))

    problems.extend(_metrics_problems(payload))
    problems.extend(_uncertainty_problems(payload.get("uncertainty")))
    if payload.get("aggregation") not in AGGREGATIONS:
        problems.append(
            f"aggregation is {payload.get('aggregation')!r}; this version implements "
            + ", ".join(AGGREGATIONS)
        )

    scorer = payload.get("scorer")
    if not isinstance(scorer, Mapping) or not str(scorer.get("path") or "").strip():
        problems.append("scorer.path is required (the study-local scorer, e.g. lib/parity_score.py)")
    elif Path(str(scorer["path"])).is_absolute() or ".." in Path(str(scorer["path"])).parts:
        problems.append("scorer.path must be a study-relative path inside the study")

    problems.extend(_margins_set_by_problems(payload.get("margins_set_by"), experimenter))
    scoring = payload.get("scoring")
    if not isinstance(scoring, Mapping):
        problems.append("scoring must record masked and scorer_name (testimony, R-PAR-6)")
    else:
        if not isinstance(scoring.get("masked"), bool):
            problems.append("scoring.masked must be true or false (testimony, R-PAR-6)")
        problems.extend(_text_problem(scoring.get("scorer_name"), "scoring.scorer_name"))

    problems.extend(_prediction_problems(payload, contract))
    if "ablation_study" not in payload:
        problems.append(
            "ablation_study is required (a matched frozen-2.0 study id, or null) — a causal "
            "AI-value claim needs a matched ablation, and the field records that it has none"
        )
    elif payload.get("ablation_study") is not None and not isinstance(
        payload.get("ablation_study"), str
    ):
        problems.append("ablation_study must be a study id or null")
    problems.extend(_amendment_problems(payload, previous))
    return problems


def _metrics_problems(payload: Mapping[str, Any]) -> list[str]:
    rows = payload.get("metrics")
    if not isinstance(rows, list) or not rows:
        return ["metrics must be a non-empty list — a scalar comparison is not a vector one"]
    problems: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows, start=1):
        if not isinstance(raw, Mapping):
            problems.append(f"metric {index}: must be a mapping")
            continue
        key = raw.get("key")
        label = f"metric {key!r}" if isinstance(key, str) and key else f"metric {index}"
        if not isinstance(key, str) or not key.strip():
            problems.append(f"{label}: key is required (a short id, e.g. gini)")
        elif not key.replace("_", "").isalnum():
            problems.append(f"{label}: key must be alphanumeric with underscores")
        elif key in seen:
            problems.append(f"{label}: key is listed twice")
        else:
            seen.add(key)
        problems.extend(_text_problem(raw.get("name"), f"{label}: name"))
        if raw.get("direction") not in DIRECTIONS:
            problems.append(
                f"{label}: direction is {raw.get('direction')!r}, expected "
                + " or ".join(DIRECTIONS)
            )
        problems.extend(_text_problem(raw.get("units"), f"{label}: units"))
        problems.extend(_text_problem(raw.get("estimand"), f"{label}: estimand"))
        problems.extend(_floor_ref_problems(raw.get("floor_ref"), label))
        margin = _number(raw.get("margin"))
        if margin is None or margin < 0:
            problems.append(
                f"{label}: margin must be a finite number >= 0 (the noninferiority "
                "margin epsilon_j), got " + repr(raw.get("margin"))
            )
        if not str(raw.get("margin_rationale") or "").strip():
            problems.append(
                f"{label}: margin_rationale is required — a margin justified only by the "
                "measured floor is resolution sold as acceptability (R-INV-4)"
            )
        if raw.get("undefined_handling") not in UNDEFINED_HANDLING:
            problems.append(
                f"{label}: undefined_handling is {raw.get('undefined_handling')!r}; this "
                "version implements " + ", ".join(UNDEFINED_HANDLING)
            )
    return problems


def _floor_ref_problems(value: Any, label: str) -> list[str]:
    if isinstance(value, str) and value.startswith("run:") and value[4:].strip():
        return []
    if isinstance(value, str) and value.startswith("sweep:") and value[6:].strip():
        return []
    return [
        f"{label}: floor_ref is {value!r}, expected 'run:E####' (a Phase-0 calibration run "
        "that printed floor_<key>) or 'sweep:<registered name>'"
    ]


def _uncertainty_problems(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["uncertainty must declare method, n_boot, seed and alpha"]
    problems: list[str] = []
    if value.get("method") != UNCERTAINTY_METHOD:
        problems.append(
            f"uncertainty.method is {value.get('method')!r}; this version implements "
            f"{UNCERTAINTY_METHOD!r}"
        )
    n_boot = value.get("n_boot")
    if isinstance(n_boot, bool) or not isinstance(n_boot, int) or n_boot < stats.MIN_BOOT:
        problems.append(f"uncertainty.n_boot must be an integer >= {stats.MIN_BOOT}")
    if isinstance(value.get("seed"), bool) or not isinstance(value.get("seed"), int):
        problems.append("uncertainty.seed must be an integer (the bounds are deterministic)")
    alpha = _number(value.get("alpha"))
    if alpha is None or not 0.0 < alpha < 1.0:
        problems.append("uncertainty.alpha must lie strictly inside (0, 1)")
    return problems


def _margins_set_by_problems(value: Any, experimenter: str | None) -> list[str]:
    if not isinstance(value, Mapping):
        return ["margins_set_by must name who set the margins (testimony)"]
    problems: list[str] = []
    name = value.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("margins_set_by.name is required")
    elif same_actor(name, experimenter):
        problems.append(
            f"margins_set_by.name {name!r} is the roster experimenter {experimenter!r} — the "
            "actor being compared cannot set the bar it is measured against (string "
            "comparison, never authenticated)"
        )
    if "session_receipt" not in value:
        problems.append("margins_set_by.session_receipt is required (a path, or null)")
    elif value.get("session_receipt") is not None and not isinstance(
        value.get("session_receipt"), str
    ):
        problems.append("margins_set_by.session_receipt must be a path or null")
    return problems


def _prediction_problems(
    payload: Mapping[str, Any], contract: Mapping[str, Any]
) -> list[str]:
    """Every metric names a registered prediction whose rule IS its margin.

    The notary, not this module, decides the sealed cell.  If the rule and the
    margin ever disagreed, the run's verdict and the parity assessment would be
    two different comparisons wearing one name — so they are compared here at
    lock time and again at every verify.
    """
    declared = payload.get("predictions")
    if not isinstance(declared, Mapping):
        return ["predictions must map every metric key to the registered prediction id that adjudicates it"]
    registered = registered_predictions(contract)
    track = payload.get("comparison_track")
    problems: list[str] = []
    for row in metric_rows(payload):
        key = row.get("key")
        if not isinstance(key, str) or not key:
            continue
        name = declared.get(key)
        if not isinstance(name, str) or not name:
            problems.append(f"predictions.{key} is required (the P# that adjudicates it)")
            continue
        entry = registered.get(name)
        if entry is None:
            problems.append(
                f"predictions.{key} names {name!r}, which study.yaml does not register "
                f"({', '.join(sorted(registered)) or 'none registered'})"
            )
            continue
        if entry.get("track") is not None and str(entry["track"]) != str(track):
            problems.append(
                f"{name} belongs to track {entry.get('track')!r}, not the comparison track "
                f"{track!r}"
            )
        margin = _number(row.get("margin"))
        problems.extend(_rule_problems(entry.get("rule"), name, key, margin))
    extra = [str(k) for k in declared if k not in set(metric_keys(payload))]
    if extra:
        problems.append(
            "predictions names metric key(s) the lock does not carry: " + ", ".join(sorted(extra))
        )
    return problems


def _rule_problems(rule: Any, name: str, key: str, margin: float | None) -> list[str]:
    bound = "-margin" if margin is None else format(-margin, ".12g")
    if not isinstance(rule, Mapping):
        return [
            f"{name} has no arithmetic rule; parity needs "
            f"{{key: L_{key}, op: '>=', value: {bound}}}"
        ]
    raw_op = rule.get("op", rule.get("operator"))
    op = OPERATOR_ALIASES.get(str(raw_op).strip(), str(raw_op).strip())
    value = _number(rule.get("value"))
    problems: list[str] = []
    if str(rule.get("key")) != f"L_{key}":
        problems.append(
            f"{name} tests {rule.get('key')!r}; the parity rule reads the lower simultaneous "
            f"bound L_{key}"
        )
    if op != "ge":
        problems.append(f"{name} uses op {raw_op!r}; noninferiority is '>=' on the lower bound")
    if margin is not None and (value is None or abs(value - (-margin)) > 1e-12):
        problems.append(
            f"{name} tests value {rule.get('value')!r}; the locked margin for {key} is "
            f"{margin:.12g}, so the rule's value must be {-margin:.12g}"
        )
    if set(rule) - {"key", "op", "operator", "value"}:
        problems.append(f"{name}'s rule carries keys beyond key/op/value")
    return problems


def _amendment_problems(
    payload: Mapping[str, Any], previous: Mapping[str, Any] | None
) -> list[str]:
    """An amendment may clarify; it may never move a criterion."""
    if previous is None:
        return []
    problems: list[str] = []
    for key in FROZEN_LOCK_KEYS:
        if canonical_json(payload.get(key)) != canonical_json(previous.get(key)):
            problems.append(
                f"{key} is frozen at version 1 ({previous.get(key)!r}); an amendment may "
                "not restate it"
            )
    before = {str(row.get("key")): row for row in metric_rows(previous)}
    after = {str(row.get("key")): row for row in metric_rows(payload)}
    if set(before) != set(after):
        problems.append(
            "the metric set is frozen at version 1 ("
            + ", ".join(sorted(before))
            + ") — adding or dropping a metric changes the conjunction"
        )
        return problems
    for key, row in after.items():
        for field in FROZEN_METRIC_KEYS:
            if canonical_json(row.get(field)) != canonical_json(before[key].get(field)):
                problems.append(
                    f"metric {key!r}: {field} is frozen at version 1 "
                    f"({before[key].get(field)!r} → {row.get(field)!r}) — lowering a bar you "
                    "did not clear is a different study"
                )
    return problems


# --------------------------------------------------------------------------
# object builders
# --------------------------------------------------------------------------


def lock_object(
    *,
    study: str,
    version: int,
    payload: Mapping[str, Any],
    file_sha256: str,
    parent_ids: Sequence[str],
    late: bool,
) -> dict[str, Any]:
    """The file VERBATIM plus its hash — the criteria, frozen."""
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "parity_lock",
        "study": study,
        "version": version,
        "file_path": PARITY_NAME,
        "file_sha256": file_sha256,
        # PyYAML resolves an unquoted `2026-09-05` to a `date`, which the object
        # store's canonical JSON cannot carry; `_plain` is the package's
        # coercion, shared with the domain card rather than copied.
        "payload": _plain(payload),
        "parent_ids": list(parent_ids),
        "late": bool(late),
    }


def bind_object(
    *,
    study: str,
    lock_sha: str,
    scorer: Mapping[str, Any],
    floors: Mapping[str, Mapping[str, Any]],
    snapshots: Mapping[str, Sequence[Sequence[Any]]],
) -> dict[str, Any]:
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "parity_bind",
        "study": study,
        "lock_object": lock_sha,
        "scorer": dict(scorer),
        "floors": {key: dict(value) for key, value in floors.items()},
        "pipelines": {
            side: [list(entry) for entry in snapshots.get(side, ())] for side in _PIPELINES
        },
    }


# --------------------------------------------------------------------------
# the pinned table
# --------------------------------------------------------------------------


def read_units(path: Path, keys: Sequence[str]) -> dict[str, Any]:
    """Parse ``tables/parity_units.tsv`` into aligned per-unit arrays.

    Columns: ``unit``, ``block``, then ``ai_<key>`` and ``expert_<key>`` for
    every locked metric.  A missing column is a structural failure, not a
    silently dropped metric.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowError(f"could not read {path.name}: {exc}") from exc
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise WorkflowError(f"{path.name} has a header but no unit rows")
    header = lines[0].split("\t")
    needed = ["unit", "block", *[f"{side}_{key}" for key in keys for side in _PIPELINES]]
    missing = [name for name in needed if name not in header]
    if missing:
        raise WorkflowError(
            f"{path.name} is missing column(s): {', '.join(missing)} — the pinned table "
            "carries one row per sampling unit and both pipelines' contribution per metric"
        )
    index = {name: header.index(name) for name in header}
    units: list[str] = []
    blocks: list[str] = []
    columns: dict[str, list[float]] = {
        f"{side}_{key}": [] for key in keys for side in _PIPELINES
    }
    for number, line in enumerate(lines[1:], start=2):
        cells = line.split("\t")
        if len(cells) != len(header):
            raise WorkflowError(
                f"{path.name} line {number}: {len(cells)} cells, header has {len(header)}"
            )
        units.append(cells[index["unit"]])
        blocks.append(cells[index["block"]])
        for name in columns:
            raw = cells[index[name]].strip()
            try:
                columns[name].append(float(raw) if raw else float("nan"))
            except ValueError:
                columns[name].append(float("nan"))
    return {
        "units": units,
        "blocks": blocks,
        "columns": {name: np.asarray(values, dtype=float) for name, values in columns.items()},
    }


# --------------------------------------------------------------------------
# the decision rule
# --------------------------------------------------------------------------


def decide(metrics: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """``{verdict, agreement_within_floor, undefined_metrics, reasons}``.

    Pure and total: the same rows always give the same verdict, which is what
    lets ``generation verify`` recompute an assessment and compare it to the
    recorded one numeral for numeral.
    """
    undefined = [key for key, row in metrics.items() if not row.get("defined")]
    defined = {key: row for key, row in metrics.items() if row.get("defined")}
    refutes = [key for key, row in defined.items() if float(row["U"]) < -float(row["margin"])]
    reasons: list[str] = []

    if undefined:
        verdict = "refuted" if refutes else "inconclusive"
        reasons.append(
            "undefined metric(s) "
            + ", ".join(undefined)
            + " cannot pass (undefined_handling: cannot_pass)"
        )
    elif all(float(row["L"]) >= 0.0 for row in defined.values()) and any(
        float(row["L"]) >= float(row["delta_floor"]) for row in defined.values()
    ):
        verdict = "exceeds"
    elif all(float(row["L"]) >= -float(row["margin"]) for row in defined.values()):
        verdict = "parity"
    elif refutes:
        verdict = "refuted"
    else:
        verdict = "inconclusive"

    if refutes:
        reasons.append("refuted by " + ", ".join(refutes) + " (U < -margin)")
    for key, row in defined.items():
        if float(row["L"]) < -float(row["margin"]) and key not in refutes:
            reasons.append(f"{key}: L below -margin but U above it — inconclusive, not parity")
    agreement = bool(metrics) and all(
        row.get("defined") and abs(float(row["d"])) <= float(row["delta_floor"])
        for row in metrics.values()
    )
    return {
        "verdict": verdict,
        "agreement_within_floor": agreement,
        "undefined_metrics": undefined,
        "reasons": reasons,
    }


# --------------------------------------------------------------------------
# the assessment
# --------------------------------------------------------------------------


def build_assessment(
    study_dir: Path,
    *,
    study: str,
    run: str,
    lock: Mapping[str, Any],
    bind: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """The whole ``parity_assessed`` body — pure, and replayable by verify.

    Reads exactly three things: the locked criteria, the bound floors, and the
    bytes of the table the run pinned (whose sha256 the manifest recorded).
    Nothing here reads the printed bounds: the scorer's arithmetic is checked
    AGAINST this, never trusted by it.
    """
    payload = lock.get("payload") if isinstance(lock.get("payload"), Mapping) else {}
    rows = metric_rows(payload)
    keys = [str(row.get("key")) for row in rows]
    if not keys:
        raise WorkflowError("the parity lock carries no metrics")

    table = study_dir / UNITS_TABLE
    recorded = _artifact_sha(manifest, UNITS_TABLE)
    if recorded is None:
        raise WorkflowError(
            f"{run} pinned no `artifact: {UNITS_TABLE}` — the comparison cell's evidence is "
            "the per-unit table, and a cell that did not pin it measured nothing"
        )
    if not table.is_file():
        raise WorkflowError(f"{UNITS_TABLE} is missing; {run} hashed it as {recorded[:12]}…")
    actual = sha256_file(table)
    if actual != recorded:
        raise WorkflowError(
            f"{UNITS_TABLE} is {actual[:12]}… but {run} pinned {recorded[:12]}… — the table "
            "the assessment reads must be the bytes the sealed cell produced"
        )

    parsed = read_units(table, keys)
    columns = parsed["columns"]
    block_column = payload.get("block_column")
    blocks = parsed["blocks"] if block_column else None
    n_units = len(parsed["units"])
    n_blocks = stats.block_count(blocks, n_units)

    printed = manifest.get("metrics")
    printed = printed if isinstance(printed, Mapping) else {}
    deltas: dict[str, np.ndarray] = {}
    for row in rows:
        key = str(row.get("key"))
        sign = sign_of(row.get("direction"))
        deltas[key] = sign * (columns[f"ai_{key}"] - columns[f"expert_{key}"])
    uncertainty = payload.get("uncertainty") if isinstance(payload.get("uncertainty"), Mapping) else {}
    bounds = stats.simultaneous_bounds(
        deltas,
        blocks,
        n_boot=int(uncertainty.get("n_boot", 2000)),
        seed=int(uncertainty.get("seed", 0)),
        alpha=float(uncertainty.get("alpha", 0.05)),
    )

    floors = bind.get("floors") if isinstance(bind.get("floors"), Mapping) else {}
    metrics: dict[str, Any] = {}
    for row in rows:
        key = str(row.get("key"))
        floor = floors.get(key)
        if not isinstance(floor, Mapping) or _number(floor.get("value")) is None:
            raise WorkflowError(
                f"the bind records no measured floor for metric {key!r} — every delta_j is "
                "measured by the paired recipe before the comparison runs"
            )
        ai = float(np.mean(columns[f"ai_{key}"]))
        expert = float(np.mean(columns[f"expert_{key}"]))
        difference = float(np.mean(deltas[key]))
        low, high = bounds[key]
        told = printed.get(f"defined_{key}")
        defined = (
            all(math.isfinite(value) for value in (ai, expert, difference, low, high))
            and not (isinstance(told, int | float) and not isinstance(told, bool) and float(told) == 0.0)
        )
        metrics[key] = {
            "ai": _finite_or_none(ai),
            "expert": _finite_or_none(expert),
            "d": _finite_or_none(difference),
            "L": _finite_or_none(low),
            "U": _finite_or_none(high),
            "delta_floor": float(floor["value"]),
            "margin": float(_number(row.get("margin")) or 0.0),
            "defined": defined,
        }

    decision = decide(
        {
            key: {
                **value,
                "L": value["L"] if value["L"] is not None else float("nan"),
                "U": value["U"] if value["U"] is not None else float("nan"),
                "d": value["d"] if value["d"] is not None else float("nan"),
            }
            for key, value in metrics.items()
        }
    )
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "parity_assessment",
        "study": study,
        "run": run,
        "lock_object": _bound_lock(bind),
        "table_sha256": recorded,
        "n_units": n_units,
        "n_blocks": n_blocks,
        "metrics": metrics,
        "verdict": decision["verdict"],
        "agreement_within_floor": decision["agreement_within_floor"],
        "undefined_metrics": decision["undefined_metrics"],
        "reasons": decision["reasons"],
    }


def _bound_lock(bind: Mapping[str, Any]) -> str | None:
    """The lock object the BIND named — carried into the assessment for resolvability."""
    value = bind.get("lock_object")
    return value if isinstance(value, str) else None


def _finite_or_none(value: float) -> float | None:
    return float(value) if math.isfinite(value) else None


def _artifact_sha(manifest: Mapping[str, Any], rel: str) -> str | None:
    artifacts = manifest.get("artifacts")
    entry = artifacts.get(rel) if isinstance(artifacts, Mapping) else None
    sha = entry.get("sha256") if isinstance(entry, Mapping) else None
    return sha if isinstance(sha, str) else None


# --------------------------------------------------------------------------
# admission (registered into the spine, never appended to its list)
# --------------------------------------------------------------------------


def _rule_sealed_access_needs_a_bind(ctx: Context) -> list[str]:
    """Deferral D-2, enforced where the extension CAN enforce it.

    The core still grants every track its own single look; what the extension
    can refuse is the ADMISSION.  A study that spends a frontier seal before the
    pipelines and floors are frozen cannot earn the parity outcome, and this is
    where it is told so — before the look, not after it.
    """
    if ctx.action != "sealed":
        return []
    if joined(ctx.study_dir, read_events(ctx.study_dir), BIND_TYPE):
        return []
    return [
        "parity is declared and no `klein generation parity bind` exists: both pipelines' "
        "snapshots and every metric's measured floor are frozen BEFORE any sealed access on "
        "ANY track (deferral D-2), so this look would put the comparison out of reach"
    ]


def _receipt_inputs(ctx: Context) -> dict[str, str | None]:
    """What parity artifact was in force when this admission was taken."""
    events = read_events(ctx.study_dir)
    bind = latest(joined(ctx.study_dir, events, BIND_TYPE))
    if bind is not None:
        return {"parity": str(bind[0].get("payload_sha256"))}
    lock = _latest_lock(ctx.study_dir, events)
    return {"parity": str(lock[0].get("payload_sha256"))} if lock else {}


def _latest_lock(
    study_dir: Path, events: Sequence[Mapping[str, Any]]
) -> tuple[Mapping[str, Any], dict[str, Any]] | None:
    rows = [row for kind in LOCK_TYPES for row in joined(study_dir, events, kind)]
    rows.sort(key=lambda row: int(row[0].get("sequence") or 0))
    return rows[-1] if rows else None


def locks(
    study_dir: Path, events: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    """Every locked version, oldest first."""
    rows = [row for kind in LOCK_TYPES for row in joined(study_dir, events, kind)]
    rows.sort(key=lambda row: int(row[0].get("sequence") or 0))
    return rows


# --------------------------------------------------------------------------
# the verify family
# --------------------------------------------------------------------------

LOCK_CHECK = "parity lock"
BIND_CHECK = "parity bind"
CELL_CHECK = "parity cell"
ASSESS_CHECK = "parity assessment"


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


def _warn(name: str, detail: str) -> Check:
    return Check(name, "WARN", detail)


def _pass(name: str, detail: str) -> Check:
    return Check(name, "PASS", detail)


def _sequence(event: Mapping[str, Any]) -> int:
    return int(event.get("sequence") or 0)


def _core_sequence(event: Mapping[str, Any]) -> int:
    anchor = event.get("core_anchor")
    return int(anchor.get("sequence") or 0) if isinstance(anchor, Mapping) else 0


def parity_family(ctx: FamilyContext) -> tuple[list[Check], dict[str, Any]]:
    """The ``parity`` family: integrity of the record, then the outcome."""
    events = list(ctx.events)
    versions = locks(ctx.study_dir, events)
    binds = joined(ctx.study_dir, events, BIND_TYPE)
    assessments = joined(ctx.study_dir, events, ASSESS_TYPE)

    checks: list[Check] = []
    checks += _lock_checks(ctx, versions)
    try:
        manifests = {str(m.get("experiment")): m for m in load_manifests(ctx.study_dir)}
    except WorkflowError as exc:
        manifests = {}
        checks.append(_fail(CELL_CHECK, f"run manifests unreadable: {exc}"))
    checks += _bind_checks(ctx, versions, binds, manifests)
    checks += _cell_checks(ctx, versions, manifests)
    assessment_checks, outcome, agreement, undefined = _assessment_checks(
        ctx, versions, binds, assessments, manifests
    )
    checks += assessment_checks

    review = _expertise_outcome(ctx)
    if assessments and review == "incomplete":
        checks.append(
            _warn(
                ASSESS_CHECK,
                "the expertise obligation is still open: this outcome is parity against an "
                "UNREPRODUCED baseline and must be reported with that scope",
            )
        )
    integrity = "FAIL" if any(check.status == "FAIL" for check in checks) else "PASS"
    return checks, {
        "integrity": integrity,
        "outcome": outcome,
        "agreement_within_floor": agreement,
        "review": review,
        "undefined_metrics": undefined,
    }


def _lock_checks(
    ctx: FamilyContext, versions: Sequence[tuple[Mapping[str, Any], dict[str, Any]]]
) -> list[Check]:
    if not versions:
        return [
            _fail(
                LOCK_CHECK,
                f"{PARITY_NAME} is not locked — `klein generation parity lock` freezes the "
                "comparison's criteria before the CONSULT gate",
            )
        ]
    problems: list[str] = []
    if versions[0][1].get("late"):
        problems.append(
            "version 1 was locked after the consult gate: criteria registered once the study "
            "was under way constrain nothing they did not already know"
        )
    newest = versions[-1][1]
    path = parity_path(ctx.study_dir)
    if not path.is_file():
        problems.append(f"{PARITY_NAME} is missing; version {newest.get('version')} hashed it")
    elif sha256_file(path) != newest.get("file_sha256"):
        problems.append(
            f"{PARITY_NAME} is {sha256_file(path)[:12]}… but version "
            f"{newest.get('version')} locked {str(newest.get('file_sha256'))[:12]}… — locked "
            "criteria are immutable; a change is `klein generation parity amend`"
        )
    payload = newest.get("payload") if isinstance(newest.get("payload"), Mapping) else {}
    problems.extend(_prediction_problems(payload, ctx.contract))
    if problems:
        return [_fail(LOCK_CHECK, "; ".join(problems[:6]))]
    late_amendments = [
        str(obj.get("version")) for _event, obj in versions[1:] if obj.get("late")
    ]
    checks = [
        _pass(
            LOCK_CHECK,
            f"{len(versions)} locked version(s); {len(metric_rows(payload))} metric(s), each "
            "with a margin, a rationale and the registered rule that adjudicates it",
        )
    ]
    if late_amendments:
        checks.append(
            _warn(
                LOCK_CHECK,
                "amendment(s) " + ", ".join(late_amendments) + " were recorded after the "
                "consult gate — they are labelled, and the primary criteria remain version 1's",
            )
        )
    return checks


def _bind_checks(
    ctx: FamilyContext,
    versions: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    binds: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    manifests: Mapping[str, Mapping[str, Any]],
) -> list[Check]:
    sealed = [m for m in manifests.values() if m.get("evaluation_kind") == "final_test"]
    if not binds:
        if sealed:
            return [
                _fail(
                    BIND_CHECK,
                    "sealed run(s) "
                    + ", ".join(sorted(str(m.get("experiment")) for m in sealed))
                    + " were taken with no `parity bind`: the pipelines and floors were never "
                    "frozen, so the comparison cannot be earned (deferral D-2)",
                )
            ]
        return [
            _warn(
                BIND_CHECK,
                "no `klein generation parity bind` yet — bind before any sealed access on any "
                "track; an honestly unbound study is label-eligible, an unbound seal is not",
            )
        ]
    if len(binds) > 1:
        return [
            _fail(
                BIND_CHECK,
                f"{len(binds)} binds recorded; the pipelines are frozen ONCE, before the first "
                "sealed access",
            )
        ]
    event, obj = binds[0]
    anchor = _core_sequence(event)
    problems: list[str] = []
    started = run_started_events(ctx.core)
    for manifest in sealed:
        run = str(manifest.get("experiment"))
        sequence = int((started.get(run) or {}).get("sequence") or 0)
        if sequence and sequence < anchor:
            problems.append(
                f"{run} ({manifest.get('track')}) took its sealed look at core sequence "
                f"{sequence}, before the bind anchored at {anchor}"
            )
    payload = versions[-1][1].get("payload") if versions else {}
    payload = payload if isinstance(payload, Mapping) else {}
    floors = obj.get("floors") if isinstance(obj.get("floors"), Mapping) else {}
    for key in metric_keys(payload):
        entry = floors.get(key)
        if not isinstance(entry, Mapping) or _number(entry.get("value")) is None:
            problems.append(f"no measured floor is bound for metric {key!r}")
    problems.extend(_pinned_file_problems(ctx, obj, manifests, payload))
    if problems:
        return [_fail(BIND_CHECK, "; ".join(problems[:6]))]
    return [
        _pass(
            BIND_CHECK,
            f"both pipelines and {len(floors)} floor(s) frozen at core sequence {anchor}, "
            f"before every sealed access ({len(sealed)} recorded)",
        )
    ]


def _pinned_file_problems(
    ctx: FamilyContext,
    bind: Mapping[str, Any],
    manifests: Mapping[str, Mapping[str, Any]],
    payload: Mapping[str, Any],
) -> list[str]:
    """The scorer and both snapshots ARE what the bind pinned, at the sealed commit.

    R-INV-3: the checker is never the searcher.  A scorer edited between the
    bind and the comparison would be a scorer tuned to the answer, and the
    candidate commit of the sealed cell is exactly where that shows up.
    """
    run = _comparison_run(manifests, payload)
    if run is None:
        return []
    if ctx.repo is None:
        return ["not a git repository; the pinned files cannot be read at the sealed commit"]
    candidate = manifests[run].get("candidate_commit")
    if not isinstance(candidate, str):
        return [f"{run} has no candidate commit, so the pinned files cannot be resolved"]
    problems: list[str] = []
    scorer = bind.get("scorer") if isinstance(bind.get("scorer"), Mapping) else {}
    pinned: list[tuple[str, Any]] = []
    if isinstance(scorer.get("path"), str):
        pinned.append((str(scorer["path"]), scorer.get("sha256")))
    for side in _PIPELINES:
        for entry in (bind.get("pipelines") or {}).get(side) or ():
            if isinstance(entry, Sequence) and not isinstance(entry, str | bytes) and len(entry) == 2:
                pinned.append((str(entry[0]), entry[1]))
    for path, recorded in pinned:
        blob = git_blob(ctx.repo, candidate, relative(ctx.repo, ctx.study_dir / path))
        if blob is None:
            problems.append(f"{path} is absent from {candidate[:12]} (the sealed candidate)")
            continue
        if sha256_bytes(blob) != recorded:
            problems.append(
                f"{path} at {candidate[:12]} is not the file the bind pinned "
                f"({str(recorded)[:12]}…)"
            )
    return problems


def _comparison_run(
    manifests: Mapping[str, Mapping[str, Any]], payload: Mapping[str, Any]
) -> str | None:
    track = str(payload.get("comparison_track"))
    sealed = sorted(
        str(m.get("experiment"))
        for m in manifests.values()
        if m.get("evaluation_kind") == "final_test" and str(m.get("track")) == track
    )
    return sealed[0] if sealed else None


def _cell_checks(
    ctx: FamilyContext,
    versions: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    manifests: Mapping[str, Mapping[str, Any]],
) -> list[Check]:
    if not versions:
        return []
    payload = versions[-1][1].get("payload")
    payload = payload if isinstance(payload, Mapping) else {}
    track = str(payload.get("comparison_track"))
    sealed = sorted(
        str(m.get("experiment"))
        for m in manifests.values()
        if m.get("evaluation_kind") == "final_test" and str(m.get("track")) == track
    )
    if not sealed:
        return []
    problems: list[str] = []
    if len(sealed) > 1:
        problems.append(
            f"track {track!r} has {len(sealed)} sealed runs ({', '.join(sealed)}); the "
            "comparison is the track's SOLE sealed evaluation"
        )
    run = sealed[0]
    receipt = _consumed_receipt(ctx, run)
    if receipt is None:
        problems.append(f"{run} consumed no admission receipt")
    elif receipt.checkpoint != "sealed":
        problems.append(
            f"{run} was admitted as {receipt.checkpoint!r}; the comparison cell is a sealed "
            "admission"
        )
    printed = manifests[run].get("metrics")
    printed = printed if isinstance(printed, Mapping) else {}
    for key in metric_keys(payload):
        # An UNDEFINED metric legitimately has no finite number to print — the
        # notary's parser refuses a non-finite line, so the scorer prints `NA`
        # and declares `defined_<key>: 0`.  That declaration is the thing that
        # may not be omitted: silence about a metric is not the same as saying
        # it could not be computed.
        told = printed.get(f"defined_{key}")
        declared_undefined = (
            isinstance(told, int | float) and not isinstance(told, bool) and float(told) == 0.0
        )
        if declared_undefined:
            continue
        missing = [
            name
            for name in (f"ai_{key}", f"expert_{key}", f"d_{key}", f"L_{key}", f"U_{key}")
            if name not in printed
        ]
        if missing:
            problems.append(
                f"metric {key!r} is in the lock but {', '.join(missing)} was never printed by "
                f"{run} (and no `defined_{key}: 0` declared it undefined) — an omitted metric "
                "is not a passed one"
            )
    if problems:
        return [_fail(CELL_CHECK, "; ".join(problems[:6]))]
    return [
        _pass(
            CELL_CHECK,
            f"{run} is the sole sealed evaluation of track {track!r}, admitted as sealed, and "
            f"printed the full table for {len(metric_keys(payload))} metric(s)",
        )
    ]


def _consumed_receipt(ctx: FamilyContext, run: str) -> Any:
    for sha, consumer in ctx.match.consumed.items():
        if consumer == run:
            return next((receipt for receipt in ctx.receipts if receipt.sha == sha), None)
    return None


def _assessment_checks(
    ctx: FamilyContext,
    versions: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    binds: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    assessments: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    manifests: Mapping[str, Mapping[str, Any]],
) -> tuple[list[Check], str, bool | None, list[str]]:
    if not assessments:
        return [], "unassessed", None, []
    event, recorded = assessments[-1]
    run = str(recorded.get("run"))
    if not versions or not binds:
        return (
            [_fail(ASSESS_CHECK, f"{run} was assessed without a lock and a bind")],
            "unassessed",
            None,
            [],
        )
    manifest = manifests.get(run)
    if manifest is None:
        return (
            [_fail(ASSESS_CHECK, f"no run manifest for {run}")],
            "unassessed",
            None,
            [],
        )
    try:
        recomputed = build_assessment(
            ctx.study_dir,
            study=str(recorded.get("study")),
            run=run,
            lock=versions[-1][1],
            bind=binds[0][1],
            manifest=manifest,
        )
    except WorkflowError as exc:
        return (
            [_fail(ASSESS_CHECK, f"the assessment cannot be recomputed: {exc}")],
            "unassessed",
            None,
            [],
        )
    comparable = {key: recorded.get(key) for key in _ASSESS_KEYS}
    expected = {key: recomputed[key] for key in _ASSESS_KEYS}
    if canonical_json(comparable) != canonical_json(expected):
        return (
            [
                _fail(
                    ASSESS_CHECK,
                    f"{run}: the recorded assessment does not recompute from the pinned table "
                    f"(recorded {recorded.get('verdict')!r}, recomputes {recomputed['verdict']!r})",
                )
            ],
            "unassessed",
            None,
            [],
        )
    checks = [
        _pass(
            ASSESS_CHECK,
            f"{event.get('id')} {run}: {recomputed['verdict']} "
            f"(agreement_within_floor={recomputed['agreement_within_floor']}) recomputes from "
            f"{str(recorded.get('table_sha256'))[:12]}… over {recomputed['n_units']} unit(s) in "
            f"{recomputed['n_blocks']} block(s)",
        )
    ]
    checks.extend(_printed_agreement_warnings(recomputed, manifest, run))
    return (
        checks,
        str(recomputed["verdict"]),
        bool(recomputed["agreement_within_floor"]),
        list(recomputed["undefined_metrics"]),
    )


#: The fields verify recomputes and compares.  `reasons` is included on purpose:
#: the explanation is part of the record, and a changed explanation for the same
#: numbers is a changed decision rule.
_ASSESS_KEYS: tuple[str, ...] = (
    "run",
    "table_sha256",
    "n_units",
    "n_blocks",
    "metrics",
    "verdict",
    "agreement_within_floor",
    "undefined_metrics",
    "reasons",
)


def _printed_agreement_warnings(
    recomputed: Mapping[str, Any], manifest: Mapping[str, Any], run: str
) -> list[Check]:
    """Did the scorer PRINT the numbers its own table implies?

    A WARN rather than a FAIL: the authority is the pinned table, which the
    assessment already recomputed, and a scorer that rounds its printed block
    differently has not laundered anything.  A large gap is still worth a
    reader's attention, which is what this line is for.
    """
    printed = manifest.get("metrics")
    printed = printed if isinstance(printed, Mapping) else {}
    drift: list[str] = []
    for key, row in (recomputed.get("metrics") or {}).items():
        for name, value in (("d", row.get("d")), ("L", row.get("L")), ("U", row.get("U"))):
            told = printed.get(f"{name}_{key}")
            if value is None or not isinstance(told, int | float) or isinstance(told, bool):
                continue
            scale = max(1.0, abs(float(value)))
            if abs(float(told) - float(value)) / scale > 1e-6:
                drift.append(f"{name}_{key}: printed {float(told):.12g}, table gives {float(value):.12g}")
    if not drift:
        return []
    return [
        _warn(
            ASSESS_CHECK,
            f"{run} printed bounds that differ from its own pinned table: "
            + "; ".join(drift[:4])
            + " — the assessment used the TABLE",
        )
    ]


def _expertise_outcome(ctx: FamilyContext) -> str:
    """The expertise family's own outcome, computed by the expertise family.

    Calling it rather than re-deriving it keeps one implementation of "was the
    baseline reproduced, and by whom" — R-EXP-4 wants that word to propagate
    into the parity scope, and a second copy of the rule would drift from it.
    """
    from . import expert

    try:
        _checks, outcome = expert.verify_family(ctx)
    except WorkflowError:  # pragma: no cover - the family catches its own errors
        return "unknown"
    value = outcome.get("outcome")
    return str(value) if isinstance(value, str) else "unknown"


def experimenter_of(study_dir: Path) -> str | None:
    """The roster's experimenter — the actor the margins may not be set by."""
    return roster_experimenter(study_dir)


CAPABILITY = Capability(
    name=CAPABILITY_NAME,
    admission_rules=(_rule_sealed_access_needs_a_bind,),
    verify_family=parity_family,
    receipt_inputs=_receipt_inputs,
)
