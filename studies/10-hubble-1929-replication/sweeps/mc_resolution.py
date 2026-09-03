"""MEASUREMENT sweep — the Monte-Carlo resolution of the estimate track's printed keys.

Phase adaptive-1. A measurement sweep promotes no winner and no `results.tsv`
row (`references/sweep-rules.md`, the measurement carve-out); its evidence is
this sidecar plus the block `klein noise-floor` prints, and it is registered with
`klein sweep register` so findings can cite it as `sweep:mc_resolution`.

**What it measures, and why it is not the track's bar.** The `estimate` track's
primary metric is a point estimate of K: a closed-form least-squares slope over
the same fixed 24 rows every time, so it is deterministic and its spread across
seeds is exactly zero — the track declares `exactness: exact` for that reason.
What is NOT deterministic is the part of the printed block a registered rule
actually reads: the bootstrap keys. P5's rule is
`inverse_minus_forward_se_units > 1`, a ratio that moves with the master seed of
the resampling, and a verdict that flips with the seed is not a verdict.

So this sweep re-runs the SAME paired bootstrap — forward and inverse estimators
on common random numbers, B = 2000 — under five independent master seeds, and
records that ratio. Its spread is `fit_noise` on the estimate track: provenance,
never a keep bar (`klein noise-floor --estimand fit-noise` refuses to call it
one). Findings quote it beside P5's verdict so a reader can see how far the
verdict sits from the seed's reach.

    uv run --locked python ../../scripts/run_with_log.py \\
      --timeout-seconds 300 --log sweeps/mc_resolution.log -- \\
      uv run --locked python -u sweeps/mc_resolution.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kleinlib.sweep import SweepRunner  # noqa: E402

from lib.hubble import BLOCK_TABLE1, load_block, paired_bootstrap_k  # noqa: E402

#: Five independent master seeds. NONE of them is seed block A (20260903), the
#: block the estimate track's own cells use, nor B or C, the simulate track's
#: development and sealed blocks: a floor measured on the same seed a cell
#: reports would flatter the cell.
MASTER_SEEDS = (20260921, 20260922, 20260923, 20260924, 20260925)

#: The same B the estimate cells use, so the resolution measured here is the
#: resolution those cells actually have.
N_BOOT = 2000


def main() -> None:
    table1 = load_block(BLOCK_TABLE1, echo=False)
    r = table1["r_mpc"].to_numpy(dtype=float)
    v = table1["v_kms"].to_numpy(dtype=float)

    def trial(params: dict) -> dict:
        seed = int(params["master_seed"])
        draws = paired_bootstrap_k(
            r, v, n_boot=N_BOOT, seed=seed, estimators=("free", "inverse")
        )
        difference = draws["inverse"] - draws["free"]
        se_difference = float(np.std(difference, ddof=1))
        point = float(np.mean(difference))
        return {
            "primary_metric": point / se_difference,
            "point_difference": point,
            "se_difference": se_difference,
        }

    summary = SweepRunner(
        "mc_resolution",
        study_dir=Path(__file__).resolve().parent.parent,
        trial_fn=trial,
        params_list=[{"master_seed": seed, "n_boot": N_BOOT} for seed in MASTER_SEEDS],
        metric_goal="higher",
    ).run()

    values = [t.primary_metric for t in summary.trials if t.status == "ok"]
    print(f"trials ok: {len(values)} of {len(MASTER_SEEDS)}")
    print("values: " + ", ".join(f"{x:.6f}" for x in values))
    print(f"mean:  {np.mean(values):.6f}")
    print(f"std:   {np.std(values, ddof=1):.6f}")
    print(f"range: {max(values) - min(values):.6f}")


if __name__ == "__main__":
    main()
