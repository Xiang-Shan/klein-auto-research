"""Family registry for study 08-iris-rematch — the 23-family roster.

Same interface contract as study 07's families.py (train.py compatibility):
``REGISTRY: name -> (factory, columns)``, ``build(name)``, ``fit_predict_proba``,
``dev_brier``. Additions for the rematch: ``ERA`` tags, ``MIN_RUNG`` eligibility,
and ``_SubsetWrapper`` for the sealed-coda ``<family>@n<k>`` wrapper entries
(registered at METHOD gate with baked train-position lists; train.py keeps its
single edited FAMILY line).

Design brief: presentation task 20260828 reference/study08_design_brief_v1.md §6.
All estimators seeded ESTIMATOR_SEED. Calibrators/tuners run inner-CV on the
train rows they receive — never on development rows (leakage law).
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.discriminant_analysis import (
    LinearDiscriminantAnalysis,
    QuadraticDiscriminantAnalysis,
)
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
    StackingClassifier,
    VotingClassifier,
)
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import RBF, ConstantKernel
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import GridSearchCV
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.svm import SVC

ESTIMATOR_SEED = 20260907

FEATURE_COLUMNS = [
    "sepal_length_cm",
    "sepal_width_cm",
    "petal_length_cm",
    "petal_width_cm",
]
PETAL_COLUMNS = ["petal_length_cm", "petal_width_cm"]
SEPAL_COLUMNS = ["sepal_length_cm", "sepal_width_cm"]

ANCHOR = "anchor_lda4"
CONTROL = "lda_sepal"


def _add_petal_area(X: Any) -> np.ndarray:
    """Append petal_length*petal_width. Column order is FEATURE_COLUMNS."""
    arr = np.asarray(X, dtype=float)
    return np.column_stack([arr, arr[:, 2] * arr[:, 3]])


class _SubsetWrapper(BaseEstimator, ClassifierMixin):
    """Fit ``base`` on a baked subset of the incoming train rows (positional).

    Used ONLY by the sealed-coda ``<family>@n<k>`` wrapper entries: the position
    list is pre-registered (design brief §9, quota scan of the declared train
    partition, seed 20260901999) and baked at METHOD gate. Evaluation rows pass
    through untouched.
    """

    def __init__(self, base: Any = None, keep_positions: tuple[int, ...] = ()):
        self.base = base
        self.keep_positions = keep_positions

    def fit(self, X, y):
        pos = list(self.keep_positions)
        Xs = X.iloc[pos] if hasattr(X, "iloc") else np.asarray(X)[pos]
        ys = y.iloc[pos] if hasattr(y, "iloc") else np.asarray(y)[pos]
        self.model_ = clone(self.base)
        self.model_.fit(Xs, ys)
        self.classes_ = self.model_.classes_
        return self

    def predict_proba(self, X):
        return self.model_.predict_proba(X)

    def predict(self, X):
        return self.model_.predict(X)


def _lda() -> Any:
    return LinearDiscriminantAnalysis(solver="svd")


def _qda() -> Any:
    return QuadraticDiscriminantAnalysis(reg_param=0.1)


def _gnb() -> Any:
    return GaussianNB()


def _lda_shrinkage() -> Any:
    return LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")


def _lda_platt() -> Any:
    return CalibratedClassifierCV(
        LinearDiscriminantAnalysis(solver="svd"), method="sigmoid", cv=3
    )


def _lda_isotonic() -> Any:
    return CalibratedClassifierCV(
        LinearDiscriminantAnalysis(solver="svd"), method="isotonic", cv=3
    )


def _logit_l2() -> Any:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    C=1.0, penalty="l2", solver="lbfgs", max_iter=1000
                ),
            ),
        ]
    )


def _logit_area() -> Any:
    return Pipeline(
        [
            ("area", FunctionTransformer(_add_petal_area)),
            ("scale", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    C=1.0, penalty="l2", solver="lbfgs", max_iter=1000
                ),
            ),
        ]
    )


def _knn_tuned() -> Any:
    # k values infeasible at a rung (k > inner-fold size) score error_score=nan
    # and drop out of the selection; if every k is infeasible the fit raises and
    # the arena records a crash row — the honest outcome.
    base = Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", KNeighborsClassifier(weights="distance")),
        ]
    )
    return GridSearchCV(
        base,
        param_grid={"clf__n_neighbors": [3, 5, 7, 9]},
        scoring="neg_brier_score",
        cv=3,
        error_score=np.nan,
        n_jobs=1,
    )


def _svm_rbf_platt() -> Any:
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
                    random_state=ESTIMATOR_SEED,
                ),
            ),
        ]
    )


def _svm_linear_platt() -> Any:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "clf",
                SVC(
                    kernel="linear",
                    C=1.0,
                    probability=True,
                    random_state=ESTIMATOR_SEED,
                ),
            ),
        ]
    )


def _rf() -> Any:
    return RandomForestClassifier(
        n_estimators=300,
        max_depth=4,
        min_samples_leaf=2,
        random_state=ESTIMATOR_SEED,
    )


def _rf_isotonic() -> Any:
    return CalibratedClassifierCV(
        RandomForestClassifier(
            n_estimators=200,
            max_depth=4,
            min_samples_leaf=2,
            random_state=ESTIMATOR_SEED,
        ),
        method="isotonic",
        cv=3,
    )


def _extratrees() -> Any:
    return ExtraTreesClassifier(
        n_estimators=300,
        max_depth=4,
        min_samples_leaf=2,
        random_state=ESTIMATOR_SEED,
    )


def _hgbt() -> Any:
    # study 07's small-sample sizing, unchanged
    return HistGradientBoostingClassifier(
        min_samples_leaf=5,
        max_leaf_nodes=4,
        early_stopping=False,
        random_state=ESTIMATOR_SEED,
    )


def _hgbt_isotonic() -> Any:
    return CalibratedClassifierCV(_hgbt(), method="isotonic", cv=3)


def _gpc_rbf() -> Any:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "clf",
                GaussianProcessClassifier(
                    kernel=ConstantKernel(1.0) * RBF(1.0),
                    random_state=ESTIMATOR_SEED,
                ),
            ),
        ]
    )


def _mlp_small() -> Any:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "clf",
                MLPClassifier(
                    hidden_layer_sizes=(16,),
                    alpha=1e-2,
                    solver="lbfgs",
                    max_iter=2000,
                    random_state=ESTIMATOR_SEED,
                ),
            ),
        ]
    )


def _tabpfn() -> Any:
    # v2 = the Nature-2025 checkpoint (Prior-Labs/TabPFN-v2-clf, public,
    # ungated). Pinned explicitly: the 8.4.0 package's "auto" path resolves to
    # a newer checkpoint family that requires a browser license flow. Spike
    # 2026-08-25: bit-identical same-seed CPU fits, 0.099 s warm at n=60.
    from tabpfn import TabPFNClassifier  # optional extra "foundation"
    from tabpfn.constants import ModelVersion

    return TabPFNClassifier.create_default_for_version(
        ModelVersion.V2, n_estimators=4, device="cpu", random_state=ESTIMATOR_SEED
    )


def _tabpfn_e16() -> Any:
    from tabpfn import TabPFNClassifier
    from tabpfn.constants import ModelVersion

    return TabPFNClassifier.create_default_for_version(
        ModelVersion.V2, n_estimators=16, device="cpu", random_state=ESTIMATOR_SEED
    )


def _vote_soft() -> Any:
    return VotingClassifier(
        estimators=[("lda", _lda()), ("gpc", _gpc_rbf()), ("hgbt", _hgbt())],
        voting="soft",
    )


def _stack_logit() -> Any:
    return StackingClassifier(
        estimators=[
            ("lda", _lda()),
            ("svm", _svm_rbf_platt()),
            ("hgbt", _hgbt()),
            ("gnb", _gnb()),
        ],
        final_estimator=LogisticRegression(max_iter=1000),
        cv=3,
        stack_method="predict_proba",
    )


REGISTRY: dict[str, tuple[Callable[[], Any], list[str]]] = {
    ANCHOR: (_lda, FEATURE_COLUMNS),
    CONTROL: (_lda, SEPAL_COLUMNS),
    "qda": (_qda, FEATURE_COLUMNS),
    "gnb": (_gnb, FEATURE_COLUMNS),
    "lda_shrinkage": (_lda_shrinkage, FEATURE_COLUMNS),
    "lda_platt": (_lda_platt, FEATURE_COLUMNS),
    "lda_isotonic": (_lda_isotonic, FEATURE_COLUMNS),
    "logit_l2": (_logit_l2, FEATURE_COLUMNS),
    "logit_area": (_logit_area, FEATURE_COLUMNS),
    "knn_tuned": (_knn_tuned, FEATURE_COLUMNS),
    "svm_rbf_platt": (_svm_rbf_platt, FEATURE_COLUMNS),
    "svm_linear_platt": (_svm_linear_platt, FEATURE_COLUMNS),
    "rf": (_rf, FEATURE_COLUMNS),
    "rf_isotonic": (_rf_isotonic, FEATURE_COLUMNS),
    "extratrees": (_extratrees, FEATURE_COLUMNS),
    "hgbt": (_hgbt, FEATURE_COLUMNS),
    "hgbt_isotonic": (_hgbt_isotonic, FEATURE_COLUMNS),
    "gpc_rbf": (_gpc_rbf, FEATURE_COLUMNS),
    "mlp_small": (_mlp_small, FEATURE_COLUMNS),
    "tabpfn": (_tabpfn, FEATURE_COLUMNS),
    "tabpfn_e16": (_tabpfn_e16, FEATURE_COLUMNS),
    "vote_soft": (_vote_soft, FEATURE_COLUMNS),
    "stack_logit": (_stack_logit, FEATURE_COLUMNS),
}

CHALLENGERS: tuple[str, ...] = tuple(
    name for name in REGISTRY if name not in (ANCHOR, CONTROL)
)

# Era tags (design brief §5, attribution rule).
ERA: dict[str, str] = {
    ANCHOR: "1936",
    CONTROL: "1936",
    "qda": "20c-stats",
    "gnb": "20c-stats",
    "lda_shrinkage": "20c-stats",
    "lda_platt": "20c-stats",
    "lda_isotonic": "20c-stats",
    "logit_l2": "20c-stats",
    "logit_area": "20c-stats",
    "knn_tuned": "20c-stats",
    "svm_rbf_platt": "modern-ml",
    "svm_linear_platt": "modern-ml",
    "rf": "modern-ml",
    "rf_isotonic": "modern-ml",
    "extratrees": "modern-ml",
    "hgbt": "modern-ml",
    "hgbt_isotonic": "modern-ml",
    "gpc_rbf": "modern-ml",
    "mlp_small": "modern-ml",
    "tabpfn": "foundation",
    "tabpfn_e16": "foundation",
    "vote_soft": "modern-ml",
    "stack_logit": "modern-ml",
}

# Rung eligibility: smallest n_train at which the family enters the arena test
# family (design brief §6). Absent = eligible at every rung.
MIN_RUNG: dict[str, int] = {
    "lda_isotonic": 30,
    "rf_isotonic": 30,
    "hgbt_isotonic": 30,
    "svm_rbf_platt": 12,
    "svm_linear_platt": 12,
    "stack_logit": 20,
}

RECALIBRATED_FISHER: tuple[str, ...] = ("lda_platt", "lda_isotonic", "lda_shrinkage")


def eligible(name: str, n_train: int) -> bool:
    return n_train >= MIN_RUNG.get(name, 0)


def build(name: str) -> Any:
    factory, _ = REGISTRY[name]
    return factory()


def fit_predict_proba(
    name: str, train: Any, evaluation: Any, target: str = "is_virginica"
) -> np.ndarray:
    _, columns = REGISTRY[name]
    model = build(name)
    model.fit(train[list(columns)], train[target])
    return model.predict_proba(evaluation[list(columns)])[:, 1]


def dev_brier(
    name: str, train: Any, evaluation: Any, target: str = "is_virginica"
) -> float:
    proba = fit_predict_proba(name, train, evaluation, target)
    return float(brier_score_loss(evaluation[target], proba))
