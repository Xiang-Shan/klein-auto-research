"""CELL E0008 — jackknife influence of each object (track `estimate`).

Phase adaptive-3. With 24 objects, leave-one-out is exhaustive and costs
nothing, so this cell answers a question the interval cannot: **which galaxies
carry the constant?** For each object i it refits the free-intercept slope on
the other 23 and records the shift, then summarizes with the jackknife standard
error (`ref:efron1979`).

It also settles data-card issue 6 without a cell of its own. Four Table-1
objects — N.G.C. 4382, 4472, 4486 and 4649 — are all assigned r = 2.0 Mpc,
because Hubble gave the whole Virgo cluster one distance from its mean
luminosity rather than measuring four. Those are the largest distances in the
table, so they have the longest lever on any slope; the cell drops all four
together and reports what K becomes. That is a *sensitivity* measurement, not a
correction: nothing downstream uses the reduced fit, and the reported estimate
stays the one E0006 fixed.

The jackknife is used here for INFLUENCE, which is what it is good at on a
smooth statistic like a least-squares slope. It is not used as the study's
uncertainty method — that is the bootstrap of E0006 — and the two standard
errors are printed side by side so a reader can see they agree.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kleinlib.eval import evaluate_table  # noqa: E402

from lib.hubble import (  # noqa: E402
    BLOCK_TABLE1,
    analytic_slope_se,
    block_fingerprint,
    jackknife_k,
    jackknife_se,
    load_block,
    ols_free_intercept,
    write_table,
)

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("estimate" if SMOKE else None)

#: The Virgo-cluster distance Hubble assigned from the cluster's mean luminosity
#: — one number shared by four objects (data card, issue 6).
VIRGO_DISTANCE_MPC = 2.0


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
            "analyze.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python analyze.py`. "
            "Missing: " + ", ".join(missing)
        )

    table1 = load_block(BLOCK_TABLE1, echo=False)
    names = [str(x) for x in table1["object"]]
    r = table1["r_mpc"].to_numpy(dtype=float)
    v = table1["v_kms"].to_numpy(dtype=float)

    k_full, _intercept = ols_free_intercept(r, v)
    loo = jackknife_k(r, v, estimator="free")
    influence = loo - k_full
    se_jack = jackknife_se(loo)

    rows = [
        {
            "object": name,
            "r_mpc": float(ri),
            "v_kms": float(vi),
            "k_without_object": float(ki),
            "influence_kms_per_mpc": float(di),
            "virgo_cluster": "yes" if ri == VIRGO_DISTANCE_MPC else "no",
        }
        for name, ri, vi, ki, di in zip(names, r, v, loo, influence, strict=True)
    ]
    artifact = write_table(
        "tables/jackknife_k.tsv",
        (
            "object",
            "r_mpc",
            "v_kms",
            "k_without_object",
            "influence_kms_per_mpc",
            "virgo_cluster",
        ),
        rows,
    )

    # Data-card issue 6: drop the whole Virgo group at once.
    virgo = r == VIRGO_DISTANCE_MPC
    k_without_virgo, _c = ols_free_intercept(r[~virgo], v[~virgo])

    worst = int(np.argmax(np.abs(influence)))
    evaluate_table(
        artifact,
        float(np.mean(loo)),
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        metric_name="k_kms_per_mpc",
        metric_goal="lower",
        split_fingerprint=block_fingerprint(table1),
        extra={
            "k_full": k_full,
            "k_jackknife_mean": float(np.mean(loo)),
            "jackknife_se": se_jack,
            "analytic_se": analytic_slope_se(r, v),
            "max_abs_influence": float(np.abs(influence).max()),
            "max_influence_r_mpc": float(r[worst]),
            "n_objects": float(r.size),
            "n_virgo_objects": float(int(virgo.sum())),
            "k_without_virgo_group": float(k_without_virgo),
            "virgo_group_influence": float(k_without_virgo - k_full),
        },
    )


if __name__ == "__main__":
    main()
