"""method_check.py — the METHOD gate's quarantined verification artifact.

Runs the from-scratch Fisher discriminant against sklearn's LDA and reports the
checks `method_card.md` cites. **It scores nothing and touches no partition**: it
is fitted on all 100 hard-pair rows precisely so it can never become evidence on
the study's frontier. It writes nothing.

    uv run --locked python method_check.py

Checks
------
1. **Direction identity.** cosine(from-scratch w, sklearn LDA direction) for each of
   sklearn's three solvers (`svd`, `eigen`, `lsqr`). Pre-registered pass bar:
   **>= 1 - 1e-12**.
2. **Group means.** The four per-species means, to 3 decimal places.
3. **Convention probe.** How far the discriminant direction moves when the scatter
   matrix convention changes (pooled WITHIN-class vs TOTAL scatter about the grand
   mean, and ddof). This bounds what "a convention difference" can explain about the
   recorded gap to Fisher's printed 1936 coefficients — it does not resolve it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from prepare import FEATURE_COLUMNS, TARGET_COLUMN  # noqa: E402

PASS_BAR = 1.0 - 1e-12


def fisher_direction(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Fisher's linear discriminant, from scratch. Ten lines, numpy only.

    w = S_W^{-1} (mu_1 - mu_0), with S_W the pooled within-class scatter.
    Maximizes (w'(mu_1 - mu_0))^2 / (w' S_W w) — between-class separation per unit
    of within-class spread. Returned unit-normalized: only the DIRECTION is defined
    by the criterion, the scale is a convention.
    """
    X0, X1 = X[y == 0], X[y == 1]
    mu0, mu1 = X0.mean(axis=0), X1.mean(axis=0)
    S_W = (X0 - mu0).T @ (X0 - mu0) + (X1 - mu1).T @ (X1 - mu1)
    w = np.linalg.solve(S_W, mu1 - mu0)
    return w / np.linalg.norm(w)


def total_scatter_direction(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """The same formula with TOTAL scatter about the grand mean — a WRONG-but-plausible
    convention, used here only to bound how far a convention choice can move things."""
    mu = X.mean(axis=0)
    S_T = (X - mu).T @ (X - mu)
    mu0, mu1 = X[y == 0].mean(axis=0), X[y == 1].mean(axis=0)
    w = np.linalg.solve(S_T, mu1 - mu0)
    return w / np.linalg.norm(w)


def unit(v: np.ndarray) -> np.ndarray:
    return np.asarray(v, dtype=float).ravel() / np.linalg.norm(v)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(abs(unit(a) @ unit(b)))


def main() -> int:
    frame = pd.read_csv(HERE / "data" / "prepared" / "iris_hard_pair.csv")
    X = frame[FEATURE_COLUMNS].to_numpy(dtype=float)
    y = frame[TARGET_COLUMN].to_numpy(dtype=int)

    print(f"rows fitted: {len(frame)} (ALL of them — this artifact scores nothing)")
    print(f"features: {FEATURE_COLUMNS}")
    print()

    w_scratch = fisher_direction(X, y)
    print("1. DIRECTION IDENTITY — from-scratch vs sklearn LinearDiscriminantAnalysis")
    print(f"   pre-registered pass bar: cosine >= 1 - 1e-12 = {PASS_BAR:.15f}")
    print(f"   from-scratch w (unit): {np.array2string(w_scratch, precision=9)}")
    failures = 0
    for solver in ("svd", "eigen", "lsqr"):
        lda = LinearDiscriminantAnalysis(solver=solver)
        lda.fit(X, y)
        cos = cosine(w_scratch, lda.coef_[0])
        ok = cos >= PASS_BAR
        failures += not ok
        print(
            f"   solver={solver:<6} cosine={cos:.15f}  1-cosine={1.0 - cos:.3e}  "
            f"{'PASS' if ok else 'FAIL'}"
        )
    print()

    print("2. GROUP MEANS (3 dp)")
    means = frame.groupby("species")[FEATURE_COLUMNS].mean().round(3)
    names = {1: "versicolor", 2: "virginica"}
    print(f"   {'species':<12}" + "".join(f"{c:>18}" for c in FEATURE_COLUMNS))
    for code, row in means.iterrows():
        print(f"   {names[int(code)]:<12}" + "".join(f"{row[c]:>18.3f}" for c in FEATURE_COLUMNS))
    print()

    print("3. CONVENTION PROBE — what can and cannot move the discriminant direction?")
    X0, X1 = X[y == 0], X[y == 1]
    mu0, mu1 = X0.mean(axis=0), X1.mean(axis=0)
    delta = mu1 - mu0
    S_W = (X0 - mu0).T @ (X0 - mu0) + (X1 - mu1).T @ (X1 - mu1)

    w_total = total_scatter_direction(X, y)
    print(f"   a) TOTAL scatter about the grand mean instead of pooled WITHIN-class:")
    print(f"        cosine = {cosine(w_scratch, w_total):.15f}")
    print("        Not a coincidence: S_T = S_W + S_B and S_B is rank-1 along (mu1-mu0),")
    print("        so by Sherman-Morrison S_T^-1 (mu1-mu0) is a positive multiple of")
    print("        S_W^-1 (mu1-mu0). Same direction, exactly. NOT an explanation.")
    for ddof, label in ((0, "ddof=0 (population)"), (1, "ddof=1 (sample)")):
        n = len(X0) + len(X1)
        S = S_W / (n - 2 if ddof == 1 else n)
        w = np.linalg.solve(S, delta)
        print(f"   b) {label:<22} cosine vs from-scratch = {cosine(w_scratch, w):.15f}")
    print("        Any positive rescaling of the scatter matrix leaves the direction")
    print("        untouched. 'Covariance vs sum-of-squares' and ddof are NOT explanations.")

    print("   c) HAND-ARITHMETIC ROUNDING — Fisher computed this in 1936 by hand.")
    print("      Round the scatter matrix to k significant figures, re-solve, compare:")
    for sig in (2, 3, 4, 5):
        with np.errstate(divide="ignore"):
            scale = np.where(S_W == 0, 1.0, 10.0 ** (sig - 1 - np.floor(np.log10(np.abs(S_W)))))
        S_round = np.round(S_W * scale) / scale
        w_round = np.linalg.solve(S_round, delta)
        cos = cosine(w_scratch, w_round)
        print(f"        {sig} sig. figs -> cosine {cos:.9f}   (1-cosine {1.0 - cos:.3e})")
    print("      Reading: rounding the intermediate scatter matrix the way a 1936 desk")
    print("      calculation would is a CANDIDATE explanation whose magnitude is bounded")
    print("      above. Whether it covers the recorded gap to Fisher's PRINTED")
    print("      coefficients is settled by re-deriving those coefficients from a")
    print("      verified source — not by this probe. Logged, not resolved.")

    lda_svd = LinearDiscriminantAnalysis(solver="svd").fit(X, y)
    print()
    print(f"   sklearn svd coef_ (raw, unnormalized): "
          f"{np.array2string(lda_svd.coef_[0], precision=6)}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
