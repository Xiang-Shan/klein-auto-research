"""Generate the known-truth table declared by `study.yaml:data.source`.

This study exists to show the headroom law against a ceiling nobody has to
guess. That is only possible when the truth is DECLARED rather than observed,
so the evidence here is simulated by the process written out below — and the
same process yields, in closed form, the best score any model could ever reach
on these rows.

The generating process
----------------------
Eight independent standard-normal features. Six of them enter the true
log-odds; ``x7`` and ``x8`` enter nothing at all and exist so the study can
watch a model spend capacity on noise. The log-odds are linear in the six
informative features PLUS one two-way interaction and one quadratic term::

    eta = b0 + sum_j b_j x_j + b_12 x1 x2 + b_33 x3^2
    p   = sigmoid(eta)
    y   ~ Bernoulli(p)

The interaction and the quadratic are what a linear-in-raw-features model
cannot express, which is the whole question the ladder asks.

The ceiling
-----------
Because ``eta`` is known per row, the Bayes-optimal RANKING of these rows is
known too: it is ``eta`` itself. So

* **Bayes AUC** = ``roc_auc_score(y, sigmoid(eta))`` — no model can rank better
  on these rows, because nothing beats the true probability;
* **Bayes Brier** = ``brier_score_loss(y, sigmoid(eta))`` — the irreducible
  loss left by the coin flips.

Both are computed here, per contract partition, and written to
``data/prepared/truth.json`` together with the per-row true log-odds. The
development partition's Bayes AUC is what ``study.yaml`` declares as
``tracks.primary.metric.bound.ideal`` after the DATA gate has hashed this file.

Determinism and the split
-------------------------
The generator seed is READ FROM THE CONTRACT (``data.split.seed``) and appears
nowhere as a literal here — war story 8: a partition rule or a seed baked into
a script is how a whole ledger lane ends up measuring the wrong rows. The
partitions themselves come from :func:`kleinlib.data.contract_split`, so the
per-partition ceilings below are the ceilings of exactly the rows the runs are
graded on.

The stored log-odds are rounded to ``ETA_DECIMALS`` BEFORE anything is derived
from them, so the ceiling this file reports and the ceiling ``train.py`` later
recomputes from the same file are the same number, not two roundings of it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from kleinlib import sources
from kleinlib.contract import load_contract
from kleinlib.data import contract_split

# --- the declared data-generating process ---------------------------------
N_ROWS = 20_000
FEATURES = ("x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8")
NOISE_FEATURES = ("x7", "x8")
TARGET = "y"

#: Linear part of the true log-odds. The two noise features are absent by
#: construction, not by a zero coefficient.
LINEAR_COEFFS = {
    "x1": 0.90,
    "x2": 0.80,
    "x3": 0.70,
    "x4": 0.50,
    "x5": -0.60,
    "x6": 0.40,
}
#: The one two-way interaction: (feature, feature, coefficient).
INTERACTION = ("x1", "x2", 1.00)
#: The one nonlinear term: (feature, coefficient) on the SQUARE of the feature.
QUADRATIC = ("x3", 0.70)
#: Chosen so the positive rate lands in the 20-30% band the study declares.
INTERCEPT = -2.40

#: Decimals the stored log-odds are rounded to. Everything derived from the
#: truth is derived from the ROUNDED values, here and in `train.py`.
ETA_DECIMALS = 8

PREPARED_PATH = Path("data/prepared/prepared.csv")
TRUTH_PATH = Path("data/prepared/truth.json")


def true_log_odds(frame: pd.DataFrame) -> np.ndarray:
    """The DGP's log-odds for each row of `frame`, rounded as stored."""
    eta = np.full(len(frame), float(INTERCEPT))
    for name, coefficient in LINEAR_COEFFS.items():
        eta = eta + coefficient * frame[name].to_numpy()
    left, right, weight = INTERACTION
    eta = eta + weight * frame[left].to_numpy() * frame[right].to_numpy()
    base, weight = QUADRATIC
    eta = eta + weight * np.square(frame[base].to_numpy())
    return np.round(eta, ETA_DECIMALS)


def simulate(seed: int, n_rows: int = N_ROWS) -> tuple[pd.DataFrame, np.ndarray]:
    """`(frame, eta)` — the prepared table and its per-row true log-odds."""
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(
        rng.standard_normal((n_rows, len(FEATURES))).round(6), columns=list(FEATURES)
    )
    eta = true_log_odds(frame)
    probability = 1.0 / (1.0 + np.exp(-eta))
    frame[TARGET] = (rng.random(n_rows) < probability).astype(int)
    return frame, eta


def _ceiling(eta: np.ndarray, y: np.ndarray) -> dict[str, float | int]:
    """Bayes AUC and Bayes Brier for one partition, from the true log-odds."""
    probability = 1.0 / (1.0 + np.exp(-eta))
    return {
        "n": int(len(y)),
        "positive_rate": round(float(np.mean(y)), 6),
        "bayes_auc": round(float(roc_auc_score(y, probability)), 6),
        "bayes_brier": round(float(brier_score_loss(y, probability)), 6),
    }


def main() -> None:
    sources.resolve("synthetic:prepare.py", study_dir=Path("."), offline=True)
    contract = load_contract(".")
    seed = int(contract["data"]["split"]["seed"])

    frame, eta = simulate(seed)
    PREPARED_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(PREPARED_PATH, index=False, lineterminator="\n")

    # The partitions come from the contract, so the per-partition ceilings are
    # the ceilings of exactly the rows the runs are graded on.
    X_train, X_dev, X_test, y_train, y_dev, y_test = contract_split(".")
    partitions = {
        "full": _ceiling(eta, frame[TARGET].to_numpy()),
        "train": _ceiling(eta[X_train.index.to_numpy()], y_train.to_numpy()),
        "development": _ceiling(eta[X_dev.index.to_numpy()], y_dev.to_numpy()),
        "final_test": _ceiling(eta[X_test.index.to_numpy()], y_test.to_numpy()),
    }
    truth = {
        "dgp": {
            "n_rows": N_ROWS,
            "seed_source": "study.yaml:data.split.seed",
            "seed": seed,
            "features": list(FEATURES),
            "noise_features": list(NOISE_FEATURES),
            "intercept": INTERCEPT,
            "linear_coeffs": LINEAR_COEFFS,
            "interaction": {"left": INTERACTION[0], "right": INTERACTION[1], "coeff": INTERACTION[2]},
            "quadratic": {"feature": QUADRATIC[0], "coeff": QUADRATIC[1]},
            "eta_decimals": ETA_DECIMALS,
        },
        "partitions": partitions,
        "true_log_odds": [float(value) for value in eta],
    }
    TRUTH_PATH.write_text(json.dumps(truth, indent=1) + "\n", encoding="utf-8")

    print(f"rows: {len(frame)}  positives: {int(frame[TARGET].sum())}")
    for name, stats in partitions.items():
        print(
            f"{name}: n={stats['n']} positive_rate={stats['positive_rate']} "
            f"bayes_auc={stats['bayes_auc']} bayes_brier={stats['bayes_brier']}"
        )
    print(f"prepared: {PREPARED_PATH.as_posix()}")
    print(f"truth: {TRUTH_PATH.as_posix()}")


if __name__ == "__main__":
    main()
