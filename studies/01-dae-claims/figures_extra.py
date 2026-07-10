"""figures_extra.py — study-01 bespoke figure set (pre-registered in program.md).

Four figures kleinlib.figures has no generic helper for, styled with kleinlib.figures'
own palette (the validated dataviz-skill instance) so the study's figure set reads as
one system. Every number is parsed from the committed artifacts — results.tsv,
aux_metrics.tsv, sweeps/swaprate.sidecar.tsv — plus the three CITED campaign constants
(raw-LR 0.6255, tuned raw-GBDT 0.6701, soft-vote 0.6715; see program.md "Baselines
cited"). Torch-free, lightgbm-free; regenerate any time with:

    cd studies/01-dae-claims && uv run python figures_extra.py

Figures:
  plot_when_it_pays.png      — val_auc per pipeline arm; E2's supervised MLP given
                               full prominence (the study's surprise) next to the
                               0.6701 / 0.6715 campaign reference lines. Bars start
                               at 0.5 = AUC chance, so length == skill-above-chance.
  plot_noise_sensitivity.png — E5 sidecar: val_auc vs swap rate, with the DAE's
                               held-out recon es_mse per rate on a twin axis.
  plot_imputer_gain.png      — E7: downstream val_auc by MCAR rate and imputer arm
                               (line panel, clean reference), + cell-level numeric
                               RMSE bars (the 3.4x story), cat-accuracy annotated.
  plot_anomaly_lift.png      — E8: lift@{5,10,20}% of the recon-error ranker vs the
                               1.0 no-signal line (an honest null).
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from kleinlib.figures import CATEGORICAL, CHROME, _save_fig

_STUDY = Path(__file__).resolve().parent

# Campaign baselines — CITED constants (program.md "Baselines cited", never rerun).
RAW_LR = 0.6255
RAW_GBDT = 0.6701
SOFT_VOTE = 0.6715


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _aux(rows: list[dict[str, str]], exp: str, metric: str) -> float:
    for r in rows:
        if r["experiment"] == exp and r["metric"] == metric:
            return float(r["value"])
    raise KeyError(f"aux metric {metric!r} for experiment {exp} not found")


def _results_metric(rows: list[dict[str, str]], exp: str) -> float:
    for r in rows:
        if r["experiment"] == exp:
            return float(r["primary_metric"])
    raise KeyError(f"experiment {exp} not in results.tsv")


def plot_when_it_pays(results: list[dict[str, str]]) -> Path:
    arms = [  # (label, val_auc, is_the_surprise)
        ("E1 raw features -> LR\n(campaign anchor)", _results_metric(results, "1"), False),
        ("E4 DAE reps -> linear probe", _results_metric(results, "4"), False),
        ("E6 DAE reps + raw -> LGBM", _results_metric(results, "6"), False),
        ("E3 DAE reps -> LGBM\n(RQ1 headline)", _results_metric(results, "3"), False),
        ("E2 raw encoding -> supervised MLP\n(THE SURPRISE)", _results_metric(results, "2"), True),
    ]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    y = np.arange(len(arms))
    for i, (label, auc, surprise) in enumerate(arms):
        color = CATEGORICAL[1] if surprise else CATEGORICAL[0]
        ax.barh(i, auc - 0.5, left=0.5, color=color, height=0.62, zorder=2)
        ax.text(auc + 0.0008, i, f"{auc:.4f}", va="center", fontsize=9,
                fontweight="bold" if surprise else "normal", color=CHROME["primary_ink"])
    ax.axvline(RAW_GBDT, color=CHROME["secondary_ink"], linestyle="--", linewidth=1.2, zorder=3)
    ax.axvline(SOFT_VOTE, color=CHROME["secondary_ink"], linestyle=":", linewidth=1.2, zorder=3)
    # reference labels live in the empty bottom-right region (right of E1's short bar)
    ax.text(RAW_GBDT - 0.0012, -0.42, f"tuned raw GBDT {RAW_GBDT} ", rotation=90,
            va="bottom", ha="right", fontsize=8, color=CHROME["secondary_ink"])
    ax.text(SOFT_VOTE + 0.0012, -0.42, f" campaign soft-vote {SOFT_VOTE}", rotation=90,
            va="bottom", ha="left", fontsize=8, color=CHROME["secondary_ink"])
    ax.set_yticks(y)
    ax.set_yticklabels([a[0] for a in arms], fontsize=9)
    ax.set_xlim(0.5, 0.695)
    ax.set_xlabel("val_auc  (bars start at 0.5 = chance, so length = skill above chance)")
    ax.set_title("When does the DAE pay? — no arm beats plain supervised learning")
    ax.grid(axis="y", visible=False)
    return _save_fig(fig, _STUDY, "plot_when_it_pays")


def plot_noise_sensitivity(aux: list[dict[str, str]]) -> Path:
    rates = [0.10, 0.15, 0.25]
    aucs = [_aux(aux, "5", f"swaprate_{r:.2f}_val_auc") for r in rates]
    mses = [_aux(aux, "5", f"swaprate_{r:.2f}_es_mse") for r in rates]

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.plot(rates, aucs, marker="o", linewidth=2, color=CATEGORICAL[0], label="DAE->LGBM val_auc", zorder=3)
    for r, a in zip(rates, aucs):
        ax.annotate(f"{a:.4f}", (r, a), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=8, color=CHROME["primary_ink"])
    ax.annotate("Jahrer's 0.15 = local optimum\n(E3/E5 winner)", (0.15, aucs[1]),
                textcoords="offset points", xytext=(12, -30), fontsize=8,
                color=CHROME["secondary_ink"],
                arrowprops={"arrowstyle": "-", "color": CHROME["muted"], "lw": 0.8})
    ax.set_xlabel("swap rate p (fraction of eligible cells corrupted)")
    ax.set_ylabel("downstream val_auc", color=CATEGORICAL[0])
    ax.tick_params(axis="y", labelcolor=CATEGORICAL[0])
    ax.set_xticks(rates)

    ax2 = ax.twinx()
    ax2.plot(rates, mses, marker="s", linewidth=1.6, linestyle="--", color=CATEGORICAL[2],
             label="held-out recon MSE", zorder=2)
    ax2.set_ylabel("held-out reconstruction MSE (early-stop signal)", color=CATEGORICAL[2])
    ax2.tick_params(axis="y", labelcolor=CATEGORICAL[2])
    ax2.grid(visible=False)

    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [ln.get_label() for ln in lines], loc="lower center", fontsize=8)
    ax.set_title("Noise sensitivity (E5): swap-rate is a real lever, not flat")
    return _save_fig(fig, _STUDY, "plot_noise_sensitivity")


def plot_imputer_gain(aux: list[dict[str, str]]) -> Path:
    rates = [10, 30]
    auc_dae = [_aux(aux, "7", f"auc_dae_mcar{r}") for r in rates]
    auc_med = [_aux(aux, "7", f"auc_median_mcar{r}") for r in rates]
    clean = _aux(aux, "7", "auc_clean_reps")
    rmse_dae = [_aux(aux, "7", f"rmse_num_dae_mcar{r}") for r in rates]
    rmse_med = [_aux(aux, "7", f"rmse_num_median_mcar{r}") for r in rates]
    acc_dae = [_aux(aux, "7", f"cat_acc_dae_mcar{r}") for r in rates]
    acc_med = [_aux(aux, "7", f"cat_acc_median_mcar{r}") for r in rates]

    fig, (axl, axr) = plt.subplots(1, 2, figsize=(10, 4.2))

    axl.axhline(clean, color=CHROME["muted"], linestyle="--", linewidth=1,
                label=f"clean reps ({clean:.4f})")
    axl.plot(rates, auc_dae, marker="o", linewidth=2, color=CATEGORICAL[0], label="DAE-reconstruction impute")
    axl.plot(rates, auc_med, marker="s", linewidth=2, color=CATEGORICAL[5], label="median/mode impute")
    for r, a in zip(rates, auc_dae):
        axl.annotate(f"{a:.4f}", (r, a), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
    for r, a in zip(rates, auc_med):
        axl.annotate(f"{a:.4f}", (r, a), textcoords="offset points", xytext=(0, -14), ha="center", fontsize=8)
    axl.set_xticks(rates)
    axl.set_xticklabels([f"{r}%" for r in rates])
    axl.set_xlabel("MCAR missing rate (eligible columns)")
    axl.set_ylabel("downstream val_auc (frozen E3-LGBM head)")
    axl.set_title("Downstream: DAE wins at both rates — barely")
    axl.legend(fontsize=8, loc="lower left")

    x = np.arange(len(rates))
    w = 0.36
    axr.bar(x - w / 2, rmse_dae, w, color=CATEGORICAL[0], label="DAE-reconstruction")
    axr.bar(x + w / 2, rmse_med, w, color=CATEGORICAL[5], label="median")
    for i in range(len(rates)):
        axr.text(x[i] - w / 2, rmse_dae[i] + 0.05, f"{rmse_dae[i]:.2f}", ha="center", fontsize=8)
        axr.text(x[i] + w / 2, rmse_med[i] + 0.05, f"{rmse_med[i]:.2f}", ha="center", fontsize=8)
    axr.set_xticks(x)
    axr.set_xticklabels([f"{r}% MCAR" for r in rates])
    axr.set_ylabel("numeric RMSE at masked cells (RankGauss space)")
    axr.set_title("Cell level: DAE imputes 3.4x better")
    axr.text(0.02, 0.97,
             "categorical accuracy at masked cells:\n"
             f"  DAE {acc_dae[0]:.1%} / {acc_dae[1]:.1%}   vs   mode {acc_med[0]:.1%} / {acc_med[1]:.1%}",
             transform=axr.transAxes, va="top", fontsize=8, color=CHROME["secondary_ink"])
    axr.legend(fontsize=8, loc="center right")

    fig.suptitle("DAE as imputer (E7): dominant on values, marginal on rank", y=1.0)
    return _save_fig(fig, _STUDY, "plot_imputer_gain")


def plot_anomaly_lift(aux: list[dict[str, str]], results: list[dict[str, str]]) -> Path:
    ks = ["5%", "10%", "20%"]
    lifts = [
        _aux(aux, "8", "anomaly_lift_at_5pct"),
        _aux(aux, "8", "val_lift_top10"),
        _aux(aux, "8", "anomaly_lift_at_20pct"),
    ]
    auc = _results_metric(results, "8")

    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    bars = ax.bar(ks, lifts, color=CATEGORICAL[0], width=0.55)
    for b, v in zip(bars, lifts):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.3f}", ha="center", fontsize=9)
    ax.axhline(1.0, color=CATEGORICAL[5], linestyle="--", linewidth=1.4,
               label="lift = 1.0 (no signal; the pre-registered bar)")
    ax.set_ylim(0, 1.25)
    ax.set_xlabel("top-k% of rows by DAE reconstruction error")
    ax.set_ylabel("lift over base claim rate")
    ax.set_title(f"Recon-error anomaly score (E8): an honest null\n"
                 f"ranker val_auc = {auc:.4f} — slightly inverted, prior falsified")
    ax.legend(fontsize=8)
    return _save_fig(fig, _STUDY, "plot_anomaly_lift")


def main() -> None:
    results = _read_tsv(_STUDY / "results.tsv")
    aux = _read_tsv(_STUDY / "aux_metrics.tsv")
    for path in (
        plot_when_it_pays(results),
        plot_noise_sensitivity(aux),
        plot_imputer_gain(aux),
        plot_anomaly_lift(aux, results),
    ):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
