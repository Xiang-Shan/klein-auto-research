"""make_figures.py — study-local exhibits for 22-cnn-data-scaling.

Deterministic (no randomness, no timestamps, no network) and read-only on the study:
every plotted number comes from a committed pinned artifact, never from a re-run.

  tables/cell_E000[1-6]_s[0-2].tsv   per-seed development cells (scored on the development lane)
  tables/scaling_fit.tsv             the pinned law (E0007): a, alpha, per-N fitted loss
  tables/sealed_E0008_s[0-2].tsv     the sealed full-pool cell (scored on the official t10k test set)
  runs/E####/manifest.json           track, disposition, evaluation kind, printed block (steps, best_step)
  study.yaml                         the registered ranges of P1 and P5

PNGs written into --out (200 dpi, white background):

  scaling_loglog.png                  the six development cells, the fitted power law and the sealed point
  decision_trajectory__primary.png    the primary track run by run, sealed cell separate
  decision_trajectory__exponent.png   the exponent track (one registered cell) against P1 and P5
  per_seed_curves.png                 each seed's own loss curve (nested subsamples): the N=1000 inversion
  step_budget.png                     optimizer steps and best-checkpoint step against N

Run from the repo root:

    uv run --no-sync python studies/22-cnn-data-scaling/figures/make_figures.py \\
        --study studies/22-cnn-data-scaling --out studies/22-cnn-data-scaling/figures
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

DPI = 200
CELL_RUNS = [f"E000{i}" for i in range(1, 7)]
FIT_RUN = "E0007"
SEALED_RUN = "E0008"
INK, GREY, ACCENT, ALERT = "#1a1a1a", "#7a7a7a", "#1f5fa8", "#b5481a"

plt.rcParams.update(
    {
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
    }
)


def save(fig, out: Path, name: str) -> None:
    fig.savefig(out / name, dpi=DPI, metadata={"Software": None})
    plt.close(fig)


def read_cells(study: Path) -> pd.DataFrame:
    frames = [pd.read_csv(p, sep="\t") for p in sorted((study / "tables").glob("cell_E000[1-6]_s[0-2].tsv"))]
    return pd.concat(frames, ignore_index=True)


def read_sealed(study: Path) -> pd.DataFrame:
    frames = [pd.read_csv(p, sep="\t") for p in sorted((study / "tables").glob("sealed_E0008_s[0-2].tsv"))]
    return pd.concat(frames, ignore_index=True)


def read_manifest(study: Path, run: str) -> dict:
    return json.loads((study / "runs" / run / "manifest.json").read_text(encoding="utf-8"))


def scaling_loglog(study: Path, out: Path) -> None:
    cells, sealed = read_cells(study), read_sealed(study)
    fit = pd.read_csv(study / "tables" / "scaling_fit.tsv", sep="\t")
    a, alpha = float(fit["a"].iloc[0]), float(fit["alpha"].iloc[0])
    n_full = int(sealed["n_train"].iloc[0])
    predicted = float(sealed["predicted_loss"].iloc[0])
    means = cells.groupby("n_train")["val_mlogloss"].mean()

    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    n_in = np.geomspace(500, 16000, 50)
    n_out = np.geomspace(16000, n_full, 50)
    ax.plot(n_in, a * n_in ** (-alpha), color=ACCENT, lw=2, label="pinned power law, fitted range (E0007)")
    ax.plot(n_out, a * n_out ** (-alpha), color=ACCENT, lw=2, ls="--", label="same law, extrapolated")
    ax.scatter(cells["n_train"], cells["val_mlogloss"], s=22, facecolors="none", edgecolors=GREY,
               label="development cells, one seed each (E0001-E0006)")
    ax.plot(means.index, means.values, "s", color=INK, ms=7, label="development cells, seed mean")
    ax.scatter(sealed["n_train"], sealed["val_mlogloss"], s=26, facecolors="none", edgecolors=ALERT,
               label="sealed cell, one seed each (E0008, test set)")
    ax.plot([n_full], [sealed["val_mlogloss"].mean()], "*", color=ALERT, ms=15, mec=INK,
            label="sealed cell, seed mean (measured)")
    ax.plot([n_full], [predicted], "D", color=ACCENT, ms=8, mec=INK, label="law's prediction at N = 59,992")
    ax.annotate("", xy=(n_full, sealed["val_mlogloss"].mean()), xytext=(n_full, predicted),
                arrowprops={"arrowstyle": "->", "color": INK, "lw": 1})
    ax.axvline(16000, color=GREY, ls=":", lw=1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Training-set size N (images, log scale)")
    ax.set_ylabel("Cross-entropy (nats per image, log scale)")
    ax.set_yticks([0.4, 0.5, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.4", "0.5", "0.6", "0.8", "1.0"])
    ax.minorticks_off()
    ax.set_title("Six development cells, the pinned law, and the sealed point", fontsize=11)
    ax.legend(fontsize=7.5, loc="lower left", frameon=False)
    fig.tight_layout()
    save(fig, out, "scaling_loglog.png")


def decision_trajectory_primary(study: Path, out: Path) -> None:
    cells, sealed = read_cells(study), read_sealed(study)
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    runs = CELL_RUNS + [SEALED_RUN]
    pos = {r: i for i, r in enumerate(runs)}
    for r in CELL_RUNS:
        sub = cells[cells["run"] == r]
        m = read_manifest(study, r)
        ax.vlines(pos[r], sub["val_mlogloss"].min(), sub["val_mlogloss"].max(), color=GREY, lw=2)
        ax.plot(pos[r], sub["val_mlogloss"].mean(), "o", color=ACCENT, ms=8, mec=INK)
        ax.annotate(f"N={int(sub['n_train'].iloc[0]):,}", (pos[r], sub["val_mlogloss"].max()),
                    textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
        assert m["disposition"] == "measured"
    ax.vlines(pos[SEALED_RUN], sealed["val_mlogloss"].min(), sealed["val_mlogloss"].max(), color=GREY, lw=2)
    ax.plot(pos[SEALED_RUN], sealed["val_mlogloss"].mean(), "*", color=ALERT, ms=16, mec=INK)
    ax.annotate("N=59,992", (pos[SEALED_RUN], sealed["val_mlogloss"].max()),
                textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
    ax.axvspan(-0.5, 5.5, color=ACCENT, alpha=0.06)
    ax.axvspan(5.5, 6.5, color=ALERT, alpha=0.08)
    ax.text(2.5, 0.28, "phase cells: development lane", ha="center", fontsize=8, color=GREY)
    ax.text(6, 0.28, "confirmation:\nsealed, test set", ha="center", fontsize=8, color=GREY)
    ax.set_xticks(range(len(runs)))
    ax.set_xticklabels(runs, fontsize=8)
    ax.set_ylim(0.25, 1.15)
    ax.set_xlabel("Primary-track run (experiment ordinal; each run is one 3-seed cell)")
    ax.set_ylabel("val_mlogloss (nats per image, linear scale)")
    ax.set_title("Primary track: registered cells, no keeps or discards", fontsize=11)
    ax.legend(
        handles=[
            Line2D([], [], marker="o", color=ACCENT, mfc=ACCENT, mec=INK, ls="", ms=8, label="measured cell, seed mean"),
            Line2D([], [], color=GREY, lw=2, label="seed min to max"),
            Line2D([], [], marker="*", color=ALERT, mec=INK, ls="", ms=14, label="sealed cell, seed mean (test set)"),
        ],
        fontsize=8, loc="upper right", frameon=False,
    )
    fig.tight_layout()
    save(fig, out, "decision_trajectory__primary.png")


def decision_trajectory_exponent(study: Path, out: Path) -> None:
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    rules = {p["id"]: p["rule"]["value"] for p in contract["predictions"]}
    m = read_manifest(study, FIT_RUN)
    fit = pd.read_csv(study / "tables" / "scaling_fit.tsv", sep="\t")
    alpha = float(m["primary_metric"])
    lo, hi = float(fit["alpha_ci_low"].iloc[0]), float(fit["alpha_ci_high"].iloc[0])
    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    ax.axhspan(*rules["P1"], color=ACCENT, alpha=0.10, label="P1 range (registered at CONSULT)")
    ax.axhspan(*rules["P5"], facecolor="none", edgecolor=ACCENT, hatch="//", alpha=0.5, lw=0,
               label="P5 range (registered at METHOD)")
    ax.errorbar([0], [alpha], yerr=[[alpha - lo], [hi - alpha]], fmt="o", color=INK, ms=7, capsize=6, lw=1.5,
                label="fitted alpha, E0007, with printed bootstrap spread (descriptive)")
    ax.set_xlim(-1, 1)
    ax.set_ylim(0, 0.65)
    ax.set_xticks([0])
    ax.set_xticklabels([FIT_RUN + " (exponent track, one registered cell)"])
    ax.set_xlabel("")
    ax.set_ylabel("scaling_exponent alpha (dimensionless, linear scale)")
    ax.set_title("Exponent track: inside P1, below P5", fontsize=11)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=1, frameon=False)
    fig.tight_layout()
    save(fig, out, "decision_trajectory__exponent.png")


def per_seed_curves(study: Path, out: Path) -> None:
    cells = read_cells(study)
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    styles = {0: ("-", "o"), 1: ("--", "s"), 2: (":", "^")}
    for seed, (ls, mk) in styles.items():
        sub = cells[cells["seed"] == seed].sort_values("n_train")
        ax.plot(sub["n_train"], sub["val_mlogloss"], ls=ls, marker=mk, color=INK, ms=6, lw=1.5, label=f"seed {seed}")
    ax.axvspan(450, 1100, color=ALERT, alpha=0.08)
    ax.text(700, 0.56, "N=500 to 1,000:\nloss rises in\nall three seeds", ha="center", fontsize=8, color=ALERT)
    ax.set_xscale("log")
    ax.set_ylim(0.5, 1.08)
    ax.set_xlabel("Training-set size N (images, log scale)")
    ax.set_ylabel("val_mlogloss, development lane (nats per image, linear scale)")
    ax.set_title("Each seed's own curve (nested subsamples within a seed)", fontsize=11)
    ax.minorticks_off()
    ax.set_xticks([500, 1000, 2000, 4000, 8000, 16000])
    ax.set_xticklabels(["500", "1,000", "2,000", "4,000", "8,000", "16,000"])
    ax.legend(fontsize=8, loc="upper right", frameon=False)
    fig.tight_layout()
    save(fig, out, "per_seed_curves.png")


def step_budget(study: Path, out: Path) -> None:
    rows = []
    for r in CELL_RUNS + [SEALED_RUN]:
        m = read_manifest(study, r)["metrics"]
        rows.append((m["n_train"], m["steps"], m["best_step"], r == SEALED_RUN))
    df = pd.DataFrame(rows, columns=["n", "steps", "best", "sealed"])
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(df["n"], df["steps"], "-", color=INK, lw=1.5, marker="o", ms=6, label="step budget of the cell")
    ax.plot(df["n"], df["best"], "--", color=ACCENT, lw=1.5, marker="s", ms=6,
            label="best inner-validation checkpoint (seed mean)")
    ax.axhline(400, color=GREY, ls=":", lw=1)
    ax.text(2300, 352, "400-step floor shared by N = 500, 1,000, 2,000", fontsize=8, color=GREY)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Training-set size N (images, log scale)")
    ax.set_ylabel("Optimizer steps (count, log scale)")
    ax.set_title("The best checkpoint sits at the end of every budget", fontsize=11)
    ax.minorticks_off()
    ax.set_xticks([500, 1000, 2000, 4000, 8000, 16000, 59992])
    ax.set_xticklabels(["500", "1,000", "2,000", "4,000", "8,000", "16,000", "59,992"], fontsize=8)
    ax.legend(fontsize=8, loc="upper left", frameon=False)
    fig.tight_layout()
    save(fig, out, "step_budget.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--study", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    study, out = args.study.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    scaling_loglog(study, out)
    decision_trajectory_primary(study, out)
    decision_trajectory_exponent(study, out)
    per_seed_curves(study, out)
    step_budget(study, out)


if __name__ == "__main__":
    main()
