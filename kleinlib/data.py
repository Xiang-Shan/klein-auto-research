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

import hashlib
import os
from collections.abc import Mapping
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


def load_data_hub(name: str) -> Any:
    """Load a dataset by name — from a data-hub if configured, else the repo bundle.

    A thin wrapper over :func:`kleinlib.sources.resolve` (``hub:<name>``),
    which owns the resolution chain and prints the ``data source: ...``
    provenance line — BYTE-IDENTICAL to this function's own pre-Klein-2.0
    printed lines for the two paths that predate it, because studies
    00/05/06's run logs already contain them as evidence:

    1. **``$DATA_HUB``** (explicit env var only — there is deliberately no
       implicit home-directory default): a ``loaders.python.hub.load_dataset``
       module, if importable — whatever it returns (typically a DataFrame,
       sometimes a dict of DataFrames for multi-table datasets) comes back
       unchanged; otherwise a plain ``<name>/*.csv`` (or ``.csv.gz``)
       directory straight under ``$DATA_HUB`` (new in Klein 2.0 — a hub that
       ships no loader module is no longer a dead end).
    2. **Repo-bundled copy** at ``datasets/<name>/`` (the same single-file
       convention, read with the same plain ``pandas.read_csv``).
    3. Otherwise raises :class:`FileNotFoundError` with the available options
       spelled out — :func:`kleinlib.sources.resolve` itself raises
       :class:`kleinlib.errors.WorkflowError`; this wrapper translates it
       back to keep this function's long-standing public contract.
    """
    from .errors import WorkflowError
    from .sources import resolve

    try:
        resolved = resolve(f"hub:{name}", study_dir=None, offline=os.environ.get("KLEIN_OFFLINE") == "1")
    except WorkflowError as exc:
        raise FileNotFoundError(str(exc)) from exc
    if resolved.loaded is not None:
        return resolved.loaded
    return pd.read_csv(resolved.path)


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


# ---------------------------------------------------------------------------
# Contract-driven partitions (schema 3) — war story 8
#
# A study-09 evaluator hardcoded a retired split seed and a whole ledger lane
# measured the wrong partition; the lock's numeral scan caught it a study later.
# The fix is structural: the entrypoint never chooses a partition, it ASKS the
# contract for one, and the partition it got prints a fingerprint the notary
# compares against the one frozen at the DATA gate. A number computed on the
# wrong partition is a crash now, not a result.
# ---------------------------------------------------------------------------

#: Bump only if the canonical encoding below changes; a bump invalidates every
#: recorded fingerprint, which is why it is versioned rather than implicit.
SPLIT_FINGERPRINT_VERSION = "klein-split-v1"

#: The line every evaluator prints so the notary can check the partition.
SPLIT_FINGERPRINT_KEY = "split_fingerprint"

#: What a sealed dry-run prints to prove it ran with substituted data.
SEALED_DRYRUN_KEY = "sealed_dryrun"


def split_fingerprint(*index_arrays: Any) -> str:
    """Hash the REALIZED membership of one or more partitions.

    Order-insensitive within a partition (a partition is a set of rows, not a
    sequence) and order-sensitive between them, so ``(train, dev)`` and
    ``(dev, train)`` are different fingerprints. Row labels are canonicalized to
    text, so an int64 index and a Python-int index over the same rows agree.

    This is the counterpart of :func:`kleinlib.contract.split_fingerprint`,
    which hashes the declared POLICY. The policy says how to split; this says
    what the split actually was.
    """
    digest = hashlib.sha256()
    digest.update(SPLIT_FINGERPRINT_VERSION.encode("utf-8") + b"\n")
    digest.update(f"partitions={len(index_arrays)}\n".encode())
    for position, values in enumerate(index_arrays):
        labels = sorted(str(item) for item in _index_labels(values))
        digest.update(f"partition={position} n={len(labels)}\n".encode())
        for label in labels:
            digest.update(label.encode("utf-8") + b"\n")
    return digest.hexdigest()


def _index_labels(values: Any) -> list[Any]:
    """Row labels of a frame / series / index / array, as plain Python objects."""
    if isinstance(values, (pd.DataFrame, pd.Series)):
        return list(values.index)
    if isinstance(values, pd.Index):
        return list(values)
    return list(np.asarray(values).ravel())


