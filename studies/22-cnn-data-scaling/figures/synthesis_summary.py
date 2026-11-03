"""Derived scalars for SYNTHESIZE — arithmetic on pinned tables, no training, no data read.

Run:  uv run --locked python studies/22-cnn-data-scaling/figures/synthesis_summary.py

Reads only artifacts that run manifests already pin:
  tables/cell_E000[1-6]_s[0-2].tsv   per-seed development cells (E0001-E0006)
  tables/scaling_fit.tsv              the pinned fit (E0007)
  tables/sealed_E0008_s[0-2].tsv      the sealed full-pool cell (E0008, test partition)
  aux_metrics.tsv                     printed aux keys (steps, best_step, n_fit, ECE)

Writes tables/synthesis_summary.tsv (quantity, value). Every row is POST-HOC and
EXPLORATORY: none was registered, none adjudicates a prediction. They exist so that
findings.md can hold the method card's unregistered priors (MC2, MC4, the N=16,000 half
of MC5) to account and quote derived numbers that have a pinned home.

Caveat carried by every cross-partition row: the six fit cells are scored on the
development lane (official train rows 50,000-59,999), the sealed cell on the official
t10k test set.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

STUDY = Path(__file__).resolve().parents[1]
N_FULL = 59_992


def slope(sizes, losses) -> float:
    """alpha of log L = log a - alpha log N by OLS (the lib/scaling.py convention)."""
    x, y = np.log(np.asarray(sizes, float)), np.log(np.asarray(losses, float))
    return float(-np.polyfit(x, y, 1)[0])


def fit(sizes, losses) -> tuple[float, float]:
    x, y = np.log(np.asarray(sizes, float)), np.log(np.asarray(losses, float))
    b, c = np.polyfit(x, y, 1)
    return float(np.exp(c)), float(-b)


def main() -> None:
    tables = STUDY / "tables"
    cells = pd.concat(
        [pd.read_csv(p, sep="\t") for p in sorted(tables.glob("cell_E000*_s*.tsv"))],
        ignore_index=True,
    )
    sealed = pd.concat(
        [pd.read_csv(p, sep="\t") for p in sorted(tables.glob("sealed_E0008_s*.tsv"))],
        ignore_index=True,
    )
    fitted = pd.read_csv(tables / "scaling_fit.tsv", sep="\t")
    aux = pd.read_csv(STUDY / "aux_metrics.tsv", sep="\t")
    auxv = {(r.experiment, r.metric): float(r.value) for r in aux.itertuples()}

    means = cells.groupby("n_train")["val_mlogloss"].mean().sort_index()
    sizes = means.index.to_numpy()
    small, large = sizes[:3], sizes[3:]
    rows: dict[str, float] = {}

    # MC2: does the curve flatten (small-end local exponent > large-end by >= 0.03)?
    rows["alpha_local_small_500_2000"] = slope(small, means.loc[small])
    rows["alpha_local_large_4000_16000"] = slope(large, means.loc[large])
    rows["mc2_small_minus_large"] = rows["alpha_local_small_500_2000"] - rows["alpha_local_large_4000_16000"]
    rows["alpha_local_8000_16000"] = slope(sizes[-2:], means.loc[sizes[-2:]])

    # MC4: printed interval width; per-seed-slope t-interval (df = seeds - 1).
    alpha_pinned = float(fitted["alpha"].iloc[0])
    printed_width = float(fitted["alpha_ci_high"].iloc[0] - fitted["alpha_ci_low"].iloc[0])
    per_seed = (
        cells.sort_values("n_train")
        .groupby("seed")
        .apply(lambda g: slope(g["n_train"], g["val_mlogloss"]), include_groups=False)
    )
    k = len(per_seed)
    tcrit = float(stats.t.ppf(0.975, k - 1))
    half = tcrit * float(per_seed.std(ddof=1)) / np.sqrt(k)
    for seed, value in per_seed.items():
        rows[f"alpha_seed{int(seed)}"] = float(value)
    rows["alpha_per_seed_mean"] = float(per_seed.mean())
    rows["alpha_t_low"] = float(per_seed.mean()) - half
    rows["alpha_t_high"] = float(per_seed.mean()) + half
    rows["alpha_t_width"] = 2 * half
    rows["alpha_printed_ci_width"] = printed_width
    rows["mc4_t_over_printed_width"] = 2 * half / printed_width

    # The N=500 vs N=1000 inversion, paired within seed (nested subsamples).
    by = cells.pivot(index="seed", columns="n_train", values="val_mlogloss")
    diff = by[1000] - by[500]
    rows["n1000_minus_n500_mean"] = float(diff.mean())
    rows["n1000_minus_n500_min"] = float(diff.min())
    rows["n1000_minus_n500_max"] = float(diff.max())
    rows["n1000_minus_n500_seeds_positive"] = float((diff > 0).sum())

    # Step budget and epochs per cell (steps x batch 128 / n_fit) and best_step share.
    for exp in [f"E000{i}" for i in range(1, 7)] + ["E0008"]:
        steps = auxv[(exp, "steps")]
        rows[f"{exp}_epochs"] = steps * 128 / auxv[(exp, "n_fit")]
        rows[f"{exp}_best_step_share"] = auxv[(exp, "best_step")] / steps
        # held-out loss over the same run's selected inner-validation loss (train-file
        # images; min over checkpoints, so selection-biased low, most at small n_inner)
        rows[f"{exp}_heldout_over_inner"] = auxv[(exp, "val_mlogloss")] / auxv[(exp, "best_inner_loss")]

    # Sealed vs the pinned law; cross-partition descriptive local exponent.
    sealed_mean = float(sealed["val_mlogloss"].mean())
    predicted = float(fitted["predicted_loss_at_full"].iloc[0])
    rows["sealed_mean_loss"] = sealed_mean
    rows["predicted_minus_sealed"] = predicted - sealed_mean
    # The notary's extrapolation_rel_error is the SEED MEAN of per-seed signed errors;
    # the signed error of the seed-mean loss differs slightly (referee note 3).
    rows["rel_error_mean_of_seeds"] = float(sealed["extrapolation_rel_error"].mean())
    rows["rel_error_of_seed_mean_loss"] = (sealed_mean - predicted) / sealed_mean
    rows["n16000_minus_sealed"] = float(means.loc[16000]) - sealed_mean
    rows["alpha_realised_16000_to_full_xpartition"] = slope([16000, N_FULL], [means.loc[16000], sealed_mean])

    # Post-hoc exploratory refit over N >= 4000 only (NOT the registered law).
    a_l, alpha_l = fit(large, means.loc[large])
    pred_l = a_l * N_FULL ** (-alpha_l)
    rows["posthoc_large_a"] = a_l
    rows["posthoc_large_alpha"] = alpha_l
    rows["posthoc_large_predicted_at_full"] = pred_l
    rows["posthoc_large_rel_error"] = (sealed_mean - pred_l) / sealed_mean
    rows["pinned_alpha"] = alpha_pinned

    # Calibration along the curve (printed val_ece seed means; E0008 on test).
    rows["ece_E0001"] = auxv[("E0001", "val_ece")]
    rows["ece_E0006"] = auxv[("E0006", "val_ece")]
    rows["ece_E0008"] = auxv[("E0008", "val_ece")]

    out = pd.DataFrame({"quantity": list(rows), "value": [round(v, 6) for v in rows.values()]})
    out.to_csv(tables / "synthesis_summary.tsv", sep="\t", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
