"""Figure library for Klein Auto Research studies.

Every function saves a PNG to ``<study_dir>/figures/<name>.png`` and returns
that path (as a `pathlib.Path`) — nothing is ever shown interactively.
`kleinlib.eval.evaluate`/`evaluate_regression` already print every number
these figures visualize; regenerate figures only for a synthesis/tutorial
pass (or via the `make_figures.py` CLI), not once per experiment.

Backend: forced to `Agg` at import time unless the `MPLBACKEND` environment
variable is already set (so a caller who wants an interactive backend for
their own purposes is never overridden).

Palette: the categorical color cycle, sequential ramp, and diverging pair
below are the validated default instance from the shared `dataviz` skill
(`references/palette.md`), light-mode slots, in the fixed hue order that
maximizes minimum adjacent CVD separation (worst adjacent deltaE 24.2,
well clear of the >=12 target) — never re-ordered or re-cycled per chart.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

if "MPLBACKEND" not in os.environ:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from cycler import cycler  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from scipy import stats  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

from . import schema  # noqa: E402

# --------------------------------------------------------------------------
# Colorblind-safe palette (dataviz skill, references/palette.md, light mode)
# --------------------------------------------------------------------------

#: Fixed-order categorical hues: blue, aqua, yellow, green, violet, red,
#: magenta, orange. Assign by entity identity, never re-ordered per chart.
CATEGORICAL: tuple[str, ...] = (
    "#2a78d6",
    "#1baf7a",
    "#eda100",
    "#008300",
    "#4a3aa7",
    "#e34948",
    "#e87ba4",
    "#eb6834",
)

#: Sequential single-hue ramp (blue, light -> dark) for magnitude encodings.
SEQUENTIAL: tuple[str, ...] = (
    "#cde2fb",
    "#9ec5f4",
    "#5598e7",
    "#2a78d6",
    "#184f95",
    "#0d366b",
)

#: Chart chrome (ink/gridlines), light surface.
CHROME: dict[str, str] = {
    "primary_ink": "#0b0b0b",
    "secondary_ink": "#52514e",
    "muted": "#898781",
    "gridline": "#e1e0d9",
    "baseline": "#c3c2b7",
}

DPI = 150


def _sequential_cmap() -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list("klein_blues", SEQUENTIAL)


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "axes.prop_cycle": cycler(color=CATEGORICAL),
            "figure.dpi": DPI,
            "savefig.dpi": DPI,
            "axes.edgecolor": CHROME["baseline"],
            "axes.labelcolor": CHROME["primary_ink"],
            "axes.grid": True,
            "grid.color": CHROME["gridline"],
            "grid.linewidth": 0.6,
            "text.color": CHROME["primary_ink"],
            "xtick.color": CHROME["secondary_ink"],
            "ytick.color": CHROME["secondary_ink"],
            "font.size": 10,
        }
    )


_apply_style()


def _save_fig(fig: plt.Figure, study_dir: str | Path, name: str) -> Path:
    fig_dir = Path(study_dir) / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    path = fig_dir / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def _quantile_bins(n: int, n_bins: int) -> list[np.ndarray]:
    """Split `arange(n)` into `n_bins` equal-weight (quantile) index groups."""
    return [b for b in np.array_split(np.arange(n), n_bins) if len(b)]


# --------------------------------------------------------------------------
# Binary classification
# --------------------------------------------------------------------------


def plot_roc(y_true: Any, proba: Any, study_dir: str | Path, *, name: str = "plot_roc") -> Path:
    """ROC curve with AUC in the legend."""
    y_true = np.asarray(y_true)
    proba = np.asarray(proba, dtype=float)
    fpr, tpr, _ = roc_curve(y_true, proba)
    auc = roc_auc_score(y_true, proba)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(fpr, tpr, color=CATEGORICAL[0], linewidth=2, label=f"ROC (AUC={auc:.3f})")
    ax.plot([0, 1], [0, 1], color=CHROME["muted"], linestyle="--", linewidth=1, label="chance")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC curve")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right")
    return _save_fig(fig, study_dir, name)


def plot_pr(y_true: Any, proba: Any, study_dir: str | Path, *, name: str = "plot_pr") -> Path:
    """Precision-recall curve with average precision, vs. the base-rate line."""
    y_true = np.asarray(y_true)
    proba = np.asarray(proba, dtype=float)
    precision, recall, _ = precision_recall_curve(y_true, proba)
    ap = average_precision_score(y_true, proba)
    base_rate = float(y_true.mean())

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(recall, precision, color=CATEGORICAL[0], linewidth=2, label=f"PR (AP={ap:.3f})")
    ax.axhline(
        base_rate, color=CHROME["muted"], linestyle="--", linewidth=1,
        label=f"base rate ({base_rate:.3f})",
    )
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall curve")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.legend(loc="upper right")
    return _save_fig(fig, study_dir, name)


def plot_reliability(
    y_true: Any, proba: Any, study_dir: str | Path, *, n_bins: int = 10, name: str = "plot_reliability"
) -> Path:
    """Reliability diagram over `n_bins` equal-count (quantile) bins."""
    y_true = np.asarray(y_true, dtype=float)
    proba = np.asarray(proba, dtype=float)
    order = np.argsort(proba)
    y_sorted, p_sorted = y_true[order], proba[order]
    bins = _quantile_bins(len(p_sorted), n_bins)
    mean_pred = [float(p_sorted[b].mean()) for b in bins]
    mean_obs = [float(y_sorted[b].mean()) for b in bins]

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], color=CHROME["muted"], linestyle="--", linewidth=1, label="perfect calibration")
    ax.plot(mean_pred, mean_obs, marker="o", color=CATEGORICAL[0], linewidth=2, label="model")
    ax.set_xlabel(f"Mean predicted probability ({len(bins)} quantile bins)")
    ax.set_ylabel("Observed positive rate")
    ax.set_title("Reliability diagram")
    ax.legend(loc="upper left")
    return _save_fig(fig, study_dir, name)


def plot_score_hist_by_class(
    y_true: Any, proba: Any, study_dir: str | Path, *, name: str = "plot_score_hist_by_class"
) -> Path:
    """Overlaid predicted-probability histograms for class 0 vs. class 1."""
    y_true = np.asarray(y_true)
    proba = np.asarray(proba, dtype=float)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(proba[y_true == 0], bins=30, range=(0, 1), alpha=0.65, color=CATEGORICAL[0], density=True, label="class 0")
    ax.hist(proba[y_true == 1], bins=30, range=(0, 1), alpha=0.65, color=CATEGORICAL[5], density=True, label="class 1")
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Density")
    ax.set_title("Score distribution by class")
    ax.legend()
    return _save_fig(fig, study_dir, name)


def plot_decile_lift(
    y_true: Any, proba: Any, study_dir: str | Path, *, n_bins: int = 10, name: str = "plot_decile_lift"
) -> Path:
    """Bar chart of lift-over-base-rate by predicted-probability decile (D1=highest)."""
    y_true = np.asarray(y_true, dtype=float)
    proba = np.asarray(proba, dtype=float)
    order = np.argsort(-proba)
    y_sorted = y_true[order]
    bins = _quantile_bins(len(y_sorted), n_bins)
    base_rate = float(y_true.mean())
    lifts = [float(y_sorted[b].mean()) / base_rate if base_rate > 0 else 0.0 for b in bins]
    labels = [f"D{i + 1}" for i in range(len(bins))]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, lifts, color=CATEGORICAL[0])
    ax.axhline(1.0, color=CHROME["muted"], linestyle="--", linewidth=1)
    ax.set_xlabel("Decile (D1 = highest predicted probability)")
    ax.set_ylabel("Lift over base rate")
    ax.set_title("Decile lift")
    return _save_fig(fig, study_dir, name)


def plot_confusion_at_threshold(
    y_true: Any,
    proba: Any,
    study_dir: str | Path,
    *,
    threshold: float = 0.5,
    name: str = "plot_confusion_at_threshold",
) -> Path:
    """Confusion matrix heatmap at a fixed decision `threshold`."""
    y_true = np.asarray(y_true)
    pred = (np.asarray(proba, dtype=float) > threshold).astype(int)
    cm = confusion_matrix(y_true, pred, labels=[0, 1])
    vmax = cm.max() if cm.max() > 0 else 1

    fig, ax = plt.subplots(figsize=(4.5, 4))
    im = ax.imshow(cm, cmap=_sequential_cmap(), vmin=0, vmax=vmax)
    for i in range(2):
        for j in range(2):
            color = "white" if cm[i, j] > vmax * 0.5 else CHROME["primary_ink"]
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", color=color, fontsize=13, fontweight="bold")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["pred 0", "pred 1"])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["true 0", "true 1"])
    ax.set_title(f"Confusion matrix @ threshold={threshold:.2f}")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    return _save_fig(fig, study_dir, name)


def standard_binary_report(
    y_true: Any, proba: Any, study_dir: str | Path, *, threshold: float | None = None
) -> dict[str, Path]:
    """Emit the full binary-classification figure set. Returns name -> path."""
    if threshold is None:
        y_arr = np.asarray(y_true)
        p_arr = np.asarray(proba, dtype=float)
        thresholds = np.linspace(0.01, 0.99, 99)
        f1s = [f1_score(y_arr, (p_arr > t).astype(int), zero_division=0) for t in thresholds]
        threshold = float(thresholds[int(np.argmax(f1s))])

    return {
        "roc": plot_roc(y_true, proba, study_dir),
        "pr": plot_pr(y_true, proba, study_dir),
        "reliability": plot_reliability(y_true, proba, study_dir),
        "score_hist_by_class": plot_score_hist_by_class(y_true, proba, study_dir),
        "decile_lift": plot_decile_lift(y_true, proba, study_dir),
        "confusion_at_threshold": plot_confusion_at_threshold(y_true, proba, study_dir, threshold=threshold),
    }


# --------------------------------------------------------------------------
# Regression / severity
# --------------------------------------------------------------------------


def plot_pred_vs_actual(
    y_true: Any, y_pred: Any, study_dir: str | Path, *, name: str = "plot_pred_vs_actual"
) -> Path:
    """Scatter of predicted vs. actual, with the y=x reference line."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    lo, hi = float(min(y_true.min(), y_pred.min())), float(max(y_true.max(), y_pred.max()))

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(y_true, y_pred, s=14, alpha=0.5, color=CATEGORICAL[0], edgecolors="none")
    ax.plot([lo, hi], [lo, hi], color=CHROME["muted"], linestyle="--", linewidth=1, label="y = x")
    ax.set_xlabel("Actual")
    ax.set_ylabel("Predicted")
    ax.set_title("Predicted vs. actual")
    ax.legend(loc="upper left")
    return _save_fig(fig, study_dir, name)


