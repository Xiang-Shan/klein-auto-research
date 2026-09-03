"""Phase 0 metrology: the three floors this study is allowed to quote.

Three recipes, three estimands, one script. They answer different questions and only
one of them may ever become the keep bar:

* ``fit_noise`` (recipe ``seed-sweep``, estimand ``fit-noise``, k = 5) refits the
  ANCHOR rung on the SAME contract partition under five different fit seeds. It says
  how much the FIT moves. It is provenance, never the bar — and for a convex solver on
  fixed rows it is usually near zero, which is precisely why pasting it into
  ``minimum_delta`` would put the keep bar at zero and keep everything.
* ``split_lottery`` (recipe ``split-lottery``, estimand ``marginal-resplit``, k = 10)
  re-draws the train/development partition INSIDE the train+development pool only, at
  the contract's own development proportion, and re-measures the anchor. It says how
  much one candidate's OWN score moves when the draw changes. This study reports it
  because it is the right yardstick for reading an anchor RESIDUAL (how far a ported
  rung may land from the v1 value for no reason but the rows) — it is never a rule.
* ``paired_bootstrap`` (recipe ``paired-bootstrap``, estimand ``paired-comparison``,
  k = 20) resamples the development rows and scores BOTH rungs of a declared pair on
  the same resample. It says how much a DIFFERENCE moves, which is what every keep on
  this track actually is. **This one is the bar.**

Two choices are recorded here because they were made BEFORE the measurement, and
`program.md` carries them as dated decisions:

1. **The pair is (`glm_ohe_balanced`, `hgbt_balanced`)** — the raw-GLM anchor and the
   boosted tree. They are the two most dissimilar scorers in the ladder, so their
   paired difference has the widest sampling spread of any pair the study compares:
   the bar it yields is conservative for every other comparison, and a conservative
   bar can never manufacture a keep. Both are v1 rungs. Neither is an isotonic rung,
   so the calibration lever this study asks about (RQ4) is not touched at Phase 0.
2. **k = 20 replicates for the contract block, with a 1000-replicate run beside it.**
   The schema-3 bar is ``max(2*std, range/2)``. ``range`` is an order statistic: it
   grows with the number of replicates, so at B = 1000 the rule returns ≈3.2 sigma and
   inflates the bar by ~60 % for a reason that is an artefact of counting, not a
   property of the measurement. At k = 20 the expected range is ≈3.7 sigma, so
   ``2*std`` binds and the bar is the conventional two-standard-error bar. The
   1000-replicate run is executed anyway, into its own sidecar, so the k = 20 spread
   can be checked against a precise estimate of the same quantity; if any registered
   verdict would flip between the two bars, findings must say so.

Neither recipe touches ``results.tsv``: a measurement sweep promotes no winner
(`references/sweep-rules.md`) and is made citable with `klein sweep register`.

The rungs come from `lib/rungs.py`, the study's STABLE library module — the same file
`train.py` imports. Re-typing them here would let the floor describe a model the ledger
never ran; importing them from the mutable surface would let a per-experiment edit
silently change what the floor was measured on. A stable library has neither failure.

Usage::

    uv run --locked python sweeps/noise_floor.py fit_noise
    uv run --locked python sweeps/noise_floor.py split_lottery
    uv run --locked python sweeps/noise_floor.py paired_bootstrap
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

STUDY_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY_DIR))

from kleinlib.contract import load_contract  # noqa: E402
from kleinlib.data import contract_split, load_prepared  # noqa: E402

from lib.rungs import fit_rung, positive_probabilities  # noqa: E402

FIT_SEEDS = (11, 22, 33, 44, 55)
SPLIT_SEEDS = (101, 202, 303, 404, 505, 606, 707, 808, 909, 1010)
BOOTSTRAP_SEED = 20260903
PAIR = ("glm_ohe_balanced", "hgbt_balanced")

_CACHE: dict[str, tuple[np.ndarray, np.ndarray]] = {}


def _development_rows():
    X_train, X_dev, _, y_train, y_dev, _ = contract_split(STUDY_DIR)
    return X_train, X_dev, y_train, y_dev


def _fit_noise_trial(params: dict) -> dict:
    """Same rows, a different fit seed — how much does the FIT move?"""
    t0 = time.time()
    X_train, X_dev, y_train, y_dev = _development_rows()
    model, _, X_dev_t = fit_rung(
        PAIR[0], X_train, X_dev, y_train, fit_seed=int(params["seed"])
    )
    proba = positive_probabilities(model, X_dev_t)
    return {
        "primary_metric": float(roc_auc_score(y_dev, proba)),
        "status": "ok",
        "wall_seconds": time.time() - t0,
    }


def _split_lottery_trial(params: dict) -> dict:
    """A different train/development draw — how much does the MEASUREMENT move?

    The sealed partition is never touched: the lottery re-draws only inside the
    train+development pool the contract already carved out, at the contract's own
    development proportion.
    """
    t0 = time.time()
    contract = load_contract(STUDY_DIR)
    target = str(contract["target"])
    split = contract["data"]["split"]
    frame = load_prepared(STUDY_DIR / contract["data"]["prepared_path"])

    X_train, X_dev, y_train, y_dev = _development_rows()
    pool_rows = list(X_train.index) + list(X_dev.index)
    pool = frame.loc[pool_rows]
    y_pool = pool[target]
    X_pool = pool.drop(columns=[target])
    development_share = len(X_dev) / len(pool_rows)

    X_tr, X_ev, y_tr, y_ev = train_test_split(
        X_pool,
        y_pool,
        test_size=development_share,
        random_state=int(params["seed"]),
        stratify=y_pool if split["kind"] == "stratified" else None,
    )
    model, _, X_ev_t = fit_rung(PAIR[0], X_tr, X_ev, y_tr)
    proba = positive_probabilities(model, X_ev_t)
    return {
        "primary_metric": float(roc_auc_score(y_ev, proba)),
        "status": "ok",
        "wall_seconds": time.time() - t0,
    }


def _paired_predictions() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit both rungs of the declared pair ONCE on the train rows; cache their
    development-row probabilities. The bootstrap resamples ROWS, not fits."""
    if "pair" not in _CACHE:
        X_train, X_dev, y_train, y_dev = _development_rows()
        probabilities = []
        for rung in PAIR:
            model, _, X_dev_t = fit_rung(rung, X_train, X_dev, y_train)
            probabilities.append(positive_probabilities(model, X_dev_t))
        _CACHE["pair"] = (np.asarray(y_dev, dtype=int), probabilities[0], probabilities[1])
    return _CACHE["pair"]


