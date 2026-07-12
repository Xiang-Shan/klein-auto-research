"""Tests for kleinlib.encoders.build_preprocessor across encoder kinds.

`category_encoders` (needed by "frequency" and "james-stein") is not a core
dependency (see kleinlib/encoders.py's module docstring) — those two kinds
are skipped cleanly via `pytest.importorskip` when it isn't installed.
"target" uses sklearn's own `TargetEncoder` (a core dependency) so it is
tested directly, no skip needed.
"""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from kleinlib import encoders

NUMERIC_COLS = ["num1", "num2"]
CATEGORICAL_COLS = ["cat1", "cat2"]


def _toy_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "num1": [1.0, 2.0, None, 4.0, 5.0, 6.0],
            "num2": [10, 20, 30, 40, 50, 60],
            "cat1": ["a", "b", "a", "c", "b", "a"],
            "cat2": ["x", "x", "y", "y", "z", None],
        }
    )


def _toy_df_larger() -> tuple[pd.DataFrame, pd.Series]:
    """12 rows, 6 per class — sklearn's `TargetEncoder` cross-fits with an
    internal default `cv=5`, which needs >=5 samples per class.
    """
    n = 12
    df = pd.DataFrame(
        {
            "num1": [float(i) for i in range(n)],
            "num2": [i * 10 for i in range(n)],
            "cat1": ["a", "b", "c"] * (n // 3),
            "cat2": ["x", "y"] * (n // 2),
        }
    )
    y = pd.Series([i % 2 for i in range(n)])
    return df, y


@pytest.mark.parametrize("kind", ["ohe", "ordinal", "hashing", "native"])
def test_build_preprocessor_fit_transform(kind):
    df = _toy_df()
    pre = encoders.build_preprocessor(NUMERIC_COLS, CATEGORICAL_COLS, kind=kind)
    out = pre.fit_transform(df)
    assert out.shape[0] == len(df)


def test_build_preprocessor_target_kind():
    df, y = _toy_df_larger()
    pre = encoders.build_preprocessor(NUMERIC_COLS, CATEGORICAL_COLS, kind="target")
    out = pre.fit_transform(df, y)
    assert out.shape[0] == len(df)


def test_ohe_preserves_dense_v1_estimator_compatibility():
    pre = encoders.build_preprocessor(NUMERIC_COLS, CATEGORICAL_COLS, kind="ohe")
    transformed = pre.fit_transform(_toy_df())
    assert isinstance(transformed, np.ndarray)
    assert not sparse.issparse(transformed)


def test_build_preprocessor_target_kind_supports_regression():
    n = 30
    df = pd.DataFrame(
        {
            "num1": np.linspace(0.0, 1.0, n),
            "num2": np.arange(n),
            "cat1": ["a", "b", "c"] * 10,
            "cat2": ["x", "y"] * 15,
        }
    )
    y = pd.Series(np.linspace(10.0, 20.0, n))
    pre = encoders.build_preprocessor(
        NUMERIC_COLS, CATEGORICAL_COLS, kind="target", task="regression"
    )
    out = pre.fit_transform(df, y)
    assert out.shape == (n, 4)
    assert np.isfinite(out).all()


def test_hashing_preprocessor_is_sparse_and_joblib_serializable(tmp_path):
    df = _toy_df()
    pre = encoders.build_preprocessor(
        NUMERIC_COLS,
        CATEGORICAL_COLS,
        kind="hashing",
        n_hash_features=128,
    )
    expected = pre.fit_transform(df)
    assert sparse.issparse(expected)

    path = tmp_path / "hashing.joblib"
    joblib.dump(pre, path)
    restored = joblib.load(path)
    actual = restored.transform(df)
    assert sparse.issparse(actual)
    assert np.array_equal(expected.toarray(), actual.toarray())


def test_hashing_stays_sparse_with_numeric_only_input():
    df = _toy_df()[NUMERIC_COLS]
    pre = encoders.build_preprocessor(NUMERIC_COLS, [], kind="hashing")
    transformed = pre.fit_transform(df)
    assert sparse.isspmatrix_csr(transformed)
    assert sparse.isspmatrix_csr(pre.transform(df))


def test_native_preprocessor_preserves_categories_and_round_trips(tmp_path):
    df = _toy_df()
    pre = encoders.build_preprocessor(
        NUMERIC_COLS, CATEGORICAL_COLS, kind="native"
    )
    expected = pre.fit_transform(df)
    assert isinstance(expected, pd.DataFrame)
    assert all(isinstance(expected[col].dtype, pd.CategoricalDtype) for col in CATEGORICAL_COLS)

    path = tmp_path / "native.joblib"
    joblib.dump(pre, path)
    restored = joblib.load(path)
    unseen = df.copy()
    unseen.loc[0, "cat1"] = "unseen"
    actual = restored.transform(unseen)
    assert all(isinstance(actual[col].dtype, pd.CategoricalDtype) for col in CATEGORICAL_COLS)
    assert pd.isna(actual.loc[0, "cat1"])


def test_categorical_imputation_handles_mixed_values_without_sentinel_collision():
    df = pd.DataFrame(
        {
            "num1": [1.0, 2.0, 3.0, 4.0],
            "num2": [1, 2, 3, 4],
            "cat1": [1, "1", None, "__KLEIN_MISSING__"],
            "cat2": ["x", "x", "y", "y"],
        }
    )
    ohe = encoders.build_preprocessor(
        NUMERIC_COLS, CATEGORICAL_COLS, kind="ohe", min_frequency=None
    )
    transformed = ohe.fit_transform(df)
    assert transformed.shape[0] == len(df)

    native = encoders.build_preprocessor(
        NUMERIC_COLS, CATEGORICAL_COLS, kind="native"
    )
    native_out = native.fit_transform(df)
    assert native_out.loc[2, "cat1"] != native_out.loc[3, "cat1"]


def test_build_preprocessor_frequency_kind_or_skip():
    pytest.importorskip("category_encoders")
    df = _toy_df()
    pre = encoders.build_preprocessor(NUMERIC_COLS, CATEGORICAL_COLS, kind="frequency")
    out = pre.fit_transform(df)
    assert out.shape[0] == len(df)


def test_build_preprocessor_james_stein_kind_or_skip():
    pytest.importorskip("category_encoders")
    df = _toy_df()
    y = pd.Series([0, 1, 0, 1, 0, 1])
    pre = encoders.build_preprocessor(
        NUMERIC_COLS, CATEGORICAL_COLS, kind="james-stein"
    )
    out = pre.fit_transform(df, y)
    assert out.shape[0] == len(df)


def test_build_preprocessor_unknown_kind_raises():
    with pytest.raises(ValueError):
        encoders.build_preprocessor(NUMERIC_COLS, CATEGORICAL_COLS, kind="nope")


def test_frequency_kind_raises_clear_error_when_deps_missing(monkeypatch):
    import sys

    # Force the lazy `from category_encoders import CountEncoder` to fail
    # regardless of whether category-encoders happens to be installed here,
    # so this test is meaningful in both environments.
    monkeypatch.setitem(sys.modules, "category_encoders", None)
    with pytest.raises(RuntimeError, match="category-encoders not installed"):
        encoders.build_preprocessor(NUMERIC_COLS, CATEGORICAL_COLS, kind="frequency")
