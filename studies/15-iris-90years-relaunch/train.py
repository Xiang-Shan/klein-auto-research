"""The only per-candidate mutable surface in a Klein v2 study."""

from __future__ import annotations

import os
import time

import kleinlib
from kleinlib.contract import load_contract
from kleinlib.data import load_partition
from lib.iris import fit_and_score, frontier_extra

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
MODERN_RECIPE = "lda_all4"  # E0002: seed the `modern` frontier with Fisher's own LDA


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
    raise NotImplementedError(
        f"KLEIN_TRACK={TRACK!r}: only the `modern` frontier cell (Phase `parade`) "
        "exists in train.py right now -- the `fisher` anchor cell (E0001) and the "
        "`ablation` cells are separate candidate transactions in their own phases "
        "(research_plan.md's experiment ladder)."
    )


if __name__ == "__main__":
    main()
