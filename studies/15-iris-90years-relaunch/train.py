"""The only per-candidate mutable surface in this study.

E0001, `fisher` track -- the identity-anchor-and-level cell
(`research_plan.md` Phase `anchor-and-floor`, step 1). `lib/iris.py` is
STABLE library code (the loader, the five recipes, the three feature sets,
the bootstrap helpers, the `extra={...}` assembly); this file composes those
primitives into ONE cell and prints its block.

What this cell does, in order
------------------------------
1. Asserts the identity anchor (P0) on the RAW loader -- `sklearn.datasets
   .load_iris` restricted to the hard pair, never the prepared table, so a
   lawful DATA-gate row drop cannot manufacture a false refutation -- and on
   a fresh count of the prepared table against the contract split's own
   partition sizes.
2. Fits Fisher's 1936 LDA (`lda_all4`) on the training rows the contract
   hands back, scores the development rows, and reports accuracy/errors at
   the 0.5 threshold (P1, P2) the way Fisher himself would have read them.
3. Bootstraps a 95% interval for that ROC-AUC (P3), 2000 replicates.

`kleinlib.eval.evaluate_estimate` is the registered-mode "estimate" cell
shape (`fisher` is `mode: registered, kind: estimate` -- a track that
MEASURES a level, not one that climbs): it prints `primary_metric` (the
point AUC estimate), `ci_low`/`ci_high`/`n`, and everything else named in
`extra={...}`.

Later phases (`parade`, `ablation-map`, `confirmation`) will branch this
file on `KLEIN_TRACK` to add the `modern` and `ablation` cells -- each such
edit is its own candidate transaction, one falsifiable idea at a time. Only
the `fisher` anchor cell exists today.
"""

from __future__ import annotations

import os
import time

import kleinlib
from kleinlib.data import load_partition
from lib.iris import anchor_extra, bootstrap_auc_ci, fit_and_score, partition_sizes_and_total, raw_identity_counts

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("fisher" if SMOKE else None)

RECIPE = "lda_all4"


def run_fisher_anchor_cell(evaluation_kind: str, t0: float) -> float:
    """E0001: identity anchor (P0) + Fisher's 1936 LDA level with a bootstrap
    interval (P1, P2, P3). The only cell this track has today.
    """
    # ---- P0: the identity anchor, independent of the prepared table -------
    raw_counts = raw_identity_counts()
    train_rows, dev_rows, test_rows, prepared_total = partition_sizes_and_total(".")
    partition_sum_matches = (train_rows + dev_rows + test_rows) == prepared_total

    # ---- the partition this run actually scores ----------------------------
    # `load_partition` prints `split_fingerprint:`, which the notary compares
    # against the value the DATA gate froze -- the ONLY partition authority
    # this file uses (war story 8).
    X_fit, X_eval, y_fit, y_eval = load_partition(evaluation_kind, study_dir=".")

    model, p_eval, fit_seconds = fit_and_score(RECIPE, X_fit, y_fit, X_eval)
    y_pred = (p_eval >= 0.5).astype(int)
    y_eval_arr = y_eval.to_numpy()
    val_accuracy = float((y_pred == y_eval_arr).mean())
    val_errors = int((y_pred != y_eval_arr).sum())

    ci_low, ci_high, n_boot = bootstrap_auc_ci(y_eval_arr, p_eval, n_boot=2000)

    from sklearn.metrics import roc_auc_score

    val_auc = float(roc_auc_score(y_eval_arr, p_eval))

    extra = anchor_extra(
        raw_counts=raw_counts,
        partition_sum_matches=partition_sum_matches,
        val_accuracy=val_accuracy,
        val_errors=val_errors,
        val_rows=len(X_eval),
        ci_low=ci_low,
        ci_high=ci_high,
        n_boot=n_boot,
    )

    return kleinlib.eval.evaluate_estimate(
        val_auc,
        ci_low,
        ci_high,
        len(X_eval),
        exp_id=EXPERIMENT_ID,
        metric_name="val_auc",
        metric_goal="higher",
        extra=extra,
        study_dir=".",
        t0=t0,
    )


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
    if SMOKE:
        evaluation_kind = evaluation_kind or "development"
    missing = [
        name
        for name, value in (
            ("KLEIN_EVALUATION_KIND", evaluation_kind),
            ("KLEIN_EXPERIMENT_ID", EXPERIMENT_ID),
            ("KLEIN_TRACK", TRACK),
        )
        if value is None
    ]
    if missing:
        raise RuntimeError(
            "train.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python train.py` — it prints "
            "the canonical block, writes no sidecars or snapshots, and is not "
            "evidence. Missing: " + ", ".join(missing)
        )

    if TRACK == "fisher":
        run_fisher_anchor_cell(evaluation_kind, t0)
        return
    raise NotImplementedError(
        f"KLEIN_TRACK={TRACK!r}: only the `fisher` anchor cell (E0001) exists in "
        "train.py so far — the `modern`/`ablation` cells are added in later phases, "
        "one candidate transaction at a time (research_plan.md's experiment ladder)."
    )


if __name__ == "__main__":
    main()
