"""CELL E0003 — Table 1's printed absolute magnitudes (track `reproduction`, tests P9).

Phase adaptive-2. One published target: **Table 1's `M_t` column**, all 24
values, reproduced from the paper's own `m_t` and `r_mpc` by the distance
modulus (`method_card.md` eq. 4, `lib/hubble.absolute_magnitude`):

    M = m - 5 log10(r) - 25          (r in Mpc)

The tolerance registered in `study.yaml:predictions.P9` is 0.06 mag for EVERY
object — half the paper's own printed precision of 0.1 mag, so a value that
merely rounded differently still passes and a value computed under a different
convention does not.

Why this cell exists, and why it runs before the two gap cells: it is the
development rehearsal of the SEALED cell's machinery. The sealed statistic is
the mean of `absolute_magnitude(m_t, v_kms / k_lane)` over Table 2
(`study.yaml:sealed_lock`), and this cell exercises the identical function on
the block that is not sealed. If the modulus does not reproduce the paper's own
printed column, the sealed registration rests on a wrong formula — and the seal
is still unspent when that is discovered.

The cell reproduces the paper's printed column MEAN as well (a second published
quantity: Hubble prints -15.5 for Table 1), but only the per-object agreement is
the registered target; the mean is printed as context.
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
    absolute_magnitude,
    block_fingerprint,
    load_block,
    write_table,
)

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("reproduction" if SMOKE else None)

#: Half the paper's printed precision of 0.1 mag — registered as P9's tolerance.
TARGET_TOL = 0.06

#: The column mean Hubble prints under Table 1, for context (not the target).
PRINTED_MEAN_M_T = -15.5


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
    m = table1["m_t"].to_numpy(dtype=float)
    r = table1["r_mpc"].to_numpy(dtype=float)
    printed = table1["M_t"].to_numpy(dtype=float)

    computed = absolute_magnitude(m, r)
    deviation = np.abs(computed - printed)

    rows = [
        {
            "object": str(name),
            "m_t": float(mi),
            "r_mpc": float(ri),
            "M_t_printed": float(pi),
            "M_t_computed": float(ci),
            "abs_deviation": float(di),
            "tolerance": TARGET_TOL,
            "reproduced": "yes" if di <= TARGET_TOL else "no",
        }
        for name, mi, ri, pi, ci, di in zip(
            table1["object"], m, r, printed, computed, deviation, strict=True
        )
    ]

    max_dev = float(np.max(deviation))
    # One declared target for this cell: the whole printed column. It counts as
    # reproduced only if EVERY object is inside the registered tolerance.
    outside = 0 if max_dev <= TARGET_TOL else 1

    artifact = write_table(
        "tables/table1_absolute_magnitudes.tsv",
        (
            "object",
            "m_t",
            "r_mpc",
            "M_t_printed",
            "M_t_computed",
            "abs_deviation",
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
            "max_abs_mag_dev": max_dev,
            "mean_abs_mag_dev": float(np.mean(deviation)),
            "n_objects": float(printed.size),
            "n_outside_tolerance": float(int(np.sum(deviation > TARGET_TOL))),
            "mean_M_t_computed": float(np.mean(computed)),
            "mean_M_t_printed": float(np.mean(printed)),
            "paper_printed_mean_M_t": PRINTED_MEAN_M_T,
            "abs_gap_printed_column_mean": abs(float(np.mean(printed)) - PRINTED_MEAN_M_T),
        },
    )


if __name__ == "__main__":
    main()
