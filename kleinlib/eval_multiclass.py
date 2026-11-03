"""Multiclass classification evaluator (Klein 2.3).

``kleinlib.eval.evaluate`` is binary by design (labels {0,1}, ``predict_proba``
shape (n, 2)).  Image classification, document classification and most
benchmark tasks have K > 2 classes; before 2.3 they fell back to
``evaluate_scalar`` and lost the collapse guard, the row counts and the chance
audit.  ``evaluate_multiclass`` takes the predictions as ARRAYS (any model —
a torch network, a gradient-boosted ensemble, an API) and prints the same
canonical block every evaluator prints.

Metrics (all registered in ``kleinlib.eval`` with task ``classification``):

* ``val_accuracy`` — fraction correct (argmax of ``proba`` or ``y_pred``)
* ``val_balanced_accuracy`` — mean per-class recall (chance = 1/K)
* ``val_macro_f1`` — unweighted mean of per-class F1
* ``val_top5_accuracy`` — true class among the 5 highest scores (needs ``proba``)
* ``val_mlogloss`` — multiclass cross-entropy (needs ``proba``)
* ``val_ece`` — expected calibration error of the top-class confidence,
  equal-width bins (needs ``proba``)

The confusion matrix is written to ``tables/confusion_<exp>.tsv`` (``…_s<seed>.tsv``
under a seed array, one per seed) and pinned
with an ``artifact:`` line, so a claim about which classes are confused has a
hashed home.
"""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .eval import (
    _METRIC_SPECS,
    _SMOKE_NOTICE,
    _append_aux_rows,
    _print_canonical_block,
    _print_split_fingerprint,
    _print_wall_seconds,
    _smoke_mode,
    get_metric_spec,
)

__all__ = ["evaluate_multiclass", "multiclass_metrics"]


def _labels_and_index(y_true: np.ndarray, labels: Sequence[Any] | None, k: int | None) -> list[Any]:
    if labels is not None:
        return list(labels)
    present = sorted({item.item() if hasattr(item, "item") else item for item in y_true})
    if k is not None and k > len(present):
        # proba columns beyond the observed labels: assume 0..K-1 integer classes
        return list(range(k))
    return present


def _ece(confidence: np.ndarray, correct: np.ndarray, bins: int) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    n = len(confidence)
    for low, high in zip(edges[:-1], edges[1:], strict=True):
        mask = (confidence > low) & (confidence <= high) if low > 0 else (confidence >= low) & (confidence <= high)
        if mask.any():
            total += mask.sum() / n * abs(correct[mask].mean() - confidence[mask].mean())
    return float(total)


def multiclass_metrics(
    y_true: Any,
    proba: Any = None,
    *,
    y_pred: Any = None,
    labels: Sequence[Any] | None = None,
    top_k: int = 5,
    ece_bins: int = 15,
) -> tuple[dict[str, float], np.ndarray, list[Any]]:
    """``(metrics, confusion, labels)`` — pure computation, no printing.

    ``proba`` is (n, K) with columns in ``labels`` order; rows must be finite,
    within [0, 1] and sum to 1 (within 1e-3).  Without ``proba``, ``y_pred``
    gives hard predictions and only the three hard-label metrics are returned.
    """
    y = np.asarray(y_true)
    if y.ndim != 1 or y.size == 0:
        raise ValueError(f"y_true must be a non-empty 1-D array, got shape {y.shape}")
    p = None
    if proba is not None:
        p = np.asarray(proba, dtype=float)
        if p.ndim != 2 or p.shape[0] != y.size or p.shape[1] < 2:
            raise ValueError(f"proba must have shape (n, K>=2) with n={y.size}, got {p.shape}")
        if not np.all(np.isfinite(p)):
            raise ValueError("predicted probabilities contain non-finite values")
        if np.any((p < 0) | (p > 1)):
            raise ValueError("predicted probabilities must lie in [0, 1]")
        sums = p.sum(axis=1)
        if np.any(np.abs(sums - 1.0) > 1e-3):
            raise ValueError(
                "each proba row must sum to 1 (softmax output); max deviation "
                f"{float(np.max(np.abs(sums - 1.0))):.3g}"
            )
    elif y_pred is None:
        raise ValueError("pass proba (n, K) or y_pred")
    label_list = _labels_and_index(y, labels, p.shape[1] if p is not None else None)
    if p is not None and p.shape[1] != len(label_list):
        raise ValueError(f"proba has {p.shape[1]} columns but labels has {len(label_list)}")
    position = {label: i for i, label in enumerate(label_list)}
    unknown = sorted({str(v) for v in y.tolist() if v not in position})
    if unknown:
        raise ValueError(f"y_true holds labels not in labels: {unknown[:5]}")
    true_idx = np.array([position[v] for v in y.tolist()])
    if p is not None:
        pred_idx = p.argmax(axis=1)
    else:
        hard = np.asarray(y_pred)
        missing = sorted({str(v) for v in hard.tolist() if v not in position})
        if missing:
            raise ValueError(f"y_pred holds labels not in labels: {missing[:5]}")
        pred_idx = np.array([position[v] for v in hard.tolist()])
    k = len(label_list)
    if len(np.unique(true_idx)) > 1 and len(np.unique(pred_idx)) == 1:
        raise RuntimeError(
            "Collapsed predictions: every item was assigned the same class "
            f"({label_list[int(pred_idx[0])]!r}) while the truth holds "
            f"{len(np.unique(true_idx))} classes — inspect the fit for degeneracy "
            "(the MPS DataLoader war story; a dead network; a constant head)"
        )
    confusion = np.zeros((k, k), dtype=np.int64)
    np.add.at(confusion, (true_idx, pred_idx), 1)
    tp = np.diag(confusion).astype(float)
    support = confusion.sum(axis=1).astype(float)
    predicted = confusion.sum(axis=0).astype(float)
    recall = np.divide(tp, support, out=np.zeros(k), where=support > 0)
    precision = np.divide(tp, predicted, out=np.zeros(k), where=predicted > 0)
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros(k), where=(precision + recall) > 0)
    present = support > 0
    metrics: dict[str, float] = {
        "val_accuracy": float(tp.sum() / y.size),
        "val_balanced_accuracy": float(recall[present].mean()),
        "val_macro_f1": float(f1[present].mean()),
    }
    if p is not None:
        eps = 1e-15
        metrics["val_mlogloss"] = float(-np.mean(np.log(np.clip(p[np.arange(y.size), true_idx], eps, 1.0))))
        kk = min(top_k, k)
        top = np.argsort(-p, axis=1, kind="stable")[:, :kk]
        metrics["val_top5_accuracy"] = float(np.mean((top == true_idx[:, None]).any(axis=1)))
        confidence = p.max(axis=1)
        metrics["val_ece"] = _ece(confidence, (pred_idx == true_idx).astype(float), ece_bins)
    for i, label in enumerate(label_list):
        metrics[f"val_recall__{label}"] = float(recall[i])
    return metrics, confusion, label_list


