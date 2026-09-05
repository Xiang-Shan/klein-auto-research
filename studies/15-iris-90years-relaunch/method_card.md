---
type: method-card
domain: "botany"
profile: "generic"
status: complete
concepts:
  - linear-discriminant-analysis
  - fisher-criterion
  - pooled-covariance
  - plug-in-bayes-rule
  - logistic-regression
  - k-nearest-neighbours
  - rbf-kernel-svm
  - histogram-gradient-boosting
  - roc-auc-resolution
  - paired-bootstrap-floor
  - headroom-law
related:
  - study.yaml
  - research_plan.md
  - data_card.md
  - references.yaml
  - method_check_lda.py
refs_verified: true
triad:
  theory: true       # §2 carries the notation table and five display equations
  papers: true       # every row of §5 verified against a publisher/archive page; refs_verified is true
  practice: true     # §3's from-scratch numpy LDA was RUN at this gate and agrees with sklearn to 7.1e-15
---

# Method card — Fisher's linear discriminant, and the four post-1936 challengers measured against it

> Gate 2 (METHOD). Pedagogy for the method this study is about, written BEFORE any
> modeling. Protocol: `.claude/skills/klein/references/method-gate-protocol.md`.
> The five parts are an authoring ARC — written in order, each resting on the one before.

**Scholar identity & clean-room disclosure.** Written by a Claude Code
`klein-method-scholar` subagent (Opus 5), in this study's own worktree on
`experiments/15-iris-90years-relaunch`. Per this study's independence design
(`scouting_ledger.md`), **no file under `studies/07-iris-90years/`,
`studies/08-iris-rematch/` or `studies/09-iris-first-lesson/` was opened at any point
while this card was written** — not their method cards, not their `references.yaml`,
not their findings. Files read inside the study: `study.yaml`, `research_plan.md`,
`program.md`, `data_card.md`, `scouting_ledger.md`, `prepare.py`, `train.py` (the
scaffold stub). Files read outside it: the method-gate protocol, the generic profile,
the card template, `kleinlib/{eval,data,metrology,references,state,contract}.py`, and
two non-iris exhibits (`10-hubble-1929-replication`, `12-insurance-claims-frequency`)
for card and `references.yaml` shape only. R. A. Fisher's 1936 paper was read in the
original, from the *Annals of Human Genetics* archive scan, and is transcribed in §5.

**One thing this card does NOT do.** It does not score the development block and it
does not touch the sealed block. The only number it measures is an *implementation
agreement* — §3's from-scratch LDA against scikit-learn's — computed on the 49
**training** rows alone. Every performance number in this card is either transcribed
from 1936 literature or derived from it in closed form. No evidence is spent here.

---

## 1. Intuition (for a practitioner)

You are a scientist. You have 99 iris flowers of two species, *versicolor* and
*virginica*, and four numbers per flower: sepal length, sepal width, petal length,
petal width. The two species overlap. You want to know whether the four numbers can
tell them apart, and whether ninety years of classification research has found a
better way to ask than Fisher's.

### The shadow-casting angle

Picture the 99 flowers as 99 points floating in a four-dimensional room, one axis per
measurement, coloured by species. The two colours form two overlapping clouds.

Now imagine shining a light through the room and reading the **shadow** the points
cast on a wall — a one-dimensional line. Every direction you could shine from gives a
different shadow, and most of them are useless: the two colours smear into each other.
But some direction gives the cleanest separation, and **that direction is the whole of
linear discriminant analysis**. Once you have it, classification is trivial: project
the flower onto that one line, and see which side of a threshold it lands on.

Which direction is "cleanest"? Not simply the one where the two cloud *centres* land
furthest apart — a direction can spread the centres and also spread each cloud, and
you gain nothing. What you want is the direction where the gap between the centres is
largest **relative to how fat the clouds are along that same direction**. That ratio —
spread *between* species over spread *within* species — is **Fisher's criterion**, and
1936's contribution was that the direction maximizing it has a closed form. No search,
no iteration, no learning rate: one matrix inverse and you are done.

Three analogies, pick whichever lands:

- **LDA is a t-test in four dimensions.** A two-sample t-statistic is
  (difference of means) ÷ (pooled standard deviation). LDA finds the one linear
  combination of your four measurements whose t-statistic is as large as it can
  possibly be, and then reports that combination.
- **LDA is PCA that has been told the labels.** PCA finds the direction of largest
  total spread and does not know or care which points are which species. LDA finds the
  direction of largest *between-species* spread per unit of *within-species* spread.
  Same shape of computation — an eigenproblem — different objective.
- **LDA is "whiten, then point at the difference".** Rescale the room so that the
  within-species scatter becomes a perfect sphere (that is what multiplying by the
  inverse covariance does). In that reshaped room, all directions are equally noisy, so
  the best direction is simply the straight line joining the two cloud centres. Undo
  the reshaping and you get Fisher's answer: `direction = Σ⁻¹ × (mean₁ − mean₀)`.

### Why it is not just *a* method but *the* method — under one assumption

Suppose each species really is a Gaussian blob, and — this is the load-bearing part —
suppose the two blobs have the **same shape and orientation**, differing only in where
they sit. Then the mathematically best possible classifier, the one no procedure of any
kind can beat, is a flat boundary, and its direction is exactly the one Fisher's
criterion produces (Welch 1939). LDA is not an approximation in that world; it *is*
the optimal rule with the population means and covariance replaced by sample estimates.

That matters enormously here, because iris versicolor and virginica are close to that
world: four smooth, roughly bell-shaped physical measurements in centimetres, two
species whose scatter matrices are similar. If the assumption holds even approximately,
then a more flexible method has nothing left to find — it can only add variance.

### The four challengers, in one sentence each

| Recipe | Published | One-sentence intuition |
|---|---|---|
| `logreg_l2` | Berkson 1944 / Cox 1958 | The same flat boundary, chosen by a different question: instead of "which direction separates the clouds", it asks "which boundary makes the labels I actually observed most likely" — and the L2 penalty shrinks the coefficients toward zero to stop it chasing a perfect fit. |
| `knn5` | Fix & Hodges 1951 / Cover & Hart 1967 | No model at all: to classify a flower, find its five nearest neighbours among the training flowers and take a vote. Infinitely flexible in principle; with 49 training flowers, a very coarse instrument. |
| `svm_rbf` | Boser–Guyon–Vapnik 1992 / Cortes & Vapnik 1995 | Lay the widest possible "road" between the two classes and put the boundary down its centre line — but first bend space with a Gaussian kernel so the road is allowed to curve. |
| `hgbt` | Friedman 2001 / Ke et al. 2017 | A committee of hundreds of short axis-aligned staircases, each new one fitted to what the committee so far still gets wrong. It draws boundaries out of horizontal and vertical steps. |

