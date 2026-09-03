"""make_figures.py — study-local exhibits for 13-charlm-fixed-budget.

Self-contained: stdlib + pandas + matplotlib only (no seaborn). Deterministic —
no randomness, no timestamps, no network — so two runs produce byte-identical
PNGs. Reads ONLY files inside the study, and every number it draws is read from a
pinned artifact and CROSS-CHECKED against a second source before it is plotted
(the numbers law: nothing invented, nothing retyped):

  results.tsv                          the ledger: every run's verified val_loss
  runs/E####/manifest.json             the printed block per run (delta_in_floors,
                                       anchor_z, steps, the verifier's own number)
  aux_metrics.tsv                      the trainer's printed keys, for cross-checks
  study.yaml                           minimum_delta, the two floor blocks
  sweeps/fit_noise.sidecar.tsv         the five anchor seeds
  sweeps/paired_floor.sidecar.tsv      the ten paired differences
  tables/learning_curves.tsv           val_loss against steps, anchor and cosine
  tables/reference_losses.tsv          uniform and unigram reference levels

Writes `tables/frontier.tsv` (one row per ledger run) and `tables/study_summary.tsv`
(the derived scalars findings quotes but no single run prints — the headroom, the
incumbent's gain, the sealed gap in floors, the parameter arithmetic), plus four PNGs
(200 dpi, white background) into --out:

  learning_curves.png   val_loss against optimizer steps, anchor vs cosine
  seed_variance.png     the measured floors: zero-based bars + a zoomed spread
  candidate_effects.png every candidate in units of the measured floor
  trajectory.png        the decision trajectory, run by run, with the sealed point

Run from the repo root:

    uv run --locked python studies/13-charlm-fixed-budget/figures/make_figures.py \\
        --study studies/13-charlm-fixed-budget --out studies/13-charlm-fixed-budget/figures
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

DPI = 200
#: Deterministic PNG metadata — matplotlib writes no timestamp; pin Software too.
META = {"Software": "make_figures.py (study 13)"}

# Colourblind-safe Dark2 family, the palette studies 09 and 10 used.
INK = "#1a1a1a"
TEAL = "#1b9e77"
ORANGE = "#d95f02"
PURPLE = "#7570b3"
MAGENTA = "#e7298a"
GREEN = "#66a61e"
GREY = "#8a8a8a"

#: Short labels for the ledger, in run order. The one idea each run changed.
LABELS = {
    "E0001": "anchor\n(constant LR)",
    "E0002": "warmup 200\n(constant LR)",
    "E0003": "weight tying",
    "E0004": "dropout 0.1",
    "E0005": "width 256",
    "E0006": "cosine decay",
    "E0007": "cosine\n+ warmup 200",
    "E0008": "sealed\n(cosine)",
}


# ---------------------------------------------------------------------------
# Reading and cross-checking
# ---------------------------------------------------------------------------
def load_everything(study: Path):
    ledger = pd.read_csv(study / "results.tsv", sep="\t")
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    metric = contract["tracks"]["primary"]["metric"]
    delta = float(metric["minimum_delta"])
    fit = metric["fit_noise"]
    paired = metric["noise_floor"]

    manifests = {}
    for row in ledger["experiment"]:
        manifests[row] = json.loads(
            (study / "runs" / row / "manifest.json").read_text(encoding="utf-8")
        )

    aux = pd.read_csv(study / "aux_metrics.tsv", sep="\t")
    curves = pd.read_csv(study / "tables" / "learning_curves.tsv", sep="\t")
    refs = pd.read_csv(study / "tables" / "reference_losses.tsv", sep="\t")
    seeds = pd.read_csv(study / "sweeps" / "fit_noise.sidecar.tsv", sep="\t")
    pairs = pd.read_csv(study / "sweeps" / "paired_floor.sidecar.tsv", sep="\t")

    # --- cross-checks: two independent sources must agree before we plot -----
    for run, manifest in manifests.items():
        ledger_value = float(ledger.loc[ledger["experiment"] == run, "primary_metric"].iloc[0])
        assert abs(ledger_value - float(manifest["primary_metric"])) < 5e-7, (
            f"{run}: results.tsv and its manifest disagree"
        )
        # The disposition is decided on the VERIFIER's number; the trainer's own
        # claim is recorded beside it and must agree inside the declared tolerance.
        assert abs(float(manifest["metric"]["verified"]) - ledger_value) < 5e-7
        trainer = aux[(aux["experiment"] == run) & (aux["metric"] == "train_steps")]
        assert not trainer.empty and int(float(trainer["value"].iloc[0])) == int(
            manifest["metrics"]["steps"]
        ), f"{run}: the trainer's step count and the checker's disagree"

    assert abs(float(fit["std"]) - float(np.std(seeds["primary_metric"], ddof=1))) < 5e-7
    assert abs(float(paired["std"]) - float(np.std(pairs["primary_metric"], ddof=1))) < 5e-7
    assert abs(delta - max(2 * float(paired["std"]), float(paired["range"]) / 2)) < 5e-7

    for recipe, expected in (("anchor", 1.563815), ("cosine", 1.518369)):
        tail = curves[curves["recipe"] == recipe].sort_values("step")["val_nats_per_char"].iloc[-1]
        assert abs(float(tail) - expected) < 5e-7, f"{recipe} curve endpoint moved"

    return ledger, manifests, aux, curves, refs, seeds, pairs, delta, fit, paired


def frontier_table(study: Path, ledger: pd.DataFrame, manifests: dict) -> pd.DataFrame:
    rows = []
    for _, row in ledger.iterrows():
        run = row["experiment"]
        m = manifests[run]
        printed = m["metrics"]
        rows.append(
            {
                "experiment": run,
                "recipe": LABELS[run].replace("\n", " "),
                "evaluation_kind": m.get("evaluation_kind", "development"),
                "disposition": row["status"],
                "val_nats_per_char": round(float(row["primary_metric"]), 6),
                "val_bits_per_char": round(float(printed["bpc"]), 6),
                "delta_in_floors": (
                    round(float(printed["delta_in_floors"]), 4)
                    if "delta_in_floors" in printed
                    else ""
                ),
                "anchor_z": (
                    round(float(printed["anchor_z"]), 4) if "anchor_z" in printed else ""
                ),
                "sealed_gap_in_fit_noise": (
                    round(float(printed["sealed_gap_in_fit_noise"]), 4)
                    if "sealed_gap_in_fit_noise" in printed
                    else ""
                ),
                "steps": int(printed["steps"]),
                "eval_context": int(printed["eval_context"]),
                "n_params": int(printed["n_params"]),
                "verifier_gap": round(float(printed["verifier_gap"]), 8),
                "reported_val_loss": round(float(printed["reported_val_loss"]), 6),
            }
        )
    table = pd.DataFrame(rows)
    (study / "tables").mkdir(exist_ok=True)
    table.to_csv(study / "tables" / "frontier.tsv", sep="\t", index=False)
    return table


def summary_table(study: Path, table: pd.DataFrame, refs: pd.DataFrame, fit: dict,
                  delta: float) -> pd.DataFrame:
    """Derived scalars: computed here from pinned inputs, so they have a home.

    Nothing in this table is typed by hand — every value is arithmetic on
    `tables/frontier.tsv`, `study.yaml`'s floor blocks,
    `tables/reference_losses.tsv` and the E0001 replication records.
    """
    row = {r["experiment"]: r for _, r in table.iterrows()}
    anchor = float(row["E0001"]["val_nats_per_char"])
    incumbent = float(row["E0006"]["val_nats_per_char"])
    sealed = float(row["E0008"]["val_nats_per_char"])
    warm = float(row["E0007"]["val_nats_per_char"])
    unigram = float(refs.loc[refs["reference"] == "unigram", "val_nats_per_char"].iloc[0])
    uniform = float(refs.loc[refs["reference"] == "uniform", "val_nats_per_char"].iloc[0])
    records = sorted((study / "runs" / "E0001" / "replications").glob("*.json"))
    full = [json.loads(path.read_text(encoding="utf-8")) for path in records]
    rerun = [r for r in full if r["mode"] == "replicate"][0]

    values = {
        "headroom_h_at_incumbent": incumbent / delta,
        "incumbent_gain_nats": anchor - incumbent,
        "incumbent_gain_floors": (anchor - incumbent) / delta,
        "sealed_minus_dev_nats": sealed - incumbent,
        "sealed_minus_dev_floors": (sealed - incumbent) / delta,
        "warmup_on_cosine_minus_incumbent_nats": warm - incumbent,
        "warmup_on_cosine_minus_incumbent_floors": (warm - incumbent) / delta,
        "anchor_below_unigram_nats": unigram - float(fit["mean"]),
        "anchor_below_uniform_nats": uniform - float(fit["mean"]),
        "incumbent_below_unigram_nats": unigram - incumbent,
        "tying_params_removed": float(row["E0001"]["n_params"] - row["E0003"]["n_params"]),
        "tying_params_share_percent": 100.0
        * (row["E0001"]["n_params"] - row["E0003"]["n_params"]) / row["E0001"]["n_params"],
        "width_params_ratio": float(row["E0005"]["n_params"]) / float(row["E0001"]["n_params"]),
        "max_verifier_gap_nats": float(table["verifier_gap"].max()),
        "replication_difference_nats": float(rerun["difference"]),
        "replication_difference_in_fit_noise_std": float(rerun["difference"]) / float(fit["std"]),
        "replication_tolerance_nats": float(rerun["tolerance"]),
        "verify_only_records": float(sum(1 for r in full if r["mode"] == "verify")),
        # What the copy-the-input control WOULD score if the harness aligned the
        # targets with the inputs instead of shifting them by one: the predictor
        # puts 0.5 on the current character, so every prediction would be right
        # with probability one half and the loss would be ln 2.
        "copy_input_loss_under_off_by_one": math.log(2.0),
    }
    out = pd.DataFrame([{"quantity": k, "value": round(v, 6)} for k, v in values.items()])
    out.to_csv(study / "tables" / "study_summary.tsv", sep="\t", index=False)
    return out


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def figure_learning_curves(out: Path, curves: pd.DataFrame, refs: pd.DataFrame, table: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    unigram = float(refs.loc[refs["reference"] == "unigram", "val_nats_per_char"].iloc[0])
    for recipe, colour, label in (
        ("anchor", PURPLE, "anchor — constant LR 3e-3"),
        ("cosine", TEAL, "cosine decay to 10% of peak"),
    ):
        sub = curves[curves["recipe"] == recipe].sort_values("step")
        ax.plot(sub["step"], sub["val_nats_per_char"], marker="o", ms=3.4, lw=1.7,
                color=colour, label=label)
    ax.axhline(unigram, color=GREY, lw=1.1, ls="--")
    ax.annotate(
        f"add-one unigram, {unigram:.6f} nats — a context-free model",
        xy=(26, unigram), xytext=(26, unigram + 0.055), color=GREY, fontsize=8,
    )
    ax.set_xscale("log")
    ax.set_xlim(20, 4200)
    ax.set_xlabel("optimizer steps (log scale) — the budget, held at 2000 for every candidate")
    ax.set_ylabel("validation loss (nats / character)")
    ax.set_title("Where the schedule earns its floors", loc="left", fontsize=12, color=INK)
    ax.set_ylim(1.42, 3.46)
    ax.grid(alpha=0.25, lw=0.6)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    final_anchor = float(curves[curves["recipe"] == "anchor"].sort_values("step")["val_nats_per_char"].iloc[-1])
    final_cosine = float(curves[curves["recipe"] == "cosine"].sort_values("step")["val_nats_per_char"].iloc[-1])
    ax.annotate(f"{final_anchor:.6f}", xy=(2000, final_anchor), xytext=(2180, final_anchor + 0.035),
                color=PURPLE, fontsize=8.5)
    ax.annotate(f"{final_cosine:.6f}", xy=(2000, final_cosine), xytext=(2180, final_cosine - 0.075),
                color=TEAL, fontsize=8.5)
    ax.text(
        0.012, 0.035,
        "measured by sweep:learning_curves — both curves are one seed, re-trained from scratch;\n"
        "the two schedules are indistinguishable until the decay starts to bite",
        transform=ax.transAxes, fontsize=7.6, color=GREY,
    )
    fig.tight_layout()
    fig.savefig(out / "learning_curves.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


def figure_seed_variance(out: Path, seeds: pd.DataFrame, pairs: pd.DataFrame, table: pd.DataFrame,
                         delta: float, fit: dict, paired: dict):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.0, 4.2), gridspec_kw={"width_ratios": [1.05, 1]})
    values = list(seeds["primary_metric"])
    labels = [json.loads(p)["seed"] for p in seeds["params_json"]]

    # Left: ZERO-BASED bars, so the eye sees how small the spread really is.
    ax1.bar(range(len(values)), values, color=PURPLE, width=0.62)
    ax1.axhline(float(fit["mean"]), color=INK, lw=1.0, ls="--")
    ax1.set_xticks(range(len(values)))
    ax1.set_xticklabels([f"seed {s}" for s in labels], fontsize=8.5)
    ax1.set_ylim(0, 1.85)
    ax1.set_ylabel("validation loss (nats / character)")
    ax1.set_title("The anchor at five seeds — zero-based bars", loc="left", fontsize=11, color=INK)
    ax1.annotate(f"mean {float(fit['mean']):.5f}", xy=(4.4, float(fit["mean"])),
                 xytext=(2.2, float(fit["mean"]) + 0.10), fontsize=8.5, color=INK)
    ax1.grid(axis="y", alpha=0.25, lw=0.6)

    # Right: the TEN paired differences — the numbers that actually set the bar.
    # Points, not bars, so a non-zero-centred axis is legitimate.
    diffs = list(pairs["primary_metric"])
    ax2.scatter(diffs, [1] * len(diffs), color=MAGENTA, s=46, zorder=3)
    ax2.axvspan(-delta, delta, color=GREY, alpha=0.18)
    ax2.axvline(0.0, color=INK, lw=1.0, ls="--")
    ax2.set_yticks([])
    ax2.set_ylim(0.42, 1.58)
    ax2.set_xlim(-0.034, 0.034)
    ax2.set_xlabel("difference between two seeds of the SAME recipe (nats/char)")
    ax2.set_title("…and the ten paired differences that set the bar", loc="left",
                  fontsize=11, color=INK)
    ax2.text(
        0.02, 0.05,
        f"shaded band = ±1 measured floor ({delta:.7f} nats)\n"
        f"paired std {float(paired['std']):.8f}, range {float(paired['range']):.6f}, k = {int(paired['k'])} pairs\n"
        f"minimum_delta = max(2·std, range/2)",
        transform=ax2.transAxes, fontsize=8, color=GREY,
    )
    ax2.grid(axis="x", alpha=0.25, lw=0.6)
    fig.tight_layout()
    fig.savefig(out / "seed_variance.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


def figure_candidate_effects(out: Path, table: pd.DataFrame, delta: float):
    dev = table[(table["evaluation_kind"] == "development") & (table["experiment"] != "E0001")]
    runs = list(dev["experiment"])
    floors = [float(v) for v in dev["delta_in_floors"]]
    disps = list(dev["disposition"])
    colours = [TEAL if f >= 1 else (MAGENTA if f <= -1 else GREY) for f in floors]

    fig, ax = plt.subplots(figsize=(10.2, 4.9))
    ax.barh(range(len(runs)), floors, color=colours, height=0.6)
    ax.axvline(0, color=INK, lw=1.0)
    ax.axvspan(-1, 1, color=GREY, alpha=0.16)
    ax.set_yticks(range(len(runs)))
    ax.set_yticklabels(
        [f"{r}  {LABELS[r]}".replace("\n", " ") + f"  [{d}]" for r, d in zip(runs, disps, strict=True)],
        fontsize=8.8,
    )
    ax.invert_yaxis()
    ax.set_xlabel(
        "improvement over the anchor's five-seed mean, in units of the measured floor\n"
        f"(one floor = {delta:.7f} nats; the shaded band is ±1 floor — inside it nothing is decidable)"
    )
    ax.set_title("Six single changes at 2000 steps, against the anchor's five-seed mean",
                 loc="left", fontsize=12, color=INK)
    for i, (f) in enumerate(floors):
        ax.annotate(f"{f:+.4f}", xy=(f, i), xytext=(f + (0.35 if f >= 0 else -0.35), i),
                    va="center", ha="left" if f >= 0 else "right", fontsize=8.5, color=INK)
    ax.set_xlim(-14.6, 6.4)
    ax.grid(axis="x", alpha=0.25, lw=0.6)
    ax.legend(
        handles=[
            Line2D([], [], color=TEAL, lw=7, label="better than the anchor by more than a floor"),
            Line2D([], [], color=GREY, lw=7, label="inside the floor — not decidable"),
            Line2D([], [], color=MAGENTA, lw=7, label="worse than the anchor by more than a floor"),
        ],
        frameon=False, fontsize=8.5, loc="upper left", title="colour = effect vs the ANCHOR;  [keep]/[discard] = the frontier decision vs the INCUMBENT",
        title_fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(out / "candidate_effects.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


def figure_trajectory(out: Path, table: pd.DataFrame, refs: pd.DataFrame, delta: float):
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    runs = list(table["experiment"])
    values = [float(v) for v in table["val_nats_per_char"]]
    kinds = list(table["evaluation_kind"])
    disps = list(table["disposition"])

    incumbent = []
    best = math.inf
    for value, kind, disp in zip(values, kinds, disps, strict=True):
        if kind == "development" and disp == "keep":
            best = min(best, value)
        incumbent.append(best)
    ax.step(range(len(runs)), incumbent, where="post", color=TEAL, lw=1.6,
            label="development incumbent")
    for i, (value, kind, disp) in enumerate(zip(values, kinds, disps, strict=True)):
        if kind == "final_test":
            ax.scatter([i], [value], color=ORANGE, s=105, marker="D", zorder=4)
        elif disp == "keep":
            ax.scatter([i], [value], color=TEAL, s=95, marker="*", zorder=4)
        else:
            ax.scatter([i], [value], color=GREY, s=52, zorder=3)
        below = kind == "development" and disp == "keep" and i > 0
        ax.annotate(f"{value:.6f}", xy=(i, value),
                    xytext=(i, value - 0.021 if below else value + 0.026),
                    ha="center", fontsize=7.6, color=INK)
    unigram = float(refs.loc[refs["reference"] == "unigram", "val_nats_per_char"].iloc[0])
    ax.set_xticks(range(len(runs)))
    ax.set_xticklabels([f"{r}\n{LABELS[r]}" for r in runs], fontsize=7.8)
    ax.set_ylabel("validation loss (nats / character)")
    ax.set_ylim(1.47, 1.80)
    ax.set_title("The decision trajectory: eight runs, one keep, one sealed look",
                 loc="left", fontsize=12, color=INK)
    ax.grid(axis="y", alpha=0.25, lw=0.6)
    ax.legend(
        handles=[
            Line2D([], [], color=TEAL, lw=1.6, label="development incumbent"),
            Line2D([], [], color=TEAL, marker="*", ls="", ms=11, label="keep"),
            Line2D([], [], color=GREY, marker="o", ls="", ms=7, label="discard (evidence, not failure)"),
            Line2D([], [], color=ORANGE, marker="D", ls="", ms=8, label="sealed final test, spent once"),
        ],
        frameon=False, fontsize=8.5, loc="upper left",
    )
    ax.text(
        0.985, 0.045,
        f"every point is the CHECKER's number; one floor = {delta:.7f} nats\n"
        f"a context-free unigram would score {unigram:.6f} — off the top of this axis",
        transform=ax.transAxes, fontsize=7.6, color=GREY, ha="right",
    )
    fig.tight_layout()
    fig.savefig(out / "trajectory.png", dpi=DPI, facecolor="white", metadata=META)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    study, out = args.study, args.out
    out.mkdir(parents=True, exist_ok=True)

    with plt.rc_context(
        {
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "axes.edgecolor": "#4d4d4d",
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": "#4d4d4d",
            "ytick.color": "#4d4d4d",
            "font.size": 10,
            "svg.hashsalt": "klein-13",
        }
    ):
        ledger, manifests, aux, curves, refs, seeds, pairs, delta, fit, paired = load_everything(study)
        table = frontier_table(study, ledger, manifests)
        summary_table(study, table, refs, fit, delta)
        figure_learning_curves(out, curves, refs, table)
        figure_seed_variance(out, seeds, pairs, table, delta, fit, paired)
        figure_candidate_effects(out, table, delta)
        figure_trajectory(out, table, refs, delta)
    print(f"wrote 4 figures to {out}, tables/frontier.tsv and tables/study_summary.tsv")


if __name__ == "__main__":
    main()
