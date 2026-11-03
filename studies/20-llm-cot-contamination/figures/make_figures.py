"""make_figures.py -- study-local exhibits for 20-llm-cot-contamination.

Deterministic (no randomness, no timestamps, no network, no model call). Reads ONLY
committed files inside the study:

  tables/cot_gain_E0002|E0004|E0005.tsv     per-item 0/1 scores, both arms
  tables/contamination_E0003|E0006.tsv      per-template original score and twin mean
  tables/synthesis_controls.tsv             the post-hoc planted-gain controls
  calls/E000*-000.jsonl.gz                  the pinned call-ledger shards (token counts)
  runs/E####/manifest.json                  printed metric block, track, disposition

Nothing is recomputed that a pinned artifact already holds: the intervals come from the
manifests' printed blocks, the planted-gain intervals from the controls table.

Writes into --out (200 dpi PNGs, fixed metadata):

  decision_trajectory__cot_gain.png, decision_trajectory__contamination.png
  paired_outcomes.png    the discordant items of every cot_gain cell
  accuracy_by_block.png  exact-match per arm per item block (zero-based)
  tokens_by_arm.png      output tokens per call, direct arm against CoT arm
  gap_per_template.png   the per-template gap, development and sealed
  planted_gain.png       observed gains beside the single seeded plants

Run from the repo root:

    uv run --no-sync python studies/20-llm-cot-contamination/figures/make_figures.py \\
        --study studies/20-llm-cot-contamination --out studies/20-llm-cot-contamination/figures
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

DPI = 200
META = {"Software": "make_figures.py (study 20)"}
INK, TEAL, ORANGE, PURPLE, GREY = "#1a1a1a", "#1b9e77", "#d95f02", "#7570b3", "#8a8a8a"

#: The six ledger cells: id -> short label (the one idea each cell measured).
LABELS = {
    "E0001": "E0001 public\n(crash)",
    "E0002": "E0002 public\nanchor",
    "E0003": "E0003 originals\nvs dev twins",
    "E0004": "E0004\ndev twins",
    "E0005": "E0005 sealed\ntwins",
    "E0006": "E0006 sealed\ngap",
}
THRESHOLD = {"cot_gain": 0.10, "contamination": 0.05}  # the registered rule values (study.yaml)


def _style() -> None:
    plt.rcParams.update({
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "axes.edgecolor": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
        "text.color": INK, "font.size": 10, "axes.titlesize": 11, "axes.spines.top": False,
        "axes.spines.right": False, "legend.frameon": False,
    })


def _save(fig, out: Path, name: str) -> None:
    fig.savefig(out / name, dpi=DPI, metadata=META, bbox_inches="tight")
    plt.close(fig)


def read_manifests(study: Path) -> dict[str, dict]:
    return {p.parent.name: json.loads(p.read_text()) for p in sorted((study / "runs").glob("E*/manifest.json"))}


def read_shards(study: Path) -> pd.DataFrame:
    rows, seen = [], set()
    for shard in sorted((study / "calls").glob("*.jsonl.gz")):
        with gzip.open(shard, "rt", encoding="utf-8") as handle:
            for line in handle:
                rec = json.loads(line)
                if rec["key"] in seen:
                    continue
                seen.add(rec["key"])
                prompt = rec["request"]["messages"][0]["content"]
                reply = rec["response"]["choices"][0]["message"]["content"] or ""
                rows.append({
                    "arm": "direct" if prompt.startswith("Answer with the final number only") else "cot",
                    "tokens_out": rec["tokens_out"],
                    "bare": bool(re.fullmatch(r"\s*-?[\d,]+(\.\d+)?\s*", reply)),
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
def fig_trajectory(manifests: dict[str, dict], track: str, out: Path) -> None:
    """One registered track: the measured value per cell with its interval; sealed starred."""
    rows = [(k, m) for k, m in manifests.items() if m["track"] == track]
    name = rows[0][1]["metric_name"]
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    ordinals = {k: int(k[1:]) for k, _ in rows}
    crashes = [k for k, m in rows if m["disposition"] == "crash"]
    for k, m in rows:
        if m["disposition"] == "crash":
            continue
        met, x = m["metrics"], ordinals[k]
        sealed = m["evaluation_kind"] == "final_test"
        ax.errorbar(x, m["primary_metric"], yerr=[[m["primary_metric"] - met["ci_low"]],
                    [met["ci_high"] - m["primary_metric"]]], color=INK, capsize=4, lw=1.2, zorder=2)
        ax.scatter([x], [m["primary_metric"]], s=150 if sealed else 55, marker="*" if sealed else "o",
                   color=ORANGE if sealed else TEAL, edgecolor=INK, zorder=3)
    for k in crashes:
        ax.plot([ordinals[k]], [0], marker="|", ms=26, color=GREY, mew=2.2, zorder=1, ls="none",
                transform=ax.get_xaxis_transform(), clip_on=False)
    thr = THRESHOLD[track]
    ax.axhline(0, color=INK, lw=1.0)
    ax.axhline(thr, color=PURPLE, lw=1.3, ls="--")
    ax.text(0.99, thr, f"registered rule value {thr:.2f}", ha="right", va="bottom",
            transform=ax.get_yaxis_transform(), color=PURPLE, fontsize=9)
    lo = min(m["metrics"]["ci_low"] for _, m in rows if m["disposition"] != "crash")
    ax.set_ylim(min(-0.08, lo - 0.02), thr + 0.03)
    ax.set_xlim(min(ordinals.values()) - 0.6, max(ordinals.values()) + 0.6)
    ax.set_xticks(sorted(ordinals.values()))
    ax.set_xticklabels([LABELS[k] for k in sorted(ordinals)], fontsize=8)
    ax.set_xlabel("Experiment (ledger order)")
    ax.set_ylabel(f"{name} (exact-match difference, 0 = no difference)")
    ax.set_title(f"Track {track}: registered cells, measured once each; no frontier climbs")
    handles = [Line2D([], [], marker="o", ls="none", color=TEAL, mec=INK, label="development cell + 95% interval"),
               Line2D([], [], marker="*", ls="none", ms=13, color=ORANGE, mec=INK, label="sealed confirmation cell + 95% interval"),
               Line2D([], [], ls="--", color=PURPLE, label="registered prediction rule value")]
    if crashes:
        handles.append(Line2D([], [], marker="|", ms=14, ls="none", color=GREY, mew=2.2, label="crash (no value)"))
    ax.legend(handles=handles, loc="lower left" if track == "contamination" else "upper left",
              bbox_to_anchor=(0.0, 0.0) if track == "contamination" else (0.0, 0.86), fontsize=8)
    _save(fig, out, f"decision_trajectory__{track}.png")


def fig_paired(study: Path, out: Path) -> None:
    cells = [("E0002", "public GSM8K\n(300 items)"), ("E0004", "development twins\n(200 items)"),
             ("E0005", "sealed twins\n(200 items)")]
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    width = 0.36
    for i, (cell, label) in enumerate(cells):
        t = pd.read_csv(study / "tables" / f"cot_gain_{cell}.tsv", sep="\t")
        cot_only = int(((t.score_cot == 1) & (t.score_direct == 0)).sum())
        dir_only = int(((t.score_cot == 0) & (t.score_direct == 1)).sum())
        both_wrong = int(((t.score_cot == 0) & (t.score_direct == 0)).sum())
        both_right = int(((t.score_cot == 1) & (t.score_direct == 1)).sum())
        ax.bar(i - width / 2, cot_only, width, color=TEAL, edgecolor=INK, label="only CoT right" if i == 0 else None)
        ax.bar(i + width / 2, dir_only, width, color="white", edgecolor=INK, hatch="//",
               label="only direct right" if i == 0 else None)
        ax.text(i - width / 2, cot_only + 0.15, str(cot_only), ha="center", fontsize=9)
        ax.text(i + width / 2, dir_only + 0.15, str(dir_only), ha="center", fontsize=9)
        cells[i] = (cell, f"{label}\nboth right {both_right}, both wrong {both_wrong}")
    ax.set_xticks(range(len(cells)))
    ax.set_xticklabels([c[1] for c in cells])
    ax.set_ylim(0, 8)
    ax.set_ylabel("Items on which the two arms disagree (count)")
    ax.set_xlabel("Cell (cot_gain track; concordant items shown beneath each pair)")
    ax.set_title("Paired outcomes: a handful of disagreements, in both directions")
    ax.legend(loc="upper right", fontsize=9)
    _save(fig, out, "paired_outcomes.png")


def fig_accuracy(study: Path, out: Path) -> None:
    pub = pd.read_csv(study / "tables" / "cot_gain_E0002.tsv", sep="\t")
    dev = pd.read_csv(study / "tables" / "cot_gain_E0004.tsv", sep="\t")
    sea = pd.read_csv(study / "tables" / "cot_gain_E0005.tsv", sep="\t")
    org = pd.read_csv(study / "tables" / "contamination_E0003.tsv", sep="\t")
    blocks = ["public GSM8K\n(presumed seen)", "50 template\noriginals", "development\ntwins", "sealed\ntwins"]
    direct = [pub.score_direct.mean(), np.nan, dev.score_direct.mean(), sea.score_direct.mean()]
    cot = [pub.score_cot.mean(), org.score_original.mean(), dev.score_cot.mean(), sea.score_cot.mean()]
    x = np.arange(len(blocks))
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    w = 0.38
    for xi, v in zip(x, direct):
        if not np.isnan(v):
            ax.bar(xi - w / 2, v, w, color="white", edgecolor=INK, hatch="//")
            ax.text(xi - w / 2, v + 0.01, f"{v:.3f}".rstrip("0").rstrip("."), ha="center", fontsize=8)
    ax.text(x[1] - w / 2, 0.03, "not run", ha="center", fontsize=8, color=GREY, rotation=90, va="bottom")
    for xi, v in zip(x, cot):
        ax.bar(xi + w / 2, v, w, color=TEAL, edgecolor=INK)
        ax.text(xi + w / 2, v + 0.01, f"{v:.3f}".rstrip("0").rstrip("."), ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(blocks, fontsize=9)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Exact-match (fraction of items answered correctly)")
    ax.set_xlabel("Item block (qwen-flash-2025-07-28, temperature 0, thinking off)")
    ax.set_title("Both arms sit near the ceiling on every block")
    ax.legend(handles=[Line2D([], [], marker="s", ls="none", mfc="white", mec=INK, label="direct arm (registered number-only prompt)"),
                       Line2D([], [], marker="s", ls="none", color=TEAL, mec=INK, label="CoT arm")],
              loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=8)
    _save(fig, out, "accuracy_by_block.png")


def fig_tokens(study: Path, out: Path) -> None:
    calls = read_shards(study)
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    bins = np.arange(0, 1100, 40)
    styles = {"direct": (ORANGE, "-", "direct arm (told: number only)"), "cot": (TEAL, "--", "CoT arm (told: step by step)")}
    for arm, (color, ls, label) in styles.items():
        tok = calls.loc[calls.arm == arm, "tokens_out"].clip(upper=1024)
        ax.hist(tok, bins=bins, histtype="step", lw=2, color=color, ls=ls, label=f"{label}, {len(tok)} calls")
        ax.axvline(float(tok.median()), color=color, ls=ls, lw=1, alpha=0.7)
    bare = int(calls.loc[calls.arm == "direct", "bare"].sum())
    ax.text(0.98, 0.42, f"bare-number replies, direct arm: {bare}", transform=ax.transAxes, ha="right", fontsize=9)
    ax.set_xlabel("Output tokens per call (capped at max_tokens 1024; vertical lines = medians)")
    ax.set_ylabel("Calls (count)")
    ax.set_title("The 'direct' arm writes its working too: its replies are CoT-sized, not number-sized")
    ax.legend(loc="upper right", fontsize=8)
    _save(fig, out, "tokens_by_arm.png")


def fig_gap(study: Path, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 4.0), sharey=True)
    edges = np.array([-1.0, -0.6, -0.2, 0.2, 0.6, 1.01])
    labels = ["-1 to -0.6", "-0.6 to -0.2", "about 0", "0.2 to 0.6", "0.6 to 1"]
    for ax, cell, title in zip(axes, ["E0003", "E0006"], ["development (E0003)", "sealed (E0006)"]):
        t = pd.read_csv(study / "tables" / f"contamination_{cell}.tsv", sep="\t")
        gap = (t.score_original - t.twin_mean).to_numpy()
        counts, _ = np.histogram(gap, bins=edges)
        ax.bar(range(len(counts)), counts, color=TEAL, edgecolor=INK)
        for i, c in enumerate(counts):
            ax.text(i, c + 0.6, str(int(c)), ha="center", fontsize=9)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        ax.set_title(title)
        ax.set_ylim(0, 56)
    axes[0].set_ylabel("Templates (count)")
    fig.supxlabel("Per-template gap: original's score minus the mean score of its four twins", fontsize=10)
    fig.suptitle("Almost every template shows no gap; the mean gap is carried by a few", y=1.0)
    fig.tight_layout()
    _save(fig, out, "gap_per_template.png")


def fig_planted(study: Path, manifests: dict[str, dict], out: Path) -> None:
    c = pd.read_csv(study / "tables" / "synthesis_controls.tsv", sep="\t")

    def val(control: str, cell: str, q: str) -> float:
        return float(c[(c.control == control) & (c.cell == cell) & (c.quantity == q)].value.iloc[0])

    cells = [("E0002", "public"), ("E0004", "development twins"), ("E0005", "sealed twins")]
    fig, ax = plt.subplots(figsize=(7.8, 4.4))
    offsets = {"observed": -0.22, "plant 0.05": 0.0, "plant 0.10": 0.22}
    marks = {"observed": ("o", TEAL), "plant 0.05": ("s", ORANGE), "plant 0.10": ("D", PURPLE)}
    for i, (cell, label) in enumerate(cells):
        m = manifests[cell]["metrics"]
        entries = {
            "observed": (manifests[cell]["primary_metric"], m["ci_low"], m["ci_high"]),
            "plant 0.05": tuple(val("positive_plant_gain_0.05", cell, q) for q in ("em_gain", "ci95_low", "ci95_high")),
            "plant 0.10": tuple(val("positive_plant_gain_0.10", cell, q) for q in ("em_gain", "ci95_low", "ci95_high")),
        }
        for key, (mid, lo, hi) in entries.items():
            y = i + offsets[key]
            mk, col = marks[key]
            ax.plot([lo, hi], [y, y], color=INK, lw=1.4)
            ax.plot([mid], [y], marker=mk, color=col, mec=INK, ms=8, ls="none")
    ax.axvline(0, color=INK, lw=1.0)
    ax.set_yticks(range(len(cells)))
    ax.set_yticklabels([x[1] for x in cells])
    ax.invert_yaxis()
    ax.set_xlim(-0.1, 0.16)
    ax.set_xlabel("em_gain, CoT minus direct (exact-match difference; vertical line = 0)")
    ax.set_ylabel("cot_gain cell")
    ax.set_title("Post-hoc controls: the observed gain beside one seeded plant per size, per block")
    ax.legend(handles=[Line2D([], [], marker=marks[k][0], color=marks[k][1], mec=INK, ls="none", label=lab)
                       for k, lab in [("observed", "observed gain + 95% interval"),
                                      ("plant 0.05", "single seeded plant of 0.05"),
                                      ("plant 0.10", "single seeded plant of 0.10")]],
              loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3, fontsize=8)
    _save(fig, out, "planted_gain.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--study", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    study = args.study.resolve()
    out = (args.out or study / "figures").resolve()
    out.mkdir(parents=True, exist_ok=True)
    _style()
    manifests = read_manifests(study)
    for track in ("cot_gain", "contamination"):
        fig_trajectory(manifests, track, out)
    fig_paired(study, out)
    fig_accuracy(study, out)
    fig_tokens(study, out)
    fig_gap(study, out)
    fig_planted(study, manifests, out)


if __name__ == "__main__":
    main()