Two of these (`logreg_l2`, `svm_rbf` with a small enough kernel width) can reproduce
something close to Fisher's straight boundary. Two of them (`knn5`, `hgbt`) cannot draw
a smooth oblique line at all: kNN draws a jagged polygon and boosting draws a
staircase. If the true boundary really is an oblique plane, that is a handicap, not a
feature — an axis-aligned staircase approximating a diagonal line is the classic
picture of a method paying variance for flexibility it cannot use.

### The part that decides this study: the ruler, not the models

Here is the uncomfortable arithmetic, and it is the reason this card spends as much
space on measurement as on models.

The metric is ROC-AUC: the probability that a randomly chosen virginica scores above
a randomly chosen versicolor (Hanley & McNeil 1982). The development block holds
13 versicolor and 12 virginica (`data_card.md`), so the AUC is a count over
13 × 12 = 156 ordered pairs and can only take values that are multiples of
1/156 = 0.0064. That is the *finest* the instrument can move.

But resolution is not the same as noise. If you resample those 25 flowers, or redraw
which 25 they are, the AUC wanders — and that wandering is the real floor. If the
wandering is, say, ±0.03 AUC, then a challenger that scores 0.02 higher than Fisher
has not beaten him; it has landed inside the width of the ruler's own tick mark. And
if Fisher's own score is already 0.97, then the *entire remaining distance to a perfect
1.0* is 0.03 — the same size as the tick. When the distance left to travel is smaller
than one tick, **no improvement is measurable, in either direction, by construction**.
That is Klein's headroom law, and this study has armed it deliberately
(`tracks.modern.metric.bound.ideal: 1.0`, prediction P4).

So the honest framing of this card is: five classifiers will be run, and the most
likely finding is not "X beat Y" but "at n = 99 the question 'which classifier wins'
does not have a resolvable answer, and here is the measured width of the ruler that
proves it". That is a real result, and it is one Fisher himself would have recognized —
in 1936 he wrote of this very species pair that "a certain diagnosis of these two
species could not be based solely on these four measurements of a single flower taken
on a plant growing wild" (§5, transcribed).

---

## 2. Math core

### Notation

| Symbol | Meaning |
|---|---|
| $n$ | number of fitting rows (here $n = 49$ on the training partition) |
| $p$ | number of measurements per flower ($p = 4$) |
| $K$ | number of classes ($K = 2$: versicolor = 0, virginica = 1) |
| $\mathbf{x}_i \in \mathbb{R}^p$ | the four measurements of flower $i$, in centimetres |
| $y_i \in \{0,1\}$ | species label of flower $i$ (`is_virginica`) |
| $n_c$ | number of fitting rows in class $c$ |
| $\boldsymbol{\mu}_c \in \mathbb{R}^p$ | sample mean vector of class $c$ |
| $\mathbf{d} = \boldsymbol{\mu}_1 - \boldsymbol{\mu}_0$ | the mean difference vector |
| $\mathbf{S}_W$ | within-class scatter matrix ($p \times p$), summed over classes |
| $\mathbf{S}_B$ | between-class scatter matrix ($p \times p$) |
| $\hat{\boldsymbol{\Sigma}} = \mathbf{S}_W / (n-K)$ | pooled covariance estimate (the unbiased one; $n-K = 47$ here) |
| $\mathbf{w} \in \mathbb{R}^p$ | the discriminant direction — the "shadow-casting angle" of §1 |
| $b \in \mathbb{R}$ | the intercept that turns the direction into a decision rule |
| $\pi_c = n_c/n$ | empirical prior of class $c$ |
| $J(\mathbf{w})$ | Fisher's criterion, the between/within scatter ratio |
| $\Delta$ | Mahalanobis separation $\sqrt{\mathbf{d}^\top \boldsymbol{\Sigma}^{-1}\mathbf{d}}$ |
| $\Phi$ | standard normal cumulative distribution function |
| $A$ | ROC-AUC, $P(\text{score of a random class-1 row} > \text{score of a random class-0 row})$ |

### E1 — the two scatter matrices

$$
\mathbf{S}_W \;=\; \sum_{c\in\{0,1\}} \; \sum_{i:\,y_i=c} (\mathbf{x}_i-\boldsymbol{\mu}_c)(\mathbf{x}_i-\boldsymbol{\mu}_c)^\top ,
\qquad
\mathbf{S}_B \;=\; (\boldsymbol{\mu}_1-\boldsymbol{\mu}_0)(\boldsymbol{\mu}_1-\boldsymbol{\mu}_0)^\top \;=\; \mathbf{d}\,\mathbf{d}^\top .
$$

$\mathbf{S}_W$ is how fat the clouds are, pooled across species; $\mathbf{S}_B$ is how
far apart their centres are. With two classes $\mathbf{S}_B$ has rank 1 — it is an
outer product — and that single fact is what makes the next two equations collapse to a
closed form.

### E2 — Fisher's criterion

$$
J(\mathbf{w}) \;=\; \frac{\mathbf{w}^\top \mathbf{S}_B \mathbf{w}}{\mathbf{w}^\top \mathbf{S}_W \mathbf{w}}
\;=\; \frac{\left(\mathbf{w}^\top \mathbf{d}\right)^2}{\mathbf{w}^\top \mathbf{S}_W \mathbf{w}} .
$$

The squared gap between the projected class means, divided by the pooled variance of
the projections. Note $J(\alpha\mathbf{w}) = J(\mathbf{w})$ for any $\alpha \neq 0$:
the criterion fixes a **direction**, never a scale. Any implementation is free to
return $\mathbf{w}$ scaled however it likes, so two implementations must be compared by
*angle* (or by identical ranking), not by raw coefficient magnitude.

### E3 — the closed-form solution

Setting $\nabla_{\mathbf{w}} J = 0$ gives the generalized eigenproblem
$\mathbf{S}_B \mathbf{w} = \lambda\, \mathbf{S}_W \mathbf{w}$. Because
$\mathbf{S}_B \mathbf{w} = \mathbf{d}\,(\mathbf{d}^\top \mathbf{w})$ is always a scalar
multiple of $\mathbf{d}$, the eigenproblem degenerates and the maximizer is available
in one line:

$$
\boxed{\;\mathbf{w} \;\propto\; \mathbf{S}_W^{-1}\,\mathbf{d} \;=\; \hat{\boldsymbol{\Sigma}}^{-1}\,(\boldsymbol{\mu}_1-\boldsymbol{\mu}_0)\;}
$$

This is the entire fitting procedure. **No iteration, no tuning, no random seed** —
which is why `lda_all4` has no `random_state` in the recipe table and why its
`fit_noise` is exactly zero by construction.