def evaluate_multiclass(
    y_true: Any,
    proba: Any = None,
    *,
    y_pred: Any = None,
    labels: Sequence[Any] | None = None,
    exp_id: int | str,
    metric_name: str = "val_macro_f1",
    metric_goal: str | None = None,
    t0: float | None = None,
    fit_seconds: float | None = None,
    train_n: int | None = None,
    top_k: int = 5,
    ece_bins: int = 15,
    extra: dict[str, Any] | None = None,
    split_fingerprint: str | None = None,
    status: str = "ok",
    study_dir: str | Path | None = None,
) -> float:
    """Canonical block + aux sidecar + pinned confusion table for a K-class task."""
    spec = get_metric_spec(metric_name, goal=metric_goal, task="classification")
    if spec.name not in _MULTICLASS_METRICS:
        raise ValueError(
            f"evaluate_multiclass scores {sorted(_MULTICLASS_METRICS)}, not {spec.name!r} "
            "(binary metrics belong to kleinlib.eval.evaluate)"
        )
    metrics, confusion, label_list = multiclass_metrics(
        y_true, proba, y_pred=y_pred, labels=labels, top_k=top_k, ece_bins=ece_bins
    )
    if spec.name not in metrics:
        raise ValueError(f"{spec.name} needs proba (n, K), not hard predictions")
    for name in _MULTICLASS_METRICS:
        if name in metrics:
            _METRIC_SPECS[name].validate_value(metrics[name])
    primary_value = spec.validate_value(metrics[spec.name])
    total_seconds = 0.0 if t0 is None else time.time() - t0
    n = int(np.asarray(y_true).size)

    table_rel: str | None = None
    writing = study_dir is not None and not _smoke_mode()
    if writing:
        # Under a seed array (KLEIN_SEED set by the notary) every seed pins its own
        # table; without one the name is unchanged.
        seed = os.environ.get("KLEIN_SEED")
        table_rel = f"tables/confusion_{exp_id}{f'_s{seed}' if seed is not None else ''}.tsv"
        path = Path(study_dir) / table_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        header = "true\\pred\t" + "\t".join(str(label) for label in label_list)
        rows = [
            f"{label}\t" + "\t".join(str(int(v)) for v in confusion[i])
            for i, label in enumerate(label_list)
        ]
        path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")

    _print_canonical_block(
        primary_value=primary_value,
        metric_name=spec.name,
        metric_goal=spec.goal,
        fit_seconds=fit_seconds,
        total_seconds=total_seconds,
        train_n=train_n,
        val_n=n,
        status=status,
    )
    print("--- aux_metrics ---")
    for name in ("val_accuracy", "val_balanced_accuracy", "val_macro_f1", "val_top5_accuracy", "val_mlogloss", "val_ece"):
        if name in metrics:
            print(f"{name}: {metrics[name]:.6f}")
    print(f"n_classes:         {len(label_list)}")
    _print_wall_seconds(total_seconds, extra)
    _print_split_fingerprint(split_fingerprint)
    if extra:
        for key, value in extra.items():
            print(f"{key}: {value}")
    if table_rel is not None:
        print(f"artifact: {table_rel}")
    if study_dir is not None and _smoke_mode():
        print(_SMOKE_NOTICE)
    elif writing:
        aux = {key: value for key, value in metrics.items()}
        aux["n_classes"] = len(label_list)
        aux["wall_seconds"] = total_seconds
        if extra:
            aux.update(extra)
        _append_aux_rows(study_dir, exp_id, aux)
    return primary_value


_MULTICLASS_METRICS = (
    "val_accuracy",
    "val_balanced_accuracy",
    "val_macro_f1",
    "val_top5_accuracy",
    "val_mlogloss",
    "val_ece",
)
