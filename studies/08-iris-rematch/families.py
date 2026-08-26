"""Family registry for study 08-iris-rematch — the 23-family roster.

Interface (train.py + sweeps): ``REGISTRY: name -> (builder, columns)`` where a
builder takes ``inner_splits`` (a list of (train_idx, val_idx) pairs or None)
and returns an unfitted estimator; ``fit_model(name, X, y, groups)`` computes
GROUP-AWARE inner splits and fits; ``fit_predict_proba`` / ``dev_brier`` take
prepared DataFrames (with group_id) and never leak `species`/`group_id` into
features.

Post-red-team revisions (2026-08-25, all registered before gates):
- Every internal CV (calibration, kNN tuning, stacking) receives PRE-COMPUTED
  StratifiedGroupKFold(3) splits so the twin group (iris rows 102/143) can never
  straddle an inner train/validation boundary — the study's own gate law applied
  inside the estimators.
- ``CalibratedClassifierCV(..., ensemble=False)`` everywhere: the base model is
  fit on ALL train rows and only the calibration map is learned out-of-fold —
  the pure "calibration lane" the capture rule (RQ4) needs.
- SVC's internal ``probability=True`` (row-level 5-fold Platt) is BANNED; the
  svm families are external group-aware Platt calibrations of a probability-free
  SVC.
- Sealed-coda entries ``coda_primary`` / ``coda_challenger`` read the committed
  ``sweeps/coda_manifest.json`` written by the frozen analysis — the branch
  selection is data, not a post-selection code edit; train.py keeps its single
  edited FAMILY line.

All estimators seeded ESTIMATOR_SEED. Eligibility (MIN_RUNG) and era tags below.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
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
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.svm import SVC

STUDY_DIR = Path(__file__).resolve().parent

ESTIMATOR_SEED = 20260907
INNER_FOLDS = 3

FEATURE_COLUMNS = [
    "sepal_length_cm",
    "sepal_width_cm",
    "petal_length_cm",
    "petal_width_cm",
]
PETAL_COLUMNS = ["petal_length_cm", "petal_width_cm"]
SEPAL_COLUMNS = ["sepal_length_cm", "sepal_width_cm"]
GROUP_COLUMN = "group_id"
TARGET_COLUMN = "is_virginica"

ANCHOR = "anchor_lda4"
CONTROL = "lda_sepal"


def inner_splits(y: Any, groups: Any) -> list[tuple[np.ndarray, np.ndarray]]:
    """Group-aware stratified inner-CV splits (twins never straddle)."""
    y_arr = np.asarray(y)
    g_arr = np.asarray(groups)
    skf = StratifiedGroupKFold(
        n_splits=INNER_FOLDS, shuffle=True, random_state=ESTIMATOR_SEED
    )
    return list(skf.split(np.zeros(len(y_arr)), y_arr, g_arr))


def _add_petal_area(X: Any) -> np.ndarray:
    """Append petal_length*petal_width. Column order is FEATURE_COLUMNS."""
    arr = np.asarray(X, dtype=float)
    return np.column_stack([arr, arr[:, 2] * arr[:, 3]])


class _SubsetWrapper(BaseEstimator, ClassifierMixin):
    """Fit ``base`` on a baked subset of the incoming train rows (positional).

    Used ONLY by the sealed-coda entries: the position list comes from the
    committed ``sweeps/coda_manifest.json`` (written by the frozen analysis
    selection rule, never by hand). Evaluation rows pass through untouched.
    An empty ``keep_positions`` means "use every train row".
    """

    def __init__(self, base: Any = None, keep_positions: tuple[int, ...] = ()):
        self.base = base
        self.keep_positions = keep_positions

    def fit(self, X, y):
        if self.keep_positions:
            pos = list(self.keep_positions)
            Xs = X.iloc[pos] if hasattr(X, "iloc") else np.asarray(X)[pos]
            ys = y.iloc[pos] if hasattr(y, "iloc") else np.asarray(y)[pos]
        else:
            Xs, ys = X, y
        self.model_ = clone(self.base)
        self.model_.fit(Xs, ys)
        self.classes_ = self.model_.classes_
        return self

    def predict_proba(self, X):
        return self.model_.predict_proba(X)

    def predict(self, X):
        return self.model_.predict(X)


# ---------------------------------------------------------------------------
# builders — each takes inner_splits (list | None) and returns an unfitted model
# ---------------------------------------------------------------------------

def _lda(splits=None) -> Any:
    return LinearDiscriminantAnalysis(solver="svd")


def _qda(splits=None) -> Any:
    return QuadraticDiscriminantAnalysis(reg_param=0.1)


def _gnb(splits=None) -> Any:
    return GaussianNB()


def _lda_shrinkage(splits=None) -> Any:
    return LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")


def _lda_platt(splits=None) -> Any:
    return CalibratedClassifierCV(
        LinearDiscriminantAnalysis(solver="svd"),
        method="sigmoid",
        cv=splits,
        ensemble=False,
    )


def _lda_isotonic(splits=None) -> Any:
    return CalibratedClassifierCV(
        LinearDiscriminantAnalysis(solver="svd"),
        method="isotonic",
        cv=splits,
        ensemble=False,
    )


def _logit_l2(splits=None) -> Any:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", max_iter=1000)),
        ]
    )


def _logit_area(splits=None) -> Any:
    return Pipeline(
        [
            ("area", FunctionTransformer(_add_petal_area)),
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", max_iter=1000)),
        ]
    )


def _knn_tuned(splits=None) -> Any:
    # Fixed grid {3,5,7,9}; a k infeasible at a rung (k > inner-fold fit size)
    # scores error_score=nan and drops out of selection; if EVERY candidate is
    # nan the refit raises and the fold-eval is recorded as a crash row — the
    # registered failure policy (research_plan §5), never a silent substitute.
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
        cv=splits,
        error_score=np.nan,
        n_jobs=1,
    )


def _svc_rbf_raw() -> Any:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", SVC(kernel="rbf", C=1.0, gamma="scale", probability=False,
                        random_state=ESTIMATOR_SEED)),
        ]
    )


def _svc_linear_raw() -> Any:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", SVC(kernel="linear", C=1.0, probability=False,
                        random_state=ESTIMATOR_SEED)),
        ]
    )


def _svm_rbf_platt(splits=None) -> Any:
    return CalibratedClassifierCV(
        _svc_rbf_raw(), method="sigmoid", cv=splits, ensemble=False
    )


def _svm_linear_platt(splits=None) -> Any:
    return CalibratedClassifierCV(
        _svc_linear_raw(), method="sigmoid", cv=splits, ensemble=False
    )


def _rf(splits=None) -> Any:
    return RandomForestClassifier(
        n_estimators=300, max_depth=4, min_samples_leaf=2, random_state=ESTIMATOR_SEED
    )


def _rf_isotonic(splits=None) -> Any:
    return CalibratedClassifierCV(
        RandomForestClassifier(
            n_estimators=200, max_depth=4, min_samples_leaf=2,
            random_state=ESTIMATOR_SEED,
        ),
        method="isotonic",
        cv=splits,
        ensemble=False,
    )


def _extratrees(splits=None) -> Any:
    return ExtraTreesClassifier(
        n_estimators=300, max_depth=4, min_samples_leaf=2, random_state=ESTIMATOR_SEED
    )


def _hgbt(splits=None) -> Any:
    # study 07's small-sample sizing, unchanged
    return HistGradientBoostingClassifier(
        min_samples_leaf=5, max_leaf_nodes=4, early_stopping=False,
        random_state=ESTIMATOR_SEED,
    )


def _hgbt_isotonic(splits=None) -> Any:
    return CalibratedClassifierCV(_hgbt(), method="isotonic", cv=splits, ensemble=False)


def _gpc_rbf(splits=None) -> Any:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", GaussianProcessClassifier(
                kernel=ConstantKernel(1.0) * RBF(1.0), random_state=ESTIMATOR_SEED)),
        ]
    )


def _mlp_small(splits=None) -> Any:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", MLPClassifier(hidden_layer_sizes=(16,), alpha=1e-2, solver="lbfgs",
                                  max_iter=2000, random_state=ESTIMATOR_SEED)),
        ]
    )


def _tabpfn(splits=None) -> Any:
    # v2 = the Nature-2025 checkpoint (Prior-Labs/TabPFN-v2-clf, public,
    # ungated). Pinned explicitly: the 8.4.0 package's "auto" path resolves to
    # a newer checkpoint family that requires a browser license flow. Spike
    # 2026-08-25: bit-identical same-seed CPU fits, 0.099 s warm at n=60.
    from tabpfn import TabPFNClassifier  # optional extra "foundation"
    from tabpfn.constants import ModelVersion

    return TabPFNClassifier.create_default_for_version(
        ModelVersion.V2, n_estimators=4, device="cpu", random_state=ESTIMATOR_SEED
    )


def _tabpfn_e16(splits=None) -> Any:
    from tabpfn import TabPFNClassifier
    from tabpfn.constants import ModelVersion

    return TabPFNClassifier.create_default_for_version(
        ModelVersion.V2, n_estimators=16, device="cpu", random_state=ESTIMATOR_SEED
    )


def _vote_soft(splits=None) -> Any:
    return VotingClassifier(
        estimators=[("lda", _lda()), ("gpc", _gpc_rbf()), ("hgbt", _hgbt())],
        voting="soft",
    )


def _stack_logit(splits=None) -> Any:
    # NESTED-CONTEXT AMENDMENT (2026-08-25, committed before Stage B; parade
    # E0023 recorded the original wiring's crash honestly): precomputed absolute
    # splits cannot survive the stack's internal cross-fitting refits on row
    # subsets ("cross_val_predict only works for partitions"). The inner svm
    # therefore uses cv=3 stratified — LAWFUL THIS STUDY because the non-sealed
    # pool contains no multi-row group (the twin pair sealed together; data
    # card §NEW), so row-level and group-aware inner splits coincide.
    return StackingClassifier(
        estimators=[
            ("lda", _lda()),
            ("svm", _svm_rbf_platt(3)),
            ("hgbt", _hgbt()),
            ("gnb", _gnb()),
        ],
        final_estimator=LogisticRegression(max_iter=1000),
        cv=splits,
        stack_method="predict_proba",
    )


def _coda_entry(track_key: str) -> Callable[..., Any]:
    def build_coda(splits=None) -> Any:
        manifest_path = STUDY_DIR / "sweeps" / "coda_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        spec = manifest[track_key]
        base_builder, _cols = REGISTRY[spec["family"]]
        # base built with cv=3 (not precomputed splits): under Branch W the
        # wrapper refits on a baked subset, where absolute splits would break —
        # same nested-context amendment and same no-multi-row-group lawfulness
        # argument as _stack_logit.
        return _SubsetWrapper(
            base=base_builder(3),
            keep_positions=tuple(spec["train_positions"]),
        )

    return build_coda


REGISTRY: dict[str, tuple[Callable[..., Any], list[str]]] = {
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

# Sealed-coda entries (branch resolved by the committed manifest, not by code).
REGISTRY["coda_primary"] = (_coda_entry("primary"), FEATURE_COLUMNS)
REGISTRY["coda_challenger"] = (_coda_entry("challenger"), FEATURE_COLUMNS)

# Era tags (research_plan §5, LDA-family adjustment capture).
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

# Rung eligibility: smallest n_train at which the family enters the arena guard
# family. Absent = eligible at every rung. The guard family is FIXED by this
# matrix; failed/short cells occupy their slot with t = -inf (research_plan §5).
MIN_RUNG: dict[str, int] = {
    "lda_isotonic": 30,
    "rf_isotonic": 30,
    "hgbt_isotonic": 30,
    "svm_rbf_platt": 12,
    "svm_linear_platt": 12,
    "stack_logit": 20,
}

# "LDA-family adjustment" capture set (RQ4 — observed capture ratio, NON-causal:
# two calibration maps + one covariance-shrinkage estimator).
RECALIBRATED_FISHER: tuple[str, ...] = ("lda_platt", "lda_isotonic", "lda_shrinkage")

# Registered TabPFN fallbacks (dormant — the 2026-08-25 spike PASSED). Frozen
# substitution map, method_card §fallbacks: tabpfn -> nystroem_logit,
# tabpfn_e16 -> mlp_bag5, coda branch-G challenger -> gpc_rbf.

_NEEDS_SPLITS: frozenset[str] = frozenset(
    {
        "lda_platt", "lda_isotonic", "knn_tuned", "svm_rbf_platt",
        "svm_linear_platt", "rf_isotonic", "hgbt_isotonic", "stack_logit",
        "coda_primary", "coda_challenger",
    }
)


def eligible(name: str, n_train: int) -> bool:
    return n_train >= MIN_RUNG.get(name, 0)


def build(name: str, y: Any = None, groups: Any = None) -> Any:
    """Build an unfitted estimator; CV families get group-aware inner splits."""
    builder, _ = REGISTRY[name]
    if name in _NEEDS_SPLITS:
        if y is None or groups is None:
            raise ValueError(
                f"{name} needs group-aware inner splits: pass y and groups to build()"
            )
        return builder(inner_splits(y, groups))
    return builder()


def fit_model(name: str, X: Any, y: Any, groups: Any) -> Any:
    model = build(name, y=y, groups=groups)
    model.fit(X, y)
    return model


def columns_for(name: str) -> list[str]:
    """Feature columns; coda entries resolve through the committed manifest."""
    if name.startswith("coda_"):
        manifest_path = STUDY_DIR / "sweeps" / "coda_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return list(REGISTRY[manifest[name.removeprefix("coda_")]["family"]][1])
    return list(REGISTRY[name][1])


def fit_predict_proba(
    name: str, train: pd.DataFrame, evaluation: pd.DataFrame,
    target: str = TARGET_COLUMN,
) -> np.ndarray:
    columns = columns_for(name)
    model = fit_model(name, train[columns], train[target], train[GROUP_COLUMN])
    return model.predict_proba(evaluation[columns])[:, 1]


def dev_brier(
    name: str, train: pd.DataFrame, evaluation: pd.DataFrame,
    target: str = TARGET_COLUMN,
) -> float:
    proba = fit_predict_proba(name, train, evaluation, target)
    return float(brier_score_loss(evaluation[target], proba))


def positions_sha256(positions: list[int] | tuple[int, ...]) -> str:
    payload = ",".join(str(int(p)) for p in sorted(positions))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()
