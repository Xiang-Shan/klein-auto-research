"""The only per-candidate mutable surface in this study.

The per-experiment diff is the four constants under "the candidate" — ``CANDIDATE``
(the rung being tried), ``REFERENCE`` (the rung it claims to beat, refitted on the same
rows in this same process), ``V1_ANCHOR`` (the value the v1 ledger recorded for this
rung, or ``None``) and ``DEV_INCUMBENT`` (set only for the sealed run) — and nothing
else. The rung definitions live in ``lib/rungs.py``, which is stable study library code:
a per-experiment edit must not be able to change what Phase 0 measured its floor on.

What every run prints, on top of the canonical block
---------------------------------------------------
Nothing here is a literal a later reader must trust: the floor comes from the contract,
the anchor comes from the v1 ledger transcribed in ``scouting_ledger.md``, and the
reference rung is refitted on the SAME evaluation rows so a comparison lives inside one
printed block instead of being subtracted across two log files.

============================ =================================================
``rung``                     which rung this run is
``v1_anchor``                what the v1 study recorded for this rung, on its
                             own (two-way) partition
``anchor_gap``               ``val_auc - v1_anchor`` — the transfer residual
``reference_rung``           the rung refitted here for comparison
``reference_auc``            that rung's AUC on these same rows
``delta_vs_reference``       ``val_auc - reference_auc`` (a PAIRED difference)
``delta_in_floors``          that difference in units of the contract's
                             ``minimum_delta`` — the number P3, P5 and P6 read
``reference_brier``          the reference rung's Brier score on these rows
``brier_delta_vs_reference`` candidate Brier minus reference Brier; negative
                             means better-calibrated
``dev_incumbent``            (sealed run only) the development incumbent's score
``sealed_shift_in_floors``   (sealed run only) the sealed score's distance from
                             that incumbent, in floors
``twin_free_rows``           evaluation rows with NO byte-identical twin among the
                             rows this run was fitted on
``twin_free_auc``            the AUC on exactly those rows
``twin_free_gap``            ``twin_free_auc - val_auc`` — how much of the headline
                             number the duplicated rows were worth
============================ =================================================

The last three exist because the DATA gate FAILED this study on duplicate row content
straddling the partitions and the gate was overridden rather than fixed (`program.md`,
2026-09-03; `data_card.md` BLOCKER #1). An accepted risk that is never measured is an
excuse, so every run measures it. ``primary_metric`` deliberately stays the
full-partition AUC: the registered anchors compare against v1 values computed the same
contaminated way, and re-defining the measurement would make that comparison
meaningless.

``delta_in_floors`` and ``sealed_shift_in_floors`` are printed only once the contract
carries a measured ``minimum_delta``. Before Phase 0 sets it there is no floor to divide
by, and a prediction whose key is not printed is INCONCLUSIVE rather than refuted, which
is the honest answer.
"""

from __future__ import annotations

import os
import time

from sklearn.metrics import brier_score_loss, roc_auc_score

import kleinlib
from kleinlib.contract import load_contract
from kleinlib.data import load_partition
from lib.duplicate_exposure import duplicate_free_mask
from lib.rungs import fit_rung, positive_probabilities

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("primary" if SMOKE else None)

# --- the candidate: the whole per-experiment diff surface -------------------
# Empty between experiments. Choosing a rung IS the falsifiable idea a candidate
# transaction carries, so the surface carries no rung until one is chosen.
CANDIDATE = "glm_ohe_balanced"   # E0001: the v1 split-identity anchor
REFERENCE = None                 # the first rung has nothing to beat yet
V1_ANCHOR = 0.625462             # scouting_ledger.md S1, v1 results.tsv row 1
DEV_INCUMBENT = None             # set only for the sealed confirmation run


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
            "syntax/shape check use `KLEIN_SMOKE=1 python train.py` — it prints the "
            "canonical block, writes no sidecars or snapshots, and is not evidence. "
            "Missing: " + ", ".join(missing)
        )

    if CANDIDATE is None:
        raise RuntimeError(
            "no rung is chosen: set CANDIDATE to a key of lib.rungs.RECIPES. The "
            "surface is empty between experiments on purpose — choosing the rung is "
            "the one falsifiable idea a candidate transaction carries."
        )

    X_fit, X_eval, y_fit, y_eval = load_partition(evaluation_kind, study_dir=".")
    minimum_delta = float(
        load_contract(".")["tracks"][TRACK]["metric"].get("minimum_delta") or 0.0
    )

    fit_start = time.time()
    model, _, X_eval_t = fit_rung(CANDIDATE, X_fit, X_eval, y_fit)
    fit_seconds = time.time() - fit_start

    probabilities = positive_probabilities(model, X_eval_t)
    candidate_auc = float(roc_auc_score(y_eval, probabilities))
    candidate_brier = float(brier_score_loss(y_eval, probabilities))

    # The overridden DATA-gate BLOCKER, measured on this run's own rows.
    twin_free = duplicate_free_mask(X_fit, y_fit, X_eval, y_eval)
    twin_free_auc = float(roc_auc_score(y_eval[twin_free], probabilities[twin_free]))

    extra: dict[str, str] = {
        "rung": CANDIDATE,
        "twin_free_rows": str(int(twin_free.sum())),
        "twin_free_auc": f"{twin_free_auc:.6f}",
        "twin_free_gap": f"{twin_free_auc - candidate_auc:.6f}",
    }
    if V1_ANCHOR is not None:
        extra["v1_anchor"] = f"{V1_ANCHOR:.6f}"
        extra["anchor_gap"] = f"{candidate_auc - V1_ANCHOR:.6f}"
    if REFERENCE is not None:
        reference_model, _, X_reference_eval = fit_rung(REFERENCE, X_fit, X_eval, y_fit)
        reference_probabilities = positive_probabilities(reference_model, X_reference_eval)
        reference_auc = float(roc_auc_score(y_eval, reference_probabilities))
        reference_brier = float(brier_score_loss(y_eval, reference_probabilities))
        extra["reference_rung"] = REFERENCE
        extra["reference_auc"] = f"{reference_auc:.6f}"
        extra["delta_vs_reference"] = f"{candidate_auc - reference_auc:.6f}"
        extra["reference_brier"] = f"{reference_brier:.6f}"
        extra["brier_delta_vs_reference"] = f"{candidate_brier - reference_brier:.6f}"
        if minimum_delta > 0:
            extra["delta_in_floors"] = f"{(candidate_auc - reference_auc) / minimum_delta:.4f}"
    if DEV_INCUMBENT is not None:
        extra["dev_incumbent"] = f"{DEV_INCUMBENT:.6f}"
        if minimum_delta > 0:
            extra["sealed_shift_in_floors"] = (
                f"{(candidate_auc - DEV_INCUMBENT) / minimum_delta:.4f}"
            )

    kleinlib.eval.evaluate(
        model,
        X_eval_t,
        y_eval,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        fit_seconds=fit_seconds,
        train_n=len(X_fit),
        val_n=len(X_eval),
        metric_name="val_auc",
        metric_goal="higher",
        extra=extra,
    )


if __name__ == "__main__":
    main()
