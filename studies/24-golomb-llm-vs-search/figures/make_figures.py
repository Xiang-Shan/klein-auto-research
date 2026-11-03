"""make_figures.py — the exhibits for 24-golomb-llm-vs-search.

Deterministic: no randomness, no timestamps, no network, no model call. Re-running it
overwrites the same bytes, the property the tutorial's inlined figures depend on.

Reads only committed study evidence:

  tables/synthesis_pairs.tsv      one row per (arm, order, trial): optimum, best verified
                                  length, gap, matched, first-match proposal, valid and
                                  unparsed counts (written by tables/synthesis_derive.py)
  tables/synthesis_summary.tsv    the aggregates the figures are cross-checked against
  tables/solution_E000{1,4,5,6}.json   the artifacts the declared verifier scored
  calls/E0006-000.jsonl.gz        the pinned call-ledger shard of the sealed LLM cell
  runs/E####/manifest.json        dispositions, usage (calls, tokens), metric.verified
  aux_metrics.tsv                 wall_seconds per run (the pinned `aux` artifact)

Writes into --out (default: this study's figures/):

  plot_decision_trajectory__search.png   the engine's decision trajectory, one per track:
  plot_decision_trajectory__llm.png      registered cells, the two transport crashes on the
                                         rug, the sealed cell as a star off the frontier
  gap_by_order.png        best verified length against the tabulated optimum per order and
                          arm, and the gap on a zero-based axis
  first_match_proposals.png   LLM arm: the proposal at which each development pair first held
                          a verified ruler at the tabulated length
  valid_vs_unparsed.png   LLM arm, by order: unparsed replies and valid rulers
  compute_vs_budget.png   the budget that was matched (verifier calls) against the cost that
                          was not (wall-clock seconds, model tokens)

Every number drawn is read from an artifact and asserted equal to its pinned counterpart
(the numbers law: nothing retyped). This script re-derives no objective: it plots what
`verify.py` scored, as the tables record it.

Run from the repo root:

    KLEIN_OFFLINE=1 uv run --no-sync python studies/24-golomb-llm-vs-search/figures/make_figures.py \
        --study studies/24-golomb-llm-vs-search --out <dir>
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import yaml  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from kleinlib import figures as klein_figures  # noqa: E402
from kleinlib import workflow  # noqa: E402

DPI = klein_figures.DPI
META = {"Software": "make_figures.py (study 24-golomb-llm-vs-search)"}

INK = klein_figures.CHROME["primary_ink"]
MUTED = klein_figures.CHROME["muted"]
GRID = klein_figures.CHROME["gridline"]
SEARCH = klein_figures.CATEGORICAL[0]    # blue
LLM = klein_figures.CATEGORICAL[7]       # orange
OPT = klein_figures.CATEGORICAL[4]       # violet: the tabulated optimum, never an arm colour
CRASH = klein_figures.STATUS_COLOR["crash"]

DEV_ORDERS = (8, 9, 10, 11)
SEALED_ORDERS = (12, 13)
ORDERS = DEV_ORDERS + SEALED_ORDERS
RUNS = {  # (arm, lane) -> the run that measured it
    ("search", "development"): "E0001",
    ("llm", "development"): "E0004",
    ("search", "sealed"): "E0005",
    ("llm", "sealed"): "E0006",
}


def _fail(message: str) -> None:
    raise SystemExit(f"make_figures: {message}")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def save(fig: plt.Figure, out: Path, name: str, *, top: float = 1.0) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    fig.tight_layout(rect=(0.0, 0.0, 1.0, top))
    fig.savefig(path, dpi=DPI, metadata=META)
    plt.close(fig)
    print(f"wrote {path}")
    return path


def load_pairs(study: Path) -> list[dict]:
    rows = []
    for row in read_tsv(study / "tables" / "synthesis_pairs.tsv"):
        def num(key: str) -> int | None:
            return None if row[key] == "NA" else int(row[key])

        rows.append({
            "exp": row["experiment"], "arm": row["arm"], "lane": row["lane"],
            "order": int(row["order"]), "trial": int(row["trial"]),
            "optimum": int(row["optimum"]), "best": num("best_length"), "gap": num("gap"),
            "matched": int(row["matched"]), "first": num("first_match_index"),
            "evals": int(row["evaluations"]), "valid": num("valid_rulers"),
            "unparsed": num("unparsed_replies"),
        })
    return rows


def load_summary(study: Path) -> dict[str, float]:
    return {r["metric"]: float(r["value"]) for r in read_tsv(study / "tables" / "synthesis_summary.tsv")}


def cross_check(study: Path, pairs: list[dict], summary: dict[str, float]) -> None:
    """The figures' inputs must equal the pinned records, or no figure is drawn."""
    for (arm, lane), exp in RUNS.items():
        sol = json.loads((study / "tables" / f"solution_{exp}.json").read_text(encoding="utf-8"))
        mine = [p for p in pairs if p["exp"] == exp]
        if len(mine) != len(sol["pairs"]):
            _fail(f"{exp}: {len(mine)} table rows but {len(sol['pairs'])} artifact pairs")
        for art in sol["pairs"]:
            row = next(p for p in mine if p["order"] == art["order"] and p["trial"] == art["trial"])
            if row["best"] != art["best_length"]:
                _fail(f"{exp} n={art['order']} t={art['trial']}: table {row['best']} != artifact {art['best_length']}")
        matched = sum(p["matched"] for p in mine)
        if matched != int(summary[f"{exp}_matched"]):
            _fail(f"{exp}: matched {matched} != summary {summary[f'{exp}_matched']}")
        manifest = json.loads((study / "runs" / exp / "manifest.json").read_text(encoding="utf-8"))
        if float(manifest["metric"]["verified"]) != float(matched):
            _fail(f"{exp}: manifest verified {manifest['metric']['verified']} != table {matched}")
    for order in ORDERS:
        exp = "E0001" if order in DEV_ORDERS else "E0005"
        gaps = [p["gap"] for p in pairs if p["exp"] == exp and p["order"] == order]
        mean = round(sum(gaps) / len(gaps), 3)
        if abs(mean - summary[f"search_gap_mean_n{order}"]) > 1e-9:
            _fail(f"search gap mean n={order}: {mean} != summary")