def _paired_bootstrap_trial(params: dict) -> dict:
    """ONE index draw applied to BOTH rungs — common random numbers by construction."""
    t0 = time.time()
    y, p_a, p_b = _paired_predictions()
    rng = np.random.default_rng(BOOTSTRAP_SEED + int(params["replicate"]))
    n = y.shape[0]
    idx = rng.integers(0, n, size=n)
    y_resampled = y[idx]
    if y_resampled.min() == y_resampled.max():  # a degenerate resample is data, not a pass
        return {"primary_metric": float("nan"), "status": "crash",
                "error": "resample has one class", "wall_seconds": time.time() - t0}
    delta = float(
        roc_auc_score(y_resampled, p_b[idx]) - roc_auc_score(y_resampled, p_a[idx])
    )
    return {"primary_metric": delta, "status": "ok", "wall_seconds": time.time() - t0}


RECIPES = {
    "fit_noise": (_fit_noise_trial, [{"seed": s} for s in FIT_SEEDS]),
    "split_lottery": (_split_lottery_trial, [{"seed": s} for s in SPLIT_SEEDS]),
    "paired_bootstrap": (_paired_bootstrap_trial, [{"replicate": i} for i in range(20)]),
    "paired_bootstrap_b1000": (
        _paired_bootstrap_trial,
        [{"replicate": i} for i in range(1000)],
    ),
}


def main() -> int:
    from kleinlib.sweep import SweepRunner

    which = sys.argv[1] if len(sys.argv) > 1 else "fit_noise"
    trial, params = RECIPES[which]
    summary = SweepRunner(
        which,
        STUDY_DIR,
        trial,
        params,
        metric_goal="higher",
        overwrite=True,
    ).run()
    values = [t.primary_metric for t in summary.trials if t.status == "ok"]
    print(f"{which}: k={len(values)} ok trials")
    if values:
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        print(f"  mean={mean:.6f}  std={std:.6f}  "
              f"range={max(values) - min(values):.6f}  "
              f"max(2*std, range/2)={max(2 * std, (max(values) - min(values)) / 2):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