### E4 — why it is optimal under equal-covariance Gaussians, and the intercept

Assume $\mathbf{x}\mid y=c \;\sim\; \mathcal{N}(\boldsymbol{\mu}_c, \boldsymbol{\Sigma})$
with **the same** $\boldsymbol{\Sigma}$ for both classes. Then the log posterior odds is

$$
\log\frac{P(y=1\mid \mathbf{x})}{P(y=0\mid \mathbf{x})}
= \underbrace{\left[\boldsymbol{\Sigma}^{-1}(\boldsymbol{\mu}_1-\boldsymbol{\mu}_0)\right]^\top}_{\mathbf{w}^\top}\mathbf{x}
\;\underbrace{-\;\tfrac12\!\left(\boldsymbol{\mu}_1^\top\boldsymbol{\Sigma}^{-1}\boldsymbol{\mu}_1-\boldsymbol{\mu}_0^\top\boldsymbol{\Sigma}^{-1}\boldsymbol{\mu}_0\right)+\log\frac{\pi_1}{\pi_0}}_{b} .
$$

The quadratic terms in $\mathbf{x}$ cancel *because the two covariances are equal* —
that cancellation is the whole reason the boundary is flat. The Bayes-optimal rule is
therefore "predict class 1 when $\mathbf{w}^\top\mathbf{x} + b > 0$", with exactly the
$\mathbf{w}$ of E3. LDA is the **plug-in Bayes rule**: substitute
$\boldsymbol{\mu}_c \to$ sample means and $\boldsymbol{\Sigma} \to \hat{\boldsymbol{\Sigma}}$.
Welch (1939) is the compact statement of this. Two consequences an implementer must
internalize:

1. **Nothing can beat it in that world** except by estimating $\boldsymbol{\mu}$ and
   $\boldsymbol{\Sigma}$ better — which, at $n = 49$ and $p = 4$, is where the only
   remaining headroom lives.
2. **Equal covariance is the assumption that can break.** If the two species' scatter
   matrices genuinely differ, the quadratic terms survive, the true boundary is a
   conic, and a flexible learner has something real to find. Whether they differ enough
   to matter on these flowers is, in effect, what the `modern` track measures.

### E5 — separation, ROC-AUC, and the resolution of the ruler

Under the same model, the score $s = \mathbf{w}^\top\mathbf{x}$ is Gaussian within each
class with a common variance, so the AUC is available in closed form:

$$
A \;=\; P(s_1 > s_0) \;=\; \Phi\!\left(\frac{\Delta}{\sqrt{2}}\right),
\qquad
\Delta \;=\; \sqrt{\mathbf{d}^\top\boldsymbol{\Sigma}^{-1}\mathbf{d}}
\;=\;\frac{\text{gap between class means on the score}}{\text{within-class standard deviation of the score}} .
$$

and the misclassification rate at the midpoint threshold is $\Phi(-\Delta/2)$ — which
is precisely the calculation Fisher performs in his §III for the *easy* pair.

The empirical AUC on a held-out block of $n_1$ positives and $n_0$ negatives is the
Mann–Whitney statistic: the fraction of the $n_1 n_0$ cross-pairs that are correctly
ordered. On this study's development block, $n_1 n_0 = 12 \times 13 = 156$, so

$$
\hat{A} \in \left\{0,\ \tfrac{1}{156},\ \tfrac{2}{156},\ \dots,\ 1\right\},
\qquad \text{step} = 0.0064 .
$$

Two numbers to keep apart, because conflating them is how a study talks itself into a
result: **0.0064 is the resolution** (the smallest non-zero difference the statistic can
express) and the **noise floor is something else entirely** — the spread of the *paired
difference* between two candidates under resampling of those same 25 rows, which
`study.yaml` declares will be measured at Phase 0 by a 1000-replicate paired bootstrap
under common random numbers (Efron 1979 for the resampling argument). The floor will be
several times the resolution. Only the floor is a bar.

---

## 3. Minimal from-scratch implementation plan

### 3.1 LDA in fourteen lines of numpy — and what it actually measured

This is the whole method. No sklearn, no framework, no magic.

```python
import numpy as np

classes = np.unique(y)                                   # [0, 1]
n, p = X.shape
K = classes.size

mus    = np.stack([X[y == c].mean(axis=0) for c in classes])   # (K, p) class means
priors = np.array([(y == c).mean() for c in classes])          # (K,)  empirical priors

S_W = np.zeros((p, p))                                   # E1: within-class scatter
for k, c in enumerate(classes):
    Z = X[y == c] - mus[k]
    S_W += Z.T @ Z
Sigma = S_W / (n - K)                                    # pooled covariance, unbiased

d = mus[1] - mus[0]                                      # E1: S_B = np.outer(d, d)
w = np.linalg.solve(Sigma, d)                            # E3: Sigma^-1 (mu1 - mu0)
b = -0.5 * (mus[1] @ np.linalg.solve(Sigma, mus[1])      # E4: the intercept
            - mus[0] @ np.linalg.solve(Sigma, mus[0])) + np.log(priors[1] / priors[0])

score = X @ w + b                                        # > 0  ->  predict virginica
```

Two implementation notes that are easy to get wrong and cost you the agreement below:

- Use `np.linalg.solve`, never `np.linalg.inv(Sigma) @ d`. Same answer in exact
  arithmetic; the explicit inverse is less accurate and, on a nearly singular pooled
  covariance, visibly so.
- The `log(π₁/π₀)` term is part of the intercept, not an afterthought. scikit-learn
  includes it (`priors=None` means empirical priors). Omit it and your **direction**
  still matches to machine precision, while your **decision threshold** — and therefore
  every accuracy and error count, though not the AUC — quietly differs. On this study's
  49-row training partition the two classes are 25/24, so the term is
  `log(24/25) = -0.0408`: small enough to hide, large enough to move a borderline flower.

**Measured at this gate** (`method_check_lda.py`, run under `uv run --locked python`,
scikit-learn 1.9.0, numpy 2.5.1, on the 49 **training** rows of
`data/prepared/iris_hardpair.csv` obtained through `kleinlib.data.contract_split` —
the development block was not scored and the sealed block was not read):

