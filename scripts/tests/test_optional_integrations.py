"""Tiny CPU fits proving the optional GBDT distributions are actually usable.

Each fit runs in its OWN fresh subprocess, never in the pytest process. This is
war story 5 enforced by construction: torch and a GBDT library (or two GBDT
libraries) loaded into one process SIGSEGV on macOS arm64 via their bundled
duplicate libomp — below Python, where no guard can fire. Subprocess isolation
makes this module safe inside any collection, including the default
`uv run --locked pytest` in an all-extras environment.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap

import pytest

_FIT_SNIPPETS = {
    "lightgbm": """
        import lightgbm, numpy as np
        rng = np.random.default_rng(42)
        X = rng.normal(size=(80, 4)).astype(np.float32)
        y = (X[:, 0] + 0.2 * X[:, 1] > 0).astype(np.int64)
        model = lightgbm.LGBMClassifier(n_estimators=3, n_jobs=1, verbosity=-1, random_state=42)
        assert model.fit(X, y).predict_proba(X).shape == (len(X), 2)
        print("ok")
    """,
    "xgboost": """
        import xgboost, numpy as np
        rng = np.random.default_rng(42)
        X = rng.normal(size=(80, 4)).astype(np.float32)
        y = (X[:, 0] + 0.2 * X[:, 1] > 0).astype(np.int64)
        model = xgboost.XGBClassifier(n_estimators=3, n_jobs=1, verbosity=0, random_state=42)
        assert model.fit(X, y).predict_proba(X).shape == (len(X), 2)
        print("ok")
    """,
    "catboost": """
        import catboost, numpy as np
        rng = np.random.default_rng(42)
        X = rng.normal(size=(80, 4)).astype(np.float32)
        y = (X[:, 0] + 0.2 * X[:, 1] > 0).astype(np.int64)
        model = catboost.CatBoostClassifier(iterations=3, thread_count=1, verbose=False, random_seed=42)
        assert model.fit(X, y).predict_proba(X).shape == (len(X), 2)
        print("ok")
    """,
}


def _fit_in_subprocess(library: str) -> None:
    if importlib.util.find_spec(library) is None:
        pytest.skip(f"requires the optional gbdt extra ({library} not installed)")
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(_FIT_SNIPPETS[library])],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"{library} smoke fit failed:\n{result.stdout}\n{result.stderr}"
    assert "ok" in result.stdout


def test_lightgbm_cpu_fit() -> None:
    _fit_in_subprocess("lightgbm")


def test_xgboost_cpu_fit() -> None:
    _fit_in_subprocess("xgboost")


def test_catboost_cpu_fit() -> None:
    _fit_in_subprocess("catboost")
