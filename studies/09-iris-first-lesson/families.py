"""Family registry for study 09-iris-first-lesson — the frozen 10-family roster.

Interface (train.py + sweeps): ``REGISTRY: name -> (builder, columns)`` where a
builder takes ``inner_splits`` (a list of (train_idx, val_idx) pairs or None)
and returns an unfitted estimator; ``fit_model(name, X, y, groups)`` computes
GROUP-AWARE inner splits and fits; ``fit_predict_proba`` / ``dev_brier`` take
prepared DataFrames (with group_id) and never leak `species`/`group_id` into
features.

Study-009 registration (frozen at the METHOD gate, BEFORE any 09 measurement;
research_plan §2/§5/§7). Deltas from study 08's registry, each registered here:

- ROSTER FREEZE. Exactly ten arena families: 1 anchor (``anchor_lda4``),
  7 challengers (``CHALLENGERS``, registry order = the parade order), 2 controls
  (``lda_petal``, ``lda_sepal``). 08's other thirteen families are NOT
  re-registered: the calibration-capture lane (lda_platt / lda_isotonic /
  rf_isotonic / hgbt_isotonic) is retired with 08's RQ4, the GPC class is
  excluded for 08's separability pathology, and gnb / logit_area /
  svm_linear_platt / rf / extratrees / mlp_small / tabpfn_e16 / vote_soft /
  stack_logit are dropped so the guard family is the fixed 42 cells
  (7 challengers x 6 rungs) research_plan §6 registers. Configurations are
  otherwise byte-equivalent to 08's builders except the seed constant.
- ESTIMATOR_SEED = 20260912 (the 07/08 split=estimator idiom, registered
  explicitly), replacing 08's 20260907. ``INNER_FOLDS = 3`` and the precomputed
  group-aware inner-split law are unchanged: every internal CV (calibration,
  kNN tuning) receives PRE-COMPUTED StratifiedGroupKFold(3, shuffle=True,
  random_state=ESTIMATOR_SEED) splits so the twin group (iris rows 102/143) can
  never straddle an inner train/validation boundary — the study's own gate law
  applied inside the estimators. ``assert ESTIMATOR_SEED < 2**32`` guards the
  overflow trap that bit BOTH predecessors (claim 08#C11).
- ``CalibratedClassifierCV(..., ensemble=False)``: the base model is fit on ALL
  train rows and only the calibration map is learned out-of-fold.
- SVC's internal ``probability=True`` (row-level 5-fold Platt) stays BANNED;
  ``svm_rbf_platt`` is an external group-aware Platt calibration of a
  probability-free SVC.
- FALLBACKS. ``nystroem_logit`` is REGISTERED (not merely commented) as the
  frozen, DORMANT substitute for ``tabpfn`` via the ``FALLBACKS`` map — declared
  before outcomes, exactly as 08's method_card §fallbacks froze it. The
  2026-08-25 spike PASSED and TabPFN is live, so the substitution is not in
  force; it would activate only if TabPFN cannot run at parade time, and the
  substitution would be committed with its reason before any substituted fit is
  summarized.
- CODA AMENDMENT (research_plan §7, red-team item 8). Sealed-coda entries
  ``coda_primary`` / ``coda_challenger`` read the committed
  ``sweeps/coda_manifest.json`` written by the frozen analysis — the branch
  selection is data, not a post-selection code edit; train.py keeps its single
  edited FAMILY line. 08 built the coda base with a literal ``cv=3`` on the
  argument that the non-sealed pool held no multi-row group; that argument does
  NOT port to split seed 20260912, so 09's coda base is built through the
  NORMAL builder path on the BAKED SUBSET's own y and groups — ``knn_tuned`` and
  ``svm_rbf_platt`` therefore receive group-aware precomputed splits inside the
  coda too. ``_SubsetWrapper`` subsets the groups array with the same positions
  it subsets X and y with. Under Branch B, building ``coda_challenger`` RAISES:
  the challenger seal stays shut by pre-registered rule.

All estimators seeded ESTIMATOR_SEED. Eligibility (MIN_RUNG) and era tags below.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, TransformerMixin, clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.discriminant_analysis import (
    LinearDiscriminantAnalysis,
    QuadraticDiscriminantAnalysis,
)
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.kernel_approximation import Nystroem
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

STUDY_DIR = Path(__file__).resolve().parent

ESTIMATOR_SEED = 20260912
INNER_FOLDS = 3

# The overflow trap that crashed a seed namespace in BOTH predecessors
# (claim 08#C11): sklearn's random_state domain is [0, 2**32 - 1). Every sweep
# asserts its own seed domain in its header; this is the estimator namespace's.
assert ESTIMATOR_SEED < 2**32, f"ESTIMATOR_SEED {ESTIMATOR_SEED} outside sklearn's seed domain"

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


def _take(values: Any, positions: list[int]) -> Any:
    """Positional subset that works for DataFrame / Series / ndarray / None."""
    if values is None:
        return None
    if hasattr(values, "iloc"):
        return values.iloc[positions]
    return np.asarray(values)[positions]


class _SubsetWrapper(BaseEstimator, ClassifierMixin):
    """Fit ``base`` on a baked subset of the incoming train rows (positional).

    Used ONLY by the sealed-coda entries: the position list comes from the
    committed ``sweeps/coda_manifest.json`` (written by the frozen analysis
    selection rule, never by hand). Evaluation rows pass through untouched.
    An empty ``keep_positions`` means "use every train row".

    009 AMENDMENT (research_plan §7): ``fit`` accepts and FORWARDS ``groups``,
    subsetting the groups array with the same positions it subsets X and y
    with, so a group-aware base stays group-aware after the bake. When ``base``
    is None the base is built lazily from the SUBSET via the normal
    :func:`build` path (the sweep-side call, where groups arrive at fit time);
    ``build`` pre-builds it the same way from the same subset for train.py's
    ``model.fit(X, y)`` call, so both paths yield the identical estimator.
    """

    def __init__(
        self,
        base: Any = None,
        keep_positions: tuple[int, ...] = (),
        family: str | None = None,
    ):
        self.base = base
        self.keep_positions = keep_positions
        self.family = family

    def fit(self, X, y, groups=None):
        pos = list(self.keep_positions)
        if pos:
            Xs, ys, gs = _take(X, pos), _take(y, pos), _take(groups, pos)
        else:
            Xs, ys, gs = X, y, groups
        base = self.base
        if base is None:
            if self.family is None or gs is None:
                raise ValueError(
                    "coda subset wrapper needs either a pre-built base or "
                    "family + groups (group-aware coda base, research_plan §7)"
                )
            base = build(self.family, y=ys, groups=gs)
        self.model_ = clone(base)
        self.model_.fit(Xs, ys)
        self.classes_ = self.model_.classes_
        self.groups_ = gs
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


def _lda_shrinkage(splits=None) -> Any:
    return LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")


def _logit_l2(splits=None) -> Any:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)),
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


def _svm_rbf_platt(splits=None) -> Any:
    return CalibratedClassifierCV(
        _svc_rbf_raw(), method="sigmoid", cv=splits, ensemble=False
    )


def _hgbt(splits=None) -> Any:
    # study 07's small-sample sizing, unchanged
    return HistGradientBoostingClassifier(
        min_samples_leaf=5, max_leaf_nodes=4, early_stopping=False,
        random_state=ESTIMATOR_SEED,
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


class _NystroemCapped(BaseEstimator, TransformerMixin):
    """RBF Nystroem features with the registered ``min(cap, n_train - 1)`` cap.

    08's method_card §fallbacks registered ``n_components = min(30, n_train−1)``;
    sklearn's ``Nystroem`` takes a fixed integer, so the rung-dependent cap is
    resolved here at fit time. Nothing else differs from ``Nystroem``.
    """

    def __init__(self, cap: int = 30, random_state: int | None = None):
        self.cap = cap
        self.random_state = random_state

    def fit(self, X, y=None):
        n_components = max(1, min(int(self.cap), len(X) - 1))
        self.nystroem_ = Nystroem(
            n_components=n_components, random_state=self.random_state
        ).fit(X)
        return self

    def transform(self, X):
        return self.nystroem_.transform(X)


def _nystroem_logit(splits=None) -> Any:
    # REGISTERED DORMANT FALLBACK for tabpfn (FALLBACKS below) — the frozen
    # substitution from 08's method_card §fallbacks, carried verbatim:
    # Pipeline(StandardScaler, Nystroem(RBF, n_components=min(30, n_train-1),
    # random_state=ESTIMATOR_SEED), LogisticRegression C=1.0 lbfgs
    # max_iter=1000). The rung-dependent cap keeps the registered family legal
    # at every rung — same eligibility as the tabpfn it would replace.
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("rff", _NystroemCapped(cap=30, random_state=ESTIMATOR_SEED)),
            ("clf", LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)),
        ]
    )


def _coda_entry(track_key: str) -> Callable[..., Any]:
    def build_coda(splits=None, *, y=None, groups=None) -> Any:
        spec = coda_spec(track_key)
        keep = spec["keep_positions"]
        # 009 AMENDMENT (research_plan §7, red-team item 8): the base is built
        # through the NORMAL builder path on the BAKED SUBSET's own y/groups,
        # so knn_tuned / svm_rbf_platt get group-aware precomputed splits that
        # are valid for the rows they will actually be fit on. 08 used a
        # literal cv=3 here on a no-multi-row-group argument that does not port
        # to split seed 20260912.
        base = None
        if y is not None and groups is not None:
            pos = list(keep)
            y_sub = _take(y, pos) if pos else y
            g_sub = _take(groups, pos) if pos else groups
            base = build(spec["family"], y=y_sub, groups=g_sub)
        return _SubsetWrapper(base=base, keep_positions=keep, family=spec["family"])

    return build_coda


REGISTRY: dict[str, tuple[Callable[..., Any], list[str]]] = {
    ANCHOR: (_lda, FEATURE_COLUMNS),
    "lda_shrinkage": (_lda_shrinkage, FEATURE_COLUMNS),
    "qda": (_qda, FEATURE_COLUMNS),
    "logit_l2": (_logit_l2, FEATURE_COLUMNS),
    "knn_tuned": (_knn_tuned, FEATURE_COLUMNS),
    "svm_rbf_platt": (_svm_rbf_platt, FEATURE_COLUMNS),
    "hgbt": (_hgbt, FEATURE_COLUMNS),
    "tabpfn": (_tabpfn, FEATURE_COLUMNS),
    "lda_petal": (_lda, PETAL_COLUMNS),
    CONTROL: (_lda, SEPAL_COLUMNS),
    # Registered dormant fallback (declared before outcomes) — never in
    # CHALLENGERS, never an arena guard cell unless a committed substitution
    # activates FALLBACKS below.
    "nystroem_logit": (_nystroem_logit, FEATURE_COLUMNS),
}

CONTROLS: tuple[str, ...] = ("lda_petal", "lda_sepal")

#: The parade order (research_plan §3 step 9): one run-one per name, in
#: registry order, on the PRIMARY track. Also the 7 rows of the fixed 42-cell
#: guard family (research_plan §6).
CHALLENGERS: tuple[str, ...] = (
    "lda_shrinkage",
    "qda",
    "logit_l2",
    "knn_tuned",
    "svm_rbf_platt",
    "hgbt",
    "tabpfn",
)

#: Frozen TabPFN substitution map, declared BEFORE outcomes (08 method_card
#: §fallbacks; research_plan §12). DORMANT — the 2026-08-25 spike PASSED and
#: TabPFN is live. A substitution activates only if TabPFN cannot run at parade
#: time, and would be committed with its reason before any substituted fit is
#: summarized. 08's other two rows (tabpfn_e16 -> mlp_bag5, coda branch-G
#: challenger -> gpc_rbf) are not re-registered: neither family is in 09's roster.
FALLBACKS: dict[str, str] = {"tabpfn": "nystroem_logit"}

# Sealed-coda entries (branch resolved by the committed manifest, not by code).
REGISTRY["coda_primary"] = (_coda_entry("primary"), FEATURE_COLUMNS)
REGISTRY["coda_challenger"] = (_coda_entry("challenger"), FEATURE_COLUMNS)

# Era tags — the ninety-years spine of the talk (research_plan §1). Descriptive
# provenance labels for the method, not claims about implementations.
ERA: dict[str, str] = {
    ANCHOR: "1936",           # Fisher, Ann. Eugen. 1936
    "lda_petal": "1936",      # same estimator, feature control
    CONTROL: "1936",          # same estimator, feature control
    "qda": "1970s",           # quadratic discriminant, classical multivariate era
    "logit_l2": "1970s",      # Nelder & Wedderburn GLM 1972 (Cox 1958 logit)
    "knn_tuned": "1970s",     # Cover & Hart 1967, Stone 1977
    "svm_rbf_platt": "1990s", # Boser/Guyon/Vapnik 1992; Platt scaling 1999
    "lda_shrinkage": "2000s", # sklearn shrinkage="auto" = Ledoit & Wolf 2004
    "hgbt": "2000s",          # Friedman gradient boosting 2001 (histogram variants later)
    "tabpfn": "2025",         # TabPFN v2, Nature 2025
    "nystroem_logit": "2000s",  # Williams & Seeger 2001 / random features 2007 (dormant)
}

# Rung eligibility: smallest n_train at which the family enters the arena guard
# family. 009 registration: ALL SEVEN CHALLENGERS ARE ELIGIBLE AT EVERY RUNG
# {60,45,30,20,12,8} — the guard family is the FIXED 42 cells (research_plan
# §6) and a family may not disappear from it. Where a cell cannot fit (a
# calibration fold with one class, a kNN grid that is all-nan) the fold-eval is
# recorded as a crash row and the cell occupies its slot as a never-firing
# placeholder with t = -inf. 08's staggered MIN_RUNG (svm 12, isotonic 30,
# stack 20) is retired with the families it gated.
MIN_RUNG: dict[str, int] = {
    ANCHOR: 8,
    "lda_shrinkage": 8,
    "qda": 8,
    "logit_l2": 8,
    "knn_tuned": 8,
    "svm_rbf_platt": 8,
    "hgbt": 8,
    "tabpfn": 8,
    "lda_petal": 8,
    CONTROL: 8,
    "nystroem_logit": 8,
}

_NEEDS_SPLITS: frozenset[str] = frozenset(
    {"knn_tuned", "svm_rbf_platt", "coda_primary", "coda_challenger"}
)

#: Coda entries take raw y + groups (not precomputed splits): they must subset
#: BOTH by the baked positions before deriving their base's inner splits.
_CODA_ENTRIES: frozenset[str] = frozenset({"coda_primary", "coda_challenger"})


def coda_spec(track_key: str) -> dict[str, Any]:
    """Resolve one sealed-coda track from the committed manifest.

    ``sweeps/coda_manifest.json`` (written by the frozen analysis before the
    confirmation ack) carries ``branch`` ("A" | "B"), ``families``
    (track -> registered family), ``train_positions`` ([] = every train row),
    ``positions_sha256``, and ``bands`` (track -> numeric band). The last three
    may be given once (shared by both tracks) or as a {track: value} mapping.

    Branch B raises for the challenger track: the seal stays shut by rule.
    """
    manifest_path = STUDY_DIR / "sweeps" / "coda_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    branch = str(manifest["branch"]).upper()
    if branch not in {"A", "B"}:
        raise ValueError(
            f"coda manifest branch must be 'A' or 'B', got {manifest['branch']!r}"
        )
    if track_key == "challenger" and branch == "B":
        raise RuntimeError(
            "Branch B: challenger seal stays shut by pre-registered rule "
            "(research_plan §7 — no licensed challenger comparison existed)"
        )
    families_map = manifest["families"]
    if track_key not in families_map:
        raise RuntimeError(
            f"coda manifest (branch {branch}) registers no family for track {track_key!r}"
        )
    family = families_map[track_key]
    if family not in REGISTRY:
        raise ValueError(f"coda manifest names an unregistered family: {family!r}")
    positions = _per_track(manifest.get("train_positions", []), track_key, default=[])
    keep = tuple(int(p) for p in positions)
    published = _per_track(manifest.get("positions_sha256", ""), track_key, default="")
    if published:
        actual = positions_sha256(keep)
        if actual != published:
            raise ValueError(
                f"coda manifest positions_sha256 mismatch for track {track_key!r}: "
                f"published {published}, positions hash to {actual} "
                "(convention: families.positions_sha256 — sorted ints, comma-joined, ascii)"
            )
    return {
        "branch": branch,
        "family": family,
        "keep_positions": keep,
        "band": _per_track(manifest.get("bands", {}), track_key, default=None),
    }


def _per_track(value: Any, track_key: str, *, default: Any) -> Any:
    """Accept a manifest value shared by both tracks OR a {track: value} map."""
    if isinstance(value, dict):
        return value.get(track_key, default)
    return value


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
        if name in _CODA_ENTRIES:
            # The coda builder subsets y AND groups by its baked positions and
            # then re-enters build() for its base — group-aware inside the bake.
            return builder(y=y, groups=groups)
        return builder(inner_splits(y, groups))
    return builder()


def fit_model(name: str, X: Any, y: Any, groups: Any) -> Any:
    model = build(name, y=y, groups=groups)
    model.fit(X, y)
    return model


def columns_for(name: str) -> list[str]:
    """Feature columns; coda entries resolve through the committed manifest."""
    if name.startswith("coda_"):
        return list(REGISTRY[coda_spec(name.removeprefix("coda_"))["family"]][1])
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
