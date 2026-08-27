"""make_figures.py — study-local exhibits for 09-iris-first-lesson.

Self-contained: stdlib + pandas + matplotlib only (no seaborn). Deterministic
(no randomness, no timestamps), no network, reads ONLY files inside the study's
sweeps/ directory:

  sweeps/candidate_floors.tsv    paired floors per family (anchor row = marginal, exhibit-only)
  sweeps/rq0_headroom.tsv        h_c = anchor mean / floor_c permission map + ledger scalar
  sweeps/headroom.tsv            per-rung anchor mean m_n and per-rung floor delta_n
  sweeps/arena_verdicts.tsv      per family x rung mean_gain (anchor - family; + = challenger better)
  sweeps/arena.sidecar.tsv       challenger fold-eval Briers (cross-check only)
  sweeps/rq4_saturation.tsv      rung-60 AUC ceiling share vs mean val Brier
  sweeps/sim_risk.tsv            plug-in risk decomposition irr + bias^2 + var over G1..G4

Writes four PNGs (200 dpi, white background) into --out:

  rq0_permission.png    claim-permission map: floor_c bars vs the anchor's own mean
  rung_ladder.png       fog/ceiling ladder: anchor m_n +/- delta_n band + challenger means
  rq4_saturation.png    rung 60: AUC ceiling share vs mean val Brier per family
  sim_decomposition.png 2x2 G1..G4 stacked irr/bias^2/var bars, lda vs structural winner

Every number is read from the study artifacts and cross-checked (numbers law:
nothing invented, nothing retyped). Run from the repo root:

    uv run --no-sync python make_figures.py \
        --study studies/09-iris-first-lesson --out <outdir>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

DPI = 200
#: deterministic PNG metadata (matplotlib writes no timestamp; pin Software too).
META = {"Software": "make_figures.py (study 09)"}

# ---------------------------------------------------------------------------
# palette — colorblind-safe Dark2 family (#1b9e77/#d95f02/#7570b3/#666666 ...)
# ---------------------------------------------------------------------------
INK = "#1a1a1a"      # anchor
TEAL = "#1b9e77"
ORANGE = "#d95f02"
PURPLE = "#7570b3"
MAGENTA = "#e7298a"
GREEN = "#66a61e"
GOLD = "#e6ab02"
BROWN = "#a6761d"
GREY = "#666666"
LIGHTGREY = "#999999"

#: challenger order (era order), color + marker per family (marker = redundancy
#: for grayscale / colorblind readers).
CHALLENGERS = [
    ("qda", TEAL, "o"),
    ("logit_l2", ORANGE, "s"),
    ("knn_tuned", PURPLE, "D"),
    ("svm_rbf_platt", MAGENTA, "^"),
    ("lda_shrinkage", GREEN, "v"),
    ("hgbt", BROWN, "P"),
    ("tabpfn", GOLD, "X"),
]
FAMILY_COLOR = {f: c for f, c, _ in CHALLENGERS}
FAMILY_MARKER = {f: m for f, _, m in CHALLENGERS}
FAMILY_COLOR["anchor_lda4"] = INK
FAMILY_MARKER["anchor_lda4"] = "*"
FAMILY_COLOR["lda_petal"] = GREY
FAMILY_MARKER["lda_petal"] = "<"
FAMILY_COLOR["lda_sepal"] = LIGHTGREY
FAMILY_MARKER["lda_sepal"] = ">"

C_OPEN = TEAL        # measurement-open rows
C_CLOSED = "#8a8a8a" # measurement-closed rows (grey tint)
C_COMP_IRR = GREY    # irreducible risk
C_COMP_BIAS = ORANGE # bias^2
C_COMP_VAR = PURPLE  # variance


def read_tsv(study: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(study / "sweeps" / name, sep="\t")


def source_tag(fig: plt.Figure, study_label: str, files: str) -> None:
    fig.text(0.008, 0.006, f"{study_label} · {files}", fontsize=7,
             color="#909090", ha="left", va="bottom")


# ---------------------------------------------------------------------------
# figure 1 — rq0_permission.png
# ---------------------------------------------------------------------------
def fig_rq0_permission(study: Path, out: Path, study_label: str) -> None:
    floors = read_tsv(study, "candidate_floors.tsv")
    rq0 = read_tsv(study, "rq0_headroom.tsv")

    # anchor row is MARGINAL stats — exhibit only, never a clearance bar.
    anchor = floors[floors["role"] == "anchor"]
    assert len(anchor) == 1 and anchor["stat_kind"].iloc[0] == "marginal-resplit"
    assert "exhibit" in anchor["floor_rule"].iloc[0]
    anchor_mean = float(anchor["mean_d"].iloc[0])
    assert abs(anchor_mean - 0.04302915) < 1e-9, anchor_mean

    cand = rq0[rq0["scope"] == "candidate"].copy()
    assert len(cand) == 7 and (cand["numerator"] == anchor_mean).all()
    assert (cand["denominator_name"] == "floor_c").all()
    ledger = rq0[rq0["scope"] == "ledger"]
    assert len(ledger) == 1 and ledger["denominator_name"].iloc[0] == "minimum_delta"
    delta_ledger = float(ledger["denominator"].iloc[0])
    assert delta_ledger == 0.08, delta_ledger

    # cross-check: rq0 floor_c must equal candidate_floors floor_c, h = mean/floor.
    fl = floors.set_index("family")["floor_c"]
    for _, r in cand.iterrows():
        assert abs(float(r["denominator"]) - float(fl[r["family"]])) < 1e-12
        assert abs(float(r["h"]) - anchor_mean / float(r["denominator"])) < 1e-9
        assert bool(r["measurement_closed"]) == (float(r["h"]) < 1.0)

    cand = cand.sort_values("denominator")  # sorted by floor_c, smallest on top
    n = len(cand)
    ys = list(range(n))[::-1]

    fig, ax = plt.subplots(figsize=(9.0, 5.6))
    for y, (_, r) in zip(ys, cand.iterrows()):
        closed = bool(r["measurement_closed"])
        floor_c = float(r["denominator"])
        ax.barh(y, floor_c, height=0.62,
                facecolor=C_CLOSED if closed else C_OPEN,
                alpha=0.55 if closed else 0.85,
                edgecolor="black", linewidth=0.8, zorder=2)
        verdict = "closed" if closed else "open"
        note = f"h$_c$ = {float(r['h']):.2f} — {verdict}"
        if floor_c > 0.055:  # long bar: annotate inside so nothing hits the δ line
            ax.text(floor_c - 0.0012, y, note, va="center", ha="right",
                    fontsize=9.5, fontweight="bold", color="#2d2d2d", zorder=3)
        else:
            ax.text(floor_c + 0.0012, y, note, va="center", fontsize=9.5,
                    fontweight="bold", color=GREY if closed else TEAL, zorder=3)

    ax.axvline(anchor_mean, color=INK, linewidth=1.8, linestyle="--", zorder=4)
    ax.text(anchor_mean + 0.0012, 6.62, "anchor mean Brier (20 paired redraws)",
            fontsize=8.6, color=INK, va="center")
    ax.axvline(delta_ledger, color=ORANGE, linewidth=1.8, linestyle="-.", zorder=4)
    ax.text(delta_ledger + 0.0012, 6.05, f"ledger δ = {delta_ledger:.2f}",
            fontsize=8.6, color=ORANGE, va="center")

    ax.set_yticks(ys)
    ax.set_yticklabels(cand["family"], fontsize=10)
    ax.set_xlim(0, 0.092)
    ax.set_ylim(-0.55, 7.0)
    ax.set_xlabel("Brier score (unitless; bars = paired floor floor$_c$, k = 20 redraws)")
    ax.set_title(
        "RQ0 claim-permission map: which challengers can even be measured?\n"
        "h$_c$ = anchor mean / floor$_c$;  h$_c$ < 1 ⇒ measurement-closed",
        fontsize=11.5,
    )
    fig.legend(
        handles=[
            Patch(facecolor=C_OPEN, alpha=0.85, edgecolor="black",
                  label="measurement-open (h$_c$ ≥ 1)"),
            Patch(facecolor=C_CLOSED, alpha=0.55, edgecolor="black",
                  label="measurement-closed (h$_c$ < 1)"),
            Line2D([], [], color=INK, linestyle="--",
                   label=f"anchor mean Brier (20 paired redraws) = {anchor_mean:.6f}"),
            Line2D([], [], color=ORANGE, linestyle="-.",
                   label=f"ledger scalar δ = {delta_ledger:.2f} (minimum_delta)"),
        ],
        loc="lower center", ncol=2, fontsize=8.6, frameon=False,
        bbox_to_anchor=(0.54, 0.015),
    )
    ax.grid(True, axis="x", linewidth=0.4, alpha=0.4)
    fig.tight_layout(rect=(0, 0.105, 1, 1))
    source_tag(fig, study_label, "sweeps/candidate_floors.tsv + sweeps/rq0_headroom.tsv")
    fig.savefig(out / "rq0_permission.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


# ---------------------------------------------------------------------------
# figure 2 — rung_ladder.png
# ---------------------------------------------------------------------------
def fig_rung_ladder(study: Path, out: Path, study_label: str) -> None:
    hr = read_tsv(study, "headroom.tsv").sort_values("rung")  # 8 -> 60 left to right
    verdicts = read_tsv(study, "arena_verdicts.tsv")
    assert (hr["n_folds_ok"] == 40).all() and (hr["anchor_failures"] == 0).all()
    assert (hr["state"] == "CLOSED").all()
    assert len(verdicts) == len(hr) * len(CHALLENGERS)

    # cross-check the derivation family_mean = m_n - mean_gain against the raw
    # challenger sidecar (published columns are 6 dp, so tolerance 2e-6).
    side = read_tsv(study, "arena.sidecar.tsv")
    assert (side["status"] == "ok").all() and len(side) == 1680
    params = side["params_json"].map(json.loads)
    side = side.assign(family=[p["family"] for p in params],
                       rung=[int(p["rung"]) for p in params])
    raw_mean = side.groupby(["family", "rung"])["primary_metric"].mean()
    m_n = hr.set_index("rung")["m_n"].astype(float)
    for _, v in verdicts.iterrows():
        derived = float(m_n[int(v["rung"])]) - float(v["mean_gain"])
        assert abs(derived - float(raw_mean[(v["family"], int(v["rung"]))])) < 2e-6

    x = list(range(len(hr)))
    m = hr["m_n"].astype(float).to_numpy()
    d = hr["delta_n"].astype(float).to_numpy()

    fig, ax = plt.subplots(figsize=(9.6, 6.2))
    ax.fill_between(x, m - d, m + d, color="#c9c9c9", alpha=0.45, zorder=1,
                    label="anchor m$_n$ ± δ$_n$ (per-rung floor δ$_n$)")
    ax.plot(x, m, "o-", color=INK, linewidth=2.4, markersize=8, zorder=4,
            label="anchor_lda4 mean m$_n$ (40 fold-evals)")
    ax.axhline(0.0, color=GREY, linewidth=0.9, linestyle=":", zorder=2)
    ax.annotate("Brier = 0 (perfect score)", xy=(len(hr) - 1.02, 0.0),
                ha="right", va="bottom", fontsize=8, color=GREY)

    offsets = [(-3 + i) * 0.09 for i in range(len(CHALLENGERS))]  # deterministic dodge
    for (family, color, marker), dx in zip(CHALLENGERS, offsets):
        sub = verdicts[verdicts["family"] == family].set_index("rung")
        ys = [float(m_n[r]) - float(sub.loc[r, "mean_gain"]) for r in hr["rung"]]
        ax.scatter([xi + dx for xi in x], ys, s=42, marker=marker,
                   facecolor=color, edgecolor="white", linewidth=0.5,
                   zorder=3, label=f"{family} mean (40 fold-evals)")

    # per-rung closure verdicts from headroom.tsv reason (below the band).
    for xi, (_, r) in zip(x, hr.iterrows()):
        kind = {"ceiling-closed": "ceiling", "fog-closed": "fog"}[r["reason"]]
        ax.text(xi, -0.135, f"CLOSED\n({kind})", ha="center", va="center",
                fontsize=8.6, fontweight="bold", color=GREY)

    ax.set_xticks(x)
    ax.set_xticklabels([f"n = {int(r)}" for r in hr["rung"]])
    ax.set_xlabel("nominal rung: training rows per fold-eval (rows)")
    ax.set_ylabel("development val Brier (unitless; lower is better)")
    ax.set_ylim(-0.20, 0.31)
    ax.set_title(
        "The data ladder: every rung closed — floor δ$_n$ swallows every gain\n"
        "(band bottom m$_n$ − δ$_n$ sits below zero: no beat is measurable)",
        fontsize=11.5,
    )
    ax.legend(loc="upper right", fontsize=8.2, ncol=2, framealpha=0.95)
    ax.grid(True, axis="y", linewidth=0.4, alpha=0.4)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    source_tag(fig, study_label,
               "sweeps/headroom.tsv + sweeps/arena_verdicts.tsv")
    fig.savefig(out / "rung_ladder.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


# ---------------------------------------------------------------------------
# figure 3 — rq4_saturation.png
# ---------------------------------------------------------------------------
def fig_rq4_saturation(study: Path, out: Path, study_label: str) -> None:
    rq4 = read_tsv(study, "rq4_saturation.tsv")
    sub = rq4[(rq4["rung"] == 60) & (rq4["metric"] == "val_auc")
              & (rq4["scope"] == "family")].copy()
    assert (sub["n_evals"] == 40).all() and (sub["n_na"] == 0).all()
    for _, r in sub.iterrows():
        assert abs(float(r["ceiling_share"]) - int(r["n_ceiling"]) / 40) < 1e-12

    # deterministic hand-placed labels (data coords, ha) — the low-Brier cluster
    # at ceiling_share 0.55–0.78 is dense, so each label has a fixed home.
    place = {
        "lda_sepal": (0.015, 0.2146, "left"),
        "hgbt": (0.192, 0.0927, "left"),
        "knn_tuned": (0.535, 0.0439, "right"),
        "lda_petal": (0.585, 0.0505, "right"),
        "svm_rbf_platt": (0.640, 0.0459, "left"),
        "tabpfn": (0.610, 0.0365, "right"),
        "qda": (0.665, 0.0388, "left"),
        "logit_l2": (0.740, 0.0404, "left"),
        "anchor_lda4": (0.790, 0.0335, "left"),
        "lda_shrinkage": (0.790, 0.0288, "left"),
    }

    fig, ax = plt.subplots(figsize=(9.0, 6.0))
    for _, r in sub.sort_values("family").iterrows():
        fam = r["family"]
        x, y = float(r["ceiling_share"]), float(r["mean_val_brier"])
        is_anchor = fam == "anchor_lda4"
        ax.scatter([x], [y], s=170 if is_anchor else 70,
                   marker=FAMILY_MARKER[fam], facecolor=FAMILY_COLOR[fam],
                   edgecolor="black" if is_anchor else "white",
                   linewidth=1.2 if is_anchor else 0.6, zorder=4 if is_anchor else 3)
        label = fam + (" (anchor)" if is_anchor else "")
        if fam in ("lda_petal", "lda_sepal"):
            label += " (control)"
        tx, ty, ha = place[fam]
        ax.text(tx, ty, label, fontsize=8.8, color=INK, ha=ha, va="center", zorder=5)

    # the saturation zone and its honest headline, computed from the table.
    zone = sub[sub["ceiling_share"] >= 0.55]
    spread = float(zone["mean_val_brier"].max() / zone["mean_val_brier"].min())
    ax.axvspan(0.55, 0.80, color=TEAL, alpha=0.08, zorder=1)
    ax.text(0.675, 0.135,
            f"{len(zone)} of {len(sub)} families pile up here:\n"
            f"val AUC = 1.0 in ≥ 55% of fold-evals,\n"
            f"yet mean Brier still spreads {spread:.1f}×",
            ha="center", fontsize=8.8, color=GREY)

    ax.set_xlim(-0.05, 0.90)
    ax.set_yscale("log")
    ax.set_ylim(0.024, 0.28)
    ax.set_yticks([0.03, 0.04, 0.05, 0.07, 0.10, 0.15, 0.20])
    ax.set_yticklabels(["0.03", "0.04", "0.05", "0.07", "0.10", "0.15", "0.20"])
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("AUC ceiling share (fraction of 40 fold-evals with val AUC = 1.0)")
    ax.set_ylabel("mean val Brier over 40 fold-evals (unitless, log scale; lower is better)")
    ax.set_title(
        "Rung n = 60: ranking saturates — probability quality still separates",
        fontsize=11.5,
    )
    ax.grid(True, which="major", linewidth=0.4, alpha=0.4)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    source_tag(fig, study_label, "sweeps/rq4_saturation.tsv")
    fig.savefig(out / "rq4_saturation.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


# ---------------------------------------------------------------------------
# figure 4 — sim_decomposition.png
# ---------------------------------------------------------------------------
PANELS = [  # (dgp key, panel title, structural winner, irr-label x [log10 units] or None)
    ("G1-linear-match", "G1 linear-match (LDA's world)", "slda", None),
    ("G2-irrelevant-dims", "G2 +16 irrelevant dims", "slda", None),
    ("G3-unequal-cov", "G3 unequal covariance (QDA's world)", "qda", None),
    ("G4-xor", "G4 XOR (nonlinear world)", "hgbt", 2.50),  # mid-gap: clears the n=500 bars
]


def fig_sim_decomposition(study: Path, out: Path, study_label: str) -> None:
    sim = read_tsv(study, "sim_risk.tsv")
    ok = sim[sim["k_effective"] > 0]
    # identity gate, recomputed AND against the recorded check column.
    assert float(ok["check_abs_err"].max()) <= 1e-9
    recomputed = (ok["total"] - (ok["irr"] + ok["bias2"] + ok["var"])).abs()
    assert float(recomputed.max()) <= 1e-9
    assert (ok["k_effective"] == 100).all()
    # the only registered failures: QDA x G2 x n <= 30.
    failed = sim[sim["k_effective"] == 0]
    assert set(map(tuple, failed[["dgp", "model", "n"]].to_numpy())) == {
        ("G2-irrelevant-dims", "qda", 8), ("G2-irrelevant-dims", "qda", 12),
        ("G2-irrelevant-dims", "qda", 20), ("G2-irrelevant-dims", "qda", 30)}

    ns = sorted(sim["n"].unique())
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.2))
    half_w, gap = 0.036, 0.041  # bar half-width / model offset, in log10(n) units

    for ax, (dgp, title, winner, irr_label_x) in zip(axes.flat, PANELS):
        panel = sim[(sim["dgp"] == dgp) & (sim["k_effective"] > 0)]
        irr_vals = panel["irr"].unique()
        assert len(irr_vals) == 1  # irr is a DGP property, constant across cells
        irr = float(irr_vals[0])

        for model, dx, hatch in ((("lda"), -gap, None), ((winner), +gap, "///")):
            sub = panel[panel["model"] == model].set_index("n")
            assert list(sub.index) == ns
            xs = [math.log10(n) + dx for n in ns]
            b = sub["bias2"].astype(float).to_numpy()
            v = sub["var"].astype(float).to_numpy()
            kw = dict(width=2 * half_w, edgecolor="black", linewidth=0.4,
                      hatch=hatch, zorder=3)
            ax.bar(xs, [irr] * len(ns), color=C_COMP_IRR, alpha=0.45, **kw)
            ax.bar(xs, b, bottom=[irr] * len(ns), color=C_COMP_BIAS, alpha=0.9, **kw)
            ax.bar(xs, v, bottom=irr + b, color=C_COMP_VAR, alpha=0.9, **kw)

        ax.axhline(irr, color=INK, linewidth=1.1, linestyle="--", zorder=4)
        lx = math.log10(ns[-1]) + 0.28 if irr_label_x is None else irr_label_x
        ax.annotate(f"irr = {irr:.3f}", xy=(lx, irr),
                    xytext=(0, 3), textcoords="offset points",
                    fontsize=8, va="bottom", ha="right" if irr_label_x is None else "center",
                    color=INK)

        ax.set_xticks([math.log10(n) for n in ns])
        ax.set_xticklabels([str(n) for n in ns], fontsize=9)
        ax.set_xlim(math.log10(ns[0]) - 0.14, math.log10(ns[-1]) + 0.30)
        ax.set_xlabel("training set size n (rows, log scale)")
        ax.set_ylabel("risk: expected squared error (unitless)")
        ax.set_title(f"{title} — lda (solid) vs {winner} (hatched)", fontsize=10.5)
        ax.grid(True, axis="y", linewidth=0.4, alpha=0.4)

    fig.legend(
        handles=[
            Patch(facecolor=C_COMP_IRR, alpha=0.45, edgecolor="black", label="irr (irreducible)"),
            Patch(facecolor=C_COMP_BIAS, alpha=0.9, edgecolor="black", label="bias²"),
            Patch(facecolor=C_COMP_VAR, alpha=0.9, edgecolor="black", label="var"),
            Patch(facecolor="white", edgecolor="black", label="lda (solid)"),
            Patch(facecolor="white", edgecolor="black", hatch="///", label="panel winner (hatched)"),
            Line2D([], [], color=INK, linestyle="--", label="irreducible p*(1−p*)"),
        ],
        loc="lower center", ncol=6, fontsize=8.8, frameon=False,
        bbox_to_anchor=(0.5, 0.033),
    )
    fig.suptitle("Where each assumption pays: risk = irr + bias² + var", fontsize=12.5)
    fig.text(0.5, 0.012,
             "plug-in decomposition over 100 registered draws; "
             "identity |total−(irr+bias²+var)| ≤ 1e-9",
             ha="center", fontsize=8.4, color=GREY)
    fig.tight_layout(rect=(0, 0.055, 1, 0.965))
    source_tag(fig, study_label, "sweeps/sim_risk.tsv")
    fig.savefig(out / "sim_decomposition.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True,
                        help="study directory (e.g. studies/09-iris-first-lesson)")
    parser.add_argument("--out", required=True, help="output directory for PNGs")
    args = parser.parse_args()

    study = Path(args.study)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    study_label = "/".join(study.resolve().parts[-2:])

    plt.rcParams.update({"font.size": 10.5, "figure.facecolor": "white",
                         "axes.facecolor": "white", "savefig.facecolor": "white"})

    fig_rq0_permission(study, out, study_label)
    fig_rung_ladder(study, out, study_label)
    fig_rq4_saturation(study, out, study_label)
    fig_sim_decomposition(study, out, study_label)

    for name in ("rq0_permission.png", "rung_ladder.png",
                 "rq4_saturation.png", "sim_decomposition.png"):
        path = out / name
        print(f"wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
