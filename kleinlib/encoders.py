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

from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    OneHotEncoder,
    OrdinalEncoder,
    StandardScaler,
    TargetEncoder,
)


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


def _cat_imputer() -> SimpleImputer:
    return SimpleImputer(strategy="most_frequent")


def build_preprocessor(
    numeric_cols: list[str],
    categorical_cols: list[str],
    *,
    kind: str = "ohe",
    numeric_strategy: str = "standard",
    min_frequency: int | None = 20,
    n_hash_features: int = 64,
    target_smooth: float | str = "auto",
) -> ColumnTransformer:
    """Build a `ColumnTransformer` for the given encoding strategy."""
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
                        smooth=target_smooth, target_type="binary", random_state=42
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

        # FeatureHasher expects an iterable of mapping/strings per row. Use a
        # small adapter that turns each row's categorical values into a list
        # of "col=value" tokens.
        from sklearn.preprocessing import FunctionTransformer

        def _to_tokens(X_df: pd.DataFrame) -> list[list[str]]:
            X_df = X_df.fillna("__NaN__")
            cols = X_df.columns
            return [
                [f"{c}={v}" for c, v in zip(cols, row)] for row in X_df.values
            ]

        cat_pipe = Pipeline(
            [
                ("impute", _cat_imputer()),
                ("to_df", FunctionTransformer(lambda X: pd.DataFrame(X))),
                ("tokenize", FunctionTransformer(_to_tokens)),
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
        # Passthrough — caller is expected to convert these columns to
        # pandas `category` dtype and pass them through to LightGBM /
        # CatBoost native categorical handling.
        from sklearn.preprocessing import FunctionTransformer

        def _to_category(X: pd.DataFrame) -> pd.DataFrame:
            X = X.copy()
            for col in X.columns:
                X[col] = X[col].astype("category")
            return X

        cat_pipe = Pipeline(
            [
                ("impute", _cat_imputer()),
                (
                    "to_df",
                    FunctionTransformer(
                        lambda X: pd.DataFrame(X, columns=categorical_cols)
                    ),
                ),
                ("to_category", FunctionTransformer(_to_category)),
            ]
        )
    else:
        raise ValueError(f"unknown encoder kind: {kind}")

    return ColumnTransformer(
        transformers=[
            ("num", num_pipe, numeric_cols),
            ("cat", cat_pipe, categorical_cols),
        ],
        remainder="drop",
        sparse_threshold=0.3 if kind == "ohe" else 0.0,
    )
