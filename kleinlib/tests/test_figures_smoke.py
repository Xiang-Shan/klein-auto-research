"""Smoke tests for kleinlib.figures: reports produce the expected PNG files."""

from __future__ import annotations

import numpy as np

from kleinlib import figures

BINARY_NAMES = {
    "roc",
    "pr",
    "reliability",
    "score_hist_by_class",
    "decile_lift",
    "confusion_at_threshold",
}

REGRESSION_NAMES = {
    "pred_vs_actual",
    "residuals",
    "qq",
    "lorenz",
    "lift_quantile",
    "calibration_by_decile",
}


def test_standard_binary_report_smoke(tmp_path):
    rng = np.random.default_rng(0)
    n = 300
    y_true = rng.integers(0, 2, size=n)
    proba = np.clip(y_true * 0.5 + rng.normal(scale=0.2, size=n) + 0.25, 0.01, 0.99)

    paths = figures.standard_binary_report(y_true, proba, tmp_path)

    assert set(paths) == BINARY_NAMES
    for name, path in paths.items():
        assert path.exists(), f"{name} figure missing"
        assert path.stat().st_size > 0
        assert path.parent == tmp_path / "figures"


def test_standard_regression_report_smoke(tmp_path):
    rng = np.random.default_rng(1)
    n = 300
    y_true = rng.normal(loc=1000, scale=200, size=n)
    y_pred = y_true + rng.normal(scale=100, size=n)

    paths = figures.standard_regression_report(y_true, y_pred, tmp_path)

    assert set(paths) == REGRESSION_NAMES
    for name, path in paths.items():
        assert path.exists(), f"{name} figure missing"
        assert path.stat().st_size > 0


def test_plot_metric_trajectory_smoke(tmp_path):
    rows = [
        {"experiment": "1", "primary_metric": "0.60", "status": "keep", "commit": "abc1234", "description": "baseline"},
        {"experiment": "2", "primary_metric": "0.55", "status": "discard", "commit": "-", "description": "worse"},
        {"experiment": "3", "primary_metric": "NA", "status": "crash", "commit": "-", "description": "oom"},
        {"experiment": "4", "primary_metric": "0.65", "status": "keep", "commit": "def5678", "description": "better"},
    ]
    path = figures.plot_metric_trajectory(rows, tmp_path)
    assert path.exists()
    assert path.stat().st_size > 0
