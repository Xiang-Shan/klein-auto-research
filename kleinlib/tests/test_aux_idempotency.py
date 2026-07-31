"""Re-running an experiment must refresh, not duplicate, its aux block."""

import csv
import time

import numpy as np
import pandas as pd
import pytest

from kleinlib import schema
from kleinlib.eval import _append_aux_rows, evaluate_regression, evaluate_scalar


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_rerun_replaces_own_block_and_keeps_others(tmp_path):
    _append_aux_rows(tmp_path, 1, {"val_brier": 0.24, "wall_seconds": 10})
    _append_aux_rows(tmp_path, 2, {"val_brier": 0.06})
    # exp 1 re-run with a corrected value
    _append_aux_rows(tmp_path, 1, {"val_brier": 0.20, "wall_seconds": 12})

    lines = _lines(tmp_path / schema.AUX_SIDECAR)
    assert lines[0] == "\t".join(schema.AUX_COLUMNS)
    exp1 = [line for line in lines[1:] if line.startswith("1\t")]
    exp2 = [line for line in lines[1:] if line.startswith("2\t")]
    assert len(exp1) == 2  # one line per metric, no duplicates
    assert "1\tval_brier\t0.2" in exp1
    assert exp2 == ["2\tval_brier\t0.06"]  # untouched by exp 1's re-run
    assert len(lines) == 1 + 2 + 1


def test_exp_id_prefix_does_not_clobber_longer_ids(tmp_path):
    _append_aux_rows(tmp_path, 1, {"m": 1})
    _append_aux_rows(tmp_path, 11, {"m": 2})
    _append_aux_rows(tmp_path, 1, {"m": 3})  # must not delete exp 11's rows

    lines = _lines(tmp_path / schema.AUX_SIDECAR)
    assert "11\tm\t2" in lines
    assert "1\tm\t3" in lines
    assert "1\tm\t1" not in lines


def test_aux_values_with_tabs_and_newlines_round_trip_safely(tmp_path):
    value = "first\tfield\nsecond line"
    _append_aux_rows(tmp_path, 1, {"note": value})
    path = tmp_path / schema.AUX_SIDECAR
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream, delimiter="\t"))
    assert rows[0] == list(schema.AUX_COLUMNS)
    assert rows[1] == ["1", "note", value]


def test_invalid_existing_aux_file_is_not_overwritten(tmp_path):
    path = tmp_path / schema.AUX_SIDECAR
    path.write_text("bad\theader\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid aux metrics header"):
        _append_aux_rows(tmp_path, 1, {"m": 1})
    assert path.read_text(encoding="utf-8") == "bad\theader\n"


class _StubModel:
    def __init__(self, predictions):
        self.predictions = np.asarray(predictions, dtype=float)

    def predict(self, X):
        return self.predictions[: len(X)]


def test_smoke_mode_skips_every_sidecar_and_snapshot_write(tmp_path, monkeypatch, capsys):
    """Soak F2: an off-loop train.py execution under KLEIN_SMOKE=1 must leave
    the evidence ledger byte-untouched — canonical block still prints."""
    monkeypatch.setenv("KLEIN_SMOKE", "1")
    y = pd.Series([1.0, 2.0, 3.0, 4.0])
    X = pd.DataFrame({"x": range(4)})
    value = evaluate_regression(
        _StubModel([1.1, 2.1, 2.9, 4.2]), X, y,
        exp_id="SMOKE", t0=time.time(), fit_seconds=0.1, train_n=4, val_n=4,
        study_dir=tmp_path,
    )
    assert value > 0
    evaluate_scalar(
        0.5, exp_id="SMOKE", metric_name="gap", metric_goal="lower",
        study_dir=tmp_path,
    )
    out = capsys.readouterr().out
    assert "primary_metric:" in out
    assert out.count("smoke mode: no sidecar/snapshot writes (KLEIN_SMOKE=1)") == 2
    assert not (tmp_path / schema.AUX_SIDECAR).exists()
    assert not (tmp_path / "models").exists()


def test_smoke_mode_off_still_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("KLEIN_SMOKE", "")  # run-one's force-clear value
    y = pd.Series([1.0, 2.0, 3.0, 4.0])
    X = pd.DataFrame({"x": range(4)})
    evaluate_regression(
        _StubModel([1.1, 2.1, 2.9, 4.2]), X, y,
        exp_id="E0001", t0=time.time(), fit_seconds=0.1, train_n=4, val_n=4,
        study_dir=tmp_path,
    )
    assert (tmp_path / schema.AUX_SIDECAR).exists()
