"""The only per-candidate mutable surface in a Klein v2 study.

freMTPL2 claim frequency, GLM vs GBDT. The CONFIG block is the experiment
surface; pipeline.py is the stable study library. Metric: exposure-weighted
mean Poisson deviance on the development fold (computed in-study — registry
gap logged as soak friction F1).
"""

from __future__ import annotations

import os
import time

from kleinlib.eval import evaluate_scalar
from pipeline import fit_and_deviance, null_dev_deviance, read_reference

EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID")
TRACK = os.environ.get("KLEIN_TRACK")

# ---- CONFIG: the per-experiment surface (keep diffs 5-15 lines) ----
MODEL = "hgbt_native"    # glm_ohe | glm_shaped | hgbt_ohe | hgbt_native
HGBT_SEED = 0
HGBT_LR = 0.1
HGBT_MAX_ITER = 200
HGBT_MAX_LEAF = 31
# --------------------------------------------------------------------


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
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

    result = fit_and_deviance(
        MODEL,
        evaluation_kind=evaluation_kind,
        seed=HGBT_SEED,
        learning_rate=HGBT_LR,
        max_iter=HGBT_MAX_ITER,
        max_leaf_nodes=HGBT_MAX_LEAF,
    )
    evaluate_scalar(
        result["val_poisson_deviance"],
        exp_id=EXPERIMENT_ID,
        metric_name="val_poisson_deviance",
        metric_goal="lower",
        study_dir=".",
        t0=t0,
        extra={
            "calibration_ratio": result["calibration_ratio"],
            "n_eval_rows": float(result["n_eval_rows"]),
            "eval_claims": result["eval_claims"],
            "wall_seconds": time.time() - t0,
        },
    )


if __name__ == "__main__":
    main()
