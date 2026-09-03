"""Post-loop metrology: what each of the ladder's OWN comparisons costs to resolve.

Registered in `program.md` BEFORE the loop ran, and run after it closed. The contract
carries ONE keep bar, measured at Phase 0 on the ladder's most dissimilar pair
(`glm_ohe_balanced` vs `hgbt_balanced`) — a conservative choice that can suppress a
real effect but can never manufacture one. The ladder, though, makes three comparisons
of very different similarity, and a paired floor is a property of the PAIR:

* `pair_anchor_splines`   — E0002's comparison: the spline+isotonic chain against the
  raw GLM anchor. Two linear models sharing a design matrix; their scores should be
  strongly correlated, so this floor should be the smallest of the three.
* `pair_splines_hgbt`     — E0003's comparison: a boosted tree against the calibrated
  GLM. Different model classes.
* `pair_anchor_doctrine`  — E0004's comparison: one lever (class weighting plus an
  isotonic wrapper) on an otherwise identical rung. The most similar pair in the study.

**These numbers cannot and do not change a registered verdict.** The bar was declared
at Phase 0 with its pair and its replicate count on the record, every verdict was
adjudicated by the notary against it, and nothing here re-opens any of that. They exist
so a reader of findings §③ can see how much of a "within noise" verdict is the
instrument and how much is the effect — which is RQ3's question.

Same machinery as `noise_floor.py`: one index draw per replicate applied to both rungs
(common random numbers), 1000 replicates, rungs imported from `lib/rungs.py`.

Usage::

    uv run --locked python sweeps/pair_floors.py pair_anchor_splines
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

STUDY_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY_DIR))

from kleinlib.data import contract_split  # noqa: E402

from lib.rungs import fit_rung, positive_probabilities  # noqa: E402

BOOTSTRAP_SEED = 20260903
N_REPLICATES = 1000

PAIRS = {
    "pair_anchor_splines": ("glm_ohe_balanced", "glm_splines_isotonic"),
    "pair_splines_hgbt": ("glm_splines_isotonic", "hgbt_balanced"),
    "pair_anchor_doctrine": ("glm_ohe_balanced", "glm_ohe_none_isotonic"),
}

_CACHE: dict[str, tuple] = {}


def _predictions(pair: tuple[str, str]):
    key = "|".join(pair)
    if key not in _CACHE:
        X_train, X_dev, _, y_train, y_dev, _ = contract_split(STUDY_DIR)
        probabilities = []
        for rung in pair:
            model, _, X_dev_t = fit_rung(rung, X_train, X_dev, y_train)
            probabilities.append(positive_probabilities(model, X_dev_t))
        _CACHE[key] = (np.asarray(y_dev, dtype=int), probabilities[0], probabilities[1])
    return _CACHE[key]


def _trial(pair: tuple[str, str]):
    def run(params: dict) -> dict:
        t0 = time.time()
        y, p_a, p_b = _predictions(pair)
        rng = np.random.default_rng(BOOTSTRAP_SEED + int(params["replicate"]))
        idx = rng.integers(0, y.shape[0], size=y.shape[0])
        y_resampled = y[idx]
        if y_resampled.min() == y_resampled.max():
            return {"primary_metric": float("nan"), "status": "crash",
                    "error": "resample has one class", "wall_seconds": time.time() - t0}
        delta = float(
            roc_auc_score(y_resampled, p_b[idx]) - roc_auc_score(y_resampled, p_a[idx])
        )
        return {"primary_metric": delta, "status": "ok", "wall_seconds": time.time() - t0}

    return run


def main() -> int:
    from kleinlib.sweep import SweepRunner

    which = sys.argv[1]
    pair = PAIRS[which]
    summary = SweepRunner(
        which,
        STUDY_DIR,
        _trial(pair),
        [{"replicate": i} for i in range(N_REPLICATES)],
        metric_goal="higher",
        overwrite=True,
    ).run()
    values = [t.primary_metric for t in summary.trials if t.status == "ok"]
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1))
    value_range = max(values) - min(values)
    print(f"{which}: {pair[0]} -> {pair[1]}  k={len(values)}")
    print(f"  mean={mean:.6f}  std={std:.6f}  range={value_range:.6f}  "
          f"max(2*std, range/2)={max(2 * std, value_range / 2):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
