"""Per-item evaluator — benchmarks, LLM evaluations, any score over a set of items (Klein 2.3).

An LLM benchmark, a retrieval suite, a theorem set, a battery of CV test images —
each is a set of ITEMS, each item scored (exact match, pass@k over n samples, a
judge's score).  Two facts make per-item scoring different from a single
validation number:

1. **The item is the unit of uncertainty.**  A 400-question benchmark accuracy of
   0.62 carries a sampling error of a few points; two prompts compared on the
   SAME items should be compared item by item (paired), not as two marginal
   means.  So the evaluator writes the per-item table, pins it with an
   ``artifact:`` line, and prints a bootstrap interval over items (or over
   clusters of items, ``group``) with a FIXED bootstrap seed, so a replay of the
   run reproduces the interval bit for bit.
2. **pass@k is an estimator, not a fraction.**  With ``n`` samples per item of
   which ``c`` are correct, the unbiased estimate of "at least one of k draws is
   correct" is ``1 - C(n-c, k) / C(n, k)`` (Chen et al. 2021, *Evaluating Large
   Language Models Trained on Code*), not ``c > 0``.

Metrics (registered in ``kleinlib.eval``, task ``scalar``, goal ``higher``):
``exact_match``, ``item_accuracy``, ``pass_at_k``, ``mean_item_score``.  Any other
name is allowed with an explicit ``metric_goal`` (a custom judged score).
"""

from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .eval import (
    _SMOKE_NOTICE,
    _append_aux_rows,
    _print_canonical_block,
    _print_split_fingerprint,
    _print_wall_seconds,
    _smoke_mode,
    get_metric_spec,
)

__all__ = ["bootstrap_mean_ci", "evaluate_items", "pass_at_k", "read_item_table"]

