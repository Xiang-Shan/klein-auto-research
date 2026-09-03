"""Shared evaluation block for Klein Auto Research studies.

Adapted from the model-survey campaign's ``lib/eval.py``. The original
printed a canonical metric block (parsed by the agent-smith
``summarize_results.py`` auto-detector) followed by an ``--- aux_metrics
---`` block, and said aux metrics "never enter results.tsv — they're for
the agent's reading." That constraint is now lifted: aux metrics are
appended to a dedicated ``<study_dir>/aux_metrics.tsv`` sidecar (long format:
``experiment  metric  value``, per ``kleinlib.schema.AUX_COLUMNS``) so a
later phase can read them programmatically. ``results.tsv`` itself is
untouched — the "5 columns, one row per experiment" contract is unaffected.

The printed canonical block — the eight lines from ``primary_metric``
through ``status``, and (for :func:`evaluate`) the six classification aux
lines beneath ``--- aux_metrics ---`` — is preserved **exactly, line for
line** (including the original's spacing) from the campaign source, so any
existing summarizer keeps parsing it unchanged. Every evaluator shape below
(:func:`evaluate`, :func:`evaluate_regression`, :func:`evaluate_scalar`, and
the three registered-cell shapes :func:`evaluate_estimate`,
:func:`evaluate_test`, :func:`evaluate_table`) shares that same canonical-block
format via `_print_canonical_block`.

A **registered** track measures instead of climbing
(`.claude/skills/klein/references/registered-mode.md`): each run is a cell of a
pre-registered measurement program, and its printed block is what a registered
prediction's rule reads. The three cell shapes are an estimate with an interval,
a hypothesis test with its family size, and a table that IS the measurement.
Every key they print is registered in `kleinlib.schema.EVALUATOR_PRINTED_KEYS`,
so `klein preflight` knows which guardrail keys will be visible.

The ONE sanctioned addition since the campaign source: every evaluator also
prints a ``wall_seconds:`` aux line (via `_print_wall_seconds`) unless the
caller already supplies ``wall_seconds`` through ``extra`` — the runner's
guardrail check reads the PRINTED block only, and the sidecar-only
``wall_seconds`` cost study 05 an anchor-exact candidate (E0001).

Hard guard (the MPS collapse war story): on Apple Silicon, torch
`DataLoader` + `TensorDataset` silently collapsed every prediction to a
near-constant value. ``evaluate`` now rejects non-finite output and detects
true collapse from probability range and unique values, without rejecting a
valid weak-signal model merely because its absolute standard deviation is
below a domain-specific threshold.
"""

from __future__ import annotations

import csv
import os
import time
import uuid
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    mean_absolute_error,
    mean_gamma_deviance,
    mean_poisson_deviance,
    mean_squared_error,
    mean_tweedie_deviance,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold

from . import schema, snapshot
from .primitives import sha256_file

__all__ = [
    "MetricSpec",
    "evaluate",
    "evaluate_estimate",
    "evaluate_regression",
    "evaluate_scalar",
    "evaluate_table",
    "evaluate_test",
    "evaluate_with_inner_cv",
    "get_metric_spec",
    "save_holdout_predictions",
]


_VALID_GOALS = frozenset({"higher", "lower"})


@dataclass(frozen=True)
class MetricSpec:
    """Validated identity, direction, and task for a primary metric."""

    name: str
    goal: str
    task: str

    def __post_init__(self) -> None:
        if not self.name or any(char.isspace() for char in self.name):
            raise ValueError("metric name must be a non-empty token without whitespace")
        if self.goal not in _VALID_GOALS:
            raise ValueError(
                f"metric goal must be one of {sorted(_VALID_GOALS)}, got {self.goal!r}"
            )

    def validate_value(self, value: Any) -> float:
        """Return ``value`` as a finite float or raise an actionable error."""
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"metric {self.name!r} must be numeric, got {value!r}"
            ) from exc
        if not np.isfinite(result):
            raise ValueError(
                f"metric {self.name!r} must be finite, got {result!r}"
            )
        return result


_METRIC_SPECS: dict[str, MetricSpec] = {
    "val_auc": MetricSpec("val_auc", "higher", "classification"),
    "val_pr_auc": MetricSpec("val_pr_auc", "higher", "classification"),
    "val_logloss": MetricSpec("val_logloss", "lower", "classification"),
    "val_brier": MetricSpec("val_brier", "lower", "classification"),
    "val_lift_top10": MetricSpec("val_lift_top10", "higher", "classification"),
    "val_f1_at_best": MetricSpec("val_f1_at_best", "higher", "classification"),
    "val_rmse": MetricSpec("val_rmse", "lower", "regression"),
    "val_mae": MetricSpec("val_mae", "lower", "regression"),
    "val_r2": MetricSpec("val_r2", "higher", "regression"),
    "val_poisson_deviance": MetricSpec("val_poisson_deviance", "lower", "regression"),
    "val_gamma_deviance": MetricSpec("val_gamma_deviance", "lower", "regression"),
    "val_tweedie_deviance": MetricSpec("val_tweedie_deviance", "lower", "regression"),
}

#: Best achievable value for each hard-bounded metric — the basis for the
#: headroom (detection-limit) audit: with ``goal: lower`` and an ideal of 0,
#: no challenger can beat an incumbent by more than the incumbent's own score.
#: Declaring ``metric.bound.ideal`` in study.yaml arms the audit; this table
#: only powers the preflight HINT for studies that have not declared it
#: (``val_lift_top10`` is unbounded and deliberately absent).
KNOWN_IDEALS: dict[str, float] = {
    "val_auc": 1.0,
    "val_pr_auc": 1.0,
    "val_logloss": 0.0,
    "val_brier": 0.0,
    "val_f1_at_best": 1.0,
    "val_rmse": 0.0,
    "val_mae": 0.0,
    "val_r2": 1.0,
    "val_poisson_deviance": 0.0,
    "val_gamma_deviance": 0.0,
    "val_tweedie_deviance": 0.0,
}

