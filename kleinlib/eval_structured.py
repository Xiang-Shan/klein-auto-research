"""Ranking, survival and segmentation evaluators (Klein 2.3).

Each prints the canonical block every evaluator prints, so the notary, the
guardrails and the prediction rules treat them like any other.  The metric
definitions are the textbook ones, written out in numpy so a reader can check
them line by line:

* **ranking** (retrieval, recommendation, re-ranking): per query, ``NDCG@k`` with
  linear gain ``rel`` and ``log2(rank + 1)`` discount (scikit-learn's
  ``ndcg_score`` convention; identical to the exponential-gain form for binary
  relevance); ``MRR`` —
  the reciprocal rank of the first relevant item (0 when none is retrieved);
  ``recall@k`` — the share of a query's relevant items in its top k.  Queries
  with no relevant item are excluded from all three and counted.
* **survival**: Harrell's concordance index over comparable pairs (the shorter
  time is an observed event); a HIGHER risk score predicts a SHORTER time; ties
  in risk count one half; ties in time are not comparable.
* **segmentation**: per-class IoU ``TP / (TP + FP + FN)`` and Dice
  ``2TP / (2TP + FP + FN)`` from the pixel confusion matrix, averaged over the
  classes present in either truth or prediction; ``ignore_index`` pixels are
  dropped.  Detection mAP is deliberately absent: VOC and COCO conventions
  differ, and an evaluator no study has exercised is not one Klein ships.
"""

from __future__ import annotations

import time
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

__all__ = [
    "concordance_index",
    "evaluate_ranking",
    "evaluate_segmentation",
    "evaluate_survival",
    "ranking_metrics",
    "segmentation_metrics",
]


def _emit(
    *,
    spec,
    primary_value: float,
    aux: dict[str, float],
    n: int,
    exp_id: int | str,
    t0: float | None,
    fit_seconds: float | None,
    train_n: int | None,
    extra: dict[str, Any] | None,
    split_fingerprint: str | None,
    status: str,
    study_dir: str | Path | None,
) -> float:
    total_seconds = 0.0 if t0 is None else time.time() - t0
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
    for key, value in aux.items():
        print(f"{key}: {value:.6f}" if isinstance(value, float) else f"{key}: {value}")
    _print_wall_seconds(total_seconds, extra)
    _print_split_fingerprint(split_fingerprint)
    if extra:
        for key, value in extra.items():
            print(f"{key}: {value}")
    if study_dir is not None and _smoke_mode():
        print(_SMOKE_NOTICE)
    elif study_dir is not None:
        rows: dict[str, Any] = {**aux, "wall_seconds": total_seconds}
        if extra:
            rows.update(extra)
        _append_aux_rows(study_dir, exp_id, rows)
    return primary_value


# ---------------------------------------------------------------------------
# ranking
# ---------------------------------------------------------------------------


def ranking_metrics(query_ids: Any, relevance: Any, scores: Any, *, k: int = 10) -> dict[str, float]:
    """Mean NDCG@k, MRR and recall@k over queries with at least one relevant item."""
    q = np.asarray(query_ids).astype(str)
    rel = np.asarray(relevance, dtype=float)
    s = np.asarray(scores, dtype=float)
    if not (q.shape == rel.shape == s.shape) or q.ndim != 1 or q.size == 0:
        raise ValueError("query_ids, relevance and scores must be equal-length non-empty 1-D arrays")
    if not np.all(np.isfinite(s)) or not np.all(np.isfinite(rel)) or np.any(rel < 0):
        raise ValueError("scores must be finite and relevance finite and non-negative")
    if k < 1:
        raise ValueError("k must be >= 1")
    ndcg: list[float] = []
    mrr: list[float] = []
    recall: list[float] = []
    skipped = 0
    for query in np.unique(q):
        mask = q == query
        r, sc = rel[mask], s[mask]
        if not np.any(r > 0):
            skipped += 1
            continue
        order = np.argsort(-sc, kind="stable")
        ranked = r[order]
        discounts = 1.0 / np.log2(np.arange(2, min(k, ranked.size) + 2))
        dcg = float(np.sum(ranked[:k] * discounts))
        ideal = np.sort(r)[::-1]
        idcg = float(np.sum(ideal[:k] * discounts[: min(k, ideal.size)]))
        ndcg.append(dcg / idcg if idcg > 0 else 0.0)
        first = np.flatnonzero(ranked > 0)
        mrr.append(1.0 / (first[0] + 1) if first.size else 0.0)
        recall.append(float(np.sum(ranked[:k] > 0) / np.sum(r > 0)))
    if not ndcg:
        raise ValueError("no query has a relevant item")
    return {
        "val_ndcg_at_k": float(np.mean(ndcg)),
        "val_mrr": float(np.mean(mrr)),
        "val_recall_at_k": float(np.mean(recall)),
        "n_queries": float(len(ndcg)),
        "n_queries_without_relevant": float(skipped),
    }


