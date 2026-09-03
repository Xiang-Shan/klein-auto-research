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
    "INCONCLUSIVE",
    "MAX_RULE_DEPTH",
    "METRIC_LINE_RE",
    "OPERATOR_ALIASES",
    "REFUTED",
    "RULE_OPERATORS",
    "SUPPORTED",
    "VALID_VERDICTS",
    "adjudicate",
    "choose_disposition",
    "evaluate_rule",
    "parse_metric_log",
    "parse_printed_lines",
    "parse_printed_strings",
    "printed_values",
    "registered_guardrails",
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


# ---------------------------------------------------------------------------
# Evaluating a rule — the predictions ledger's arithmetic
#
# Three-valued on purpose.  ``inconclusive`` is not a polite ``refuted``: it
# says the run did not carry the number the belief was about, and a study that
# closes on it has a finding ("not adjudicated because ...") rather than a
# result.  Same closed operator set as :func:`validate_rule`, same absence of
# ``eval``/``exec``/``compile``.
# ---------------------------------------------------------------------------

SUPPORTED = "supported"
REFUTED = "refuted"
INCONCLUSIVE = "inconclusive"

#: Every verdict a prediction can hold in the ledger.  ``open`` is the absence
#: of a record, never a stored value.
VALID_VERDICTS: frozenset[str] = frozenset({SUPPORTED, REFUTED, INCONCLUSIVE})


def _num(value: float) -> str:
    """A number as a reader would write it: no trailing float noise."""
    return format(float(value), ".12g")


def _verdict(held: bool) -> str:
    return SUPPORTED if held else REFUTED


#: ``op -> (predicate, symbol)``.  The dispatch table IS the operator set: an
#: op that is not a key here cannot be evaluated, however the contract spells it.
_COMPARISONS: dict[str, tuple[Any, str]] = {
    "lt": (lambda x, v: x < v, "<"),
    "le": (lambda x, v: x <= v, "<="),
    "gt": (lambda x, v: x > v, ">"),
    "ge": (lambda x, v: x >= v, ">="),
    "ne": (lambda x, v: x != v, "!="),
}


def _leaf_verdict(rule: Mapping[str, Any], printed: Mapping[str, float]) -> tuple[str, str]:
    key = str(rule.get("key"))
    raw_op = str(rule.get("op", rule.get("operator", ""))).strip()
    op = OPERATOR_ALIASES.get(raw_op, raw_op)
    if key not in printed:
        return (
            INCONCLUSIVE,
            f"{key} was not printed by this run → inconclusive (a missing number "
            "is not a refutation)",
        )
    try:
        observed = float(printed[key])
    except (TypeError, ValueError):
        return (INCONCLUSIVE, f"{key} was printed as {printed[key]!r}, not a number → inconclusive")
    if op in _COMPARISONS:
        predicate, symbol = _COMPARISONS[op]
        target = float(rule["value"])
        verdict = _verdict(predicate(observed, target))
        return verdict, f"{key} {_num(observed)} {symbol} {_num(target)} → {verdict}"
    if op == "eq":
        target, tol = float(rule["value"]), float(rule["tol"])
        delta = abs(observed - target)
        verdict = _verdict(delta <= tol)
        return (
            verdict,
            f"{key} {_num(observed)} == {_num(target)} ± {_num(tol)} "
            f"(|Δ| = {_num(delta)}) → {verdict}",
        )
    if op in {"abs_lt", "abs_le"}:
        target = float(rule["value"])
        magnitude = abs(observed)
        symbol = "<" if op == "abs_lt" else "<="
        verdict = _verdict(magnitude < target if op == "abs_lt" else magnitude <= target)
        return (
            verdict,
            f"|{key}| {_num(magnitude)} {symbol} {_num(target)} "
            f"(from {_num(observed)}) → {verdict}",
        )
    if op == "within":
        value = rule.get("value")
        merged: Mapping[str, Any] = {**rule, **value} if isinstance(value, Mapping) else rule
        target, tol = float(merged["target"]), float(merged["tol"])
        delta = abs(observed - target)
        verdict = _verdict(delta <= tol)
        return (
            verdict,
            f"{key} {_num(observed)} within {_num(tol)} of {_num(target)} "
            f"(|Δ| = {_num(delta)}) → {verdict}",
        )
    if op == "between":
        low, high = rule.get("low"), rule.get("high")
        if low is None and high is None:
            low, high = rule["value"]
        low, high = float(low), float(high)
        verdict = _verdict(low <= observed <= high)
        return verdict, f"{key} {_num(observed)} in [{_num(low)}, {_num(high)}] → {verdict}"
    return (INCONCLUSIVE, f"unknown op {raw_op!r} → inconclusive")


