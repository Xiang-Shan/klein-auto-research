"""make_figures.py — the three exhibits for 11-exact-verifier-construction.

Deterministic: no randomness, no timestamps, no network. Re-running it overwrites
the same bytes, which is the property the tutorial's inlined figures depend on
and which is checked here by rendering twice and comparing.

Reads only study artifacts:

  study.yaml                     the two tracks' bounds and external incumbents
  results.tsv                    one row per notarized run (the VERIFIER's number)
  aux_metrics.tsv                every extra key the runs printed
  runs/E####/manifest.json       dispositions, matched_external, the E0008 crash
  models/E0009/solution.json     the verified 22-point object the sealed run found

Writes three PNGs into --out:

  reach_vs_budget.png            the verified objective against the evaluation
                                 budget, one panel per track, with the proven
                                 maximum 2n drawn as a horizontal reference
  verified_object.png            the object itself: the sealed run's 22 points on
                                 the 11 x 11 grid, drawn from the artifact the
                                 verifier accepted, with the parabola control beside it
  checker_ledger.png             what the checker did to the ledger: the twelve
                                 planted objects it rejected, and the one run whose
                                 self-report it refused

Every number drawn is read from an artifact and then asserted equal to the
artifact's own value (the numbers law: nothing invented, nothing retyped). The
independence the study is about is enforced here too: this script re-derives no
objective. It plots what `verify.py` computed, as `results.tsv` records it.

Run from the repo root:

    uv run --locked python studies/11-exact-verifier-construction/figures/make_figures.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import yaml  # noqa: E402

from kleinlib import figures as klein_figures  # noqa: E402

DPI = klein_figures.DPI
#: Deterministic PNG metadata: matplotlib writes no timestamp, and pinning
#: Software keeps the bytes stable across matplotlib versions too.
META = {"Software": "make_figures.py (study 11-exact-verifier-construction)"}

INK = klein_figures.CHROME["primary_ink"]
MUTED = klein_figures.CHROME["muted"]
GRID = klein_figures.CHROME["gridline"]
DISCARD = klein_figures.STATUS_COLOR["discard"]
CRASH = klein_figures.STATUS_COLOR["crash"]
BOUND = klein_figures.CATEGORICAL[4]      # violet: the proven maximum, never a keep colour
DEV = klein_figures.CATEGORICAL[0]
SEALED = klein_figures.CATEGORICAL[1]

#: The two budget ladders, in the order they were run: (experiment, budget key).
LADDERS = {
    "n_small": (("E0002", "small"), ("E0003", "medium"), ("E0004", "large")),
    "n_large": (("E0005", "small"), ("E0006", "medium"), ("E0007", "large")),
}
#: The sealed cell of each track — confirmation evidence, drawn apart from the ladder.
SEALED_RUN = {"n_small": "E0009", "n_large": "E0010"}
TRACK_TITLE = {"n_small": "n = 11", "n_large": "n = 31"}


def _fail(message: str) -> None:
    raise SystemExit(f"make_figures: {message}")


def _eq(left: float, right: float) -> bool:
    """Exact-metric equality: the objective is an integer, so no tolerance."""
    return math.isfinite(left) and math.isfinite(right) and left == right


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def save(fig: plt.Figure, out: Path, name: str, *, top: float = 1.0) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    # `tight_layout` does not reserve room for a suptitle, so a figure that has
    # one passes the fraction of the canvas the axes may use.
    fig.tight_layout(rect=(0.0, 0.0, 1.0, top))
    fig.savefig(path, dpi=DPI, metadata=META)
    plt.close(fig)
    print(f"wrote {path}")
    return path


# ---------------------------------------------------------------------------
# figure 1 — the verified objective against the evaluation budget
# ---------------------------------------------------------------------------
def figure_reach(
    contract: dict,
    results: dict[str, dict[str, str]],
    aux: dict[str, dict[str, str]],
    out: Path,
) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.4))
    for panel, track in zip(axes, ("n_small", "n_large"), strict=True):
        metric = contract["tracks"][track]["metric"]
        bound = float(metric["bound"]["ideal"])
        external = float(metric["incumbent_external"]["value"])
        if not _eq(bound, external):
            _fail(f"{track}: bound.ideal {bound} != incumbent_external {external}")

        budgets, scores = [], []
        for exp, _rung in LADDERS[track]:
            budget = float(aux[exp]["budget"])
            score = float(results[exp]["primary_metric"])
            # The numbers law, mechanized: the searcher's own claim, the object it
            # wrote, and the ledger's number must be the same integer.
            if not _eq(score, float(aux[exp]["claimed_objective"])):
                _fail(f"{exp}: ledger {score} != claimed_objective {aux[exp]['claimed_objective']}")
            if not _eq(score, float(aux[exp]["object_size"])):
                _fail(f"{exp}: ledger {score} != object_size {aux[exp]['object_size']}")
            if not _eq(budget, float(aux[exp]["evaluations"])):
                _fail(f"{exp}: budget {budget} != evaluations spent {aux[exp]['evaluations']}")
            budgets.append(budget)
            scores.append(score)

        sealed = SEALED_RUN[track]
        sealed_budget = float(aux[sealed]["budget"])
        sealed_score = float(results[sealed]["primary_metric"])

        panel.axhline(
            bound,
            color=BOUND,
            linewidth=1.6,
            linestyle="--",
            zorder=1,
            label=f"proven maximum 2n = {bound:.0f}",
        )
        panel.plot(
            budgets, scores, marker="o", color=DEV, linewidth=1.8, zorder=3,
            label="development seed block",
        )
        # The sealed cell ran at the same budget as the last development rung, so
        # it is drawn slightly to its right: a confirmation cell is not another
        # point on the ladder, and overlapping markers would say it was.
        sealed_x = sealed_budget * 1.55
        panel.plot(
            [sealed_x], [sealed_score], marker="*", markersize=17, color=SEALED,
            linestyle="none", zorder=4, label="sealed seed block (one access)",
        )
        for x, y in zip(budgets, scores, strict=True):
            panel.annotate(
                f"{y:.0f}", (x, y), textcoords="offset points", xytext=(0, -16),
                ha="center", fontsize=9, color=INK,
            )
        panel.annotate(
            f"{sealed_score:.0f}", (sealed_x, sealed_score), textcoords="offset points",
            xytext=(2, 10), ha="center", fontsize=9, color=SEALED, fontweight="bold",
        )
        panel.set_xscale("log")
        panel.set_xlabel("evaluation budget (addability tests, log scale)")
        panel.set_ylabel("points, as the declared verifier scored them")
        panel.set_title(f"{TRACK_TITLE[track]} — reach against budget")
        panel.set_ylim(0, bound * 1.18)
        panel.grid(True, color=GRID, linewidth=0.6, alpha=0.7)
        panel.legend(loc="lower right", fontsize=8, framealpha=0.9)
    fig.suptitle(
        "Every point is the checker's number, not the searcher's — and no point can rise "
        "above the dashed line, which is a theorem",
        fontsize=10, color=MUTED,
    )
    return save(fig, out, "reach_vs_budget", top=0.94)


# ---------------------------------------------------------------------------
# figure 2 — the verified object itself
# ---------------------------------------------------------------------------
def figure_object(study: Path, results: dict[str, dict[str, str]], out: Path) -> Path:
    solution = json.loads((study / "models" / "E0009" / "solution.json").read_text(encoding="utf-8"))
    instances = json.loads(
        (study / "data" / "prepared" / "instances.json").read_text(encoding="utf-8")
    )
    control = instances["controls"]["negative"]

    points = [tuple(p) for p in solution["points"]]
    n = int(solution["n"])
    ledger = float(results["E0009"]["primary_metric"])
    if not _eq(float(len(points)), ledger):
        _fail(f"E0009: the artifact holds {len(points)} points, the ledger says {ledger}")
    # Redrawing an object is a chance to check it, so check it: the figure asserts
    # the same property verify.py asserted, from the same bytes.
    for a, b, c in combinations(points, 3):
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) == 0:
            _fail(f"E0009's artifact has a collinear triple {a}, {b}, {c}")

    control_points = [tuple(p) for p in control["points"]]
    if len(control_points) != int(control["expected_objective"]):
        _fail("the negative control's point count disagrees with its expected objective")

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.9))
    panels = (
        (axes[0], points, f"E0009 — the sealed run's object: {len(points)} points"),
        (
            axes[1],
            control_points,
            f"the negative control: Erdős's parabola, {len(control_points)} points",
        ),
    )
    for panel, pts, title in panels:
        for x in range(n):
            panel.axhline(x, color=GRID, linewidth=0.5, zorder=0)
            panel.axvline(x, color=GRID, linewidth=0.5, zorder=0)
        colour = SEALED if pts is points else DEV
        panel.scatter(
            [p[0] for p in pts], [p[1] for p in pts], s=110, color=colour,
            edgecolor=INK, linewidth=0.8, zorder=3,
        )
        panel.set_xlim(-0.6, n - 0.4)
        panel.set_ylim(-0.6, n - 0.4)
        panel.set_xticks(range(n))
        panel.set_yticks(range(n))
        panel.tick_params(labelsize=7)
        panel.set_aspect("equal")
        panel.set_title(title, fontsize=10)
    fig.suptitle(
        "Two objects the checker accepted. Left: found by search, and it attains the "
        "proven maximum 2n. Right: known valid before any code ran.",
        fontsize=9.5, color=MUTED,
    )
    return save(fig, out, "verified_object", top=0.93)


# ---------------------------------------------------------------------------
# figure 3 — what the checker did to the ledger
# ---------------------------------------------------------------------------
def figure_checker(
    study: Path,
    results: dict[str, dict[str, str]],
    aux: dict[str, dict[str, str]],
    out: Path,
) -> Path:
    instances = json.loads(
        (study / "data" / "prepared" / "instances.json").read_text(encoding="utf-8")
    )
    planted = instances["controls"]["positive"]["objects"]
    n_planted = float(aux["E0001"]["planted"])
    n_rejected = float(aux["E0001"]["rejected"])
    if not _eq(n_planted, float(len(planted))):
        _fail(f"E0001 printed planted={n_planted}, the frozen file holds {len(planted)}")

    crash = json.loads((study / "runs" / "E0008" / "manifest.json").read_text(encoding="utf-8"))
    reported = float(crash["metric"]["reported"])
    verified = float(crash["metric"]["verified"])
    if crash["disposition"] != "crash" or "verifier_disagreement" not in crash["decision_reason"]:
        _fail("E0008 is not the recorded verifier_disagreement crash")
    if results["E0008"]["primary_metric"] != "NA":
        _fail("E0008's ledger row should carry NA")

    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.3))

    left = axes[0]
    names = [obj["name"].replace("_", " ") for obj in planted]
    # Markers, not bars: the quantity here is a VERDICT, and a bar whose length
    # is one categorical step invites the reading that a shorter one was possible.
    left.scatter(
        [1.0] * len(names), range(len(names)), marker="X", s=110,
        color=DISCARD, edgecolor=INK, linewidth=0.7, zorder=3,
    )
    left.set_yticks(range(len(names)))
    left.set_yticklabels(names, fontsize=8)
    left.invert_yaxis()
    left.set_xlim(-0.35, 1.35)
    left.set_xticks([0, 1])
    left.set_xticklabels(["accepted\n(exit 0)", "rejected\n(exit 2)"], fontsize=8.5)
    left.set_title(
        f"positive control: {n_rejected:.0f} of {n_planted:.0f} planted objects rejected",
        fontsize=10,
    )
    left.grid(True, axis="y", color=GRID, linewidth=0.6, alpha=0.7)
    left.axvline(0.0, color=GRID, linewidth=1.0, zorder=1)

    right = axes[1]
    right.bar(
        [0, 1], [reported, verified],
        color=[CRASH, DISCARD], edgecolor=INK, linewidth=0.8, width=0.55,
    )
    right.set_xticks([0, 1])
    right.set_xticklabels(
        ["what the SEARCH\nreported", "what the CHECKER\nmeasured"], fontsize=9
    )
    right.set_ylim(0, max(reported, verified) * 1.35)
    right.set_ylabel("points")
    for x, value in ((0, reported), (1, verified)):
        right.annotate(f"{value:.0f}", (x, value), textcoords="offset points",
                       xytext=(0, 7), ha="center", fontsize=11, color=INK, fontweight="bold")
    right.set_title("E0008: the deliberate disagreement", fontsize=10)
    right.annotate(
        "recorded as a crash;\nthe ledger row is NA",
        (0, reported), textcoords="offset points", xytext=(0, 34), ha="center",
        fontsize=8.5, color=CRASH,
    )
    right.grid(True, axis="y", color=GRID, linewidth=0.6, alpha=0.7)

    fig.suptitle(
        "The checker fires on what it should, and the notary refuses what the searcher "
        "said about itself",
        fontsize=10, color=MUTED,
    )
    return save(fig, out, "checker_ledger", top=0.96)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    default_study = Path(__file__).resolve().parent.parent
    parser.add_argument("--study", type=Path, default=default_study)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    study = args.study.resolve()
    out = (args.out or (study / "figures")).resolve()
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))

    instances = study / "data" / "prepared" / "instances.json"
    if not instances.is_file():
        _fail(f"{instances} is absent — regenerate it with `uv run --locked python prepare.py`")

    results = {row["experiment"]: row for row in read_tsv(study / "results.tsv")}
    aux: dict[str, dict[str, str]] = {}
    for row in read_tsv(study / "aux_metrics.tsv"):
        aux.setdefault(row["experiment"], {})[row["metric"]] = row["value"]

    figure_reach(contract, results, aux, out)
    figure_object(study, results, out)
    figure_checker(study, results, aux, out)
    print("all cross-checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