| Quantity | Value |
|---|---|
| from-scratch $\mathbf{w}$ | `[-5.2977423747, -2.9287767653, 8.4884382625, 10.4695397572]` |
| sklearn `LinearDiscriminantAnalysis(solver="svd").coef_[0]` | `[-5.2977423747, -2.9287767653, 8.4884382625, 10.4695397572]` |
| **cosine similarity of the two directions** | **1.000000000000000** (`1 − cos = −2.22e−16`, i.e. below one double-precision ulp) |
| max absolute coefficient difference | **7.105e−15** |
| max relative coefficient difference | 2.426e−15 |
| intercept, from scratch vs sklearn | `−17.616930179737` vs `−17.616930179737`, difference **1.776e−14** |
| max absolute difference of decision scores over the 49 training rows | **1.776e−14** |
| predicted labels identical on all 49 training rows | yes |
| Fisher criterion $J(\mathbf{w})$, E2, both vectors | `0.318850456779` (and unchanged under $\mathbf{w}\to 3.7\mathbf{w}$, confirming the scale-invariance E2 predicts) |
| `np.allclose(w, w_sklearn, rtol=1e-10, atol=1e-12)` | `True` |

The two implementations are the same computation. That is the point of writing it out:
`solver="svd"` reaches the answer by a numerically better route (it standardizes and
takes an SVD rather than forming and inverting $\hat{\boldsymbol{\Sigma}}$), but the
answer it reaches is E3 and nothing else. **Nobody in this study has to take
scikit-learn's word for what Fisher's method is.** This is the card's Practice leg.

A bonus number, free from the same fit and reported because it is the only place in
this study where 1936 and 2026 touch: Fisher's own published §VI compound direction
(coefficients ×100: `[-3.308998, -2.759132, 8.866048, 9.392551]`, transcribed in §5)
and the direction fitted above on this study's 49 training flowers have a **cosine
similarity of 0.990203 — 8.03° apart**. They are not the same function (Fisher's was
built for a three-species allopolyploidy test on all 150 flowers under a 16 : 1 : 25
weighting of the species scatter matrices, not for a two-class discriminant on the hard
pair), and yet they point almost the same way, both dominated by the two petal
measurements with small negative sepal coefficients. That is a hint about RQ2 from
literature rather than from this study's data, and it is descriptive only.

### 3.2 What `train.py` composes, cell by cell

`research_plan.md` fixes the architecture: `lib/iris.py` is stable library code
(loader, three feature sets, five recipe factories, the paired bootstrap, the `extra`
assembly) and `train.py` — the only mutable surface — composes those primitives into
**one cell per experiment**. The per-experiment diff is always "which recipe / which
feature set / which reference", never "a new method". Skeleton of a paired cell:

```python
# ---- partition: never chosen by experiment code -------------------------
X_fit, X_eval, y_fit, y_eval = kleinlib.data.load_partition()   # reads KLEIN_EVALUATION_KIND,
                                                                # prints split_fingerprint:

# ---- the reference rung and the candidate, on the SAME rows -------------
reference = build("lda_all4").fit(X_fit[COLS["all4"]], y_fit)   # refit inside the cell
candidate = build(RECIPE).fit(X_fit[COLS[FEATURES]], y_fit)

p_ref  = reference.predict_proba(X_eval[COLS["all4"]])[:, 1]
p_cand = candidate.predict_proba(X_eval[COLS[FEATURES]])[:, 1]

ref_auc   = roc_auc_score(y_eval, p_ref)
delta     = roc_auc_score(y_eval, p_cand) - ref_auc
floor     = contract_minimum_delta("modern")                    # measured at Phase 0

kleinlib.eval.evaluate(
    candidate, X_eval[COLS[FEATURES]], y_eval,
    exp_id=EXPERIMENT_ID, study_dir=".", t0=t0, fit_seconds=fit_seconds,
    train_n=len(X_fit), val_n=len(X_eval),
    metric_name="val_auc", metric_goal="higher",
    extra={
        "reference_metric":    round(ref_auc, 6),
        "delta_vs_reference":  round(delta, 6),
        "delta_in_floors":     round(delta / floor, 4),
        "gap_in_floors":       round((1.0 - ref_auc) / floor, 4),
        "val_accuracy":        round(accuracy, 6),
        "val_errors":          int(errors),
    },
)
```

Three contract-level facts this skeleton encodes, each of which is a rule of this study
and not a stylistic choice:

1. **The reference is refitted inside the same cell, on the same fit rows, and scored
   on the same eval rows.** That is what makes every comparison paired by construction
   and what makes `delta_in_floors` comparable to a paired-bootstrap floor. An
   unpaired comparison — candidate today against a number written down last week —
   measures a different, larger-variance estimand and would need a different (larger)
   bar.
2. **`load_partition()` and nothing else** decides which rows are which. It reads
   `KLEIN_EVALUATION_KIND`, which `klein run-one` sets; it prints
   `split_fingerprint:`, which the notary compares against the value frozen at the DATA
   gate (`development=41553e71…`, `final_test=49a84dcd…`); and under
   `KLEIN_SEALED_DRYRUN=1` it answers a `final_test` request with the development rows
   plus a `sealed_dryrun: 1` acknowledgement, so `--final-test --dry-run` exercises the
   whole path and spends nothing. A literal split seed anywhere in `train.py` is a
   BLOCKER (war story 8).
3. **Everything that is not `val_auc` travels in `extra={...}`.** `wall_seconds`,
   `train_rows`, `val_rows` and `split_fingerprint` print without being asked; every
   other key `study.yaml`'s prediction rules name — `raw_rows`, `partition_sum_matches`,
   `ci_width`, `n_boot`, `gap_in_floors`, `delta_in_floors`, `sepal_delta_in_floors`,
   `sealed_shift_in_floors`, `val_accuracy`, `val_errors` — must be passed explicitly,
   or the prediction is unadjudicable and `klein preflight` warns.

### 3.3 kleinlib helpers this study leans on — and the ones it deliberately does not

| Helper | Used? | Why |
|---|---|---|
| `kleinlib.data.load_partition` / `contract_split` | **yes, exclusively** | the only partition authority; prints the fingerprint the notary checks |
| `kleinlib.eval.evaluate` | **yes, every cell** | validated metric spec (`val_auc` is the registered classification primary, direction `higher`), the canonical printed block, the aux block, `aux_metrics.tsv` append, best-model snapshot |
| `kleinlib.eval`'s collapse / non-finite guard | **yes — and it matters here** | see below |
| `kleinlib.metrology.paired_bootstrap` | for the two paired floors | resamples ONE index vector and applies it to both series — common random numbers enforced by construction, not by a flag |
| `kleinlib.metrology.split_lottery` | for the `fisher` marginal floor | redraws train/development **inside the 75 non-sealed rows only** |
| `kleinlib.metrology.seed_sweep` | for `fit_noise` provenance | never a bar — `fit-noise` lands under `metric.fit_noise` with no `minimum_delta` line |
| `kleinlib.sweep.SweepRunner` + `klein sweep register` | the four Phase-0 sweeps | every trial to a sidecar TSV; crash rows are data |
| `kleinlib.encoders` | **no** | all four features are genuine `float64` centimetre measurements and there is no categorical column (`data_card.md`). Naming an encoder helper this study does not need would be cargo cult. |
| `kleinlib.torch_loop` | **no** | there is no neural network in the five declared recipes, so the MPS DataLoader collapse war story does not apply *as a batching problem*. Its downstream guard does apply — see below. |