# ---------------------------------------------------------------------------
# figure 0 — the engine's decision trajectory, one per track
# ---------------------------------------------------------------------------
def figure_trajectory(study: Path, contract: dict, track: str, out: Path) -> Path:
    metric = contract["tracks"][track]["metric"]
    path = klein_figures.plot_decision_trajectory(
        workflow.load_manifests(study),
        study,
        track=track,
        metric_goal=metric["goal"],
        metric_name=metric["name"],
        minimum_delta=float(metric["minimum_delta"]),
        name=f"plot_decision_trajectory__{track}",
    )
    # The helper always writes into <study>/figures; copy across when --out differs.
    if path.parent != out:
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out / path.name)
        path = out / path.name
    print(f"wrote {path}")
    return path


# ---------------------------------------------------------------------------
# figure 1 — best length against the tabulated optimum, and the gap
# ---------------------------------------------------------------------------
def figure_gap(pairs: list[dict], out: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
    offset = {"search": -0.17, "llm": 0.17}
    style = {
        "search": dict(marker="o", color=SEARCH, label="classical search (verified best)"),
        "llm": dict(marker="D", color=LLM, label="LLM arm (verified best)"),
    }
    optimum = {p["order"]: p["optimum"] for p in pairs}
    for ax, key in zip(axes, ("best", "gap"), strict=True):
        top = max(p[key] for p in pairs if p[key] is not None)
        ymax = top * 1.22
        rug = top * 1.12
        for arm in ("search", "llm"):
            for order in ORDERS:
                rows = sorted(
                    (p for p in pairs if p["arm"] == arm and p["order"] == order),
                    key=lambda p: p["trial"],
                )
                for p in rows:
                    x = order + offset[arm] + (p["trial"] - 1) * 0.045
                    if p[key] is None:
                        ax.scatter([x], [rug], marker="x", s=46, color=CRASH, linewidths=1.8, zorder=4)
                    else:
                        ax.scatter(
                            [x], [p[key]], s=46, marker=style[arm]["marker"], color=style[arm]["color"],
                            edgecolors="white", linewidths=0.7, zorder=3, clip_on=False,
                        )
        if key == "best":
            for order in ORDERS:
                ax.hlines(optimum[order], order - 0.38, order + 0.38, color=OPT, linewidth=2.6, zorder=2)
            ax.set_ylabel("best verified ruler length (length units)")
            ax.set_title("(a) best verified length against the tabulated optimum")
        else:
            ax.axhline(0, color=OPT, linewidth=1.6, zorder=1)
            ax.set_ylabel("gap = best verified length − tabulated optimum (length units)")
            ax.set_title("(b) the gap; 0 is a match")
        ax.axvline(11.5, color=MUTED, linestyle=":", linewidth=1.2)
        ax.text(11.45, ymax * 0.985, "development", ha="right", va="top", fontsize=8.5, color=MUTED)
        ax.text(11.55, ymax * 0.985, "sealed", ha="left", va="top", fontsize=8.5, color=MUTED)
        ax.set_xticks(ORDERS)
        ax.set_xlim(7.5, 13.5)
        ax.set_ylim(0, ymax)
        ax.set_xlabel("order n (number of marks)")
    handles = [
        Line2D([], [], marker="o", color=SEARCH, linestyle="none", markeredgecolor="white", label="classical search, one trial"),
        Line2D([], [], marker="D", color=LLM, linestyle="none", markeredgecolor="white", label="LLM arm, one trial"),
        Line2D([], [], marker="x", color=CRASH, linestyle="none", markeredgewidth=1.8, label="no valid ruler (nothing to measure)"),
        Line2D([], [], color=OPT, linewidth=2.6, label="tabulated optimum (OEIS A003022)"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=8.5, frameon=False)
    fig.suptitle(
        "Both arms spent 2000 candidate evaluations per (order, trial); three trials per order",
        fontsize=10, color=MUTED,
    )
    fig.tight_layout(rect=(0.0, 0.07, 1.0, 0.94))
    path = out / "gap_by_order.png"
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, metadata=META)
    plt.close(fig)
    print(f"wrote {path}")
    return path


# ---------------------------------------------------------------------------
# figure 2 — proposals to first match
# ---------------------------------------------------------------------------
def figure_first_match(study: Path, pairs: list[dict], out: Path) -> Path:
    sol = json.loads((study / "tables" / "solution_E0004.json").read_text(encoding="utf-8"))
    proposals = int(sol["pairs"][0]["proposals"])
    art = {(p["order"], p["trial"]): p.get("first_optimal_proposal") for p in sol["pairs"]}
    rows = sorted((p for p in pairs if p["exp"] == "E0004"), key=lambda p: (p["order"], p["trial"]))
    for p in rows:
        if art[(p["order"], p["trial"])] != p["first"]:
            _fail(f"first match n={p['order']} t={p['trial']}: artifact {art[(p['order'], p['trial'])]} != table {p['first']}")

    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    none_x = proposals + 14
    ys = list(range(len(rows)))[::-1]
    for y, p in zip(ys, rows, strict=True):
        if p["first"] is None:
            ax.scatter([none_x], [y], marker="x", s=60, color=CRASH, linewidths=1.8, zorder=3)
            ax.hlines(y, 0, none_x, color=GRID, linewidth=0.8, zorder=1)
        else:
            ax.hlines(y, 0, p["first"], color=LLM, linewidth=1.4, alpha=0.7, zorder=1)
            ax.scatter([p["first"]], [y], marker="D", s=62, color=LLM, edgecolors="white", linewidths=0.8, zorder=3)
            ax.annotate(str(p["first"]), (p["first"], y), textcoords="offset points", xytext=(8, -3), fontsize=8.5, color=INK)
    ax.axvline(1, color=OPT, linestyle="--", linewidth=1.4, zorder=2)
    ax.axvline(proposals + 7, color=MUTED, linestyle=":", linewidth=1.2)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"n={p['order']}, trial {p['trial']}" for p in rows], fontsize=8.5)
    ax.set_xlim(0, proposals + 24)
    ax.set_xticks([0, 50, 100, 150, proposals])
    ax.set_xlabel(f"proposal index of the first verified ruler at the tabulated length (of {proposals}; 1 = first batch)")
    ax.set_ylabel("development (order, trial) pair, LLM arm")
    ax.set_title("A recall signature would put every match at proposal 1")
    ax.text(proposals + 8, ys[0] + 0.55, "no match\nin 200", ha="left", va="bottom", fontsize=8, color=CRASH)
    handles = [
        Line2D([], [], marker="D", color=LLM, linestyle="none", markeredgecolor="white", label="matched: first proposal at the tabulated length"),
        Line2D([], [], marker="x", color=CRASH, linestyle="none", markeredgewidth=1.8, label="not matched within 200 proposals"),
        Line2D([], [], color=OPT, linestyle="--", linewidth=1.4, label="proposal 1: before any verifier feedback"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=8, framealpha=0.92)
    ax.grid(axis="y", visible=False)
    return save(fig, out, "first_match_proposals")


# ---------------------------------------------------------------------------
# figure 3 — valid rulers and unparsed replies, by order
# ---------------------------------------------------------------------------
def figure_valid_unparsed(study: Path, pairs: list[dict], summary: dict[str, float], out: Path) -> Path:
    sol = json.loads((study / "tables" / "solution_E0004.json").read_text(encoding="utf-8"))
    proposals = int(sol["pairs"][0]["proposals"])
    trials = int(sol["trials"])
    evals = int(sol["budget_evaluations"])
    replies = proposals * trials          # replies per order
    candidates = evals * trials           # candidate evaluations per order
    llm = [p for p in pairs if p["arm"] == "llm"]

    # The shard of the sealed cell is the independent witness for the sealed half.
    shard = study / "calls" / "E0006-000.jsonl.gz"
    with gzip.open(shard, "rt", encoding="utf-8") as stream:
        shard_replies = sum(1 for line in stream if line.strip())
    sealed_rows = [p for p in llm if p["exp"] == "E0006"]
    if shard_replies != proposals * len(sealed_rows):
        _fail(f"E0006 shard holds {shard_replies} replies, expected {proposals * len(sealed_rows)}")
    aux_unparsed = {
        r["experiment"]: float(r["value"])
        for r in read_tsv(study / "aux_metrics.tsv") if r["metric"] == "unparsed_replies"
    }
    for exp in ("E0004", "E0006"):
        total = sum(p["unparsed"] for p in llm if p["exp"] == exp)
        if total != int(aux_unparsed[exp]):
            _fail(f"{exp}: unparsed replies {total} != aux {aux_unparsed[exp]}")

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.4))
    for ax, key, denom, label in (
        (axes[0], "unparsed", replies, "unparsed replies, share of the replies per order (%)"),
        (axes[1], "valid", candidates, "valid rulers, share of candidate evaluations per order (%)"),
    ):
        for i, order in enumerate(ORDERS):
            count = sum(p[key] for p in llm if p["order"] == order)
            sealed = order in SEALED_ORDERS
            ax.bar(
                i, 100.0 * count / denom, width=0.62,
                color=LLM if not sealed else "white", edgecolor=LLM, linewidth=1.6,
                hatch="//" if sealed else None, zorder=3,
            )
            ax.annotate(
                f"{count}", (i, 100.0 * count / denom), textcoords="offset points",
                xytext=(0, 4), ha="center", fontsize=9, color=INK,
            )
        ax.set_xticks(range(len(ORDERS)))
        ax.set_xticklabels([f"n={n}" for n in ORDERS])
        ax.set_ylim(0, (40 if key == "unparsed" else 5.2))
        ax.set_xlabel("order n (LLM arm, three trials each)")
        ax.set_ylabel(label)
        ax.grid(axis="x", visible=False)
    axes[0].set_title(f"(a) replies the parser could not read (of {replies} per order)")
    axes[1].set_title(f"(b) valid Golomb rulers (of {candidates} candidates per order)")
    axes[0].legend(
        handles=[
            Patch(facecolor=LLM, edgecolor=LLM, label="development orders (E0004)"),
            Patch(facecolor="white", edgecolor=LLM, hatch="//", label="sealed orders (E0006)"),
        ],
        loc="upper right", fontsize=8.5, framealpha=0.92,
    )
    fig.suptitle("Counts above the bars are the searcher's own (solution tables); the sealed valid count is recounted from the call shard in findings", fontsize=9.5, color=MUTED)
    return save(fig, out, "valid_vs_unparsed", top=0.94)


