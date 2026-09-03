"""make_figures.py — the three exhibits for 00-known-truth-quickstart.

Deterministic: no randomness, no timestamps, no network. Re-running it
overwrites the same bytes, which is the property the tutorial's inlined figures
depend on and which CI checks by rendering twice and comparing.

Reads only study artifacts:

  study.yaml                        minimum_delta, the noise floor, metric.bound.ideal
  results.tsv                       one row per notarized run
  aux_metrics.tsv                   every extra key the runs printed
  sweeps/split_lottery.sidecar.tsv  the k = 10 marginal-resplit floor trials
  data/prepared/prepared.csv        the prepared table (regenerate with prepare.py)
  data/prepared/truth.json          the declared truth: per-row log-odds + ceilings
  train.py                          the recipe library, imported so the figures
                                    cannot drift from the code that produced the
                                    ledger — and cross-checked against it below

Writes three PNGs into --out:

  plot_decision_trajectory__primary.png   the engine's standard decision trajectory
  headroom_bar.png                        every rung against the KNOWN ceiling on a
                                          zero-based axis, and the same distances in
                                          units of the measured floor
  known_truth_calibration.png             predicted probability vs the TRUE
                                          probability — the plot only a known-truth
                                          study can draw

Every number drawn is read from an artifact or recomputed and then asserted
equal to the artifact's own value (the numbers law: nothing invented, nothing
retyped). Run from the repo root:

    uv run --locked python studies/00-known-truth-quickstart/figures/make_figures.py
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import brier_score_loss, roc_auc_score

from kleinlib import figures as klein_figures
from kleinlib import workflow
from kleinlib.data import contract_split

DPI = klein_figures.DPI
#: Deterministic PNG metadata: matplotlib writes no timestamp, and pinning
#: Software keeps the bytes stable across matplotlib versions too.
META = {"Software": "make_figures.py (study 00-known-truth-quickstart)"}

INK = klein_figures.CHROME["primary_ink"]
MUTED = klein_figures.CHROME["muted"]
GRID = klein_figures.CHROME["gridline"]
KEEP = klein_figures.STATUS_COLOR["keep"]
DISCARD = klein_figures.STATUS_COLOR["discard"]
IDEAL = klein_figures.CATEGORICAL[4]     # violet: never the green a keep is drawn in
ANCHOR = klein_figures.CATEGORICAL[0]
BOOSTED = klein_figures.CATEGORICAL[1]

#: The ladder, in the order it was climbed. (experiment, recipe, label).
LADDER = (
    ("E0001", "logreg_raw", "E0001\nlogistic,\nraw"),
    ("E0002", "logreg_interaction", "E0002\nlogistic\n+ true x1·x2"),
    ("E0003", "hgbt_default", "E0003\nboosted,\ndefaults"),
    ("E0004", "hgbt_overcapacity", "E0004\nboosted,\nover-capacity"),
)
#: The sealed run sits apart from the ladder: it is confirmation evidence, never
#: another frontier candidate, and the plots keep that visible.
SEALED_X = 4.7


def _fail(message: str) -> None:
    raise SystemExit(f"make_figures: {message}")


def _close(left: float, right: float, tol: float = 5e-7) -> bool:
    return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= tol


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def load_train_module(study: Path):
    """Import the study's own entrypoint so the recipes cannot drift."""
    spec = importlib.util.spec_from_file_location("study00_train", study / "train.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["study00_train"] = module
    spec.loader.exec_module(module)
    return module


def save(fig: plt.Figure, out: Path, name: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, metadata=META)
    plt.close(fig)
    print(f"wrote {path}")
    return path


# ---------------------------------------------------------------------------
# figure 1 — the engine's standard decision trajectory
# ---------------------------------------------------------------------------
def figure_trajectory(study: Path, contract: dict, out: Path) -> Path:
    manifests = workflow.load_manifests(study)
    metric = contract["tracks"]["primary"]["metric"]
    path = klein_figures.plot_decision_trajectory(
        manifests,
        study,
        track="primary",
        metric_goal=metric["goal"],
        metric_name=metric["name"],
        minimum_delta=float(metric["minimum_delta"]),
        noise_floor_std=float(metric["noise_floor"]["std"]),
        name="plot_decision_trajectory__primary",
    )
    # The engine helper always writes into <study>/figures. When --out points
    # somewhere else (klein verify re-renders into a temp dir and compares the
    # bytes), copy the result across rather than refusing: the helper's write is
    # deterministic, so the in-place overwrite is a no-op on the same bytes.
    if path.parent != out:
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out / path.name)
        path = out / path.name
    print(f"wrote {path}")
    return path


