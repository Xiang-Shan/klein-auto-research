"""The ladder's rungs — STABLE study library code, not the mutable surface.

The loop contract puts a study's `lib/` beside `kleinlib/` and `prepare.py`: it
changes rarely, deliberately, and never as part of a per-experiment diff. The rung
DEFINITIONS live here for one reason: `train.py` (the mutable surface) and
`sweeps/noise_floor.py` (Phase 0 metrology) must fit the same models. Re-typing them
in the floor script would let the floor describe a model the ledger never ran;
importing them from the mutable surface would let a per-experiment edit silently
change what the floor was measured on. A stable library module has neither failure.

Four rungs, each the v1 quickstart's own recipe:

``glm_ohe_balanced``
    The v1 split-identity anchor. `LogisticRegression(max_iter=2000, solver="saga",
    class_weight="balanced")` over median-imputed, standardised numerics and one-hot
    categoricals with rare levels pooled at `min_frequency=20`. The constructor is the
    ancestor campaign's exp1, transcribed into the v1 notebook from a `git show` of the
    commit that carried it.

``glm_splines_isotonic``
    The v1 "E2-redux" rung, recovered by v1 from prose that named its three
    non-default kwargs: quantile knots, `include_bias=False`, and
    `CalibratedClassifierCV(cv=5)` rather than `cv=3`. Degree-3 B-spline bases on
    subscription length, vehicle age and customer age, plus `log1p(region_density)`
    and two interactions, all ADDED to the base design matrix.

``hgbt_balanced``
    The v1 tree rung, the only one recoverable verbatim from a committed file
    (`v1.3.0:studies/00-glm-claims-quickstart/train.py` is its sibling, differing by
    `learning_rate` alone). Seven near-deterministic functions of `model` are dropped.

``glm_ohe_none_isotonic``
    The doctrine A/B: the anchor with `class_weight=None` and an isotonic calibration
    wrapper instead of the balanced reweighting.

Nothing here chooses rows or partitions, and the only integer seed is a FIT seed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import SplineTransformer

import kleinlib
from kleinlib.data import feature_column_groups

#: A FIT seed and nothing else: it reaches `LogisticRegression(random_state=...)` and
#: `HistGradientBoostingClassifier(random_state=...)`. No partition is chosen anywhere
#: in this study's code — rows come from `kleinlib.data.load_partition`, which reads
#: `study.yaml` alone and prints the fingerprint the notary checks (war story 8).
FIT_SEED = 42

#: The v1 study's one-hot rarity threshold; the anchors depend on it.
MIN_FREQUENCY = 20

#: Seven columns that are near-deterministic functions of `model`, dropped by the v1
#: HGBT rung (its data card's ranked issue #2).
DROP_REDUNDANT = [
    "engine_type",
    "displacement",
    "cylinder",
    "max_torque_nm",
    "max_torque_rpm",
    "max_power_bhp",
    "max_power_rpm",
]

#: The three numeric columns the v1 spline chain bends, and the density column it logs.
SPLINE_COLUMNS = ["subscription_length", "vehicle_age", "customer_age"]
DENSITY_COLUMN = "region_density"


# --- feature builders ------------------------------------------------------
def drop_model_derivatives(
    X_fit: pd.DataFrame, X_eval: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return (
        X_fit.drop(columns=DROP_REDUNDANT, errors="ignore"),
        X_eval.drop(columns=DROP_REDUNDANT, errors="ignore"),
    )


def spline_chain(
    X_fit: pd.DataFrame, X_eval: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Quantile-knot splines + log1p(density) + 2 interactions, fitted on FIT rows only.

    The knot positions are quantiles of the fitting rows, i.e. learned parameters:
    letting the evaluation rows influence them would be lookahead, so the transformer
    is fitted once on `X_fit` and applied to both frames.
    """
    spline = SplineTransformer(
        n_knots=5, degree=3, knots="quantile", include_bias=False
    ).fit(X_fit[SPLINE_COLUMNS])

    def build(X: pd.DataFrame) -> pd.DataFrame:
        out = X.copy()
        basis = spline.transform(X[SPLINE_COLUMNS])
        names = [f"spl_{i:02d}" for i in range(basis.shape[1])]
        out[names] = pd.DataFrame(basis, index=X.index, columns=names)
        out["log_density"] = np.log1p(X[DENSITY_COLUMN])
        out["log_density_x_vehicle_age"] = out["log_density"] * X["vehicle_age"]
        out["sublen_x_vehicle_age"] = X["subscription_length"] * X["vehicle_age"]
        return out

    return build(X_fit), build(X_eval)


