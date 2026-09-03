"""CELL E0013 — SEALED (track `simulate`, tests P6). Fresh seed block C.

Confirmation phase. For kind `simulate`, "sealed" means **a fresh seed block
never used in development** (`inquiry-model.md`). Block C (20260905) is declared
in `study.yaml:simulation.seed_blocks`, was fixed at the CONSULT gate, and has
been read by nothing: the development coverage cells used block B, the Phase-0
floor used blocks 20260911-20260915, and the estimate track's bootstrap uses
block A.

The experiment is byte-for-byte the one E0009 ran, on a new seed: 1000
replicates of

    v_i = 450.0 * r_i + Normal(0, 232.910670)      i = 1..24

at Table 1's own 24 design points, each replicate refitting the free-intercept
slope and building the same 500-resample percentile interval the `estimate`
track reports, and recording whether 450.0 lies inside.

**P6** asks whether that coverage clears 0.90. Its consequence was pre-scripted
at CONSULT and has not moved since: if refuted, every interval this study
reports is downgraded to descriptive in the findings and no claim rests on
nominal coverage.

**Disclosed twice already, and once more here.** `sweep:coverage_floor` measured
coverage on five floor blocks (mean 0.9268) at Phase 0, and E0009 measured 0.911
on block B — so P6's verdict is foreseeable. That is the unavoidable cost of
measuring the resolution of a quantity a prediction reads; it was recorded when
it happened (`program.md`, Phase-0 decision log) and findings §② carries it. The
sealed block is what the verdict is *taken on*, and it is fresh.

The rehearsal substitutes seed block B for C, so a dry-run's number is E0009's
and not this cell's.
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
    acknowledge_sealed_dryrun,
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

#: E0009's development coverage on block B, quoted for the printed block so a
#: reader sees the sealed number beside the one it confirms. Its home is E0009.
DEVELOPMENT_COVERAGE_BLOCK_B = 0.911


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
    seed_blocks = spec["seed_blocks"]

    # THE seal for a simulation lane: which seed block is read. The rehearsal
    # substitutes the development block, so no dry-run ever touches C.
    rehearsing = acknowledge_sealed_dryrun()
    block_name = "B" if rehearsing else "C"
    seed = int(seed_blocks[block_name])
    if not rehearsing and evaluation_kind != "final_test":
        raise RuntimeError(
            "seed block C is the simulate track's sealed evidence and is readable "
            "only inside `klein run-one --final-test`; this run has "
            f"KLEIN_EVALUATION_KIND={evaluation_kind!r}"
        )

    k_true = float(spec["k_true"])
    n_rep = int(spec["n_rep"])
    n_boot = int(spec["n_boot"])
    level = float(spec["ci_level"])

    table1 = load_block(BLOCK_TABLE1, echo=False)
    r = table1["r_mpc"].to_numpy(dtype=float)

    result = coverage_experiment(
        r,
        k_true=k_true,
        sigma=DGP_SIGMA,
        n_rep=n_rep,
        seed=seed,
        method="bootstrap",
        n_boot=n_boot,
        level=level,
    )

    rows = [
        {
            "interval": "percentile_bootstrap",
            "seed_block": block_name,
            "seed": float(seed),
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
        "tables/sealed_coverage_blockC.tsv",
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
            "sealed_seed_block_c": float(seed_blocks["C"]),
            "seed_used": float(seed),
            "shortfall_from_nominal": level - result["coverage"],
            "mean_k_hat": result["mean_k_hat"],
            "bias": result["bias"],
            "mean_ci_width": result["mean_ci_width"],
            "development_coverage_block_b": DEVELOPMENT_COVERAGE_BLOCK_B,
            "sealed_minus_development": result["coverage"] - DEVELOPMENT_COVERAGE_BLOCK_B,
        },
    )


if __name__ == "__main__":
    main()
