"""The power-law fit and the extrapolation arithmetic — outside the mutable surface.

``log L = log a - alpha log N``, fitted by ordinary least squares to the SEED
MEANS of the pinned development cells (one point per training-set size N), with
``fit_r2`` on the log scale and a percentile bootstrap interval for alpha that
resamples the seeds WITHIN each N (independently across N; 2,000 draws, a fixed
resampling seed). Within a seed the cells' subsamples are nested
(`lib/protocol.py`), so losses at different N of the same seed are positively
correlated; resampling within N ignores that pairing, which for a slope makes the
interval wider, not narrower. With 3 seeds per N the resampled mean's variance is
(3-1)/3 of the sample variance of the mean — a known small-sample shortfall of
the percentile bootstrap, stated rather than corrected.

``tables/scaling_fit.tsv`` carries one row per N (``n_train, n_seeds,
mean_val_mlogloss, std_val_mlogloss, fitted_loss``) and repeats the fit's
parameters on every row (``a, alpha, fit_r2, alpha_ci_low, alpha_ci_high,
predicted_loss_at_full``), so each row is self-contained and the sealed run reads
``a`` and ``alpha`` from any of them (:func:`read_fit` checks they agree).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from kleinlib.primitives import sha256_file

CELL_GLOB = "cell_*_s*.tsv"
CELL_NAME_RE = re.compile(r"^cell_(?P<run>.+)_s(?P<seed>-?\d+)\.tsv$")
CELL_COLUMNS = ("run", "seed", "n_train", "val_mlogloss", "best_step")
FIT_TABLE = "tables/scaling_fit.tsv"
FIT_PARAMETER_COLUMNS = ("a", "alpha", "fit_r2", "alpha_ci_low", "alpha_ci_high", "predicted_loss_at_full")
MIN_SIZES = 3
BOOTSTRAP_DRAWS = 2_000
#: A RESAMPLING seed for the bootstrap, not a partition seed: the partitions come
#: from the contract (`kleinlib.data`), and this only orders the resampling draws.
BOOTSTRAP_SEED = 20_261_103


def pinning_manifest(study: Path, rel: str, *, track: str) -> dict[str, Any] | None:
    """The newest ``measured`` manifest of ``track`` that pins ``rel``, or None."""
    found = None
    for path in sorted((study / "runs").glob("E*/manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("track") != track or manifest.get("disposition") != "measured":
            continue
        if rel in (manifest.get("artifacts") or {}):
            found = manifest
    return found


def collect_cells(study: Path, *, require_pinned: bool) -> tuple[pd.DataFrame, list[str]]:
    """Every development cell row in ``tables/cell_*_s*.tsv``; ``(rows, notes)``.

    With ``require_pinned`` (every real run) a table counts only when the manifest
    of the run it names is a ``measured`` development run of the ``primary`` track,
    pins this exact path, and the bytes on disk still hash to the pin; a table
    from a run that crashed or was discarded is left out and named in ``notes``; a
    table with no manifest at all, or whose bytes differ from its pin, stops the
    fit (it is not evidence, and silently dropping it would hide why). Without it
    (``KLEIN_SMOKE=1`` against synthetic tables) every table counts.
    """
    rows: list[pd.DataFrame] = []
    notes: list[str] = []
    for path in sorted((study / "tables").glob(CELL_GLOB)):
        rel = path.relative_to(study).as_posix()
        match = CELL_NAME_RE.match(path.name)
        if match is None:
            raise ValueError(f"{rel}: not a cell table name (cell_<run>_s<seed>.tsv)")
        frame = pd.read_csv(path, sep="\t", dtype={"run": str})
        missing = [c for c in CELL_COLUMNS if c not in frame.columns]
        if missing or len(frame) != 1:
            raise ValueError(f"{rel}: expected one row with columns {list(CELL_COLUMNS)}; missing {missing}")
        run, seed = str(frame["run"].iloc[0]), int(frame["seed"].iloc[0])
        if (run, seed) != (match["run"], int(match["seed"])):
            raise ValueError(f"{rel}: holds run {run} seed {seed}, which is not the run its name says")
        if require_pinned:
            manifest_path = study / "runs" / run / "manifest.json"
            if not manifest_path.is_file():
                raise ValueError(f"{rel}: no manifest runs/{run}/manifest.json — an unpinned table is not evidence")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("track") != "primary" or manifest.get("evaluation_kind", "development") != "development":
                raise ValueError(f"{rel}: run {run} is not a development cell of the primary track")
            if manifest.get("disposition") != "measured":
                notes.append(f"excluded {rel}: run {run} disposition {manifest.get('disposition')!r}")
                continue
            pinned = (manifest.get("artifacts") or {}).get(rel)
            if not pinned:
                raise ValueError(f"{rel}: run {run}'s manifest does not pin this table")
            if pinned.get("sha256") != sha256_file(path):
                raise ValueError(f"{rel}: bytes differ from the sha256 pinned by run {run}")
        rows.append(frame[list(CELL_COLUMNS)])
    if not rows:
        raise ValueError("no development cell tables (tables/cell_*_s*.tsv) to fit")
    table = pd.concat(rows, ignore_index=True)
    duplicated = table[table.duplicated(["run", "seed"], keep=False)]
    if not duplicated.empty:
        raise ValueError(f"duplicate (run, seed) cell rows: {duplicated[['run', 'seed']].values.tolist()}")
    if not np.all(np.isfinite(table["val_mlogloss"].to_numpy(dtype=float))) or (table["val_mlogloss"] <= 0).any():
        raise ValueError("cell losses must be finite and positive for a log-log fit")
    return table, notes


def ols_loglog(sizes: np.ndarray, losses: np.ndarray) -> tuple[float, float, float]:
    """``(a, alpha, r2)`` of ``log L = log a - alpha log N`` by least squares."""
    x, y = np.log(np.asarray(sizes, dtype=float)), np.log(np.asarray(losses, dtype=float))
    slope, intercept = np.polyfit(x, y, 1)
    residual = y - (intercept + slope * x)
    total = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - float(np.sum(residual**2)) / total if total > 0 else float("nan")
    return float(np.exp(intercept)), float(-slope), r2


def fit_cells(table: pd.DataFrame, *, n_full: int) -> tuple[pd.DataFrame, dict[str, float]]:
    """Seed means per N, the log-log fit, and the bootstrap interval for alpha."""
    groups = {int(n): g["val_mlogloss"].to_numpy(dtype=float) for n, g in table.groupby("n_train")}
    sizes = np.array(sorted(groups), dtype=float)
    if sizes.size < MIN_SIZES:
        raise ValueError(f"the fit needs measured cells at >= {MIN_SIZES} sizes, found {sizes.size}")
    means = np.array([groups[int(n)].mean() for n in sizes])
    a, alpha, r2 = ols_loglog(sizes, means)

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_DRAWS)
    for i in range(BOOTSTRAP_DRAWS):
        resampled = [rng.choice(groups[int(n)], size=groups[int(n)].size, replace=True).mean() for n in sizes]
        draws[i] = ols_loglog(sizes, np.array(resampled))[1]
    low, high = (float(q) for q in np.quantile(draws, [0.025, 0.975]))
    clamped = not (low <= alpha <= high)
    params = {
        "a": a,
        "alpha": alpha,
        "fit_r2": r2,
        # A percentile interval can, rarely, exclude its own point estimate; it is
        # widened to include it and `ci_clamped` says so on the printed block.
        "alpha_ci_low": min(low, alpha),
        "alpha_ci_high": max(high, alpha),
        "ci_clamped": float(clamped),
        "predicted_loss_at_full": a * float(n_full) ** (-alpha),
        "n_sizes": float(sizes.size),
        "n_cell_rows": float(len(table)),
    }
    per_n = pd.DataFrame(
        {
            "n_train": sizes.astype(int),
            "n_seeds": [groups[int(n)].size for n in sizes],
            "mean_val_mlogloss": means,
            "std_val_mlogloss": [groups[int(n)].std(ddof=1) if groups[int(n)].size > 1 else 0.0 for n in sizes],
            "fitted_loss": a * sizes ** (-alpha),
        }
    )
    for key in FIT_PARAMETER_COLUMNS:
        per_n[key] = params[key]
    return per_n, params


def write_fit(study: Path, per_n: pd.DataFrame) -> str:
    path = study / FIT_TABLE
    path.parent.mkdir(parents=True, exist_ok=True)
    per_n.to_csv(path, sep="\t", index=False, lineterminator="\n", float_format="%.10g")
    return FIT_TABLE


def read_fit(path: Path) -> tuple[float, float]:
    """``(a, alpha)`` from a fit table; raises when it is missing or inconsistent."""
    if not path.is_file():
        raise FileNotFoundError(
            f"{path.name} is missing — a sealed extrapolation without a pinned fit is a crash; "
            "run the exponent track first"
        )
    frame = pd.read_csv(path, sep="\t")
    missing = [c for c in ("a", "alpha") if c not in frame.columns]
    if missing or frame.empty:
        raise ValueError(f"{path.name}: no fit parameters (missing {missing})")
    a_values, alpha_values = frame["a"].unique(), frame["alpha"].unique()
    if a_values.size != 1 or alpha_values.size != 1:
        raise ValueError(f"{path.name}: rows disagree on the fit parameters")
    a, alpha = float(a_values[0]), float(alpha_values[0])
    if not (np.isfinite(a) and a > 0 and np.isfinite(alpha)):
        raise ValueError(f"{path.name}: unusable fit parameters a={a!r}, alpha={alpha!r}")
    return a, alpha


def extrapolation(a: float, alpha: float, n: int, measured: float) -> Mapping[str, float]:
    """The law's prediction at ``n`` and the signed relative error of ``measured``.

    ``extrapolation_rel_error = (measured - predicted) / measured``: positive when
    the measured loss is ABOVE the pure power law (the law was optimistic).
    """
    predicted = a * float(n) ** (-alpha)
    return {"predicted_loss": predicted, "extrapolation_rel_error": (measured - predicted) / measured}
