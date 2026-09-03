"""Phase 0 metrology: the two floors this study is allowed to quote.

Two recipes, two estimands, one script. They answer different questions and only
one of them may ever become a keep bar:

* ``fit_noise`` (recipe ``seed-sweep``, k = 5) refits the SAME anchor recipe on
  the SAME contract partition under five different fit seeds. It says how much
  the FIT moves. It is provenance, never the bar — and for a convex solver on
  fixed rows it is usually near zero, which is precisely why pasting it in as
  ``minimum_delta`` would put the keep bar at zero and keep everything.
* ``split_lottery`` (recipe ``split-lottery``, estimand ``marginal-resplit``,
  k = 10) re-draws the train/development partition at the contract's own
  proportions and re-measures. It says how much the MEASUREMENT moves, which is
  what a keep must clear.

Neither touches ``results.tsv``: a measurement sweep promotes no winner
(`references/sweep-rules.md`) and is made citable with `klein sweep register`.

The recipe under both floors is the study's ANCHOR rung (`logreg_raw` in
`train.py`), rebuilt here rather than imported, so that editing the mutable
surface can never silently change what the floor was measured on.
"""

from __future__ import annotations

import sys
import time

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from kleinlib.contract import load_contract
from kleinlib.data import contract_split, load_prepared

FIT_SEEDS = (11, 22, 33, 44, 55)
SPLIT_SEEDS = (101, 202, 303, 404, 505, 606, 707, 808, 909, 1010)
ANCHOR_MAX_ITER = 1000


def _anchor(random_state: int):
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=ANCHOR_MAX_ITER, random_state=random_state),
    )


def _fit_noise_trial(params: dict) -> dict:
    """Same rows, a different fit seed — how much does the FIT move?"""
    t0 = time.time()
    X_train, X_dev, _, y_train, y_dev, _ = contract_split(".")
    model = _anchor(int(params["seed"]))
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_dev)[:, 1]
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
    contract = load_contract(".")
    target = str(contract["target"])
    split = contract["data"]["split"]
    frame = load_prepared(contract["data"]["prepared_path"])

    X_train, X_dev, _, y_train, y_dev, _ = contract_split(".")
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
    model = _anchor(42)
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_ev)[:, 1]
    return {
        "primary_metric": float(roc_auc_score(y_ev, proba)),
        "status": "ok",
        "wall_seconds": time.time() - t0,
    }


RECIPES = {
    "fit_noise": (_fit_noise_trial, FIT_SEEDS),
    "split_lottery": (_split_lottery_trial, SPLIT_SEEDS),
}


def main() -> int:
    from kleinlib.sweep import SweepRunner

    which = sys.argv[1] if len(sys.argv) > 1 else "fit_noise"
    trial, seeds = RECIPES[which]
    summary = SweepRunner(
        which,
        ".",
        trial,
        [{"seed": seed} for seed in seeds],
        metric_goal="higher",
        overwrite=True,
    ).run()
    values = [t.primary_metric for t in summary.trials if t.status == "ok"]
    print(f"{which}: k={len(values)} ok trials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
