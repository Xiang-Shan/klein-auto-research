"""Deviance metric family: golden values, domain guards, weight threading.

The reference formulation is study 04's pipeline (the exposure-weighted-rate
convention): the target is rate = counts / exposure, ``sample_weight`` is the
exposure, and the score is ``mean_*_deviance(rate, pred, sample_weight)``.
These tests are fully synthetic — no $DATA_HUB, no committed study touched.
"""

from __future__ import annotations

import math
import time

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import (
    mean_absolute_error,
    mean_gamma_deviance,
    mean_poisson_deviance,
    mean_squared_error,
    mean_tweedie_deviance,
)

from kleinlib import eval as klein_eval


class _StubModel:
    def __init__(self, predictions):
        self.predictions = np.asarray(predictions, dtype=float)

    def predict(self, X):
        return self.predictions[: len(X)]


def _kwargs(n):
    return dict(exp_id="E0001", t0=time.time(), fit_seconds=0.1, train_n=n, val_n=n)


@pytest.fixture
def freq():
    """Counts with zeros, uneven exposure, strictly positive predictions."""
    rng = np.random.default_rng(42)
    n = 200
    counts = rng.integers(0, 4, size=n).astype(float)
    exposure = rng.uniform(0.05, 2.0, size=n)
    rate = counts / exposure
    pred = np.clip(rng.gamma(2.0, 0.75, size=n), 1e-6, None)
    assert (counts == 0).any(), "fixture must exercise zero counts"
    return pd.DataFrame({"x": np.arange(n)}), counts, exposure, rate, pred


def test_registry_carries_the_deviance_family():
    for name in sorted(klein_eval.DEVIANCE_METRICS):
        spec = klein_eval.get_metric_spec(name, task="regression")
        assert spec.goal == "lower"
    with pytest.raises(ValueError, match="canonical goal"):
        klein_eval.get_metric_spec("val_poisson_deviance", goal="higher")


def test_poisson_deviance_matches_the_study04_formulation(freq):
    X, counts, exposure, rate, pred = freq
    result = klein_eval.evaluate_regression(
        _StubModel(pred),
        X,
        pd.Series(rate),
        metric_name="val_poisson_deviance",
        metric_goal="lower",
        sample_weight=exposure,
        **_kwargs(len(rate)),
    )
    expected = mean_poisson_deviance(counts / exposure, pred, sample_weight=exposure)
    assert result == pytest.approx(expected, rel=1e-12)


def test_constant_predictor_reproduces_the_hand_null_deviance(freq):
    X, counts, exposure, rate, _ = freq
    lam = counts.sum() / exposure.sum()
    result = klein_eval.evaluate_regression(
        _StubModel(np.full_like(rate, lam)),
        X,
        pd.Series(rate),
        metric_name="val_poisson_deviance",
        metric_goal="lower",
        sample_weight=exposure,
        **_kwargs(len(rate)),
    )
    # Hand-rolled weighted null deviance with the y*ln(y/mu) -> 0 convention
    # at y == 0 (the anchor quantity study 04's pipeline computes).
    with np.errstate(divide="ignore", invalid="ignore"):
        log_term = np.where(rate > 0, rate * np.log(rate / lam), 0.0)
    dev = 2.0 * (log_term - (rate - lam))
    expected = float(np.sum(exposure * dev) / exposure.sum())
    assert result == pytest.approx(expected, rel=1e-12)


def test_gamma_and_tweedie_match_sklearn(freq, capsys):
    X, counts, exposure, _, pred = freq
    severity = counts + 1.0  # strictly positive target for Gamma
    result = klein_eval.evaluate_regression(
        _StubModel(pred),
        X,
        pd.Series(severity),
        metric_name="val_gamma_deviance",
        metric_goal="lower",
        sample_weight=exposure,
        **_kwargs(len(severity)),
    )
    assert result == pytest.approx(
        mean_gamma_deviance(severity, pred, sample_weight=exposure), rel=1e-12
    )
    rate = counts / exposure
    result = klein_eval.evaluate_regression(
        _StubModel(pred),
        X,
        pd.Series(rate),
        metric_name="val_tweedie_deviance",
        metric_goal="lower",
        sample_weight=exposure,
        tweedie_power=1.5,
        **_kwargs(len(rate)),
    )
    assert result == pytest.approx(
        mean_tweedie_deviance(rate, pred, sample_weight=exposure, power=1.5), rel=1e-12
    )
    out = capsys.readouterr().out
    assert "tweedie_power: 1.5" in out


