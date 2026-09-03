"""The only per-candidate mutable surface in this study.

The per-experiment diff is two constants — ``CANDIDATE`` (the rung being tried)
and ``REFERENCE`` (the rung it claims to beat) — and nothing else. Everything
below them is fixed machinery.

What every run prints, on top of the canonical block
---------------------------------------------------
Because the truth is declared, each run can report where it stands relative to
things a normal study can only guess at. All of them are read from the contract
and from ``data/prepared/truth.json``; none is written here as a literal:

===================== ==========================================================
``bayes_auc``         the Bayes-optimal AUC for exactly the rows this run was
                      graded on, from the DGP's true log-odds
``gap_to_ideal``      ``bayes_auc - val_auc``: how far this rung is from the
                      ceiling, in metric units
``gap_in_floors``     the same distance divided by the contract's
                      ``minimum_delta`` — i.e. **this run's own headroom h**,
                      the number the detection-limit law is about
``reference_auc``     the named reference rung refitted on the SAME rows (common
                      random numbers), so the comparison lives in one block
``delta_vs_reference``  ``val_auc - reference_auc``
``delta_in_floors``   that lift in units of the measured floor
===================== ==========================================================

`gap_in_floors` and `delta_in_floors` are printed only once the contract carries
a measured ``minimum_delta``; before Phase 0 sets it there is no floor to divide
by, and a prediction whose key is not printed is INCONCLUSIVE rather than
refuted, which is the honest answer.

The partition comes from ``kleinlib.data.load_partition`` (which prints the
``split_fingerprint:`` the notary checks against the DATA gate) and the ceiling
is looked up by row label, so the sealed dry-run — which hands back development
rows — reports the development ceiling without this file knowing anything about
it.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import kleinlib
from kleinlib.contract import load_contract
from kleinlib.data import load_partition

RANDOM_SEED = 42
SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("primary" if SMOKE else None)

TRUTH_PATH = Path("data/prepared/truth.json")


def _with_interaction(X: pd.DataFrame) -> pd.DataFrame:
    """Hand the linear model the DGP's true two-way interaction term."""
    out = X.copy()
    out["x1_x2"] = out["x1"] * out["x2"]
    return out


#: The ladder's rungs. A recipe is (feature builder or None, estimator factory).
#: Adding a rung is a deliberate edit to this library; choosing one is the
#: per-experiment idea.
RECIPES = {
    "logreg_raw": (
        None,
        lambda: make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, random_state=RANDOM_SEED),
        ),
    ),
    "logreg_interaction": (
        _with_interaction,
        lambda: make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, random_state=RANDOM_SEED),
        ),
    ),
    "hgbt_default": (
        None,
        lambda: HistGradientBoostingClassifier(random_state=RANDOM_SEED),
    ),
    "hgbt_overcapacity": (
        None,
        lambda: HistGradientBoostingClassifier(
            max_iter=500,
            learning_rate=0.25,
            max_leaf_nodes=127,
            min_samples_leaf=1,
            l2_regularization=0.0,
            early_stopping=False,
            random_state=RANDOM_SEED,
        ),
    ),
}

# --- the candidate: the whole per-experiment diff surface -------------------
CANDIDATE = "logreg_raw"
REFERENCE = None


def fit_recipe(name: str, X_fit: pd.DataFrame, y_fit: pd.Series):
    """Fit one rung; return the model and the feature transform it expects."""
    build, make = RECIPES[name]
    transform = build or (lambda frame: frame)
    model = make()
    model.fit(transform(X_fit), y_fit)
    return model, transform


def positive_probabilities(model, X: pd.DataFrame) -> np.ndarray:
    return np.asarray(model.predict_proba(X))[:, 1]


def ceiling_for(rows: pd.Index, y_eval: pd.Series) -> float:
    """The Bayes AUC of exactly these rows, from the declared true log-odds."""
    eta = np.asarray(json.loads(TRUTH_PATH.read_text(encoding="utf-8"))["true_log_odds"], dtype=float)
    probability = 1.0 / (1.0 + np.exp(-eta[np.asarray(rows)]))
    return float(roc_auc_score(y_eval, probability))


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

    X_fit, X_eval, y_fit, y_eval = load_partition(evaluation_kind, study_dir=".")
    minimum_delta = float(
        load_contract(".")["tracks"][TRACK]["metric"].get("minimum_delta") or 0.0
    )

    fit_start = time.time()
    model, transform = fit_recipe(CANDIDATE, X_fit, y_fit)
    fit_seconds = time.time() - fit_start
    X_eval_t = transform(X_eval)

    # The same arithmetic `evaluate` is about to do, computed here so the
    # distance to the ceiling can be printed alongside the score rather than
    # reconstructed by a reader afterwards.
    candidate_auc = float(roc_auc_score(y_eval, positive_probabilities(model, X_eval_t)))
    bayes_auc = ceiling_for(X_eval.index, y_eval)

    extra: dict[str, str] = {
        "bayes_auc": f"{bayes_auc:.6f}",
        "gap_to_ideal": f"{bayes_auc - candidate_auc:.6f}",
    }
    if minimum_delta > 0:
        extra["gap_in_floors"] = f"{(bayes_auc - candidate_auc) / minimum_delta:.4f}"
    if REFERENCE is not None:
        reference_model, reference_transform = fit_recipe(REFERENCE, X_fit, y_fit)
        reference_auc = float(
            roc_auc_score(
                y_eval, positive_probabilities(reference_model, reference_transform(X_eval))
            )
        )
        extra["reference_auc"] = f"{reference_auc:.6f}"
        extra["delta_vs_reference"] = f"{candidate_auc - reference_auc:.6f}"
        if minimum_delta > 0:
            extra["delta_in_floors"] = f"{(candidate_auc - reference_auc) / minimum_delta:.4f}"

    kleinlib.eval.evaluate(
        model,
        X_eval_t,
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


if __name__ == "__main__":
    main()
