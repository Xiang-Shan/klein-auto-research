"""Off-ledger gap forensics for study 05 — analysis, not evidence.

Three tools, all reading models/predictions produced by the sanctioned loop:

- segment_deviance_gap: WHERE the gap lives — additive per-segment attribution
  (weighted Poisson deviance decomposes over disjoint segments).
- surrogate_glm: the translate-back mechanism — fit an interpretable linear
  surrogate to the GBDT's log-predictions on the TRAIN fold only, then rank
  candidate 2-way numeric interactions by how much surrogate residual they
  explain. Derive on train, evaluate on dev, confirm sealed (multiplicity
  discipline lives in program.md: screened vs adopted counts are reported).
- two_way_pd_gap: model-agnostic 2-D partial dependence minus the additive sum
  of 1-D PDs, on the log scale (GLM additivity is log-scale additivity), over
  an exposure-subsampled frame — the non-additive signature of an interaction.

Nothing here writes ledger state; figures/tables land in program.md and figures/.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd


def _poisson_dev_rows(y_rate: np.ndarray, mu: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Per-row weighted Poisson deviance contributions (sum = total weighted dev)."""
    y = np.asarray(y_rate, dtype=float)
    mu = np.asarray(mu, dtype=float)
    w = np.asarray(w, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = np.where(y > 0, y * np.log(y / mu) - (y - mu), mu)
    return 2.0 * w * term


def segment_deviance_gap(
    y_rate, w, pred_glm, pred_gbdt, seg: pd.Series, *, n_bins: int = 8
) -> pd.DataFrame:
    """Per-segment attribution of the GLM-minus-GBDT deviance gap.

    ``seg`` is a raw rating-factor column aligned with the eval fold; numeric
    columns are quantile-binned into ``n_bins``. Returns one row per segment:
    exposure share, per-model mean deviance, and the segment's share of the
    total gap (shares sum to 1 when the gap is positive everywhere it matters).
    """
    seg = pd.Series(np.asarray(seg), name=seg.name if hasattr(seg, "name") else "seg")
    if pd.api.types.is_numeric_dtype(seg) and seg.nunique() > n_bins:
        seg = pd.qcut(seg, q=n_bins, duplicates="drop")
    d_glm = _poisson_dev_rows(y_rate, pred_glm, w)
    d_gbdt = _poisson_dev_rows(y_rate, pred_gbdt, w)
    frame = pd.DataFrame(
        {"seg": seg.to_numpy(), "w": np.asarray(w, float), "d_glm": d_glm, "d_gbdt": d_gbdt}
    )
    total_gap = frame["d_glm"].sum() - frame["d_gbdt"].sum()
    g = frame.groupby("seg", observed=True)
    out = pd.DataFrame(
        {
            "exposure_share": g["w"].sum() / frame["w"].sum(),
            "mean_dev_glm": g["d_glm"].sum() / g["w"].sum(),
            "mean_dev_gbdt": g["d_gbdt"].sum() / g["w"].sum(),
            "gap_share": (g["d_glm"].sum() - g["d_gbdt"].sum()) / total_gap,
        }
    )
    return out.sort_values("gap_share", ascending=False)


def surrogate_glm(
    log_mu_train: np.ndarray, X_train: pd.DataFrame, numeric_cols: list[str], *, w=None
) -> dict:
    """Distill the GBDT's TRAIN-fold log-predictions into main effects, then rank
    2-way numeric interactions by residual correlation.

    Main-effect basis: per-column standardized cubic terms (x, x^2, x^3) — a cheap
    stand-in for the scoped-spline basis that needs no sklearn plumbing here.
    Returns {"r2_main": ..., "ranked_pairs": [(colA, colB, |resid corr|), ...]}.
    """
    y = np.asarray(log_mu_train, dtype=float)
    w = np.ones_like(y) if w is None else np.asarray(w, dtype=float)
    cols = []
    for c in numeric_cols:
        x = X_train[c].to_numpy(dtype=float)
        x = (x - x.mean()) / (x.std() + 1e-12)
        cols += [x, x**2, x**3]
    A = np.column_stack([np.ones_like(y)] + cols)
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)
    resid = y - A @ beta
    ss_res = float(np.sum(w * resid**2))
    ss_tot = float(np.sum(w * (y - np.average(y, weights=w)) ** 2))
    r2_main = 1.0 - ss_res / ss_tot
    std = {
        c: (X_train[c].to_numpy(float) - X_train[c].mean()) / (X_train[c].std() + 1e-12)
        for c in numeric_cols
    }
    ranked = []
    for a, b in itertools.combinations(numeric_cols, 2):
        prod = std[a] * std[b]
        prod = (prod - prod.mean()) / (prod.std() + 1e-12)
        corr = float(np.abs(np.average(prod * resid, weights=w))
                     / (np.sqrt(np.average(resid**2, weights=w)) + 1e-12))
        ranked.append((a, b, corr))
    ranked.sort(key=lambda t: -t[2])
    return {"r2_main": r2_main, "ranked_pairs": ranked}


def _pd_1d(model, X: pd.DataFrame, col: str, grid: np.ndarray) -> np.ndarray:
    out = np.empty(len(grid))
    Xc = X.copy()
    for i, v in enumerate(grid):
        Xc[col] = v
        out[i] = np.log(model.predict(Xc)).mean()
    return out


def two_way_pd_gap(model, X_sub: pd.DataFrame, pair: tuple[str, str], *, n_grid: int = 8) -> dict:
    """Non-additive interaction signature on the log scale.

    PD2(a,b) - [PD1(a) + PD1(b)] over a quantile grid, all centered; the std of
    the residual surface is the interaction strength in log-rate units.
    """
    a, b = pair
    ga = np.quantile(X_sub[a].to_numpy(float), np.linspace(0.05, 0.95, n_grid))
    gb = np.quantile(X_sub[b].to_numpy(float), np.linspace(0.05, 0.95, n_grid))
    pd_a = _pd_1d(model, X_sub, a, ga)
    pd_b = _pd_1d(model, X_sub, b, gb)
    surf = np.empty((n_grid, n_grid))
    Xc = X_sub.copy()
    for i, va in enumerate(ga):
        Xc[a] = va
        for j, vb in enumerate(gb):
            Xc[b] = vb
            surf[i, j] = np.log(model.predict(Xc)).mean()
    surf -= surf.mean()
    additive = (pd_a - pd_a.mean())[:, None] + (pd_b - pd_b.mean())[None, :]
    resid = surf - additive
    return {
        "pair": pair,
        "grid_a": ga,
        "grid_b": gb,
        "interaction_surface": resid,
        "strength": float(resid.std()),
    }
