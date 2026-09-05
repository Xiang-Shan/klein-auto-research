"""lib/iris.py -- stable library code for 15-iris-90years-relaunch.

NOT the mutable experiment surface (`study.yaml:entrypoint.mutable` names only
`train.py`). Per `research_plan.md` ("Stable library versus mutable surface")
and `method_card.md` section 3.2/3.3, this module is COMPLETE before E0001:

  - the loader for P0's raw identity counts, and a partition-consistency check
    (both independent of, and never overriding, `kleinlib.data.contract_split`);
  - the three feature sets (`all4` / `petal` / `sepal`);
  - the five model-recipe factories, exactly as fixed in `research_plan.md`'s
    recipe table and verified against `references.yaml`;
  - a single-sample bootstrap CI helper (E0001's anchor interval, P3) and a
    paired-bootstrap-under-common-random-numbers helper for an AUC
    DIFFERENCE (the two Phase-0 paired floors, `floor_modern`/`floor_ablation`);
  - the `extra={...}` block-assembly helpers for the four printed-key shapes
    `study.yaml`'s predictions comment declares: anchor / frontier / ablation
    / sealed.

Every partition decision goes through `kleinlib.data.contract_split` /
`kleinlib.data.load_partition` and NOTHING ELSE (war story 8) -- no literal
split seed appears anywhere below. The two constants this module DOES fix
(`MODEL_SEED`, `BOOTSTRAP_SEED`) are not split seeds: they never decide which
row lands in which partition, only how a model is fit (`svm_rbf`/`hgbt`'s own
`random_state=`) or how already-drawn rows are resampled.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

__all__ = [
    "FEATURE_SETS",
    "RECIPES",
    "MODEL_SEED",
    "BOOTSTRAP_SEED",
    "raw_identity_counts",
    "partition_sizes_and_total",
    "build_estimator",
    "build_recipe",
    "fit_and_score",
    "bootstrap_auc_ci",
    "paired_bootstrap_auc_delta",
    "anchor_extra",
    "frontier_extra",
    "ablation_extra",
    "sealed_extra",
]

# ---------------------------------------------------------------------------
# Feature sets (research_plan.md "Stable library versus mutable surface";
# method_card.md section 1's "ruler, not the models" and section 4).
# ---------------------------------------------------------------------------

FEATURE_SETS: dict[str, list[str]] = {
    "all4": ["sepal_length_cm", "sepal_width_cm", "petal_length_cm", "petal_width_cm"],
    "petal": ["petal_length_cm", "petal_width_cm"],
    "sepal": ["sepal_length_cm", "sepal_width_cm"],
}

# ---------------------------------------------------------------------------
# The five model recipes -- exact configs fixed in research_plan.md's recipe
# table and cross-checked against method_card.md / references.yaml.
# `MODEL_SEED` is the study's own start date (study.yaml:data.split.seed),
# reused here ONLY as the fixed `random_state=` of `svm_rbf`/`hgbt` -- the two
# recipes method_card.md section 3.3 notes carry a seed at all. It never
# decides a partition.
# ---------------------------------------------------------------------------

MODEL_SEED = 20260904

#: Bootstrap resampling seed (E0001's CI and the Phase-0 paired floors).
#: Fixed before any byte of the table was read, like every other constant in
#: this study; never used to decide a partition.
BOOTSTRAP_SEED = 20260904

_ESTIMATOR_NAMES = ("lda", "logreg_l2", "knn5", "svm_rbf", "hgbt")


def build_estimator(name: str, *, random_state: int | None = None) -> Any:
    """One unfitted sklearn estimator/pipeline for `name`.

    `name` is one of `{lda, logreg_l2, knn5, svm_rbf, hgbt}` -- the five
    configs research_plan.md's recipe table and `references.yaml` pin.
    `random_state` overrides `MODEL_SEED` for `svm_rbf`/`hgbt` ONLY (the two
    recipes that carry a seed at all; `lda`, `logreg_l2` and `knn5` have none,
    so their `fit_noise` is zero by construction -- method_card.md 3.3). Used
    by the Phase-0 `fit_noise` sweep; every development/sealed cell uses the
    default `MODEL_SEED`.
    """
    if name not in _ESTIMATOR_NAMES:
        raise ValueError(f"unknown estimator {name!r}; want one of {_ESTIMATOR_NAMES}")
    seed = MODEL_SEED if random_state is None else int(random_state)
    if name == "lda":
        return LinearDiscriminantAnalysis(solver="svd")
    if name == "logreg_l2":
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(penalty="l2", C=1.0, max_iter=1000),
        )
    if name == "knn5":
        return make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=5))
    if name == "svm_rbf":
        return make_pipeline(
            StandardScaler(),
            SVC(kernel="rbf", C=1.0, gamma="scale", probability=True, random_state=seed),
        )
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, random_state=seed)


#: study recipe id -> (estimator name, feature-set name). `lda_petal` /
#: `lda_sepal` are the ablation track's two extra cells (P12/P13); every
#: other id pairs its algorithm with `all4`, per research_plan.md.
RECIPES: dict[str, tuple[str, str]] = {
    "lda_all4": ("lda", "all4"),
    "lda_petal": ("lda", "petal"),
    "lda_sepal": ("lda", "sepal"),
    "logreg_l2": ("logreg_l2", "all4"),
    "knn5": ("knn5", "all4"),
    "svm_rbf": ("svm_rbf", "all4"),
    "hgbt": ("hgbt", "all4"),
}


def build_recipe(recipe_id: str, *, random_state: int | None = None) -> tuple[Any, list[str]]:
    """`(estimator, feature_columns)` for a study recipe id, e.g. `"lda_all4"`."""
    if recipe_id not in RECIPES:
        raise ValueError(f"unknown recipe {recipe_id!r}; want one of {sorted(RECIPES)}")
    estimator_name, feature_set = RECIPES[recipe_id]
    return build_estimator(estimator_name, random_state=random_state), FEATURE_SETS[feature_set]


def fit_and_score(
    recipe_id: str,
    X_fit: pd.DataFrame,
    y_fit: pd.Series,
    X_eval: pd.DataFrame,
    *,
    random_state: int | None = None,
) -> tuple[Any, np.ndarray, float]:
    """Fit `recipe_id` on `X_fit[cols]`/`y_fit`; return `(model, p_eval, fit_seconds)`.

    `p_eval` is P(virginica) on `X_eval[cols]` -- the same columns the model
    was fit on, selected here so every caller (train.py cells, the Phase-0
    sweep scripts) makes the same column choice the same way.
    """
    model, cols = build_recipe(recipe_id, random_state=random_state)
    t0 = time.time()
    model.fit(X_fit[cols], y_fit)
    fit_seconds = time.time() - t0
    p_eval = np.asarray(model.predict_proba(X_eval[cols]))[:, 1]
    return model, p_eval, fit_seconds


# ---------------------------------------------------------------------------
# P0: the identity anchor, asserted on the RAW loader (never the prepared
# table -- a lawful DATA-gate row drop must not manufacture a false
# refutation; data_card.md BLOCKER #1, research_plan.md).
# ---------------------------------------------------------------------------


def raw_identity_counts() -> dict[str, int]:
    """`{raw_rows, raw_versicolor, raw_virginica, raw_features}` straight from
    `sklearn.datasets.load_iris`, restricted to the hard pair -- exactly what
    P0 checks, independent of `prepare.py`'s output.
    """
    from sklearn.datasets import load_iris

    bunch = load_iris()
    y = np.asarray(bunch.target)
    mask = np.isin(y, [1, 2])  # 1 = versicolor, 2 = virginica; 0 = setosa out of scope
    return {
        "raw_rows": int(mask.sum()),
        "raw_versicolor": int((y[mask] == 1).sum()),
        "raw_virginica": int((y[mask] == 2).sum()),
        "raw_features": int(np.asarray(bunch.data).shape[1]),
    }


def partition_sizes_and_total(study_dir: str = ".") -> tuple[int, int, int, int]:
    """`(train_rows, dev_rows, test_rows, prepared_total_rows)`.

    Two independent reads of the prepared table: the CONTRACT split (via
    `kleinlib.data.contract_split`, never a literal seed) and a fresh count of
    the prepared CSV itself, so P0's `partition_sum_matches` is a real
    consistency check rather than a tautology over the same variables.
    """
    from kleinlib.contract import load_contract, prepared_data_path, resolve_study
    from kleinlib.data import contract_split, load_prepared

    study = resolve_study(study_dir)
    contract = load_contract(study)
    total_rows = len(load_prepared(prepared_data_path(study, contract)))
    X_tr, X_dev, X_te, _, _, _ = contract_split(study_dir)
    return len(X_tr), len(X_dev), len(X_te), total_rows


# ---------------------------------------------------------------------------
# Bootstrap helpers. Both skip (redraw) a degenerate single-class resample --
# at 13/12 on 25 rows that has probability ~5e-8 (method_card.md section 3.3)
# and would make roc_auc_score undefined; redrawing keeps the returned array
# at the requested length without ever admitting an undefined value. The
# guard below only ever fires on a broken RNG/inputs, not on bad luck.
# ---------------------------------------------------------------------------


def bootstrap_auc_ci(
    y: pd.Series | np.ndarray,
    p: np.ndarray,
    *,
    n_boot: int = 2000,
    seed: int = BOOTSTRAP_SEED,
    alpha: float = 0.05,
) -> tuple[float, float, int]:
    """`(ci_low, ci_high, n_boot)` -- the percentile bootstrap CI of ONE
    candidate's own ROC-AUC on rows `(y, p)`. E0001's anchor interval (P3).
    """
    y_arr = np.asarray(y)
    p_arr = np.asarray(p)
    n = y_arr.shape[0]
    rng = np.random.default_rng(seed)
    values: list[float] = []
    guard = 0
    while len(values) < n_boot:
        guard += 1
        if guard > 50 * n_boot:
            raise RuntimeError("bootstrap_auc_ci: too many degenerate resamples in a row")
        idx = rng.integers(0, n, size=n)
        y_r = y_arr[idx]
        if y_r.min() == y_r.max():
            continue
        values.append(float(roc_auc_score(y_r, p_arr[idx])))
    values.sort()
    lo = float(np.percentile(values, 100 * alpha / 2))
    hi = float(np.percentile(values, 100 * (1 - alpha / 2)))
    return lo, hi, len(values)


def paired_bootstrap_auc_delta(
    y: pd.Series | np.ndarray,
    p_reference: np.ndarray,
    p_candidate: np.ndarray,
    *,
    n_boot: int = 1000,
    seed: int = BOOTSTRAP_SEED,
) -> np.ndarray:
    """`n_boot` values of `AUC(p_candidate) - AUC(p_reference)`, ONE shared
    index draw per replicate (common random numbers by construction).

    `kleinlib.metrology.paired_bootstrap`'s generic `statistic=` callback only
    ever sees the two ALREADY-RESAMPLED series, never the resampled labels --
    fine for a row-mean statistic, not for AUC, which needs the labels
    resampled in lockstep too (method_card.md section 3.3, "paired-bootstrap
    gotcha for an AUC difference"). This is that recipe, spelled out once here
    rather than duplicated in every sweep script that needs it.
    """
    y_arr = np.asarray(y)
    ref = np.asarray(p_reference)
    cand = np.asarray(p_candidate)
    n = y_arr.shape[0]
    rng = np.random.default_rng(seed)
    values: list[float] = []
    guard = 0
    while len(values) < n_boot:
        guard += 1
        if guard > 50 * n_boot:
            raise RuntimeError("paired_bootstrap_auc_delta: too many degenerate resamples in a row")
        idx = rng.integers(0, n, size=n)
        y_r = y_arr[idx]
        if y_r.min() == y_r.max():
            continue
        delta = roc_auc_score(y_r, cand[idx]) - roc_auc_score(y_r, ref[idx])
        values.append(float(delta))
    return np.array(values)


# ---------------------------------------------------------------------------
# extra={...} block assembly -- one helper per printed-key shape study.yaml's
# predictions comment declares (anchor / frontier / ablation / sealed).
# Only the anchor shape is exercised by E0001; the other three are written
# now so this module is COMPLETE before E0001, per research_plan.md.
# ---------------------------------------------------------------------------


def anchor_extra(
    *,
    raw_counts: dict[str, int],
    partition_sum_matches: bool,
    val_accuracy: float,
    val_errors: int,
    val_rows: int,
    ci_low: float,
    ci_high: float,
    n_boot: int,
) -> dict[str, Any]:
    """The anchor cell's printed keys (E0001, `fisher` track): `raw_rows
    raw_versicolor raw_virginica raw_features partition_sum_matches
    val_accuracy val_errors ci_low ci_high ci_width n_boot`.

    `ci_low`/`ci_high` themselves print via `evaluate_estimate`'s own
    parameters, not through this dict -- only `ci_width` (derived) belongs
    here. `val_rows` is included explicitly because `evaluate_estimate` has no
    train/val-split concept and always prints `val_rows: NA` in its canonical
    block; the `fisher` track's own `val_rows: {min: 20}` guardrail needs a
    real numeric line to read.
    """
    return {
        "raw_rows": raw_counts["raw_rows"],
        "raw_versicolor": raw_counts["raw_versicolor"],
        "raw_virginica": raw_counts["raw_virginica"],
        "raw_features": raw_counts["raw_features"],
        "partition_sum_matches": int(bool(partition_sum_matches)),
        "val_accuracy": round(float(val_accuracy), 6),
        "val_errors": int(val_errors),
        "val_rows": int(val_rows),
        "ci_width": round(float(ci_high) - float(ci_low), 6),
        "n_boot": int(n_boot),
    }


def frontier_extra(
    *,
    reference_metric: float,
    candidate_metric: float,
    minimum_delta: float,
    val_accuracy: float,
    val_errors: int,
    ideal: float = 1.0,
) -> dict[str, Any]:
    """The frontier cell's printed keys (`modern` track, E0002+): `gap_in_floors
    reference_metric delta_vs_reference delta_in_floors val_accuracy
    val_errors`.

    `gap_in_floors` and `delta_in_floors` print only once `minimum_delta > 0`
    (Phase 0 has measured the floor) -- before that a prediction whose key is
    not printed reads INCONCLUSIVE rather than refuted, which is the honest
    answer (P4/P5-P8's own `inconclusive_if`).
    """
    extra: dict[str, Any] = {
        "reference_metric": round(float(reference_metric), 6),
        "delta_vs_reference": round(float(candidate_metric) - float(reference_metric), 6),
        "val_accuracy": round(float(val_accuracy), 6),
        "val_errors": int(val_errors),
    }
    if minimum_delta and minimum_delta > 0:
        extra["delta_in_floors"] = round(
            (float(candidate_metric) - float(reference_metric)) / minimum_delta, 4
        )
        extra["gap_in_floors"] = round((float(ideal) - float(reference_metric)) / minimum_delta, 4)
    return extra


def ablation_extra(
    *,
    reference_metric: float,
    candidate_metric: float,
    minimum_delta: float,
    sepal_metric: float | None = None,
) -> dict[str, Any]:
    """The ablation cell's printed keys (`ablation` track): `reference_metric
    delta_vs_reference delta_in_floors` (plus `sepal_delta_in_floors` on the
    sealed cell only, when `sepal_metric` is given).
    """
    extra: dict[str, Any] = {
        "reference_metric": round(float(reference_metric), 6),
        "delta_vs_reference": round(float(candidate_metric) - float(reference_metric), 6),
    }
    if minimum_delta and minimum_delta > 0:
        extra["delta_in_floors"] = round(
            (float(candidate_metric) - float(reference_metric)) / minimum_delta, 4
        )
        if sepal_metric is not None:
            extra["sepal_delta_in_floors"] = round(
                (float(sepal_metric) - float(reference_metric)) / minimum_delta, 4
            )
    return extra


def sealed_extra(
    *,
    base_extra: dict[str, Any],
    development_metric: float,
    sealed_metric: float,
    minimum_delta: float,
) -> dict[str, Any]:
    """Adds `sealed_shift_in_floors` on top of a frontier/ablation extra dict
    -- the sealed cell shape, which is "plus the above" per study.yaml's
    printed-key comment.
    """
    extra = dict(base_extra)
    if minimum_delta and minimum_delta > 0:
        extra["sealed_shift_in_floors"] = round(
            (float(sealed_metric) - float(development_metric)) / minimum_delta, 4
        )
    return extra