#: The deviance family follows the exposure-weighted-rate convention: the
#: target is a RATE (e.g. claim counts / exposure) and ``sample_weight`` is
#: the exposure base. This is the standard actuarial formulation (and the one
#: study 04 hand-rolled before the registry carried it).
DEVIANCE_METRICS = frozenset(
    {"val_poisson_deviance", "val_gamma_deviance", "val_tweedie_deviance"}
)


def _validate_sample_weight(sample_weight: Any, n: int) -> np.ndarray | None:
    """Return validated weights (1-D, length n, finite, strictly positive)."""
    if sample_weight is None:
        return None
    w = np.asarray(sample_weight, dtype=float)
    if w.ndim != 1 or w.size != n:
        raise ValueError(
            f"sample_weight must be 1-D with length {n}, got shape {w.shape}"
        )
    if not np.all(np.isfinite(w)):
        raise ValueError("sample_weight must contain only finite values")
    if np.any(w <= 0):
        raise ValueError(
            "sample_weight must be strictly positive — drop zero-exposure rows "
            "in prepare.py rather than weighting them to nothing"
        )
    return w


def _deviance_value(
    name: str,
    y_true: np.ndarray,
    pred: np.ndarray,
    *,
    sample_weight: np.ndarray | None,
    tweedie_power: float | None,
) -> float:
    """Compute one deviance metric with actionable domain guards.

    The evaluator never clips: a non-positive prediction is the model's
    problem to fix in train.py (e.g. ``np.clip(pred, 1e-6, None)``), not
    something the evidence layer should paper over silently.
    """
    if name == "val_tweedie_deviance":
        if tweedie_power is None:
            raise ValueError(
                "val_tweedie_deviance requires tweedie_power= (the contract's "
                "metric.power); use val_poisson_deviance (p=1) or "
                "val_gamma_deviance (p=2) for the endpoints"
            )
        power = float(tweedie_power)
        if not np.isfinite(power) or not 1.0 < power < 2.0:
            raise ValueError(
                f"tweedie_power must satisfy 1 < power < 2, got {tweedie_power!r}"
            )
    elif tweedie_power is not None:
        raise ValueError("tweedie_power applies only to val_tweedie_deviance")
    if name == "val_gamma_deviance":
        if np.any(y_true <= 0):
            raise ValueError(
                "val_gamma_deviance requires strictly positive targets; "
                "filter zero rows in prepare.py or use val_tweedie_deviance"
            )
    elif np.any(y_true < 0):
        raise ValueError(f"{name} requires non-negative targets")
    if np.any(pred <= 0):
        raise ValueError(
            f"{name} requires strictly positive predictions; clip in train.py "
            "(e.g. np.clip(pred, 1e-6, None))"
        )
    if name == "val_poisson_deviance":
        return float(mean_poisson_deviance(y_true, pred, sample_weight=sample_weight))
    if name == "val_gamma_deviance":
        return float(mean_gamma_deviance(y_true, pred, sample_weight=sample_weight))
    return float(
        mean_tweedie_deviance(
            y_true, pred, sample_weight=sample_weight, power=float(tweedie_power)
        )
    )


def get_metric_spec(
    name: str,
    *,
    goal: str | None = None,
    task: str | None = None,
    allow_custom: bool = False,
) -> MetricSpec:
    """Resolve and validate a metric contract.

    Known evaluator metrics have one canonical task and direction.  Custom
    names are accepted only for scalar studies, where the caller already owns
    the calculation and must state an explicit direction.
    """
    spec = _METRIC_SPECS.get(name)
    if spec is None:
        if not allow_custom:
            known = ", ".join(sorted(_METRIC_SPECS))
            raise ValueError(f"unknown metric {name!r}; supported metrics: {known}")
        if goal is None:
            raise ValueError(f"custom metric {name!r} requires metric_goal")
        spec = MetricSpec(name=name, goal=goal, task=task or "scalar")
    if goal is not None and goal != spec.goal:
        raise ValueError(
            f"metric {name!r} has canonical goal {spec.goal!r}, got {goal!r}"
        )
    if task is not None and spec.task != task and not allow_custom:
        raise ValueError(
            f"metric {name!r} belongs to task {spec.task!r}, not {task!r}"
        )
    return spec


def _validate_probabilities(
    probabilities: Any,
    *,
    collapse_rtol: float,
    legacy_min_std: float | None,
) -> tuple[np.ndarray, float, float, int]:
    """Validate probabilities and reject only genuinely near-constant output."""
    p = np.asarray(probabilities, dtype=float)
    if p.ndim != 1 or p.size == 0:
        raise ValueError(
            f"positive-class probabilities must be a non-empty 1-D array, got {p.shape}"
        )
    if collapse_rtol < 0:
        raise ValueError("collapse_rtol must be non-negative")
    if not np.all(np.isfinite(p)):
        bad = int(np.size(p) - np.count_nonzero(np.isfinite(p)))
        raise ValueError(f"predicted probabilities contain {bad} non-finite value(s)")
    if np.any((p < 0.0) | (p > 1.0)):
        raise ValueError("predicted probabilities must lie in the closed interval [0, 1]")

    proba_std = float(np.std(p))
    proba_range = float(np.ptp(p))
    unique_count = int(np.unique(p).size)
    scale = max(1.0, float(np.max(np.abs(p))))
    tolerance = max(np.finfo(float).eps * 32 * scale, collapse_rtol * scale)
    if unique_count < 2 or proba_range <= tolerance:
        raise RuntimeError(
            "Collapsed predictions: positive-class probabilities are constant or "
            f"numerically indistinguishable (range={proba_range:.6g}, "
            f"unique_values={unique_count}, tolerance={tolerance:.6g}). This is the "
            "MPS DataLoader+TensorDataset collapse war story; use "
            "kleinlib.torch_loop's index-shuffle batching or inspect the fit for "
            "degeneracy."
        )
    if legacy_min_std is not None:
        if legacy_min_std < 0:
            raise ValueError("min_proba_std must be non-negative when provided")
        warnings.warn(
            "min_proba_std is deprecated; the default collapse guard now uses "
            "finite probability range and unique values",
            DeprecationWarning,
            stacklevel=3,
        )
        if proba_std < legacy_min_std:
            raise RuntimeError(
                f"Collapsed predictions under explicit legacy min_proba_std: "
                f"std={proba_std:.6g} < {legacy_min_std:.6g}"
            )
    return p, proba_std, proba_range, unique_count


