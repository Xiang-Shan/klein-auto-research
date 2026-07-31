"""Phase-0 measurement sweep: gbdt-track fit-seed floor (sweep-rules carve-out).

k=5 random_states of the HGBT anchor config — the stochastic component of the
gbdt track. Promotes no winner; sidecar only. The glm track's fit-seed twin is
sweeps/noise_floor_glm.py; the paired-difference floors (which set minimum_delta,
study-04 precedent) are sweeps/paired_floor.py.

Run from the study directory:  uv run --no-sync python sweeps/noise_floor_gbdt.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from sklearn.metrics import mean_poisson_deviance

from kleinlib.sweep import SweepRunner
from pipeline import fit_model


def hgbt_seed_cell(params: dict) -> dict:
    model, X_ev, y_rate, w, _, _ = fit_model("hgbt_ohe", seed=int(params["seed"]))
    dev = float(mean_poisson_deviance(y_rate, model.predict(X_ev), sample_weight=w))
    return {"primary_metric": dev, "status": "ok"}


if __name__ == "__main__":
    runner = SweepRunner(
        "noise_floor_gbdt",
        Path(__file__).resolve().parents[1],
        hgbt_seed_cell,
        [{"seed": s} for s in range(5)],
        metric_goal="lower",
    )
    runner.run()
    print(f"measurement sweep complete -> {runner.sidecar_path}")
