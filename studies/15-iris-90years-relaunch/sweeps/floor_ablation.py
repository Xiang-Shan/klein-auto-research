"""Phase-0 sweep: floor_ablation -- the PAIRED floor for the `ablation` track.

`study.yaml` declares this floor's pair (`lda_all4`, `lda_sepal` -- "this
track's most dissimilar pair") and replicate count (1000) BEFORE any
measurement. Same recipe as `sweeps/floor_modern.py`, restated here rather
than parameterized across the two scripts: each Phase-0 floor is its own
committed, independently-registered artifact (`sweep-rules.md`), and the
pair is a study.yaml-level declaration, not a CLI flag a later edit could
quietly change.

Usage::

    uv run --locked python sweeps/floor_ablation.py
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
CANDIDATE_RECIPE = "lda_sepal"


def main() -> None:
    X_fit, X_eval, y_fit, y_eval = load_partition(
        "development", study_dir=STUDY_DIR, echo=False
    )
    _, p_reference, _ = fit_and_score(REFERENCE_RECIPE, X_fit, y_fit, X_eval)
    _, p_candidate, _ = fit_and_score(CANDIDATE_RECIPE, X_fit, y_fit, X_eval)
    y = y_eval.to_numpy()
    n = len(y)

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
        "floor_ablation", STUDY_DIR, trial_fn, params_list, metric_goal="higher", overwrite=True
    )
    summary = runner.run()
    n_ok = sum(1 for t in summary.trials if t.status == "ok")
    print(
        f"floor_ablation: pair=({REFERENCE_RECIPE}, {CANDIDATE_RECIPE}) "
        f"{n_ok}/{len(summary.trials)} ok trials"
    )


if __name__ == "__main__":
    main()