def _classification_metric_values(
    y_true: Any, probabilities: np.ndarray
) -> tuple[dict[str, float], float]:
    """Compute the supported binary metrics once, from one probability vector."""
    y_array = np.asarray(y_true)
    val_auc = float(roc_auc_score(y_array, probabilities))
    val_pr_auc = float(average_precision_score(y_array, probabilities))
    val_logloss = float(log_loss(y_array, probabilities, labels=[0, 1]))
    val_brier = float(brier_score_loss(y_array, probabilities))

    order = np.argsort(-probabilities)
    decile_n = max(1, len(probabilities) // 10)
    base_rate = float(y_array.mean())
    val_lift10 = (
        float(y_array[order[:decile_n]].mean()) / base_rate if base_rate > 0 else 0.0
    )
    thresholds = np.linspace(0.01, 0.99, 99)
    predictions = probabilities[:, None] > thresholds[None, :]
    positives = y_array.astype(bool)[:, None]
    true_positive = np.count_nonzero(predictions & positives, axis=0)
    false_positive = np.count_nonzero(predictions & ~positives, axis=0)
    false_negative = np.count_nonzero(~predictions & positives, axis=0)
    denominator = 2 * true_positive + false_positive + false_negative
    f1s = np.divide(
        2 * true_positive,
        denominator,
        out=np.zeros_like(denominator, dtype=float),
        where=denominator != 0,
    )
    best_idx = int(np.argmax(f1s))
    values = {
        "val_auc": val_auc,
        "val_pr_auc": val_pr_auc,
        "val_logloss": val_logloss,
        "val_brier": val_brier,
        "val_lift_top10": val_lift10,
        "val_f1_at_best": float(f1s[best_idx]),
    }
    for name, value in values.items():
        _METRIC_SPECS[name].validate_value(value)
    return values, float(thresholds[best_idx])


def _positive_class_probabilities(model: Any, X: Any, y_true: Any) -> np.ndarray:
    """Return P(y=1), validating the binary target and estimator class order."""
    target = np.asarray(y_true)
    if target.ndim != 1 or target.size == 0:
        raise ValueError(f"binary target must be a non-empty 1-D array, got {target.shape}")
    target_values = set(np.unique(target).tolist())
    if target_values != {0, 1}:
        raise ValueError(
            "binary classification evaluate() requires target labels exactly {0, 1}; "
            f"got {sorted(target_values, key=str)!r}"
        )
    raw_proba = np.asarray(model.predict_proba(X))
    if raw_proba.ndim != 2 or raw_proba.shape[1] != 2:
        raise ValueError(
            "binary classification evaluate() requires predict_proba with shape (n, 2)"
        )
    if raw_proba.shape[0] != target.size:
        raise ValueError(
            f"predict_proba returned {raw_proba.shape[0]} rows for {target.size} targets"
        )
    classes = getattr(model, "classes_", None)
    if classes is None:
        return raw_proba[:, 1]
    class_values = np.asarray(classes)
    if class_values.ndim != 1 or class_values.size != 2:
        raise ValueError("model.classes_ must contain exactly two labels")
    if set(class_values.tolist()) != {0, 1}:
        raise ValueError(
            "model.classes_ must contain exactly {0, 1}; "
            f"got {class_values.tolist()!r}"
        )
    positive = np.flatnonzero(class_values == 1)
    if positive.size != 1:
        raise ValueError("model.classes_ must identify class 1 exactly once")
    return raw_proba[:, int(positive[0])]


def _smoke_mode() -> bool:
    """True under ``KLEIN_SMOKE=1`` — the sanctioned pre-run syntax check.

    Smoke runs print the canonical block (that is the point) but skip every
    sidecar and snapshot write, so an off-loop `train.py` execution can never
    pollute the evidence ledger (the soak's F2 friction). `klein run-one`
    force-clears the variable in the child environment, so a forgotten
    ``export KLEIN_SMOKE=1`` can never silently suppress real evidence.
    """
    return os.environ.get("KLEIN_SMOKE") == "1"


_SMOKE_NOTICE = "smoke mode: no sidecar/snapshot writes (KLEIN_SMOKE=1)"


def _fmt_num(x: float | None, spec: str = ".6f") -> str:
    return "NA" if x is None else format(x, spec)


def _fmt_int(x: int | None) -> str:
    return "NA" if x is None else str(x)


def _print_canonical_block(
    *,
    primary_value: float,
    metric_name: str,
    metric_goal: str,
    fit_seconds: float | None,
    total_seconds: float,
    train_n: int | None,
    val_n: int | None,
    status: str,
) -> None:
    """Print the canonical block shared by all three evaluators.

    Line-for-line identical (spacing included) to the model-survey
    campaign's `lib/eval.py` format whenever `fit_seconds`/`train_n`/`val_n`
    are provided (true for :func:`evaluate` and :func:`evaluate_regression`).
    They print as ``NA`` when the caller has no such concept — e.g.
    :func:`evaluate_scalar`, for Monte-Carlo studies with no train/val split.
    """
    print("---")
    print(f"primary_metric:    {primary_value:.6f}")
    print(f"metric_name:       {metric_name}")
    print(f"metric_goal:       {metric_goal}")
    print(f"training_seconds:  {_fmt_num(fit_seconds, '.1f')}")
    print(f"total_seconds:     {total_seconds:.1f}")
    print(f"train_rows:        {_fmt_int(train_n)}")
    print(f"val_rows:          {_fmt_int(val_n)}")
    print(f"status:            {status}")


def _print_wall_seconds(total_seconds: float, extra: dict[str, Any] | None) -> None:
    """Print the framework's ``wall_seconds:`` aux line unless the caller supplies its own.

    ``wall_seconds`` has always been written to the aux sidecar but never
    printed, and ``klein run-one`` reads guardrails off the PRINTED block
    only — so a declared ``wall_seconds`` guardrail scored "missing" and
    discarded an anchor-exact candidate (study 05, E0001). Callers that
    already pass ``wall_seconds`` in ``extra`` keep byte-identical output:
    their value prints once, from the ``extra`` loop, and that is the value
    the runner parses.
    """
    if not (extra and "wall_seconds" in extra):
        print(f"wall_seconds:      {total_seconds:.6f}")


def _print_split_fingerprint(split_fingerprint: str | None) -> None:
    """Print the partition the numbers were computed on (war story 8).

    ``kleinlib.data.load_partition`` already prints this line for the studies
    that call it; an evaluator fed partitions some other way passes the
    fingerprint through here instead, so `klein run-one` can still refuse a
    number measured on the wrong rows. Absent, the run proceeds with a notice.
    """
    if split_fingerprint:
        print(f"split_fingerprint: {split_fingerprint}")


def _append_aux_rows(
    study_dir: str | Path, exp_id: int | str, rows: dict[str, Any]
) -> None:
    """Append `rows` (metric -> value) as long-format lines to aux_metrics.tsv.

    Creates the file with the canonical header (`schema.AUX_COLUMNS`) if it
    does not yet exist or is empty. Idempotent per experiment: any existing
    lines for `exp_id` are dropped first, so re-running an experiment's
    train.py (a legitimate debugging move) refreshes its aux block instead of
    silently double-appending it.
    """
    path = Path(study_dir) / schema.AUX_SIDECAR
    path.parent.mkdir(parents=True, exist_ok=True)
    kept: list[list[str]] = []
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, delimiter="\t")
            try:
                header = next(reader)
            except StopIteration:
                header = []
            if tuple(header) != schema.AUX_COLUMNS:
                raise ValueError(f"invalid aux metrics header in {path}: {header}")
            exp_text = str(exp_id)
            for row in reader:
                if len(row) != len(schema.AUX_COLUMNS):
                    raise ValueError(f"invalid aux metrics row in {path}: {row}")
                if row[0] != exp_text:
                    kept.append(row)

    new_rows = [[str(exp_id), str(metric), str(value)] for metric, value in rows.items()]
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
            writer.writerow(schema.AUX_COLUMNS)
            writer.writerows([*kept, *new_rows])
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def evaluate(
    model: Any,
    X_va: pd.DataFrame,
    y_va: pd.Series,
    *,
    exp_id: int | str,
    t0: float,
    fit_seconds: float,
    train_n: int,
    val_n: int,
    metric_name: str = "val_auc",
    metric_goal: str = "higher",
    extra: dict[str, Any] | None = None,
    split_fingerprint: str | None = None,
    status: str = "ok",
    min_proba_std: float | None = None,
    collapse_rtol: float = 1e-12,
    study_dir: str | Path | None = None,
) -> float:
    """Binary-classification canonical eval: compute, print, guard, persist.

    Computes the primary metric (ROC-AUC) plus aux metrics (PR-AUC, logloss,
    Brier, lift@top-10%, best F1 threshold, F1-at-best). Prints the
    canonical block followed by an ``--- aux_metrics ---`` block. When
    `study_dir` is given: every aux metric plus `wall_seconds` and
    `min_proba_std` (and `model_path`, if a new best was saved) are appended
    to `<study_dir>/aux_metrics.tsv`, and `kleinlib.snapshot.maybe_save_best`
    is called so the best-so-far model is pickled.

    ``metric_name`` selects the actual primary calculation and its registered
    direction must agree with ``metric_goal``. Raises ``RuntimeError`` for
    numerically collapsed probabilities. ``min_proba_std`` remains only as a
    deprecated explicit compatibility guard. Returns the selected primary
    metric as a plain float.
    """
    spec = get_metric_spec(metric_name, goal=metric_goal, task="classification")
    p, proba_std, proba_range, proba_unique = _validate_probabilities(
        _positive_class_probabilities(model, X_va, y_va),
        collapse_rtol=collapse_rtol,
        legacy_min_std=min_proba_std,
    )
    metric_values, val_best_threshold = _classification_metric_values(y_va, p)
    primary_value = spec.validate_value(metric_values[spec.name])
    val_pr_auc = metric_values["val_pr_auc"]
    val_logloss = metric_values["val_logloss"]
    val_brier = metric_values["val_brier"]
    val_lift10 = metric_values["val_lift_top10"]
    val_f1_at_best = metric_values["val_f1_at_best"]

    total_seconds = time.time() - t0

    _print_canonical_block(
        primary_value=primary_value,
        metric_name=metric_name,
        metric_goal=metric_goal,
        fit_seconds=fit_seconds,
        total_seconds=total_seconds,
        train_n=train_n,
        val_n=val_n,
        status=status,
    )
    print("--- aux_metrics ---")
    print(f"val_pr_auc:        {val_pr_auc:.6f}")
    print(f"val_logloss:       {val_logloss:.6f}")
    print(f"val_brier:         {val_brier:.6f}")
    print(f"val_lift_top10:    {val_lift10:.4f}")
    print(f"val_best_threshold: {val_best_threshold:.4f}")
    print(f"val_f1_at_best:    {val_f1_at_best:.4f}")
    _print_wall_seconds(total_seconds, extra)
    _print_split_fingerprint(split_fingerprint)
    if extra:
        for k, v in extra.items():
            print(f"{k}: {v}")

    if study_dir is not None and _smoke_mode():
        print(_SMOKE_NOTICE)
    elif study_dir is not None:
        model_path = snapshot.maybe_save_best(
            model,
            exp_id=exp_id,
            metric_value=primary_value,
            metric_goal=metric_goal,
            study_dir=study_dir,
            primary_name=metric_name,
            track=os.environ.get("KLEIN_TRACK", "primary"),
        )
        aux_rows: dict[str, Any] = {
            "val_auc": metric_values["val_auc"],
            "val_pr_auc": val_pr_auc,
            "val_logloss": val_logloss,
            "val_brier": val_brier,
            "val_lift_top10": val_lift10,
            "val_best_threshold": val_best_threshold,
            "val_f1_at_best": val_f1_at_best,
            "wall_seconds": total_seconds,
            "min_proba_std": proba_std,
            "proba_range": proba_range,
            "proba_unique_values": proba_unique,
        }
        if model_path is not None:
            aux_rows["model_path"] = model_path
        if extra:
            aux_rows.update(extra)
        _append_aux_rows(study_dir, exp_id, aux_rows)

    return primary_value


