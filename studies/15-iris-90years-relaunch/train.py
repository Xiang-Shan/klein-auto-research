"""The only per-candidate mutable surface in a Klein v2 study."""

from __future__ import annotations

import os
import time

import numpy as np

import kleinlib
from kleinlib.contract import load_contract
from kleinlib.data import load_partition
from lib.iris import (
    FEATURE_SETS,
    MODEL_SEED,
    ablation_extra,
    build_estimator,
    fit_and_score,
    frontier_extra,
)

from sklearn.metrics import roc_auc_score

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("modern" if SMOKE else None)

# ---------------------------------------------------------------------------
# E0002-E0006, `modern` track (research_plan.md Phase `parade`, steps 5-6).
#
# ONE falsifiable idea per candidate: which post-1936 recipe is fit and
# scored against Fisher's own `lda_all4`, refit on the SAME development rows
# inside the SAME run (paired by construction). This is the whole
# per-experiment diff for this phase -- everything else in `run_modern_
# frontier_cell` below is fixed machinery, unchanged run to run.
#
#   E0002  lda_all4    -- seeds the frontier; reference IS the candidate (P4)
#   E0003  logreg_l2   -- P5
#   E0004  knn5        -- P6
#   E0005  svm_rbf     -- P7
#   E0006  hgbt        -- P8
# ---------------------------------------------------------------------------
MODERN_RECIPE = "hgbt"  # E0006: histogram gradient-boosted tree vs Fisher's LDA (P8)


def run_modern_frontier_cell(evaluation_kind: str, t0: float) -> float:
    """`modern` track cell: fit `MODERN_RECIPE`, refit `lda_all4` as the
    reference on the SAME rows in the SAME run, and print both scores plus
    `delta_vs_reference`/`delta_in_floors` (the latter only once
    `minimum_delta > 0` -- currently 0, so P4-P8's rule keys read
    INCONCLUSIVE by their own stated `inconclusive_if`, per program.md's
    dated Decision).
    """
    X_fit, X_eval, y_fit, y_eval = load_partition(evaluation_kind, study_dir=".")
    y_eval_arr = y_eval.to_numpy()
    minimum_delta = float(
        load_contract(".")["tracks"]["modern"]["metric"].get("minimum_delta") or 0.0
    )

    model, p_eval, fit_seconds = fit_and_score(MODERN_RECIPE, X_fit, y_fit, X_eval)
    candidate_auc = float(roc_auc_score(y_eval_arr, p_eval))

    if MODERN_RECIPE == "lda_all4":
        # E0002 seeds the frontier with Fisher's own recipe -- the reference
        # IS the candidate, so no second fit is needed.
        reference_auc = candidate_auc
    else:
        _, p_reference, _ = fit_and_score("lda_all4", X_fit, y_fit, X_eval)
        reference_auc = float(roc_auc_score(y_eval_arr, p_reference))

    y_pred = (p_eval >= 0.5).astype(int)
    val_accuracy = float((y_pred == y_eval_arr).mean())
    val_errors = int((y_pred != y_eval_arr).sum())

    extra = frontier_extra(
        reference_metric=reference_auc,
        candidate_metric=candidate_auc,
        minimum_delta=minimum_delta,
        val_accuracy=val_accuracy,
        val_errors=val_errors,
        ideal=1.0,
    )

    return kleinlib.eval.evaluate(
        model,
        X_eval,
        y_eval,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        fit_seconds=fit_seconds,
        train_n=len(X_fit),
        val_n=len(X_eval),
        metric_name="val_auc",
        metric_goal="higher",
        extra=extra,
    )


# ---------------------------------------------------------------------------
# E0007-E0009, `ablation` track (research_plan.md Phase `ablation-map`,
# steps 8-10). Registered mode: every run here is a CELL (disposition
# `measured`, never keep/discard) and the mutable surface is ALWAYS restored
# afterwards -- the candidate commit is the record (references/registered-
# mode.md). Same paired-comparison shape as `run_modern_frontier_cell` above
# (candidate + reference refit on the SAME development rows in the SAME
# run), just composing `lib.iris.build_estimator`/`FEATURE_SETS` directly
# instead of going through the fixed `RECIPES` table, so ANY estimator can
# be paired with ANY feature set without touching the stable library.
#
# ONE falsifiable idea per candidate: which estimator, paired with which
# feature set, against the SAME estimator refit on all four columns.
#
#   E0007  lda,  petal vs all4 (lda)   -- P12
#   E0008  lda,  sepal vs all4 (lda)   -- P13
#   E0009  hgbt, petal vs all4 (hgbt)  -- P14 (the parade's best-scoring
#          `modern` family; see program.md's dated Decision on why hgbt is
#          the honest choice among the parade's four printed-tie keeps)
# ---------------------------------------------------------------------------
ABLATION_ESTIMATOR = "lda"      # E0007: lda
ABLATION_FEATURE_SET = "petal"  # E0007: petal-only vs all4 (P12)