**The near-constant / non-finite prediction guard, and why a 99-row study needs it.**
`kleinlib.eval` refuses a probability vector that is non-finite, outside [0, 1], or
numerically constant (fewer than 2 unique values, or range below
`max(32·eps·scale, collapse_rtol·scale)`), and records `proba_range`,
`min_proba_std` and `proba_unique_values` in `aux_metrics.tsv`. In this study that guard
is not a formality:

- `knn5` with $k=5$ can only ever emit probabilities from
  $\{0, 0.2, 0.4, 0.6, 0.8, 1.0\}$ — **at most 6 distinct values on 25 development
  flowers**. That is legitimate (`proba_unique_values ≤ 6` is the method's signature,
  not a bug) but it is exactly the regime where a genuine degeneracy would look normal.
  Reading `proba_unique_values` alongside the AUC is how you tell "coarse by design"
  from "collapsed by accident".
- `hgbt` with `max_iter=200` on 49 rows will drive its training probabilities toward
  0 and 1. If a fit ever degenerates to a single leaf, the guard raises rather than
  silently reporting AUC = 0.5.
- `svm_rbf` carries `probability=True`, which fits an internal Platt calibration by
  cross-validation with `random_state=20260904`. ROC-AUC is rank-based, so this map
  touches the number only through ties — but it *does* introduce seed dependence, which
  is precisely what the Phase-0 `fit_noise` sweep is there to document. `lda_all4`,
  `logreg_l2` and `knn5` have no seed at all; their `fit_noise` is zero by construction.

**Paired-bootstrap gotcha for an AUC difference.** `metrology.paired_bootstrap`'s
default statistic is a difference of row means, which AUC is not. An AUC floor must
draw the index vector explicitly and apply it to `y_eval`, `p_reference` and
`p_candidate` together:

```python
idx = rng.integers(0, n, size=n)
y_r = y[idx]
if y_r.min() == y_r.max():        # a single-class resample is a crash row, and crash rows are data
    return {"primary_metric": float("nan"), "status": "crash"}
delta = roc_auc_score(y_r, p_cand[idx]) - roc_auc_score(y_r, p_ref[idx])
```

At 13/12 on 25 rows a single-class resample has probability $\approx 5\times10^{-8}$,
so it will almost certainly never fire — but "almost certainly never" is the class of
event that ends a study at 2 a.m., and a `crash` row costs nothing.

**No verifier is declared.** This study is `kind: predict`, not `optimize`, and nothing
is checkpoint-scored, so there is no checker to freeze. `lib/iris.py` is stable library
code, deliberately outside the mutable surface, but it is *not* a verifier and must not
be described as one. `study.yaml` declares no `metric.verifier` on any track, and
`klein gate record method` will therefore hash an empty verifier set.

---

## 4. When it pays / when it doesn't

### The regime table

Read this as: *what does each family buy you, as a function of how much data you have
and what shape the truth is?* "Signal" here means the shape of the true boundary, not
its strength.

| Regime | Fit rows | Features | True boundary | LDA | `logreg_l2` | `knn5` | `svm_rbf` | `hgbt` |
|---|---|---|---|---|---|---|---|---|
| **A — this study** | ~50 | 4, smooth, near-Gaussian, near-equal covariance | close to a hyperplane | **pays — it is the plug-in Bayes rule (E4)** | ties LDA up to the penalty; the L2 shrinkage is a small, mostly harmless bias | doesn't pay: ~6-valued scores, high variance, curse of dimensionality already biting at $p=4$, $n=49$ | roughly ties at best; the kernel buys curvature the boundary does not need | doesn't pay: axis-aligned steps approximating an oblique plane, 200 boosting rounds on 49 rows |
| **B** | ~50 | few, but covariances genuinely unequal | a conic | breaks down — the flat boundary is the wrong family | same breakdown | may win, if the curvature is large relative to the noise | **pays — this is what the kernel is for** | may win if the curvature is axis-friendly |
| **C** | 10³–10⁴ | 10–100, mixed types, interactions, heavy tails | irregular, interaction-rich | underfits badly | underfits without engineered interactions | mediocre; distance loses meaning as $p$ grows | competitive but slow to tune | **pays — the tabular workhorse** (Grinsztajn et al. 2022) |
| **D** | ≥10⁵ | many, with strong nonlinearity | very irregular | no | no | no | poor scaling ($O(n^2)$–$O(n^3)$) | **pays**; deep tabular methods only start to compete here |
| **E** | ≤10³, tabular, 2025-era | any | any | strong, near-free baseline | strong baseline | weak | fair | fair — and a tabular foundation model (Hollmann et al. 2025) is the current frontier answer for exactly this cell |

### The doctrine, and where this study sits in it

The generic profile's doctrine (`references/profiles/generic.md` §3) is **measurement
resolution before comparison**: no delta is discussed before the floor that would
detect it has been measured, and no frontier is opened before its headroom is
disclosed. That is not a stylistic preference here — it is the single most likely
finding of the study, and §1 explains the arithmetic behind it.

Two pieces of published evidence support the pessimism, and one qualifies it:

- **Grinsztajn, Oyallon & Varoquaux (2022)** is the standard citation for "trees still
  win on typical tabular data", but read carefully it is a statement about *medium*
  data (~10 k rows) with mixed feature types, irregular target functions and
  uninformative features. Iris versicolor-versus-virginica has none of those
  properties: 99 rows, four smooth numeric measurements, no uninformative column. The
  paper's own analysis of *why* trees win — robustness to uninformative features and
  to non-smooth target functions — predicts, if anything, that trees should do
  **worse** here, because the target function is smooth and every feature is informative.
- **Fernández-Delgado et al. (2014)** ran 179 classifiers over 121 UCI datasets and
  found random forests and RBF-SVMs on top *on average* — while also documenting how
  small the winner's margin usually is over a competent simple baseline, and how much
  of the ranking is dataset-specific. A parade of five classifiers on one 99-row
  dataset is, statistically, one row of that table.
- **Hollmann et al. (2025)**, TabPFN, is the honest frontier qualifier: it is a
  transformer pre-trained on synthetic tabular tasks that is *specifically* strong on
  datasets with fewer than ~10 000 rows, i.e. this regime. It is **not** in this
  study's parade, and adding it now would be a contract change after the gate, which
  the loop forbids. It is named here so that "ninety years of research" is not read as
  "everything anyone has ever tried" — the parade is five named recipes fixed at
  CONSULT, and the study's conclusion can only ever be about those five.

