"""Phase-0 measurement: paired-difference bootstrap floors (sweep-rules carve-out).

Study 04's central metrology finding — three defensible floors differ 25×, and
the PAIRED-difference bootstrap is the one that matches a two-model comparison —
transplanted to the two-track design. Common random numbers by construction:
per-row unit-deviance differences are computed first, then rows are resampled
once per replicate, so both models see identical bootstrap draws.

Three floors, one per comparison the study adjudicates:
  glm pair   : glm_ohe            vs glm_scoped_splines   -> glm-track minimum_delta
  gbdt pair  : hgbt_ohe           vs lgbm_poisson         -> gbdt-track minimum_delta
  cross pair : glm_ohe            vs hgbt_ohe             -> headline-gap uncertainty band
                                                            (NOT a minimum_delta)

Each SE is reported with B=1000 replicates in 5 blocks of 200 (block SEs show
the bootstrap's own stability). minimum_delta = 2 x SE_paired per track (the
fit-seed floors from the sibling sweeps are folded in via max(); see program.md).

Run from the study directory:  uv run --no-sync python sweeps/paired_floor.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from pipeline import fit_model

B_BLOCKS, B_PER_BLOCK = 5, 200


def _unit_dev_rows(y: np.ndarray, mu: np.ndarray) -> np.ndarray:
    """Per-row UNIT Poisson deviance (weights applied at aggregation time)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return 2.0 * np.where(y > 0, y * np.log(y / mu) - (y - mu), mu)


def paired_se(dev_a: np.ndarray, dev_b: np.ndarray, w: np.ndarray, seed: int) -> tuple[float, list[float]]:
    """SE of the weighted-mean deviance DIFFERENCE under row bootstrap (CRN)."""
    diff = dev_a - dev_b
    rng = np.random.default_rng(seed)
    n = len(diff)
    reps: list[float] = []
    block_ses: list[float] = []
    for _ in range(B_BLOCKS):
        block: list[float] = []
        for _ in range(B_PER_BLOCK):
            idx = rng.integers(0, n, n)
            block.append(float(np.sum(w[idx] * diff[idx]) / np.sum(w[idx])))
        reps.extend(block)
        block_ses.append(float(np.std(block, ddof=1)))
    return float(np.std(reps, ddof=1)), block_ses


def main() -> None:
    preds: dict[str, np.ndarray] = {}
    shared: dict[str, np.ndarray] = {}
    for name in ["glm_ohe", "glm_scoped_splines", "hgbt_ohe", "lgbm_poisson"]:
        model, X_ev, y_rate, w, fit_s, _ = fit_model(name)
        preds[name] = model.predict(X_ev)
        shared["y"], shared["w"] = np.asarray(y_rate, float), np.asarray(w, float)
        print(f"fitted {name:>20} ({fit_s:.1f}s)")
    y, w = shared["y"], shared["w"]
    dev = {k: _unit_dev_rows(y, v) for k, v in preds.items()}

    pairs = {
        "glm_pair  (glm_ohe vs glm_scoped_splines)": ("glm_ohe", "glm_scoped_splines"),
        "gbdt_pair (hgbt_ohe vs lgbm_poisson)": ("hgbt_ohe", "lgbm_poisson"),
        "cross     (glm_ohe vs hgbt_ohe)": ("glm_ohe", "hgbt_ohe"),
    }
    for label, (a, b) in pairs.items():
        point = float(np.sum(w * (dev[a] - dev[b])) / np.sum(w))
        se, blocks = paired_se(dev[a], dev[b], w, seed=0)
        print(f"{label}: delta={point:+.6f}  paired SE={se:.6f}  "
              f"2xSE={2 * se:.6f}  block SEs={['%.6f' % s for s in blocks]}")


if __name__ == "__main__":
    main()
