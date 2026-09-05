"""METHOD-gate (Gate 2) pedagogy artifact: the from-scratch LDA of `method_card.md` §3.1,
checked numerically against `sklearn.discriminant_analysis.LinearDiscriminantAnalysis`.

This is NOT the mutable experiment surface (`train.py` is), NOT library code
(`lib/iris.py` will be), and NOT a verifier (this study declares none — it is
`kind: predict`, nothing is checkpoint-scored). Nothing imports it. It exists so
that the method card's Practice leg is re-runnable by a referee rather than
merely asserted, and so nobody in this study has to take scikit-learn's word for
what Fisher's 1936 method computes.

What it deliberately does NOT do
--------------------------------
It does not score the development block and it never reads the sealed block. The
fit and every comparison below use the 49 TRAINING rows only, obtained through
`kleinlib.data.contract_split` (never a literal seed — war story 8). This gate
measures an implementation agreement, not a result; no evidence is spent here.

Run::

    uv run --locked python studies/15-iris-90years-relaunch/method_check_lda.py

Measured on 2026-09-04 (scikit-learn 1.9.0, numpy 2.5.1):
    cosine similarity of the two discriminant directions = 1.000000000000000
    max |w_scratch - w_sklearn|                          = 7.105e-15
    |b_scratch - b_sklearn|                              = 1.776e-14
    max |score difference| over the 49 training rows     = 1.776e-14
    Fisher criterion J(w), both vectors                  = 0.318850456779
    cos(Fisher 1936 §VI compound, this fit)              = 0.990203  (8.03 degrees)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

from kleinlib.data import contract_split

STUDY_DIR = Path(__file__).resolve().parent

# Fisher (1936) §VI, "Applications to the theory of allopolyploidy", p. 186: the
# coefficients of the three-species compound, as printed (multiplied by 100), in
# the column order sepal length, sepal breadth, petal length, petal breadth.
# Transcribed from the Annals of Human Genetics archive scan. NOT a two-class
# discriminant of the hard pair — see method_card.md §5.1.
FISHER_1936_SECTION_VI = np.array([-3.308998, -2.759132, 8.866048, 9.392551])


def lda_from_scratch(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Equations E1-E4 of method_card.md §2, in plain numpy. Returns (w, b, S_W, S_B)."""
    classes = np.unique(y)
    n, p = X.shape
    K = classes.size

    mus = np.stack([X[y == c].mean(axis=0) for c in classes])      # (K, p)
    priors = np.array([(y == c).mean() for c in classes])          # (K,)

    S_W = np.zeros((p, p))                                         # E1
    for k, c in enumerate(classes):
        Z = X[y == c] - mus[k]
        S_W += Z.T @ Z
    Sigma = S_W / (n - K)                                          # pooled covariance

    d = mus[1] - mus[0]
    S_B = np.outer(d, d)                                           # E1

    w = np.linalg.solve(Sigma, d)                                  # E3
    b = -0.5 * (                                                   # E4
        mus[1] @ np.linalg.solve(Sigma, mus[1])
        - mus[0] @ np.linalg.solve(Sigma, mus[0])
    ) + np.log(priors[1] / priors[0])
    return w, float(b), S_W, S_B


def main() -> int:
    X_tr, X_dev, _X_te, y_tr, _y_dev, _y_te = contract_split(STUDY_DIR)
    X = X_tr.to_numpy(dtype=float)
    y = y_tr.to_numpy(dtype=int)
    print(f"columns:     {list(X_tr.columns)}")
    print(f"train rows:  {X.shape[0]} (class counts {np.bincount(y).tolist()})")
    print(f"development rows: {len(X_dev)} — NOT scored here; the sealed block is never read")

    w, b, S_W, S_B = lda_from_scratch(X, y)
    sk = LinearDiscriminantAnalysis(solver="svd").fit(X, y)
    w_sk, b_sk = sk.coef_[0], float(sk.intercept_[0])

    def fisher_ratio(v: np.ndarray) -> float:                       # E2
        return float((v @ S_B @ v) / (v @ S_W @ v))

    cos = float(w @ w_sk / (np.linalg.norm(w) * np.linalg.norm(w_sk)))
    score_scratch, score_sk = X @ w + b, sk.decision_function(X)

    print()
    print(f"w_scratch:   {np.array2string(w, precision=10)}")
    print(f"w_sklearn:   {np.array2string(w_sk, precision=10)}")
    print(f"b_scratch:   {b:.12f}")
    print(f"b_sklearn:   {b_sk:.12f}")
    print()
    print(f"cosine similarity(w_scratch, w_sklearn): {cos:.15f}")
    print(f"max |w_scratch - w_sklearn|:             {np.max(np.abs(w - w_sk)):.3e}")
    print(f"max relative coefficient difference:     {np.max(np.abs((w - w_sk) / w_sk)):.3e}")
    print(f"|b_scratch - b_sklearn|:                 {abs(b - b_sk):.3e}")
    print(f"max |score difference| (49 train rows):  {np.max(np.abs(score_scratch - score_sk)):.3e}")
    print(f"identical predicted labels on train:     {bool(np.all((score_scratch > 0) == (score_sk > 0)))}")
    print(f"Fisher criterion J(w) scratch / sklearn: {fisher_ratio(w):.12f} / {fisher_ratio(w_sk):.12f}")
    print(f"J(3.7 * w_scratch) (E2 scale-invariance): {fisher_ratio(3.7 * w):.12f}")

    cos_1936 = float(
        FISHER_1936_SECTION_VI @ w
        / (np.linalg.norm(FISHER_1936_SECTION_VI) * np.linalg.norm(w))
    )
    print()
    print(f"cos(Fisher 1936 §VI compound, this fit): {cos_1936:.6f}  "
          f"({np.degrees(np.arccos(cos_1936)):.2f} degrees apart)")

    ok = (
        np.allclose(w, w_sk, rtol=1e-10, atol=1e-12)
        and np.allclose(b, b_sk, rtol=1e-10, atol=1e-10)
        and np.allclose(score_scratch, score_sk, rtol=1e-10, atol=1e-10)
    )
    print()
    print("PRACTICE LEG:", "AGREES" if ok else "DISAGREES — the method card is wrong")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
