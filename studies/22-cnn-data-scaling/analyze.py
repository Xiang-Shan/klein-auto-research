"""Data-scaling cells, the power-law fit, and the sealed extrapolation — THE mutable surface.

A candidate changes ONE thing: ``CELL["n_train"]`` (the training-set size N of a
`primary` development cell). The training protocol is fixed in `lib/protocol.py`
and the fit arithmetic in `lib/scaling.py`, both outside `entrypoint.mutable`.

Tracks (`KLEIN_TRACK`, set by `klein run-one`):

* ``primary`` — development: the seed (`KLEIN_SEED`; `entrypoint.seeds` makes one
  cell a 3-seed array) draws N items of the train partition, holds out 10% as an
  inner validation set, trains the fixed protocol, and scores the best
  inner-validation checkpoint on the development partition (`val_mlogloss`). It
  pins ``tables/cell_<run>_s<seed>.tsv`` (run, seed, n_train, val_mlogloss,
  best_step) and the per-seed confusion table.
  SEALED (`klein run-one --final-test`, ``KLEIN_EVALUATION_KIND=final_test``):
  the fit pool is train + development (60,000) and N is all of it; the test
  partition is scored once, and the pinned law ``tables/scaling_fit.tsv`` is
  compared with this seed's measured loss (`predicted_loss`,
  `extrapolation_rel_error`). It pins ``tables/sealed_<run>_s<seed>.tsv`` — NOT a
  ``cell_*`` name, so a later fit can never pick up a sealed number.
* ``exponent`` — fits ``log L = log a - alpha log N`` over the seed means of every
  pinned development cell and prints alpha with its bootstrap interval
  (`scaling_exponent`, `fit_r2`), pinning ``tables/scaling_fit.tsv``. The fit is
  deterministic, so the seed array prints three identical blocks.

The partitions come from the contract: `kleinlib.data.load_items()` is the
index-table wrapper of `kleinlib.data.load_partition()`, prints the
`split_fingerprint:` the notary checks, and under ``KLEIN_SEALED_DRYRUN=1``
answers a sealed request with the development partition plus ``sealed_dryrun: 1``.

``KLEIN_SMOKE=1`` is a shape check: N = 300, 30 steps, nothing written. It never
reads the sealed partition (a smoke ``final_test`` must also set
``KLEIN_SEALED_DRYRUN=1``).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from lib import protocol, scaling  # the study's fixed machinery, beside this file

from kleinlib.data import load_items, partition_fingerprints
from kleinlib.dl import report_usage, seed_everything
from kleinlib.eval import evaluate_estimate
from kleinlib.eval_multiclass import evaluate_multiclass, multiclass_metrics
from kleinlib.primitives import sha256_file
from kleinlib.torch_device import pick_device

HERE = Path(__file__).resolve().parent

# --- the candidate: the whole per-experiment diff ------------------------------
CELL = {"n_train": 1000}
# -------------------------------------------------------------------------------

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
DRY_RUN = os.environ.get("KLEIN_SEALED_DRYRUN") == "1"
FINAL = os.environ.get("KLEIN_EVALUATION_KIND") == "final_test"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("primary" if SMOKE else None)
SEED = int(os.environ.get("KLEIN_SEED", "0"))
LABELS = list(range(protocol.N_CLASSES))


def run_primary(t0: float) -> None:
    if SMOKE and FINAL and not DRY_RUN:
        raise SystemExit("a smoke run never reads the sealed partition: add KLEIN_SEALED_DRYRUN=1")
    sealed = FINAL and not DRY_RUN
    fit_law = None
    if FINAL:
        # Read the pinned law BEFORE training: a missing fit crashes in seconds,
        # not after the whole full-data budget.
        fit_path = HERE / scaling.FIT_TABLE
        if not SMOKE:
            pin = scaling.pinning_manifest(HERE, scaling.FIT_TABLE, track="exponent")
            if pin is None:
                raise SystemExit(f"{scaling.FIT_TABLE} is not pinned by a measured exponent run")
            if pin["artifacts"][scaling.FIT_TABLE].get("sha256") != sha256_file(fit_path):
                raise SystemExit(f"{scaling.FIT_TABLE} differs from the bytes {pin['experiment']} pinned")
        fit_law = scaling.read_fit(fit_path)

    fit_ids, eval_ids = load_items(study_dir=HERE)  # prints split_fingerprint (+ sealed_dryrun)
    n_pool = len(fit_ids)
    if SMOKE:
        n = protocol.SMOKE_N_TRAIN
    elif FINAL:
        n = n_pool  # the full-data cell: every item of the fit pool
    else:
        n = int(CELL["n_train"])
    if sealed and n != protocol.N_FULL:
        raise SystemExit(f"the sealed cell must train on N={protocol.N_FULL}, the fit pool holds {n_pool}")

    seed_everything(SEED, deterministic=True)
    rng = np.random.default_rng(SEED)
    fit_pos, inner_pos = protocol.draw_subsample(n_pool, n, rng)
    store = protocol.ItemStore(HERE / "data" / "prepared")
    x_fit, y_fit = store.load([fit_ids[i] for i in fit_pos])
    x_inner, y_inner = store.load([fit_ids[i] for i in inner_pos])
    x_eval, y_eval = store.load(eval_ids)

    steps = protocol.SMOKE_STEPS if SMOKE else (protocol.DRYRUN_STEPS if DRY_RUN else protocol.steps_for(n))
    every = protocol.SMOKE_EVAL_EVERY if SMOKE else protocol.eval_every(steps)
    model, info = protocol.train(x_fit, y_fit, x_inner, y_inner, steps=steps, every=every, rng=rng, device=pick_device())
    proba = protocol.predict_proba(model, x_eval, next(model.parameters()).device)
    report_usage(steps=info["steps"])

    extra: dict[str, float | int] = {
        "n_train": n,
        "n_fit": len(fit_pos),
        "n_inner": len(inner_pos),
        "steps": info["steps"],
        "eval_every": every,
        "best_step": info["best_step"],
        "best_inner_loss": round(info["best_inner_loss"], 6),
    }
    if FINAL:
        # The measured loss of THIS seed (the same number the block prints).
        measured = multiclass_metrics(y_eval, proba, labels=LABELS)[0]["val_mlogloss"]
        a, alpha = fit_law
        law = scaling.extrapolation(a, alpha, n, measured)
        # Per seed: predicted = a * N**(-alpha) at THIS run's N (60,000 on the
        # sealed run; the 50,000-item train partition on a dry run, so the
        # rehearsal compares like with like), and
        # extrapolation_rel_error = (measured - predicted) / measured. The notary
        # averages every printed key over the seed array, so the run's
        # `extrapolation_rel_error` is the SEED MEAN OF THE PER-SEED RELATIVE
        # ERRORS — which differs from (mean measured - predicted) / mean measured
        # only at second order in the seed spread (Jensen); P3 and P4 read the
        # former. Both are recomputable from the pinned sealed tables.
        extra.update({"fit_a": a, "fit_alpha": alpha, **law})

    # Under the seed array the evaluator pins tables/confusion_<run>_s<seed>.tsv itself.
    writes = not (SMOKE or DRY_RUN)  # the dry run must leave the tree as it found it
    value = evaluate_multiclass(
        y_eval, proba, labels=LABELS, exp_id=EXPERIMENT_ID, metric_name="val_mlogloss", t0=t0,
        fit_seconds=info["fit_seconds"], train_n=len(fit_pos), extra=extra,
        study_dir=HERE if writes else None,
    )
    if writes:
        row = {"run": EXPERIMENT_ID, "seed": SEED, "n_train": n, "val_mlogloss": f"{value:.6f}", "best_step": info["best_step"]}
        if FINAL:
            name = f"tables/sealed_{EXPERIMENT_ID}_s{SEED}.tsv"
            row.update({k: f"{float(extra[k]):.10g}" for k in ("fit_a", "fit_alpha", "predicted_loss", "extrapolation_rel_error")})
        else:
            name = f"tables/cell_{EXPERIMENT_ID}_s{SEED}.tsv"
        (HERE / "tables").mkdir(parents=True, exist_ok=True)
        pd.DataFrame([row]).to_csv(HERE / name, sep="\t", index=False, lineterminator="\n")
        print(f"artifact: {name}")


def run_exponent(t0: float) -> None:
    if FINAL:
        raise SystemExit("the exponent track takes no sealed run (its confirmation is a replication)")
    table, notes = scaling.collect_cells(HERE, require_pinned=not SMOKE)
    for note in notes:
        print(f"note: {note}")
    per_n, params = scaling.fit_cells(table, n_full=protocol.N_FULL)
    # The fit's inputs were measured on the development partition; print its
    # fingerprint so the notary can hold the fit to the same rows.
    fingerprint = partition_fingerprints(HERE)["development"]
    if not SMOKE:
        rel = scaling.write_fit(HERE, per_n)
        print(f"artifact: {rel}")
    evaluate_estimate(
        params["alpha"], params["alpha_ci_low"], params["alpha_ci_high"], int(params["n_cell_rows"]),
        exp_id=EXPERIMENT_ID, metric_name="scaling_exponent", metric_goal="higher", t0=t0,
        extra={
            "fit_r2": params["fit_r2"],
            "a": params["a"],
            "n_sizes": int(params["n_sizes"]),
            "predicted_loss_at_full": params["predicted_loss_at_full"],
            "ci_clamped": int(params["ci_clamped"]),
        },
        split_fingerprint=fingerprint,
        study_dir=None if SMOKE else HERE,
    )


def main() -> None:
    if EXPERIMENT_ID is None or TRACK is None:
        raise SystemExit("run through `klein run-one` (or KLEIN_SMOKE=1 for a shape check)")
    t0 = time.time()
    if TRACK == "primary":
        run_primary(t0)
    elif TRACK == "exponent":
        run_exponent(t0)
    else:
        raise SystemExit(f"unknown track {TRACK!r} (primary | exponent)")


if __name__ == "__main__":
    main()
