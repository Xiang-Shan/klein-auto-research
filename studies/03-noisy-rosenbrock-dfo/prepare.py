"""Prepare the immutable local artifact declared by study.yaml:data.prepared_path.

The prepared artifact of a synthetic lab is its REFERENCE CELL: the anchor
config (single-start Nelder-Mead, 200-eval budget) run once per development
seed, per-rep true gaps recorded. E0001 recomputes the identical cell through
the loop and must match to 1e-9 — the split-identity anchor for a study whose
"split" is a seed-block contract. Never reads the sealed final block.
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

from objective import DEV_BASE, EVAL_BUDGET, N_REPS, assert_blocks_disjoint

OUT = Path("data/prepared/reference_cell.csv")


def main() -> None:
    assert_blocks_disjoint()  # the seed-block contract, proven mechanically
    from objective import F_STAR, NoisyBudgetedObjective, block, rosenbrock
    from optimizers import nelder_mead

    rows = []
    for seed in block(DEV_BASE, N_REPS):
        objective = NoisyBudgetedObjective(seed, budget=EVAL_BUDGET)
        answer = nelder_mead(objective, objective.random_start(), EVAL_BUDGET)
        rows.append({"rep": seed - DEV_BASE, "seed": seed,
                     "final_gap": f"{rosenbrock(answer) - F_STAR:.12f}",
                     "evals_used": objective.calls})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["rep", "seed", "final_gap", "evals_used"])
        writer.writeheader()
        writer.writerows(rows)
    mean_gap = statistics.fmean(float(r["final_gap"]) for r in rows)
    print(f"data source: synthetic:noisy_rosenbrock_v1 — generated locally, seed block {DEV_BASE}..{DEV_BASE + N_REPS - 1}")
    print(f"wrote {OUT} ({len(rows)} reps); reference mean_final_gap: {mean_gap:.6f}")


if __name__ == "__main__":
    main()
