"""Categorical encoder factory for Klein Auto Research studies.

Ported as-is from the model-survey campaign's ``lib/encoders.py`` (7 kinds,
battle-tested across 215 experiments) — only the module docstring changed.
Returns an sklearn `ColumnTransformer` configured with the requested encoding
strategy on categorical columns. Numeric columns get median-imputed +
StandardScaler by default (override via `numeric_strategy`).

Supported `kind` values:
- "ohe"        — OneHotEncoder (sparse output by default; `min_frequency` exposed)
- "ordinal"    — OrdinalEncoder (integer codes, unknown→-1)
- "target"     — sklearn 1.3+ TargetEncoder (cross-fit on training)
- "frequency"  — count-encoding via category_encoders.CountEncoder
- "hashing"    — sklearn FeatureHasher (n_features parameter)
- "james-stein"— category_encoders.JamesSteinEncoder
- "native"     — passthrough as `category` dtype (for LightGBM/CatBoost native cat)

`category_encoders` (used by "frequency" and "james-stein") is NOT a core
Klein dependency — both branches import it lazily and raise a clear
`RuntimeError` naming the missing package if it isn't installed, rather than
failing at module import time for callers who never use those two kinds.
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    OneHotEncoder,
    OrdinalEncoder,
    StandardScaler,
    TargetEncoder,
)


class CategoricalTokenTransformer(BaseEstimator, TransformerMixin):
    """Convert categorical rows to stable ``column=value`` token lists.

    This top-level estimator replaces the former nested functions/lambdas so
    hashing preprocessors survive ``joblib`` round trips.
    """

    def __init__(self, columns: list[str]) -> None:
        self.columns = columns

    def fit(self, X: Any, y: Any = None) -> CategoricalTokenTransformer:
        values = np.asarray(X, dtype=object)
        if values.ndim != 2 or values.shape[1] != len(self.columns):
            raise ValueError(
                f"expected {len(self.columns)} categorical columns, got {values.shape}"
            )
        self.n_features_in_ = values.shape[1]
        return self

    def transform(self, X: Any) -> list[list[str]]:
        values = np.asarray(X, dtype=object)
        if values.ndim != 2 or values.shape[1] != len(self.columns):
            raise ValueError(
                f"expected {len(self.columns)} categorical columns, got {values.shape}"
            )
        return [
            [
                f"{column}={value}"
                for column, value in zip(self.columns, row, strict=True)
            ]
            for row in values
        ]


class SafeCategoricalImputer(BaseEstimator, TransformerMixin):
    """Encode arbitrary scalar categories as strings with a collision-free NA token."""

    _MISSING = "__KLEIN_MISSING__"

    def fit(self, X: Any, y: Any = None) -> SafeCategoricalImputer:
        values = np.asarray(X, dtype=object)
        if values.ndim != 2:
            raise ValueError(f"categorical input must be 2-D, got {values.shape}")
        self.n_features_in_ = values.shape[1]
        return self

    @staticmethod
    def _encode(value: Any) -> str:
        missing = pd.isna(value)
        if isinstance(missing, (bool, np.bool_)) and missing:
            return SafeCategoricalImputer._MISSING
        value_type = f"{type(value).__module__}.{type(value).__qualname__}"
        return f"{value_type}:{value!r}"

    def transform(self, X: Any) -> np.ndarray:
        values = np.asarray(X, dtype=object)
        if values.ndim != 2 or values.shape[1] != self.n_features_in_:
            raise ValueError(
                f"expected {self.n_features_in_} categorical columns, got {values.shape}"
            )
        encoded = np.empty(values.shape, dtype=object)
        for index, value in np.ndenumerate(values):
            encoded[index] = self._encode(value)
        return encoded


class NativeCategoricalPreprocessor(BaseEstimator, TransformerMixin):
    """Impute numeric data while retaining pandas categorical dtypes."""

    _MISSING = "__KLEIN_MISSING__"

    def __init__(
        self,
        numeric_cols: list[str],
        categorical_cols: list[str],
        numeric_strategy: str = "standard",
    ) -> None:
        self.numeric_cols = numeric_cols
        self.categorical_cols = categorical_cols
        self.numeric_strategy = numeric_strategy

    def _frame(self, X: Any) -> pd.DataFrame:
        if isinstance(X, pd.DataFrame):
            return X
        columns = [*self.numeric_cols, *self.categorical_cols]
        return pd.DataFrame(X, columns=columns)

    def fit(self, X: Any, y: Any = None) -> NativeCategoricalPreprocessor:
        frame = self._frame(X)
        missing = [
            column
            for column in [*self.numeric_cols, *self.categorical_cols]
            if column not in frame.columns
        ]
        if missing:
            raise ValueError(f"missing preprocessing columns: {missing}")
        self.numeric_pipeline_ = _numeric_pipeline(self.numeric_strategy)
        if self.numeric_cols:
            self.numeric_pipeline_.fit(frame[self.numeric_cols], y)

        self.categories_: dict[str, list[Any]] = {}
        self.missing_tokens_: dict[str, str] = {}
        for column in self.categorical_cols:
            values = frame[column].astype(object)
            present_strings = {value for value in values.dropna() if isinstance(value, str)}
            missing_token = self._MISSING
            while missing_token in present_strings:
                missing_token += "_"
            self.missing_tokens_[column] = missing_token
            values = values.where(values.notna(), missing_token)
            categories = list(pd.unique(values))
            if missing_token not in categories:
                categories.append(missing_token)
            self.categories_[column] = categories
        self.feature_names_in_ = np.asarray(frame.columns, dtype=object)
        self.n_features_in_ = frame.shape[1]
        return self

    def transform(self, X: Any) -> pd.DataFrame:
        if not hasattr(self, "categories_"):
            raise RuntimeError("NativeCategoricalPreprocessor must be fitted first")
        frame = self._frame(X)
        result = pd.DataFrame(index=frame.index)
        if self.numeric_cols:
            numeric = self.numeric_pipeline_.transform(frame[self.numeric_cols])
            result[self.numeric_cols] = np.asarray(numeric)
        for column in self.categorical_cols:
            values = frame[column].astype(object)
            values = values.where(values.notna(), self.missing_tokens_[column])
            values = values.where(values.isin(self.categories_[column]), None)
            result[column] = pd.Categorical(
                values,
                categories=self.categories_[column],
            )
        return result[[*self.numeric_cols, *self.categorical_cols]]

    def get_feature_names_out(self, input_features: Any = None) -> np.ndarray:
        return np.asarray([*self.numeric_cols, *self.categorical_cols], dtype=object)


class SparseColumnTransformer(ColumnTransformer):
    """A serializable ``ColumnTransformer`` that guarantees CSR output."""

    def fit_transform(self, X: Any, y: Any = None, **params: Any):
        from scipy import sparse

        return sparse.csr_matrix(super().fit_transform(X, y, **params))

    def transform(self, X: Any, **params: Any):
        from scipy import sparse

        return sparse.csr_matrix(super().transform(X, **params))


def _numeric_pipeline(strategy: str = "standard") -> Pipeline:
    """Median impute + scale (or passthrough)."""
    steps: list[tuple[str, Any]] = [("impute", SimpleImputer(strategy="median"))]
    if strategy == "standard":
        steps.append(("scale", StandardScaler()))
    elif strategy == "robust":
        from sklearn.preprocessing import RobustScaler

        steps.append(("scale", RobustScaler()))
    elif strategy == "quantile":
        from sklearn.preprocessing import QuantileTransformer

        steps.append(
            (
                "scale",
                QuantileTransformer(
                    output_distribution="normal", random_state=42
                ),
            )
        )
    elif strategy == "passthrough":
        pass
    else:
        raise ValueError(f"unknown numeric_strategy: {strategy}")
    return Pipeline(steps)


def _cat_imputer() -> SafeCategoricalImputer:
    return SafeCategoricalImputer()


def build_preprocessor(
    numeric_cols: list[str],
    categorical_cols: list[str],
    *,
    kind: str = "ohe",
    numeric_strategy: str = "standard",
    min_frequency: int | None = 20,
    n_hash_features: int = 64,
    target_smooth: float | str = "auto",
    task: Literal["classification", "regression"] = "classification",
) -> ColumnTransformer | NativeCategoricalPreprocessor:
    """Build a `ColumnTransformer` for the given encoding strategy."""
    if task not in ("classification", "regression"):
        raise ValueError("task must be 'classification' or 'regression'")
    num_pipe = _numeric_pipeline(numeric_strategy)

    if kind == "ohe":
        cat_pipe = Pipeline(
            [
                ("impute", _cat_imputer()),
                (
                    "encode",
                    OneHotEncoder(
                        handle_unknown="ignore",
                        min_frequency=min_frequency,
                        sparse_output=True,
                    ),
                ),
            ]
        )
    elif kind == "ordinal":
        cat_pipe = Pipeline(
            [
                ("impute", _cat_imputer()),
                (
                    "encode",
                    OrdinalEncoder(
                        handle_unknown="use_encoded_value",
                        unknown_value=-1,
                    ),
                ),
            ]
        )
    elif kind == "target":
        cat_pipe = Pipeline(
            [
                ("impute", _cat_imputer()),
                (
                    "encode",
                    TargetEncoder(
                        smooth=target_smooth,
                        target_type=(
                            "binary" if task == "classification" else "continuous"
                        ),
                        random_state=42,
                    ),
                ),
            ]
        )
    elif kind == "frequency":
        try:
            from category_encoders import CountEncoder
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "category-encoders not installed (need `uv add category-encoders`, "
                "or run with `uv sync --extra category-encoders` once that extra "
                "is added to pyproject.toml) — required for encoder kind='frequency'"
            ) from e
        cat_pipe = Pipeline(
            [("impute", _cat_imputer()), ("encode", CountEncoder())]
        )
    elif kind == "hashing":
        from sklearn.feature_extraction import FeatureHasher

        cat_pipe = Pipeline(
            [
                ("impute", _cat_imputer()),
                ("tokenize", CategoricalTokenTransformer(categorical_cols)),
                (
                    "hash",
                    FeatureHasher(n_features=n_hash_features, input_type="string"),
                ),
            ]
        )
    elif kind == "james-stein":
        try:
            from category_encoders import JamesSteinEncoder
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "category-encoders not installed (need `uv add category-encoders`, "
                "or run with `uv sync --extra category-encoders` once that extra "
                "is added to pyproject.toml) — required for encoder kind='james-stein'"
            ) from e
        cat_pipe = Pipeline(
            [("impute", _cat_imputer()), ("encode", JamesSteinEncoder())]
        )
    elif kind == "native":
        return NativeCategoricalPreprocessor(
            numeric_cols=numeric_cols,
            categorical_cols=categorical_cols,
            numeric_strategy=numeric_strategy,
        )
    else:
        raise ValueError(f"unknown encoder kind: {kind}")

    transformer_type = SparseColumnTransformer if kind == "hashing" else ColumnTransformer
    return transformer_type(
        transformers=[
            ("num", num_pipe, numeric_cols),
            ("cat", cat_pipe, categorical_cols),
        ],
        remainder="drop",
        # Preserve v1's dense OHE contract for estimators such as sklearn HGBT;
        # only hashing has a v0.2 guarantee of sparse output.
        sparse_threshold=1.0 if kind == "hashing" else 0.0,
    )
