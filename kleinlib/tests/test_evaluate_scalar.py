"""Tests for kleinlib.eval.evaluate_scalar: the no-model/no-proba evaluator
used by Monte-Carlo / simulation studies (e.g. Klein study 02's QLS lab).
"""

from __future__ import annotations

import time

from kleinlib import eval as klein_eval
from kleinlib import schema


def test_evaluate_scalar_canonical_block_format(capsys):
    result = klein_eval.evaluate_scalar(
        0.123456789,
        exp_id=3,
        metric_name="premium_error_pct",
        metric_goal="lower",
    )
    assert result == 0.123456789

    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == "---"
    # Exact campaign format: "primary_metric:" + 4 spaces + %.6f value.
    assert lines[1] == "primary_metric:    0.123457"
    assert "metric_name:       premium_error_pct" in out
    assert "metric_goal:       lower" in out
    assert "training_seconds:  NA" in out
    assert "train_rows:        NA" in out
    assert "val_rows:          NA" in out
    assert "--- aux_metrics ---" in out


def test_evaluate_scalar_writes_sidecar(tmp_path):
    t0 = time.time()
    klein_eval.evaluate_scalar(
        1.5,
        exp_id=4,
        metric_name="val_rmse",
        metric_goal="lower",
        study_dir=tmp_path,
        t0=t0,
        extra={"note": "toy"},
    )
    sidecar = tmp_path / schema.AUX_SIDECAR
    assert sidecar.exists()
    lines = sidecar.read_text().strip().splitlines()
    assert lines[0] == "\t".join(schema.AUX_COLUMNS)
    body = "\n".join(lines[1:])
    assert "wall_seconds" in body
    assert "note" in body
    assert all(line.startswith("4\t") for line in lines[1:])


def test_evaluate_scalar_without_t0_reports_zero_total_seconds(capsys):
    klein_eval.evaluate_scalar(
        2.0, exp_id=5, metric_name="m", metric_goal="higher"
    )
    out = capsys.readouterr().out
    assert "total_seconds:     0.0" in out