**Verdict for this study's regime (A).** LDA should be at or very near the ceiling, and
every challenger is spending parameters on structure that probably is not there. The
interesting question is therefore not "who wins" but "**how wide is the ruler compared
with the distance anyone could possibly move**" — which is why the study measures the
floor before it runs a single challenger, and why P4 is written as a pre-scripted
branch rather than as a hope.

### Falsifiable priors this card stakes

Two classes of prior, and the distinction is load-bearing.

**(a) The registered ledger — already frozen.** `study.yaml` carries `predictions:`
P0–P15, registered at CONSULT and hashed into the consult gate record. In schema 3,
`predictions:` **is** the field the method-gate protocol calls
`predictions_to_falsify` (`kleinlib/contract.py` normalizes the legacy alias and
refuses a study that declares both). So the protocol's "mirror them into
`study.yaml:predictions_to_falsify`" step is satisfied by the existing ledger and this
card makes **no edit to `study.yaml`** — an edit would both break contract validation
and invalidate a recorded gate. What this card adds is the *method reasoning* behind
each, so SYNTHESIZE can tell a prediction that held for the right reason from one that
held by luck:

| id | Registered claim (abridged) | The method reason this card gives it |
|---|---|---|
| P1 | `lda_all4` dev ROC-AUC ≥ 0.90 | E4: the plug-in Bayes rule in its own assumption's regime; Fisher's own §VI separation was 3.57 pooled SDs, which is $\Phi(\Delta/\sqrt2)=0.994$ under E5 |
| P2 | ≤ 3 of 25 development flowers misclassified | E5's $\Phi(-\Delta/2)$ with a Fisher-era separation gives a few per hundred; on 25 flowers, 3 errors is 12 % and therefore a **tight** bar, not a safe one — the consultant said so and this card agrees |
| P3 | 95 % bootstrap CI for the dev AUC wider than 0.05 | 156 ordered pairs; Hanley & McNeil 1982's variance formula at $A \approx 0.97$ with $n_1=12$, $n_0=13$ gives a standard error of about 0.037, hence a 95 % interval on the order of 0.14 AUC wide — nearly three times the bar P3 sets |
| P4 | headroom $h<1$: no keep is arithmetically possible | if P1 and P3 both hold, $(1 - A_\text{ref})$ is smaller than one paired floor by construction |
| P5 | `logreg_l2` does not beat LDA by one floor | same hypothesis class (a hyperplane); only the fitting criterion and the L2 penalty differ |
| P6 | `knn5` does not beat LDA by one floor | ≤ 6 distinct scores, every tie costs ranking resolution; $p=4$, $n_\text{fit}=49$ |
| P7 | `svm_rbf` does not beat LDA by one floor | a kernel buys curvature this boundary does not need (regime A vs B) |
| P8 | `hgbt` lands at least one floor **below** LDA | axis-aligned staircases approximating an oblique plane, 200 rounds on 49 rows |
| P9 | zero keeps across the whole parade | the conjunction of P5–P8 |
| P10, P11 | the sealed shift ≤ 2 floors; the sealed gap < 1 floor | development and test are same-size, same-construction, hence exchangeable |
| P12–P15 | petal-only ≈ all-four; sepal-only ≥ 1 floor below | E3's $\mathbf{w}$ on the training rows is dominated by the two petal coefficients (`+8.49`, `+10.47`) against small sepal ones (`−5.30`, `−2.93`); Fisher's own 1936 compound has the same shape |

**(b) The card's own priors — M1–M6, descriptive, adjudicated in findings §③.** These
are stated in **AUC units** rather than in floors, so that they remain checkable
whatever the Phase-0 floor turns out to be. They are explicitly **not** registered
predictions, carry no `klein predict` id, and can never be substituted for one:

- **M1 (already resolved — HELD).** A from-scratch numpy LDA (E1–E4) reproduces
  `LinearDiscriminantAnalysis(solver="svd")` on this study's 49 training rows to within
  `1e-12` absolute on every coefficient. **Measured at this gate: max absolute
  coefficient difference 7.105e−15, cosine similarity 1.000000000000000.** Held by
  three orders of magnitude.
- **M2 — the parade is tight.** The best-minus-worst spread of development ROC-AUC
  across the five recipes will be **at most 0.12 AUC**. Falsified if any recipe lands
  more than 0.12 below the best.
- **M3 — kNN pays for its ties.** `knn5` will print `proba_unique_values ≤ 6`, and its
  development ROC-AUC will be **strictly below** `lda_all4`'s on the same rows
  (Δ < 0.000 AUC). Falsified if `knn5` ties or beats LDA.
- **M4 — boosting pays a capacity cost.** `hgbt` will land **at least 0.01 AUC below**
  `lda_all4` on the same development rows (Δ ≤ −0.010). Falsified if it lands within
  0.01, or above.
- **M5 — the petals carry it, in AUC units.** `lda_petal` will land **within 0.02 AUC**
  of `lda_all4` (|Δ| ≤ 0.020) and `lda_sepal` will land **at least 0.10 AUC below**
  it (Δ ≤ −0.100), both on the same development rows.
- **M6 — the ruler is wider than the race.** The Phase-0 paired-bootstrap floor for
  (`lda_all4`, `hgbt`) on the 25 development flowers — Klein's schema-3 bar,
  $\max(2\sigma,\ \text{range}/2)$ over 1000 replicates, where with $k=1000$ the
  $\text{range}/2$ term will bind at roughly $3.25\sigma$ — will land **between 0.03 and
  0.20 AUC**, and will exceed `lda_all4`'s entire remaining distance $1 - A_\text{ref}$
  to a perfect AUC. Falsified if the measured floor comes in below 0.03 or above 0.20
  AUC, or if it turns out smaller than $1 - A_\text{ref}$.

M2, M4 and M6 are the ones this card expects to be most at risk, and they are stated in
that form deliberately: a prior that cannot lose is not a prior. M6's lower bound in
particular is a real bet against the possibility that a paired comparison under common
random numbers cancels enough correlation to make 25 flowers a usable ruler after all —
if it does, the headline question becomes answerable and P4 is refuted.

---

## 5. Verified references

### 5.1 What Fisher himself reported about this exact species pair

**Transcribed at this gate from the original**, not from memory and not from a
textbook: the *Annals of Human Genetics* archive scan of Fisher (1936) was fetched,
its embedded text layer extracted, and the two load-bearing pages re-OCRed at 300 dpi
to recover the table digits. What follows is verbatim or directly tabulated from the
paper. **It is descriptive context for findings only. It is not a scored prediction,
and it is not the source of P2's bar of ≤ 3 development errors** — P2 is the
consultant's own independent first-principles estimate, registered before this
transcription existed, and the two must not be conflated in any later document.

