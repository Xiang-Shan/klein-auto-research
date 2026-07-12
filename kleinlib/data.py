"""Data loading and splitting utilities for Klein Auto Research studies.

Generalizes the model-survey campaign's ``lib/data.py``. That module hardcoded
a single CSV path (``data/prepared/insurance_claims_prepared.csv``) and a
single target column (``claim_status``) because every one of its 215
experiments loaded the same dataset. A Klein study can point at any prepared
CSV/parquet file, or pull straight from the shared ``data_hub`` repo, so those
specifics are call-time arguments here rather than module constants — see
:func:`load_prepared`, :func:`load_data_hub`, and the optional
:func:`load_xy` helper (a parametrized version of the campaign's old
``load_data()``).

The :func:`fixed_split` defaults (``seed=42``, ``test_size=0.2``,
stratified) are the literal campaign values, kept as defaults on purpose:
they are the reproducibility contract ("split-identity gate" in study
cards), not domain-specific hardcoding, so studies replicating the
model-survey doctrine get identical splits with zero configuration.

War story (the value-pattern check): pandas cannot tell a Yes/No column
apart from any other ``object``/``string``-dtype column by dtype alone — a
naive ``dtype == "object"`` check let a Yes/No column slip through the
numeric/categorical router untouched in the ancestor campaign. Everything in
this module that classifies a column checks the actual *value set*, never
the dtype label. See :func:`detect_yes_no_columns`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit, train_test_split

#: Canonical split contract for studies replicating the model-survey doctrine.
RANDOM_SEED = 42
TEST_SIZE = 0.2

_YES_NO = frozenset({"Yes", "No"})


def load_prepared(path: str | Path) -> pd.DataFrame:
    """Load a prepared dataset from CSV or Parquet, dispatched by extension.

    Pure I/O — no target-column knowledge, no splitting. Pair with
    :func:`load_xy` (or drop the target column yourself) plus
    :func:`fixed_split`.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".parquet", ".pq"):
        return pd.read_parquet(path)
    raise ValueError(
        f"unsupported file extension {suffix!r} for {path} (want .csv or .parquet)"
    )


def load_xy(path: str | Path, target_column: str) -> tuple[pd.DataFrame, pd.Series]:
    """Load a prepared file and split it into `(X, y)` on `target_column`.

    A generalized, parametrized replacement for the campaign's
    ``load_data()``, which hardcoded both the file path and the target
    column name (``claim_status``). Both are now call-time arguments; no
    dtype coercion is applied to `y` (the campaign forced ``.astype(int)`,
    which only makes sense for a binary target — severity/regression studies
    need their own float target untouched).
    """
    df = load_prepared(path)
    X = df.drop(columns=[target_column], errors="ignore")
    y = df[target_column]
    return X, y


def _bundled_dataset_dir(name: str) -> Path:
    """Path of the repo-bundled ``datasets/<name>/`` directory.

    Anchored on this module's own location (repo root = parent of the
    ``kleinlib`` package), NEVER on the working directory — CI and study
    scripts routinely run with cwd outside the repo. The directory only
    exists in a clone of the klein-auto-research repo; a bare
    ``pip install git+…`` ships the ``kleinlib`` package alone.
    """
    return Path(__file__).resolve().parent.parent / "datasets" / name


def load_data_hub(name: str) -> Any:
    """Load a dataset by name — from a data-hub if configured, else the repo bundle.

    Resolution order (the loader prints a ``data source:`` line naming which
    branch fed the run, so every log records its data provenance):

    1. **``$DATA_HUB``** (explicit env var only — there is deliberately no
       implicit home-directory default): inserts the hub root onto
       ``sys.path`` and calls its ``loaders.python.hub.load_dataset(name)``.
       Whatever that loader returns (typically a DataFrame, sometimes a dict
       of DataFrames for multi-table datasets) is returned unchanged.
    2. **Repo-bundled copy** at ``datasets/<name>/`` (single ``*.csv`` /
       ``*.csv.gz`` file, read with a plain ``pandas.read_csv`` — the same
       call the hub loader uses, so both branches yield identical frames
       from identical bytes).
    3. Otherwise raises with the available options spelled out.
    """
    hub_root = os.environ.get("DATA_HUB")
    if hub_root:
        if hub_root not in sys.path:
            sys.path.insert(0, hub_root)
        from loaders.python.hub import load_dataset  # type: ignore[import-not-found]

        result = load_dataset(name)
        print(f"data source: hub — {Path(hub_root) / 'datasets' / name}")
        return result

    bundled = _bundled_dataset_dir(name)
    if bundled.is_dir():
        files = sorted(bundled.glob("*.csv")) + sorted(bundled.glob("*.csv.gz"))
        if len(files) != 1:
            raise FileNotFoundError(
                f"bundled dataset dir {bundled} must contain exactly one "
                f"*.csv/*.csv.gz file, found {len(files)}: {[f.name for f in files]}"
            )
        frame = pd.read_csv(files[0])
        print(f"data source: bundled — {files[0]}")
        return frame

    raise FileNotFoundError(
        f"cannot resolve dataset {name!r}: $DATA_HUB is not set and no bundled "
        f"copy exists at {bundled}. Options: (1) export DATA_HUB=<your data-hub "
        f"root>; (2) run from a clone of the klein-auto-research repo, which "
        f"bundles its study datasets under datasets/; (3) point the study at a "
        f"local file instead (data source csv:<path> via kleinlib.data.load_prepared)."
    )