def evaluate_regression(
    model: Any,
    X_va: pd.DataFrame,
    y_va: pd.Series,
    *,
    exp_id: int | str,
    t0: float,
    fit_seconds: float,
    train_n: int,
    val_n: int,
    metric_name: str = "val_rmse",
    metric_goal: str = "lower",
    sample_weight: Any = None,
    tweedie_power: float | None = None,
    extra: dict[str, Any] | None = None,
    split_fingerprint: str | None = None,
    status: str = "ok",
    study_dir: str | Path | None = None,
) -> float:
    """Regression/severity twin of :func:`evaluate`.

    Computes the primary metric (RMSE by default) plus aux metrics (MAE, R^2).
    Same canonical-block format, aux sidecar, and `maybe_save_best` wiring as
    :func:`evaluate` — there is no `min_proba_std` guard here since there is
    no probability output to collapse.

    ``sample_weight`` (optional, strictly positive) threads into every metric;
    with ``None`` the numbers are bit-identical to the unweighted history.
    The deviance family (``val_poisson_deviance`` / ``val_gamma_deviance`` /
    ``val_tweedie_deviance``) uses the **exposure-weighted-rate convention**:
    ``y_va`` is the rate (e.g. claim counts / exposure) and ``sample_weight``
    is the exposure. Tweedie additionally requires ``tweedie_power`` (the
    contract's ``metric.power``, 1 < power < 2), echoed as an aux line so the
    manifest records it. A deviance primary also reports ``calibration_ratio``
    (sum of weighted predictions over weighted actuals — the pricing A/E
    sanity number). Deviance-family metrics are computed only when selected
    as the primary.
    """
    spec = get_metric_spec(metric_name, goal=metric_goal, task="regression")
    pred = np.asarray(model.predict(X_va), dtype=float)
    y_true = np.asarray(y_va, dtype=float)

    if pred.shape != y_true.shape:
        raise ValueError(
            f"regression predictions shape {pred.shape} does not match target {y_true.shape}"
        )
    if not np.all(np.isfinite(pred)) or not np.all(np.isfinite(y_true)):
        raise ValueError("regression predictions and targets must contain only finite values")
    weights = _validate_sample_weight(sample_weight, y_true.size)
    if spec.name not in DEVIANCE_METRICS and tweedie_power is not None:
        raise ValueError("tweedie_power applies only to val_tweedie_deviance")

    val_rmse = float(np.sqrt(mean_squared_error(y_true, pred, sample_weight=weights)))
    val_mae = float(mean_absolute_error(y_true, pred, sample_weight=weights))
    val_r2 = float(r2_score(y_true, pred, sample_weight=weights))
    metric_values = {
        "val_rmse": val_rmse,
        "val_mae": val_mae,
        "val_r2": val_r2,
    }
    calibration_ratio: float | None = None
    if spec.name in DEVIANCE_METRICS:
        metric_values[spec.name] = _deviance_value(
            spec.name,
            y_true,
            pred,
            sample_weight=weights,
            tweedie_power=tweedie_power,
        )
        w_eff = weights if weights is not None else np.ones_like(y_true)
        observed = float(np.sum(w_eff * y_true))
        if observed != 0.0:
            calibration_ratio = float(np.sum(w_eff * pred) / observed)
    for name, value in metric_values.items():
        _METRIC_SPECS[name].validate_value(value)
    primary_value = spec.validate_value(metric_values[spec.name])

    total_seconds = time.time() - t0

    _print_canonical_block(
        primary_value=primary_value,
        metric_name=metric_name,
        metric_goal=metric_goal,
        fit_seconds=fit_seconds,
        total_seconds=total_seconds,
        train_n=train_n,
        val_n=val_n,
        status=status,
    )
    print("--- aux_metrics ---")
    print(f"val_rmse:          {val_rmse:.6f}")
    print(f"val_mae:           {val_mae:.6f}")
    print(f"val_r2:            {val_r2:.6f}")
    if spec.name in DEVIANCE_METRICS:
        print(f"{spec.name}: {primary_value:.6f}")
        if calibration_ratio is not None:
            print(f"calibration_ratio: {calibration_ratio:.6f}")
        if spec.name == "val_tweedie_deviance":
            print(f"tweedie_power: {float(tweedie_power):.6g}")
    _print_wall_seconds(total_seconds, extra)
    _print_split_fingerprint(split_fingerprint)
    if extra:
        for k, v in extra.items():
            print(f"{k}: {v}")

    if study_dir is not None and _smoke_mode():
        print(_SMOKE_NOTICE)
    elif study_dir is not None:
        model_path = snapshot.maybe_save_best(
            model,
            exp_id=exp_id,
            metric_value=primary_value,
            metric_goal=metric_goal,
            study_dir=study_dir,
            primary_name=metric_name,
            track=os.environ.get("KLEIN_TRACK", "primary"),
        )
        aux_rows: dict[str, Any] = {
            "val_rmse": val_rmse,
            "val_mae": val_mae,
            "val_r2": val_r2,
            "wall_seconds": total_seconds,
        }
        if spec.name in DEVIANCE_METRICS:
            aux_rows[spec.name] = primary_value
            if calibration_ratio is not None:
                aux_rows["calibration_ratio"] = calibration_ratio
            if spec.name == "val_tweedie_deviance":
                aux_rows["tweedie_power"] = float(tweedie_power)
        if model_path is not None:
            aux_rows["model_path"] = model_path
        if extra:
            aux_rows.update(extra)
        _append_aux_rows(study_dir, exp_id, aux_rows)

    return primary_value


