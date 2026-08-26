"""Figure generator for study 08-iris-rematch (deterministic, local files only).

Run from the study dir:  uv run --project ../.. --locked python figures/make_figures.py
Outputs (150 dpi): figures/headroom_ladder.png · figures/parade_board.png ·
figures/arena_strip.png (only if the Stage-B sidecar exists).
Numbers come ONLY from committed study artifacts (headroom.tsv, results.tsv,
sweeps sidecars, study.yaml).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

STUDY = Path(__file__).resolve().parent.parent
FIG = STUDY / "figures"
INK = "#1a1a2e"
BLUE = "#2563eb"
RED = "#dc2626"
GRAY = "#9ca3af"
GOLD = "#b45309"
GREEN = "#047857"

MIN_DELTA = 0.029
ANCHOR_DEV = 0.029442
KEEP_NEEDS = ANCHOR_DEV - MIN_DELTA  # 0.000442


def headroom_ladder() -> None:
    hr = pd.read_csv(STUDY / "sweeps" / "headroom.tsv", sep="\t")
    hr = hr.sort_values("rung", ascending=False)
    x = range(len(hr))
    m = hr["m_n"].astype(float)
    d = hr["delta_n"].astype(float)
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    ax.fill_between(x, m, d, where=(d >= m), color=RED, alpha=0.12,
                    label="closed zone: floor above the incumbent's own error")
    ax.plot(x, m, "o-", color=BLUE, lw=2.2, ms=7,
            label="anchor mean dev Brier  m$_n$  (40 fold-evals)")
    ax.plot(x, d, "s--", color=RED, lw=2.0, ms=7,
            label="per-rung floor  δ$_n$ = max(⌈2·sd$_n$⌉, 0.005)")
    for i, (_, r) in enumerate(hr.iterrows()):
        ax.annotate(f"{r['reason']}", (i, float(r["delta_n"])),
                    textcoords="offset points", xytext=(0, 10),
                    ha="center", fontsize=8, color=RED)
        ax.annotate(f"{float(r['m_n']) / float(r['delta_n']):.2f}",
                    (i, float(r["m_n"])), textcoords="offset points",
                    xytext=(0, -16), ha="center", fontsize=8, color=BLUE)
    ax.set_xticks(list(x), [f"n={int(r)}" for r in hr["rung"]])
    ax.set_ylabel("development Brier (lower is better)")
    ax.set_title("The data ladder is closed at every rung — the floor outruns the error\n"
                 "(blue annotations: headroom ratio m$_n$/δ$_n$ ≈ 0.5 everywhere)")
    ax.legend(loc="upper left", fontsize=9, framealpha=0.95)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG / "headroom_ladder.png", dpi=150, facecolor="white")
    plt.close(fig)


def parade_board() -> None:
    res = pd.read_csv(STUDY / "results.tsv", sep="\t")
    rows = []
    for _, r in res.iterrows():
        exp = r["experiment"]
        if exp in ("E0001", "E0002"):
            continue
        fam = str(r["description"]).split("verification parade: ")[-1].split(" -")[0].strip()
        rows.append((fam, r["status"],
                     float(r["primary_metric"]) if str(r["primary_metric"]) not in ("NA", "nan") else None))
    rows = rows[::-1]
    fig, ax = plt.subplots(figsize=(8.6, 7.2))
    ys = range(len(rows))
    for y, (fam, status, val) in zip(ys, rows):
        if val is None:
            ax.barh(y, 0.19, color="white", edgecolor=RED, hatch="///", height=0.62)
            ax.text(0.191, y, " crash", va="center", fontsize=8.5, color=RED)
        else:
            better = val < ANCHOR_DEV
            ax.barh(y, val, color=(GREEN if better else GRAY), height=0.62, alpha=0.9)
            ax.text(val + 0.002, y, f"{val:.4f}", va="center", fontsize=8)
    ax.axvline(ANCHOR_DEV, color=BLUE, lw=2.2)
    ax.text(ANCHOR_DEV, len(rows) - 0.1, f"  anchor 1936 = {ANCHOR_DEV:.6f}",
            color=BLUE, fontsize=9, va="bottom")
    ax.axvline(KEEP_NEEDS, color=GOLD, lw=2.0, ls=":")
    ax.text(KEEP_NEEDS + 0.001, -0.45, f"keep needs ≤ {KEEP_NEEDS:.6f} (the ajar door)",
            color=GOLD, fontsize=9)
    ax.set_yticks(list(ys), [f[0] for f in rows], fontsize=9)
    ax.set_xlabel("declared-split dev Brier (lower is better)")
    ax.set_title("The verification parade: 21 challengers, the door ajar by 0.000442 —\n"
                 "nobody walked through (green = beat the anchor's raw score; none by ≥ δ = 0.029)")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG / "parade_board.png", dpi=150, facecolor="white")
    plt.close(fig)


def arena_strip() -> None:
    side = STUDY / "sweeps" / "rematch_arena.sidecar.tsv"
    if not side.is_file():
        print("arena sidecar absent — skipping arena_strip.png")
        return
    df = pd.read_csv(side, sep="\t")
    df["params"] = df["params_json"].apply(json.loads)
    df["family"] = df["params"].apply(lambda p: p["family"])
    df["rung"] = df["params"].apply(lambda p: int(p["rung"]))
    anc = pd.read_csv(STUDY / "sweeps" / "rematch_arena_anchor.sidecar.tsv", sep="\t")
    anc["params"] = anc["params_json"].apply(json.loads)
    anc["family"] = anc["params"].apply(lambda p: p["family"])
    anc["rung"] = anc["params"].apply(lambda p: int(p["rung"]))
    hr = pd.read_csv(STUDY / "sweeps" / "headroom.tsv", sep="\t")
    rungs = sorted(hr["rung"].astype(int), reverse=True)
    fams = ["qda", "lda_shrinkage", "knn_tuned", "lda_platt", "hgbt", "tabpfn", "tabpfn_e16"]
    fig, axes = plt.subplots(1, len(rungs), figsize=(13.5, 4.6), sharey=False)
    for ax, n in zip(axes, rungs):
        a = anc[(anc["family"] == "anchor_lda4") & (anc["rung"] == n) & (anc["status"] == "ok")]
        am = a["primary_metric"].astype(float).mean()
        dn = float(hr[hr["rung"] == n]["delta_n"].iloc[0])
        ax.axhspan(am - dn, am + dn, color=RED, alpha=0.10)
        ax.axhline(am, color=BLUE, lw=1.6)
        for i, f in enumerate(fams):
            vals = df[(df["family"] == f) & (df["rung"] == n) & (df["status"] == "ok")][
                "primary_metric"].astype(float)
            if len(vals):
                ax.plot([i + 0.9 + 0.02 * (j % 5) for j in range(len(vals))], vals,
                        ".", ms=2.6, color=INK, alpha=0.45)
                ax.plot([i + 1.0], [vals.mean()], "D", ms=5, color=GOLD)
        ax.set_title(f"n={n}", fontsize=10)
        ax.set_xticks(range(1, len(fams) + 1), fams, rotation=90, fontsize=7)
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(axis="y", alpha=0.2)
    axes[0].set_ylabel("dev Brier")
    fig.suptitle("Arena fold-evals (dots) vs the anchor mean (blue) and its ±δ$_n$ band — 7 selected families",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "arena_strip.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    FIG.mkdir(exist_ok=True)
    headroom_ladder()
    parade_board()
    arena_strip()
    for p in sorted(FIG.glob("*.png")):
        print(p.name, p.stat().st_size)
