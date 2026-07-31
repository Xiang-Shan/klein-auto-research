"""Stable modeling library for study 05 — created BEFORE the loop.

freMTPL2 claim frequency: y = ClaimNb/Exposure with Exposure as the Poisson weight
(the standard offset-free equivalence). Split, prep, and the two anchor configs are
FROZEN to study 04 (tag v1.0.0) — E0001/E0002 must reproduce its published numbers
to 1e-9 through the v0.4.0 metric registry (`evaluate_regression`, which computes
the exposure-weighted deviance itself and refuses non-positive predictions — hence
the ClippedRegressor wrapper, since the registry calls `model.predict()`).

New constructors beyond study 04: lgbm_poisson / catboost_poisson (the audience's
libraries, matched capacity), hgbt_monotone (filability probe), glm_scoped_splines
(fixes study-04 E0002's spline-basis-on-OHE-dummies leak by scoping splines to the
three continuous rating factors only), glm_interactions (surrogate-derived products
on top of the scoped splines).

train.py selects a MODEL config; sweeps vary only seeds / bootstrap draws.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_poisson_deviance
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

from kleinlib.data import three_way_split
from kleinlib.encoders import build_preprocessor

PREPARED = Path("data/prepared/fremtpl2_frequency.csv")
REFERENCE = Path("data/prepared/reference_cell.json")
SEED = 42
NUMERIC = ["VehPower", "VehAge", "DrivAge", "BonusMalus", "Density"]
CATEGORICAL = ["Area", "VehBrand", "VehGas", "Region"]
SPLINED = ["DrivAge", "BonusMalus", "Density"]  # Density is log1p'd first (shaping)
MIN_PRED = 1e-6  # Poisson deviance needs strictly positive predictions


class ClippedRegressor:
    """Prediction-clipping wrapper: the v0.4.0 registry calls model.predict()
    itself and raises on pred <= 0 rather than clipping (its contract)."""

    def __init__(self, inner, *, shaped: bool = False, interactions=None):
        self.inner = inner
        self.shaped = shaped
        self.interactions = interactions or []

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X = _transform_frame(X, shaped=self.shaped, interactions=self.interactions)
        return np.clip(np.asarray(self.inner.predict(X), dtype=float), MIN_PRED, None)


class CatBoostPoisson:
    """CatBoost with Poisson loss on the raw frame (native categoricals).
    predict() must return expected counts (exp space), not the raw score."""

    def __init__(self, *, seed: int = 0, learning_rate: float = 0.1,
                 iterations: int = 200, depth: int = 6):
        from catboost import CatBoostRegressor

        self.model = CatBoostRegressor(
            loss_function="Poisson", iterations=iterations,
            learning_rate=learning_rate, depth=depth, random_seed=seed,
            allow_writing_files=False, verbose=False,
        )

    def fit(self, X: pd.DataFrame, y, sample_weight=None):
        self.model.fit(X, y, sample_weight=sample_weight,
                       cat_features=[c for c in CATEGORICAL if c in X.columns])
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.model.predict(X, prediction_type="Exponent"), dtype=float)


def load_split(evaluation_kind: str):
    """The declared fixed split — identical to study 04. Adaptive work sees
    train+development only; evaluation_kind == "final_test" swaps the scoring
    fold to the sealed test."""
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


def _transform_frame(X: pd.DataFrame, *, shaped: bool, interactions) -> pd.DataFrame:
    """Frame-level shaping shared by fit and predict: log-density plus any
    surrogate-derived numeric product columns."""
    out = X.copy()
    if shaped:
        out["Density"] = np.log1p(out["Density"])
    for a, b in interactions:
        out[f"{a}_x_{b}"] = out[a].astype(float) * out[b].astype(float)
    return out


def _scoped_preprocessor(interactions=()) -> ColumnTransformer:
    """Splines ONLY on the three continuous rating factors (post-log Density);
    plain standardization for the other numerics and any interaction products;
    OHE for categoricals. This is the study-04 E0002 fix: the spline basis never
    touches the OHE dummies."""
    inter_cols = [f"{a}_x_{b}" for a, b in interactions]
    rest = [c for c in NUMERIC if c not in SPLINED]
    return ColumnTransformer(
        [
            ("spline", Pipeline([
                ("scale", StandardScaler()),
                ("spline", SplineTransformer(n_knots=6, degree=3)),
            ]), SPLINED),
            ("num", StandardScaler(), rest + inter_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20,
                                  sparse_output=True), CATEGORICAL),
        ]
    )


def make_model(model: str, *, seed: int = 0, learning_rate: float = 0.1,
               max_iter: int = 200, max_leaf_nodes: int = 31, interactions=()):
    """Returns (estimator, shaped, interactions) — the latter two describe the
    frame-level transform the ClippedRegressor must replay at predict time."""
    interactions = tuple(interactions)
    if model == "glm_ohe":
        pre = build_preprocessor(NUMERIC, CATEGORICAL, kind="ohe")
        return Pipeline([("pre", pre), ("glm", PoissonRegressor(alpha=1e-4, max_iter=300))]), False, ()
    if model == "glm_scoped_splines":
        return Pipeline([
            ("pre", _scoped_preprocessor()),
            ("glm", PoissonRegressor(alpha=1e-4, max_iter=300)),
        ]), True, ()
    if model == "glm_interactions":
        return Pipeline([
            ("pre", _scoped_preprocessor(interactions)),
            ("glm", PoissonRegressor(alpha=1e-4, max_iter=300)),
        ]), True, interactions
    if model == "hgbt_ohe":
        pre = build_preprocessor(NUMERIC, CATEGORICAL, kind="ohe")
        est = HistGradientBoostingRegressor(
            loss="poisson", learning_rate=learning_rate, max_iter=max_iter,
            max_leaf_nodes=max_leaf_nodes, random_state=seed,
        )
        return Pipeline([("pre", pre), ("hgbt", est)]), False, ()
    if model == "hgbt_monotone":
        # Native-categorical path so monotonic_cst indexes the raw column order
        # (NUMERIC then CATEGORICAL); +1 on BonusMalus only.
        pre = build_preprocessor(NUMERIC, CATEGORICAL, kind="native")
        cst = [1 if c == "BonusMalus" else 0 for c in NUMERIC] + [0] * len(CATEGORICAL)
        est = HistGradientBoostingRegressor(
            loss="poisson", learning_rate=learning_rate, max_iter=max_iter,
            max_leaf_nodes=max_leaf_nodes, random_state=seed,
            categorical_features=list(range(len(NUMERIC), len(NUMERIC) + len(CATEGORICAL))),
            monotonic_cst=cst,
        )
        return Pipeline([("pre", pre), ("hgbt", est)]), False, ()
    if model == "lgbm_poisson":
        from lightgbm import LGBMRegressor

        pre = build_preprocessor(NUMERIC, CATEGORICAL, kind="ohe")
        est = LGBMRegressor(
            objective="poisson", num_leaves=max_leaf_nodes,
            learning_rate=learning_rate, n_estimators=max_iter,
            random_state=seed, verbose=-1,
        )
        return Pipeline([("pre", pre), ("lgbm", est)]), False, ()
    if model == "catboost_poisson":
        return CatBoostPoisson(seed=seed, learning_rate=learning_rate,
                               iterations=max_iter), False, ()
    raise ValueError(f"unknown MODEL {model!r}")


def fit_model(model: str, *, evaluation_kind: str = "development",
              seed: int = 0, learning_rate: float = 0.1,
              max_iter: int = 200, max_leaf_nodes: int = 31, interactions=()):
    """Fit the named config; return everything train.py needs to hand the
    registry evaluator: (clipped_model, X_ev, y_rate_ev, w_ev, fit_seconds,
    train_n) — the registry computes the deviance itself."""
    (X_tr, y_tr, w_tr), (X_ev, y_ev, w_ev) = load_split(evaluation_kind)
    estimator, shaped, inter = make_model(
        model, seed=seed, learning_rate=learning_rate,
        max_iter=max_iter, max_leaf_nodes=max_leaf_nodes, interactions=interactions,
    )
    X_fit = _transform_frame(X_tr, shaped=shaped, interactions=inter)
    t_fit = time.time()
    if isinstance(estimator, CatBoostPoisson):
        estimator.fit(X_fit, frequency(y_tr, w_tr), sample_weight=w_tr.to_numpy())
    else:
        fit_kwargs = {estimator.steps[-1][0] + "__sample_weight": w_tr.to_numpy()}
        estimator.fit(X_fit, frequency(y_tr, w_tr), **fit_kwargs)
    fit_seconds = time.time() - t_fit
    clipped = ClippedRegressor(estimator, shaped=shaped, interactions=inter)
    return clipped, X_ev, frequency(y_ev, w_ev), w_ev.to_numpy(), fit_seconds, len(X_tr)


def effective_trees(clipped: ClippedRegressor) -> float:
    """Fitted tree count — method-card risk R1: HGBT's early_stopping='auto'
    engages above 10k samples, so nominal max_iter is NOT matched capacity
    across libraries; every GBDT row logs the effective count to aux."""
    inner = clipped.inner
    est = inner.steps[-1][1] if isinstance(inner, Pipeline) else inner
    if isinstance(est, HistGradientBoostingRegressor):
        return float(est.n_iter_)
    if isinstance(inner, CatBoostPoisson):
        return float(inner.model.tree_count_)
    if hasattr(est, "booster_"):  # LightGBM sklearn wrapper
        return float(est.booster_.num_trees())
    return float("nan")  # deterministic GLMs: no tree count


def read_reference() -> dict:
    return json.loads(REFERENCE.read_text(encoding="utf-8"))