def evaluate_scalar(
    value: float,
    *,
    exp_id: int | str,
    metric_name: str,
    metric_goal: str,
    extra: dict[str, Any] | None = None,
    split_fingerprint: str | None = None,
    status: str = "ok",
    study_dir: str | Path | None = None,
    t0: float | None = None,
) -> float:
    """Canonical block + aux sidecar for a scalar result with no model/proba.

    For Monte-Carlo / simulation studies (e.g. Klein study 02's QLS severity
    lab) where there is no fitted model or held-out validation frame — the
    caller has already computed the one primary metric (e.g. absolute
    risk-loaded premium error % vs. known truth) as a plain scalar.
    `train_rows`/`val_rows`/`training_seconds` print as ``NA`` since there is
    no train/val split concept here; `total_seconds` is measured from `t0`
    when given, else 0.0.
    """
    spec = get_metric_spec(
        metric_name, goal=metric_goal, task="scalar", allow_custom=True
    )
    primary_value = spec.validate_value(value)
    total_seconds = 0.0 if t0 is None else time.time() - t0

    _print_canonical_block(
        primary_value=primary_value,
        metric_name=metric_name,
        metric_goal=metric_goal,
        fit_seconds=None,
        total_seconds=total_seconds,
        train_n=None,
        val_n=None,
        status=status,
    )
    print("--- aux_metrics ---")
    _print_wall_seconds(total_seconds, extra)
    _print_split_fingerprint(split_fingerprint)
    if extra:
        for k, v in extra.items():
            print(f"{k}: {v}")

    if study_dir is not None and _smoke_mode():
        print(_SMOKE_NOTICE)
    elif study_dir is not None:
        aux_rows: dict[str, Any] = {"wall_seconds": total_seconds}
        if extra:
            aux_rows.update(extra)
        _append_aux_rows(study_dir, exp_id, aux_rows)

    return primary_value


