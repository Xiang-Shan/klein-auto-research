"""Stable modeling library for study 04 — created BEFORE the loop.

freMTPL2 claim frequency: y = ClaimNb/Exposure with Exposure as Poisson weight
(the standard offset-free equivalence for deviance minimization). The metric is
exposure-weighted mean Poisson deviance on the development fold — computed HERE
because the framework's registry has no deviance metrics yet (soak friction F1).

train.py selects a MODEL config; sweeps/noise_floor.py varies only the seed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_poisson_deviance
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import SplineTransformer

from kleinlib.data import three_way_split
from kleinlib.encoders import build_preprocessor

PREPARED = Path("data/prepared/fremtpl2_frequency.csv")
REFERENCE = Path("data/prepared/reference_cell.json")
SEED = 42
NUMERIC = ["VehPower", "VehAge", "DrivAge", "BonusMalus", "Density"]
CATEGORICAL = ["Area", "VehBrand", "VehGas", "Region"]
MIN_PRED = 1e-6  # Poisson deviance needs strictly positive predictions


def load_split(evaluation_kind: str):
    """The declared fixed split. Adaptive work sees train+development only;
    evaluation_kind == "final_test" swaps the scoring fold to the sealed test."""
    df = pd.read_csv(PREPARED)
    X = df[NUMERIC + CATEGORICAL]
    y = df["ClaimNb"].astype(float)
    X_tr, X_dev, X_te, y_tr, y_dev, y_te = three_way_split(
        X, y, task="regression", strategy="random",
        development_size=0.2, test_size=0.2, seed=SEED,
    )
    exposure = df["Exposure"]
    parts = {
        "train": (X_tr, y_tr, exposure.loc[X_tr.index]),
        "development": (X_dev, y_dev, exposure.loc[X_dev.index]),
        "final_test": (X_te, y_te, exposure.loc[X_te.index]),
    }
    score_on = "final_test" if evaluation_kind == "final_test" else "development"
    return parts["train"], parts[score_on]


def frequency(y_counts, exposure):
    return np.asarray(y_counts, dtype=float) / np.asarray(exposure, dtype=float)


def null_dev_deviance() -> float:
    """Intercept-only model's development deviance — the split-identity anchor."""
    (X_tr, y_tr, w_tr), (X_ev, y_ev, w_ev) = load_split("development")
    lam = float(np.sum(y_tr) / np.sum(w_tr))
    return float(
        mean_poisson_deviance(
            frequency(y_ev, w_ev), np.full(len(y_ev), lam), sample_weight=w_ev
        )
    )


def _with_shaping(X: pd.DataFrame) -> pd.DataFrame:
    shaped = X.copy()
    shaped["Density"] = np.log1p(shaped["Density"])
    return shaped


def make_model(model: str, *, seed: int = 0, learning_rate: float = 0.1,
               max_iter: int = 200, max_leaf_nodes: int = 31):
    if model == "glm_ohe":
        pre = build_preprocessor(NUMERIC, CATEGORICAL, kind="ohe")
        return Pipeline([("pre", pre), ("glm", PoissonRegressor(alpha=1e-4, max_iter=300))]), False
    if model == "glm_shaped":
        spline = SplineTransformer(n_knots=6, degree=3)
        pre = build_preprocessor(NUMERIC, CATEGORICAL, kind="ohe")
        # shaping happens on the frame (log-density) + splines on the standardized numerics
        return Pipeline([
            ("pre", pre),
            ("spline", spline),
            ("glm", PoissonRegressor(alpha=1e-4, max_iter=300)),
        ]), True
    if model == "hgbt_ohe":
        pre = build_preprocessor(NUMERIC, CATEGORICAL, kind="ohe")
        est = HistGradientBoostingRegressor(
            loss="poisson", learning_rate=learning_rate, max_iter=max_iter,
            max_leaf_nodes=max_leaf_nodes, random_state=seed,
        )
        return Pipeline([("pre", pre), ("hgbt", est)]), False
    if model == "hgbt_native":
        pre = build_preprocessor(NUMERIC, CATEGORICAL, kind="native")
        est = HistGradientBoostingRegressor(
            loss="poisson", learning_rate=learning_rate, max_iter=max_iter,
            max_leaf_nodes=max_leaf_nodes, random_state=seed,
            categorical_features=list(range(len(NUMERIC), len(NUMERIC) + len(CATEGORICAL))),
        )
        return Pipeline([("pre", pre), ("hgbt", est)]), False
    raise ValueError(f"unknown MODEL {model!r}")


def fit_and_deviance(model: str, *, evaluation_kind: str = "development",
                     seed: int = 0, learning_rate: float = 0.1,
                     max_iter: int = 200, max_leaf_nodes: int = 31) -> dict:
    (X_tr, y_tr, w_tr), (X_ev, y_ev, w_ev) = load_split(evaluation_kind)
    estimator, shaped = make_model(
        model, seed=seed, learning_rate=learning_rate,
        max_iter=max_iter, max_leaf_nodes=max_leaf_nodes,
    )
    if shaped:
        X_tr, X_ev = _with_shaping(X_tr), _with_shaping(X_ev)
    fit_kwargs = {estimator.steps[-1][0] + "__sample_weight": w_tr.to_numpy()}
    estimator.fit(X_tr, frequency(y_tr, w_tr), **fit_kwargs)
    pred = np.clip(estimator.predict(X_ev), MIN_PRED, None)
    dev = float(mean_poisson_deviance(frequency(y_ev, w_ev), pred, sample_weight=w_ev))
    calibration = float(np.sum(pred * w_ev) / np.sum(y_ev))  # predicted / actual claims
    return {
        "val_poisson_deviance": dev,
        "calibration_ratio": calibration,
        "n_eval_rows": int(len(y_ev)),
        "eval_claims": float(np.sum(y_ev)),
    }


def read_reference() -> dict:
    return json.loads(REFERENCE.read_text(encoding="utf-8"))
