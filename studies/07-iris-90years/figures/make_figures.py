"""make_figures.py — tutorial exhibits for 07-iris-90years.

Self-contained: stdlib + pandas + matplotlib only. Deterministic (fixed jitter
seed), no network, reads ONLY files inside this study directory:

  data/prepared/iris_hard_pair.csv   (falls back to fixtures/iris_hard_pair.csv)
  results.tsv                        (declared-split ladder + sealed one-look)
  sweeps/split_lottery.sidecar.tsv   (the 20 group-aware lottery draws)
  study.yaml                         (minimum_delta + the recorded floor stats)

Writes (150 dpi, white background):

  figures/hook_scatter.png   the hard pair in petal space, twins ringed
  figures/floor_ladder.png   lottery dots per family + anchor band + declared
                             markers + sealed line + the (sub-zero) keep bar
  figures/ladder_bars.png    declared-split ladder as keep/discard/crash bars
                             with the delta = 0.033 improvement bracket

Every number is read from the study artifacts and cross-checked against the
values recorded in study.yaml (numbers law: nothing invented, nothing retyped).

Run from the study directory:
    uv run --project ../.. --locked python figures/make_figures.py
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

STUDY = Path(__file__).resolve().parents[1]
FIGURES = STUDY / "figures"

#: ladder order (results.tsv E0001, E0003..E0008) and display labels.
FAMILIES = [
    ("anchor_lda4", "anchor_lda4\n(LDA 1936)"),
    ("logit", "logit\n(1944/58)"),
    ("knn7", "knn7\n(1951/67)"),
    ("svm_rbf", "svm_rbf\n(1995)"),
    ("hgbt", "hgbt\n(2001/19)"),
    ("lda_petal", "lda_petal\n(RQ2 ablation)"),
    ("lda_sepal", "lda_sepal\n(RQ3 control)"),
]
EXP_TO_FAMILY = {
    "E0001": "anchor_lda4",
    "E0003": "logit",
    "E0004": "knn7",
    "E0005": "svm_rbf",
    "E0006": "hgbt",
    "E0007": "lda_petal",
    "E0008": "lda_sepal",
}

# Colors chosen to stay distinguishable in grayscale via shape/hatch as well.
C_VERSICOLOR = "#4477AA"
C_VIRGINICA = "#EE6677"
C_KEEP = "#1a7f37"
C_DISCARD = "#8496a9"
C_CONTROL = "#b06f00"
C_BAND = "#c9d7e4"
C_SEALED = "#7b3294"


def load_data() -> pd.DataFrame:
    prepared = STUDY / "data" / "prepared" / "iris_hard_pair.csv"
    fixture = STUDY / "fixtures" / "iris_hard_pair.csv"
    path = prepared if prepared.is_file() else fixture
    df = pd.read_csv(path)
    assert len(df) == 100 and int(df["is_virginica"].sum()) == 50
    return df


def load_results() -> pd.DataFrame:
    df = pd.read_csv(STUDY / "results.tsv", sep="\t")
    assert list(df["experiment"]) == [f"E{i:04d}" for i in range(1, 10)]
    return df


def load_lottery() -> pd.DataFrame:
    df = pd.read_csv(STUDY / "sweeps" / "split_lottery.sidecar.tsv", sep="\t")
    params = df["params_json"].map(json.loads)
    df["draw"] = [p["draw"] for p in params]
    df["family"] = [p["family"] for p in params]
    assert (df["status"] == "ok").all() and len(df) == 140
    return df


def load_contract_floor() -> tuple[float, float, float]:
    """(minimum_delta, recorded anchor mean, recorded anchor std) from study.yaml."""
    text = (STUDY / "study.yaml").read_text(encoding="utf-8")
    delta = float(re.search(r"minimum_delta:\s*([0-9.]+)", text).group(1))
    mean = float(re.search(r"^\s*mean:\s*([0-9.eE+-]+)", text, re.M).group(1))
    std = float(re.search(r"^\s*std:\s*([0-9.eE+-]+)", text, re.M).group(1))
    return delta, mean, std


def declared_ladder(results: pd.DataFrame) -> dict[str, float]:
    """family -> declared-split val_brier, from results.tsv (E0002 excluded: NA)."""
    out: dict[str, float] = {}
    for _, row in results.iterrows():
        family = EXP_TO_FAMILY.get(row["experiment"])
        if family is not None:
            out[family] = float(row["primary_metric"])
    return out


def fig_hook_scatter(df: pd.DataFrame) -> None:
    rng = random.Random(20260828)  # deterministic jitter on the 0.1 cm grid
    fig, ax = plt.subplots(figsize=(8.0, 5.6))

    versicolor = df[df["is_virginica"] == 0]
    virginica = df[df["is_virginica"] == 1]

    # Overlap region of the two classes' petal ranges — computed from the data.
    x_lo = max(versicolor["petal_length_cm"].min(), virginica["petal_length_cm"].min())
    x_hi = min(versicolor["petal_length_cm"].max(), virginica["petal_length_cm"].max())
    y_lo = max(versicolor["petal_width_cm"].min(), virginica["petal_width_cm"].min())
    y_hi = min(versicolor["petal_width_cm"].max(), virginica["petal_width_cm"].max())
    ax.add_patch(
        Rectangle(
            (x_lo, y_lo), x_hi - x_lo, y_hi - y_lo,
            facecolor="#bdbdbd", alpha=0.35, edgecolor="#757575",
            linestyle="--", linewidth=1.0, zorder=1,
        )
    )
    ax.annotate(
        "overlap region", xy=(x_lo + 0.03, y_hi - 0.02),
        fontsize=10, color="#424242", va="top",
    )

    def jitter(values: pd.Series) -> list[float]:
        return [v + rng.uniform(-0.02, 0.02) for v in values]

    ax.scatter(
        jitter(versicolor["petal_length_cm"]), jitter(versicolor["petal_width_cm"]),
        s=42, marker="o", facecolor=C_VERSICOLOR, edgecolor="white",
        linewidth=0.5, alpha=0.9, zorder=3, label="versicolor (n=50)",
    )
    ax.scatter(
        jitter(virginica["petal_length_cm"]), jitter(virginica["petal_width_cm"]),
        s=48, marker="^", facecolor=C_VIRGINICA, edgecolor="white",
        linewidth=0.5, alpha=0.9, zorder=3, label="virginica (n=50)",
    )

    # The printed twins — both rows sit on the identical point, plotted unjittered.
    twins = df[df["group_id"] == "twins102-143"]
    assert len(twins) == 2
    tx = float(twins["petal_length_cm"].iloc[0])
    ty = float(twins["petal_width_cm"].iloc[0])
    assert (twins["petal_length_cm"] == tx).all() and (twins["petal_width_cm"] == ty).all()
    ax.scatter(
        [tx], [ty], s=340, facecolor="none", edgecolor="black",
        linewidth=2.2, zorder=4, label="printed twins (2 rows, 1 point)",
    )
    ax.annotate(
        "printed twins (rows 102/143)",
        xy=(tx, ty), xytext=(tx - 1.55, ty + 0.38),
        fontsize=10.5, fontweight="bold",
        arrowprops=dict(arrowstyle="->", linewidth=1.2, color="black"),
    )

    ax.set_xlabel("petal length (cm) — 0.1 cm grid, points jittered ±0.02 cm for visibility")
    ax.set_ylabel("petal width (cm)")
    ax.set_title("Fisher's hard pair: 100 flowers, versicolor vs virginica")
    ax.legend(loc="lower right", fontsize=9.5, framealpha=0.95)
    ax.grid(True, linewidth=0.4, alpha=0.4)
    fig.tight_layout()
    fig.savefig(FIGURES / "hook_scatter.png", dpi=150, facecolor="white")
    plt.close(fig)


def fig_floor_ladder(
    lottery: pd.DataFrame, declared: dict[str, float],
    sealed: float, delta: float, rec_mean: float, rec_std: float,
) -> None:
    rng = random.Random(20260828)
    anchor = lottery[lottery["family"] == "anchor_lda4"]["primary_metric"]
    mean = float(anchor.mean())
    std = float(anchor.std(ddof=1))  # sample std — reproduces study.yaml's 0.0163144
    # Numbers law: the sidecar must reproduce the floor stats recorded in study.yaml.
    assert abs(mean - rec_mean) < 1e-6, (mean, rec_mean)
    assert abs(std - rec_std) < 1e-6, (std, rec_std)

    fig, ax = plt.subplots(figsize=(9.0, 5.8))

    # Anchor mean ± 2*std band, shaded across the whole plot.
    ax.axhspan(
        mean - 2 * std, mean + 2 * std, color=C_BAND, alpha=0.55, zorder=1,
        label=f"anchor mean ± 2×std over 20 draws ({mean:.4f} ± {2 * std:.4f})",
    )
    ax.axhline(mean, color="#5b7a99", linewidth=1.0, linestyle=":", zorder=2)

    # Sealed one-look and the keep bar.
    ax.axhline(
        sealed, color=C_SEALED, linewidth=1.6, linestyle="--", zorder=2,
        label=f"sealed one-look (E0009) = {sealed:.6f}",
    )
    keep_bar = declared["anchor_lda4"] - delta
    ax.axhline(
        keep_bar, color="#c62828", linewidth=1.6, linestyle="-.", zorder=2,
        label=f"keep bar = anchor − δ = {keep_bar:.6f} (below zero: unreachable, Brier ≥ 0)",
    )
    ax.axhline(0.0, color="#9e9e9e", linewidth=0.8, zorder=1)

    for i, (family, label) in enumerate(FAMILIES):
        values = lottery[lottery["family"] == family]["primary_metric"]
        assert len(values) == 20
        xs = [i + rng.uniform(-0.14, 0.14) for _ in range(len(values))]
        ax.scatter(
            xs, values, s=16, facecolor="#37474f", alpha=0.55,
            edgecolor="none", zorder=3,
            label="20 lottery draws per family" if i == 0 else None,
        )
        ax.scatter(
            [i], [declared[family]], s=150, marker="D",
            facecolor=C_KEEP if family == "anchor_lda4" else "#ffffff",
            edgecolor="black", linewidth=1.4, zorder=4,
            label="declared split (the value the ledger judges)" if i == 0 else None,
        )

    ax.set_xticks(range(len(FAMILIES)))
    ax.set_xticklabels([label for _, label in FAMILIES], fontsize=9)
    ax.set_ylabel("development val_brier (lower is better)")
    ax.set_title(
        "The split lottery: every family, 20 group-aware re-draws of the 80 non-sealed rows\n"
        "No challenger's improvement crosses the floor — the keep bar sits below zero"
    )
    ax.set_ylim(-0.02, 0.33)
    ax.grid(True, axis="y", linewidth=0.4, alpha=0.4)
    ax.legend(loc="upper left", fontsize=8.6, framealpha=0.95)
    fig.tight_layout()
    fig.savefig(FIGURES / "floor_ladder.png", dpi=150, facecolor="white")
    plt.close(fig)


def fig_ladder_bars(results: pd.DataFrame, delta: float) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 5.6))

    rows = []  # (label, value or None, color, hatch, note)
    anchor_value = None
    for _, row in results.iterrows():
        exp = row["experiment"]
        if exp == "E0009":
            continue  # sealed evidence never enters the adaptive frontier
        if exp == "E0002":
            rows.append(("E0002  species column\n(registered crash)", None,
                         "#ffffff", "///", "crash — NA (exit 1, refused by design)"))
            continue
        family = EXP_TO_FAMILY[exp]
        value = float(row["primary_metric"])
        if exp == "E0001":
            anchor_value = value
            color, hatch, note = C_KEEP, None, f"keep — frontier {value:.6f}"
        elif exp == "E0008":
            x = (value - anchor_value) / delta
            color, hatch, note = C_CONTROL, None, f"discard — {value:.6f}  (+{x:.2f}×δ, control)"
        else:
            x = (value - anchor_value) / delta
            color, hatch, note = C_DISCARD, None, f"discard — {value:.6f}  (+{x:.2f}×δ)"
        era = FAMILIES[[f for f, _ in FAMILIES].index(family)][1].split("\n")[1]
        rows.append((f"{exp}  {family} {era}", value, color, hatch, note))

    xmax = 0.20
    ys = range(len(rows))[::-1]  # E0001 on top
    for y, (label, value, color, hatch, note) in zip(ys, rows):
        if value is None:
            ax.barh(y, xmax, height=0.62, facecolor=color, edgecolor="#c62828",
                    hatch=hatch, linewidth=1.2, alpha=0.7, zorder=2)
            ax.text(0.002, y, note, va="center", fontsize=9.5, color="#c62828",
                    fontweight="bold", zorder=3)
        else:
            ax.barh(y, value, height=0.62, facecolor=color, edgecolor="black",
                    linewidth=0.8, zorder=2)
            if value > 0.12:  # long bar: annotate inside so nothing leaves the axes
                ax.text(value - 0.003, y, note, va="center", ha="right",
                        fontsize=9.5, color="white", fontweight="bold", zorder=3)
            else:
                ax.text(value + 0.002, y, note, va="center", fontsize=9.5, zorder=3)

    # The improvement bracket: a keep required anchor − δ, which is negative.
    y_anchor = max(ys)
    keep_bar = anchor_value - delta
    ax.annotate(
        "", xy=(keep_bar, y_anchor + 0.42), xytext=(anchor_value, y_anchor + 0.42),
        arrowprops=dict(arrowstyle="->", linewidth=1.6, color="#c62828"),
    )
    ax.text(
        (anchor_value + keep_bar) / 2, y_anchor + 0.62,
        f"δ = {delta} (measured floor): a keep needed val_brier ≤ {keep_bar:.6f} — below zero",
        ha="center", fontsize=9.5, color="#c62828",
    )
    ax.axvline(keep_bar, color="#c62828", linewidth=1.4, linestyle="-.", zorder=1)
    ax.axvline(0.0, color="#616161", linewidth=0.9, zorder=1)

    ax.set_yticks(list(ys))
    ax.set_yticklabels([label for label, *_ in rows], fontsize=9.5)
    ax.set_xlim(-0.045, xmax)
    ax.set_ylim(-0.6, len(rows) - 0.1)
    ax.set_xlabel("development val_brier, declared split seed 20260828 (lower is better; bars start at 0)")
    ax.set_title("The 90-year ladder: 1 keep, 1 registered crash, 6 discards")
    fig.legend(
        handles=[
            Patch(facecolor=C_KEEP, edgecolor="black", label="keep (anchor, 1936)"),
            Patch(facecolor=C_DISCARD, edgecolor="black", label="discard (challenger / ablation)"),
            Patch(facecolor=C_CONTROL, edgecolor="black", label="discard (positive control)"),
            Patch(facecolor="#ffffff", edgecolor="#c62828", hatch="///", label="registered crash (NA)"),
            Line2D([], [], color="#c62828", linestyle="-.", label="keep bar (anchor − δ)"),
        ],
        loc="lower center", ncol=3, fontsize=8.8, frameon=False,
        bbox_to_anchor=(0.5, 0.0),
    )
    ax.grid(True, axis="x", linewidth=0.4, alpha=0.4)
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.savefig(FIGURES / "ladder_bars.png", dpi=150, facecolor="white")
    plt.close(fig)


def main() -> None:
    plt.rcParams.update({"font.size": 10.5, "figure.facecolor": "white",
                         "axes.facecolor": "white", "savefig.facecolor": "white"})
    df = load_data()
    results = load_results()
    lottery = load_lottery()
    delta, rec_mean, rec_std = load_contract_floor()
    assert delta == 0.033, delta

    declared = declared_ladder(results)
    # C6 guard: lottery draw 1 IS the declared split — every family must agree.
    draw1 = {r["family"]: float(r["primary_metric"])
             for _, r in lottery[lottery["draw"] == 1].iterrows()}
    for family, value in declared.items():
        assert abs(draw1[family] - value) < 1e-9, (family, draw1[family], value)

    sealed = float(results.loc[results["experiment"] == "E0009", "primary_metric"].iloc[0])

    fig_hook_scatter(df)
    fig_floor_ladder(lottery, declared, sealed, delta, rec_mean, rec_std)
    fig_ladder_bars(results, delta)
    for name in ("hook_scatter.png", "floor_ladder.png", "ladder_bars.png"):
        path = FIGURES / name
        print(f"wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