def evaluate_estimate(
    value: float,
    ci_low: float,
    ci_high: float,
    n: int,
    *,
    exp_id: int | str,
    metric_name: str,
    metric_goal: str,
    extra: dict[str, Any] | None = None,
    split_fingerprint: str | None = None,
    status: str = "ok",
    study_dir: str | Path | None = None,
    t0: float | None = None,
) -> float:
    """The printed block of an ESTIMATION cell: a value with its interval.

    One of the three cell shapes of a registered track
    (``references/registered-mode.md``).  A registered cell has no incumbent to
    beat — it measures — so what the ledger needs is the point estimate, and
    what a registered prediction reads is the interval::

        predictions:
          - {id: P4, statement: "the CI lower bound exceeds 70",
             rule: {key: ci_low, op: ">", value: 70}}

    ``ci_low``/``ci_high`` must be finite and ordered: an interval is the whole
    point of this shape, and a one-sided bound printed as ``NA`` would let a
    rule silently read "inconclusive" forever (use :func:`evaluate_scalar` plus
    ``extra=`` for a genuinely one-sided summary).  ``n`` is the number of
    observations the estimate rests on, so a reader can size the claim.

    ``split_fingerprint`` is the partition the estimate was computed on, the
    same explicit kwarg :func:`evaluate` / :func:`evaluate_regression` /
    :func:`evaluate_scalar` take.  It is PRINTED, never appended to
    ``aux_metrics.tsv``: passing a digest through ``extra=`` writes a 64-char
    hex string into the aux ledger's numeric ``value`` column, which is not a
    measurement.
    """
    spec = get_metric_spec(
        metric_name, goal=metric_goal, task="scalar", allow_custom=True
    )
    primary_value = spec.validate_value(value)
    low = _finite_or_raise(ci_low, "ci_low")
    high = _finite_or_raise(ci_high, "ci_high")
    if low > high:
        raise ValueError(f"ci_low {low!r} must not exceed ci_high {high!r}")
    if not (low <= primary_value <= high):
        raise ValueError(
            f"the estimate {primary_value!r} lies outside its own interval "
            f"[{low!r}, {high!r}] — an interval that excludes its point estimate "
            "is a sign convention bug, not a measurement"
        )
    count = _count_or_raise(n, "n")
    total_seconds = 0.0 if t0 is None else time.time() - t0

    _print_canonical_block(
        primary_value=primary_value,
        metric_name=metric_name,
        metric_goal=metric_goal,
        fit_seconds=None,
        total_seconds=total_seconds,
        train_n=None,
        val_n=None,
        status=status,
    )
    print("--- aux_metrics ---")
    print(f"ci_low:            {low:.6f}")
    print(f"ci_high:           {high:.6f}")
    print(f"n:                 {count}")
    _print_wall_seconds(total_seconds, extra)
    _print_split_fingerprint(split_fingerprint)
    _print_extra(extra)

    _write_aux(
        study_dir,
        exp_id,
        {"ci_low": low, "ci_high": high, "n": count, "wall_seconds": total_seconds},
        extra,
    )
    return primary_value


