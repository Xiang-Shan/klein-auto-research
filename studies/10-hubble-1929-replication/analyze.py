"""CELL E0002 — the two-parameter fits of Table 1 (track `reproduction`, tests P1).

Phase adaptive-2. One published target: **K = 465 km/s/Mpc**, Hubble's constant
from the 24 objects individually, with the tolerance +/-10 registered in
`study.yaml:predictions.P1`.

Two fits, both from scratch on numpy normal equations (`method_card.md` 2-3):

    origin   v = K r                 K0 = sum(r*v) / sum(r*r)
    free     v = K r + c             (K1, c) solves (A'A)b = A'v,  A = [r 1]

P1 is supported when the NEARER of the two is still more than 10 km/s/Mpc from
465 — that is, when no two-parameter fit of the paper's own table returns the
paper's own headline number. The reason it should not is registered on the
method card: 465 came from a FOUR-parameter model that removes the solar motion
first (eq. 3), and the cell that tries to reproduce that one is E0004.

`k_free` printed here is the K the sealed cell will use
(`study.yaml:sealed_lock.k_lane_source`), so this cell also fixes the sealed
statistic's one free input, and does so before the seal is spent.
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
    HUBBLE_K_24,
    analytic_slope_se,
    block_fingerprint,
    load_block,
    ols_free_intercept,
    ols_through_origin,
    probable_error,
    r_squared,
    residual_sd_free_intercept,
    write_table,
)

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("reproduction" if SMOKE else None)

#: The one target this cell aims at, and the tolerance registered for it.
TARGET_K = HUBBLE_K_24
TARGET_TOL = 10.0


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
    r = table1["r_mpc"].to_numpy(dtype=float)
    v = table1["v_kms"].to_numpy(dtype=float)

    k_origin = ols_through_origin(r, v)
    k_free, intercept = ols_free_intercept(r, v)
    se_free = analytic_slope_se(r, v)
    sigma = residual_sd_free_intercept(r, v)

    fits = (
        ("origin", k_origin, 0.0, r_squared(r, v, k_origin * r)),
        ("free_intercept", k_free, intercept, r_squared(r, v, k_free * r + intercept)),
    )
    rows = [
        {
            "fit": name,
            "k_kms_per_mpc": k,
            "intercept_kms": c,
            "r_squared": r2,
            "target_k": TARGET_K,
            "abs_gap_to_target": abs(k - TARGET_K),
            "tolerance": TARGET_TOL,
            "reproduced": "yes" if abs(k - TARGET_K) <= TARGET_TOL else "no",
        }
        for name, k, c, r2 in fits
    ]
    min_abs_gap = min(row["abs_gap_to_target"] for row in rows)
    # One declared target for this cell; it counts as reproduced only if SOME
    # two-parameter fit lands inside the registered tolerance.
    outside = 0 if min_abs_gap <= TARGET_TOL else 1

    artifact = write_table(
        "tables/two_parameter_fits.tsv",
        (
            "fit",
            "k_kms_per_mpc",
            "intercept_kms",
            "r_squared",
            "target_k",
            "abs_gap_to_target",
            "tolerance",
            "reproduced",
        ),
        rows,
    )

    evaluate_table(
        artifact,
        outside,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        metric_name="targets_outside_tolerance",
        metric_goal="lower",
        split_fingerprint=block_fingerprint(table1),
        extra={
            "k_origin": k_origin,
            "k_free": k_free,
            "intercept_free": intercept,
            "abs_gap_465_origin": abs(k_origin - TARGET_K),
            "abs_gap_465_free": abs(k_free - TARGET_K),
            "min_abs_gap_465": min_abs_gap,
            "se_k_free": se_free,
            "probable_error_k_free": probable_error(se_free),
            "residual_sd_kms": sigma,
            "r2_origin": float(rows[0]["r_squared"]),
            "r2_free": float(rows[1]["r_squared"]),
            "n": float(np.size(r)),
        },
    )


if __name__ == "__main__":
    main()