**Finding 1 — Fisher's famous worked example is the EASY pair, not this one.**
Sections II–V of the paper derive the discriminant for *Iris setosa* vs
*I. versicolor*, obtaining
$\lambda_1 = -0.0311511,\ \lambda_2 = -0.1839075,\ \lambda_3 = +0.2221044,\ \lambda_4 = +0.3147370$,
normalized to $X = x_1 + 5.9037x_2 - 7.1299x_3 - 10.1036x_4$, a mean difference of
33.816 cm and a within-species standard deviation of 3.3804 cm. From the ratio 5.0018
he concludes: *"the probability of misclassification, using the compound movement only
is less than three per million."* **That number is about setosa, and has nothing to do
with this study.**

**Finding 2 — for versicolor vs virginica, Fisher reported no misclassification count
at all.** The hard pair appears only in §VI, "Applications to the theory of
allopolyploidy", where the compound is built to test whether versicolor sits two-thirds
of the way from setosa to virginica — the within-species matrix is formed by weighting
virginica × 16, versicolor × 1 and setosa × 25 — so it is **not** a two-class
discriminant of the hard pair. Its coefficients, ×100, are:

| Coefficient of | value ×100 |
|---|---|
| sepal length | −3.308998 |
| sepal breadth | −2.759132 |
| petal length | +8.866048 |
| petal breadth | +9.392551 |

and its **Table IX** reads, verbatim:

| species | Mean | Sum of squares | Mean square | Standard deviation |
|---|---|---|---|---|
| *I. virginica* | 38.24827 | 923.7958 | 18.8530 | 4.342 |
| *I. versicolor* | 22.93888 | 873.5119 | 17.8268 | 4.222 |
| *I. setosa* | −10.75042 | 292.8958 | 5.9775 | 2.444 |

Fisher's own two sentences about the pair this study models:

> "From this table it can be seen that, whereas the difference between *I. setosa* and
> *I. versicolor*, 33·69 of our units, is so great compared with the standard deviations
> that no appreciable overlapping of values can occur, the difference between
> *I. virginica* and *I. versicolor*, 15·31 units, is **less than four times the
> standard deviation of each species**."

> "It will be noticed, as was anticipated above, that there is some overlap of the
> distributions of *I. virginica* and *I. versicolor*, so that **a certain diagnosis of
> these two species could not be based solely on these four measurements of a single
> flower taken on a plant growing wild**. It is not, however, impossible that in culture
> the measurements alone should afford a more complete discrimination."

*(— Fisher 1936, pp. 187–188.)*

**So the transcription's answer is: Fisher reported a separation, not an error count.**
The number to carry into findings is **15.31 units between the two species means,
against within-species standard deviations of 4.342 and 4.222** — a separation Fisher
himself characterized as *less than four standard deviations*, with explicit,
unavoidable overlap. Any secondary source that attributes a specific
misclassification count for versicolor-versus-virginica to Fisher (1936) is
attributing something the paper does not contain.

**Derived by this card, clearly labelled as such.** Applying E5 to Fisher's own printed
Table IX (pooled within-species standard deviation
$\sqrt{(18.8530+17.8268)/2} = 4.2825$):

- separation $\hat\Delta = 15.30939 / 4.2825 = \mathbf{3.575}$ pooled standard deviations;
- implied ROC-AUC $\Phi(\hat\Delta/\sqrt2) = \mathbf{0.9943}$;
- implied error rate at the midpoint threshold, in Fisher's own one-tail style,
  $\Phi(-\hat\Delta/2) = 0.0369 = \mathbf{3.7\ per\ 100\ flowers}$.

Three caveats, all mandatory. *(i)* This is **this card's arithmetic on Fisher's
published summary statistics under a Gaussian equal-covariance model**, on all 100 of
his flowers, using a compound built for a three-species test — not a held-out
measurement, not this study's partition, and not comparable to a count of errors on 25
development flowers. *(ii)* The one-tail convention was checked, not assumed: Fisher's
two quoted anchor deviates, 4·89164 and 5·32672, correspond to exact one-tail normal
tails of $5\times10^{-7}$ and $5\times10^{-8}$, so his rule is the one-tail probability
(his printed "per million" figures correspond to one-tail probabilities ten times
smaller — i.e. per ten million — consistently across that passage).
*(iii)* **None of this is P2.** P2's bar of at most 3 misclassified development flowers
was registered at CONSULT from the consultant's own first-principles estimate, before
this transcription existed, and is adjudicated by `klein run-one --tests P2` on the
printed `val_errors` key. "3.7 per 100" and "3 of 25" are different quantities on
different rows under different assumptions, and no later document may substitute one
for the other or describe P2 as "Fisher's number".

### 5.2 Lit-scan and positioning

LDA is not a frontier method — it is the oldest method in the repository. The scan
required by the gate protocol was therefore run in the other direction: *where does a
1936 linear discriminant sit against 2026 practice, honestly?*

- **Seminal:** Fisher 1936 (the criterion), on data collected by Anderson 1935.
  Welch 1939 is the two-page note that makes the decision-theoretic optimality
  statement E4 rests on.
- **Key follow-ups, one per challenger:** Berkson 1944 and Cox 1958 (the logistic
  model as the discriminative twin of LDA); Fix & Hodges 1951 and Cover & Hart 1967
  (the nearest-neighbour rule and its asymptotic error bound, ≤ 2× Bayes);
  Boser–Guyon–Vapnik 1992 and Cortes & Vapnik 1995 (margins and kernels);
  Friedman 2001 and Ke et al. 2017 (gradient boosting and its histogram-binned
  descendant, which is what `HistGradientBoostingClassifier` implements).
- **The trend, and the honest position:** Grinsztajn et al. 2022 says trees still beat
  deep learning on typical tabular data — but its "typical" is ~10 k rows with mixed
  types and irregular targets, none of which describes 99 smooth numeric rows, and its
  own explanation of *why* trees win predicts they should do worse here.
  Fernández-Delgado et al. 2014 is the sobering companion: 179 classifiers, 121
  datasets, and margins between the leaders that are frequently smaller than
  dataset-to-dataset variation. Hollmann et al. 2025 (TabPFN) is the live frontier for
  exactly this size of table and is deliberately **outside** this study's parade — the
  five recipes were fixed at CONSULT and a sixth added now would be a contract change.
- **Data provenance:** Bezdek et al. 1999 documents that at least two distinct
  published replicates of the iris table exist and that the UCI copy contains errors.
  This study's DATA gate independently re-derived that diff and found the discrepancies
  confined to two *setosa* rows, so nothing in the hard pair is affected
  (`data_card.md`, NOTE 5).