def _fit_feature_set(
    estimator_name: str,
    feature_set: str,
    X_fit,
    y_fit,
    X_eval,
    *,
    random_state: int | None = None,
):
    """Fit `estimator_name` (`lib.iris.build_estimator`) on `feature_set`'s
    columns; mirrors `lib.iris.fit_and_score` exactly but takes the feature
    set directly instead of going through the `RECIPES` table, so an
    ablation cell can pair ANY estimator with ANY of the three feature sets
    without a new stable-library entry (research_plan.md's "COMPOSES those
    primitives in train.py").
    """
    cols = FEATURE_SETS[feature_set]
    model = build_estimator(estimator_name, random_state=random_state)
    t0 = time.time()
    model.fit(X_fit[cols], y_fit)
    fit_seconds = time.time() - t0
    p_eval = np.asarray(model.predict_proba(X_eval[cols]))[:, 1]
    return model, p_eval, fit_seconds


def run_ablation_cell(evaluation_kind: str, t0: float) -> float:
    """`ablation` track cell: fit `ABLATION_ESTIMATOR` on
    `ABLATION_FEATURE_SET`'s columns, refit the SAME estimator on all four
    columns as the reference on the SAME development rows in the SAME run,
    and print both scores plus `delta_vs_reference`/`delta_in_floors`. This
    track's floor is real and measured (`minimum_delta=0.28125`, unlike
    `modern`'s 0), so `delta_in_floors` prints and P12/P13/P14 resolve by
    ordinary arithmetic, not INCONCLUSIVE.
    """
    X_fit, X_eval, y_fit, y_eval = load_partition(evaluation_kind, study_dir=".")
    y_eval_arr = y_eval.to_numpy()
    minimum_delta = float(
        load_contract(".")["tracks"]["ablation"]["metric"].get("minimum_delta") or 0.0
    )

    model, p_eval, fit_seconds = _fit_feature_set(
        ABLATION_ESTIMATOR,
        ABLATION_FEATURE_SET,
        X_fit,
        y_fit,
        X_eval,
        random_state=MODEL_SEED,
    )
    candidate_auc = float(roc_auc_score(y_eval_arr, p_eval))

    _, p_reference, _ = _fit_feature_set(
        ABLATION_ESTIMATOR, "all4", X_fit, y_fit, X_eval, random_state=MODEL_SEED
    )
    reference_auc = float(roc_auc_score(y_eval_arr, p_reference))

    extra = ablation_extra(
        reference_metric=reference_auc,
        candidate_metric=candidate_auc,
        minimum_delta=minimum_delta,
    )

    return kleinlib.eval.evaluate(
        model,
        X_eval[FEATURE_SETS[ABLATION_FEATURE_SET]],
        y_eval,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        fit_seconds=fit_seconds,
        train_n=len(X_fit),
        val_n=len(X_eval),
        metric_name="val_auc",
        metric_goal="higher",
        extra=extra,
    )


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
    if SMOKE:
        evaluation_kind = evaluation_kind or "development"
    missing = [
        name
        for name, value in (
            ("KLEIN_EVALUATION_KIND", evaluation_kind),
            ("KLEIN_EXPERIMENT_ID", EXPERIMENT_ID),
            ("KLEIN_TRACK", TRACK),
        )
        if value is None
    ]
    if missing:
        raise RuntimeError(
            "train.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python train.py` — it prints "
            "the canonical block, writes no sidecars or snapshots, and is not "
            "evidence. Missing: " + ", ".join(missing)
        )

    if TRACK == "modern":
        run_modern_frontier_cell(evaluation_kind, t0)
        return
    if TRACK == "ablation":
        run_ablation_cell(evaluation_kind, t0)
        return
    raise NotImplementedError(
        f"KLEIN_TRACK={TRACK!r}: only the `modern` frontier cell (Phase `parade`) "
        "and the `ablation` cell (Phase `ablation-map`) exist in train.py right "
        "now -- the `fisher` anchor cell (E0001) was a separate candidate "
        "transaction in its own phase (research_plan.md's experiment ladder)."
    )


if __name__ == "__main__":
    main()