def plot_residuals(
    y_true: Any, y_pred: Any, study_dir: str | Path, *, name: str = "plot_residuals"
) -> Path:
    """Scatter of residual (actual - predicted) vs. predicted, with a zero line."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    resid = y_true - y_pred

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(y_pred, resid, s=14, alpha=0.5, color=CATEGORICAL[0], edgecolors="none")
    ax.axhline(0.0, color=CHROME["muted"], linestyle="--", linewidth=1)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Residual (actual - predicted)")
    ax.set_title("Residuals vs. predicted")
    return _save_fig(fig, study_dir, name)


def plot_qq(y_true: Any, y_pred: Any, study_dir: str | Path, *, name: str = "plot_qq") -> Path:
    """Q-Q plot of residuals against the normal distribution."""
    resid = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    (osm, osr), (slope, intercept, r) = stats.probplot(resid, dist="norm")

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(osm, osr, s=14, alpha=0.6, color=CATEGORICAL[0], edgecolors="none", label="residuals")
    ax.plot(osm, slope * osm + intercept, color=CATEGORICAL[5], linewidth=1.5, label=f"normal fit (R={r:.3f})")
    ax.set_xlabel("Theoretical quantiles")
    ax.set_ylabel("Ordered residuals")
    ax.set_title("Q-Q plot of residuals")
    ax.legend(loc="upper left")
    return _save_fig(fig, study_dir, name)


def plot_lorenz(y_true: Any, y_pred: Any, study_dir: str | Path, *, name: str = "plot_lorenz") -> Path:
    """Lorenz/concentration curve (ordered by predicted risk) with Gini annotation."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    order = np.argsort(y_pred)
    y_sorted = y_true[order]

    cum_loss = np.concatenate([[0.0], np.cumsum(y_sorted)])
    total = cum_loss[-1]
    cum_loss_frac = cum_loss / total if total > 0 else cum_loss
    cum_pop_frac = np.linspace(0.0, 1.0, len(cum_loss_frac))

    area_under_curve = np.trapezoid(cum_loss_frac, cum_pop_frac)
    gini = 1.0 - 2.0 * float(area_under_curve)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(cum_pop_frac, cum_loss_frac, color=CATEGORICAL[0], linewidth=2, label="model-ordered Lorenz")
    ax.plot([0, 1], [0, 1], color=CHROME["muted"], linestyle="--", linewidth=1, label="equality line")
    ax.fill_between(cum_pop_frac, cum_loss_frac, cum_pop_frac, color=CATEGORICAL[0], alpha=0.15)
    ax.set_xlabel("Cumulative share of exposure (ordered by predicted risk)")
    ax.set_ylabel("Cumulative share of actual loss")
    ax.set_title(f"Lorenz curve (Gini = {gini:.3f})")
    ax.legend(loc="upper left")
    return _save_fig(fig, study_dir, name)


