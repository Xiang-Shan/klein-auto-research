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
existing summarizer keeps parsing it unchanged. All three evaluator shapes
below (:func:`evaluate`, :func:`evaluate_regression`, :func:`evaluate_scalar`)
share that same canonical-block format via `_print_canonical_block`.

Hard guard (the MPS collapse war story): on Apple Silicon, torch
`DataLoader` + `TensorDataset` silently collapsed every prediction to a
near-constant value — no error, no warning, just a wrecked metric. `evaluate`
raises `RuntimeError` the instant predicted-probability std falls below
`min_proba_std`, so that failure mode is loud instead of silent.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

from . import schema, snapshot

__all__ = [
    "evaluate",
    "evaluate_regression",
    "evaluate_scalar",
    "evaluate_with_inner_cv",
]


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
    header = "\t".join(schema.AUX_COLUMNS)
    kept: list[str] = []
    if path.exists() and path.stat().st_size > 0:
        prefix = f"{exp_id}\t"
        kept = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line and line != header and not line.startswith(prefix)
        ]
    new_lines = [f"{exp_id}\t{metric}\t{value}" for metric, value in rows.items()]
    path.write_text("\n".join([header, *kept, *new_lines]) + "\n", encoding="utf-8")


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
    status: str = "ok",
    min_proba_std: float = 0.01,
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

    Raises `RuntimeError` if the predicted-probability std is below
    `min_proba_std` — the MPS `DataLoader`/`TensorDataset` collapse war
    story (see module docstring). Returns the ROC-AUC as a plain float.
    """
    p = np.asarray(model.predict_proba(X_va)[:, 1], dtype=float)

    proba_std = float(np.std(p))
    if proba_std < min_proba_std:
        raise RuntimeError(
            f"Collapsed predictions: predicted-probability std={proba_std:.6g} "
            f"is below min_proba_std={min_proba_std}. This is the MPS "
            "DataLoader+TensorDataset collapse war story (predictions "
            "silently constant) — if this is a torch model, use "
            "kleinlib.torch_loop's index-shuffle batching instead of "
            "DataLoader/TensorDataset; otherwise look for a degenerate fit "
            "(single-class target, saturated regularization, etc.)."
        )

    val_auc = float(roc_auc_score(y_va, p))
    val_pr_auc = float(average_precision_score(y_va, p))
    val_logloss = float(log_loss(y_va, p, labels=[0, 1]))
    val_brier = float(brier_score_loss(y_va, p))

    order = np.argsort(-p)
    decile_n = max(1, len(p) // 10)
    top_idx = order[:decile_n]
    base_rate = float(np.asarray(y_va).mean())
    val_lift10 = (
        float(np.asarray(y_va)[top_idx].mean()) / base_rate if base_rate > 0 else 0.0
    )

    thresholds = np.linspace(0.01, 0.99, 99)
    f1s = [f1_score(y_va, (p > t).astype(int), zero_division=0) for t in thresholds]
    best_idx = int(np.argmax(f1s))
    val_best_threshold = float(thresholds[best_idx])
    val_f1_at_best = float(f1s[best_idx])

    total_seconds = time.time() - t0

    _print_canonical_block(
        primary_value=val_auc,
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
    if extra:
        for k, v in extra.items():
            print(f"{k}: {v}")

    if study_dir is not None:
        model_path = snapshot.maybe_save_best(
            model,
            exp_id=exp_id,
            metric_value=val_auc,
            metric_goal=metric_goal,
            study_dir=study_dir,
            primary_name=metric_name,
        )
        aux_rows: dict[str, Any] = {
            "val_pr_auc": val_pr_auc,
            "val_logloss": val_logloss,
            "val_brier": val_brier,
            "val_lift_top10": val_lift10,
            "val_best_threshold": val_best_threshold,
            "val_f1_at_best": val_f1_at_best,
            "wall_seconds": total_seconds,
            "min_proba_std": proba_std,
        }
        if model_path is not None:
            aux_rows["model_path"] = model_path
        if extra:
            aux_rows.update(extra)
        _append_aux_rows(study_dir, exp_id, aux_rows)

    return val_auc


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
    extra: dict[str, Any] | None = None,
    status: str = "ok",
    study_dir: str | Path | None = None,
) -> float:
    """Regression/severity twin of :func:`evaluate`.

    Computes the primary metric (RMSE) plus aux metrics (MAE, R^2). Same
    canonical-block format, aux sidecar, and `maybe_save_best` wiring as
    :func:`evaluate` — there is no `min_proba_std` guard here since there is
    no probability output to collapse.
    """
    pred = np.asarray(model.predict(X_va), dtype=float)
    y_true = np.asarray(y_va, dtype=float)

    val_rmse = float(np.sqrt(mean_squared_error(y_true, pred)))
    val_mae = float(mean_absolute_error(y_true, pred))
    val_r2 = float(r2_score(y_true, pred))

    total_seconds = time.time() - t0

    _print_canonical_block(
        primary_value=val_rmse,
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
    if extra:
        for k, v in extra.items():
            print(f"{k}: {v}")

    if study_dir is not None:
        model_path = snapshot.maybe_save_best(
            model,
            exp_id=exp_id,
            metric_value=val_rmse,
            metric_goal=metric_goal,
            study_dir=study_dir,
            primary_name=metric_name,
        )
        aux_rows: dict[str, Any] = {
            "val_rmse": val_rmse,
            "val_mae": val_mae,
            "val_r2": val_r2,
            "wall_seconds": total_seconds,
        }
        if model_path is not None:
            aux_rows["model_path"] = model_path
        if extra:
            aux_rows.update(extra)
        _append_aux_rows(study_dir, exp_id, aux_rows)

    return val_rmse


def evaluate_scalar(
    value: float,
    *,
    exp_id: int | str,
    metric_name: str,
    metric_goal: str,
    extra: dict[str, Any] | None = None,
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
    total_seconds = 0.0 if t0 is None else time.time() - t0

    _print_canonical_block(
        primary_value=float(value),
        metric_name=metric_name,
        metric_goal=metric_goal,
        fit_seconds=None,
        total_seconds=total_seconds,
        train_n=None,
        val_n=None,
        status=status,
    )
    print("--- aux_metrics ---")
    if extra:
        for k, v in extra.items():
            print(f"{k}: {v}")

    if study_dir is not None:
        aux_rows: dict[str, Any] = {"wall_seconds": total_seconds}
        if extra:
            aux_rows.update(extra)
        _append_aux_rows(study_dir, exp_id, aux_rows)

    return float(value)


def evaluate_with_inner_cv(
    model_factory,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    n_splits: int = 3,
    metric: str = "val_auc",
) -> tuple[float, list[float]]:
    """Inner stratified-k-fold CV on training data; returns (mean, fold_scores).

    Kept from the campaign source as-is. Used for 'honest' HPO experiments
    that need an inner CV loop without double-using the held-out validation
    split for both early-stopping and trial-selection. `model_factory` must
    be a callable returning a fresh sklearn-compatible estimator each call.
    """
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    scores: list[float] = []
    for fold, (tr_idx, va_idx) in enumerate(skf.split(X, y)):
        X_tr, X_va = X.iloc[tr_idx], X.iloc[va_idx]
        y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]
        m = model_factory()
        m.fit(X_tr, y_tr)
        p = m.predict_proba(X_va)[:, 1]
        scores.append(roc_auc_score(y_va, p))
    return float(np.mean(scores)), scores
