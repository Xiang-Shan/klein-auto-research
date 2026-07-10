"""Tests for kleinlib.sweep: SweepRunner, the boxed-sweep escape-hatch."""

from __future__ import annotations

import json

import pytest

from kleinlib import schema
from kleinlib.sweep import SIDECAR_COLUMNS, SweepRunner


def _read_rows(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "\t".join(SIDECAR_COLUMNS)
    return [dict(zip(SIDECAR_COLUMNS, line.split("\t"))) for line in lines[1:]]


def _ok(metric):
    return {"primary_metric": metric, "status": "ok"}


def test_all_trials_in_sidecar_in_order(tmp_path):
    params_list = [{"x": 1}, {"x": 2}, {"x": 3}]
    calls = []

    def trial_fn(params):
        calls.append(params["x"])
        return _ok(params["x"] * 0.1)

    runner = SweepRunner("axis", tmp_path, trial_fn, params_list, metric_goal="higher")
    summary = runner.run()

    assert calls == [1, 2, 3]  # sequential, params_list order
    rows = _read_rows(runner.sidecar_path)
    assert [r["trial"] for r in rows] == ["1", "2", "3"]
    assert [json.loads(r["params_json"])["x"] for r in rows] == [1, 2, 3]
    assert [r["status"] for r in rows] == ["ok", "ok", "ok"]
    assert [float(r["primary_metric"]) for r in rows] == [
        pytest.approx(0.1), pytest.approx(0.2), pytest.approx(0.3)
    ]
    assert " " not in rows[0]["params_json"]  # compact JSON, no spaces
    assert [t.trial for t in summary.trials] == [1, 2, 3]


def test_crash_trial_recorded_and_skipped_for_winner(tmp_path):
    params_list = [{"x": 1}, {"x": 2}, {"x": 3}]

    def trial_fn(params):
        if params["x"] == 2:
            raise RuntimeError("boom")
        return _ok(params["x"] * 1.0)

    runner = SweepRunner("crashy", tmp_path, trial_fn, params_list, metric_goal="higher")
    summary = runner.run()

    rows = _read_rows(runner.sidecar_path)
    assert len(rows) == 3  # the crash is still recorded, not silent
    assert rows[1]["status"] == "crash"
    assert rows[1]["primary_metric"] == schema.NA_METRIC

    assert summary.winner is not None
    assert summary.winner.trial == 3  # the crashed trial 2 is skipped
    assert summary.winner.primary_metric == pytest.approx(3.0)


def test_crash_via_explicit_status_also_skipped(tmp_path):
    """A trial can self-report status='crash' without raising; same handling."""
    params_list = [{"x": 1}, {"x": 2}]

    def trial_fn(params):
        if params["x"] == 1:
            return {"primary_metric": None, "status": "crash"}
        return _ok(5.0)

    runner = SweepRunner("explicit-crash", tmp_path, trial_fn, params_list)
    summary = runner.run()

    rows = _read_rows(runner.sidecar_path)
    assert rows[0]["status"] == "crash"
    assert rows[0]["primary_metric"] == schema.NA_METRIC
    assert summary.winner.trial == 2


def test_status_defaults_to_ok_when_omitted(tmp_path):
    runner = SweepRunner("noStatus", tmp_path, lambda p: {"primary_metric": 1.0}, [{}])
    summary = runner.run()
    assert summary.trials[0].status == "ok"


def test_winner_correct_for_higher_goal(tmp_path):
    params_list = [{"x": 1}, {"x": 5}, {"x": 3}]
    runner = SweepRunner(
        "higher", tmp_path, lambda p: _ok(p["x"]), params_list, metric_goal="higher"
    )
    summary = runner.run()
    assert summary.winner.trial == 2
    assert summary.winner.primary_metric == pytest.approx(5.0)


def test_winner_correct_for_lower_goal(tmp_path):
    params_list = [{"x": 1}, {"x": 5}, {"x": 3}]
    runner = SweepRunner(
        "lower", tmp_path, lambda p: _ok(p["x"]), params_list, metric_goal="lower"
    )
    summary = runner.run()
    assert summary.winner.trial == 1
    assert summary.winner.primary_metric == pytest.approx(1.0)


def test_invalid_metric_goal_rejected(tmp_path):
    with pytest.raises(ValueError):
        SweepRunner("bad", tmp_path, lambda p: _ok(1.0), [{}], metric_goal="sideways")


def test_improved_over_higher_and_lower(tmp_path):
    params_list = [{"x": 1}, {"x": 5}, {"x": 3}]

    higher_summary = SweepRunner(
        "h", tmp_path, lambda p: _ok(p["x"]), params_list, metric_goal="higher"
    ).run()
    assert higher_summary.improved_over(4.0) is True  # winner 5 > 4
    assert higher_summary.improved_over(5.0) is False  # not strictly greater
    assert higher_summary.improved_over(6.0) is False

    lower_summary = SweepRunner(
        "l", tmp_path, lambda p: _ok(p["x"]), params_list, metric_goal="lower"
    ).run()
    assert lower_summary.improved_over(2.0) is True  # winner 1 < 2
    assert lower_summary.improved_over(1.0) is False
    assert lower_summary.improved_over(0.5) is False


def test_improved_over_false_when_all_crash(tmp_path):
    def always_crash(params):
        raise ValueError("nope")

    summary = SweepRunner("allcrash", tmp_path, always_crash, [{"x": 1}, {"x": 2}]).run()
    assert summary.winner is None
    assert summary.improved_over(0.0) is False
    assert summary.improved_over(-999.0) is False


def test_sidecar_append_as_you_go_kill_mid_run(tmp_path):
    """KeyboardInterrupt on trial 3 of 4 must not erase trials 1-2 already on disk."""
    params_list = [{"x": 1}, {"x": 2}, {"x": 3}, {"x": 4}]
    seen = []

    def trial_fn(params):
        seen.append(params["x"])
        if params["x"] == 3:
            raise KeyboardInterrupt()
        return _ok(params["x"] * 1.0)

    runner = SweepRunner("killed", tmp_path, trial_fn, params_list, metric_goal="higher")
    with pytest.raises(KeyboardInterrupt):
        runner.run()

    assert seen == [1, 2, 3]  # trial 4 never dispatched
    rows = _read_rows(runner.sidecar_path)
    assert [r["trial"] for r in rows] == ["1", "2"]  # trial 3's row never written
    assert [r["status"] for r in rows] == ["ok", "ok"]


def test_rerun_starts_sidecar_fresh(tmp_path):
    """A second `.run()` replaces the sidecar rather than appending to the old one."""
    runner = SweepRunner("rerun", tmp_path, lambda p: _ok(p["x"]), [{"x": 1}, {"x": 2}])
    runner.run()
    assert len(_read_rows(runner.sidecar_path)) == 2

    runner2 = SweepRunner("rerun", tmp_path, lambda p: _ok(p["x"]), [{"x": 9}])
    runner2.run()
    rows = _read_rows(runner2.sidecar_path)
    assert len(rows) == 1
    assert json.loads(rows[0]["params_json"]) == {"x": 9}
