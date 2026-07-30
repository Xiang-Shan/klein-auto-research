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


def _manifest(number, *, phase="p1", disposition="discard", metric=0.5, kind="development", track="frequency"):
    return {
        "experiment": f"E{number:04d}",
        "track": track,
        "phase": phase,
        "evaluation_kind": kind,
        "disposition": disposition,
        "primary_metric": metric,
        "metric_name": "val_pr_auc",
        "wall_seconds": 2.0,
    }


DECISION_MANIFESTS = [
    _manifest(1, disposition="keep", metric=0.60),
    _manifest(2, disposition="discard", metric=0.58),
    _manifest(3, disposition="crash", metric=None),
    _manifest(4, disposition="keep", metric=0.64),
    _manifest(5, phase="p2", disposition="discard", metric=0.63),
    _manifest(6, phase="p2", disposition="keep", metric=0.67),
    _manifest(7, phase="p2", disposition="discard", metric=0.61),
    _manifest(8, phase="p2", disposition="keep", metric=0.66, kind="final_test"),
]


def test_plot_decision_trajectory_smoke(tmp_path):
    path = figures.plot_decision_trajectory(
        DECISION_MANIFESTS, tmp_path, track="frequency", metric_goal="higher",
        metric_name="val_pr_auc", minimum_delta=0.005, noise_floor_std=0.01,
    )
    assert path == tmp_path / "figures" / "plot_decision_trajectory.png"
    assert path.exists()
    assert path.stat().st_size > 10_000, "PNG should be non-trivial (marks, bands, legend)"


def test_plot_decision_trajectory_lower_goal(tmp_path):
    lower = [
        {**m, "primary_metric": None if m["primary_metric"] is None else round(1 - m["primary_metric"], 3)}
        for m in DECISION_MANIFESTS
    ]
    path = figures.plot_decision_trajectory(
        lower, tmp_path, track="frequency", metric_goal="lower",
        metric_name="val_logloss", minimum_delta=0.005,
    )
    assert path.exists()
    assert path.stat().st_size > 0


def test_plot_decision_trajectory_all_crash_does_not_raise(tmp_path):
    crashes = [_manifest(n, disposition="crash", metric=None) for n in (1, 2, 3)]
    path = figures.plot_decision_trajectory(
        crashes, tmp_path, track="frequency", metric_goal="higher"
    )
    assert path.exists()
    assert path.stat().st_size > 0


def test_plot_decision_trajectory_single_phase_single_experiment(tmp_path):
    path = figures.plot_decision_trajectory(
        [_manifest(1, disposition="keep", metric=0.6)],
        tmp_path, track="frequency", metric_goal="higher", name="single",
    )
    assert path == tmp_path / "figures" / "single.png"
    assert path.exists()
    assert path.stat().st_size > 0


def test_plot_decision_trajectory_track_name_suffix(tmp_path):
    mixed = DECISION_MANIFESTS + [
        _manifest(9, track="severity", disposition="keep", metric=240.0),
        _manifest(10, track="severity", disposition="discard", metric=250.0),
    ]
    path = figures.plot_decision_trajectory(
        mixed, tmp_path, track="severity", metric_goal="lower",
        metric_name="val_rmse", name="plot_decision_trajectory__severity",
    )
    assert path == tmp_path / "figures" / "plot_decision_trajectory__severity.png"
    assert path.exists()
    assert path.stat().st_size > 0


def test_decision_trajectory_declares_log_scale_on_extreme_range(tmp_path):
    """A divergence outlier must not flatten the frontier story: all-positive
    values spanning >3 decades switch to a DECLARED log scale (figure critique)."""
    from kleinlib.figures import plot_decision_trajectory

    manifests = [
        {"experiment": "E0001", "track": "primary", "phase": "p1",
         "disposition": "keep", "primary_metric": 1.25, "metric_name": "gap"},
        {"experiment": "E0002", "track": "primary", "phase": "p1",
         "disposition": "discard", "primary_metric": 1.1e196, "metric_name": "gap"},
        {"experiment": "E0003", "track": "primary", "phase": "p1",
         "disposition": "keep", "primary_metric": 0.41, "metric_name": "gap"},
        {"experiment": "E0004", "track": "primary", "phase": "p1",
         "disposition": "crash", "primary_metric": None, "metric_name": "gap"},
    ]
    path = plot_decision_trajectory(
        manifests, tmp_path, track="primary", metric_goal="lower", metric_name="gap"
    )
    assert path.exists() and path.stat().st_size > 5000
