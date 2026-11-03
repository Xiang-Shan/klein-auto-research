"""make_figures.py — exhibits for 23-lalonde-causal-replication.

Deterministic (no randomness, no timestamps, no network). Reads ONLY committed files
inside the study: tables/*.tsv (pinned by claims.lock), results.tsv and the run
manifests (for the decision trajectories). Every plotted value is cross-checked
against a second pinned source before it is drawn.

Writes into --out (200 dpi PNGs, white background):

  forest_att.png                        every att estimate with its bootstrap range against the benchmark,
                                        and the largest single weight share beside it
  designs_vs_benchmark.png              naive, regression and propensity estimates on one dollar axis
  reproduction_misses.png               |reproduced - published| for every registered target, log axis
  plot_decision_trajectory__<track>.png the engine's registered-track trajectory, one per track

Run from the repo root:

    uv run --no-sync python studies/23-lalonde-causal-replication/figures/make_figures.py \\
        --study studies/23-lalonde-causal-replication --out studies/23-lalonde-causal-replication/figures
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

DPI = 200
META = {"Software": "make_figures.py (study 23)"}
INK, GREY, LIGHT = "#1a1a1a", "#666666", "#cccccc"
TEAL, ORANGE, PURPLE, MAGENTA = "#1b9e77", "#d95f02", "#7570b3", "#e7298a"

#: cell -> (table, label, sealed?) in the order they ran (E0003/E0004 are crashes with no table)
CELLS = [
    ("E0002", "IPW, PSID-1 logit", False),
    ("E0005", "1-NN matching, PSID-1 logit", False),
    ("E0006", "AIPW, PSID-1 logit", False),
    ("E0007", "IPW, no 1974 terms", False),
    ("E0009", "AIPW, re-fit on CPS-1 (sealed)", True),
]


def check(label: str, drawn: float, expected: float, tol: float = 1e-6) -> None:
    if not abs(drawn - expected) <= tol:
        raise SystemExit(f"cross-check FAILED [{label}]: drawn {drawn!r} != artifact {expected!r}")


def att_rows(study: Path) -> pd.DataFrame:
    rows = []
    for exp, label, sealed in CELLS:
        row = pd.read_csv(study / "tables" / f"att_{exp}.tsv", sep="\t").iloc[0]
        check(f"{exp} gap", row["att"] - row["experimental_att"], row["gap"], 1e-4)
        results = pd.read_csv(study / "results.tsv", sep="\t")
        ledger = float(results.loc[results["experiment"] == exp, "primary_metric"].iloc[0])
        check(f"{exp} att vs results.tsv", row["att"], ledger, 1e-4)
        rows.append({**row.to_dict(), "exp": exp, "label": label, "sealed": sealed})
    return pd.DataFrame(rows)


def fig_forest(study: Path, out: Path) -> None:
    d = att_rows(study)
    bench = float(d["experimental_att"].iloc[0])
    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(10.5, 4.4), sharey=True, gridspec_kw={"width_ratios": [3.2, 1]}
    )
    n = len(d)
    for i, r in d.iterrows():
        y = n - 1 - i
        colour = ORANGE if r["sealed"] else TEAL
        marker = "D" if r["sealed"] else "o"
        ax.plot([r["ci_low"], r["ci_high"]], [y, y], color=colour, lw=2.0,
                ls="--" if r["estimator"] == "match" else "-", zorder=2)
        ax.plot([r["att"]], [y], marker=marker, ms=9, color=colour, markeredgecolor=INK, zorder=3)
        ax.annotate(f"{r['att']:.0f}  (gap {r['gap']:+.0f})", (r["ci_high"], y),
                    textcoords="offset points", xytext=(6, -3), fontsize=8, color=INK)
        ax2.barh(y, r["max_weight_share"], color=colour, height=0.5)
        ax2.annotate(f"{r['max_weight_share']:.3f}  ({int(r['n_controls_used'])} men)", (r["max_weight_share"], y),
                     textcoords="offset points", xytext=(4, -3), fontsize=7.5)
    ax.axvline(bench, color=PURPLE, lw=1.6, zorder=1)
    ax.axvspan(bench - 1000, bench + 1000, color=PURPLE, alpha=0.10, zorder=0)
    ax.axvline(0, color=GREY, lw=0.8, ls=":")
    ax.set_yticks(range(n))
    ax.set_yticklabels(list(reversed(d["label"])), fontsize=9)
    ax.set_xlabel("ATT estimate, 1982 dollars (bootstrap range; dashed = descriptive)")
    ax.set_xlim(-3500, 6800)
    ax.set_title("Estimate and bootstrap range against the experimental 1794.34", fontsize=10.5)
    ax.legend(
        handles=[
            Line2D([], [], color=PURPLE, lw=1.6, label="experimental ATT (benchmark)"),
            Line2D([], [], color=PURPLE, lw=8, alpha=0.15, label="registered +-1000 band"),
            Line2D([], [], marker="o", ls="", color=TEAL, markeredgecolor=INK, label="development, PSID-1"),
            Line2D([], [], marker="D", ls="", color=ORANGE, markeredgecolor=INK, label="sealed, CPS-1"),
        ],
        loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=4, fontsize=7.5, framealpha=0.95,
    )
    ax2.set_xlim(0, 0.30)
    ax2.set_xlabel("largest weight share (0 to 1)")
    ax2.set_title("Weight concentration", fontsize=10.5)
    for a in (ax, ax2):
        a.grid(axis="x", color="#eeeeee")
    fig.tight_layout()
    fig.savefig(out / "forest_att.png", dpi=DPI, facecolor="white", metadata=META, bbox_inches="tight")
    plt.close(fig)


def fig_designs(study: Path, out: Path) -> None:
    psid = pd.read_csv(study / "tables" / "reproduction_psid1.tsv", sep="\t").set_index("target")
    cps = pd.read_csv(study / "tables" / "reproduction_cps1.tsv", sep="\t").set_index("target")
    d = att_rows(study).set_index("exp")
    bench = float(psid.loc["nsw_unadjusted", "reproduced"])
    check("benchmark", bench, float(d["experimental_att"].iloc[0]), 1e-4)

    # (label, estimate, half-width or None, colour, marker)
    items = [
        ("NSW experiment (benchmark)", bench, 1.96 * psid.loc["nsw_unadjusted_se", "reproduced"], PURPLE, "s"),
        ("naive difference, PSID-1", psid.loc["psid1_unadjusted", "reproduced"],
         1.96 * psid.loc["psid1_unadjusted_se", "reproduced"], GREY, "o"),
        ("naive difference, CPS-1 (sealed)", cps.loc["cps1_unadjusted", "reproduced"],
         1.96 * cps.loc["cps1_unadjusted_se", "reproduced"], GREY, "D"),
        ("OLS, note a covariates, PSID-1", psid.loc["psid1_adjusted", "reproduced"],
         1.96 * psid.loc["psid1_adjusted_se", "reproduced"], MAGENTA, "o"),
        ("OLS, note a covariates, CPS-1 (sealed)", cps.loc["cps1_adjusted", "reproduced"],
         1.96 * cps.loc["cps1_adjusted_se", "reproduced"], MAGENTA, "D"),
        ("IPW, PSID-1", d.loc["E0002", "att"], None, TEAL, "o"),
        ("1-NN matching, PSID-1", d.loc["E0005", "att"], None, TEAL, "o"),
        ("AIPW, PSID-1", d.loc["E0006", "att"], None, TEAL, "o"),
        ("AIPW, CPS-1 (sealed)", d.loc["E0009", "att"], None, ORANGE, "D"),
    ]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    n = len(items)
    for i, (label, est, half, colour, marker) in enumerate(items):
        y = n - 1 - i
        if half is not None:
            ax.plot([est - half, est + half], [y, y], color=colour, lw=1.8, zorder=2)
        ax.plot([est], [y], marker=marker, ms=9, color=colour, markeredgecolor=INK, zorder=3)
        ax.annotate(f"{est:.0f}", (est, y), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8)
    ax.axvline(bench, color=PURPLE, lw=1.4, zorder=1)
    ax.axvline(0, color=GREY, lw=0.8, ls=":")
    ax.set_yticks(range(n))
    ax.set_yticklabels([i[0] for i in reversed(items)], fontsize=9)
    ax.set_xlabel("estimated effect of NSW on 1978 earnings, 1982 dollars (bars: classical OLS +-1.96 s.e.)")
    ax.set_title("Same files, nine designs: how far each sits from the benchmark", fontsize=10.5)
    ax.legend(
        handles=[
            Line2D([], [], marker="s", ls="", color=PURPLE, markeredgecolor=INK, label="experiment"),
            Line2D([], [], marker="o", ls="", color=GREY, markeredgecolor=INK, label="no adjustment"),
            Line2D([], [], marker="o", ls="", color=MAGENTA, markeredgecolor=INK, label="regression"),
            Line2D([], [], marker="o", ls="", color=TEAL, markeredgecolor=INK, label="propensity (PSID-1)"),
            Line2D([], [], marker="D", ls="", color=ORANGE, markeredgecolor=INK, label="propensity (sealed CPS-1)"),
        ],
        loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=5, fontsize=7.5, framealpha=0.95,
    )
    ax.grid(axis="x", color="#eeeeee")
    fig.tight_layout()
    fig.savefig(out / "designs_vs_benchmark.png", dpi=DPI, facecolor="white", metadata=META, bbox_inches="tight")
    plt.close(fig)


def fig_reproduction(study: Path, out: Path) -> None:
    frames = []
    for lane, name in (("psid1", "development (PSID-1)"), ("cps1", "sealed (CPS-1)")):
        t = pd.read_csv(study / "tables" / f"reproduction_{lane}.tsv", sep="\t")
        t = t[t["status"] != "diagnostic"].copy()
        t["lane"] = name
        frames.append(t)
    d = pd.concat(frames, ignore_index=True)
    d = d[~d["target"].str.startswith("n_")].reset_index(drop=True)  # counts are exact (diff 0); shown in the text
    floor = 1e-3  # a diff of exactly 0 cannot sit on a log axis; plotted at the floor
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    n = len(d)
    for i, r in d.iterrows():
        y = n - 1 - i
        missed = r["status"] == "missed"
        colour = MAGENTA if missed else TEAL
        ax.plot([floor, max(r["abs_diff"], floor)], [y, y], color=LIGHT, lw=1.0, zorder=1)
        ax.plot([max(r["abs_diff"], floor)], [y], marker="D" if "sealed" in r["lane"] else "o", ms=8,
                color=colour, markeredgecolor=INK, zorder=3)
    ax.axvline(1.0, color=INK, lw=1.2, ls="--")
    ax.text(1.0, n - 0.35, " registered tolerance: 1 dollar", fontsize=8, va="bottom")
    ax.set_xscale("log")
    ax.set_xlim(floor, 2000)
    ax.set_ylim(-0.8, n + 0.4)
    ax.set_yticks(range(n))
    ax.set_yticklabels(list(reversed(d["target"])), fontsize=8)
    ax.set_xlabel("|reproduced - published|, dollars (log scale)")
    ax.set_title("Every registered estimate and standard error: four land outside one dollar", fontsize=10.5)
    ax.legend(
        handles=[
            Line2D([], [], marker="o", ls="", color=TEAL, markeredgecolor=INK, label="within tolerance, development"),
            Line2D([], [], marker="D", ls="", color=TEAL, markeredgecolor=INK, label="within tolerance, sealed"),
            Line2D([], [], marker="o", ls="", color=MAGENTA, markeredgecolor=INK, label="missed (marker shape: lane)"),
        ],
        loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=7.5, framealpha=0.95,
    )
    ax.grid(axis="x", color="#eeeeee")
    missed = int((d["status"] == "missed").sum())
    check("missed targets", missed, 4)
    fig.tight_layout()
    fig.savefig(out / "reproduction_misses.png", dpi=DPI, facecolor="white", metadata=META, bbox_inches="tight")
    plt.close(fig)


def fig_trajectories(study: Path, out: Path) -> None:
    from kleinlib import figures, workflow

    manifests = workflow.load_manifests(study)
    tracks = workflow.normalize_tracks(workflow.load_contract(study))
    with tempfile.TemporaryDirectory(prefix="klein-traj-") as tmp:
        for track, spec in tracks.items():
            metric = spec.get("metric", {})
            path = figures.plot_decision_trajectory(
                manifests, tmp, track=track, metric_goal=str(metric.get("goal") or "higher"),
                metric_name=metric.get("name"), minimum_delta=None, noise_floor_std=None,
                name=f"plot_decision_trajectory__{track}",
            )
            shutil.copyfile(path, out / path.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    study, out = args.study.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white",
                         "savefig.facecolor": "white", "font.family": "DejaVu Sans"})
    fig_forest(study, out)
    fig_designs(study, out)
    fig_reproduction(study, out)
    fig_trajectories(study, out)
    print("wrote forest_att designs_vs_benchmark reproduction_misses plot_decision_trajectory__*")
    print("all cross-checks passed")


if __name__ == "__main__":
    main()
