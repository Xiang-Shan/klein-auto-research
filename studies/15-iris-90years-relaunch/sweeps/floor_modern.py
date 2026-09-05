"""Phase-0 sweep: floor_modern -- the PAIRED floor for the `modern` track.

`study.yaml` declares this floor's pair (`lda_all4`, `hgbt` -- "the parade's
most dissimilar pair, which makes the bar conservative for every other
comparison") and replicate count (1000) BEFORE any measurement, so neither
can be chosen after seeing an answer. Fits both recipes ONCE on the 49
training rows, scores both on the 25 development rows, then draws 1000
bootstrap resamples of those SAME rows under ONE shared index draw per
replicate -- common random numbers by construction -- recomputing
`delta = AUC(hgbt) - AUC(lda_all4)` each time.

`kleinlib.metrology.paired_bootstrap`'s generic `statistic=` callback only
ever sees the two ALREADY-RESAMPLED probability series, never the resampled
LABELS -- fine for a row-mean statistic, wrong for AUC, which needs the
labels resampled in lockstep too (`method_card.md` section 3.3, "the paired-
bootstrap gotcha for an AUC difference"). This script spells out that exact
recipe as a `kleinlib.sweep.SweepRunner` trial function, one resample per
trial, so every replicate -- including a vanishingly rare (~5e-8) degenerate
single-class resample -- lands in the sidecar as data (a `crash` row, never
silently retried away).

Usage::

    uv run --locked python sweeps/floor_modern.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

STUDY_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY_DIR))

from kleinlib.data import load_partition  # noqa: E402
from kleinlib.sweep import SweepRunner  # noqa: E402
from lib.iris import BOOTSTRAP_SEED, fit_and_score  # noqa: E402

N_BOOT = 1000
REFERENCE_RECIPE = "lda_all4"
CANDIDATE_RECIPE = "hgbt"


def main() -> None:
    X_fit, X_eval, y_fit, y_eval = load_partition(
        "development", study_dir=STUDY_DIR, echo=False
    )
    _, p_reference, _ = fit_and_score(REFERENCE_RECIPE, X_fit, y_fit, X_eval)
    _, p_candidate, _ = fit_and_score(CANDIDATE_RECIPE, X_fit, y_fit, X_eval)
    y = y_eval.to_numpy()
    n = len(y)

    # ONE rng, advanced sequentially across trials -- SweepRunner calls
    # trial_fn strictly in params_list order, so this reproduces exactly the
    # same 1000 resamples every run (BOOTSTRAP_SEED, never a split seed).
    rng = np.random.default_rng(BOOTSTRAP_SEED)

    def trial_fn(params: dict) -> dict:
        idx = rng.integers(0, n, size=n)
        y_r = y[idx]
        if y_r.min() == y_r.max():
            return {"status": "crash", "primary_metric": None}
        delta = float(
            roc_auc_score(y_r, p_candidate[idx]) - roc_auc_score(y_r, p_reference[idx])
        )
        return {"primary_metric": delta, "status": "ok"}

    params_list = [{"boot_idx": i} for i in range(1, N_BOOT + 1)]
    runner = SweepRunner(
        "floor_modern", STUDY_DIR, trial_fn, params_list, metric_goal="higher", overwrite=True
    )
    summary = runner.run()
    n_ok = sum(1 for t in summary.trials if t.status == "ok")
    print(
        f"floor_modern: pair=({REFERENCE_RECIPE}, {CANDIDATE_RECIPE}) "
        f"{n_ok}/{len(summary.trials)} ok trials"
    )


if __name__ == "__main__":
    main()