def plot_lift_quantile(
    y_true: Any, y_pred: Any, study_dir: str | Path, *, n_bins: int = 10, name: str = "plot_lift_quantile"
) -> Path:
    """CAS-style lift chart: mean actual vs. mean predicted over equal-weight quantiles."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    order = np.argsort(y_pred)
    y_sorted, p_sorted = y_true[order], y_pred[order]
    bins = _quantile_bins(len(p_sorted), n_bins)
    mean_actual = [float(y_sorted[b].mean()) for b in bins]
    mean_pred = [float(p_sorted[b].mean()) for b in bins]
    x = np.arange(1, len(bins) + 1)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x, mean_actual, marker="o", color=CATEGORICAL[0], linewidth=2, label="actual")
    ax.plot(x, mean_pred, marker="s", color=CATEGORICAL[5], linewidth=2, label="predicted")
    ax.set_xlabel(f"Quantile of predicted value (1=lowest, {len(bins)}=highest)")
    ax.set_ylabel("Mean value")
    ax.set_title("Lift by quantile: predicted vs. actual")
    ax.legend()
    return _save_fig(fig, study_dir, name)


def plot_calibration_by_decile(
    y_true: Any, y_pred: Any, study_dir: str | Path, *, n_bins: int = 10, name: str = "plot_calibration_by_decile"
) -> Path:
    """Actual/predicted ratio by decile of predicted value (actuarial A/E chart)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    order = np.argsort(y_pred)
    y_sorted, p_sorted = y_true[order], y_pred[order]
    bins = _quantile_bins(len(p_sorted), n_bins)
    ratios = []
    for b in bins:
        pred_sum = float(p_sorted[b].sum())
        ratios.append(float(y_sorted[b].sum()) / pred_sum if pred_sum != 0 else float("nan"))
    x = np.arange(1, len(bins) + 1)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(x, ratios, color=CATEGORICAL[0])
    ax.axhline(1.0, color=CHROME["muted"], linestyle="--", linewidth=1, label="perfect calibration (A/E = 1)")
    ax.set_xlabel(f"Decile of predicted value (1=lowest, {len(bins)}=highest)")
    ax.set_ylabel("Actual / Predicted ratio")
    ax.set_title("Calibration by decile (A/E ratio)")
    ax.legend()
    return _save_fig(fig, study_dir, name)


