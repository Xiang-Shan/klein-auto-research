"""V2 three-way split strategies plus the v1 fixed-split compatibility API."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from kleinlib import data


def _frame(n=100):
    X = pd.DataFrame({"row": np.arange(n), "x": np.linspace(0.0, 1.0, n)})
    return X


def _index_digest(part: pd.DataFrame) -> str:
    """sha256 of the sorted realized index, in a platform-independent form."""
    ordered = np.sort(np.asarray(part.index))
    joined = ",".join(str(int(position)) for position in ordered)
    return hashlib.sha256(joined.encode("ascii")).hexdigest()


def test_classification_default_is_stratified_three_way():
    X = _frame()
    y = pd.Series([0, 1] * 50)
    X_tr, X_dev, X_test, y_tr, y_dev, y_test = data.three_way_split(
        X, y, task="classification"
    )
    assert (len(X_tr), len(X_dev), len(X_test)) == (60, 20, 20)
    assert [series.mean() for series in (y_tr, y_dev, y_test)] == [0.5, 0.5, 0.5]
    assert set(X_tr["row"]).isdisjoint(X_dev["row"])
    assert set(X_tr["row"]).isdisjoint(X_test["row"])


def test_three_way_split_realized_indices_match_golden_digests():
    """Golden-index evidence that the canonical v2 split is deterministic.

    `split_fingerprint` hashes the split *configuration*; this test pins the
    *realized* row memberships. The digests below were computed once from this
    exact fixture and hard-coded — they must be identical on every OS and every
    supported Python (3.11–3.14) under the locked dependency set. A mismatch
    anywhere means the same study.yaml no longer reproduces the same
    train/development/test partitions, which breaks cross-experiment metric
    comparability. Do not regenerate these digests casually: a legitimate
    update is a split-contract change and must be called out as one.
    """
    rng = np.random.default_rng(20260730)
    n = 200
    X = pd.DataFrame({"row": np.arange(n), "x": rng.normal(size=n)})
    y = pd.Series(rng.integers(0, 2, size=n))
    X_tr, X_dev, X_test, *_ = data.three_way_split(X, y, task="classification")
    assert (len(X_tr), len(X_dev), len(X_test)) == (120, 40, 40)
    assert _index_digest(X_tr) == (
        "15fd61b2ba41737b61ddd53ecdfc5342c9cf098922c93236f05ad75b5d234669"
    )
    assert _index_digest(X_dev) == (
        "e80f44f7fe23d97f1c9569b536281f60dfac2b35c523fd8ef5b87ab2ff3d230c"
    )
    assert _index_digest(X_test) == (
        "2c013c4b14b31cb5f3697b22930ba4b290318139a8ec105a20152911af976a82"
    )


def test_regression_defaults_to_random_and_fixed_split_stays_compatible():
    X = _frame()
    y = pd.Series(np.linspace(0.0, 10.0, len(X)))
    parts = data.three_way_split(X, y, task="regression")
    assert [len(part) for part in parts[:3]] == [60, 20, 20]
    X_tr, X_va, y_tr, y_va = data.fixed_split(
        X, y, task="regression", stratify=False
    )
    assert len(X_tr) == len(y_tr) == 80
    assert len(X_va) == len(y_va) == 20


def test_fixed_split_v1_default_remains_stratified():
    X = _frame(40)
    y = pd.Series([0, 1] * 20)
    _, _, y_tr, y_va = data.fixed_split(X, y)
    assert y_tr.mean() == y_va.mean() == 0.5


def test_group_split_has_no_group_leakage():
    X = _frame(120)
    y = pd.Series([0, 1] * 60)
    groups = np.repeat(np.arange(12), 10)
    X_tr, X_dev, X_test, *_ = data.three_way_split(
        X,
        y,
        task="classification",
        strategy="group",
        groups=groups,
    )
    group_sets = [set(groups[part["row"].to_numpy()]) for part in (X_tr, X_dev, X_test)]
    assert group_sets[0].isdisjoint(group_sets[1])
    assert group_sets[0].isdisjoint(group_sets[2])
    assert group_sets[1].isdisjoint(group_sets[2])


def test_time_split_is_oldest_train_newest_test():
    X = _frame(10)
    y = pd.Series(np.linspace(0.0, 1.0, 10))
    times = pd.date_range("2025-01-01", periods=10, freq="D")
    X_tr, X_dev, X_test, *_ = data.three_way_split(
        X,
        y,
        task="regression",
        strategy="time",
        time_values=times,
        development_size=0.2,
        test_size=0.2,
    )
    assert X_tr["row"].tolist() == list(range(6))
    assert X_dev["row"].tolist() == [6, 7]
    assert X_test["row"].tolist() == [8, 9]


def test_time_split_keeps_equal_timestamps_in_one_partition():
    X = _frame(12)
    y = pd.Series(np.linspace(0.0, 1.0, len(X)))
    times = np.repeat(pd.date_range("2025-01-01", periods=6, freq="D"), 2)
    X_tr, X_dev, X_test, *_ = data.three_way_split(
        X,
        y,
        task="regression",
        strategy="time",
        time_values=times,
        development_size=0.2,
        test_size=0.2,
    )
    time_sets = [set(times[part["row"].to_numpy()]) for part in (X_tr, X_dev, X_test)]
    assert time_sets[0].isdisjoint(time_sets[1])
    assert time_sets[0].isdisjoint(time_sets[2])
    assert time_sets[1].isdisjoint(time_sets[2])


def test_time_split_requires_three_distinct_time_values():
    X = _frame(8)
    y = pd.Series(np.linspace(0.0, 1.0, len(X)))
    with pytest.raises(ValueError, match="at least three distinct"):
        data.three_way_split(
            X,
            y,
            task="regression",
            strategy="time",
            time_values=[0, 0, 0, 0, 1, 1, 1, 1],
        )


def test_regression_cannot_accidentally_stratify():
    X = _frame(20)
    y = pd.Series(np.linspace(0.0, 1.0, 20))
    with pytest.raises(ValueError, match="only for classification"):
        data.three_way_split(X, y, task="regression", strategy="stratified")
