"""MEASUREMENT sweep — the `simulate` track's measured noise floor.

Phase adaptive-1. A measurement sweep promotes no winner and no `results.tsv`
row (`references/sweep-rules.md`, the measurement carve-out); its evidence is
this sidecar plus the `noise_floor:` block `klein noise-floor` prints, and it is
registered with `klein sweep register` so findings can cite it as
`sweep:coverage_floor`.

**What it measures.** The `simulate` track reports a COVERAGE — the fraction of
replicates whose 95 % interval contains the declared truth. That number really
does move: a fresh simulation seed block redraws the whole synthetic dataset, so
coverage measured on 1000 replicates carries Monte-Carlo error. `minimum_delta`
must therefore be measured, never guessed (`references/consult-protocol.md`), and
this is the recipe: run the identical coverage experiment on five independent
seed blocks and take `max(2 x std, range/2)`.

**Which estimand.** Klein ships three recipes; none of them is quite this, and
mislabelling a floor is worse than naming it honestly, so the block is recorded
with `--method "seed-block-lottery"` (free text, for a recipe Klein does not
ship) and `--estimand marginal-resplit`. A fresh simulation seed block redraws
the entire dataset the estimator sees, which is the simulation's exact analogue
of re-drawing the split; it is a MARGINAL spread of one procedure's own score,
not a paired difference between two.

The five floor seeds are declared in `study.yaml:simulation.seed_blocks.floor`
and are disjoint from blocks A, B and C — a floor measured on the same seed a
cell reports would flatter the cell.

    uv run --locked python ../../scripts/run_with_log.py \\
      --timeout-seconds 300 --log sweeps/coverage_floor.log -- \\
      uv run --locked python -u sweeps/coverage_floor.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kleinlib.sweep import SweepRunner  # noqa: E402

from lib.hubble import (  # noqa: E402
    BLOCK_TABLE1,
    coverage_experiment,
    load_block,
    simulation_spec,
)


def main() -> None:
    spec = simulation_spec()
    seeds = [int(s) for s in spec["seed_blocks"]["floor"]]
    k_true = float(spec["k_true"])
    n_rep = int(spec["n_rep"])
    n_boot = int(spec["n_boot"])
    level = float(spec["ci_level"])
    # sigma is the residual scatter of Table 1's free-intercept fit, measured at
    # the DATA gate and written on the DGP card (data_card.md, appendix).
    sigma = 232.910670

    table1 = load_block(BLOCK_TABLE1, echo=False)
    r = table1["r_mpc"].to_numpy(dtype=float)

    def trial(params: dict) -> dict:
        result = coverage_experiment(
            r,
            k_true=k_true,
            sigma=sigma,
            n_rep=n_rep,
            seed=int(params["seed_block"]),
            method="bootstrap",
            n_boot=n_boot,
            level=level,
        )
        return {"primary_metric": result["coverage"], **result}

    summary = SweepRunner(
        "coverage_floor",
        study_dir=Path(__file__).resolve().parent.parent,
        trial_fn=trial,
        params_list=[
            {"seed_block": seed, "n_rep": n_rep, "n_boot": n_boot, "k_true": k_true}
            for seed in seeds
        ],
        metric_goal="higher",
    ).run()

    values = [t.primary_metric for t in summary.trials if t.status == "ok"]
    print(f"trials ok: {len(values)} of {len(seeds)}")
    print("values: " + ", ".join(f"{x:.6f}" for x in values))
    print(f"mean:  {np.mean(values):.6f}")
    print(f"std:   {np.std(values, ddof=1):.6f}")
    print(f"range: {max(values) - min(values):.6f}")
    print(f"suggested minimum_delta: {max(2 * np.std(values, ddof=1), (max(values) - min(values)) / 2):.6f}")


if __name__ == "__main__":
    main()
