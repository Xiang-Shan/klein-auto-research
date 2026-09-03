"""Every figure in this study, deterministically, from the contract and the ledger.

Run twice and the PNGs are byte-identical: the rungs are refitted from
``lib/rungs.py`` on the contract's own partitions, nothing is sampled, and no
timestamp or absolute path reaches a canvas.

    uv run --locked python figures/make_figures.py [--study DIR] [--out DIR]

Six figures, the insurance profile's classification set plus the two this study
needs of its own:

``plot_roc`` / ``plot_pr`` / ``plot_reliability`` / ``plot_decile_lift``
    the profile's §4 set, drawn for the frontier incumbent (E0003's rung) — rank,
    precision-recall at a 6.4 % base rate, calibration, and decile lift.
``lorenz_gini``
    the pricing view: the Lorenz curve of predicted risk against realised claims for
    all three rungs, with each rung's Gini in the legend. This is the figure an
    actuary reads first, and it is the one that shows the calibrated GLM and the tree
    doing nearly the same work.
``floors_vs_gaps``
    the study's argument in one panel: every gap the ladder measured, drawn against
    the declared bar and against each comparison's own pair-specific floor. Zero-based.
``decision_trajectory``
    the ledger as the notary recorded it — keeps, discards and the sealed run.

Every number a panel prints is read from a pinned artifact
(``tables/verdict_arithmetic.tsv``, ``tables/pair_floors.tsv``, ``aux_metrics.tsv``)
and cross-checked against it in-script: a figure that disagrees with the ledger
raises rather than renders.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

DEFAULT_STUDY = Path(__file__).resolve().parent.parent


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", default=str(DEFAULT_STUDY), help="study directory")
    parser.add_argument("--out", default=None, help="output directory (default: <study>/figures)")
    return parser.parse_args()


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _aux(study: Path) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for row in _read_tsv(study / "aux_metrics.tsv"):
        try:
            out[(row["experiment"], row["metric"])] = float(row["value"])
        except (KeyError, ValueError):
            continue
    return out


def _close(a: float, b: float, tol: float = 5e-6) -> bool:
    return abs(a - b) <= tol


def main() -> int:
    args = _parse_args()
    study = Path(args.study).resolve()
    out_dir = Path(args.out).resolve() if args.out else study / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(study))

    from kleinlib import figures
    from kleinlib.data import contract_split

    from lib.rungs import fit_rung, positive_probabilities

    aux = _aux(study)
    verdicts = _read_tsv(study / "tables" / "verdict_arithmetic.tsv")
    floors = {row["sweep"]: row for row in _read_tsv(study / "tables" / "pair_floors.tsv")}
    declared_bar = float(floors["paired_bootstrap"]["bar"])

    X_train, X_dev, _, y_train, y_dev, _ = contract_split(study)
    rungs = ("glm_ohe_balanced", "glm_splines_isotonic", "hgbt_balanced")
    labels = {
        "glm_ohe_balanced": "GLM + one-hot (E0001)",
        "glm_splines_isotonic": "GLM + splines + isotonic (E0002)",
        "hgbt_balanced": "boosted tree (E0003)",
    }
    ledger_auc = {
        "glm_ohe_balanced": aux[("E0001", "val_auc")],
        "glm_splines_isotonic": aux[("E0002", "val_auc")],
        "hgbt_balanced": aux[("E0003", "val_auc")],
    }

    probabilities: dict[str, np.ndarray] = {}
    for rung in rungs:
        model, _, X_dev_t = fit_rung(rung, X_train, X_dev, y_train)
        probabilities[rung] = positive_probabilities(model, X_dev_t)
        refit = float(roc_auc_score(y_dev, probabilities[rung]))
        if not _close(refit, ledger_auc[rung]):
            raise SystemExit(
                f"{rung}: refit AUC {refit:.6f} disagrees with the ledger's "
                f"{ledger_auc[rung]:.6f} — a figure must not draw a model the "
                "ledger never recorded"
            )

    incumbent = probabilities["hgbt_balanced"]

    # --- Lorenz / Gini, all three rungs -----------------------------------
    y = np.asarray(y_dev, dtype=float)
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1, color="#8a8f98", label="no discrimination")
    for rung in rungs:
        order = np.argsort(probabilities[rung])
        cumulative = np.cumsum(y[order]) / y.sum()
        share = np.arange(1, len(y) + 1) / len(y)
        gini = float(1.0 - 2.0 * np.trapezoid(cumulative, share))
        ax.plot(share, cumulative, linewidth=2, label=f"{labels[rung]} — Gini {gini:.3f}")
    ax.set_xlabel("share of policies, ordered by predicted risk (lowest first)")
    ax.set_ylabel("share of realised claims")
    ax.set_title("Lorenz curves on the development partition")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "lorenz_gini.png", dpi=figures.DPI)
    plt.close(fig)

    # --- every gap against every bar --------------------------------------
    rows = [r for r in verdicts if r["prediction"] != "frontier keep"]
    names = {
        "E0002_vs_anchor": "splines + isotonic\nvs the GLM anchor",
        "E0003_vs_splines": "boosted tree\nvs splines + isotonic",
        "E0004_vs_anchor": "doctrine A/B\nvs the GLM anchor",
    }
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))
    x = np.arange(len(rows))
    lifts = [abs(float(r["observed_lift"])) for r in rows]
    own_bars = [float(r["own_pair_bar"]) for r in rows]
    left.bar(x - 0.2, lifts, width=0.4, color="#2f6f9f", label="observed |lift|")
    left.bar(x + 0.2, own_bars, width=0.4, color="#c2703d", label="that pair's own floor")
    left.axhline(declared_bar, color="#3d3d3d", linestyle="--", linewidth=1.2,
                 label="the declared bar")
    left.set_xticks(x)
    left.set_xticklabels([names[r["comparison"]] for r in rows], fontsize=8)
    left.set_ylabel("val_auc")
    left.set_ylim(0, max(max(lifts), max(own_bars), declared_bar) * 1.25)
    left.set_title("Every gap the ladder measured, in metric units")
    left.legend(fontsize=8)

    declared_floors = [abs(float(r["in_declared_floors"])) for r in rows]
    own_floors = [abs(float(r["in_own_pair_floors"])) for r in rows]
    right.bar(x - 0.2, declared_floors, width=0.4, color="#2f6f9f", label="in declared floors")
    right.bar(x + 0.2, own_floors, width=0.4, color="#c2703d", label="in its own pair's floors")
    right.axhline(1.0, color="#3d3d3d", linestyle="--", linewidth=1.2, label="one floor")
    right.set_xticks(x)
    right.set_xticklabels([names[r["comparison"]] for r in rows], fontsize=8)
    right.set_ylabel("floors")
    right.set_ylim(0, max(max(declared_floors), max(own_floors), 1.0) * 1.25)
    right.set_title("The same gaps, divided by which floor prices them")
    right.legend(fontsize=8)
    for index, row in enumerate(rows):
        right.text(index - 0.2, abs(float(row["in_declared_floors"])) + 0.03,
                   f"{abs(float(row['in_declared_floors'])):.2f}", ha="center", fontsize=8)
        right.text(index + 0.2, abs(float(row["in_own_pair_floors"])) + 0.03,
                   f"{abs(float(row['in_own_pair_floors'])):.2f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "floors_vs_gaps.png", dpi=figures.DPI)
    plt.close(fig)

    # `kleinlib.figures._save_fig` appends "/figures" to whatever directory it is
    # given, so a helper cannot be pointed straight at `--out`. Handing it the study
    # directory would make five of the seven figures ignore `--out` and quietly
    # rewrite committed files (referee note 1). Give the helpers a scratch root
    # instead and move their PNGs into `--out` flat: every destination is computed
    # from `--out` alone, and nothing under the study is touched unless `--out`
    # names it.
    from kleinlib.workflow import load_manifests

    helper_root = Path(tempfile.mkdtemp(prefix="klein-figures-"))
    try:
        figures.plot_roc(y_dev, incumbent, helper_root, name="plot_roc")
        figures.plot_pr(y_dev, incumbent, helper_root, name="plot_pr")
        figures.plot_reliability(y_dev, incumbent, helper_root, name="plot_reliability")
        figures.plot_decile_lift(y_dev, incumbent, helper_root, name="plot_decile_lift")
        figures.plot_decision_trajectory(
            load_manifests(study),
            helper_root,
            track="primary",
            metric_goal="higher",
            metric_name="val_auc",
            minimum_delta=declared_bar,
            noise_floor_std=float(floors["paired_bootstrap"]["std"]),
            name="plot_decision_trajectory",
        )
        for produced in sorted((helper_root / "figures").glob("*.png")):
            shutil.move(str(produced), str(out_dir / produced.name))
    finally:
        shutil.rmtree(helper_root, ignore_errors=True)

    print(f"wrote {len(sorted(out_dir.glob('*.png')))} figures to {out_dir.name}/")
    for path in sorted(out_dir.glob("*.png")):
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