# ---------------------------------------------------------------------------
# figure 2 — every rung against the KNOWN ceiling
# ---------------------------------------------------------------------------
def figure_headroom(
    study: Path, contract: dict, results: dict[str, dict[str, str]], aux: dict[str, dict[str, str]], out: Path
) -> Path:
    metric = contract["tracks"]["primary"]["metric"]
    delta = float(metric["minimum_delta"])
    floor_std = float(metric["noise_floor"]["std"])
    ideal = float(metric["bound"]["ideal"])

    # Cross-check 1: the declared bar IS max(2*std, range/2) of the registered
    # split-lottery sidecar, recomputed from the trials rather than trusted.
    trials = [float(row["primary_metric"]) for row in read_tsv(study / "sweeps" / "split_lottery.sidecar.tsv")]
    recomputed = max(2.0 * float(np.std(trials, ddof=1)), (max(trials) - min(trials)) / 2.0)
    if not _close(recomputed, delta, tol=5e-8):
        _fail(f"minimum_delta {delta} is not max(2*std, range/2) = {recomputed} of the sidecar")

    # Cross-check 2: the declared ideal IS the development partition's Bayes AUC.
    truth = json.loads((study / "data" / "prepared" / "truth.json").read_text(encoding="utf-8"))
    if not _close(float(truth["partitions"]["development"]["bayes_auc"]), ideal, tol=5e-7):
        _fail("metric.bound.ideal is not truth.json's development bayes_auc")

    scores, gaps = [], []
    for experiment, _recipe, _label in LADDER:
        value = float(results[experiment]["primary_metric"])
        gap = float(aux[experiment]["gap_in_floors"])
        # Cross-check 3: the printed headroom IS (ideal - score) / delta.
        if not _close((ideal - value) / delta, gap, tol=1e-4):
            _fail(f"{experiment}: printed gap_in_floors {gap} != recomputed {(ideal - value) / delta}")
        scores.append(value)
        gaps.append(gap)

    sealed_value = float(results["E0005"]["primary_metric"])
    sealed_ideal = float(aux["E0005"]["bayes_auc"])
    sealed_gap = float(aux["E0005"]["gap_in_floors"])

    labels = [label for _e, _r, label in LADDER]
    colors = [KEEP if results[e]["status"] == "keep" else DISCARD for e, _r, _l in LADDER]
    # Figure-critique point 3: every mark must survive grayscale, so a discard is
    # a hatch as well as a hue.
    hatches = [None if results[e]["status"] == "keep" else ".." for e, _r, _l in LADDER]
    x = np.arange(len(LADDER), dtype=float)
    ticks = list(x) + [SEALED_X]
    tick_labels = labels + ["E0005\nSEALED\nboosted, defaults"]

    fig, (left, right) = plt.subplots(1, 2, figsize=(12.4, 5.0))

    for axes in (left, right):
        axes.axvline(len(LADDER) - 0.15, color=klein_figures.CHROME["baseline"], linewidth=1.0,
                     linestyle=(0, (2, 3)), zorder=1)
        axes.set_xlim(-0.7, SEALED_X + 0.9)
        axes.set_xticks(ticks)
        axes.set_xticklabels(tick_labels, fontsize=8)

    # LEFT — scores against the ceiling, ZERO-BASED.
    #
    # Referee note 1 (2026-09-03): this panel used to run from 0.78, which is a
    # truncated axis under a bar mark and `tutorial-spec.md` critique point 2 says
    # flatly "bars are zero-based". It is zero-based now, and the honest
    # consequence is visible: on an absolute AUC scale the five rungs look nearly
    # identical and the ceiling sits just above them. That is the truth in metric
    # units, and it is exactly why the right panel exists — the same distances
    # divided by what the measurement can actually resolve. The chance line is
    # drawn because 0.5, not 0, is where an AUC axis stops being informative, and
    # a zero-based AUC axis would otherwise invite the opposite misreading.
    left.axhline(ideal, color=IDEAL, linewidth=2, linestyle="--", zorder=4,
                 label=f"development ceiling (Bayes AUC) {ideal:g}")
    left.axhline(0.5, color=MUTED, linewidth=1.4, linestyle=(0, (4, 3)), zorder=4,
                 label="chance (val_auc 0.5)")
    bars = left.bar(x, scores, width=0.62, color=colors, edgecolor="#ffffff", linewidth=0.8, zorder=3)
    for patch, hatch in zip(bars, hatches, strict=True):
        if hatch:
            patch.set_hatch(hatch)
    # Labels go INSIDE the bars: above them they collide with the ceiling and
    # chance rules, which on a zero-based axis both cross the bar tops.
    # A plain-ink label on a white plate: legible over a solid bar, over a hatched
    # one, and in grayscale — which white-on-hatch is not.
    plate = {"boxstyle": "round,pad=0.15", "fc": "#ffffff", "ec": "none", "alpha": 0.88}
    for xi, value in zip(x, scores, strict=True):
        left.annotate(f"{value:.6f}", (xi, value), textcoords="offset points", xytext=(0, -5),
                      ha="center", va="top", fontsize=7.5, color=INK, zorder=6, bbox=plate)
    left.hlines(sealed_ideal, SEALED_X - 0.45, SEALED_X + 0.45, color=IDEAL, linewidth=2,
                linestyle=":", zorder=4, label=f"sealed partition's own ceiling {sealed_ideal:g}")
    left.bar([SEALED_X], [sealed_value], width=0.62, color=KEEP, alpha=0.45, edgecolor=KEEP,
             linewidth=1.4, zorder=3, hatch="//", label="sealed run (confirmation evidence)")
    left.annotate(f"{sealed_value:.6f}", (SEALED_X, sealed_value), textcoords="offset points",
                  xytext=(0, -5), ha="center", va="top", fontsize=7.5, color=INK, zorder=6,
                  bbox=plate)
    left.bar([np.nan], [np.nan], color=KEEP, label="keep (development frontier)")
    left.bar([np.nan], [np.nan], color=DISCARD, hatch="..", label="discard (retained evidence)")
    left.set_ylim(0, 1.0)
    left.set_yticks([0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0])
    left.set_ylabel("val_auc")
    left.set_title("In metric units, every rung looks alike", fontsize=11)
    left.legend(fontsize=7, loc="lower left", framealpha=0.95)

    # RIGHT — the same distances, in floors.
    right.axhspan(0, 1, color=IDEAL, alpha=0.12, linewidth=0, zorder=0)
    right.axhline(1.0, color=IDEAL, linewidth=1.8, linestyle="--", zorder=4,
                  label="h = 1 — below this line no keep is arithmetically possible")
    right_bars = right.bar(x, gaps, width=0.62, color=colors, edgecolor="#ffffff",
                           linewidth=0.8, zorder=3)
    for patch, hatch in zip(right_bars, hatches, strict=True):
        if hatch:
            patch.set_hatch(hatch)
    for xi, value in zip(x, gaps, strict=True):
        right.annotate(f"{value:g}", (xi, value), textcoords="offset points", xytext=(0, 4),
                       ha="center", fontsize=8, color=INK)
    right.bar([SEALED_X], [sealed_gap], width=0.62, color=KEEP, alpha=0.45, edgecolor=KEEP,
              linewidth=1.4, zorder=3, hatch="//")
    right.annotate(f"{sealed_gap:g}", (SEALED_X, sealed_gap), textcoords="offset points",
                   xytext=(0, 4), ha="center", fontsize=8, color=INK)
    right.set_ylim(0, 11.6)
    right.set_ylabel("distance to the ceiling, in measured floors  (h)")
    right.set_title(f"In floors, they do not — the bar divides by {delta:g}", fontsize=11)
    right.legend(fontsize=7, loc="upper right", framealpha=0.95)

    return save(fig, out, "headroom_bar")


