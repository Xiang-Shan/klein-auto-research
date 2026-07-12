"""Tiny CPU fits proving the optional GBDT distributions are actually usable."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture(scope="module")
def binary_fixture() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(42)
    X = rng.normal(size=(80, 4)).astype(np.float32)
    y = (X[:, 0] + 0.2 * X[:, 1] > 0).astype(np.int64)
    return X, y


def test_lightgbm_cpu_fit(binary_fixture) -> None:
    lightgbm = pytest.importorskip("lightgbm", reason="requires the optional gbdt extra")
    X, y = binary_fixture
    model = lightgbm.LGBMClassifier(n_estimators=3, n_jobs=1, verbosity=-1, random_state=42)
    assert model.fit(X, y).predict_proba(X).shape == (len(X), 2)


def test_xgboost_cpu_fit(binary_fixture) -> None:
    xgboost = pytest.importorskip("xgboost", reason="requires the optional gbdt extra")
    X, y = binary_fixture
    model = xgboost.XGBClassifier(n_estimators=3, n_jobs=1, verbosity=0, random_state=42)
    assert model.fit(X, y).predict_proba(X).shape == (len(X), 2)


def test_catboost_cpu_fit(binary_fixture) -> None:
    catboost = pytest.importorskip("catboost", reason="requires the optional gbdt extra")
    X, y = binary_fixture
    model = catboost.CatBoostClassifier(iterations=3, thread_count=1, verbose=False, random_seed=42)
    assert model.fit(X, y).predict_proba(X).shape == (len(X), 2)