def evaluate_test(
    stat: float | None,
    p_value: float,
    effect: float | None,
    n: int,
    n_comparisons: int,
    *,
    exp_id: int | str,
    metric_name: str,
    metric_goal: str,
    alpha: float = 0.05,
    extra: dict[str, Any] | None = None,
    split_fingerprint: str | None = None,
    status: str = "ok",
    study_dir: str | Path | None = None,
    t0: float | None = None,
) -> float:
    """The printed block of a HYPOTHESIS-TEST cell; ``p_value`` is the primary metric.

    The ledger's summary scalar for a test cell is the p-value (``goal:
    lower``): it is the quantity a reader scans the ledger for, and every other
    printed key stays available to a registered rule (``{key: effect, op:
    ">=", value: 0.02}``).  ``stat`` and ``effect`` may be ``None`` or
    non-finite — an infinite t on a zero-spread cell is real — and print as
    ``NA``; a non-finite line would abort the whole run at the notary's parser.

    ``n_comparisons`` is the size of the family this test belongs to, declared
    BEFORE the test ran, and ``bonferroni_alpha = alpha / n_comparisons`` is
    printed from it.  Bonferroni is the crude bar; above one comparison the
    block also names the sharper instrument
    (:func:`kleinlib.metrology.family_maxt`, the sign-flip max-t guard over
    the FIXED family), because a selection guard is not a significance test
    and an unguarded family caps its claims at exploratory
    (``knowledge/research-discipline.md`` lesson 6).

    ``split_fingerprint`` is the explicit partition kwarg every other
    evaluator takes: printed, never written to ``aux_metrics.tsv``.
    """
    spec = get_metric_spec(
        metric_name, goal=metric_goal, task="scalar", allow_custom=True
    )
    p = spec.validate_value(p_value)
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p_value must lie in [0, 1], got {p!r}")
    count = _count_or_raise(n, "n")
    family = _count_or_raise(n_comparisons, "n_comparisons")
    if family < 1:
        raise ValueError("n_comparisons must be >= 1 — a test is its own family of one")
    alpha_value = _finite_or_raise(alpha, "alpha")
    if not 0.0 < alpha_value < 1.0:
        raise ValueError(f"alpha must lie in (0, 1), got {alpha_value!r}")
    bonferroni_alpha = alpha_value / family
    total_seconds = 0.0 if t0 is None else time.time() - t0

    _print_canonical_block(
        primary_value=p,
        metric_name=metric_name,
        metric_goal=metric_goal,
        fit_seconds=None,
        total_seconds=total_seconds,
        train_n=None,
        val_n=None,
        status=status,
    )
    print("--- aux_metrics ---")
    print(f"stat:              {_fmt_finite(stat)}")
    print(f"p_value:           {p:.6f}")
    print(f"effect:            {_fmt_finite(effect)}")
    print(f"n:                 {count}")
    print(f"n_comparisons:     {family}")
    print(f"bonferroni_alpha:  {bonferroni_alpha:.6g}")
    if family > 1:
        # A comment line: the notary's parser only reads `key: value` lines.
        print(
            f"# family of {family} comparisons — bonferroni_alpha {bonferroni_alpha:.6g} "
            "is the crude bar; kleinlib.metrology.family_maxt gives the sign-flip "
            "max-t guard over the FIXED family (a selection guard, not a "
            "significance test: it limits false detection, never effect size)"
        )
    _print_wall_seconds(total_seconds, extra)
    _print_split_fingerprint(split_fingerprint)
    _print_extra(extra)

    aux: dict[str, Any] = {
        "p_value": p,
        "n": count,
        "n_comparisons": family,
        "bonferroni_alpha": bonferroni_alpha,
        "wall_seconds": total_seconds,
    }
    if stat is not None and np.isfinite(stat):
        aux["stat"] = float(stat)
    if effect is not None and np.isfinite(effect):
        aux["effect"] = float(effect)
    _write_aux(study_dir, exp_id, aux, extra)
    return p


def evaluate_table(
    path: str | Path,
    summary: float,
    *,
    exp_id: int | str,
    metric_name: str,
    metric_goal: str,
    rows: int | None = None,
    extra: dict[str, Any] | None = None,
    split_fingerprint: str | None = None,
    status: str = "ok",
    study_dir: str | Path | None = None,
    t0: float | None = None,
) -> float:
    """The printed block of a TABLE cell: the table is the measurement.

    "One cell whose artifact is a 42-row table is lawful and often better than
    42 cells" (``references/registered-mode.md``): the table is hashed and
    citable as ``art:<alias>``, the summary scalar goes in the ledger, and the
    registered rules read printed keys.  Prints the three lines that make the
    table evidence rather than a file that happened to be written::

        artifact: sweeps/rq0_map.tsv
        rows:              42
        sha256:            8f21…

    The path must exist and, when ``study_dir`` is given, must live inside the
    study and is printed study-relative and POSIX — a path that escapes the
    study is refused here rather than becoming an unresolvable pin later.
    ``rows`` is counted from a ``.tsv``/``.csv`` header + data rows unless the
    caller passes it (any other artifact must).

    Under ``KLEIN_SMOKE=1`` a missing artifact is a notice, not an error: a
    smoke run does no work, so it has no table to hash.  ``klein run-one``
    force-clears the flag in its child, so a real cell that failed to write its
    table still crashes.

    ``split_fingerprint`` is the explicit partition kwarg every other
    evaluator takes: printed, never written to ``aux_metrics.tsv``.
    """
    spec = get_metric_spec(
        metric_name, goal=metric_goal, task="scalar", allow_custom=True
    )
    primary_value = spec.validate_value(summary)
    total_seconds = 0.0 if t0 is None else time.time() - t0
    artifact = Path(path)
    display = artifact.as_posix()
    if study_dir is not None:
        root = Path(study_dir).resolve()
        resolved = artifact if artifact.is_absolute() else (root / artifact)
        try:
            display = resolved.resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(
                f"artifact {artifact.as_posix()!r} escapes the study directory "
                f"{root} — a cell's evidence must live inside the study it belongs to"
            ) from exc
        artifact = resolved

    digest: str | None = None
    row_count = None if rows is None else _count_or_raise(rows, "rows")
    if not artifact.is_file():
        if not _smoke_mode():
            raise FileNotFoundError(
                f"artifact {display!r} does not exist — a cell that cannot produce "
                "its table has not measured anything"
            )
    else:
        digest = sha256_file(artifact)
        if row_count is None:
            row_count = _delimited_row_count(artifact)

    _print_canonical_block(
        primary_value=primary_value,
        metric_name=metric_name,
        metric_goal=metric_goal,
        fit_seconds=None,
        total_seconds=total_seconds,
        train_n=None,
        val_n=None,
        status=status,
    )
    print("--- aux_metrics ---")
    print(f"artifact: {display}")
    print(f"rows:              {_fmt_int(row_count)}")
    print(f"sha256:            {digest or 'NA'}")
    _print_wall_seconds(total_seconds, extra)
    _print_split_fingerprint(split_fingerprint)
    _print_extra(extra)

    aux: dict[str, Any] = {"artifact": display, "wall_seconds": total_seconds}
    if row_count is not None:
        aux["rows"] = row_count
    if digest is not None:
        aux["sha256"] = digest
    _write_aux(study_dir, exp_id, aux, extra)
    return primary_value