def evaluate_rule(
    rule: Any, printed: Mapping[str, float], *, depth: int = 1
) -> tuple[str, str]:
    """Decide one declarative rule against a run's printed block.

    Returns ``(verdict, explanation)`` where the verdict is ``supported``,
    ``refuted`` or ``inconclusive`` and the explanation is ARITHMETIC ON THE
    RECORD — ``"ci_low 336.4 > 70 → supported"`` — so a reader can re-check the
    decision without re-running anything.

    Three-valued logic through the combinators: ``all_of`` is refuted by any
    refuted child and inconclusive if any child is; ``any_of`` is supported by
    any supported child and inconclusive only when no child was decided in its
    favour; ``not`` swaps supported and refuted and leaves inconclusive alone.
    """
    if not isinstance(rule, Mapping):
        return (INCONCLUSIVE, f"rule is not a mapping ({type(rule).__name__}) → inconclusive")
    if depth > MAX_RULE_DEPTH:
        return (
            INCONCLUSIVE,
            f"rule nesting exceeds depth {MAX_RULE_DEPTH} → inconclusive",
        )
    present = sorted(COMBINATOR_KEYS & set(rule))
    if not present:
        try:
            return _leaf_verdict(rule, printed)
        except (KeyError, TypeError, ValueError) as exc:
            # A malformed rule reaches here only if it skipped validation; it is
            # still not a refutation of anything.
            return (INCONCLUSIVE, f"rule could not be evaluated ({exc}) → inconclusive")
    name = present[0]
    child = rule[name]
    if name == "not":
        verdict, explanation = evaluate_rule(child, printed, depth=depth + 1)
        flipped = {SUPPORTED: REFUTED, REFUTED: SUPPORTED}.get(verdict, verdict)
        return flipped, f"not({explanation}) → {flipped}"
    if not isinstance(child, Sequence) or isinstance(child, str) or not child:
        return (INCONCLUSIVE, f"{name} holds no rules → inconclusive")
    results = [evaluate_rule(item, printed, depth=depth + 1) for item in child]
    verdicts = [verdict for verdict, _ in results]
    if name == "all_of":
        combined = (
            REFUTED
            if REFUTED in verdicts
            else INCONCLUSIVE
            if INCONCLUSIVE in verdicts
            else SUPPORTED
        )
    else:  # any_of
        combined = (
            SUPPORTED
            if SUPPORTED in verdicts
            else INCONCLUSIVE
            if INCONCLUSIVE in verdicts
            else REFUTED
        )
    joined = "; ".join(explanation for _, explanation in results)
    return combined, f"{name}[{joined}] → {combined}"


def adjudicate(
    prediction: Mapping[str, Any], printed: Mapping[str, float]
) -> tuple[str, str]:
    """Decide one registered prediction: ``inconclusive_if`` first, then the rule.

    ``inconclusive_if`` is the pre-registered admission that some runs cannot
    decide the question at all (too few effective samples, a degenerate fit).
    It is checked BEFORE the rule so that a run inside that condition never
    produces a verdict the contract already said it could not produce.  As a
    RULE it fires when it evaluates ``supported``; as a SENTENCE it documents a
    human condition the machine cannot see, and the rule decides.
    """
    condition = prediction.get("inconclusive_if")
    if isinstance(condition, Mapping):
        verdict, explanation = evaluate_rule(condition, printed)
        if verdict == SUPPORTED:
            return (INCONCLUSIVE, f"inconclusive_if fired: {explanation}")
    rule = prediction.get("rule")
    if rule is None:
        return (
            INCONCLUSIVE,
            "prediction carries no rule (manual): adjudicate it with "
            "`klein predict adjudicate` and pin its evidence",
        )
    return evaluate_rule(rule, printed)


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


