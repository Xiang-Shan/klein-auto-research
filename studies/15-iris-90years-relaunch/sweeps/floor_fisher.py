"""Phase-0 sweep: floor_fisher -- the MARGINAL split-lottery floor for the
`fisher` track's own LEVEL (an estimate, not a comparison, so the honest
floor is the marginal one, not the paired one -- `study.yaml`'s own comment
on `tracks.fisher.metric`).

Recombines the contract's train+development rows -- whatever that count
actually is (`kleinlib.data.contract_split`'s first two partitions; NOT a
hardcoded literal, since `data_card.md`'s BLOCKER #1 fix already shifted
train from 50 to 49 rows) -- and redraws a fresh stratified split k=5 times,
at k seeds that are NOT `study.yaml`'s own split seed, refitting `lda_all4`
and rescoring its own development AUC each time. The sealed 25 rows
(`contract_split`'s third partition) are never read here -- the lottery
redraws ONLY inside the 74 non-sealed rows.

Usage::

    uv run --locked python sweeps/floor_fisher.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

STUDY_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY_DIR))

from kleinlib.data import contract_split  # noqa: E402
from kleinlib.sweep import SweepRunner  # noqa: E402
from lib.iris import fit_and_score  # noqa: E402

#: The lottery's own seeds -- distinct from study.yaml's split seed
#: (20260904); never used to decide which rows are sealed.
SEEDS = [201, 202, 203, 204, 205]


def main() -> None:
    X_tr, X_dev, X_te, y_tr, y_dev, y_te = contract_split(STUDY_DIR)
    X_nonsealed = pd.concat([X_tr, X_dev])
    y_nonsealed = pd.concat([y_tr, y_dev])
    dev_fraction = len(X_dev) / len(X_nonsealed)
    print(
        f"floor_fisher: non-sealed rows={len(X_nonsealed)} "
        f"(train={len(X_tr)} + development={len(X_dev)}), "
        f"redraw dev_fraction={dev_fraction:.6f}, sealed rows untouched={len(X_te)}"
    )

    def trial_fn(params: dict) -> dict:
        seed = params["seed"]
        X_tr_r, X_dev_r, y_tr_r, y_dev_r = train_test_split(
            X_nonsealed,
            y_nonsealed,
            test_size=dev_fraction,
            random_state=seed,
            stratify=y_nonsealed,
        )
        _, p_r, _ = fit_and_score("lda_all4", X_tr_r, y_tr_r, X_dev_r)
        auc = float(roc_auc_score(y_dev_r, p_r))
        return {"primary_metric": auc, "status": "ok"}

    params_list = [{"seed": s} for s in SEEDS]
    runner = SweepRunner(
        "floor_fisher", STUDY_DIR, trial_fn, params_list, metric_goal="higher", overwrite=True
    )
    summary = runner.run()
    values = [t.primary_metric for t in summary.trials]
    print(f"floor_fisher: seeds={SEEDS} values={values}")


if __name__ == "__main__":
    main()
