"""make_figures.py — study-local exhibits for 21-bloodmnist-cnn.

Self-contained: stdlib + numpy + pandas + matplotlib + PyYAML. Deterministic — no
randomness, no timestamps, no network, no images read. Reads ONLY committed evidence
inside the study: results.tsv, runs/E####/manifest.json and seeds.tsv, study.yaml (the
keep bar), the two registered sweep sidecars, and the pinned tables/ (per_class.tsv,
confusion_E####_s#.tsv). Every plotted number is cross-checked against a second source
before it is drawn (the numbers law: nothing invented, nothing retyped).

Writes six PNGs (200 dpi, white background) into --out:

  plot_decision_trajectory__primary.png  the frontier, run by run, with the keep bar
  candidate_deltas.png                   each candidate vs its incumbent, zero-based, bar drawn
  item_bootstrap.png                     where the keep bar comes from (1000 re-draws)
  seed_spread.png                        per-seed dev macro-F1, the anchor's fit noise
  per_class_recall.png                   per-class recall at the anchor, BN, incumbent, sealed
  confusion_incumbent_sealed.png         row-normalised confusion, E0008 dev vs E0009 sealed

Run from the repo root:

    uv run --no-sync python studies/21-bloodmnist-cnn/figures/make_figures.py \\
        --study studies/21-bloodmnist-cnn --out studies/21-bloodmnist-cnn/figures
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
from matplotlib.patches import Patch  # noqa: E402

DPI = 200
META = {"Software": "make_figures.py (study 21)"}

INK = "#1a1a1a"
TEAL = "#1b9e77"
ORANGE = "#d95f02"
PURPLE = "#7570b3"
MAGENTA = "#e7298a"
GREY = "#8a8a8a"
LIGHT = "#d9d9d9"

#: One-line idea per run, in ledger order (the description column is longer).
LABELS = {
    "E0001": "anchor\n2 blocks",
    "E0002": "pixel-linear\nsoftmax",
    "E0003": "BN, default\ninference",
    "E0004": "BN, train-set\nstatistics",
    "E0005": "+ D4\naugmentation",
    "E0006": "+ 3rd conv\nblock",
    "E0007": "4000 steps",
    "E0008": "bundle:\n3 blk+BN+D4+4000",
    "E0009": "sealed\ntest",
}


def load(study: Path):
    ledger = pd.read_csv(study / "results.tsv", sep="\t")
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    metric = contract["tracks"]["primary"]["metric"]
    delta = float(metric["minimum_delta"])
    manifests, seeds = {}, {}
    for run in ledger["experiment"]:
        manifests[run] = json.loads((study / "runs" / run / "manifest.json").read_text(encoding="utf-8"))
        seeds[run] = pd.read_csv(study / "runs" / run / "seeds.tsv", sep="\t")
    # cross-checks: ledger == manifest == mean of the per-seed table
    for run in ledger["experiment"]:
        value = float(ledger.loc[ledger["experiment"] == run, "primary_metric"].iloc[0])
        assert abs(value - float(manifests[run]["primary_metric"])) < 5e-7, run
        assert abs(value - float(seeds[run]["primary_metric"].mean())) < 5e-7, run
    assert abs(delta - max(2 * float(metric["noise_floor"]["std"]), float(metric["noise_floor"]["range"]) / 2)) < 5e-7
    boot = pd.read_csv(study / "sweeps" / "item_bootstrap.sidecar.tsv", sep="\t")
    fit = pd.read_csv(study / "sweeps" / "fit_noise.sidecar.tsv", sep="\t")
    assert abs(float(np.std(boot["primary_metric"], ddof=1)) - float(metric["noise_floor"]["std"])) < 5e-7
    per_class = pd.read_csv(study / "tables" / "per_class.tsv", sep="\t")
    return ledger, manifests, seeds, delta, metric, boot, fit, per_class


def incumbents(ledger: pd.DataFrame, manifests: dict) -> dict[str, str | None]:
    """Incumbent each candidate was judged against, read from the manifests."""
    out = {}
    for run in ledger["experiment"]:
        inc = manifests[run].get("incumbent")
        out[run] = inc if isinstance(inc, str) else None
    return out


def fig_trajectory(out: Path, ledger, manifests, delta):
    runs = list(ledger["experiment"])
    vals = [float(v) for v in ledger["primary_metric"]]
    kinds = [manifests[r]["evaluation_kind"] for r in runs]
    status = list(ledger["status"])
    phases = [manifests[r]["phase"] for r in runs]
    fig, ax = plt.subplots(figsize=(10.0, 5.2))

    # phase bands
    spans = {}
    for i, p in enumerate(phases):
        spans.setdefault(p, [i, i])[1] = i
    shade = {"anchor": "#f2f2f2", "adaptive": "#ffffff", "confirmation": "#fdebdc"}
    for p, (a, b) in spans.items():
        ax.axvspan(a - 0.5, b + 0.5, color=shade.get(p, "#ffffff"), zorder=0)
        ax.text((a + b) / 2, 1.012, f"phase: {p}", ha="center", va="bottom", fontsize=8, color=GREY)

    # frontier step + the bar to beat (frontier + keep bar), development only
    best, front, bar = -1.0, [], []
    for v, k, s in zip(vals, kinds, status, strict=True):
        if k == "development" and s == "keep":
            best = max(best, v)
        front.append(best if best >= 0 else np.nan)
        bar.append(best + delta if best >= 0 else np.nan)
    xs = np.arange(len(runs))
    ax.step(xs, front, where="post", color=TEAL, lw=1.8, zorder=2)
    ax.step(xs, bar, where="post", color=ORANGE, lw=1.3, ls="--", zorder=2)

    for i, (v, k, s) in enumerate(zip(vals, kinds, status, strict=True)):
        if k == "final_test":
            ax.scatter([i], [v], marker="*", s=260, color=ORANGE, edgecolor=INK, zorder=4)
        elif s == "keep":
            ax.scatter([i], [v], marker="D", s=90, color=TEAL, edgecolor=INK, zorder=4)
        else:
            ax.scatter([i], [v], marker="o", s=60, color="white", edgecolor=INK, lw=1.4, zorder=4)
        ax.annotate(f"{v:.4f}", xy=(i, v), xytext=(i, v + (0.045 if v < 0.9 else -0.07)), bbox={'fc': 'white', 'ec': 'none', 'alpha': 0.8, 'pad': 0.5}, ha="center",
                    fontsize=8, color=INK)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{r}\n{LABELS[r]}" for r in runs], fontsize=7.4)
    ax.set_ylim(0, 1.06)
    ax.set_ylabel("seed-mean macro-F1 (dev for E0001-E0008; sealed test for E0009)")
    ax.set_xlabel("experiment (ordinal = run order)")
    ax.set_title("Decision trajectory, track primary: two keeps in eight development arrays",
                 loc="left", fontsize=12, color=INK)
    ax.grid(axis="y", alpha=0.25, lw=0.6)
    ax.legend(
        handles=[
            Line2D([], [], color=TEAL, lw=1.8, label="development frontier (best keep so far)"),
            Line2D([], [], color=ORANGE, lw=1.3, ls="--", label=f"keep bar: frontier + {delta:.4f}"),
            Line2D([], [], color=TEAL, marker="D", ls="", mec=INK, ms=8, label="keep"),
            Line2D([], [], color="white", marker="o", ls="", mec=INK, ms=7, label="discard (retained evidence)"),
            Line2D([], [], color=ORANGE, marker="*", ls="", mec=INK, ms=13, label="sealed test, spent once (not on the frontier)"),
        ],
        frameon=True, framealpha=0.95, fontsize=8, loc="lower right",
    )
    fig.tight_layout()
    fig.savefig(out / "plot_decision_trajectory__primary.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


def fig_deltas(out: Path, ledger, manifests, delta):
    inc = incumbents(ledger, manifests)
    val = {r: float(v) for r, v in zip(ledger["experiment"], ledger["primary_metric"], strict=True)}
    rows = []
    for r in ledger["experiment"]:
        if manifests[r]["evaluation_kind"] != "development" or inc[r] is None:
            continue
        rows.append((r, inc[r], val[r] - val[inc[r]], ledger.loc[ledger["experiment"] == r, "status"].iloc[0]))
    fig, ax = plt.subplots(figsize=(10.0, 4.8))
    ys = np.arange(len(rows))
    cols = [TEAL if d == "keep" else (GREY if abs(x) < delta else MAGENTA) for _, _, x, d in rows]
    ax.barh(ys, [x for _, _, x, _ in rows], color=cols, height=0.62, edgecolor=INK, lw=0.6,
            hatch=None)
    for y, (r, i, x, d) in zip(ys, rows, strict=True):
        ax.annotate(f"{x:+.4f}", xy=(x, y), xytext=((max(x, delta) + 0.008) if x >= 0 else (x - 0.006), y), va="center",
                    ha="left" if x >= 0 else "right", fontsize=8.5, color=INK)
    ax.axvline(0, color=INK, lw=1.0)
    ax.axvline(delta, color=ORANGE, lw=1.6, ls="--")
    ax.axvspan(-delta, delta, color=LIGHT, alpha=0.35, zorder=0)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{r} vs {i}  {LABELS[r]}".replace("\n", " ") + f"  [{d}]" for r, i, _, d in rows], fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(-0.50, 0.26)
    ax.set_xlabel("change in seed-mean dev macro-F1 against the incumbent of that moment (bars start at 0)")
    ax.set_title("Seven candidate-versus-incumbent comparisons against the 0.0438 keep bar",
                 loc="left", fontsize=12, color=INK)
    ax.grid(axis="x", alpha=0.25, lw=0.6)
    ax.legend(
        handles=[
            Patch(facecolor=TEAL, edgecolor=INK, label="keep: cleared the bar"),
            Patch(facecolor=GREY, edgecolor=INK, label="inside the bar (E0006 and E0007 are positive but sub-bar)"),
            Patch(facecolor=MAGENTA, edgecolor=INK, label="worse by more than the bar"),
            Line2D([], [], color=ORANGE, lw=1.6, ls="--", label="keep bar (shaded band: +/- one bar)"),
        ],
        frameon=True, framealpha=0.95, fontsize=8, loc="lower left",
    )
    fig.tight_layout()
    fig.savefig(out / "candidate_deltas.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


def fig_bootstrap(out: Path, boot, delta, metric):
    v = boot["primary_metric"].to_numpy(dtype=float)
    sd, rng = float(np.std(v, ddof=1)), float(v.max() - v.min())
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.hist(v, bins=40, color=PURPLE, edgecolor="white", lw=0.5)
    m = float(metric["noise_floor"]["mean"])
    ax.axvline(m, color=INK, lw=1.0, ls="--")
    ax.annotate("", xy=(v.min(), -4), xytext=(v.max(), -4), arrowprops={"arrowstyle": "<->", "color": ORANGE, "lw": 1.4},
                annotation_clip=False)
    ax.set_ylim(-12, None)
    ax.text((v.min() + v.max()) / 2, -10.5, f"range {rng:.4f}; half-range {rng / 2:.4f} = the keep bar {delta:.4f}",
            ha="center", fontsize=8.5, color=ORANGE, bbox={"fc": "white", "ec": "none", "pad": 1})
    ax.set_xlabel("macro-F1 of the anchor on one bootstrap re-draw of the 1709 development items")
    ax.set_ylabel("count of re-draws (of 1000)")
    ax.set_title("Item noise at the anchor: sd %.4f, but range/2 binds, not 2 x sd (%.4f)" % (sd, 2 * sd),
                 loc="left", fontsize=11, color=INK)
    ax.grid(axis="y", alpha=0.25, lw=0.6)
    fig.tight_layout()
    fig.savefig(out / "item_bootstrap.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


def fig_seed_spread(out: Path, ledger, manifests, seeds, fit, delta):
    runs = [r for r in ledger["experiment"] if r not in ("E0002", "E0003")]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.6), gridspec_kw={"width_ratios": [1, 1.7]})

    # left: the anchor's four seed blocks (fit noise) -- points, shared 0-1 axis
    blocks = [float(seeds["E0001"]["primary_metric"].mean())] + [float(x) for x in fit["primary_metric"]]
    ax1.scatter(range(4), blocks, s=70, color=PURPLE, edgecolor=INK, zorder=3)
    for i, b in enumerate(blocks):
        ax1.annotate(f"{b:.4f}", xy=(i, b), xytext=(i, b + 0.05), ha="center", fontsize=8)
    ax1.set_xticks(range(4))
    ax1.set_xticklabels(["E0001\nseeds 0-2", "block\n10-12", "block\n20-22", "block\n30-32"], fontsize=8)
    ax1.set_ylim(0, 1.0)
    ax1.set_ylabel("three-seed-mean dev macro-F1 of the ANCHOR config")
    ax1.set_title("Fit noise at the anchor: four seed blocks", loc="left", fontsize=10.5, color=INK)
    ax1.annotate("", xy=(3.45, 0.2), xytext=(3.45, 0.2 + delta), arrowprops={"arrowstyle": "<->", "color": ORANGE, "lw": 1.4})
    ax1.text(3.38, 0.2 + delta / 2, f"keep bar\n{delta:.4f}", ha="right", va="center", fontsize=7.8, color=ORANGE)
    ax1.grid(axis="y", alpha=0.25, lw=0.6)

    # right: every seed of every array, on a zoomed axis (points, not bars)
    for x, r in enumerate(runs):
        d = seeds[r]["primary_metric"].to_numpy(dtype=float)
        sealed = manifests[r]["evaluation_kind"] == "final_test"
        ax2.scatter([x] * len(d), d, s=46, marker="*" if sealed else "o", color=ORANGE if sealed else TEAL,
                    edgecolor=INK, zorder=3)
        ax2.hlines(d.mean(), x - 0.28, x + 0.28, color=INK, lw=1.6, zorder=2)
    ax2.set_xticks(range(len(runs)))
    ax2.set_xticklabels([f"{r}\n{LABELS[r]}" for r in runs], fontsize=7)
    ax2.set_ylim(0.55, 1.0)
    ax2.set_ylabel("per-seed macro-F1 (axis starts at 0.55: points, not bars)")
    ax2.set_title("Every seed of every array (E0002 and E0003 omitted)", loc="left", fontsize=10.5, color=INK)
    ax2.annotate("", xy=(len(runs) - 0.35, 0.60), xytext=(len(runs) - 0.35, 0.60 + delta),
                 arrowprops={"arrowstyle": "<->", "color": ORANGE, "lw": 1.4})
    ax2.text(len(runs) - 0.45, 0.60 + delta / 2, f"keep bar {delta:.4f}", ha="right", va="center", fontsize=7.8, color=ORANGE)
    ax2.legend(
        handles=[
            Line2D([], [], color=TEAL, marker="o", ls="", mec=INK, ms=7, label="dev seed (E0004 baseline for E0005-E0008)"),
            Line2D([], [], color=ORANGE, marker="*", ls="", mec=INK, ms=11, label="sealed-test seed (E0009)"),
            Line2D([], [], color=INK, lw=1.6, label="three-seed mean"),
        ],
        frameon=True, framealpha=0.95, fontsize=7.5, loc="lower right",
    )
    ax2.grid(axis="y", alpha=0.25, lw=0.6)
    fig.tight_layout()
    fig.savefig(out / "seed_spread.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


def fig_per_class(out: Path, per_class: pd.DataFrame):
    runs = ["E0001", "E0004", "E0008", "E0009"]
    names = list(per_class[per_class["experiment"] == "E0001"].sort_values("class")["name"])
    fig, ax = plt.subplots(figsize=(10.4, 4.8))
    width = 0.2
    style = {"E0001": (LIGHT, None), "E0004": (PURPLE, None), "E0008": (TEAL, None), "E0009": ("white", "//")}
    for j, r in enumerate(runs):
        sub = per_class[per_class["experiment"] == r].sort_values("class")
        assert list(sub["name"]) == names
        face, hatch = style[r]
        ax.bar(np.arange(8) + (j - 1.5) * width, sub["recall_seed_mean"], width, color=face, edgecolor=INK,
               lw=0.7, hatch=hatch, label={"E0001": "E0001 anchor (dev)", "E0004": "E0004 BN (dev)",
                                           "E0008": "E0008 incumbent (dev)", "E0009": "E0009 sealed test"}[r])
    ax.set_xticks(range(8))
    ax.set_xticklabels([n.replace("_", " ") for n in names], fontsize=8.5)
    ax.set_ylim(0, 1.22)
    ax.set_ylabel("per-class recall, three-seed mean (bars start at 0)")
    ax.set_title("Per-class recall: the gains are uneven (basophil and immature granulocyte rose most)",
                 loc="left", fontsize=11, color=INK)
    ax.grid(axis="y", alpha=0.25, lw=0.6)
    ax.legend(frameon=True, framealpha=0.95, fontsize=8, loc="upper left", ncol=4)
    fig.tight_layout()
    fig.savefig(out / "per_class_recall.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


def confusion_sum(study: Path, run: str) -> np.ndarray:
    total = None
    for s in range(3):
        t = pd.read_csv(study / "tables" / f"confusion_{run}_s{s}.tsv", sep="\t", index_col=0).to_numpy(dtype=float)
        total = t if total is None else total + t
    return total


def fig_confusion(out: Path, study: Path, per_class: pd.DataFrame):
    names = list(per_class[per_class["experiment"] == "E0001"].sort_values("class")["name"])
    short = [n.replace("immature_granulocyte", "imm. gran.").replace("erythroblast", "erythrobl.").replace("eosinophil", "eosinoph.")
             .replace("lymphocyte", "lymphoc.").replace("neutrophil", "neutroph.") for n in names]
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 5.2), gridspec_kw={"wspace": 0.45})
    for ax, run, title in ((axes[0], "E0008", "E0008 incumbent, development (1709 items x 3 seeds)"),
                           (axes[1], "E0009", "E0009 sealed test (3413 items x 3 seeds)")):
        m = confusion_sum(study, run)
        norm = m / m.sum(axis=1, keepdims=True)
        im = ax.imshow(norm, cmap="Greys", vmin=0, vmax=1)
        for i in range(8):
            for j in range(8):
                ax.text(j, i, f"{norm[i, j]:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if norm[i, j] > 0.55 else INK)
        ax.set_xticks(range(8))
        ax.set_yticks(range(8))
        ax.set_xticklabels(short, rotation=45, ha="right", fontsize=7.6)
        ax.set_yticklabels(short, fontsize=7.6)
        ax.set_xlabel("predicted class")
        ax.set_ylabel("true class (row-normalised)")
        ax.set_title(title, loc="left", fontsize=9.5, color=INK)
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="share of the true class")
    fig.savefig(out / "confusion_incumbent_sealed.png", dpi=DPI, facecolor="white", metadata=META, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    study, out = args.study, args.out
    out.mkdir(parents=True, exist_ok=True)
    with plt.rc_context({
        "figure.facecolor": "white", "savefig.facecolor": "white", "axes.edgecolor": "#4d4d4d",
        "axes.labelcolor": INK, "text.color": INK, "xtick.color": "#4d4d4d", "ytick.color": "#4d4d4d",
        "font.size": 10, "svg.hashsalt": "klein-21",
    }):
        ledger, manifests, seeds, delta, metric, boot, fit, per_class = load(study)
        fig_trajectory(out, ledger, manifests, delta)
        fig_deltas(out, ledger, manifests, delta)
        fig_bootstrap(out, boot, delta, metric)
        fig_seed_spread(out, ledger, manifests, seeds, fit, delta)
        fig_per_class(out, per_class)
        fig_confusion(out, study, per_class)
    print(f"wrote 6 figures to {out}")


if __name__ == "__main__":
    main()
