"""Phase-0 noise-floor measurement sweep (sweep-rules.md carve-out).

Real-data ambiguity (soak F4): the anchor GLM is deterministic and the split is
fixed, so "vary only the seed" has no single meaning. This sweep measures the
FIT-SEED spread of the study's stochastic config (HGBT baseline, k=5
random_states); the dev-fold SAMPLING error is measured separately as a
bootstrap SE of the GLM baseline's mean deviance (printed below, recorded in
program.md); minimum_delta takes the LARGER suggestion. Promotes no winner.

Run from the study directory:  uv run --no-sync python sweeps/noise_floor.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from pipeline import MIN_PRED, fit_and_deviance, frequency, load_split, make_model
from sklearn.metrics import mean_poisson_deviance

from kleinlib.sweep import SweepRunner


def hgbt_seed_cell(params: dict) -> dict:
    result = fit_and_deviance("hgbt_ohe", seed=int(params["seed"]))
    return {"primary_metric": result["val_poisson_deviance"], "status": "ok"}


def glm_bootstrap_se(n_boot: int = 200, seed: int = 0) -> float:
    """Dev-fold sampling error of the GLM baseline's exposure-weighted mean
    deviance: bootstrap over dev rows, model FIXED (fit once on train)."""
    (X_tr, y_tr, w_tr), (X_ev, y_ev, w_ev) = load_split("development")
    est, _ = make_model("glm_ohe")
    est.fit(X_tr, frequency(y_tr, w_tr), glm__sample_weight=w_tr.to_numpy())
    pred = np.clip(est.predict(X_ev), MIN_PRED, None)
    y_freq, w = frequency(y_ev, w_ev), w_ev.to_numpy()
    rng = np.random.default_rng(seed)
    n = len(y_freq)
    stats = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        stats.append(mean_poisson_deviance(y_freq[idx], pred[idx], sample_weight=w[idx]))
    return float(np.std(stats, ddof=1))


if __name__ == "__main__":
    runner = SweepRunner(
        "noise_floor",
        Path(__file__).resolve().parents[1],
        hgbt_seed_cell,
        [{"seed": s} for s in range(5)],
        metric_goal="lower",
    )
    runner.run()
    print(f"measurement sweep complete -> {runner.sidecar_path}")
    se = glm_bootstrap_se()
    print(f"dev-fold bootstrap SE of mean deviance (GLM baseline, model fixed): {se:.6f}")
    print(f"sampling-error floor suggestion: 2 x SE = {2 * se:.6f}")
