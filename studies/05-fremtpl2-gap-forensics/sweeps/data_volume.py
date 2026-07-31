"""RQ6 measurement sweep (sweep-rules carve-out): gap vs training-set size.

Refits BOTH anchor configs on nested random subsamples of the TRAIN fold
(fixed seed, claim-stratified) and scores each on the UNCHANGED dev fold; the
recorded value per cell is the GLM-minus-HGBT deviance GAP at that fraction.
Promotes no winner; sidecar only. The dev fold and the sealed test are never
subsampled or touched.

Run from the study directory:  uv run --no-sync python sweeps/data_volume.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.metrics import mean_poisson_deviance

from kleinlib.sweep import SweepRunner
from pipeline import CATEGORICAL, NUMERIC, frequency, load_split, make_model

FRACTIONS = [0.05, 0.10, 0.15, 0.25, 0.50, 0.75, 1.00]


def _subsample(X, y, w, frac: float, seed: int = 0):
    if frac >= 1.0:
        return X, y, w
    rng = np.random.default_rng(seed)
    has_claim = (y.to_numpy() > 0)
    idx = np.arange(len(y))
    keep = []
    for mask in (has_claim, ~has_claim):
        pool = idx[mask]
        keep.append(rng.choice(pool, max(1, int(round(len(pool) * frac))), replace=False))
    sel = np.sort(np.concatenate(keep))
    return X.iloc[sel], y.iloc[sel], w.iloc[sel]


def gap_cell(params: dict) -> dict:
    frac = float(params["fraction"])
    (X_tr, y_tr, w_tr), (X_ev, y_ev, w_ev) = load_split("development")
    X_s, y_s, w_s = _subsample(X_tr, y_tr, w_tr, frac)
    devs = {}
    for name in ("glm_ohe", "hgbt_ohe"):
        est, shaped, inter = make_model(name)
        est.fit(X_s, frequency(y_s, w_s), **{est.steps[-1][0] + "__sample_weight": w_s.to_numpy()})
        pred = np.clip(est.predict(X_ev), 1e-6, None)
        devs[name] = float(
            mean_poisson_deviance(frequency(y_ev, w_ev), pred, sample_weight=w_ev)
        )
    return {
        "primary_metric": devs["glm_ohe"] - devs["hgbt_ohe"],
        "status": "ok",
        "glm_dev": devs["glm_ohe"],
        "hgbt_dev": devs["hgbt_ohe"],
        "train_rows": int(len(X_s)),
    }


if __name__ == "__main__":
    runner = SweepRunner(
        "data_volume",
        Path(__file__).resolve().parents[1],
        gap_cell,
        [{"fraction": f} for f in FRACTIONS],
        metric_goal="higher",  # the GAP; direction label only — measurement, no winner
    )
    runner.run()
    print(f"measurement sweep complete -> {runner.sidecar_path}")