# ---------------------------------------------------------------------------
# figure 4 — what was matched (verifier calls) against what was not
# ---------------------------------------------------------------------------
def figure_compute(study: Path, pairs: list[dict], out: Path) -> Path:
    aux: dict[str, dict[str, float]] = {}
    for row in read_tsv(study / "aux_metrics.tsv"):
        aux.setdefault(row["experiment"], {})[row["metric"]] = float(row["value"])
    manifests = {
        exp: json.loads((study / "runs" / exp / "manifest.json").read_text(encoding="utf-8"))
        for exp in ("E0004", "E0006")
    }
    lanes = ("development", "sealed")
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.5))

    # (a) verifier calls: the matched quantity
    ax = axes[0]
    for j, lane in enumerate(lanes):
        for k, arm in enumerate(("search", "llm")):
            exp = RUNS[(arm, lane)]
            total = sum(p["evals"] for p in pairs if p["exp"] == exp)
            if total != int(aux[exp]["evaluations"]):
                _fail(f"{exp}: table evaluations {total} != aux {aux[exp]['evaluations']}")
            x = j + (k - 0.5) * 0.36
            ax.bar(x, total, width=0.34, color=SEARCH if arm == "search" else LLM,
                   hatch=None if arm == "search" else "..", edgecolor="white", zorder=3)
            ax.annotate(f"{total}", (x, total), textcoords="offset points", xytext=(0, 4), ha="center", fontsize=8.5)
    ax.set_xticks(range(2))
    ax.set_xticklabels(["development (12 pairs)", "sealed (6 pairs)"])
    ax.set_ylim(0, 24000 * 1.3)
    ax.legend(
        handles=[
            Patch(facecolor=SEARCH, label="classical search"),
            Patch(facecolor=LLM, hatch="..", edgecolor="white", label="LLM arm"),
        ],
        loc="upper right", fontsize=9, framealpha=0.92,
    )
    ax.set_ylabel("candidate evaluations checked (verifier calls)")
    ax.set_title("(a) matched: verifier calls per run")
    ax.grid(axis="x", visible=False)

    # (b) wall-clock on a declared log axis (a dot plot, so the log scale is honest)
    ax = axes[1]
    for j, lane in enumerate(lanes):
        for k, arm in enumerate(("search", "llm")):
            exp = RUNS[(arm, lane)]
            seconds = aux[exp]["wall_seconds"]
            x = j + (k - 0.5) * 0.36
            ax.scatter([x], [seconds], s=80, marker="o" if arm == "search" else "D",
                       color=SEARCH if arm == "search" else LLM, edgecolors="white", linewidths=0.8, zorder=3)
            ax.annotate(f"{seconds:,.0f} s" if seconds >= 100 else f"{seconds:.3f} s", (x, seconds), textcoords="offset points", xytext=(0, 9), ha="center", fontsize=8.5)
    ax.set_yscale("log")
    ax.set_ylim(0.1, 3e4)
    ax.set_xlim(-0.6, 1.6)
    ax.set_xticks(range(2))
    ax.set_xticklabels(["development", "sealed"])
    ax.set_ylabel("wall-clock seconds per run (log scale)")
    ax.set_title("(b) not matched: wall-clock")
    ax.grid(axis="x", visible=False)

    # (c) model tokens (live) — only the LLM arm has any
    ax = axes[2]
    for j, (exp, lane) in enumerate((("E0004", "development"), ("E0006", "sealed"))):
        usage = manifests[exp]["usage"]
        tokens = float(usage["tokens"])
        if tokens != float(usage["tokens_in"]) + float(usage["tokens_out"]):
            _fail(f"{exp}: tokens != in + out")
        ax.bar(j, tokens / 1e6, width=0.5, color=LLM, hatch="..", edgecolor="white", zorder=3)
        ax.annotate(f"{tokens / 1e6:.2f} M\n({int(usage['calls'])} live calls)", (j, tokens / 1e6),
                    textcoords="offset points", xytext=(0, 4), ha="center", fontsize=8.5)
    ax.set_xticks(range(2))
    ax.set_xticklabels(["development (E0004)", "sealed (E0006)"])
    ax.set_ylim(0, 2.2)
    ax.set_ylabel("model tokens, in + out, live calls (millions)")
    ax.set_title("(c) not matched: tokens (search arm: none)")
    ax.grid(axis="x", visible=False)

    return save(fig, out, "compute_vs_budget", top=1.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--study", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    study = args.study.resolve()
    out = (args.out or (study / "figures")).resolve()
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))

    pairs = load_pairs(study)
    summary = load_summary(study)
    cross_check(study, pairs, summary)

    for track in ("search", "llm"):
        figure_trajectory(study, contract, track, out)
    figure_gap(pairs, out)
    figure_first_match(study, pairs, out)
    figure_valid_unparsed(study, pairs, summary, out)
    figure_compute(study, pairs, out)
    print("all cross-checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
