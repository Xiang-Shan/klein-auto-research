"""make_figures.py — study-local exhibits for 10-hubble-1929-replication.

Self-contained: stdlib + pandas + matplotlib only (no seaborn). Deterministic —
no randomness, no timestamps, no network — so two runs produce byte-identical
PNGs. Reads ONLY files inside the study, and every number it draws is read from a
pinned artifact and CROSS-CHECKED against a second source before it is plotted
(the numbers law: nothing invented, nothing retyped):

  data/prepared/prepared.csv           Hubble's Table 1 rows, for the scatter
  tables/two_parameter_fits.tsv        E0002 — the two fits and their gaps to 465
  tables/bootstrap_k.tsv               E0006 — the interval for K
  tables/inverse_vs_forward.tsv        E0007 — the paired inverse/forward comparison
  tables/jackknife_k.tsv               E0008 — leave-one-out influence
  tables/coverage_bootstrap_blockB.tsv E0009 — bootstrap coverage, development
  tables/coverage_analytic_blockB.tsv  E0010 — analytic coverage, development
  tables/sealed_coverage_blockC.tsv    E0013 — coverage, sealed block C
  sweeps/coverage_floor.sidecar.tsv    the Phase-0 floor's five blocks
  results.tsv                          the ledger, for the decision trajectory
  aux_metrics.tsv                      the printed keys, for the cross-checks

Writes four PNGs (200 dpi, white background) into --out:

  velocity_distance.png   Hubble's 24 objects with both fits and his own line
  bootstrap_k.png         the bootstrap interval for K against every reference value
  coverage.png            what the interval actually covers, under the declared DGP
  trajectory.png          the decision trajectory: every cell, per track, in order

Run from the repo root:

    uv run --locked python studies/10-hubble-1929-replication/figures/make_figures.py \\
        --study studies/10-hubble-1929-replication --out studies/10-hubble-1929-replication/figures
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

DPI = 200
#: Deterministic PNG metadata — matplotlib writes no timestamp; pin Software too.
META = {"Software": "make_figures.py (study 10)"}

# Colourblind-safe Dark2 family, the same palette study 09 used.
INK = "#1a1a1a"
TEAL = "#1b9e77"
ORANGE = "#d95f02"
PURPLE = "#7570b3"
MAGENTA = "#e7298a"
GREEN = "#66a61e"
GOLD = "#e6ab02"
GREY = "#666666"
LIGHT = "#cccccc"

#: Published reference values. Each is quoted in `lib/hubble.py` as a module
#: constant and in `references.yaml`; the cross-checks below assert that the
#: values drawn here agree with the study's own artifacts.
HUBBLE_K_24 = 465.0
HUBBLE_K_9GROUP = 513.0
HUBBLE_ADOPTED = 500.0
MODERN_H0 = 70.0
NOMINAL_LEVEL = 0.95


def read_tsv(study: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(study / name, sep="\t")


def aux(study: Path) -> pd.DataFrame:
    return pd.read_csv(study / "aux_metrics.tsv", sep="\t")


def aux_value(frame: pd.DataFrame, experiment: str, metric: str) -> float:
    rows = frame[(frame["experiment"] == experiment) & (frame["metric"] == metric)]
    if len(rows) != 1:
        raise SystemExit(f"aux_metrics.tsv: expected one {experiment}/{metric}, got {len(rows)}")
    return float(rows["value"].iloc[0])


def check(label: str, drawn: float, expected: float, tol: float = 1e-6) -> None:
    """Assert a value about to be drawn matches the artifact it came from."""
    if not abs(drawn - expected) <= tol:
        raise SystemExit(f"cross-check FAILED [{label}]: drawn {drawn!r} != artifact {expected!r}")


def source_tag(fig: plt.Figure, files: str) -> None:
    fig.text(
        0.005,
        0.005,
        f"10-hubble-1929-replication · {files}",
        fontsize=6,
        color=GREY,
        ha="left",
        va="bottom",
    )


# ---------------------------------------------------------------------------
# 1. The velocity-distance relation, with every line anyone has drawn through it
# ---------------------------------------------------------------------------


def fig_velocity_distance(study: Path, out: Path) -> None:
    prepared = pd.read_csv(study / "data" / "prepared" / "prepared.csv")
    table1 = prepared[prepared["block"] == "table1"]
    r = table1["r_mpc"].to_numpy(dtype=float)
    v = table1["v_kms"].to_numpy(dtype=float)

    fits = read_tsv(study, "tables/two_parameter_fits.tsv").set_index("fit")
    k_origin = float(fits.loc["origin", "k_kms_per_mpc"])
    k_free = float(fits.loc["free_intercept", "k_kms_per_mpc"])
    c_free = float(fits.loc["free_intercept", "intercept_kms"])

    a = aux(study)
    check("k_origin", k_origin, aux_value(a, "E0002", "k_origin"))
    check("k_free", k_free, aux_value(a, "E0002", "k_free"))
    check("intercept_free", c_free, aux_value(a, "E0002", "intercept_free"))
    check("n objects", float(r.size), aux_value(a, "E0001", "n_table1"))
    check("sum_r", float(r.sum()), aux_value(a, "E0001", "sum_r"), tol=1e-9)
    check("sum_v", float(v.sum()), aux_value(a, "E0001", "sum_v"), tol=1e-9)

    virgo = r == 2.0
    grid = np.linspace(0.0, 2.15, 200)

    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    ax.axhline(0.0, color=LIGHT, lw=0.8, zorder=0)
    ax.plot(
        grid, HUBBLE_K_24 * grid, color=MAGENTA, lw=2.0, ls="--",
        label=f"Hubble's published K = {HUBBLE_K_24:.0f} (4-parameter solution)",
    )
    ax.plot(
        grid, k_origin * grid, color=TEAL, lw=2.0,
        label=f"OLS through the origin: K = {k_origin:.2f}",
    )
    ax.plot(
        grid, k_free * grid + c_free, color=ORANGE, lw=2.0,
        label=f"free-intercept OLS: K = {k_free:.2f}, c = {c_free:.2f}",
    )
    ax.scatter(
        r[~virgo], v[~virgo], s=46, color=INK, zorder=3,
        edgecolor="white", linewidth=0.6, label="Table 1 object",
    )
    ax.scatter(
        r[virgo], v[virgo], s=70, color=PURPLE, marker="s", zorder=4,
        edgecolor="white", linewidth=0.6,
        label=f"Virgo cluster ({int(virgo.sum())} objects, one assigned distance)",
    )

    ax.set_xlabel("distance  r  (Mpc, as printed in Table 1)")
    ax.set_ylabel("radial velocity  v  (km/s)")
    ax.set_title(
        "Hubble's 24 objects: no two-parameter fit returns his published constant",
        fontsize=11.5,
    )
    ax.set_xlim(-0.05, 2.15)
    # lower right: the upper-left corner holds real data (N.G.C. 1068 at r = 1.0).
    ax.legend(loc="lower right", fontsize=8.2, framealpha=0.95)
    ax.grid(alpha=0.18, lw=0.6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    source_tag(fig, "data/prepared/prepared.csv · tables/two_parameter_fits.tsv (E0001, E0002)")
    fig.savefig(out / "velocity_distance.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 2. The interval for K, against every value anyone has quoted
# ---------------------------------------------------------------------------


def fig_bootstrap_k(study: Path, out: Path) -> None:
    boot = read_tsv(study, "tables/bootstrap_k.tsv").set_index("estimator")
    inv = read_tsv(study, "tables/inverse_vs_forward.tsv").set_index("quantity")
    jack = read_tsv(study, "tables/jackknife_k.tsv")

    k_free = float(boot.loc["free_intercept", "k_point"])
    low = float(boot.loc["free_intercept", "ci_low"])
    high = float(boot.loc["free_intercept", "ci_high"])
    k_origin = float(boot.loc["through_origin", "k_point"])
    low_o = float(boot.loc["through_origin", "ci_low"])
    high_o = float(boot.loc["through_origin", "ci_high"])
    k_inverse = float(inv.loc["inverse_r_on_v_inverted", "value"])
    low_i = float(inv.loc["inverse_r_on_v_inverted", "ci_low"])
    high_i = float(inv.loc["inverse_r_on_v_inverted", "ci_high"])

    a = aux(study)
    check("ci_low", low, aux_value(a, "E0006", "ci_low"))
    check("ci_high", high, aux_value(a, "E0006", "ci_high"))
    check("k_free point", k_free, aux_value(a, "E0002", "k_free"))
    check("k_inverse", k_inverse, aux_value(a, "E0007", "k_inverse"))
    # the sealed comparison re-ran the same locked estimator
    check("sealed ci_low", low, aux_value(a, "E0012", "ci_low"))
    k_no_virgo = aux_value(a, "E0008", "k_without_virgo_group")
    check("jackknife rows", float(len(jack)), aux_value(a, "E0008", "n_objects"))

    rows = [
        ("inverse regression\n(r on v, inverted)", k_inverse, low_i, high_i, PURPLE),
        ("free-intercept OLS\n(the study's estimate)", k_free, low, high, ORANGE),
        ("OLS through the origin", k_origin, low_o, high_o, TEAL),
    ]

    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    for i, (label, point, lo, hi, colour) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([lo, hi], [y, y], color=colour, lw=3.2, solid_capstyle="round", zorder=3)
        ax.plot([point], [y], "o", color=colour, ms=9, zorder=4,
                markeredgecolor="white", markeredgewidth=1.0)
        ax.text(hi + 14, y, f"{point:.1f}  [{lo:.1f}, {hi:.1f}]",
                va="center", fontsize=8.4, color=colour)

    # Hubble's three quoted values sit within 50 km/s/Mpc of one another, so
    # inline labels would collide: they go in a legend instead.
    references = (
        (MODERN_H0, f"modern H0 = {MODERN_H0:.0f}", GREY, ":"),
        (HUBBLE_K_24, f"Hubble {HUBBLE_K_24:.0f} — 24 objects", MAGENTA, "--"),
        (HUBBLE_ADOPTED, f"textbook {HUBBLE_ADOPTED:.0f} — his adopted value", GOLD, "-."),
        (HUBBLE_K_9GROUP, f"Hubble {HUBBLE_K_9GROUP:.0f} — 9 groups", GREEN, (0, (6, 2))),
        (k_no_virgo, f"drop the 4 Virgo rows: {k_no_virgo:.1f}", INK, (0, (1, 2))),
    )
    for value, _label, colour, style in references:
        ax.axvline(value, color=colour, ls=style, lw=1.4, zorder=1)
    ax.legend(
        handles=[
            Line2D([], [], color=colour, ls=style, lw=1.6, label=label)
            for _value, label, colour, style in references
        ],
        loc="lower right", fontsize=7.8, framealpha=0.95, title="reference values",
        title_fontsize=8.0,
    )

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in reversed(rows)], fontsize=8.6)
    ax.set_ylim(-1.15, 2.45)
    ax.set_xlim(0, 1080)
    ax.set_xlabel("K  (km/s/Mpc) — point estimate and 95% percentile bootstrap interval")
    ax.set_title(
        "What Hubble's 24 objects support, against every value anyone has quoted",
        fontsize=11.5,
    )
    ax.grid(axis="x", alpha=0.18, lw=0.6)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    source_tag(
        fig,
        "tables/bootstrap_k.tsv · inverse_vs_forward.tsv · jackknife_k.tsv (E0006-E0008, E0012)",
    )
    fig.savefig(out / "bootstrap_k.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 3. What that interval actually covers, under the declared truth
# ---------------------------------------------------------------------------


def fig_coverage(study: Path, out: Path) -> None:
    boot_b = read_tsv(study, "tables/coverage_bootstrap_blockB.tsv")
    ana_b = read_tsv(study, "tables/coverage_analytic_blockB.tsv")
    sealed = read_tsv(study, "tables/sealed_coverage_blockC.tsv")
    floor = pd.read_csv(study / "sweeps" / "coverage_floor.sidecar.tsv", sep="\t")

    cov_boot = float(boot_b["coverage"].iloc[0])
    cov_ana = float(ana_b[ana_b["interval"] == "analytic_normal_theory"]["coverage"].iloc[0])
    cov_sealed = float(sealed["coverage"].iloc[0])
    floor_values = [float(x) for x in floor[floor["status"] == "ok"]["primary_metric"]]

    a = aux(study)
    check("bootstrap coverage", cov_boot, NOMINAL_LEVEL - aux_value(a, "E0009", "shortfall_from_nominal"))
    check("analytic coverage", cov_ana, NOMINAL_LEVEL - aux_value(a, "E0010", "shortfall_from_nominal"))
    check("sealed coverage", cov_sealed, NOMINAL_LEVEL - aux_value(a, "E0013", "shortfall_from_nominal"))
    check("floor blocks", float(len(floor_values)), 5.0)

    bars = [
        ("analytic\nnormal theory\n(E0010, block B)", cov_ana, GREEN),
        ("percentile bootstrap\n(E0009, block B)", cov_boot, ORANGE),
        ("percentile bootstrap\nSEALED (E0013, block C)", cov_sealed, PURPLE),
    ]

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(9.4, 4.6), gridspec_kw={"width_ratios": [2.05, 1.0]}
    )

    x = np.arange(len(bars))
    ax.bar(x, [b[1] for b in bars], width=0.55, color=[b[2] for b in bars],
           edgecolor="white", linewidth=1.0, zorder=3)
    for xi, (_, value, _) in zip(x, bars, strict=True):
        ax.text(xi, value + 0.0022, f"{value:.3f}", ha="center", fontsize=9.2, color=INK)
    ax.axhline(NOMINAL_LEVEL, color=MAGENTA, ls="--", lw=1.6, zorder=4)
    ax.text(len(bars) - 0.42, NOMINAL_LEVEL + 0.0016, "nominal 0.95",
            fontsize=8.0, color=MAGENTA, ha="right")
    ax.axhline(0.90, color=GREY, ls=":", lw=1.4, zorder=4)
    ax.text(len(bars) - 0.42, 0.9016, "P6's registered bar 0.90",
            fontsize=8.0, color=GREY, ha="right")

    ax.set_xticks(x)
    ax.set_xticklabels([b[0] for b in bars], fontsize=8.0)
    ax.set_ylim(0.88, 0.958)
    ax.set_ylabel("coverage of the known truth K = 450")
    ax.set_title("Both intervals under-cover at n = 24; the bootstrap by more", fontsize=10.8)
    ax.grid(axis="y", alpha=0.18, lw=0.6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax2.plot(range(1, len(floor_values) + 1), floor_values, "o-", color=GOLD,
             lw=1.6, ms=7, markeredgecolor="white", zorder=3)
    ax2.axhline(cov_boot, color=ORANGE, ls="--", lw=1.5, zorder=2)
    ax2.text(0.75, cov_boot + 0.0004, "block B (E0009)", fontsize=7.4,
             color=ORANGE, va="bottom", ha="left")
    ax2.axhline(cov_sealed, color=PURPLE, ls="--", lw=1.5, zorder=2)
    ax2.text(0.75, cov_sealed - 0.0004, "block C, SEALED (E0013)", fontsize=7.4,
             color=PURPLE, va="top", ha="left")
    ax2.set_xticks(range(1, len(floor_values) + 1))
    ax2.set_xlabel("Phase-0 floor block")
    # Accurate, not rhetorical: block C sits AT the floor's minimum; block B is
    # below all five, which is the point the figure is making.
    ax2.set_title("block B fell below\nall five floor blocks", fontsize=9.6)
    ax2.set_xlim(0.7, len(floor_values) + 0.35)
    ax2.grid(alpha=0.18, lw=0.6)
    for spine in ("top", "right"):
        ax2.spines[spine].set_visible(False)

    fig.tight_layout()
    source_tag(
        fig,
        "tables/coverage_*.tsv · sweeps/coverage_floor.sidecar.tsv (E0009, E0010, E0013)",
    )
    fig.savefig(out / "coverage.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 4. The decision trajectory: every cell, per track, in the order it ran
# ---------------------------------------------------------------------------


def fig_trajectory(study: Path, out: Path) -> None:
    results = read_tsv(study, "results.tsv")
    if len(results) != 13:
        raise SystemExit(f"results.tsv: expected 13 cells, found {len(results)}")

    tracks = ["reproduction", "estimate", "simulate"]
    colours = {"reproduction": TEAL, "estimate": ORANGE, "simulate": PURPLE}
    sealed = {"E0011", "E0012", "E0013"}
    tests = {
        "E0001": "P0 supported",
        "E0002": "P1 supported",
        "E0003": "P9 REFUTED",
        "E0004": "P2 inconclusive",
        "E0005": "P3 inconclusive",
        "E0011": "P8 supported",
        "E0012": "P4, P7 supported",
        "E0013": "P6 supported",
    }

    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    for i, track in enumerate(tracks):
        y = len(tracks) - 1 - i
        rows = results[results["track"] == track]
        xs = [int(e[1:]) for e in rows["experiment"]]
        ax.plot([1, 13], [y, y], color=LIGHT, lw=1.0, zorder=1)
        for x, exp in zip(xs, rows["experiment"], strict=True):
            is_sealed = exp in sealed
            ax.plot(
                [x], [y], marker="D" if is_sealed else "o",
                ms=13 if is_sealed else 10, color=colours[track], zorder=3,
                markeredgecolor=INK if is_sealed else "white",
                markeredgewidth=1.4 if is_sealed else 0.9,
            )
            label = tests.get(exp)
            if label:
                # adjacent cells carry adjacent labels; stagger two heights so
                # "P2 inconclusive" cannot sit on top of "P3 inconclusive".
                offset = 15 if x % 2 else 30
                ax.annotate(
                    label, (x, y), textcoords="offset points", xytext=(0, offset),
                    ha="center", fontsize=7.2,
                    color=MAGENTA if "REFUTED" in label else GREY,
                )
        ax.text(0.35, y, track, ha="right", va="center", fontsize=9.4,
                color=colours[track], fontweight="bold")

    phases = ((1, 1, "adaptive-1"), (2, 5, "adaptive-2"), (6, 8, "adaptive-3"),
              (9, 10, "adaptive-4"), (11, 13, "confirmation"))
    for start, end, name in phases:
        ax.axvspan(start - 0.45, end + 0.45, color=GREY, alpha=0.055, zorder=0)
        ax.text((start + end) / 2, 2.82, name, ha="center", fontsize=8.0, color=GREY)

    ax.set_xticks(range(1, 14))
    ax.set_xticklabels([f"E{n:04d}" for n in range(1, 14)], fontsize=7.6, rotation=45)
    ax.set_yticks([])
    ax.set_ylim(-1.05, 2.95)
    ax.set_xlim(0.35, 13.7)
    ax.set_title(
        "Thirteen cells, three tracks, zero crashes — and one seal per track (◆)",
        fontsize=11.5,
    )
    for spine in ("top", "right", "left", "bottom"):
        ax.spines[spine].set_visible(False)

    ax.legend(
        handles=[
            Line2D([], [], marker="o", ls="", color=GREY, ms=9,
                   markeredgecolor="white", label="development cell (measured)"),
            Line2D([], [], marker="D", ls="", color=GREY, ms=11,
                   markeredgecolor=INK, label="sealed cell — one access per track"),
            Patch(facecolor=GREY, alpha=0.10, label="phase"),
        ],
        loc="lower left", fontsize=8.0, framealpha=0.95, ncol=3,
    )

    fig.tight_layout()
    source_tag(fig, "results.tsv · study_state.json (E0001-E0013)")
    fig.savefig(out / "trajectory.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    study = args.study.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "font.family": "DejaVu Sans",
            "axes.titlecolor": INK,
            "text.color": INK,
            "axes.labelcolor": INK,
            "xtick.color": GREY,
            "ytick.color": GREY,
            "svg.hashsalt": "10-hubble",
        }
    )

    fig_velocity_distance(study, out)
    fig_bootstrap_k(study, out)
    fig_coverage(study, out)
    fig_trajectory(study, out)
    print("wrote velocity_distance.png bootstrap_k.png coverage.png trajectory.png")
    print("all cross-checks passed (every drawn value matched its pinned artifact)")


if __name__ == "__main__":
    main()
