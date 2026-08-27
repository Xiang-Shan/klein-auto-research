"""The only per-candidate mutable surface in a Klein v2 study.

Study 09 — the first lesson. E0001 re-establishes the 1936 anchor on the declared
split (seed 20260909); the parade then edits exactly one line (FAMILY) per
transaction across the 7-family challenger roster (`families.CHALLENGERS`, in
registry order), after the two controls. Candidate selection happens ONLY through
FAMILY (families.py registry); feature columns come from the registry so `species`
(a perfect target proxy) and `group_id` can never leak in.
Sealed-coda families (`coda_primary` / `coda_challenger`) are ordinary registry
entries whose factories read the committed `sweeps/coda_manifest.json` and bake its
pre-registered train positions — this file never grows a second knob. They route
through the same `families.build(FAMILY, y=..., groups=...)` call as every other CV
family, which is what makes 09's coda base group-aware inside the bake
(research_plan §7; 08's non-group `cv=3` argument does not port to seed 20260909).

The registered auxiliary block (study.yaml `auxiliary_metrics.registered`) rides
along in `extra=`: kleinlib prints val_auc / val_pr_auc / val_brier / val_logloss
itself, and `aux_metrics()` adds val_accuracy, val_f1, cal_intercept, cal_slope and
re-states val_logloss at the REGISTERED eps clip 1e-6. Secondary metrics never
overturn the registered primary verdict after results are known.
"""

from __future__ import annotations

import os
import time

import families
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, log_loss

import kleinlib
from kleinlib.data import load_prepared, three_way_split

#: The registered family this candidate runs. The ONE line the ladder edits.
FAMILY = "hgbt"

RANDOM_SEED = 20260909
SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("primary" if SMOKE else None)

PREPARED = "data/prepared/iris_hard_pair.csv"
TARGET = "is_virginica"

#: Registered clip for the log and logit transforms ONLY — never for Brier terms
#: (study.yaml auxiliary_metrics). sklearn's own log_loss clips at machine
#: epsilon (~2.2e-16), which is not the registered instrument.
AUX_EPS = 1e-6
#: val_accuracy / val_f1 are threshold-0.5 readings (kleinlib's val_f1_at_best
#: sweeps thresholds instead — the two are different registered quantities).
AUX_THRESHOLD = 0.5


def load_split(evaluation_kind: str):
    """Select development or the sealed final-test partition explicitly.

    Split = study.yaml's declaration verbatim: kind group (twins iris-102/143 share
    one group id and always travel together), seed 20260909 (derived inner seed
    20260910), 0.20/0.20 — the pre-committed fresh seed, disjoint from every 07 and
    08 namespace; NO redraw under any outcome. ``final_test`` fits the same
    train-only candidate and evaluates the sealed 20 (PROCEDURALLY FRESH ONLY — all
    100 values, and both predecessors' sealed values, are public). Band-check role
    per research_plan §7: the arena is the evidence; the seal is the discipline.
    """
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")
    df = load_prepared(PREPARED)
    y = df[TARGET]
    x_tr, x_dev, x_te, y_tr, y_dev, y_te = three_way_split(
        df,
        y,
        task="classification",
        strategy="group",
        development_size=0.20,
        test_size=0.20,
        seed=20260909,
        groups=df["group_id"],
    )
    columns = families.columns_for(FAMILY)
    g_tr = x_tr["group_id"]
    if evaluation_kind == "development":
        return x_tr[columns], x_dev[columns], y_tr, y_dev, g_tr
    return x_tr[columns], x_te[columns], y_tr, y_te, g_tr


def build_model(y_tr, g_tr):
    # CV families receive group-aware inner splits (twins never straddle an
    # inner boundary — the gate law applied inside the estimators). The coda
    # entries take y and groups too: they subset BOTH by their baked positions
    # before deriving their base's splits (families.py §CODA AMENDMENT).
    return families.build(FAMILY, y=y_tr, groups=g_tr)


def aux_metrics(model, X_dev, y_dev) -> dict[str, float]:
    """The 09 additions to kleinlib's printed aux block (registry order).

    ``val_logloss`` is RE-STATED here at the registered eps clip 1e-6; it is the
    same key kleinlib prints, so the sidecar and the parsed block both carry the
    registered instrument (kleinlib's line still prints first, unclipped —
    the difference is itself an RQ4 reading, not an error).
    """
    p_raw = model.predict_proba(X_dev)[:, 1]
    p = np.clip(p_raw, AUX_EPS, 1.0 - AUX_EPS)
    y = np.asarray(y_dev)
    predicted = (p_raw >= AUX_THRESHOLD).astype(int)

    # Cox recalibration on the eval predictions: y ~ sigmoid(a + b*logit(p)),
    # perfect calibration = (0, 1). Unpenalized by construction — an L2 prior
    # would shrink b toward 0 and report miscalibration that is not there.
    # Under a saturated (perfectly separated) eval set the MLE diverges and
    # lbfgs returns the max_iter-truncated value: read it as "slope unbounded",
    # never as a fitted constant. RQ4 is exactly about that regime.
    logit = np.log(p / (1.0 - p))
    recalibration = LogisticRegression(penalty=None, solver="lbfgs", max_iter=1000)
    recalibration.fit(logit.reshape(-1, 1), y)

    return {
        "val_logloss": float(log_loss(y, p, labels=[0, 1])),
        "val_accuracy": float(accuracy_score(y, predicted)),
        "val_f1": float(f1_score(y, predicted, zero_division=0)),
        "cal_intercept": float(recalibration.intercept_[0]),
        "cal_slope": float(recalibration.coef_[0][0]),
    }


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
    X_tr, X_dev, y_tr, y_dev, g_tr = load_split(evaluation_kind)
    model = build_model(y_tr, g_tr)
    fit_start = time.time()
    model.fit(X_tr, y_tr)
    fit_seconds = time.time() - fit_start
    kleinlib.eval.evaluate(
        model,
        X_dev,
        y_dev,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        fit_seconds=fit_seconds,
        train_n=len(X_tr),
        val_n=len(X_dev),
        metric_name="val_brier",
        metric_goal="lower",
        extra=aux_metrics(model, X_dev, y_dev),
    )


if __name__ == "__main__":
    main()
