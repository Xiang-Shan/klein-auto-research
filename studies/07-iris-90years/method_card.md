---
type: method-card
domain: "statistics-history"
status: draft
concepts: [linear-discriminant-analysis, fisher-1936, brier-score, generalized-eigenproblem]
related: [scouting_ledger.md, method_check.py, families.py]
refs_verified: false   # set true ONLY after every reference below is verified
triad:                 # the Theory + Papers + Practice contract — self-asserted, gate-checked
  theory: true         # §2: notation table + the load-bearing equations
  papers: false        # PENDING: both references are citation-verification-pending (Tuesday)
  practice: true       # §3: method_check.py runs the from-scratch implementation; families.py is what train.py realizes
---

# Method card — Fisher's linear discriminant (1936)

> Gate 2 (METHOD). Protocol:
> `.claude/skills/klein/references/method-gate-protocol.md`. The five parts are an
> authoring ARC — written in order.
>
> **DRAFT — pending user acknowledgement.** Every number in §3 and §5 was produced by
> a real run of `method_check.py` on 2026-08-24 against the committed artifact. The two
> references are **citation-verification-pending** and are re-verified Tuesday morning;
> `refs_verified` and `triad.papers` stay `false` until then, so the gate record must
> name the **papers** leg in its `--note` (exact command in the study's Tuesday runbook).

The unfamiliar method here is not a 2023 architecture — it is a 1936 one. That is the
point: the study's anchor is the incumbent every challenger has to beat, so the study
has to be able to *build it from scratch*, not import it and hope.

## 1. Intuition (for a practitioner)

You have two clouds of flowers in four-dimensional measurement space and you want one
number per flower that separates them. Project every flower onto a single direction — a
weighted sum of the four measurements — and the four-dimensional problem collapses to a
one-dimensional one.

Which direction? Not the one that pushes the two group means furthest apart. A direction
can spread the means widely and still overlap badly, if the clouds are *also* stretched
along it. Fisher's criterion is a **signal-to-noise ratio**: maximize the squared gap
between the projected means **divided by** the within-group spread along that same
direction.

An actuary already knows this shape. It is the same instinct as a lift chart: a rating
factor is not good because high and low cells differ, but because they differ **relative
to the noise inside each cell**. Fisher's discriminant is that instinct solved exactly,
in closed form, in 1936 — no optimizer, no learning rate, no seed.

The consequence that matters for this study: **there is nothing random in it.** Refit
it a thousand times with a thousand seeds and you get the same numbers to the last bit.
That is why the protocol-prescribed k-seed noise floor is registered as degenerate here
and why the study measures a *split* floor instead.

## 2. Math core

| Symbol | Meaning |
|---|---|
| $x \in \mathbb{R}^4$ | one flower's four measurements (sepal length/width, petal length/width, cm) |
| $\mu_0, \mu_1$ | class mean vectors (versicolor, virginica) |
| $n_0, n_1$ | class counts (50 and 50 in the hard pair; 27 and 33 in this study's train partition) |
| $S_W$ | pooled **within-class scatter** matrix, $4\times4$ |
| $S_B$ | between-class scatter, rank 1 |
| $w$ | the discriminant direction — the vector of weights we solve for |
| $J(w)$ | Fisher's criterion (the ratio being maximized) |

Within-class scatter — sums of squares and cross-products about each class mean:

$$ S_W \;=\; \sum_{k\in\{0,1\}} \sum_{x \in C_k} (x-\mu_k)(x-\mu_k)^{\top} $$

Between-class scatter, for two classes, is rank one along the mean difference:

$$ S_B \;=\; (\mu_1-\mu_0)(\mu_1-\mu_0)^{\top} $$

Fisher's criterion — separation per unit of within-class spread:

$$ J(w) \;=\; \frac{w^{\top} S_B\, w}{w^{\top} S_W\, w} \;=\; \frac{\big(w^{\top}(\mu_1-\mu_0)\big)^2}{w^{\top} S_W\, w} $$

Maximizing $J$ is the generalized eigenproblem $S_B w = \lambda S_W w$; because $S_B$ has
rank 1 it collapses to a single linear solve:

$$ w^{\star} \;\propto\; S_W^{-1}(\mu_1-\mu_0) $$

Only the **direction** is determined — $J(cw) = J(w)$ for any $c \neq 0$. The scale is a
reporting convention, which is exactly why §5's comparison with Fisher's *printed*
coefficients has to be done as a **cosine**, not as a difference of numbers.

Three consequences this study leans on:

1. **Closed form.** One mean per class, one scatter matrix, one solve. No iteration.
2. **Scale invariance of the scatter.** Replacing $S_W$ by $cS_W$ for any $c>0$ leaves
   $w^\star$ unchanged — measured, §3.
3. **Within vs total scatter is not a choice.** $S_T = S_W + S_B$, and $S_B$ is rank 1
   along $\mu_1-\mu_0$, so by Sherman–Morrison $S_T^{-1}(\mu_1-\mu_0)$ is a **positive
   multiple** of $S_W^{-1}(\mu_1-\mu_0)$: the same direction, exactly — measured, §3.

To score `val_brier` the projection is turned into a probability. sklearn's
`LinearDiscriminantAnalysis` does this with the Gaussian-equal-covariance posterior,
which is the logistic of an affine function of $x$; `kleinlib.eval.evaluate` reads
`predict_proba` and computes the Brier score from $P(\text{virginica})$.

## 3. Minimal from-scratch implementation — and its verification

Ten lines of numpy. This is the whole method:

```python
def fisher_direction(X, y):
    X0, X1 = X[y == 0], X[y == 1]
    mu0, mu1 = X0.mean(axis=0), X1.mean(axis=0)
    S_W = (X0 - mu0).T @ (X0 - mu0) + (X1 - mu1).T @ (X1 - mu1)
    w = np.linalg.solve(S_W, mu1 - mu0)
    return w / np.linalg.norm(w)
```

It lives in `method_check.py`, a **quarantined** gate artifact: it is fitted on **all 100
rows** precisely so it can never become evidence on the study's frontier, and it scores
nothing and writes nothing. What `train.py` actually runs is `families.py`'s registered
`anchor_lda4` — sklearn's `LinearDiscriminantAnalysis(solver="svd")` — fitted on the
train partition only. This card's job is to prove those two are the same object.

`kleinlib` helpers the ladder leans on: `kleinlib.data.three_way_split` (the declared
group split), `kleinlib.eval.evaluate` (the canonical metric block, `val_brier` primary
with `val_auc`/`val_logloss` as auxiliaries).

### Verification — run 2026-08-24, `uv run --locked python method_check.py`, exit 0

**Check 1 — direction identity.** Pre-registered pass bar, fixed before the run:
**cosine ≥ 1 − 1e-12**.

| sklearn solver | cosine(from-scratch, sklearn) | 1 − cosine | Verdict |
|---|---|---|---|
| `svd` | 1.000000000000000 | 1.110e-16 | **PASS** |
| `eigen` | 1.000000000000000 | 0.000e+00 | **PASS** |
| `lsqr` | 1.000000000000000 | 0.000e+00 | **PASS** |

From-scratch unit direction: `[-0.226849961, -0.355849876, 0.444611533, 0.790082620]`.
The residual for `svd` is one unit in the last place of a float64 — the two
computations are the same computation. Three different solvers agree because there is
only one answer to agree on: the method is closed form.

**Check 2 — group means, 3 decimal places** (all 100 hard-pair rows):

| Species | sepal length | sepal width | petal length | petal width |
|---|---|---|---|---|
| versicolor | 5.936 | 2.770 | 4.260 | 1.326 |
| virginica | 6.588 | 2.974 | 5.552 | 2.026 |

These reproduce the per-species means to 3 dp. **Scope note, stated honestly:** this
verifies our arithmetic against the *measurements as distributed by scikit-learn*.
Comparison against the means **printed in Fisher (1936)** is
citation-verification-pending together with §5's references, and no claim about the
printed table is made until that verification is done.

## 4. When it pays / when it doesn't

| Regime | Data size | Signal | Verdict |
|---|---|---|---|
| Two classes, roughly Gaussian, similar covariance, few features | tiny (n ≈ 100) | strong, near-linear | **pays** — closed form, no variance from fitting, nothing to tune, nothing to overfit |
| Two classes, similar covariance | large | weak | pays, but logistic regression is usually preferred: it models the posterior directly and does not assume Gaussian class densities |
| Strongly unequal class covariances | any | any | **doesn't** — the pooled-covariance assumption is the whole model; QDA or a kernel method is the honest choice |
| Genuinely non-linear boundary | large | strong | **doesn't** — one projection cannot bend |
| Many correlated features, n < p | small | any | **doesn't** without regularization — $S_W$ is singular or near-singular |

For **this** study the first row is the regime, and that is the uncomfortable part: at
n = 100 with a strong near-linear boundary, a method with **no fitting variance** is
extremely hard to beat, not because it is clever but because everything else has more
ways to be wrong. That is a hypothesis the ladder tests, not a conclusion.

**Falsifiable priors this card commits to** (mirrored in
`study.yaml:predictions_to_falsify`):

1. The from-scratch direction matches sklearn's to **cosine ≥ 1 − 1e-12** on all three
   solvers. — **HELD**, measured above.
2. The k-seed fit-noise floor is **exactly 0.0**, because the estimator is closed form.
   — to be measured at Phase 0 by `sweeps/kseed_floor.py`.
3. No pre-registered challenger improves `val_brier` by ≥ the measured floor.
4. Dropping both sepal measurements degrades `val_brier` by **less** than the floor.
5. Dropping both petal measurements degrades it by **at least 2×** the floor.

## 5. Fisher's printed coefficients — RESOLVED 2026-08-25: we were comparing the wrong pair

Reproduction has layers, and they do not all have the same answer. Recorded plainly:

| Layer | Status |
|---|---|
| The **method** — from-scratch vs sklearn direction | **matches**, cosine ≥ 1 − 1e-12 on all three solvers (§3) |
| The **group means** to 3 dp | **matches** the distributed measurements (§3); the full 150×4 printed Table I diffed vs sklearn 2026-08-25: **zero mismatches** (one OCR artifact in the scan identified as such) |
| Fisher's **printed discriminant coefficients** | **RESOLVED — matches digit-exact once compared to the RIGHT problem** (see resolution below) |

The third row is a **discrepancy we record, not a match we claim**. Its two cosines come
from the 2026-08-24 scouting (`scouting_ledger.md` S8) and are **design inputs**: they
are re-derived on Tuesday against a verified transcription of Fisher (1936) before any
of them appears in a deliverable. Nothing downstream may cite them until then.

### Convention investigation performed tonight (bounded, logged, not resolved)

What could a "convention difference" even be? Three candidates were tested numerically
on our own data (`method_check.py` check 3), and the first two are **eliminated**:

| Candidate explanation | Measured effect on the direction | Verdict |
|---|---|---|
| TOTAL scatter about the grand mean instead of pooled within-class scatter | cosine **1.000000000000000** | **Eliminated.** Not luck: $S_T = S_W + S_B$ with $S_B$ rank 1 along $\mu_1-\mu_0$, so Sherman–Morrison makes $S_T^{-1}(\mu_1-\mu_0)$ a positive multiple of $S_W^{-1}(\mu_1-\mu_0)$. |
| Covariance vs sum-of-squares; `ddof` 0 vs 1 | cosine **1.000000000000000** | **Eliminated.** Any positive rescaling of $S_W$ leaves $w^\star$ untouched. |
| 1936 desk-calculation rounding of the intermediate scatter matrix | 2 s.f. → 1 − cos **2.3e-04**; 3 s.f. → **3.4e-07**; 4 s.f. → **1.0e-08**; 5 s.f. → **6.1e-10** | **Insufficient in magnitude.** Even rounding to *two* significant figures moves the direction ~80× less than the smaller recorded gap (1 − cos 0.019) and ~190× less than the larger (0.044). |

**What this bounds.** The recorded gap is **not** explained by which scatter matrix is
inverted, **not** by how it is scaled, and **not** by hand-arithmetic rounding at any
plausible precision. Whatever produces Fisher's printed numbers is therefore something
else — a different reported quantity, a different scaling of the compound, or a
different subset/units of the measurements.

**RESOLUTION (2026-08-25, citations verification against the full 1936 text).** The
convention investigation's conclusion — "a different reported quantity" — was right, and
the different quantity is now identified: **Fisher prints no versicolor-vs-virginica
discriminant at all.** His worked §II discriminant is **I. setosa vs I. versicolor**:
"X = x1 + 5.9037 x2 − 7.1299 x3 − 10.1036 x4" (p. 182). The scouted 0.981/0.956 compared
our versicolor/virginica direction against THAT vector — a wrong-pair comparison, exactly
reproduced by the verifier (0.9811 with 2-species pooled Sw, 0.9561 with 3-species
pooled Sw; the 0.981-vs-0.956 spread is an Sw-convention artifact of the wrong-pair
comparison, not a finding). The only other printed vector is §VI's three-species
4:1:−5 allopolyploidy contrast (−3.308998, −2.759132, 8.866048, 9.392551, ×100), also
not our pair.

**The verified reproduction claim (replaces the discrepancy):** the from-scratch
discriminant, run on Fisher's own §II problem (setosa vs versicolor, sklearn data =
Fisher's printed table byte-for-byte), returns **(1, 5.90380, −7.12998, −10.10366)** —
Fisher's printed compound **to every printed digit**, cosine 1.000000.

**Bonus primary-source fact for the study's framing** (§VI, verbatim): "there is some
overlap of the distributions of I. virginica and I. versicolor, so that a certain
diagnosis of these two species could not be based solely on these four measurements of
a single flower taken on a plant growing wild." — **Fisher himself flagged our hard pair
as unresolvable by these four measurements, in print, in 1936.** The 90-year ladder asks
a question Fisher explicitly declined to answer.

复现有层次，如今每一层都对上了：方法对上了(≥1−1e-12)，均值表对上了，1936 年印出来的判别式
——放回它自己的问题里——每一位数字都对上了。之前记录的"差 2%"，是我们拿错了考卷。

## 6. References — VERIFIED 2026-08-25 (citations agent, primary sources)

Both rows are **⚠️ UNVERIFIED** tonight and are re-verified Tuesday morning against
publisher/index records before the METHOD gate is recorded or `refs_verified` is set.

| Reference | Where | Verified? |
|---|---|---|
| Fisher, R. A. (1936). "The use of multiple measurements in taxonomic problems." | *Annals of Eugenics* 7(2), 179–188; reprinted in *Contributions to Mathematical Statistics* (Wiley, 1950). Cited by scikit-learn's `load_iris` `DESCR` as the source of its copy. | **VERIFIED 2026-08-25**: Annals of Eugenics 7(2):179–188, DOI 10.1111/j.1469-1809.1936.tb02137.x; open access via Rothamsted (repository.rothamsted.ac.uk/id/eprint/33079). Printed §II compound X = x1 + 5.9037x2 − 7.1299x3 − 10.1036x4 (setosa vs versicolor); §VI 4:1:−5 contrast. Anderson credited in §II |
| Bezdek, J. C., Keller, J. M., Krishnapuram, R., Kuncheva, L. I., Pal, N. R. (1999). "Will the real iris data please stand up?" | *IEEE Transactions on Fuzzy Systems* 7(3), 368–369. | ⚠️ **UNVERIFIED — citation-verification-pending-Tuesday** (venue, volume/issue, pages; and whether it says anything about rows 102/143 — the twin-row provenance question left undecidable on the data card) |

Corroborating primary sources already retrieved and committed under `reference/`
(hashes and retrieval times in `reference/PROVENANCE.md`) — these are **verified
artifacts**, not literature citations:

- UCI `iris.names`, which carries the rows-35/38 errata verbatim and credits Steve
  Chadwick, added by C. Blake.
- UCI `iris.data`, the file the errata describe.
- scikit-learn 1.9.0 `load_iris().DESCR`, which states its copy follows Fisher's paper
  rather than UCI.
