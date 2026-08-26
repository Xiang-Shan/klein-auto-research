"""families.py — the pre-registered model set, defined ONCE for the whole study.

Stable study library code, NOT the mutable experiment surface (`train.py` is).
It exists so that the anchor measured by the Phase-0 split lottery and the anchor
run on the ledger are provably the same object: the floor and the thing the floor
judges cannot drift apart if they are built by the same function.

Registered set (the ladder's rungs, `study.yaml:phases`):

===================  =========================================================
anchor_lda4          Fisher 1936, all four measurements — the incumbent
logit                logistic regression (1944 / 1958)
knn7                 k-nearest neighbours, k=7, distance-weighted (1951 / 1967)
svm_rbf              support vector machine, RBF kernel (1995)
hgbt                 histogram gradient boosting, sized for n≈60 (2001 / 2019)
lda_petal            LDA on the two petal measurements only (RQ2)
lda_sepal            LDA on the two sepal measurements only (RQ3 control)
===================  =========================================================

Every estimator is unfitted when returned; nothing here reads data, touches the
split, or writes anything.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from prepare import FEATURE_COLUMNS, PETAL_COLUMNS, SEPAL_COLUMNS
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

#: Fixed estimator seed. Only SVC's internal Platt-scaling CV and HGBT consume it;
#: LDA and kNN are deterministic (which is exactly why the k-seed fit-noise floor
#: is registered as degenerate — see sweeps/kseed_floor.py).
ESTIMATOR_SEED = 20260828

ANCHOR = "anchor_lda4"

#: Challengers named in RQ1, in ladder order.
CHALLENGERS = ("logit", "knn7", "svm_rbf", "hgbt")

#: Feature-set ablations (RQ2 / RQ3). Same estimator, fewer inputs.
ABLATIONS = ("lda_petal", "lda_sepal")


def _lda() -> LinearDiscriminantAnalysis:
    # solver="svd" is sklearn's default and the one whose direction the METHOD-gate
    # from-scratch check reproduces (cosine >= 1 - 1e-12).
    return LinearDiscriminantAnalysis(solver="svd")


def _logit() -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    penalty=None,
                    solver="lbfgs",
                    max_iter=1000,
                    class_weight=None,
                ),
            ),
        ]
    )


def _knn7() -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", KNeighborsClassifier(n_neighbors=7, weights="distance")),
        ]
    )


def _svm_rbf() -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "clf",
                SVC(
                    kernel="rbf",
                    C=1.0,
                    gamma="scale",
                    probability=True,
                    class_weight=None,
                    random_state=ESTIMATOR_SEED,
                ),
            ),
        ]
    )


def _hgbt() -> HistGradientBoostingClassifier:
    # Sized for n~60: without these caps the default (31 leaves, 20-leaf minimum)
    # memorizes a 60-row training partition.
    return HistGradientBoostingClassifier(
        min_samples_leaf=5,
        max_leaf_nodes=4,
        early_stopping=False,
        random_state=ESTIMATOR_SEED,
    )


#: name -> (estimator factory, feature columns).
REGISTRY: dict[str, tuple[Callable[[], Any], list[str]]] = {
    ANCHOR: (_lda, FEATURE_COLUMNS),
    "logit": (_logit, FEATURE_COLUMNS),
    "knn7": (_knn7, FEATURE_COLUMNS),
    "svm_rbf": (_svm_rbf, FEATURE_COLUMNS),
    "hgbt": (_hgbt, FEATURE_COLUMNS),
    "lda_petal": (_lda, PETAL_COLUMNS),
    "lda_sepal": (_lda, SEPAL_COLUMNS),
}

#: Every family the Phase-0 split lottery measures: the anchor plus everything the
#: ladder compares against it.
LOTTERY_FAMILIES: tuple[str, ...] = (ANCHOR, *CHALLENGERS, *ABLATIONS)


def build(name: str) -> tuple[Any, list[str]]:
    """Return `(unfitted estimator, feature columns)` for a registered family."""
    if name not in REGISTRY:
        raise KeyError(f"unknown family {name!r}; registered: {sorted(REGISTRY)}")
    factory, columns = REGISTRY[name]
    return factory(), list(columns)


def fit_predict_proba(
    name: str,
    train: pd.DataFrame,
    evaluation: pd.DataFrame,
    *,
    target: str = "is_virginica",
) -> np.ndarray:
    """Fit `name` on `train` and return P(is_virginica=1) for `evaluation` rows.

    Only the family's own feature columns are ever read — never `species` (a
    perfect proxy for the target) and never `group_id`.
    """
    model, columns = build(name)
    model.fit(train[columns], train[target])
    proba = np.asarray(model.predict_proba(evaluation[columns]))
    classes = np.asarray(model.classes_)
    positive = int(np.flatnonzero(classes == 1)[0])
    return proba[:, positive]


def dev_brier(
    name: str,
    train: pd.DataFrame,
    development: pd.DataFrame,
    *,
    target: str = "is_virginica",
) -> float:
    """Development-partition Brier score for one family. Lower is better."""
    scores = fit_predict_proba(name, train, development, target=target)
    return float(brier_score_loss(development[target], scores))