### 5.3 Reference table

Every row below was checked at a publisher, archive or proceedings page on the date
shown — venue, year and locator — never cited from memory. Full entries with locators
live in `references.yaml`; a `ref:<key>` evidence id resolves against that file.

| Key | Reference | Where | Verified? |
|---|---|---|---|
| `fisher1936` | Fisher, R. A. (1936), *The use of multiple measurements in taxonomic problems* | Annals of Eugenics 7(2), 179–188 · doi:10.1111/j.1469-1809.1936.tb02137.x | ✅ (full text read from the Annals of Human Genetics archive scan; venue/volume/issue/pages independently confirmed at the Rothamsted repository record, eprint 33079) |
| `anderson1935` | Anderson, E. (1935), *The irises of the Gaspé Peninsula* | Bulletin of the American Iris Society 59, 2–5 | ✅ (CiNii Research record; corroborated by the R `datasets::iris` documentation, which cites the same volume and pages as the data's origin) |
| `welch1939` | Welch, B. L. (1939), *Note on discriminant functions* | Biometrika 31(1/2), 218–220 · doi:10.2307/2334985 | ✅ (JSTOR record, volume/issue/pages/year confirmed) |
| `berkson1944` | Berkson, J. (1944), *Application of the logistic function to bio-assay* | JASA 39(227), 357–365 · doi:10.1080/01621459.1944.10500699 | ✅ (Taylor & Francis article page; JSTOR 2280041 corroborates volume, issue and pages) |
| `cox1958` | Cox, D. R. (1958), *The regression analysis of binary sequences* | JRSS Series B 20(2), 215–232 · doi:10.1111/j.2517-6161.1958.tb00292.x | ✅ (Oxford Academic and Wiley records agree on volume, issue, pages, year) |
| `fixhodges1951` | Fix, E. & Hodges, J. L. (1951), *Discriminatory analysis — nonparametric discrimination: consistency properties* | USAF School of Aviation Medicine, Randolph Field TX, Project 21-49-004, Report No. 4; reprinted International Statistical Review 57(3), 238–247 (1989) · doi:10.2307/1403797 | ✅ (JSTOR record for the 1989 reprint; the 1951 report's project and report numbers confirmed from the HathiTrust catalog record) |
| `coverhart1967` | Cover, T. M. & Hart, P. E. (1967), *Nearest neighbor pattern classification* | IEEE Trans. Information Theory 13(1), 21–27 · doi:10.1109/TIT.1967.1053964 | ✅ (dblp and ACM DL records agree on volume, issue, pages) |
| `boser1992` | Boser, B. E., Guyon, I. M. & Vapnik, V. N. (1992), *A training algorithm for optimal margin classifiers* | Proc. 5th Annual Workshop on Computational Learning Theory (COLT '92), 144–152 · doi:10.1145/130385.130401 | ✅ (ACM Digital Library proceedings record) |
| `cortesvapnik1995` | Cortes, C. & Vapnik, V. (1995), *Support-vector networks* | Machine Learning 20(3), 273–297 · doi:10.1007/BF00994018 | ✅ (Springer article page) |
| `friedman2001` | Friedman, J. H. (2001), *Greedy function approximation: a gradient boosting machine* | Annals of Statistics 29(5), 1189–1232 · doi:10.1214/aos/1013203451 | ✅ (Project Euclid article page) |
| `ke2017` | Ke, G. et al. (2017), *LightGBM: a highly efficient gradient boosting decision tree* | Advances in Neural Information Processing Systems 30, 3146–3154 | ✅ (official NeurIPS 2017 proceedings PDF) |
| `hanley1982` | Hanley, J. A. & McNeil, B. J. (1982), *The meaning and use of the area under a ROC curve* | Radiology 143(1), 29–36 · doi:10.1148/radiology.143.1.7063747 | ✅ (PubMed record 7063747; RSNA article PDF) |
| `efron1979` | Efron, B. (1979), *Bootstrap methods: another look at the jackknife* | Annals of Statistics 7(1), 1–26 · doi:10.1214/aos/1176344552 | ✅ (Project Euclid article page) |
| `grinsztajn2022` | Grinsztajn, L., Oyallon, E. & Varoquaux, G. (2022), *Why do tree-based models still outperform deep learning on typical tabular data?* | NeurIPS 2022 Datasets & Benchmarks · arXiv:2207.08815 | ✅ (arXiv id and NeurIPS D&B track confirmed; ACM DL proceedings record) |
| `fernandezdelgado2014` | Fernández-Delgado, M., Cernadas, E., Barro, S. & Amorim, D. (2014), *Do we need hundreds of classifiers to solve real world classification problems?* | JMLR 15(90), 3133–3181 | ✅ (JMLR volume-15 article page) |
| `hollmann2025` | Hollmann, N. et al. (2025), *Accurate predictions on small data with a tabular foundation model* | Nature 637(8045), 319–326 · doi:10.1038/s41586-024-08328-6 | ✅ (Nature article record) |
| `bezdek1999` | Bezdek, J. C., Keller, J. M., Krishnapuram, R., Kuncheva, L. I. & Pal, N. R. (1999), *Will the real iris data please stand up?* | IEEE Trans. Fuzzy Systems 7(3), 368–369 · doi:10.1109/91.771092 | ✅ (IEEE/ACM DL record; author's own copy of the correspondence) |
| `pedregosa2011` | Pedregosa, F. et al. (2011), *Scikit-learn: machine learning in Python* | JMLR 12, 2825–2830 | ✅ (JMLR volume-12 article page) |

**18 verified, 0 unverified.** `refs_verified: true` in the frontmatter is therefore
honest, and the Papers leg of the triad stands.

### 5.4 Triad assertion

| Leg | State | Evidence |
|---|---|---|
| **Theory** | `true` | §2 carries the notation table and five display equations E1–E5, including the derivation of the closed form from the criterion and the equal-covariance optimality argument. |
| **Papers** | `true` | §5.3: 18 references, every one verified against a publisher/archive page on 2026-09-04, 0 marked UNVERIFIED. `references.yaml` carries the locators. |
| **Practice** | `true` | §3.1's from-scratch numpy LDA was **run** at this gate (`method_check_lda.py`) on this study's own prepared training partition and agrees with `LinearDiscriminantAnalysis(solver="svd")` to a maximum absolute coefficient difference of **7.105e−15** and a direction cosine similarity of **1.000000000000000**. §3.2 gives the cell skeleton `train.py` realizes and §3.3 names the exact kleinlib helpers — and the ones deliberately not used. |

No leg is missing, so `klein gate record method` needs no `--note` naming an
incomplete leg.