# --- estimators ------------------------------------------------------------
def _glm(class_weight: str | None, fit_seed: int) -> LogisticRegression:
    return LogisticRegression(
        max_iter=2000, solver="saga", class_weight=class_weight, random_state=fit_seed
    )


def _ohe(X: pd.DataFrame):
    numeric_cols, categorical_cols = feature_column_groups(X)
    return kleinlib.encoders.build_preprocessor(
        numeric_cols, categorical_cols, kind="ohe", min_frequency=MIN_FREQUENCY
    )


def build_glm_ohe_balanced(X_fit: pd.DataFrame, fit_seed: int) -> Pipeline:
    return Pipeline([("pre", _ohe(X_fit)), ("model", _glm("balanced", fit_seed))])


def build_glm_splines_isotonic(X_fit: pd.DataFrame, fit_seed: int) -> Pipeline:
    return Pipeline(
        [
            ("pre", _ohe(X_fit)),
            ("model", CalibratedClassifierCV(_glm("balanced", fit_seed), method="isotonic", cv=5)),
        ]
    )


def build_glm_ohe_none_isotonic(X_fit: pd.DataFrame, fit_seed: int) -> Pipeline:
    return Pipeline(
        [
            ("pre", _ohe(X_fit)),
            ("model", CalibratedClassifierCV(_glm(None, fit_seed), method="isotonic", cv=5)),
        ]
    )


def build_hgbt_balanced(X_fit: pd.DataFrame, fit_seed: int) -> Pipeline:
    return Pipeline(
        [
            ("pre", _ohe(X_fit)),
            (
                "model",
                HistGradientBoostingClassifier(
                    learning_rate=0.05,
                    max_iter=500,
                    max_leaf_nodes=31,
                    l2_regularization=0.0,
                    random_state=fit_seed,
                    class_weight="balanced",
                    early_stopping=True,
                    validation_fraction=0.1,
                    n_iter_no_change=20,
                ),
            ),
        ]
    )


#: name -> (feature transform or None, pipeline builder). Adding a rung is a
#: deliberate edit to this table; CHOOSING one is the per-experiment idea.
RECIPES = {
    "glm_ohe_balanced": (None, build_glm_ohe_balanced),
    "glm_splines_isotonic": (spline_chain, build_glm_splines_isotonic),
    "hgbt_balanced": (drop_model_derivatives, build_hgbt_balanced),
    "glm_ohe_none_isotonic": (None, build_glm_ohe_none_isotonic),
}


def fit_rung(
    name: str,
    X_fit: pd.DataFrame,
    X_eval: pd.DataFrame,
    y_fit: pd.Series,
    *,
    fit_seed: int = FIT_SEED,
):
    """Fit one rung on the fit rows; return (model, X_fit_used, X_eval_used)."""
    transform, build = RECIPES[name]
    X_fit_t, X_eval_t = transform(X_fit, X_eval) if transform else (X_fit, X_eval)
    model = build(X_fit_t, fit_seed)
    model.fit(X_fit_t, y_fit)
    return model, X_fit_t, X_eval_t


def positive_probabilities(model, X: pd.DataFrame) -> np.ndarray:
    return np.asarray(model.predict_proba(X))[:, 1]
