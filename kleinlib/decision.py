"""Keep / discard arithmetic and the detection-limit (headroom) rules.

Extracted verbatim from :mod:`kleinlib.workflow`: how the printed metric block
is parsed off a run log, which manifest is a track's incumbent, whether the
guardrails pass, and — given all of that — whether a candidate is a ``keep`` or
a ``discard``.  :func:`track_headroom` and its helpers answer the prior question
of whether a keep is arithmetically possible at all.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .contract import _guardrail_entries
from .errors import WorkflowError

__all__ = [
    "COMBINATOR_KEYS",
    "MAX_RULE_DEPTH",
    "METRIC_LINE_RE",
    "OPERATOR_ALIASES",
    "RULE_OPERATORS",
    "choose_disposition",
    "parse_metric_log",
    "track_headroom",
    "validate_rule",
]

METRIC_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$")

# ---------------------------------------------------------------------------
# The prediction-rule grammar (schema 3)
#
# A registered prediction is decided by ARITHMETIC ON THE PRINTED BLOCK, never
# by prose and never by executing contract text: there is no ``eval``, ``exec``
# or ``compile`` anywhere on this path, and a test greps for that.  A rule is a
# small closed data structure and the evaluator that consumes it is a dict
# dispatch over a fixed operator set.  This module owns the GRAMMAR
# (:func:`validate_rule`, called by contract validation at the consult gate);
# evaluating a rule against a run's printed keys is the predictions ledger's job.
# ---------------------------------------------------------------------------

#: Leaf operators.  ``eq`` deliberately requires an explicit ``tol``: bare
#: floating-point equality on a measured number is never an honest prediction.
RULE_OPERATORS: frozenset[str] = frozenset(
    {"lt", "le", "gt", "ge", "eq", "ne", "abs_lt", "abs_le", "within", "between"}
)

#: The symbolic spellings the consult protocol writes (``op: ">="``).
OPERATOR_ALIASES: dict[str, str] = {
    "<": "lt",
    "<=": "le",
    ">": "gt",
    ">=": "ge",
    "==": "eq",
    "!=": "ne",
}

#: Boolean combinators.  Exactly one per node.
COMBINATOR_KEYS: frozenset[str] = frozenset({"all_of", "any_of", "not"})

#: The root counts as depth 1, so a leaf under two combinators is depth 3.  A
#: rule that needs more nesting than this is a paragraph, not a prediction.
MAX_RULE_DEPTH = 3

_LEAF_KEYS = frozenset({"key", "op", "operator", "value", "tol", "target", "low", "high"})
_NUMERIC_ONLY = frozenset({"lt", "le", "gt", "ge", "ne", "abs_lt", "abs_le"})


def _finite(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _leaf_problems(rule: Mapping[str, Any], where: str) -> list[str]:
    problems: list[str] = []
    unknown = set(rule) - _LEAF_KEYS
    if unknown:
        problems.append(f"{where}: unknown keys {sorted(unknown)}")
    if "op" in rule and "operator" in rule:
        problems.append(f"{where}: give op or operator, not both")
    raw_op = rule.get("op", rule.get("operator"))
    if not isinstance(raw_op, str) or not raw_op.strip():
        problems.append(
            f"{where}: op is required (one of {sorted(RULE_OPERATORS)} "
            f"or {sorted(OPERATOR_ALIASES)})"
        )
        return problems
    op = OPERATOR_ALIASES.get(raw_op.strip(), raw_op.strip())
    if op not in RULE_OPERATORS:
        problems.append(
            f"{where}: unknown op {raw_op!r} (one of {sorted(RULE_OPERATORS)} "
            f"or {sorted(OPERATOR_ALIASES)})"
        )
        return problems
    key = rule.get("key")
    if not isinstance(key, str) or not METRIC_LINE_RE.match(f"{key}: 0"):
        problems.append(
            f"{where}: key is required and must be a printable metric key "
            "(letters, digits, underscore)"
        )

    value = rule.get("value")
    if op in _NUMERIC_ONLY:
        if not _finite(value):
            problems.append(f"{where}: {op} requires a finite numeric value")
        if "tol" in rule:
            problems.append(f"{where}: tol applies to eq and within only")
    elif op == "eq":
        if not _finite(value):
            problems.append(f"{where}: eq requires a finite numeric value")
        tol = rule.get("tol")
        if not _finite(tol) or float(tol) < 0:
            problems.append(
                f"{where}: eq requires an explicit tol >= 0 — bare float equality "
                "on a measured number is never decidable"
            )
    elif op == "within":
        merged: Mapping[str, Any] = {**rule, **value} if isinstance(value, Mapping) else rule
        if not _finite(merged.get("target")):
            problems.append(f"{where}: within requires a finite target")
        tol = merged.get("tol")
        if not _finite(tol) or float(tol) < 0:
            problems.append(f"{where}: within requires a finite tol >= 0")
    else:  # between
        low, high = rule.get("low"), rule.get("high")
        if low is None and high is None:
            if not isinstance(value, Sequence) or isinstance(value, str) or len(value) != 2:
                problems.append(f"{where}: between requires value: [low, high]")
                return problems
            low, high = value
        if not _finite(low) or not _finite(high):
            problems.append(f"{where}: between requires finite low and high")
        elif float(low) > float(high):
            problems.append(f"{where}: between requires low <= high")
    return problems


def validate_rule(rule: Any, *, where: str = "rule", depth: int = 1) -> list[str]:
    """Shape-check one declarative prediction rule; return problem strings.

    The grammar, in full::

        leaf        {key: <printed key>, op: <operator>, value: ...}
        operators   lt le gt ge ne abs_lt abs_le  (a finite numeric value)
                    eq                            (+ an explicit tol >= 0)
                    within                        (target + tol)
                    between                       (value: [low, high])
        aliases     <  <=  >  >=  ==  !=
        combinators {all_of: [...]}  {any_of: [...]}  {not: <rule>}
        depth       <= 3, counting the root as 1

    Nothing here executes contract text; the operator set is closed.
    """
    if not isinstance(rule, Mapping):
        return [f"{where}: must be a mapping"]
    if depth > MAX_RULE_DEPTH:
        return [f"{where}: rule nesting exceeds depth {MAX_RULE_DEPTH}"]
    present = set(COMBINATOR_KEYS) & set(rule)
    if not present:
        return _leaf_problems(rule, where)
    if len(present) > 1 or set(rule) - present:
        return [
            f"{where}: a combinator node holds exactly one of "
            f"{sorted(COMBINATOR_KEYS)} and nothing else"
        ]
    name = present.pop()
    child = rule[name]
    if name == "not":
        return validate_rule(child, where=f"{where}.not", depth=depth + 1)
    if not isinstance(child, Sequence) or isinstance(child, str) or not child:
        return [f"{where}: {name} requires a non-empty list of rules"]
    problems: list[str] = []
    for index, item in enumerate(child):
        problems.extend(
            validate_rule(item, where=f"{where}.{name}[{index}]", depth=depth + 1)
        )
    return problems


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