# ---------------------------------------------------------------------------
# figure 3 — predicted probability vs the TRUE probability
# ---------------------------------------------------------------------------
def figure_calibration(
    study: Path, results: dict[str, dict[str, str]], aux: dict[str, dict[str, str]], out: Path
) -> Path:
    train = load_train_module(study)
    X_train, X_dev, _X_test, y_train, y_dev, _y_test = contract_split(study)

    truth = json.loads((study / "data" / "prepared" / "truth.json").read_text(encoding="utf-8"))
    eta = np.asarray(truth["true_log_odds"], dtype=float)[X_dev.index.to_numpy()]
    p_true = 1.0 / (1.0 + np.exp(-eta))

    # Cross-check 4: the ceiling this script computes IS the one E0003 printed.
    if not _close(float(roc_auc_score(y_dev, p_true)), float(aux["E0003"]["bayes_auc"])):
        _fail("the recomputed development Bayes AUC differs from the one E0003 printed")

    series = []
    for experiment, recipe, color, marker, dashes in (
        ("E0001", "logreg_raw", ANCHOR, "o", (0, ())),
        ("E0003", "hgbt_default", BOOSTED, "s", (0, (5, 2))),
    ):
        model, transform = train.fit_recipe(recipe, X_train, y_train)
        proba = np.asarray(model.predict_proba(transform(X_dev)))[:, 1]
        # Cross-check 5: refitting the recipe reproduces the ledger's own number.
        observed = float(roc_auc_score(y_dev, proba))
        recorded = float(results[experiment]["primary_metric"])
        if not _close(observed, recorded, tol=5e-7):
            _fail(f"{experiment}: refit scores {observed}, the ledger says {recorded}")
        series.append((experiment, recipe, color, marker, dashes, proba,
                       float(brier_score_loss(y_dev, proba))))

    bayes_brier = float(brier_score_loss(y_dev, p_true))
    if not _close(bayes_brier, float(truth["partitions"]["development"]["bayes_brier"]), tol=5e-7):
        _fail("the recomputed development Bayes Brier differs from truth.json")

    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))

    lo, hi = 0.0, max(float(p_true.max()), *(float(s[5].max()) for s in series))
    hi = math.ceil(hi * 20) / 20
    left.plot([lo, hi], [lo, hi], color=MUTED, linewidth=1.4, linestyle="--", zorder=2,
              label="perfect: predicted = true")
    for experiment, recipe, color, marker, dashes, proba, brier in series:
        order = np.argsort(proba, kind="stable")
        bins = np.array_split(order, 20)
        xs = [float(proba[b].mean()) for b in bins if len(b)]
        ys = [float(p_true[b].mean()) for b in bins if len(b)]
        left.plot(xs, ys, marker=marker, markersize=5, linewidth=1.6, color=color,
                  linestyle=dashes, zorder=3,
                  label=f"{recipe} ({experiment}), Brier {brier:.6f}")
    left.set_xlim(lo, hi)
    left.set_ylim(lo, hi)
    left.set_xlabel("mean PREDICTED probability, 20 equal-count bins")
    left.set_ylabel("mean TRUE probability of the same rows")
    left.set_title("Calibration against the truth, not against a histogram", fontsize=11)
    left.legend(fontsize=7, loc="upper left", framealpha=0.95)

    # Right panel: the residual the ranking metric cannot see.
    for experiment, recipe, color, marker, dashes, proba, _brier in series:
        order = np.argsort(p_true, kind="stable")
        bins = np.array_split(order, 25)
        xs = [float(p_true[b].mean()) for b in bins if len(b)]
        ys = [float((proba[b] - p_true[b]).mean()) for b in bins if len(b)]
        right.plot(xs, ys, marker=marker, markersize=4, linewidth=1.5, color=color,
                   linestyle=dashes, zorder=3, label=f"{recipe} ({experiment})")
    right.axhline(0.0, color=MUTED, linewidth=1.4, linestyle="--", zorder=2)
    right.set_xlabel("TRUE probability, 25 equal-count bins")
    right.set_ylabel("mean (predicted − true)")
    right.set_title(f"Where each rung is wrong (Bayes Brier {bayes_brier:g})", fontsize=11)
    right.legend(fontsize=7, loc="lower left", framealpha=0.95)

    return save(fig, out, "known_truth_calibration")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_study = Path(__file__).resolve().parent.parent
    parser.add_argument("--study", type=Path, default=default_study)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    study = args.study.resolve()
    out = (args.out or (study / "figures")).resolve()
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))

    prepared = study / "data" / "prepared" / "prepared.csv"
    if not prepared.is_file():
        _fail(f"{prepared} is absent — regenerate it with `uv run --locked python prepare.py`")

    results = {row["experiment"]: row for row in read_tsv(study / "results.tsv")}
    aux: dict[str, dict[str, str]] = {}
    for row in read_tsv(study / "aux_metrics.tsv"):
        aux.setdefault(row["experiment"], {})[row["metric"]] = row["value"]

    figure_trajectory(study, contract, out)
    figure_headroom(study, contract, results, aux, out)
    figure_calibration(study, results, aux, out)
    print("all cross-checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