def _finite_or_raise(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric, got {value!r}") from exc
    if not np.isfinite(result):
        raise ValueError(f"{name} must be finite, got {result!r}")
    return result


def _count_or_raise(value: Any, name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc
    if result < 0:
        raise ValueError(f"{name} must be >= 0, got {result!r}")
    return result


def _fmt_finite(value: Any, spec: str = ".6f") -> str:
    """A float line, or ``NA`` when it is missing or non-finite.

    The notary REFUSES a non-finite `key: value` line (it aborts the whole
    run), so an infinite statistic prints as ``NA`` and lands nowhere the
    parser reads it — the number itself belongs in the cell's own table.
    """
    if value is None:
        return "NA"
    try:
        result = float(value)
    except (TypeError, ValueError):
        return "NA"
    return format(result, spec) if np.isfinite(result) else "NA"


def _delimited_row_count(path: Path) -> int | None:
    """Data rows (header excluded) of a .tsv/.csv artifact; None for anything else."""
    delimiter = {".tsv": "\t", ".csv": ","}.get(path.suffix.lower())
    if delimiter is None:
        return None
    with path.open("r", encoding="utf-8", newline="") as stream:
        return max(sum(1 for _ in csv.reader(stream, delimiter=delimiter)) - 1, 0)


def _print_extra(extra: dict[str, Any] | None) -> None:
    if extra:
        for key, value in extra.items():
            print(f"{key}: {value}")


def _write_aux(
    study_dir: str | Path | None,
    exp_id: int | str,
    rows: dict[str, Any],
    extra: dict[str, Any] | None,
) -> None:
    """Append the cell's aux rows unless smoke mode is suppressing every write."""
    if study_dir is None:
        return
    if _smoke_mode():
        print(_SMOKE_NOTICE)
        return
    aux = dict(rows)
    if extra:
        aux.update(extra)
    _append_aux_rows(study_dir, exp_id, aux)


def save_holdout_predictions(
    study_dir: str | Path,
    exp_id: int | str,
    *,
    y_true: Any,
    y_pred: Any,
    weight: Any = None,
    dims: Any = None,
    pred_b: Any = None,
    name_b: str = "y_pred_b",
) -> Path:
    """Write a per-row holdout predictions table for external eval tooling.

    The table lands at ``<study_dir>/predictions/<exp_id>_holdout.csv.gz``
    (the ``predictions/`` directory is gitignored — the table is a derived,
    regenerable artifact; the committed exhibit is whatever card or figure is
    built FROM it). Columns follow the pricing-eval-card convention:
    ``y_true`` (observed target), ``y_pred`` (holdout prediction), ``weight``
    (the exposure base, when given), one column per rating dimension in
    ``dims`` (a mapping ``name -> values`` or a DataFrame), and optionally a
    second model's prediction as ``name_b`` for double-lift comparisons.

    Two per-row conventions coexist deliberately:
    ``models/latest_val_preds.npz`` (see ``make_figures.py``) feeds the
    BUNDLED figure regeneration path; this table feeds EXTERNAL tools.
    Both are optional, both stay out of git. Re-exporting an experiment id
    overwrites its table (derived data, not evidence).
    """
    y = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    if y.ndim != 1 or y.size == 0:
        raise ValueError(f"y_true must be a non-empty 1-D array, got shape {y.shape}")
    if pred.shape != y.shape:
        raise ValueError(f"y_pred shape {pred.shape} does not match y_true {y.shape}")
    if not np.all(np.isfinite(y)) or not np.all(np.isfinite(pred)):
        raise ValueError("y_true and y_pred must contain only finite values")
    columns: dict[str, np.ndarray] = {"y_true": y, "y_pred": pred}
    weights = _validate_sample_weight(weight, y.size)
    if weights is not None:
        columns["weight"] = weights
    if dims is not None:
        dim_frame = pd.DataFrame(dims)
        if len(dim_frame) != y.size:
            raise ValueError(
                f"dims must have {y.size} rows, got {len(dim_frame)}"
            )
        for name in dim_frame.columns:
            if str(name) in columns or str(name) == name_b:
                raise ValueError(f"dim column {name!r} collides with a reserved column")
            columns[str(name)] = dim_frame[name].to_numpy()
    if pred_b is not None:
        b = np.asarray(pred_b, dtype=float)
        if b.shape != y.shape:
            raise ValueError(f"pred_b shape {b.shape} does not match y_true {y.shape}")
        if not np.all(np.isfinite(b)):
            raise ValueError("pred_b must contain only finite values")
        columns[name_b] = b
    out_dir = Path(study_dir) / "predictions"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{exp_id}_holdout.csv.gz"
    pd.DataFrame(columns).to_csv(path, index=False, compression="gzip")
    print(f"predictions: wrote {Path('predictions') / path.name} ({y.size:,} rows)")
    return path


def evaluate_with_inner_cv(
    model_factory,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    n_splits: int = 3,
    metric: str = "val_auc",
    groups: Any = None,
) -> tuple[float, list[float]]:
    """Inner stratified-k-fold CV on training data; returns (mean, fold_scores).

    Used for 'honest' HPO experiments
    that need an inner CV loop without double-using the held-out validation
    split for both early-stopping and trial-selection. `model_factory` must
    be a callable returning a fresh sklearn-compatible estimator each call.

    Pass ``groups`` (one label per row) whenever rows share an entity — a
    policy, a patient, a document, a simulation replicate — and the folds are
    built with ``StratifiedGroupKFold`` so no group straddles the inner split.
    Without it, an inner CV on grouped data leaks the same entity into both
    sides of every fold and reports a tuning score the outer split will not
    honour; the DATA gate's ``group-overlap`` row audits the OUTER split for
    exactly this, and nothing was auditing the inner one.
    """
    spec = get_metric_spec(metric, task="classification")
    if groups is None:
        splitter: Any = StratifiedKFold(
            n_splits=n_splits, shuffle=True, random_state=42
        )
        folds = splitter.split(X, y)
    else:
        group_labels = np.asarray(groups)
        if group_labels.ndim != 1 or group_labels.shape[0] != len(X):
            raise ValueError(
                f"groups must be 1-D with one label per row ({len(X)}), got shape "
                f"{group_labels.shape}"
            )
        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42)
        folds = splitter.split(X, y, groups=group_labels)
    scores: list[float] = []
    for _fold, (tr_idx, va_idx) in enumerate(folds):
        X_tr, X_va = X.iloc[tr_idx], X.iloc[va_idx]
        y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]
        m = model_factory()
        m.fit(X_tr, y_tr)
        p, _, _, _ = _validate_probabilities(
            _positive_class_probabilities(m, X_va, y_va),
            collapse_rtol=1e-12,
            legacy_min_std=None,
        )
        values, _ = _classification_metric_values(y_va, p)
        scores.append(spec.validate_value(values[spec.name]))
    mean_score = spec.validate_value(np.mean(scores))
    return mean_score, scores