def evaluate_ranking(
    query_ids: Any,
    relevance: Any,
    scores: Any,
    *,
    exp_id: int | str,
    k: int = 10,
    metric_name: str = "val_ndcg_at_k",
    metric_goal: str | None = None,
    t0: float | None = None,
    fit_seconds: float | None = None,
    train_n: int | None = None,
    extra: dict[str, Any] | None = None,
    split_fingerprint: str | None = None,
    status: str = "ok",
    study_dir: str | Path | None = None,
) -> float:
    spec = get_metric_spec(metric_name, goal=metric_goal, task="scalar")
    if spec.name not in ("val_ndcg_at_k", "val_mrr", "val_recall_at_k"):
        raise ValueError(f"evaluate_ranking scores val_ndcg_at_k | val_mrr | val_recall_at_k, not {spec.name!r}")
    metrics = ranking_metrics(query_ids, relevance, scores, k=k)
    primary_value = spec.validate_value(metrics[spec.name])
    aux = {
        "val_ndcg_at_k": metrics["val_ndcg_at_k"],
        "val_mrr": metrics["val_mrr"],
        "val_recall_at_k": metrics["val_recall_at_k"],
        "rank_k": int(k),
        "n_queries": int(metrics["n_queries"]),
        "n_queries_without_relevant": int(metrics["n_queries_without_relevant"]),
    }
    return _emit(
        spec=spec, primary_value=primary_value, aux=aux, n=int(np.asarray(scores).size),
        exp_id=exp_id, t0=t0, fit_seconds=fit_seconds, train_n=train_n, extra=extra,
        split_fingerprint=split_fingerprint, status=status, study_dir=study_dir,
    )


# ---------------------------------------------------------------------------
# survival
# ---------------------------------------------------------------------------


def concordance_index(time_: Any, event: Any, risk: Any) -> tuple[float, int]:
    """Harrell's C and the number of comparable pairs (higher risk = shorter time)."""
    t = np.asarray(time_, dtype=float)
    e = np.asarray(event).astype(bool)
    r = np.asarray(risk, dtype=float)
    if not (t.shape == e.shape == r.shape) or t.ndim != 1 or t.size < 2:
        raise ValueError("time, event and risk must be equal-length 1-D arrays with >= 2 rows")
    if not (np.all(np.isfinite(t)) and np.all(np.isfinite(r))):
        raise ValueError("time and risk must be finite")
    concordant = 0.0
    comparable = 0
    for i in np.flatnonzero(e):
        later = t > t[i]
        if not later.any():
            continue
        comparable += int(later.sum())
        concordant += float(np.sum(r[i] > r[later]) + 0.5 * np.sum(r[i] == r[later]))
    if comparable == 0:
        raise ValueError("no comparable pairs (no observed event precedes another time)")
    return concordant / comparable, comparable


