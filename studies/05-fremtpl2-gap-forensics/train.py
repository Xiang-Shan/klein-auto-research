"""The only per-candidate mutable surface in a Klein v2 study.

freMTPL2 claim frequency, sealed two-track GLM vs GBDT. The CONFIG block is the
experiment surface; pipeline.py is the stable study library. Metric: exposure-
weighted mean Poisson deviance on the scoring fold, computed by the v0.4.0
registry (`kleinlib.eval.evaluate_regression`) — predictions are clipped positive
by the ClippedRegressor wrapper because the registry refuses pred <= 0 by contract.

A sealed final-test run additionally exports the per-row holdout prediction table
(`save_holdout_predictions`) so the off-ledger sealed-gap + paired-SE computation
and the pricing-eval double-lift card can be built after BOTH tracks have spent
their one sealed access.
"""

from __future__ import annotations

import os
import time

import math

from kleinlib.eval import evaluate_regression, save_holdout_predictions
from pipeline import effective_trees, fit_model, null_dev_deviance, read_reference

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("glm" if SMOKE else None)

# ---- CONFIG: the per-experiment surface (keep diffs 5-15 lines) ----
MODEL = "hgbt_ohe"            # glm_ohe | glm_scoped_splines | glm_interactions |
                              # hgbt_ohe | hgbt_monotone | lgbm_poisson | catboost_poisson
SEED = 0
LR = 0.1
MAX_ITER = 200
MAX_LEAF = 31
INTERACTIONS = ()        # e.g. (("BonusMalus", "DrivAge"),) — surrogate-derived only
# --------------------------------------------------------------------

PRED_DIMS = ["DrivAge", "BonusMalus", "VehGas", "Region"]


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND") or (
        "development" if SMOKE else None
    )
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
            "train.py must be invoked through `klein run-one`; missing "
            + ", ".join(missing)
        )
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")

    if evaluation_kind == "development":
        # Split-identity anchor: the null-model development deviance must match
        # prepare.py's reference cell exactly, every run, before any model fits.
        reference = read_reference()["null_dev_deviance"]
        recomputed = null_dev_deviance()
        if abs(reference - recomputed) > 1e-9:
            raise RuntimeError(
                f"split-identity anchor FAILED: reference {reference!r} vs "
                f"recomputed {recomputed!r} — split or data drifted, STOP"
            )

    model, X_ev, y_rate_ev, w_ev, fit_seconds, train_n = fit_model(
        MODEL,
        evaluation_kind=evaluation_kind,
        seed=SEED,
        learning_rate=LR,
        max_iter=MAX_ITER,
        max_leaf_nodes=MAX_LEAF,
        interactions=INTERACTIONS,
    )
    evaluate_regression(
        model,
        X_ev,
        y_rate_ev,
        exp_id=EXPERIMENT_ID,
        t0=t0,
        fit_seconds=fit_seconds,
        train_n=train_n,
        val_n=len(X_ev),
        metric_name="val_poisson_deviance",
        metric_goal="lower",
        sample_weight=w_ev,
        study_dir=".",
        extra={"model_config": MODEL, "wall_seconds": time.time() - t0}
        | ({"effective_trees": n_trees} if math.isfinite(n_trees := effective_trees(model)) else {}),
    )

    if evaluation_kind == "final_test" and not SMOKE:
        save_holdout_predictions(
            ".",
            EXPERIMENT_ID,
            y_true=y_rate_ev,
            y_pred=model.predict(X_ev),
            weight=w_ev,
            dims=X_ev[PRED_DIMS],
        )
        print(f"holdout predictions exported: predictions/{EXPERIMENT_ID}_holdout.csv.gz")


if __name__ == "__main__":
    main()