def test_domain_guards_refuse_with_actionable_messages(freq):
    X, counts, exposure, rate, pred = freq
    series = pd.Series(rate)
    base = dict(metric_goal="lower", sample_weight=exposure, **_kwargs(len(rate)))
    with pytest.raises(ValueError, match="clip in train.py"):
        klein_eval.evaluate_regression(
            _StubModel(np.zeros_like(pred)), X, series,
            metric_name="val_poisson_deviance", **base,
        )
    with pytest.raises(ValueError, match="non-negative targets"):
        klein_eval.evaluate_regression(
            _StubModel(pred), X, pd.Series(rate - rate.max() - 1.0),
            metric_name="val_poisson_deviance", **base,
        )
    with pytest.raises(ValueError, match="strictly positive targets"):
        klein_eval.evaluate_regression(
            _StubModel(pred), X, series,  # fixture has zero counts
            metric_name="val_gamma_deviance", **base,
        )
    with pytest.raises(ValueError, match="requires tweedie_power"):
        klein_eval.evaluate_regression(
            _StubModel(pred), X, series,
            metric_name="val_tweedie_deviance", **base,
        )
    with pytest.raises(ValueError, match="1 < power < 2"):
        klein_eval.evaluate_regression(
            _StubModel(pred), X, series,
            metric_name="val_tweedie_deviance", tweedie_power=2.5, **base,
        )
    with pytest.raises(ValueError, match="applies only to val_tweedie_deviance"):
        klein_eval.evaluate_regression(
            _StubModel(pred), X, series,
            metric_name="val_rmse", tweedie_power=1.5, **base,
        )


def test_sample_weight_validation(freq):
    X, _, exposure, rate, pred = freq
    series = pd.Series(rate)
    for bad, message in (
        (exposure[:-1], "length"),
        (np.where(np.arange(len(exposure)) == 0, np.nan, exposure), "finite"),
        (np.where(np.arange(len(exposure)) == 0, 0.0, exposure), "strictly positive"),
    ):
        with pytest.raises(ValueError, match=message):
            klein_eval.evaluate_regression(
                _StubModel(pred), X, series,
                metric_name="val_poisson_deviance", metric_goal="lower",
                sample_weight=bad, **_kwargs(len(rate)),
            )


def test_weights_thread_into_the_classic_regression_metrics(freq):
    X, _, exposure, rate, pred = freq
    result = klein_eval.evaluate_regression(
        _StubModel(pred),
        X,
        pd.Series(rate),
        metric_name="val_rmse",
        metric_goal="lower",
        sample_weight=exposure,
        **_kwargs(len(rate)),
    )
    assert result == pytest.approx(
        math.sqrt(mean_squared_error(rate, pred, sample_weight=exposure)), rel=1e-12
    )


def test_unweighted_output_is_byte_stable(freq, capsys):
    """No weights, classic primary: the printed block must be exactly the
    pre-deviance shape — no new lines, old formulas bit-for-bit."""
    X, _, _, rate, pred = freq
    result = klein_eval.evaluate_regression(
        _StubModel(pred),
        X,
        pd.Series(rate),
        metric_name="val_rmse",
        metric_goal="lower",
        **_kwargs(len(rate)),
    )
    assert result == pytest.approx(math.sqrt(mean_squared_error(rate, pred)), rel=1e-15)
    out = capsys.readouterr().out
    aux = out.split("--- aux_metrics ---\n", 1)[1]
    assert aux == (
        f"val_rmse:          {math.sqrt(mean_squared_error(rate, pred)):.6f}\n"
        f"val_mae:           {mean_absolute_error(rate, pred):.6f}\n"
        f"val_r2:            {aux.splitlines()[2].split()[-1]}\n"
    )
    assert "calibration_ratio" not in out
    assert "deviance" not in aux


def test_deviance_primary_lands_in_sidecar_with_calibration(freq, tmp_path, capsys):
    X, counts, exposure, rate, pred = freq
    klein_eval.evaluate_regression(
        _StubModel(pred),
        X,
        pd.Series(rate),
        metric_name="val_poisson_deviance",
        metric_goal="lower",
        sample_weight=exposure,
        study_dir=tmp_path,
        **_kwargs(len(rate)),
    )
    out = capsys.readouterr().out
    expected_ratio = float(np.sum(exposure * pred) / counts.sum())
    assert f"calibration_ratio: {expected_ratio:.6f}" in out
    sidecar = (tmp_path / "aux_metrics.tsv").read_text(encoding="utf-8")
    assert "val_poisson_deviance" in sidecar
    assert "calibration_ratio" in sidecar
