"""save_holdout_predictions: the external-eval-table export hook."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kleinlib.eval import save_holdout_predictions


@pytest.fixture
def arrays():
    rng = np.random.default_rng(7)
    n = 50
    return {
        "y_true": rng.integers(0, 3, size=n) / 1.0,
        "y_pred": rng.uniform(0.01, 1.0, size=n),
        "weight": rng.uniform(0.1, 1.0, size=n),
        "pred_b": rng.uniform(0.01, 1.0, size=n),
        "dims": {"DrivAge": rng.integers(18, 90, size=n), "VehGas": ["D", "R"] * 25},
    }


def test_round_trip_columns_and_path(tmp_path, arrays, capsys):
    path = save_holdout_predictions(
        tmp_path,
        "E0003",
        y_true=arrays["y_true"],
        y_pred=arrays["y_pred"],
        weight=arrays["weight"],
        dims=arrays["dims"],
        pred_b=arrays["pred_b"],
    )
    assert path == tmp_path / "predictions" / "E0003_holdout.csv.gz"
    out = capsys.readouterr().out
    assert "predictions: wrote predictions/E0003_holdout.csv.gz (50 rows)" in out
    frame = pd.read_csv(path)
    assert list(frame.columns) == [
        "y_true", "y_pred", "weight", "DrivAge", "VehGas", "y_pred_b",
    ]
    assert len(frame) == 50
    np.testing.assert_allclose(frame["y_pred"], arrays["y_pred"])
    # re-export overwrites (derived data, not evidence)
    save_holdout_predictions(
        tmp_path, "E0003", y_true=arrays["y_true"], y_pred=arrays["y_pred"]
    )
    assert list(pd.read_csv(path).columns) == ["y_true", "y_pred"]


def test_validation_refusals(tmp_path, arrays):
    y, p = arrays["y_true"], arrays["y_pred"]
    with pytest.raises(ValueError, match="does not match"):
        save_holdout_predictions(tmp_path, "E1", y_true=y, y_pred=p[:-1])
    with pytest.raises(ValueError, match="finite"):
        save_holdout_predictions(
            tmp_path, "E1", y_true=y, y_pred=np.where(np.arange(len(p)) == 0, np.nan, p)
        )
    with pytest.raises(ValueError, match="strictly positive"):
        save_holdout_predictions(
            tmp_path, "E1", y_true=y, y_pred=p, weight=np.zeros_like(y)
        )
    with pytest.raises(ValueError, match="rows"):
        save_holdout_predictions(
            tmp_path, "E1", y_true=y, y_pred=p, dims={"DrivAge": [1, 2, 3]}
        )
    with pytest.raises(ValueError, match="collides"):
        save_holdout_predictions(
            tmp_path, "E1", y_true=y, y_pred=p, dims={"y_true": y}
        )
    with pytest.raises(ValueError, match="does not match"):
        save_holdout_predictions(tmp_path, "E1", y_true=y, y_pred=p, pred_b=p[:-1])
