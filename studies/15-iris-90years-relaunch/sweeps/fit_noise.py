"""Phase-0 sweep: fit_noise -- PROVENANCE about the fit, never the keep bar.

`svm_rbf` (Platt calibration, `random_state=`) and `hgbt` (boosting,
`random_state=`) are the only two of the study's five recipes that carry a
seed at all (`method_card.md` section 3.3; `lda_all4`, `logreg_l2` and
`knn5` have none, so their fit_noise is zero by construction). This script
refits each of those two recipes k=5 times on the SAME train/development
rows, varying ONLY the model's own `random_state`, and records each
recipe's own five-value spread to its OWN sidecar
(`sweeps/fit_noise_<recipe>.sidecar.tsv`) via `kleinlib.sweep.SweepRunner`.

Both sub-sweeps are registered separately (`klein sweep register
fit_noise_svm_rbf ...` / `fit_noise_hgbt ...`) so either is citable on its
own; `study.yaml`'s `tracks.modern.metric.fit_noise:` is declared as a
SINGLE mapping (`kleinlib.noise_floor.yaml_block`), so only the more
conservative (larger-spread) of the two is pasted there as the track's
`fit_noise:` block -- the other stays on record as `sweep:fit_noise_<other>`
and is cited in `program.md`.

No partition is redrawn here -- `load_partition("development")` is called
once and the SAME `X_fit`/`y_fit`/`X_eval`/`y_eval` are reused for every
trial of both sub-sweeps (war story 8: no literal split seed anywhere in
this file).

Usage::

    uv run --locked python sweeps/fit_noise.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from sklearn.metrics import roc_auc_score

STUDY_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY_DIR))

from kleinlib.data import load_partition  # noqa: E402
from kleinlib.sweep import SweepRunner  # noqa: E402
from lib.iris import fit_and_score  # noqa: E402

#: Arbitrary, distinct model seeds -- NEVER a split seed; they never decide
#: which row lands in which partition, only how `svm_rbf`/`hgbt` are fit.
SEEDS = [1, 2, 3, 4, 5]


def run_for(recipe_id: str, X_fit, y_fit, X_eval, y_eval) -> None:
    def trial_fn(params: dict) -> dict:
        _, p_eval, _ = fit_and_score(
            recipe_id, X_fit, y_fit, X_eval, random_state=params["seed"]
        )
        auc = float(roc_auc_score(y_eval, p_eval))
        return {"primary_metric": auc, "status": "ok"}

    params_list = [{"seed": s} for s in SEEDS]
    runner = SweepRunner(
        f"fit_noise_{recipe_id}",
        STUDY_DIR,
        trial_fn,
        params_list,
        metric_goal="higher",
        overwrite=True,
    )
    summary = runner.run()
    values = [t.primary_metric for t in summary.trials]
    print(f"fit_noise_{recipe_id}: seeds={SEEDS} values={values}")


def main() -> None:
    X_fit, X_eval, y_fit, y_eval = load_partition(
        "development", study_dir=STUDY_DIR, echo=False
    )
    run_for("svm_rbf", X_fit, y_fit, X_eval, y_eval)
    run_for("hgbt", X_fit, y_fit, X_eval, y_eval)


if __name__ == "__main__":
    main()
