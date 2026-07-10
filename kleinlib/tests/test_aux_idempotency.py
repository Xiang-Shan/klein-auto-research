"""Re-running an experiment must refresh, not duplicate, its aux block."""

from kleinlib import schema
from kleinlib.eval import _append_aux_rows


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_rerun_replaces_own_block_and_keeps_others(tmp_path):
    _append_aux_rows(tmp_path, 1, {"val_brier": 0.24, "wall_seconds": 10})
    _append_aux_rows(tmp_path, 2, {"val_brier": 0.06})
    # exp 1 re-run with a corrected value
    _append_aux_rows(tmp_path, 1, {"val_brier": 0.20, "wall_seconds": 12})

    lines = _lines(tmp_path / schema.AUX_SIDECAR)
    assert lines[0] == "\t".join(schema.AUX_COLUMNS)
    exp1 = [l for l in lines[1:] if l.startswith("1\t")]
    exp2 = [l for l in lines[1:] if l.startswith("2\t")]
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
