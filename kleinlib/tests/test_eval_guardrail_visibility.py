"""F1 (study 05, E0001): declared guardrail metrics must be PRINTED.

`klein run-one` reads guardrails off the printed metric block, but
`wall_seconds` historically reached only the aux sidecar — so a declared
`wall_seconds` guardrail always scored "missing" and discarded the
candidate. These tests pin the fix: every evaluator prints exactly one
`wall_seconds:` line, caller-supplied values are never duplicated (the
byte-stability guarantee for studies that already pass it via `extra=`),
the printed line parses as a guardrail metric, and the E0001 disposition
flips from discard to keep. Fully synthetic — no committed study touched.
"""

from __future__ import annotations

import re
import time

import numpy as np
import pandas as pd

from kleinlib import eval as klein_eval
from kleinlib import schema
from kleinlib.workflow import choose_disposition, parse_metric_log

WALL_LINE_RE = re.compile(r"^wall_seconds:      \S+$", re.MULTILINE)


class _StubRegressor:
    def __init__(self, predictions):
        self.predictions = np.asarray(predictions, dtype=float)

    def predict(self, X):
        return self.predictions[: len(X)]


class _HealthyClassifier:
    def predict_proba(self, X):
        rng = np.random.default_rng(0)
        base = np.asarray(X["x0"], dtype=float)
        base = (base - base.min()) / (base.max() - base.min() + 1e-9)
        p1 = np.clip(base + rng.normal(scale=0.05, size=len(base)), 0.01, 0.99)
        return np.column_stack([1 - p1, p1])


def _toy_classification(n=200, seed=0):
    rng = np.random.default_rng(seed)
    x0 = rng.normal(size=n)
    y = (x0 + rng.normal(scale=0.3, size=n) > 0).astype(int)
    return pd.DataFrame({"x0": x0}), pd.Series(y)


def _toy_regression(n=100, seed=1):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({"x": np.arange(n)})
    y = pd.Series(rng.uniform(0.1, 2.0, size=n))
    pred = np.clip(y.to_numpy() + rng.normal(scale=0.1, size=n), 1e-6, None)
    return X, y, pred


def _run_all_three(capsys, extra=None):
    """Run each evaluator once and return its captured stdout."""
    outputs = {}
    X, y = _toy_classification()
    klein_eval.evaluate(
        _HealthyClassifier(), X, y,
        exp_id="E0001", t0=time.time(), fit_seconds=0.1,
        train_n=160, val_n=40, extra=dict(extra) if extra else None,
    )
    outputs["evaluate"] = capsys.readouterr().out
    X, y, pred = _toy_regression()
    klein_eval.evaluate_regression(
        _StubRegressor(pred), X, y,
        metric_name="val_rmse", metric_goal="lower",
        exp_id="E0001", t0=time.time(), fit_seconds=0.1,
        train_n=80, val_n=20, extra=dict(extra) if extra else None,
    )
    outputs["evaluate_regression"] = capsys.readouterr().out
    klein_eval.evaluate_scalar(
        0.5, exp_id="E0001", metric_name="premium_error_pct",
        metric_goal="lower", t0=time.time(),
        extra=dict(extra) if extra else None,
    )
    outputs["evaluate_scalar"] = capsys.readouterr().out
    return outputs


def test_all_three_evaluators_print_wall_seconds_once(capsys):
    for name, out in _run_all_three(capsys).items():
        matches = WALL_LINE_RE.findall(out)
        assert len(matches) == 1, f"{name}: expected exactly one wall_seconds line, got {matches}"
        value = matches[0].split()[-1]
        assert re.fullmatch(r"\d+\.\d{6}", value), f"{name}: framework format is .6f, got {value!r}"


def test_caller_supplied_wall_seconds_is_not_duplicated(capsys):
    """Studies 03/05/06 pass wall_seconds via extra= — their stdout must keep
    printing that value exactly once (the byte-stability guarantee)."""
    for name, out in _run_all_three(capsys, extra={"wall_seconds": 42.0}).items():
        lines = [ln for ln in out.splitlines() if ln.startswith("wall_seconds")]
        assert len(lines) == 1, f"{name}: {lines}"
        assert lines[0] == "wall_seconds: 42.0", f"{name}: extra formatting changed: {lines[0]!r}"


def test_printed_wall_seconds_parses_as_a_guardrail_metric(tmp_path, capsys):
    X, y, pred = _toy_regression()
    klein_eval.evaluate_regression(
        _StubRegressor(pred), X, y,
        metric_name="val_rmse", metric_goal="lower",
        exp_id="E0001", t0=time.time(), fit_seconds=0.1, train_n=80, val_n=20,
    )
    log = tmp_path / "run.log"
    log.write_text(capsys.readouterr().out, encoding="utf-8")
    _primary, _name, _goal, metrics = parse_metric_log(log)
    assert "wall_seconds" in metrics
    assert np.isfinite(metrics["wall_seconds"])
    assert "wall_seconds" in schema.AUTO_PRINTED_METRIC_KEYS


def test_wall_seconds_guardrail_now_keeps_what_it_used_to_discard():
    """The E0001 scenario, both halves: the missing-key path keeps its old
    disposition and message prefix, and the same run with the key printed
    is a keep."""
    track_spec = {
        "metric": {"goal": "lower", "minimum_delta": 0.0},
        "guardrails": {"wall_seconds": {"max": 400}},
    }
    disposition, reason = choose_disposition(
        primary_metric=0.454861, track_spec=track_spec,
        metrics={}, incumbent=None, final_test=False,
    )
    assert disposition == "discard"
    assert "guardrail metric 'wall_seconds' missing" in reason
    disposition, reason = choose_disposition(
        primary_metric=0.454861, track_spec=track_spec,
        metrics={"wall_seconds": 1.7}, incumbent=None, final_test=False,
    )
    assert disposition == "keep"
    assert reason == "first valid result on this track"


def test_sidecar_bytes_are_unchanged_by_the_print(tmp_path, capsys):
    """F1 is print-only: exactly one wall_seconds sidecar row, same as before."""
    klein_eval.evaluate_scalar(
        0.5, exp_id="E0009", metric_name="premium_error_pct",
        metric_goal="lower", t0=time.time(), study_dir=tmp_path,
    )
    capsys.readouterr()
    rows = (tmp_path / schema.AUX_SIDECAR).read_text(encoding="utf-8").strip().splitlines()
    assert rows[0] == "\t".join(schema.AUX_COLUMNS)
    wall_rows = [r for r in rows[1:] if "\twall_seconds\t" in r]
    assert len(wall_rows) == 1
    assert len(rows) == 2  # header + the one wall_seconds row, nothing new