def parse_printed_lines(path: Path) -> list[tuple[str, str]]:
    """Every ``key: value`` line of the printed block, verbatim and in order."""
    lines: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = METRIC_LINE_RE.match(line)
        if match:
            lines.append(match.groups())
    return lines


def printed_values(path: Path, key: str) -> list[str]:
    """Every value printed under ``key``, whatever its type.

    :func:`parse_metric_log` keeps only floats and :func:`parse_printed_strings`
    only non-floats, so a key whose value happens to look numeric
    (``sealed_dryrun: 1``) would fall out of a string-only lookup.  Callers that
    want one named line ask for it by name here instead of guessing its type.
    """
    return [raw for name, raw in parse_printed_lines(path) if name == key]


def parse_printed_strings(path: Path) -> dict[str, list[str]]:
    """Every NON-numeric printed line, keyed, in the order it was printed.

    :func:`parse_metric_log` keeps only the floats a guardrail or a metric can
    be, and drops everything else.  Some printed lines are evidence anyway:
    ``split_fingerprint:`` (which partition the numbers came from) and the
    ``artifact:`` lines a registered cell pins (each a study-relative POSIX
    path the notary hashes into ``manifest.artifacts``).  Values are lists
    because a cell may pin several artifacts.
    """
    found: dict[str, list[str]] = {}
    for key, raw in parse_printed_lines(path):
        try:
            float(raw)
        except ValueError:
            found.setdefault(key, []).append(raw)
    return found


def _incumbent(manifests: Sequence[Mapping[str, Any]], track: str) -> Mapping[str, Any] | None:
    keeps = [
        m
        for m in manifests
        if m.get("track") == track
        and m.get("disposition") == "keep"
        and m.get("evaluation_kind", "development") == "development"
    ]
    return keeps[-1] if keeps else None


def _seed_external_incumbent(
    track_spec: Mapping[str, Any], incumbent: Mapping[str, Any] | None
) -> Mapping[str, Any] | None:
    """Start the frontier at the best KNOWN value, not at the first run.

    With ``metric.incumbent_external`` declared, a ``keep`` means "beat the
    literature" rather than "beat yourself".  A first result that merely matches
    the published value is a ``discard`` with the match disclosed — and a search
    that fails is a search limit, never evidence of impossibility.

    It lives beside :func:`_incumbent` because both the RUNNER (which enforces
    the headroom law) and the CHECKS (which disclose it) have to resolve the
    same incumbent: a preflight that reports "no incumbent yet" while run-one
    refuses the run on h = 0 is a disclosure disagreeing with an enforcement.
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


def registered_guardrails(
    track_spec: Mapping[str, Any], metrics: Mapping[str, float]
) -> tuple[bool, list[str]]:
    """Guardrails on a registered cell: RECORDED, never disposition-flipping.

    A frontier guardrail answers "may this candidate become the incumbent?" and
    a failure is a ``discard``.  A registered cell has no incumbent to become,
    so the same arithmetic answers a different question — "is this measurement
    inside the conditions the contract declared?" — and its answer belongs on
    the manifest (``guardrails_ok``) and in findings, where a reader can weigh
    it.  Flipping the cell to ``discard`` would delete the measurement instead.

    ``incumbent=None`` on purpose: a ``maximum_degradation`` guardrail is a
    frontier comparison and has nothing to compare against here.
    """
    return _guardrails_pass(track_spec.get("guardrails", {}), metrics, None)


def choose_disposition(
    *,
    primary_metric: float,
    track_spec: Mapping[str, Any],
    metrics: Mapping[str, float],
    incumbent: Mapping[str, Any] | None,
    final_test: bool,
    mode: str = "frontier",
) -> tuple[str, str]:
    if mode == "registered":
        # `references/registered-mode.md`: a run on a registered track is a
        # CELL of a pre-registered measurement program.  There is no incumbent,
        # so there is nothing to keep or discard — the disposition says only
        # that the cell measured what it said it would.  Sealed cells included:
        # a registered kind's confirmation is still a measurement.
        _, guard_failures = registered_guardrails(track_spec, metrics)
        detail = (
            f"; guardrails failed (recorded, not hidden): {'; '.join(guard_failures)}"
            if guard_failures
            else ""
        )
        return "measured", f"registered cell measured{detail}"
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