def fixed_split(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    seed: int = RANDOM_SEED,
    test_size: float = TEST_SIZE,
    stratify: bool | None = None,
    task: Literal["classification", "regression"] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Campaign-identical train/val split: seed=42, test_size=0.2, stratified.

    Keeping these defaults identical across every experiment in a study (and
    across studies replicating the model-survey doctrine) is what makes a
    primary metric directly comparable between them. Returns
    ``(X_tr, X_va, y_tr, y_va)``.
    """
    if task not in (None, "classification", "regression"):
        raise ValueError("task must be 'classification' or 'regression'")
    if stratify is None:
        use_stratify = task != "regression"
    else:
        use_stratify = stratify
    if task == "regression" and use_stratify:
        raise ValueError(
            "regression targets cannot use stratification; pass stratify=False"
        )
    return train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=seed,
        stratify=y if use_stratify else None,
    )


SplitTask = Literal["classification", "regression"]
SplitStrategy = Literal["stratified", "random", "group", "time"]


def _validate_three_way_inputs(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    task: SplitTask,
    strategy: SplitStrategy,
    development_size: float,
    test_size: float,
) -> None:
    if task not in ("classification", "regression"):
        raise ValueError("task must be explicitly 'classification' or 'regression'")
    if strategy not in ("stratified", "random", "group", "time"):
        raise ValueError(
            "strategy must be one of 'stratified', 'random', 'group', or 'time'"
        )
    if strategy == "stratified" and task != "classification":
        raise ValueError("stratified splitting is supported only for classification")
    if len(X) != len(y):
        raise ValueError(f"X and y have different lengths: {len(X)} != {len(y)}")
    if len(X) < 3:
        raise ValueError("a three-way split requires at least three rows")
    if not (0.0 < development_size < 1.0):
        raise ValueError("development_size must be between 0 and 1")
    if not (0.0 < test_size < 1.0):
        raise ValueError("test_size must be between 0 and 1")
    if development_size + test_size >= 1.0:
        raise ValueError("development_size + test_size must be less than 1")


def _take_rows(obj: pd.DataFrame | pd.Series, positions: np.ndarray):
    return obj.iloc[positions]


def three_way_split(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    task: SplitTask,
    strategy: SplitStrategy | None = None,
    development_size: float = 0.2,
    test_size: float = 0.2,
    seed: int = RANDOM_SEED,
    groups: pd.Series | np.ndarray | list[Any] | None = None,
    time_values: pd.Series | np.ndarray | list[Any] | None = None,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.Series,
    pd.Series,
    pd.Series,
]:
    """Return deterministic train/development/test partitions for v2 studies.

    ``task`` is mandatory so continuous targets are never accidentally
    stratified.  The default strategy is ``stratified`` for classification
    and ``random`` for regression.  ``group`` keeps every group wholly inside
    one partition; ``time`` sorts oldest-to-newest and assigns the newest rows
    to the sealed test set.
    """
    resolved_strategy: SplitStrategy = strategy or (
        "stratified" if task == "classification" else "random"
    )
    _validate_three_way_inputs(
        X,
        y,
        task=task,
        strategy=resolved_strategy,
        development_size=development_size,
        test_size=test_size,
    )

    n_rows = len(X)
    positions = np.arange(n_rows)

    if resolved_strategy in ("stratified", "random"):
        stratify_values = np.asarray(y) if resolved_strategy == "stratified" else None
        holdout_size = development_size + test_size
        try:
            train_idx, holdout_idx = train_test_split(
                positions,
                test_size=holdout_size,
                random_state=seed,
                stratify=stratify_values,
            )
            holdout_stratify = (
                np.asarray(y)[holdout_idx]
                if resolved_strategy == "stratified"
                else None
            )
            dev_idx, test_idx = train_test_split(
                holdout_idx,
                test_size=test_size / holdout_size,
                random_state=seed + 1,
                stratify=holdout_stratify,
            )
        except ValueError as exc:
            raise ValueError(
                f"cannot create safe {resolved_strategy} three-way split: {exc}"
            ) from exc
    elif resolved_strategy == "group":
        if groups is None:
            raise ValueError("groups are required when strategy='group'")
        group_values = np.asarray(groups)
        if len(group_values) != n_rows:
            raise ValueError("groups must have one value per row")
        if pd.isna(group_values).any():
            raise ValueError("groups must not contain missing values")
        if np.unique(group_values).size < 3:
            raise ValueError("group splitting requires at least three distinct groups")
        outer = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        remain_idx, test_idx = next(outer.split(positions, y, group_values))
        inner = GroupShuffleSplit(
            n_splits=1,
            test_size=development_size / (1.0 - test_size),
            random_state=seed + 1,
        )
        train_rel, dev_rel = next(
            inner.split(remain_idx, np.asarray(y)[remain_idx], group_values[remain_idx])
        )
        train_idx = remain_idx[train_rel]
        dev_idx = remain_idx[dev_rel]
    else:
        if time_values is None:
            raise ValueError("time_values are required when strategy='time'")
        times = np.asarray(time_values)
        if len(times) != n_rows:
            raise ValueError("time_values must have one value per row")
        if pd.isna(times).any():
            raise ValueError("time_values must not contain missing values")
        try:
            ordered = np.argsort(times, kind="stable")
        except TypeError as exc:
            raise ValueError("time_values must be mutually orderable") from exc
        ordered_times = times[ordered]
        boundaries = np.flatnonzero(ordered_times[1:] != ordered_times[:-1]) + 1
        if len(boundaries) < 2:
            raise ValueError(
                "time splitting requires at least three distinct time values so "
                "equal timestamps never cross partitions"
            )
        n_test = max(1, int(np.ceil(n_rows * test_size)))
        n_dev = max(1, int(np.ceil(n_rows * development_size)))
        if n_test + n_dev >= n_rows:
            raise ValueError(
                "requested time split leaves no training rows; use smaller holdouts"
            )
        target_test_start = n_rows - n_test
        # Reserve at least one earlier boundary for train/development.
        test_start = int(
            min(boundaries[1:], key=lambda boundary: abs(boundary - target_test_start))
        )
        earlier = boundaries[boundaries < test_start]
        target_dev_start = n_rows - n_test - n_dev
        dev_start = int(
            min(earlier, key=lambda boundary: abs(boundary - target_dev_start))
        )
        train_idx = ordered[:dev_start]
        dev_idx = ordered[dev_start:test_start]
        test_idx = ordered[test_start:]

    return (
        _take_rows(X, np.asarray(train_idx)),
        _take_rows(X, np.asarray(dev_idx)),
        _take_rows(X, np.asarray(test_idx)),
        _take_rows(y, np.asarray(train_idx)),
        _take_rows(y, np.asarray(dev_idx)),
        _take_rows(y, np.asarray(test_idx)),
    )


def feature_column_groups(X: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return `(numeric_cols, categorical_cols)` for downstream preprocessors.

    Pandas `string` dtype is treated as categorical; numeric and boolean are
    treated as numeric. The pandas nullable `Int64` (with `<NA>`) is also
    numeric.
    """
    numeric_cols = X.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical_cols = [c for c in X.columns if c not in numeric_cols]
    return numeric_cols, categorical_cols


def detect_yes_no_columns(df: pd.DataFrame) -> list[str]:
    """Return columns whose non-null value set is exactly `{"Yes", "No"}`.

    War story: `dtype == "object"` (or pandas `string` dtype) cannot
    distinguish a Yes/No column from any other string column — this checks
    the actual values instead of trusting the dtype label. A column with
    only "Yes" (or only "No") present still counts: its non-null values are
    a non-empty subset of `{"Yes", "No"}`.
    """
    out = []
    for col in df.columns:
        vals = set(df[col].dropna().unique())
        if vals and vals <= _YES_NO:
            out.append(col)
    return out


def yes_no_to_int(
    df: pd.DataFrame, columns: list[str] | None = None
) -> pd.DataFrame:
    """Return a copy of `df` with Yes/No columns mapped to 1/0.

    `columns` defaults to :func:`detect_yes_no_columns(df)` when omitted.
    """
    out = df.copy()
    cols = columns if columns is not None else detect_yes_no_columns(df)
    mapping = {"Yes": 1, "No": 0}
    for col in cols:
        out[col] = out[col].map(mapping)
    return out