#: The bootstrap seed every item evaluator uses: a replay must reproduce the CI.
BOOTSTRAP_SEED = 20260301


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k for one item: ``1 - C(n-c, k) / C(n, k)``."""
    if not (isinstance(n, (int, np.integer)) and isinstance(c, (int, np.integer))):
        raise ValueError("n and c must be integers")
    if n < 1 or c < 0 or c > n:
        raise ValueError(f"need 0 <= c <= n and n >= 1, got n={n}, c={c}")
    if k < 1 or k > n:
        raise ValueError(f"k must satisfy 1 <= k <= n (n={n}), got {k}")
    if n - c < k:
        return 1.0
    # Product form avoids huge binomials: prod_{i=n-c+1}^{n} (1 - k/i)
    return float(1.0 - np.prod(1.0 - k / np.arange(n - c + 1, n + 1)))


def bootstrap_mean_ci(
    scores: np.ndarray,
    *,
    groups: np.ndarray | None = None,
    n_boot: int = 2000,
    ci: float = 0.95,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float]:
    """Percentile bootstrap CI of the mean, resampling items (or whole clusters)."""
    values = np.asarray(scores, dtype=float)
    if values.size == 0:
        raise ValueError("no items to bootstrap")
    rng = np.random.default_rng(seed)
    if groups is None:
        draws = rng.integers(0, values.size, size=(n_boot, values.size))
        means = values[draws].mean(axis=1)
    else:
        labels, inverse = np.unique(np.asarray(groups).astype(str), return_inverse=True)
        sums = np.bincount(inverse, weights=values, minlength=labels.size)
        counts = np.bincount(inverse, minlength=labels.size).astype(float)
        draws = rng.integers(0, labels.size, size=(n_boot, labels.size))
        means = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    alpha = (1.0 - ci) / 2.0
    low, high = np.quantile(means, [alpha, 1.0 - alpha])
    return float(low), float(high)


def read_item_table(path: str | Path) -> pd.DataFrame:
    """A per-item table written by :func:`evaluate_items` (ids as text)."""
    return pd.read_csv(path, sep="\t", dtype={"item_id": str})


def evaluate_items(
    items: pd.DataFrame | dict[str, Any],
    *,
    exp_id: int | str,
    metric_name: str = "item_accuracy",
    metric_goal: str | None = None,
    k: int | None = None,
    group_column: str | None = None,
    n_boot: int = 2000,
    ci: float = 0.95,
    t0: float | None = None,
    table_name: str | None = None,
    extra: dict[str, Any] | None = None,
    split_fingerprint: str | None = None,
    status: str = "ok",
    study_dir: str | Path | None = None,
) -> float:
    """Score a set of items; print the canonical block; pin the per-item table.

    ``items`` has an ``item_id`` column and EITHER a ``score`` column (0/1 for
    exact match / accuracy, any finite number for a judged score) OR, for
    ``pass_at_k``, the columns ``n`` (samples drawn) and ``c`` (samples correct)
    plus ``k=``.  ``group_column`` names a cluster column (passage, template,
    source document): the interval then resamples whole clusters.
    """
    frame = pd.DataFrame(items).copy()
    if "item_id" not in frame.columns:
        raise ValueError("items need an item_id column")
    frame["item_id"] = frame["item_id"].astype(str)
    if frame["item_id"].duplicated().any():
        dup = frame.loc[frame["item_id"].duplicated(), "item_id"].head(5).tolist()
        raise ValueError(f"duplicate item ids {dup}: an item is scored once per run")
    if frame.empty:
        raise ValueError("no items to score")
    custom = metric_name not in {"exact_match", "item_accuracy", "pass_at_k", "mean_item_score"}
    spec = get_metric_spec(metric_name, goal=metric_goal, task="scalar", allow_custom=custom)
    if spec.name == "pass_at_k":
        if k is None:
            raise ValueError("pass_at_k needs k=")
        for column in ("n", "c"):
            if column not in frame.columns:
                raise ValueError(f"pass_at_k needs an integer {column!r} column per item")
        frame["score"] = [
            pass_at_k(int(n), int(c), int(k)) for n, c in zip(frame["n"], frame["c"], strict=True)
        ]
    elif "score" not in frame.columns:
        raise ValueError("items need a score column (or n/c columns with metric pass_at_k)")
    scores = pd.to_numeric(frame["score"], errors="coerce").to_numpy(dtype=float)
    if not np.all(np.isfinite(scores)):
        raise ValueError("every item score must be a finite number (a failed parse scores 0, explicitly)")
    if spec.name in {"exact_match", "item_accuracy"} and not np.isin(scores, (0.0, 1.0)).all():
        raise ValueError(f"{spec.name} scores must be 0 or 1 per item")
    groups = None
    if group_column is not None:
        if group_column not in frame.columns:
            raise ValueError(f"group column {group_column!r} is not in the items")
        groups = frame[group_column].to_numpy()
    primary_value = spec.validate_value(float(scores.mean()))
    low, high = bootstrap_mean_ci(scores, groups=groups, n_boot=n_boot, ci=ci)
    total_seconds = 0.0 if t0 is None else time.time() - t0

    writing = study_dir is not None and not _smoke_mode()
    table_rel: str | None = None
    if writing:
        seed = os.environ.get("KLEIN_SEED")  # a seed array pins one table per seed
        suffix = f"_s{seed}" if seed is not None else ""
        table_rel = f"tables/{table_name or f'items_{exp_id}'}{suffix}.tsv"
        path = Path(study_dir) / table_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        keep = ["item_id", "score"] + [
            col for col in (group_column, "n", "c") if col and col in frame.columns and col != "score"
        ]
        out = frame[keep].sort_values("item_id", kind="stable")
        out.to_csv(path, sep="\t", index=False, float_format="%.10g", lineterminator="\n")

    _print_canonical_block(
        primary_value=primary_value,
        metric_name=spec.name,
        metric_goal=spec.goal,
        fit_seconds=None,
        total_seconds=total_seconds,
        train_n=None,
        val_n=int(scores.size),
        status=status,
    )
    print("--- aux_metrics ---")
    print(f"ci_low:            {low:.6f}")
    print(f"ci_high:           {high:.6f}")
    print(f"n_items:           {int(scores.size)}")
    if groups is not None:
        print(f"n_groups:          {len(set(map(str, groups)))}")
    if spec.name == "pass_at_k":
        print(f"pass_k:            {int(k)}")
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
        aux: dict[str, Any] = {
            "ci_low": low,
            "ci_high": high,
            "n_items": int(scores.size),
            "wall_seconds": total_seconds,
        }
        if extra:
            aux.update(extra)
        _append_aux_rows(study_dir, exp_id, aux)
    return primary_value


def _binom(n: int, k: int) -> int:  # used by the tests as an independent check
    return math.comb(n, k)
