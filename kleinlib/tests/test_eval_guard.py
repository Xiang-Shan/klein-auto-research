"""Tests for kleinlib.eval.evaluate: the min_proba_std collapse guard and
the aux_metrics.tsv sidecar it writes when given a study_dir.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from kleinlib import eval as klein_eval
from kleinlib import schema


class _ConstantProbaModel:
    """Simulates the MPS DataLoader+TensorDataset collapse war story."""

    def predict_proba(self, X):
        n = len(X)
        return np.tile([0.7, 0.3], (n, 1))


class _HealthyModel:
    """Predicted probability correlated with a synthetic feature, plus noise."""

    def predict_proba(self, X):
        rng = np.random.default_rng(0)
        base = np.asarray(X["x0"], dtype=float)
        base = (base - base.min()) / (base.max() - base.min() + 1e-9)
        noise = rng.normal(scale=0.05, size=len(base))
        p1 = np.clip(base + noise, 0.01, 0.99)
        return np.column_stack([1 - p1, p1])


def _toy_xy(n=200, seed=0):
    rng = np.random.default_rng(seed)
    x0 = rng.normal(size=n)
    y = (x0 + rng.normal(scale=0.3, size=n) > 0).astype(int)
    return pd.DataFrame({"x0": x0}), pd.Series(y)


def test_evaluate_raises_on_collapsed_predictions():
    X, y = _toy_xy()
    with pytest.raises(RuntimeError, match="Collapsed predictions"):
        klein_eval.evaluate(
            _ConstantProbaModel(),
            X,
            y,
            exp_id=1,
            t0=time.time(),
            fit_seconds=0.1,
            train_n=160,
            val_n=40,
        )


def test_evaluate_healthy_model_returns_float_and_writes_sidecar(tmp_path, capsys):
    X, y = _toy_xy()
    t0 = time.time()
    result = klein_eval.evaluate(
        _HealthyModel(),
        X,
        y,
        exp_id=7,
        t0=t0,
        fit_seconds=1.23,
        train_n=160,
        val_n=40,
        study_dir=tmp_path,
    )
    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0

    captured = capsys.readouterr().out
    assert "primary_metric:    " in captured
    assert "--- aux_metrics ---" in captured

    sidecar = tmp_path / schema.AUX_SIDECAR
    assert sidecar.exists()
    lines = sidecar.read_text().strip().splitlines()
    assert lines[0] == "\t".join(schema.AUX_COLUMNS)
    body = lines[1:]
    assert any("wall_seconds" in line for line in body)
    assert any("min_proba_std" in line for line in body)
    assert all(line.startswith("7\t") for line in body)


def test_evaluate_does_not_write_sidecar_without_study_dir(capsys):
    X, y = _toy_xy()
    klein_eval.evaluate(
        _HealthyModel(),
        X,
        y,
        exp_id=9,
        t0=time.time(),
        fit_seconds=0.5,
        train_n=160,
        val_n=40,
    )
    # No exception, no file — just confirming study_dir=None is a no-op for
    # the sidecar (console block still printed).
    assert "primary_metric:    " in capsys.readouterr().out