def evaluate_survival(
    time_: Any,
    event: Any,
    risk: Any,
    *,
    exp_id: int | str,
    metric_name: str = "val_c_index",
    metric_goal: str | None = None,
    t0: float | None = None,
    fit_seconds: float | None = None,
    train_n: int | None = None,
    extra: dict[str, Any] | None = None,
    split_fingerprint: str | None = None,
    status: str = "ok",
    study_dir: str | Path | None = None,
) -> float:
    spec = get_metric_spec(metric_name, goal=metric_goal, task="scalar")
    if spec.name != "val_c_index":
        raise ValueError(f"evaluate_survival scores val_c_index, not {spec.name!r}")
    c_index, pairs = concordance_index(time_, event, risk)
    primary_value = spec.validate_value(c_index)
    events = int(np.asarray(event).astype(bool).sum())
    aux = {"n_events": events, "comparable_pairs": pairs}
    return _emit(
        spec=spec, primary_value=primary_value, aux=aux, n=int(np.asarray(time_).size),
        exp_id=exp_id, t0=t0, fit_seconds=fit_seconds, train_n=train_n, extra=extra,
        split_fingerprint=split_fingerprint, status=status, study_dir=study_dir,
    )


# ---------------------------------------------------------------------------
# segmentation
# ---------------------------------------------------------------------------


def segmentation_metrics(
    y_true: Any, y_pred: Any, *, n_classes: int, ignore_index: int | None = None
) -> dict[str, float]:
    t = np.asarray(y_true).ravel()
    p = np.asarray(y_pred).ravel()
    if t.shape != p.shape or t.size == 0:
        raise ValueError("y_true and y_pred masks must have the same, non-empty shape")
    if ignore_index is not None:
        keep = t != ignore_index
        t, p = t[keep], p[keep]
    if np.any((t < 0) | (t >= n_classes)) or np.any((p < 0) | (p >= n_classes)):
        raise ValueError(f"mask values must lie in [0, {n_classes})")
    confusion = np.bincount(t.astype(np.int64) * n_classes + p.astype(np.int64), minlength=n_classes * n_classes)
    confusion = confusion.reshape(n_classes, n_classes).astype(float)
    tp = np.diag(confusion)
    fp = confusion.sum(axis=0) - tp
    fn = confusion.sum(axis=1) - tp
    present = (tp + fp + fn) > 0
    iou = np.divide(tp, tp + fp + fn, out=np.zeros(n_classes), where=present)
    dice = np.divide(2 * tp, 2 * tp + fp + fn, out=np.zeros(n_classes), where=present)
    return {
        "val_miou": float(iou[present].mean()),
        "val_dice": float(dice[present].mean()),
        "pixel_accuracy": float(tp.sum() / max(t.size, 1)),
        "n_classes_present": float(present.sum()),
    }


def evaluate_segmentation(
    y_true: Any,
    y_pred: Any,
    *,
    n_classes: int,
    exp_id: int | str,
    ignore_index: int | None = None,
    metric_name: str = "val_miou",
    metric_goal: str | None = None,
    t0: float | None = None,
    fit_seconds: float | None = None,
    train_n: int | None = None,
    extra: dict[str, Any] | None = None,
    split_fingerprint: str | None = None,
    status: str = "ok",
    study_dir: str | Path | None = None,
) -> float:
    spec = get_metric_spec(metric_name, goal=metric_goal, task="scalar")
    if spec.name not in ("val_miou", "val_dice"):
        raise ValueError(f"evaluate_segmentation scores val_miou | val_dice, not {spec.name!r}")
    metrics = segmentation_metrics(y_true, y_pred, n_classes=n_classes, ignore_index=ignore_index)
    for name in ("val_miou", "val_dice"):
        _METRIC_SPECS[name].validate_value(metrics[name])
    primary_value = spec.validate_value(metrics[spec.name])
    aux = {
        "val_miou": metrics["val_miou"],
        "val_dice": metrics["val_dice"],
        "pixel_accuracy": metrics["pixel_accuracy"],
        "n_classes_present": int(metrics["n_classes_present"]),
    }
    n_items = int(np.asarray(y_true).shape[0]) if np.asarray(y_true).ndim > 2 else 1
    return _emit(
        spec=spec, primary_value=primary_value, aux=aux, n=n_items,
        exp_id=exp_id, t0=t0, fit_seconds=fit_seconds, train_n=train_n, extra=extra,
        split_fingerprint=split_fingerprint, status=status, study_dir=study_dir,
    )
