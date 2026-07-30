"""Phase-0 noise-floor measurement sweep (see sweep-rules.md carve-out).

Runs the ANCHOR config (single-start NM, budget 200) on five disjoint seed
blocks — the dev block plus four floor blocks — varying nothing else. The
spread of the five mean gaps is the sampling noise of the estimator itself;
`klein noise-floor` turns the sidecar into study.yaml's `noise_floor:` block.
Promotes NO winner and writes NO results.tsv row: a measurement is not a search.

Run from the study directory:  uv run --locked python sweeps/noise_floor.py
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from objective import DEV_BASE, EVAL_BUDGET, F_STAR, FLOOR_BASES, N_REPS, NoisyBudgetedObjective, block, rosenbrock
from optimizers import nelder_mead

from kleinlib.sweep import SweepRunner


def anchor_mean_gap(params: dict) -> dict:
    base = int(params["seed_base"])
    gaps = []
    for seed in block(base, N_REPS):
        objective = NoisyBudgetedObjective(seed, budget=EVAL_BUDGET)
        answer = nelder_mead(objective, objective.random_start(), EVAL_BUDGET)
        gaps.append(rosenbrock(answer) - F_STAR)
    return {"primary_metric": statistics.fmean(gaps), "status": "ok"}


if __name__ == "__main__":
    runner = SweepRunner(
        "noise_floor",
        Path(__file__).resolve().parents[1],
        anchor_mean_gap,
        [{"seed_base": base} for base in (DEV_BASE, *FLOOR_BASES)],
        metric_goal="lower",
    )
    summary = runner.run()
    print(f"measurement sweep complete: {len(runner.params_list)} cells -> {runner.sidecar_path}")
