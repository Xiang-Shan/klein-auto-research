"""Phase-0 measurement sweep: glm-track fit-seed floor (sweep-rules carve-out).

PoissonRegressor is a deterministic solver — the seed parameter is accepted and
ignored by the cell, so the expected spread is EXACTLY zero. Running the k=5
sweep anyway records that determinism as evidence (a degenerate fit-seed floor
is WHY the glm track's minimum_delta must come from the paired bootstrap
instead — see sweeps/paired_floor.py and program.md).

Run from the study directory:  uv run --no-sync python sweeps/noise_floor_glm.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from sklearn.metrics import mean_poisson_deviance

from kleinlib.sweep import SweepRunner
from pipeline import fit_model


def glm_seed_cell(params: dict) -> dict:
    _ = int(params["seed"])  # accepted, deliberately unused: the solver is deterministic
    model, X_ev, y_rate, w, _, _ = fit_model("glm_ohe")
    dev = float(mean_poisson_deviance(y_rate, model.predict(X_ev), sample_weight=w))
    return {"primary_metric": dev, "status": "ok"}


if __name__ == "__main__":
    runner = SweepRunner(
        "noise_floor_glm",
        Path(__file__).resolve().parents[1],
        glm_seed_cell,
        [{"seed": s} for s in range(5)],
        metric_goal="lower",
    )
    runner.run()
    print(f"measurement sweep complete -> {runner.sidecar_path}")
