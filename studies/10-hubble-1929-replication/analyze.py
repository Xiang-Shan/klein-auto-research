"""CELL E0009 — coverage of the percentile bootstrap interval (track `simulate`).

Phase adaptive-4, development seed block B. The `estimate` track reports a
95 % percentile-bootstrap interval for K. This cell asks the only question that
makes such an interval mean anything: **under a process where the answer is
known, how often does it actually contain the answer?**

The declared truth is the DGP the DATA gate wrote and hashed
(`data_card.md`, appendix; `study.yaml:simulation`):

    v_i = 450.0 * r_i + Normal(0, 232.910670)      i = 1..24

with `r_i` fixed at Table 1's own 24 printed distances — so the simulation asks
about THIS design, not a generic n = 24 — and sigma taken from the residual
scatter of Table 1's free-intercept fit, measured at the DATA gate.

Each of 1000 replicates draws a synthetic dataset, refits the free-intercept
slope, builds the same percentile interval E0006 builds (500 resamples, the same
`lib.hubble` code path), and records whether `450.0` lies inside. Coverage is
the fraction that do, and it is this track's primary metric.

**No prediction is adjudicated here.** For kind `simulate` the sealed evidence
is a fresh seed block never used in development (`inquiry-model.md`), so P6 is
decided on block C in the confirmation phase. This cell measures the same
quantity on block B, which is what makes the sealed run a confirmation rather
than a first look.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kleinlib.eval import evaluate_table  # noqa: E402

from lib.hubble import (  # noqa: E402
    BLOCK_TABLE1,
    block_fingerprint,
    coverage_experiment,
    load_block,
    simulation_spec,
    write_table,
)

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("simulate" if SMOKE else None)

#: The residual scatter of Table 1's free-intercept fit, measured at the DATA
#: gate (`data_gate_profile.py` section 4) and declared on the DGP card.
DGP_SIGMA = 232.910670


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

    spec = simulation_spec()
    k_true = float(spec["k_true"])
    n_rep = int(spec["n_rep"])
    n_boot = int(spec["n_boot"])
    level = float(spec["ci_level"])
    seed_b = int(spec["seed_blocks"]["B"])

    table1 = load_block(BLOCK_TABLE1, echo=False)
    r = table1["r_mpc"].to_numpy(dtype=float)

    result = coverage_experiment(
        r,
        k_true=k_true,
        sigma=DGP_SIGMA,
        n_rep=n_rep,
        seed=seed_b,
        method="bootstrap",
        n_boot=n_boot,
        level=level,
    )

    rows = [
        {
            "interval": "percentile_bootstrap",
            "seed_block": "B",
            "seed": float(seed_b),
            "k_true": k_true,
            "sigma": DGP_SIGMA,
            "n_obs": float(r.size),
            "n_rep": float(n_rep),
            "n_boot": float(n_boot),
            "nominal_level": level,
            "coverage": result["coverage"],
            "mean_k_hat": result["mean_k_hat"],
            "bias": result["bias"],
            "mean_ci_width": result["mean_ci_width"],
        }
    ]
    artifact = write_table(
        "tables/coverage_bootstrap_blockB.tsv",
        (
            "interval",
            "seed_block",
            "seed",
            "k_true",
            "sigma",
            "n_obs",
            "n_rep",
            "n_boot",
            "nominal_level",
            "coverage",
            "mean_k_hat",
            "bias",
            "mean_ci_width",
        ),
        rows,
    )

    evaluate_table(
        artifact,
        result["coverage"],
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        metric_name="coverage",
        metric_goal="higher",
        split_fingerprint=block_fingerprint(table1),
        extra={
            "n_rep": float(n_rep),
            "n_boot": float(n_boot),
            "n_obs": float(r.size),
            "k_true": k_true,
            "sigma": DGP_SIGMA,
            "nominal_level": level,
            "shortfall_from_nominal": level - result["coverage"],
            "mean_k_hat": result["mean_k_hat"],
            "bias": result["bias"],
            "mean_ci_width": result["mean_ci_width"],
            "seed_block_b": float(seed_b),
        },
    )


if __name__ == "__main__":
    main()