def standard_regression_report(y_true: Any, y_pred: Any, study_dir: str | Path) -> dict[str, Path]:
    """Emit the full regression/severity figure set. Returns name -> path."""
    return {
        "pred_vs_actual": plot_pred_vs_actual(y_true, y_pred, study_dir),
        "residuals": plot_residuals(y_true, y_pred, study_dir),
        "qq": plot_qq(y_true, y_pred, study_dir),
        "lorenz": plot_lorenz(y_true, y_pred, study_dir),
        "lift_quantile": plot_lift_quantile(y_true, y_pred, study_dir),
        "calibration_by_decile": plot_calibration_by_decile(y_true, y_pred, study_dir),
    }


# --------------------------------------------------------------------------
# Cross-cutting: experiment trajectory
# --------------------------------------------------------------------------


def plot_metric_trajectory(
    results_rows: Sequence[Mapping[str, Any]] | pd.DataFrame,
    study_dir: str | Path,
    *,
    name: str = "plot_metric_trajectory",
) -> Path:
    """Primary metric vs. experiment #, with `keep` rows highlighted.

    `results_rows` follows `kleinlib.schema.RESULTS_COLUMNS` (a DataFrame, or
    any sequence of mappings with at least `experiment`/`primary_metric`/
    `status`) — typically `results.tsv` read back in. Crashed rows
    (`primary_metric == schema.NA_METRIC`) are excluded from the line.
    """
    df = results_rows.copy() if isinstance(results_rows, pd.DataFrame) else pd.DataFrame(results_rows)
    df = df[df["primary_metric"].astype(str) != schema.NA_METRIC].copy()
    df["experiment"] = df["experiment"].astype(int)
    df["primary_metric"] = df["primary_metric"].astype(float)
    df = df.sort_values("experiment")

    keeps = df[df["status"] == "keep"]
    others = df[df["status"] != "keep"]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(df["experiment"], df["primary_metric"], color=CHROME["muted"], linewidth=1, zorder=1)
    ax.scatter(others["experiment"], others["primary_metric"], color=CHROME["muted"], s=30, label="discard/crash", zorder=2)
    ax.scatter(
        keeps["experiment"], keeps["primary_metric"], color=CATEGORICAL[1],
        s=70, edgecolors=CATEGORICAL[0], linewidths=1.5, label="keep", zorder=3,
    )
    ax.set_xlabel("Experiment #")
    ax.set_ylabel("Primary metric")
    ax.set_title("Metric trajectory")
    ax.legend()
    return _save_fig(fig, study_dir, name)
