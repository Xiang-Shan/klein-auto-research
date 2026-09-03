"""CELL E0011 — SEALED (track `reproduction`, tests P8). Table 2, one access.

Confirmation phase. This is the study's prospective analysis lock being spent.
Everything below was fixed in `study.yaml:sealed_lock` and hashed at the CONSULT
gate, before any cell ran:

    block        table2 (22 nebulae)
    columns      v_kms, m_t          -- and ONLY those
    forbidden    r_mpc, vs_kms, M_t
    statistic    mean over rows with v_kms > 0 of  M = m_t - 5*log10(v_kms/K) - 25
    K            k_free from E0002's pinned tables/two_parameter_fits.tsv
    target       -15.3   tolerance  0.3

**What it is a test of.** Hubble's own argument for Table 2 was an internal
cross-check: if you turn the 22 nebulae's velocities into distances with the
constant, the absolute magnitudes you get should look like Table 1's — "the two
mean magnitudes, -15.3 and -15.5 ... are closely similar" (`ref:hubble1929`).
This cell re-runs that check with THIS study's constant in place of his. It asks
whether the paper's internal consistency survives the substitution.

**Why r_mpc is not used, and could not be.** Table 2's distance column is not an
independent measurement: the DATA gate showed `r = (v - vs)/500` holds to
floating-point exactness on 20 of the 21 rows where both are printed and rounds
on the 21st. It is Hubble's adopted K applied to the velocity. Comparing our K
against it would return, up to rounding, the ratio of our K to his — a tautology
dressed as a test. `load_block` drops it, along with `vs_kms` and the printed
`M_t`, before this cell ever sees the frame.

**The one deviation from Hubble's procedure, stated rather than hidden.** He
removed the solar motion from each velocity before dividing by K; that needs the
per-object coordinates E0004 audited as unobtainable. This cell therefore uses
the raw `v_kms`, which is the only velocity the sealed columns carry. The
registration said so from the start (`sealed_lock.statistic`), and findings will
report the difference as a limitation of the comparison, not as a result.

`K_LANE` below is transcribed from the E0002 artifact by the cell at run time,
not hardcoded: the number's home is that pinned table.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kleinlib.eval import evaluate_table  # noqa: E402

from lib.hubble import (  # noqa: E402
    BLOCK_TABLE2,
    TABLE2_FORBIDDEN_COLUMNS,
    TABLE2_MEAN_ABS_MAG,
    absolute_magnitude,
    block_fingerprint,
    load_block,
    sealed_lock,
    study_dir,
    write_table,
)

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("reproduction" if SMOKE else None)


def k_from_e0002() -> float:
    """The lane's K, read from E0002's pinned table — never recomputed here.

    `study.yaml:sealed_lock.k_lane_source` names this table and this row. Reading
    it rather than refitting is what makes the sealed statistic a function of an
    already-notarized number instead of a fresh choice made at sealing time.
    """
    table = pd.read_csv(study_dir() / "tables" / "two_parameter_fits.tsv", sep="\t")
    row = table[table["fit"] == "free_intercept"]
    if len(row) != 1:
        raise RuntimeError("tables/two_parameter_fits.tsv has no unique free_intercept row")
    return float(row["k_kms_per_mpc"].iloc[0])


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

    lock = sealed_lock()
    target = float(lock["target"])
    tolerance = float(lock["tolerance"])
    k_lane = k_from_e0002()

    # THE seal. Refuses outside --final-test; serves Table 1 and prints
    # `sealed_dryrun: 1` under KLEIN_SEALED_DRYRUN=1; drops the forbidden columns.
    block = load_block(BLOCK_TABLE2, echo=False)
    leaked = [c for c in TABLE2_FORBIDDEN_COLUMNS if c in block.columns]
    if leaked:
        raise RuntimeError(f"forbidden columns reached the sealed cell: {leaked}")

    v = block["v_kms"].to_numpy(dtype=float)
    m = block["m_t"].to_numpy(dtype=float)
    names = [str(x) for x in block["object"]]

    usable = v > 0.0
    r_implied = v[usable] / k_lane
    magnitudes = absolute_magnitude(m[usable], r_implied)
    mean_abs_mag = float(np.mean(magnitudes))
    deviation = abs(mean_abs_mag - target)

    rows = [
        {
            "object": name,
            "v_kms": float(vi),
            "m_t": float(mi),
            "r_implied_mpc": float(ri),
            "M_implied": float(Mi),
        }
        for name, vi, mi, ri, Mi in zip(
            [n for n, u in zip(names, usable, strict=True) if u],
            v[usable],
            m[usable],
            r_implied,
            magnitudes,
            strict=True,
        )
    ]
    artifact = write_table(
        "tables/sealed_table2_magnitudes.tsv",
        ("object", "v_kms", "m_t", "r_implied_mpc", "M_implied"),
        rows,
    )

    outside = 0 if deviation <= tolerance else 1
    evaluate_table(
        artifact,
        outside,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        metric_name="targets_outside_tolerance",
        metric_goal="lower",
        split_fingerprint=block_fingerprint(block),
        extra={
            "mean_abs_mag": mean_abs_mag,
            "target_mean_abs_mag": target,
            "abs_deviation": deviation,
            "tolerance": tolerance,
            "k_lane": k_lane,
            "n_used": float(int(usable.sum())),
            "n_excluded_nonpositive_v": float(int((~usable).sum())),
            "n_block_rows": float(len(block)),
            "sd_abs_mag": float(np.std(magnitudes, ddof=1)),
            "min_abs_mag": float(np.min(magnitudes)),
            "max_abs_mag": float(np.max(magnitudes)),
            "printed_table2_mean": TABLE2_MEAN_ABS_MAG,
        },
    )


if __name__ == "__main__":
    main()
