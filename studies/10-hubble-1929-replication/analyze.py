"""CELL E0006 — the bootstrap interval for K (track `estimate`).

Phase adaptive-3. This is the estimate the study reports: not "Hubble's
constant", which E0002-E0005 showed does not come back out of his table, but
**the constant those 24 objects support**, with an interval that was computed
rather than quoted.

Method (`method_card.md` eq. 5, `ref:efron1979`): case resampling of the 24
(r, v) PAIRS — the galaxies are a sample of objects, not a designed grid, so
what varies between hypothetical repetitions is which galaxies you got — 2000
resamples from seed block A (`study.yaml:simulation.seed_blocks.A`), refit each
time, and take the empirical 2.5 % and 97.5 % quantiles.

The cell prints intervals for BOTH two-parameter estimators, which is why the
phase slate could subsume its candidate #4: whether the interval depends on the
intercept choice costs nothing to answer here.

It adjudicates no prediction. P4 — whether the lower bound clears the modern
H0 = 70 — is the `estimate` track's SEALED comparison against an external
reference value, spent once in the confirmation phase (`inquiry-model.md`: for
kind `estimate`, sealed means "a prospectively locked block, or an external
reference value, compared once"). This cell fixes the estimator that comparison
will use; it does not make the comparison.
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
    HUBBLE_K_24,
    HUBBLE_PE_24,
    analytic_slope_se,
    block_fingerprint,
    bootstrap_k,
    load_block,
    ols_free_intercept,
    ols_through_origin,
    percentile_ci,
    probable_error,
    simulation_spec,
    write_table,
)

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("estimate" if SMOKE else None)

#: The resample count P4's `inconclusive_if` requires at least 1000 of.
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

    k_free, _intercept = ols_free_intercept(r, v)
    k_origin = ols_through_origin(r, v)

    draws_free = bootstrap_k(r, v, n_boot=N_BOOT, seed=seed_a, estimator="free")
    draws_origin = bootstrap_k(r, v, n_boot=N_BOOT, seed=seed_a, estimator="origin")
    low_free, high_free = percentile_ci(draws_free, CI_LEVEL)
    low_origin, high_origin = percentile_ci(draws_origin, CI_LEVEL)

    rows = [
        {
            "estimator": "free_intercept",
            "k_point": k_free,
            "ci_low": low_free,
            "ci_high": high_free,
            "ci_width": high_free - low_free,
            "bootstrap_se": float(np.std(draws_free, ddof=1)),
            "analytic_se": analytic_slope_se(r, v),
            "n_boot": float(N_BOOT),
        },
        {
            "estimator": "through_origin",
            "k_point": k_origin,
            "ci_low": low_origin,
            "ci_high": high_origin,
            "ci_width": high_origin - low_origin,
            "bootstrap_se": float(np.std(draws_origin, ddof=1)),
            "analytic_se": float("nan"),
            "n_boot": float(N_BOOT),
        },
    ]
    artifact = write_table(
        "tables/bootstrap_k.tsv",
        (
            "estimator",
            "k_point",
            "ci_low",
            "ci_high",
            "ci_width",
            "bootstrap_se",
            "analytic_se",
            "n_boot",
        ),
        rows,
    )

    se_free = float(np.std(draws_free, ddof=1))
    evaluate_estimate(
        k_free,
        low_free,
        high_free,
        int(r.size),
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        metric_name="k_kms_per_mpc",
        metric_goal="lower",
        split_fingerprint=block_fingerprint(table1),
        extra={
            "artifact": str(artifact.relative_to(Path(".").resolve())) if artifact.is_absolute() else str(artifact),
            "n_boot": float(N_BOOT),
            "seed_block_a": float(seed_a),
            "ci_width": high_free - low_free,
            "bootstrap_se_free": se_free,
            "analytic_se_free": analytic_slope_se(r, v),
            "probable_error_free": probable_error(se_free),
            "k_origin": k_origin,
            "ci_low_origin": low_origin,
            "ci_high_origin": high_origin,
            "hubble_target_k": HUBBLE_K_24,
            "hubble_probable_error": HUBBLE_PE_24,
            "target_inside_ci": 1.0 if low_free <= HUBBLE_K_24 <= high_free else 0.0,
        },
    )


if __name__ == "__main__":
    main()
