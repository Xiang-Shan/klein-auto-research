"""CELL E0001 — the identity anchor (track `reproduction`, adjudicates P0).

Phase adaptive-1. A `replicate` study anchors on a published sum, count or table
dimension of the transcribed data and hard-STOPs on mismatch
(`references/replication-protocol.md`): every later number in this study is
computed from these bytes, so if the bytes are not Hubble's, every later cell is
a confidently wrong measurement of the wrong table.

Four pre-declared targets, each with the tolerance registered in study.yaml:

    sum(r_mpc) over Table 1  == 21.873 Mpc   (tol 0.001)
    sum(v_kms) over Table 1  == 8955 km/s    (tol 1)
    rows in Table 1          == 24           (exact)
    rows in Table 2          == 22           (exact)

The cell's primary metric is `targets_outside_tolerance`: how many of those four
this run failed to reproduce. Zero is the only acceptable value, and P0's rule
re-checks the two sums independently on the printed block.

Note on the two counts: Table 2 is the SEALED block, and this cell does not read
it — `load_block("table2")` would refuse outside a `--final-test` run, and
rightly. Its row count comes from the prepared artifact's `block` column, which
is metadata the DATA gate already fingerprinted, not a measurement of any sealed
value.
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
    ANCHOR_N_TABLE1,
    ANCHOR_N_TABLE2,
    ANCHOR_SUM_R,
    ANCHOR_SUM_V,
    BLOCK_TABLE1,
    BLOCK_TABLE2,
    block_fingerprint,
    load_block,
    prepared_frame,
    write_table,
)

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("reproduction" if SMOKE else None)

#: Each anchor: (name, published target, tolerance, units).
ANCHORS = (
    ("sum_r", ANCHOR_SUM_R, 1e-3, "Mpc"),
    ("sum_v", ANCHOR_SUM_V, 1.0, "km/s"),
    ("n_table1", float(ANCHOR_N_TABLE1), 0.0, "rows"),
    ("n_table2", float(ANCHOR_N_TABLE2), 0.0, "rows"),
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
            "analyze.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python analyze.py` — it prints "
            "the canonical block, writes no sidecars or snapshots, and is not "
            "evidence. Missing: " + ", ".join(missing)
        )

    # echo=False: the evaluator prints the fingerprint once, from the block it
    # actually measured, exactly as `kleinlib.data.load_partition(echo=False)` does.
    table1 = load_block(BLOCK_TABLE1, echo=False)
    r = table1["r_mpc"].to_numpy(dtype=float)
    v = table1["v_kms"].to_numpy(dtype=float)

    # The sealed block is NOT read here: only how many rows carry its label in
    # the prepared artifact the DATA gate already fingerprinted.
    frame = prepared_frame()
    observed = {
        "sum_r": float(np.sum(r)),
        "sum_v": float(np.sum(v)),
        "n_table1": float(len(table1)),
        "n_table2": float((frame["block"] == BLOCK_TABLE2).sum()),
    }

    rows = []
    outside = 0
    for name, target, tol, units in ANCHORS:
        value = observed[name]
        deviation = abs(value - target)
        reproduced = deviation <= tol
        outside += 0 if reproduced else 1
        rows.append(
            {
                "anchor": name,
                "published": target,
                "recomputed": value,
                "abs_deviation": deviation,
                "tolerance": tol,
                "units": units,
                "reproduced": "yes" if reproduced else "no",
            }
        )

    artifact = write_table(
        "tables/identity_anchors.tsv",
        ("anchor", "published", "recomputed", "abs_deviation", "tolerance", "units", "reproduced"),
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
            "sum_r": observed["sum_r"],
            "sum_v": observed["sum_v"],
            "n_table1": observed["n_table1"],
            "n_table2": observed["n_table2"],
            "max_abs_deviation": max(row["abs_deviation"] for row in rows),
        },
    )

    if outside and not SMOKE:
        raise SystemExit(
            f"IDENTITY ANCHOR FAILED: {outside} of {len(ANCHORS)} published anchors did "
            "not reproduce. STOP — every later cell would measure the wrong bytes."
        )


if __name__ == "__main__":
    main()
