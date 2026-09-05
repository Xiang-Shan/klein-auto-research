"""Every figure in this study, deterministically, from the ledger and the contract.

Run twice and the PNGs are byte-identical: the parade's five recipes are refitted
from `lib/iris.py` on the contract's own DEVELOPMENT partition only (never the
sealed one -- each track's one sealed access was already spent by `klein run-one
--final-test`, and this script must not read it again), the refit AUC is
cross-checked against the pinned `results.tsv`/`aux_metrics.tsv` value for that
experiment before anything is drawn, and every other number on every panel is a
verbatim read of `aux_metrics.tsv`, `results.tsv` or `study.yaml` -- nothing here
recomputes or improves a metric.

    uv run --locked python figures/make_figures.py [--study DIR] [--out DIR]

Eleven figures:

``plot_decision_trajectory__{fisher,modern,ablation}``
    the generic profile's mandatory per-track decision trajectory, straight from
    the run manifests via `kleinlib.figures.plot_decision_trajectory`.
``plot_pr`` / ``plot_reliability`` / ``plot_decile_lift`` / ``plot_confusion_at_threshold``
    the generic profile's §4 classification set, completed here for Fisher's own
    LDA (E0002's recipe, refit on development) -- the one recipe every track and
    every other cell in the parade is measured against.
``roc_parade``
    ROC curves for the five `modern`-track recipes on the development block
    (E0002-E0006), refit from `lib/iris.py` and checked against the ledger.
``score_hist_by_family``
    predicted-probability histograms by species, one small panel per recipe,
    same refit predictions as the ROC parade.
``calibration_reversal``
    development calibration across the parade (Brier + log-loss, all pinned
    values, no refit) next to the one comparison this study can actually take
    onto the sealed block twice: `hgbt` (E0006 -> E0011) and the ablation
    track's petal-only LDA (E0007 -> E0012) -- the study's own fourth surprise.
``floor_vs_ceiling``
    the measured-floor-vs-headroom figure `research_plan.md` calls for: each
    track's floor drawn as a shaded band under the AUC ceiling of 1.0, with the
    track's own measured candidates marked against it.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from sklearn.metrics import roc_auc_score, roc_curve  # noqa: E402

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


def _results(study: Path) -> dict[str, dict[str, str]]:
    return {row["experiment"]: row for row in _read_tsv(study / "results.tsv")}


def _close(a: float, b: float, tol: float = 5e-6) -> bool:
    return abs(a - b) <= tol


def main() -> int:
    args = _parse_args()
    study = Path(args.study).resolve()
    out_dir = Path(args.out).resolve() if args.out else study / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(study))

    from kleinlib import figures
    from kleinlib.contract import load_contract, normalize_tracks
    from kleinlib.data import contract_split
    from kleinlib.workflow import load_manifests

    from lib.iris import fit_and_score

    contract = load_contract(study)
    tracks = normalize_tracks(contract)
    aux = _aux(study)
    results = _results(study)

    # `kleinlib.figures`' helpers always append "/figures" to the directory
    # they are given (`_save_fig`), so a bare scratch `--out` needs the
    # nested segment undone afterward; the default in-study case already
    # ends in "figures", so handing it `out_dir.parent` writes straight to
    # `out_dir` with no nesting to undo.
    helper_dst = out_dir.parent if out_dir.name == "figures" else out_dir

    # ------------------------------------------------------------------
    # Refit the five `modern`-track recipes on the DEVELOPMENT block only
    # (never the sealed one) and check every refit AUC against the ledger.
    # ------------------------------------------------------------------
    X_train, X_dev, _X_test, y_train, y_dev, _y_test = contract_split(study)
    parade = [
        ("lda_all4", "Fisher's LDA (E0002)", "E0002"),
        ("logreg_l2", "L2 logistic regression (E0003)", "E0003"),
        ("knn5", "5-nearest-neighbours (E0004)", "E0004"),
        ("svm_rbf", "RBF-kernel SVM (E0005)", "E0005"),
        ("hgbt", "Boosted tree (E0006)", "E0006"),
    ]
    y_dev_arr = np.asarray(y_dev)
    proba: dict[str, np.ndarray] = {}
    for recipe_id, _label, exp in parade:
        _model, p_eval, _fit_seconds = fit_and_score(recipe_id, X_train, y_train, X_dev)
        refit_auc = float(roc_auc_score(y_dev_arr, p_eval))
        pinned = float(results[exp]["primary_metric"])
        if not _close(refit_auc, pinned, tol=1e-6):
            raise SystemExit(
                f"{recipe_id} ({exp}): refit val_auc {refit_auc!r} disagrees with the "
                f"ledger's {pinned!r} -- a figure must not draw a model the ledger "
                "never recorded"
            )
        proba[recipe_id] = p_eval

    markers = ["o", "s", "^", "D", "P"]

    # ------------------------------------------------------------------
    # 1-3. The mandatory per-track decision trajectory (generic profile).
    # ------------------------------------------------------------------
    manifests = load_manifests(study)
    for track, spec in tracks.items():
        metric = spec.get("metric", {})
        figures.plot_decision_trajectory(
            manifests,
            helper_dst,
            track=track,
            metric_goal=str(metric.get("goal") or "higher"),
            metric_name=metric.get("name"),
            minimum_delta=metric.get("minimum_delta") or None,
            noise_floor_std=(metric.get("noise_floor") or {}).get("std"),
            name=f"plot_decision_trajectory__{track}",
        )

    # ------------------------------------------------------------------
    # 4-7. The generic profile's remaining classification set (PR,
    # reliability, decile lift, confusion@best), for Fisher's own LDA
    # (E0002's recipe) on development -- the recipe every other cell in
    # this study is measured against.
    # ------------------------------------------------------------------
    lda_p = proba["lda_all4"]
    figures.plot_pr(y_dev_arr, lda_p, helper_dst, name="plot_pr")
    figures.plot_reliability(y_dev_arr, lda_p, helper_dst, name="plot_reliability")
    figures.plot_decile_lift(y_dev_arr, lda_p, helper_dst, name="plot_decile_lift")
    figures.plot_confusion_at_threshold(
        y_dev_arr, lda_p, helper_dst, threshold=0.5, name="plot_confusion_at_threshold"
    )

    if out_dir.name != "figures":
        moved_from = out_dir / "figures"
        if moved_from.is_dir():
            for png in moved_from.glob("*.png"):
                png.replace(out_dir / png.name)
            try:
                moved_from.rmdir()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # 4. ROC curves per family (development block).
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], color=figures.CHROME["muted"], linestyle="--", linewidth=1, label="chance")
    for (recipe_id, label, exp), marker, color in zip(parade, markers, figures.CATEGORICAL):
        fpr, tpr, _ = roc_curve(y_dev_arr, proba[recipe_id])
        auc = roc_auc_score(y_dev_arr, proba[recipe_id])
        ax.plot(
            fpr, tpr, color=color, linewidth=2, marker=marker, markersize=5,
            markevery=max(1, len(fpr) // 10), label=f"{label}: AUC={auc:.4f}",
        )
    ax.set_xlabel("False positive rate (development block, 25 flowers)")
    ax.set_ylabel("True positive rate (development block, 25 flowers)")
    ax.set_title("ROC per family - the ninety-year parade, development block")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.05)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "roc_parade.png", dpi=figures.DPI)
    plt.close(fig)

    # ------------------------------------------------------------------
    # 5. Score histograms by species, one small panel per family.
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 5, figsize=(16, 3.2), sharey=True)
    for (recipe_id, label, exp), color_pos, ax in zip(
        parade, [figures.CATEGORICAL[5]] * 5, axes
    ):
        p = proba[recipe_id]
        ax.hist(
            p[y_dev_arr == 0], bins=12, range=(0, 1), alpha=0.7,
            color=figures.CATEGORICAL[0], label="versicolor", edgecolor="none",
        )
        ax.hist(
            p[y_dev_arr == 1], bins=12, range=(0, 1), alpha=0.55,
            color=figures.CATEGORICAL[5], label="virginica", hatch="//",
            edgecolor=figures.CHROME["primary_ink"], linewidth=0.4,
        )
        ax.set_title(label, fontsize=9)
        ax.set_xlabel("P(virginica)")
        ax.set_xlim(0, 1)
    axes[0].set_ylabel("Development flowers (count)")
    axes[0].legend(loc="upper center", fontsize=7)
    fig.suptitle("Predicted-probability distribution by species, development block", y=1.04)
    fig.tight_layout()
    fig.savefig(out_dir / "score_hist_by_family.png", dpi=figures.DPI, bbox_inches="tight")
    plt.close(fig)

    # ------------------------------------------------------------------
    # 6. Calibration reversal: development-only parade, then the two
    #    families that actually reached the sealed block twice.
    # ------------------------------------------------------------------
    dev_brier = [aux[(exp, "val_brier")] for _r, _l, exp in parade]
    dev_logloss = [aux[(exp, "val_logloss")] for _r, _l, exp in parade]
    parade_labels = ["lda_all4", "logreg_l2", "knn5", "svm_rbf", "hgbt"]

    reversal_families = ["hgbt\n(modern track)", "LDA petal-only\n(ablation track)"]
    reversal_dev_brier = [aux[("E0006", "val_brier")], aux[("E0007", "val_brier")]]
    reversal_sealed_brier = [aux[("E0011", "val_brier")], aux[("E0012", "val_brier")]]
    reversal_dev_logloss = [aux[("E0006", "val_logloss")], aux[("E0007", "val_logloss")]]
    reversal_sealed_logloss = [aux[("E0011", "val_logloss")], aux[("E0012", "val_logloss")]]

    fig, ((ax_b1, ax_b2), (ax_l1, ax_l2)) = plt.subplots(2, 2, figsize=(11, 8))

    x = np.arange(len(parade_labels))
    ax_b1.bar(x, dev_brier, color=figures.CATEGORICAL[0])
    ax_b1.set_xticks(x)
    ax_b1.set_xticklabels(parade_labels, fontsize=8)
    ax_b1.set_ylabel("Development Brier score (lower = better)")
    ax_b1.set_title("Development calibration across the parade")
    ax_b1.set_ylim(0, max(dev_brier) * 1.25)

    ax_l1.bar(x, dev_logloss, color=figures.CATEGORICAL[4])
    ax_l1.set_xticks(x)
    ax_l1.set_xticklabels(parade_labels, fontsize=8)
    ax_l1.set_ylabel("Development log-loss (lower = better)")
    ax_l1.set_title("Development calibration across the parade")
    ax_l1.set_ylim(0, max(dev_logloss) * 1.25)

    xg = np.arange(len(reversal_families))
    width = 0.35
    ax_b2.bar(xg - width / 2, reversal_dev_brier, width, color=figures.CATEGORICAL[0], label="development")
    ax_b2.bar(
        xg + width / 2, reversal_sealed_brier, width, color=figures.CATEGORICAL[5],
        label="sealed", hatch="//", edgecolor=figures.CHROME["primary_ink"], linewidth=0.4,
    )
    ax_b2.set_xticks(xg)
    ax_b2.set_xticklabels(reversal_families, fontsize=8)
    ax_b2.set_ylabel("Brier score (lower = better)")
    ax_b2.set_title("The reversal: development vs sealed Brier")
    ax_b2.legend(fontsize=8)
    for xi, (dv, se) in enumerate(zip(reversal_dev_brier, reversal_sealed_brier)):
        ax_b2.text(xi - width / 2, dv + 0.003, f"{dv:.3f}", ha="center", fontsize=7)
        ax_b2.text(xi + width / 2, se + 0.003, f"{se:.3f}", ha="center", fontsize=7)

    ax_l2.bar(xg - width / 2, reversal_dev_logloss, width, color=figures.CATEGORICAL[0], label="development")
    ax_l2.bar(
        xg + width / 2, reversal_sealed_logloss, width, color=figures.CATEGORICAL[5],
        label="sealed", hatch="//", edgecolor=figures.CHROME["primary_ink"], linewidth=0.4,
    )
    ax_l2.set_xticks(xg)
    ax_l2.set_xticklabels(reversal_families, fontsize=8)
    ax_l2.set_ylabel("Log-loss (lower = better)")
    ax_l2.set_title("The reversal: development vs sealed log-loss")
    ax_l2.legend(fontsize=8)
    for xi, (dv, se) in enumerate(zip(reversal_dev_logloss, reversal_sealed_logloss)):
        ax_l2.text(xi - width / 2, dv + 0.02, f"{dv:.3f}", ha="center", fontsize=7)
        ax_l2.text(xi + width / 2, se + 0.02, f"{se:.3f}", ha="center", fontsize=7)

    fig.suptitle(
        "Calibration reversal: the boosted tree was the parade's best-calibrated "
        "model on development and its worst on the sealed block",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_dir / "calibration_reversal.png", dpi=figures.DPI)
    plt.close(fig)

    # ------------------------------------------------------------------
    # 7. The measured-floor-vs-headroom figure.
    # ------------------------------------------------------------------
    floor_fisher = float(tracks["fisher"]["metric"].get("minimum_delta") or 0.0)
    floor_modern = float(tracks["modern"]["metric"].get("minimum_delta") or 0.0)
    floor_ablation = float(tracks["ablation"]["metric"].get("minimum_delta") or 0.0)

    dev_lda_auc = float(results["E0001"]["primary_metric"])
    sealed_lda_auc = float(results["E0010"]["primary_metric"])
    hgbt_sealed_auc = float(results["E0011"]["primary_metric"])
    petal_dev_auc = float(results["E0007"]["primary_metric"])
    sepal_dev_auc = float(results["E0008"]["primary_metric"])
    petal_sealed_auc = float(results["E0012"]["primary_metric"])

    track_rows = [
        (
            "fisher",
            floor_fisher,
            dev_lda_auc,
            [("incumbent, dev + sealed", sealed_lda_auc, "o", (0, -26))],
        ),
        (
            "modern",
            floor_modern,
            dev_lda_auc,
            [("hgbt, sealed (E0011)", hgbt_sealed_auc, "*", (0, -26))],
        ),
        (
            "ablation",
            floor_ablation,
            dev_lda_auc,
            [
                ("petal-only, dev (E0007)", petal_dev_auc, "o", (18, 20)),
                ("petal-only, sealed (E0012)", petal_sealed_auc, "s", (18, -34)),
                ("sepal-only, dev (E0008)", sepal_dev_auc, "^", (0, -26)),
            ],
        ),
    ]

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ceiling = 1.0
    for i, (track, floor, ref, markers_here) in enumerate(track_rows):
        y = len(track_rows) - i
        band_lo = ref - floor
        if floor > 0:
            ax.barh(
                y, floor, left=band_lo, height=0.55, color=figures.CATEGORICAL[2],
                alpha=0.35, edgecolor="none", zorder=1,
            )
        ax.plot([0.55, ceiling], [y, y], color=figures.CHROME["baseline"], linewidth=1, zorder=0)
        ax.scatter([ref], [y], marker="|", s=400, color=figures.CHROME["primary_ink"], zorder=3)
        floor_text = f"{floor:.5f}".rstrip("0").rstrip(".") if floor else "0"
        ax.text(
            0.565, y + 0.24, f"measured floor = {floor_text}", fontsize=8,
            color=figures.CHROME["secondary_ink"], va="bottom",
        )
        for label, value, marker, xytext in markers_here:
            ax.scatter(
                [value], [y], marker=marker, s=90, color=figures.CATEGORICAL[6],
                edgecolors=figures.CHROME["primary_ink"], linewidths=0.8, zorder=4,
            )
            ax.annotate(
                f"{label}\n{value:.4f}", (value, y), textcoords="offset points",
                xytext=xytext, ha="center", fontsize=7, color=figures.CHROME["secondary_ink"],
            )
    ax.axvline(ceiling, color=figures.CHROME["muted"], linestyle="--", linewidth=1, zorder=0)
    ax.text(ceiling, len(track_rows) + 0.55, "AUC ceiling = 1.0", ha="right", fontsize=8, color=figures.CHROME["secondary_ink"])
    ax.set_yticks([len(track_rows) - i for i in range(len(track_rows))])
    ax.set_yticklabels([t for t, *_ in track_rows])
    ax.set_xlim(0.55, 1.02)
    ax.set_xlabel("val_auc (development-block reference = 1.0 on every track)")
    ax.set_title("Measured floor vs. the AUC ceiling, by track")
    ax.set_ylim(0.3, len(track_rows) + 0.9)
    legend_handles = [
        Patch(facecolor=figures.CATEGORICAL[2], alpha=0.35, label="shaded = inside the measured floor (unresolvable)"),
        Line2D([0], [0], marker="|", color=figures.CHROME["primary_ink"], linestyle="None", markersize=14, label="track reference (val_auc)"),
        Line2D([0], [0], marker="o", color=figures.CATEGORICAL[6], linestyle="None", markersize=8, label="a measured candidate"),
    ]
    ax.legend(handles=legend_handles, loc="lower left", fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "floor_vs_ceiling.png", dpi=figures.DPI)
    plt.close(fig)

    written = sorted(out_dir.glob("*.png"))
    print(f"wrote {len(written)} figures to {out_dir}")
    for path in written:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
