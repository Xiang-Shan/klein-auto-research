"""CELL E0010 — coverage of the analytic interval (track `simulate`).

Phase adaptive-4, development seed block B. E0009 measured what the percentile
bootstrap covers under the declared DGP. This cell measures what the textbook
normal-theory interval covers under the same DGP and the same seed block:

    k_hat +/- 1.959963984540054 * SE(k_hat)

with SE the closed-form standard error of the free-intercept slope
(`lib.hubble.analytic_slope_se`).

**Why it earns a transaction.** One coverage number is a fact; two are a
diagnosis. If both intervals fall short of 0.95 by about the same amount, the
culprit is n = 24 — twenty-four points simply do not pin a slope — and no change
of interval method would help. If only the bootstrap falls short, the culprit is
the method, and `ref:diciccio1996` names the fix (BCa, bootstrap-t). Findings can
then say which, instead of gesturing at "small-sample effects".

The two cells do NOT share replicates, and the amendment in `program.md` says
why and what was chosen instead: each coverage carries a binomial Monte-Carlo
error of about 0.0086 at 1000 replicates, far below any shortfall worth
diagnosing.

No prediction is adjudicated here. P6 is decided on the sealed block C.
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

DGP_SIGMA = 232.910670

#: E0009's measured coverage for the percentile bootstrap on this same block,
#: read from the ledger and printed here so the two sit side by side in one
#: block. It is quoted, not recomputed: the number's home is E0009's manifest.
BOOTSTRAP_COVERAGE_BLOCK_B = 0.911


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
        method="analytic",
        level=level,
    )

    rows = [
        {
            "interval": "analytic_normal_theory",
            "seed_block": "B",
            "seed": float(seed_b),
            "k_true": k_true,
            "sigma": DGP_SIGMA,
            "n_obs": float(r.size),
            "n_rep": float(n_rep),
            "nominal_level": level,
            "coverage": result["coverage"],
            "mean_k_hat": result["mean_k_hat"],
            "bias": result["bias"],
            "mean_ci_width": result["mean_ci_width"],
        },
        {
            "interval": "percentile_bootstrap (E0009, quoted)",
            "seed_block": "B",
            "seed": float(seed_b),
            "k_true": k_true,
            "sigma": DGP_SIGMA,
            "n_obs": float(r.size),
            "n_rep": float(n_rep),
            "nominal_level": level,
            "coverage": BOOTSTRAP_COVERAGE_BLOCK_B,
            "mean_k_hat": float("nan"),
            "bias": float("nan"),
            "mean_ci_width": float("nan"),
        },
    ]
    artifact = write_table(
        "tables/coverage_analytic_blockB.tsv",
        (
            "interval",
            "seed_block",
            "seed",
            "k_true",
            "sigma",
            "n_obs",
            "n_rep",
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
            "n_obs": float(r.size),
            "k_true": k_true,
            "sigma": DGP_SIGMA,
            "nominal_level": level,
            "shortfall_from_nominal": level - result["coverage"],
            "mean_k_hat": result["mean_k_hat"],
            "bias": result["bias"],
            "mean_ci_width": result["mean_ci_width"],
            "bootstrap_coverage_e0009": BOOTSTRAP_COVERAGE_BLOCK_B,
            "analytic_minus_bootstrap": result["coverage"] - BOOTSTRAP_COVERAGE_BLOCK_B,
            "seed_block_b": float(seed_b),
        },
    )


if __name__ == "__main__":
    main()
