"""Deck-grade synthesis figures for study 05 — the three exhibits findings.md argues.

Run from the study directory:  uv run --no-sync python figures_extra.py

Produces, at 200 DPI, into ``figures/``:

- ``gap_waterfall.png``   the study's central artifact: where the GLM->GBDT gap goes,
                          and the ~83% non-additive residue that no additive shaping
                          or raw-product interaction reached.
- ``data_volume_curve.png`` RQ6: the gap as a function of training-set size, with the
                          20-41k-row crossover below which the GLM WINS.
- ``sealed_gap.png``      RQ1: the development gap and the sealed gap side by side with
                          2-SE whiskers — the replication that closes study 04's caveat.

Every number below is quoted from the committed ledgers (``results.tsv``,
``aux_metrics.tsv``, ``sweeps/data_volume.sidecar.tsv``, ``study.yaml``); the data-volume
curve is read from its sidecar at runtime rather than transcribed. Nothing here writes
ledger state.

Palette and chrome come from ``kleinlib.figures`` (the validated colorblind-safe
instance); only the DPI is raised for deck use.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

from kleinlib.figures import CATEGORICAL, CHROME, _apply_style  # noqa: E402

STUDY = Path(__file__).resolve().parent
FIGDIR = STUDY / "figures"
DPI = 200

# ---------------------------------------------------------------------------
# Ledger constants (results.tsv / aux_metrics.tsv / study.yaml — never re-derived)
# ---------------------------------------------------------------------------
GLM_ANCHOR = 0.45486081689395963     # E0002  glm_ohe            (anchor-exact vs study 04)
GLM_SPLINES = 0.4531562744675676     # E0004  glm_scoped_splines (KEEP, 3.2x glm floor)
GLM_PRODUCTS = 0.4529125938096384    # E0008  glm_interactions, 2 pairs (DISCARD, 0.45x)
GBDT_INCUMBENT = 0.4446891634048745  # E0003  hgbt_ohe           (anchor-exact vs study 04)

SEALED_GLM = 0.4592308087178836      # E0011  sealed final test, glm incumbent
SEALED_GBDT = 0.44966715594426426    # E0012  sealed final test, gbdt incumbent

SE_CROSS_DEV = 0.000963      # cross-track paired-bootstrap SE, development (B=1000 CRN)
SE_CROSS_SEALED = 0.001028   # cross-track paired-bootstrap SE, sealed test
FLOOR_GLM = 0.000539         # glm track minimum_delta
TRAIN_ROWS = 406_807         # train-fold size (data_card.md)

ANCHOR_GAP = GLM_ANCHOR - GBDT_INCUMBENT      # 0.010172
DEV_GAP = GLM_SPLINES - GBDT_INCUMBENT        # 0.008467  (incumbent-vs-incumbent)
SEALED_GAP = SEALED_GLM - SEALED_GBDT         # 0.009564

TEXT = CHROME["primary_ink"]
MUTED = CHROME["secondary_ink"]
FAINT = CHROME["muted"]
GLM_C = CATEGORICAL[0]        # blue   — the GLM track
GBDT_C = CATEGORICAL[7]       # orange — the GBDT track
WIN_C = CATEGORICAL[1]        # green  — signal actually recovered
LOSS_C = CATEGORICAL[5]       # red    — the residue nothing reached


def _save(fig: plt.Figure, name: str) -> Path:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    path = FIGDIR / f"{name}.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# (a) gap waterfall
# ---------------------------------------------------------------------------
def gap_waterfall() -> Path:
    fig, ax = plt.subplots(figsize=(10.2, 6.4))
    width = 0.52

    # --- waterfall connectors (drawn first, under everything) ---
    # NB the x=2 connector rides at GLM_SPLINES, not GLM_PRODUCTS: the products were
    # REJECTED, so the glm frontier never moved past E0004.
    for x, level in ((0, GLM_ANCHOR), (1, GLM_SPLINES), (2, GLM_SPLINES)):
        ax.plot([x + width / 2, x + 1 - width / 2], [level, level],
                color=FAINT, lw=0.9, ls=(0, (3, 2)), zorder=2)
    ax.plot([2 + width / 2, 4 - width / 2], [GBDT_INCUMBENT, GBDT_INCUMBENT],
            color=FAINT, lw=0.9, ls=(0, (3, 2)), zorder=2)

    # --- endpoint levels (markers, not bars: these are levels, not deltas) ---
    for x, level, color, label in (
        (0, GLM_ANCHOR, GLM_C, f"GLM-OHE anchor\nE0002  {GLM_ANCHOR:.6f}"),
        (4, GBDT_INCUMBENT, GBDT_C, f"HGBT-OHE incumbent\nE0003  {GBDT_INCUMBENT:.6f}"),
    ):
        ax.plot([x - width / 2, x + width / 2], [level, level], color=color, lw=3.4, zorder=5,
                solid_capstyle="butt")
        ax.annotate(label, xy=(x, level), xytext=(0, 13 if x == 0 else -34),
                    textcoords="offset points", ha="center", fontsize=9.5,
                    color=color, fontweight="bold", linespacing=1.35)

    # --- step 1: scoped splines — the only thing that cleared the floor ---
    ax.bar(1, GLM_ANCHOR - GLM_SPLINES, bottom=GLM_SPLINES, width=width,
           color=WIN_C, alpha=0.92, edgecolor=TEXT, linewidth=0.7, zorder=4)
    ax.annotate(
        f"+ scoped splines  E0004\n−{GLM_ANCHOR - GLM_SPLINES:.6f}\n"
        f"16.8% of the gap  ·  3.2× floor\nKEEP",
        xy=(1, GLM_SPLINES), xytext=(0, -52), textcoords="offset points",
        ha="center", fontsize=9, color=TEXT, linespacing=1.4,
    )

    # --- step 2: the rejected interaction products ---
    ax.bar(2, GLM_SPLINES - GLM_PRODUCTS, bottom=GLM_PRODUCTS, width=width,
           color=FAINT, alpha=0.42, edgecolor=MUTED, linewidth=0.9, hatch="////", zorder=4)
    ax.annotate(
        f"+ top-2 surrogate products  E0007/E0008\n−{GLM_SPLINES - GLM_PRODUCTS:.6f}"
        f"  =  0.45× floor\nSUB-FLOOR → REJECTED  (10 screened / 0 adopted)",
        xy=(2, GLM_PRODUCTS), xytext=(14, 30), textcoords="offset points",
        ha="left", fontsize=9, color=MUTED, linespacing=1.4,
        arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8, shrinkA=0, shrinkB=3),
    )

    # --- step 3: the residue nothing reached ---
    ax.bar(3, GLM_SPLINES - GBDT_INCUMBENT, bottom=GBDT_INCUMBENT, width=width,
           color=LOSS_C, alpha=0.28, edgecolor=LOSS_C, linewidth=1.2, hatch="\\\\\\\\",
           zorder=3)
    ax.annotate(
        f"non-additive residue\n−{DEV_GAP:.6f}\n≈ 83% of the gap  ·  8.8× SE\n"
        f"surrogate R²$_{{main}}$ = 0.66",
        xy=(3, (GLM_SPLINES + GBDT_INCUMBENT) / 2), xytext=(0, 0),
        textcoords="offset points", ha="center", va="center", fontsize=9.5,
        color=LOSS_C, fontweight="bold", linespacing=1.45,
        bbox=dict(boxstyle="round,pad=0.42", facecolor="white", edgecolor=LOSS_C, lw=1.0,
                  alpha=0.94),
    )

    # --- the resolution limit: +/-1 cross paired SE, drawn to scale ---
    ax.axhspan(GBDT_INCUMBENT - SE_CROSS_DEV, GBDT_INCUMBENT + SE_CROSS_DEV,
               color=CHROME["gridline"], alpha=0.85, zorder=1)
    ax.annotate(
        f"±1 cross-track paired SE ({SE_CROSS_DEV:.6f})\n"
        f"— the resolution limit of this axis",
        xy=(4.42, GBDT_INCUMBENT), xytext=(0, 0), textcoords="offset points",
        ha="left", va="center", fontsize=8.5, color=MUTED, linespacing=1.35,
    )

    # --- total gap bracket ---
    arrow = FancyArrowPatch((-0.62, GBDT_INCUMBENT), (-0.62, GLM_ANCHOR),
                            arrowstyle="<->", mutation_scale=13, color=TEXT, lw=1.3)
    ax.add_patch(arrow)
    ax.annotate(
        f"anchor gap\n{ANCHOR_GAP:.6f}\n10.6× SE",
        xy=(-0.72, (GLM_ANCHOR + GBDT_INCUMBENT) / 2), ha="right", va="center",
        fontsize=9, color=TEXT, fontweight="bold", linespacing=1.4,
    )

    ax.set_xlim(-1.85, 5.55)
    ax.set_ylim(GBDT_INCUMBENT - 0.0022, GLM_ANCHOR + 0.0021)
    ax.set_xticks([])
    ax.set_ylabel("validation Poisson deviance  (lower is better)", fontsize=10.5)
    ax.set_title(
        "Where the GLM→GBDT gap goes on freMTPL2 frequency\n"
        "development fold, 406,807 train rows · additive shaping reaches 17%; "
        "the other 83% is non-additive",
        fontsize=12.5, fontweight="bold", loc="left", pad=14,
    )
    ax.grid(axis="y", color=CHROME["gridline"], lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.annotate(
        "y-axis is a deviance LEVEL and is zoomed, not zero-based — bar HEIGHTS are the "
        "deltas, and the grey band shows one standard error at true scale.",
        xy=(0.0, -0.075), xycoords="axes fraction", fontsize=8, color=MUTED, ha="left",
    )
    return _save(fig, "gap_waterfall")


# ---------------------------------------------------------------------------
# (b) data-volume curve (RQ6)
# ---------------------------------------------------------------------------
def data_volume_curve() -> Path:
    side = pd.read_csv(STUDY / "sweeps" / "data_volume.sidecar.tsv", sep="\t")
    frac = side["params_json"].str.extract(r'"fraction":\s*([0-9.]+)')[0].astype(float)
    gap = side["primary_metric"].astype(float)
    rows = (frac * TRAIN_ROWS).round().astype(int)

    fig, ax = plt.subplots(figsize=(10.2, 6.0))

    # 2-SE indistinguishability band around zero
    ax.axhspan(-2 * SE_CROSS_DEV, 2 * SE_CROSS_DEV, color=CHROME["gridline"], alpha=0.9,
               zorder=1)
    ax.axhline(0.0, color=CHROME["baseline"], lw=1.2, zorder=2)

    # GLM-wins region (gap < 0)
    ax.axvspan(rows.min() * 0.72, 30_000, color=GLM_C, alpha=0.07, zorder=0)

    ax.plot(rows, gap, color=GBDT_C, lw=2.4, marker="o", ms=7.5, zorder=4,
            markerfacecolor="white", markeredgewidth=2.0, markeredgecolor=GBDT_C)

    for r, g in zip(rows, gap):
        off = (0, 14) if g >= 0 else (0, -22)
        ax.annotate(f"{g:+.4f}", xy=(r, g), xytext=off, textcoords="offset points",
                    ha="center", fontsize=8.8, color=TEXT)

    ax.annotate(
        "GLM WINS below the crossover\n"
        "−0.001931 at ~20.3k rows (5% of train)\n"
        "zero-crossing: 20–41k rows",
        xy=(rows.iloc[0], gap.iloc[0]), xytext=(30_000, -0.0040),
        ha="left", va="center", fontsize=9.4, color=GLM_C, fontweight="bold",
        linespacing=1.5,
        arrowprops=dict(arrowstyle="->", color=GLM_C, lw=1.3, shrinkA=6, shrinkB=8),
    )
    ax.annotate(
        f"GBDT advantage at full data\n+{ANCHOR_GAP:.6f}  =  10.6× SE",
        xy=(rows.iloc[-1], gap.iloc[-1]), xytext=(150_000, 0.0126),
        ha="center", va="center", fontsize=9.4, color=GBDT_C, fontweight="bold",
        linespacing=1.5,
        arrowprops=dict(arrowstyle="->", color=GBDT_C, lw=1.3, shrinkA=8, shrinkB=8),
    )
    ax.annotate(
        f"±2 cross-track paired SE ({2 * SE_CROSS_DEV:.6f})\n"
        f"— models indistinguishable inside this band",
        xy=(95_000, 0.0), xytext=(0, 0), textcoords="offset points", ha="left",
        va="center", fontsize=8.8, color=MUTED, linespacing=1.35,
    )

    ax.set_xscale("log")
    ax.set_xlim(rows.min() * 0.74, rows.max() * 1.30)
    ax.set_ylim(-0.0060, 0.0142)
    ax.set_xticks(list(rows))
    ax.set_xticklabels([f"{r / 1000:,.0f}k\n{f:.0%}" for r, f in zip(rows, frac)],
                       fontsize=8.8)
    ax.minorticks_off()
    ax.set_xlabel("training rows (log scale) / fraction of train fold — dev fold never "
                  "subsampled", fontsize=10.5)
    ax.set_ylabel(
        "gap = GLM-OHE − HGBT-OHE  (validation Poisson deviance)\n"
        "positive = GBDT better  ·  zero-based",
        fontsize=10.5,
    )
    ax.set_title(
        "RQ6 — the GLM→GBDT gap is a function of portfolio size\n"
        "freMTPL2 frequency, anchor configs refit on nested train subsamples "
        "(sweeps/data_volume.sidecar.tsv)",
        fontsize=12.5, fontweight="bold", loc="left", pad=14,
    )
    ax.grid(color=CHROME["gridline"], lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return _save(fig, "data_volume_curve")


# ---------------------------------------------------------------------------
# (c) sealed vs development gap (RQ1)
# ---------------------------------------------------------------------------
def sealed_gap() -> Path:
    fig, ax = plt.subplots(figsize=(10.2, 4.9))

    entries = [
        ("development fold\nE0004 − E0003  (incumbent vs incumbent)\n"
         "0.453156 − 0.444689", DEV_GAP, SE_CROSS_DEV, GLM_C, "exploratory", 1.0, 26),
        ("SEALED test fold\nE0011 − E0012  (one access per track)\n"
         "0.459231 − 0.449667", SEALED_GAP, SE_CROSS_SEALED, GBDT_C, "confirmed", 0.0, -46),
    ]

    ax.axvline(0.0, color=CHROME["baseline"], lw=1.4, zorder=2)
    ax.annotate("no difference", xy=(0, 1.66), ha="center", fontsize=8.8, color=MUTED)

    for label, gap, se, color, level, y, voff in entries:
        ax.errorbar(gap, y, xerr=2 * se, fmt="o", ms=13, color=color, ecolor=color,
                    elinewidth=2.4, capsize=8, capthick=2.4, zorder=5,
                    markerfacecolor="white", markeredgewidth=2.8)
        ax.annotate(label, xy=(0.00022, y), xytext=(0, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=9.4, color=TEXT, linespacing=1.45)
        ax.annotate(
            f"{gap:+.6f}   ±2×SE ({se:.6f})\n{gap / se:.1f}× SE from zero"
            f"   ·   {level}",
            xy=(gap, y), xytext=(0, voff), textcoords="offset points", ha="center",
            fontsize=9.4, color=color, fontweight="bold", linespacing=1.45,
        )

    # replication bracket, in the clear band between the two rows
    ax.annotate(
        "", xy=(DEV_GAP, 0.62), xytext=(SEALED_GAP, 0.62),
        arrowprops=dict(arrowstyle="<->", color=TEXT, lw=1.4),
    )
    ax.annotate(
        f"|sealed − development| = {abs(SEALED_GAP - DEV_GAP):.6f} = "
        f"{abs(SEALED_GAP - DEV_GAP) / SE_CROSS_SEALED:.2f}× SE\n"
        f"— inside the pre-registered 2-SE replication band   →   RQ1 CONFIRMED",
        xy=((DEV_GAP + SEALED_GAP) / 2, 0.54), ha="center", va="top", fontsize=9.6,
        color=TEXT, fontweight="bold", linespacing=1.5,
    )

    ax.set_ylim(-0.95, 1.92)
    ax.set_xlim(-0.0009, 0.0148)
    ax.set_yticks([])
    ax.set_xlabel(
        "GLM − GBDT gap  (Poisson deviance; positive = GBDT better)  ·  zero-based",
        fontsize=10.5,
    )
    ax.set_title(
        "RQ1 — the GLM→GBDT gap survives as a difference of two SEALED numbers\n"
        "freMTPL2 frequency · two tracks, one final-test access each; "
        "study 04's protocol caveat closed",
        fontsize=12, fontweight="bold", loc="left", pad=14,
    )
    ax.grid(axis="x", color=CHROME["gridline"], lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    return _save(fig, "sealed_gap")


def main() -> None:
    _apply_style()
    for fn in (gap_waterfall, data_volume_curve, sealed_gap):
        print(f"wrote {fn()}")


if __name__ == "__main__":
    main()