def _split_task(contract: Mapping[str, Any]) -> SplitTask:
    return "classification" if contract.get("task_type") == "classification" else "regression"


def contract_split(
    study_dir: str | Path = ".", *, target: str | None = None
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """``(X_train, X_dev, X_test, y_train, y_dev, y_test)`` from ``study.yaml`` alone.

    Reads ``data.prepared_path`` and every knob of ``data.split`` — kind, seed,
    sizes, group/time column — and hands them to the UNMODIFIED
    :func:`three_way_split`, so a study that switches to this helper keeps the
    exact partitions it had. No argument of this function can change the split:
    that is the point.
    """
    from .contract import load_contract, prepared_data_path, resolve_study

    study = resolve_study(study_dir)
    contract = load_contract(study)
    data = contract.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("study.yaml:data must be a mapping")
    split = data.get("split")
    if not isinstance(split, Mapping):
        raise ValueError("study.yaml:data.split is required")
    kind = split.get("kind")
    if kind == "none":
        raise ValueError(
            "data.split.kind is 'none': this study's comparability comes from "
            "declared seed blocks, not from row partitions — build them in the "
            "entrypoint and print split_fingerprint yourself"
        )
    column = target or contract.get("target")
    if not isinstance(column, str) or not column.strip():
        raise ValueError("study.yaml:target is required to split the prepared data")

    frame = load_prepared(prepared_data_path(study, contract))
    if column not in frame.columns:
        raise ValueError(f"target column {column!r} is not in the prepared data")
    X = frame.drop(columns=[column])
    y = frame[column]
    return three_way_split(
        X,
        y,
        task=_split_task(contract),
        strategy=kind,
        development_size=float(split.get("development_size", 0.2)),
        test_size=float(split.get("test_size", 0.2)),
        seed=int(split.get("seed", RANDOM_SEED)),
        groups=frame[split["group_column"]] if kind == "group" else None,
        time_values=frame[split["time_column"]] if kind == "time" else None,
    )


def partition_fingerprints(study_dir: str | Path = ".") -> dict[str, str]:
    """``{"development": ..., "final_test": ...}`` for the contract's split.

    What ``klein gate record data`` freezes, and what ``klein run-one`` compares
    the printed line against.
    """
    X_tr, X_dev, X_te, _, _, _ = contract_split(study_dir)
    return {
        "development": split_fingerprint(X_tr, X_dev),
        "final_test": split_fingerprint(pd.concat([X_tr, X_dev]), X_te),
    }


def load_partition(
    kind: str | None = None,
    *,
    study_dir: str | Path = ".",
    target: str | None = None,
    echo: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """``(X_fit, X_eval, y_fit, y_eval)`` for one evaluation kind; prints its fingerprint.

    ``development`` fits on train and evaluates on development. ``final_test``
    fits on train + development — the frozen chosen configuration's training
    data — and evaluates on the sealed partition, once.

    ``kind`` defaults to ``KLEIN_EVALUATION_KIND``, which ``klein run-one``
    sets; an entrypoint never chooses its own partition. Under
    ``KLEIN_SEALED_DRYRUN=1`` a requested ``final_test`` is answered with the
    DEVELOPMENT data plus a ``sealed_dryrun: 1`` line: the rehearsal exercises
    the whole path and spends no seal.
    """
    kind = kind or os.environ.get("KLEIN_EVALUATION_KIND") or "development"
    if kind not in {"development", "final_test"}:
        raise ValueError(f"invalid evaluation kind {kind!r}")
    dry_run = kind == "final_test" and os.environ.get("KLEIN_SEALED_DRYRUN") == "1"
    if dry_run:
        kind = "development"

    X_tr, X_dev, X_te, y_tr, y_dev, y_te = contract_split(study_dir, target=target)
    if kind == "development":
        fit_X, eval_X, fit_y, eval_y = X_tr, X_dev, y_tr, y_dev
    else:
        fit_X, fit_y = pd.concat([X_tr, X_dev]), pd.concat([y_tr, y_dev])
        eval_X, eval_y = X_te, y_te
    if echo:
        print(f"{SPLIT_FINGERPRINT_KEY}: {split_fingerprint(fit_X, eval_X)}")
        if dry_run:
            print(f"{SEALED_DRYRUN_KEY}: 1")
    return fit_X, eval_X, fit_y, eval_y
