"""Study 23's library: the published targets, the estimators, and the table writer.

Outside the mutable surface on purpose (AGENTS.md: library code changes rarely,
deliberately, never as part of a cell's diff). A cell in analyze.py only CHOOSES:
which lane, which estimator, which propensity specification.

Everything here is deterministic given the prepared table: unpenalized logits on
standardized columns (a logit is invariant to rescaling its regressors, so the
scores are the textbook ones), closed-form OLS, and a bootstrap with a fixed seed.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

BOOTSTRAP_SEED = 20261103

# ------------------------------------------------------------------ published targets
#: Dehejia & Wahba (1999, JASA 94(448)) Table 3, columns (1) "unadjusted" and (2)
#: "adjusted" — identical in NBER working paper w6586 (1998), Table 3. 1982 dollars,
#: standard errors in parentheses there. Table 1 gives the sample sizes.
#: Column (2) is least squares of RE78 on a constant, the treatment indicator, age,
#: age^2, educ, nodegree, black, hisp, RE74, RE75 (Table 3 note a).
TARGETS: dict[str, dict[str, float]] = {
    "development": {
        "nsw_unadjusted": 1794, "nsw_unadjusted_se": 633,
        "nsw_adjusted": 1672, "nsw_adjusted_se": 638,
        "psid1_unadjusted": -15205, "psid1_unadjusted_se": 1154,
        "psid1_adjusted": 731, "psid1_adjusted_se": 886,
        "n_nsw_treated": 185, "n_nsw_control": 260, "n_psid1": 2490,
    },
    "final_test": {
        "cps1_unadjusted": -8498, "cps1_unadjusted_se": 712,
        "cps1_adjusted": 972, "cps1_adjusted_se": 550,
        "n_cps1": 15992,
    },
}
#: |reproduced - printed| allowed: the paper prints whole dollars, so +-1 covers its
#: rounding (0.5) and the float storage of 1982-dollar earnings in the .dta files.
TOLERANCE = 1.0

ADJUSTMENT = ["age", "age2", "education", "nodegree", "black", "hispanic", "re74", "re75"]

#: DIAGNOSTICS, never targets. Table 3's column (2) is not one regression: its NSW value
#: (1,672) equals Table 2 Panel C column (4) — note a's covariates — while its PSID-1 (731)
#: and CPS-1 (972) values equal Panel C column (5), "all pre-treatment covariates"
#: (found at the METHOD gate, method_card.md). The reproduction cell prints both
#: regressions beside the registered targets so the run shows which is which; the
#: column-(5) covariate list is not printed in the paper, so two readings are tried.
ADJUSTMENT_ALL = {
    "all_married": ADJUSTMENT + ["married"],
    "all_married_u": ADJUSTMENT + ["married", "u74", "u75"],
}
#: Table 2 Panel C, columns (4) and (5), for the diagnostics' comparison column.
PANEL_C = {
    "nsw": {"col4": 1672, "col5": 1655},
    "psid1": {"col4": 218, "col5": 731},
    "cps1": {"col4": 739, "col5": 972},
}

#: Propensity specifications. `dw_psid` is Table 3 note c (the PSID-1 logit);
#: `no_re74` drops every 1974-earnings term (the DW 1999 section 5 / Smith & Todd 2005
#: sensitivity: is two years of pre-program earnings what makes it work?).
PROPENSITY: dict[str, list[str]] = {
    "dw_psid": ["age", "age2", "education", "educ2", "married", "nodegree", "black", "hispanic",
                "re74", "re75", "re74sq", "re75sq", "u74_black"],
    "no_re74": ["age", "age2", "education", "educ2", "married", "nodegree", "black", "hispanic",
                "re75", "re75sq", "u75"],
}


def features(frame: pd.DataFrame) -> pd.DataFrame:
    """The derived columns every specification draws from (all pre-treatment)."""
    out = frame.copy()
    out["age2"] = out["age"] ** 2
    out["educ2"] = out["education"] ** 2
    out["re74sq"] = out["re74"] ** 2
    out["re75sq"] = out["re75"] ** 2
    out["u74"] = (out["re74"] == 0).astype(int)
    out["u75"] = (out["re75"] == 0).astype(int)
    out["u74_black"] = out["u74"] * out["black"]
    return out


# ------------------------------------------------------------------ least squares


def ols_treat(y: np.ndarray, t: np.ndarray, X: np.ndarray | None = None) -> tuple[float, float]:
    """Coefficient on t and its classical (homoskedastic) standard error."""
    columns = [np.ones_like(t, dtype=float), t.astype(float)]
    if X is not None:
        columns += [X[:, j].astype(float) for j in range(X.shape[1])]
    design = np.column_stack(columns)
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    dof = len(y) - design.shape[1]
    sigma2 = float(resid @ resid) / dof
    cov = sigma2 * np.linalg.inv(design.T @ design)
    return float(beta[1]), float(np.sqrt(cov[1, 1]))


def diagnostics(treated: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, float]:
    """The column-(5) candidates: OLS coefficient on treat under each ADJUSTMENT_ALL list."""
    both = pd.concat([treated, comparison])
    y = both["re78"].to_numpy(float)
    t = both["treat"].to_numpy(int)
    return {name: ols_treat(y, t, both[cols].to_numpy(float))[0] for name, cols in ADJUSTMENT_ALL.items()}


def contrast(treated: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, float]:
    both = pd.concat([treated, comparison])
    y = both["re78"].to_numpy(float)
    t = both["treat"].to_numpy(int)
    unadj, unadj_se = ols_treat(y, t)
    adj, adj_se = ols_treat(y, t, both[ADJUSTMENT].to_numpy(float))
    return {"unadjusted": unadj, "unadjusted_se": unadj_se, "adjusted": adj, "adjusted_se": adj_se}


# ------------------------------------------------------------------ propensity estimators


@dataclass(frozen=True)
class Estimate:
    att: float
    n_treated: int
    n_controls_used: int
    max_weight_share: float  # the largest single control weight / total control weight


def propensity(treated: pd.DataFrame, comparison: pd.DataFrame, spec: str) -> tuple[np.ndarray, np.ndarray]:
    columns = PROPENSITY[spec]
    both = pd.concat([treated, comparison])
    X = StandardScaler().fit_transform(both[columns].to_numpy(float))
    t = both["treat"].to_numpy(int)
    model = LogisticRegression(penalty=None, max_iter=20000, tol=1e-10).fit(X, t)
    score = model.predict_proba(X)[:, 1]
    return score[: len(treated)], score[len(treated):]


def att(treated: pd.DataFrame, comparison: pd.DataFrame, *, estimator: str, spec: str) -> Estimate:
    e1, e0 = propensity(treated, comparison, spec)
    y1 = treated["re78"].to_numpy(float)
    y0 = comparison["re78"].to_numpy(float)
    # Common support, Table 3 note g: comparison units inside the treated score range.
    keep = (e0 >= e1.min()) & (e0 <= e1.max())
    e0k, y0k = np.clip(e0[keep], 1e-12, 1 - 1e-12), y0[keep]
    if estimator == "match":
        # 1-nearest-neighbour on the score, with replacement (Table 3 column 7's design).
        order = np.argsort(e0k)
        sorted_e = e0k[order]
        pos = np.clip(np.searchsorted(sorted_e, e1), 1, len(sorted_e) - 1)
        left, right = sorted_e[pos - 1], sorted_e[pos]
        nearest = np.where(np.abs(e1 - left) <= np.abs(right - e1), pos - 1, pos)
        matched = y0k[order][nearest]
        counts = np.bincount(nearest, minlength=len(sorted_e))
        return Estimate(float(np.mean(y1 - matched)), len(y1), int((counts > 0).sum()),
                        float(counts.max() / counts.sum()))
    w = e0k / (1 - e0k)  # ATT odds weights
    share = float(w.max() / w.sum())
    if estimator == "ipw":
        return Estimate(float(y1.mean() - np.average(y0k, weights=w)), len(y1), int(keep.sum()), share)
    if estimator == "aipw":
        X0 = comparison.loc[keep, ADJUSTMENT].to_numpy(float)
        design0 = np.column_stack([np.ones(len(X0)), X0])
        beta, *_ = np.linalg.lstsq(design0, y0k, rcond=None)
        mu1 = np.column_stack([np.ones(len(treated)), treated[ADJUSTMENT].to_numpy(float)]) @ beta
        mu0 = design0 @ beta
        return Estimate(float(np.mean(y1 - mu1) - np.average(y0k - mu0, weights=w)),
                        len(y1), int(keep.sum()), share)
    raise ValueError(f"unknown estimator {estimator!r}")


def bootstrap(treated: pd.DataFrame, comparison: pd.DataFrame, *, estimator: str, spec: str,
              reps: int) -> np.ndarray:
    """Percentile-bootstrap draws, resampling treated and comparison separately and
    re-fitting the propensity model in every draw (the score is estimated, not given)."""
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(reps)
    for b in range(reps):
        tb = treated.iloc[rng.integers(0, len(treated), len(treated))]
        cb = comparison.iloc[rng.integers(0, len(comparison), len(comparison))]
        draws[b] = att(tb, cb, estimator=estimator, spec=spec).att
    return draws


# ------------------------------------------------------------------ pinned tables


def study_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def write_table(relative_path: str, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> Path:
    """Deterministic TSV (fixed columns, %.6f, LF); not written under KLEIN_SMOKE=1."""
    path = study_dir() / relative_path
    text = pd.DataFrame(list(rows), columns=list(columns)).to_csv(
        index=False, sep="\t", float_format="%.6f", lineterminator="\n"
    )
    if os.environ.get("KLEIN_SMOKE") == "1":
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path
