"""CELL E0007 — inverse versus forward regression (track `estimate`, tests P5).

Phase adaptive-3. A least-squares line is not symmetric. Regressing v on r
minimizes vertical distances and treats the DISTANCES as exact; regressing r on
v and inverting treats the VELOCITIES as exact. When the x-variable carries the
larger error the ordinary fit is dragged toward zero — regression dilution,
`ref:frost2000` — so the two fits bracket the truth and their gap measures how
much the choice of response matters.

Hubble's velocities came from spectra and are good to a few km/s; his distances
came from a brightness argument and are wrong by factors. The method card's
prior 4 therefore says the inverse fit should return a LARGER K, and P5 puts a
number on "larger": more than one standard error of the paired difference.

**Paired, on common random numbers.** Both estimators are refit on the SAME
2000 resamples (`lib.hubble.paired_bootstrap_k`), so the difference carries no
independent noise; drawing twice would inflate its standard error and make the
comparison look less decisive than it is. This is the same construction the
Phase-0 sweep `sweep:mc_resolution` used to measure the resolution of exactly
this ratio across master seeds (mean 2.36499, std 0.0382297), so a verdict here
is already known to be outside the seed's reach.

The printed key P5's rule reads is `inverse_minus_forward_se_units`.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kleinlib.eval import evaluate_estimate  # noqa: E402

from lib.hubble import (  # noqa: E402
    BLOCK_TABLE1,
    block_fingerprint,
    inverse_regression_k,
    load_block,
    ols_free_intercept,
    paired_bootstrap_k,
    percentile_ci,
    simulation_spec,
    write_table,
)

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("estimate" if SMOKE else None)

N_BOOT = 2000
CI_LEVEL = 0.95


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

    seed_a = int(simulation_spec()["seed_blocks"]["A"])

    table1 = load_block(BLOCK_TABLE1, echo=False)
    r = table1["r_mpc"].to_numpy(dtype=float)
    v = table1["v_kms"].to_numpy(dtype=float)

    k_forward, _intercept = ols_free_intercept(r, v)
    k_inverse = inverse_regression_k(r, v)

    draws = paired_bootstrap_k(
        r, v, n_boot=N_BOOT, seed=seed_a, estimators=("free", "inverse")
    )
    difference = draws["inverse"] - draws["free"]
    se_difference = float(np.std(difference, ddof=1))
    mean_difference = float(np.mean(difference))
    low_diff, high_diff = percentile_ci(difference, CI_LEVEL)
    se_units = mean_difference / se_difference

    low_inv, high_inv = percentile_ci(draws["inverse"], CI_LEVEL)

    rows = [
        {
            "quantity": "forward_v_on_r",
            "value": k_forward,
            "bootstrap_mean": float(np.mean(draws["free"])),
            "bootstrap_se": float(np.std(draws["free"], ddof=1)),
            "ci_low": float(percentile_ci(draws["free"], CI_LEVEL)[0]),
            "ci_high": float(percentile_ci(draws["free"], CI_LEVEL)[1]),
        },
        {
            "quantity": "inverse_r_on_v_inverted",
            "value": k_inverse,
            "bootstrap_mean": float(np.mean(draws["inverse"])),
            "bootstrap_se": float(np.std(draws["inverse"], ddof=1)),
            "ci_low": low_inv,
            "ci_high": high_inv,
        },
        {
            "quantity": "paired_difference_inverse_minus_forward",
            "value": k_inverse - k_forward,
            "bootstrap_mean": mean_difference,
            "bootstrap_se": se_difference,
            "ci_low": low_diff,
            "ci_high": high_diff,
        },
    ]
    artifact = write_table(
        "tables/inverse_vs_forward.tsv",
        ("quantity", "value", "bootstrap_mean", "bootstrap_se", "ci_low", "ci_high"),
        rows,
    )

    evaluate_estimate(
        k_inverse,
        low_inv,
        high_inv,
        int(r.size),
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        metric_name="k_kms_per_mpc",
        metric_goal="lower",
        split_fingerprint=block_fingerprint(table1),
        extra={
            "artifact": "tables/inverse_vs_forward.tsv",
            "n_boot": float(N_BOOT),
            "k_forward": k_forward,
            "k_inverse": k_inverse,
            "point_difference": k_inverse - k_forward,
            "paired_mean_difference": mean_difference,
            "paired_se_difference": se_difference,
            "inverse_minus_forward_se_units": se_units,
            "difference_ci_low": low_diff,
            "difference_ci_high": high_diff,
            "ratio_inverse_over_forward": k_inverse / k_forward,
        },
    )


if __name__ == "__main__":
    main()
