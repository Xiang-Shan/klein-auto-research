"""Metric identity, direction, finiteness, and inner-CV dispatch."""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import f1_score, log_loss, mean_absolute_error

from kleinlib import eval as klein_eval


class _ProbabilityModel:
    def __init__(self, probabilities):
        self.probabilities = np.asarray(probabilities, dtype=float)

    def predict_proba(self, X):
        p = self.probabilities[: len(X)]
        return np.column_stack([1.0 - p, p])


class _ReversedClassModel(_ProbabilityModel):
    classes_ = np.array([1, 0])

    def predict_proba(self, X):
        p = self.probabilities[: len(X)]
        return np.column_stack([p, 1.0 - p])


class _RegressionModel:
    def __init__(self, predictions):
        self.predictions = np.asarray(predictions, dtype=float)

    def predict(self, X):
        return self.predictions[: len(X)]


def _eval_kwargs(n):
    return dict(exp_id=1, t0=time.time(), fit_seconds=0.1, train_n=n, val_n=n)


def test_known_metric_direction_cannot_disagree():
    X = pd.DataFrame({"x": range(6)})
    y = pd.Series([0, 0, 0, 1, 1, 1])
    with pytest.raises(ValueError, match="canonical goal"):
        klein_eval.evaluate(
            _ProbabilityModel(np.linspace(0.1, 0.9, 6)),
            X,
            y,
            metric_name="val_logloss",
            metric_goal="higher",
            **_eval_kwargs(len(y)),
        )


def test_classification_metric_name_selects_its_actual_calculation():
    X = pd.DataFrame({"x": range(6)})
    y = pd.Series([0, 0, 0, 1, 1, 1])
    p = np.linspace(0.1, 0.9, 6)
    result = klein_eval.evaluate(
        _ProbabilityModel(p),
        X,
        y,
        metric_name="val_logloss",
        metric_goal="lower",
        **_eval_kwargs(len(y)),
    )
    assert result == pytest.approx(log_loss(y, p, labels=[0, 1]))


def test_positive_probability_uses_model_class_order():
    X = pd.DataFrame({"x": range(6)})
    y = pd.Series([0, 0, 0, 1, 1, 1])
    p = np.linspace(0.1, 0.9, 6)
    normal = klein_eval.evaluate(
        _ProbabilityModel(p), X, y, **_eval_kwargs(len(y))
    )
    reversed_order = klein_eval.evaluate(
        _ReversedClassModel(p), X, y, **_eval_kwargs(len(y))
    )
    assert normal == pytest.approx(reversed_order)


def test_binary_evaluator_rejects_non_zero_one_targets():
    X = pd.DataFrame({"x": range(4)})
    y = pd.Series(["no", "no", "yes", "yes"])
    with pytest.raises(ValueError, match=r"labels exactly \{0, 1\}"):
        klein_eval.evaluate(
            _ProbabilityModel([0.1, 0.2, 0.8, 0.9]),
            X,
            y,
            **_eval_kwargs(len(y)),
        )


def test_regression_metric_name_selects_its_actual_calculation():
    X = pd.DataFrame({"x": range(4)})
    y = pd.Series([1.0, 2.0, 4.0, 8.0])
    pred = np.array([0.0, 2.0, 5.0, 6.0])
    result = klein_eval.evaluate_regression(
        _RegressionModel(pred),
        X,
        y,
        metric_name="val_mae",
        metric_goal="lower",
        **_eval_kwargs(len(y)),
    )
    assert result == pytest.approx(mean_absolute_error(y, pred))


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_scalar_rejects_non_finite_primary_metric(value):
    with pytest.raises(ValueError, match="finite"):
        klein_eval.evaluate_scalar(
            value,
            exp_id=1,
            metric_name="custom_error",
            metric_goal="lower",
        )


def test_classification_rejects_non_finite_probabilities():
    X = pd.DataFrame({"x": range(4)})
    y = pd.Series([0, 0, 1, 1])
    with pytest.raises(ValueError, match="non-finite"):
        klein_eval.evaluate(
            _ProbabilityModel([0.1, np.nan, 0.8, 0.9]),
            X,
            y,
            **_eval_kwargs(len(y)),
        )


def test_narrow_but_nonconstant_probabilities_are_not_collapsed():
    X = pd.DataFrame({"x": range(20)})
    y = pd.Series([0, 1] * 10)
    p = 0.5 + np.linspace(-1e-5, 1e-5, len(y))
    result = klein_eval.evaluate(
        _ProbabilityModel(p), X, y, **_eval_kwargs(len(y))
    )
    assert np.isfinite(result)


def test_vectorized_threshold_search_matches_reference_loop():
    rng = np.random.default_rng(20260711)
    y = rng.integers(0, 2, size=1_003)
    probabilities = rng.random(len(y))
    values, threshold = klein_eval._classification_metric_values(y, probabilities)
    thresholds = np.linspace(0.01, 0.99, 99)
    reference = np.asarray(
        [
            f1_score(y, probabilities > candidate, zero_division=0)
            for candidate in thresholds
        ]
    )
    best = int(np.argmax(reference))
    assert values["val_f1_at_best"] == pytest.approx(reference[best])
    assert threshold == pytest.approx(thresholds[best])


class _InnerCvModel:
    def fit(self, X, y):
        return self

    def predict_proba(self, X):
        p = 0.1 + 0.8 * (np.asarray(X["x"]) / 59.0)
        return np.column_stack([1.0 - p, p])


def test_inner_cv_metric_argument_is_honoured():
    X = pd.DataFrame({"x": np.arange(60, dtype=float)})
    y = pd.Series(([0, 1, 0] * 20)[:60])
    auc, _ = klein_eval.evaluate_with_inner_cv(
        _InnerCvModel, X, y, metric="val_auc"
    )
    logloss, _ = klein_eval.evaluate_with_inner_cv(
        _InnerCvModel, X, y, metric="val_logloss"
    )
    assert auc != pytest.approx(logloss)
