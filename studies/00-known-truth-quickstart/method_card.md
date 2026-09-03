---
type: method-card
domain: "synthetic"
profile: "generic"
status: draft
concepts: []
related: []
refs_verified: true
triad:
  theory: true
  papers: true
  practice: true
---

# Method card — the Bayes ceiling, and the detection-limit (headroom) law

> Gate 2 (METHOD). Pedagogy for the two ideas this study is built on, written
> BEFORE modeling. Protocol:
> `.claude/skills/klein/references/method-gate-protocol.md`.

The "method" here is not a model family — logistic regression and gradient
boosting are both older than most readers and neither needs a card. What needs a
card is the pair of ideas the study exists to teach: **how far can any model
possibly get** (the Bayes ceiling), and **when is it arithmetically pointless to
keep trying** (the headroom law). Both are quantities, both are computable here,
and a reader who has not met them will otherwise mistake "my score stopped
moving" for "my model is bad".

## 1. Intuition (for a practitioner)

Suppose you are grading weather forecasters on whether it rains tomorrow. Even a
forecaster who knows the true probability of rain for every single day will not
score perfectly — because it sometimes fails to rain on an 80 % day. There is a
best possible score, and it is set by the world's coin flips, not by the
forecaster. That best possible score is the **Bayes ceiling**.

On real data nobody knows it. Here we do, because we wrote the world: `prepare.py`
declares the process that generated every row, so the true probability of each
row's label is known, and the score a perfect forecaster would get can simply be
computed. That single fact turns a vague "how much better could this get?" into
arithmetic.

The second idea follows immediately. Suppose your best model is 0.004 AUC below
the ceiling, and you have measured that re-drawing your development partition
moves the score by about 0.012. Then **no model, not even the perfect one, can
beat your current one by an amount your measurement could tell apart from noise**.
The tournament is over before it starts. Klein writes that as

    h = (ideal - incumbent) / minimum_delta

and calls it **headroom**. `h < 1` means the door is closed: keep spending and you
are buying lottery tickets in a lottery with no prizes. The honest move is to say
so on the record and re-scope — which is exactly what this study will do, live,
in front of the reader.

Two warnings the field learned the hard way and this card repeats:

- `h >= 1` is **"not excluded"**, never "plausible". A study can stand at
  `h = 1.015`, run twenty-one challengers, and keep none of them: the *attainable*
  ceiling usually sits well below the *ideal* one.
- The floor you divide by must be the floor that judges YOUR comparison. Refitting
  the same model under different random seeds tells you how much the FIT wobbles;
  it says nothing about how much the MEASUREMENT wobbles, and it is often an order
  of magnitude smaller. Only the second is a keep bar.

## 2. Math core

| Symbol | Meaning |
|---|---|
| $x \in \mathbb{R}^{8}$ | one row's eight features |
| $y \in \{0,1\}$ | its label |
| $\eta(x)$ | the DGP's true log-odds for that row |
| $p(x) = \sigma(\eta(x))$ | the true probability of $y = 1$ |
| $s(x)$ | any model's score for that row |
| $A[s]$ | the AUC of the score $s$ on a fixed set of rows |
| $\delta$ | `minimum_delta`, the measured noise floor |
| $h$ | headroom, in units of $\delta$ |

The generating process is a logistic model with one interaction and one
quadratic term, so the truth is smooth but not linear in the raw features:

$$ \eta(x) = \beta_0 + \sum_{j=1}^{6} \beta_j x_j + \beta_{12}\, x_1 x_2 + \beta_{33}\, x_3^2, \qquad y \sim \mathrm{Bernoulli}(\sigma(\eta(x))) $$

AUC is the probability that a random positive outscores a random negative
(ref:hanley1982):

$$ A[s] = \Pr\big( s(X^{+}) > s(X^{-}) \big) + \tfrac{1}{2}\Pr\big( s(X^{+}) = s(X^{-}) \big) $$

Because $A[s]$ depends on $s$ only through the ORDER it puts the rows in, and
because $\Pr(y = 1 \mid x) = p(x)$ is by construction the true ordering, no score
can beat $p$:

$$ A[s] \le A[p] \equiv A_{\text{Bayes}} \quad \text{for every } s $$

so $A_{\text{Bayes}}$ — computable here, since $\eta$ is known per row — is the
ceiling. (It is a ceiling for THESE rows: a different draw of 4 000 rows has its
own $A_{\text{Bayes}}$, which is why the sealed partition's ceiling is a
different number from the development partition's, and why the sealed prediction
is stated with a tolerance rather than as an equality.)

The detection-limit law is then one line:

$$ h = \frac{A_{\text{Bayes}} - A[\hat{s}]}{\delta}, \qquad h < 1 \Rightarrow \text{no candidate can produce a keep} $$

## 3. Minimal from-scratch implementation plan

Both quantities are a few lines each; nothing here is a library trick.

```
# the ceiling, for exactly the rows a run was graded on
eta        = truth["true_log_odds"][rows]        # declared by prepare.py
p_true     = 1 / (1 + exp(-eta))
bayes_auc  = auc(y_eval, p_true)                 # the best any score can do here

# the run's own headroom
gap_in_floors = (bayes_auc - candidate_auc) / minimum_delta

# the measured floor itself (Phase 0, sweeps/noise_floor.py)
for seed in seeds:                               # split-lottery / marginal-resplit
    X_tr, X_dev = redraw_train_dev(seed)         # a DIFFERENT partition each time
    values.append(auc(y_dev, fit(X_tr).predict(X_dev)))
minimum_delta = max(2 * std(values), (max(values) - min(values)) / 2)
```

`train.py` realizes this plan on top of three Klein helpers rather than
re-implementing the harness: `kleinlib.data.load_partition` (the contract's
partition, and the `split_fingerprint:` line the notary checks),
`kleinlib.contract.load_contract` (the floor is READ, never written as a literal
— war story 8 applies to bars as much as to seeds), and `kleinlib.eval.evaluate`
(the canonical printed block). The floor itself is measured by
`kleinlib.sweep.SweepRunner` into a sidecar and turned into a contract block by
`klein noise-floor --recipe split-lottery --estimand marginal-resplit`.

The ladder's four rungs are the smallest set that separates the two mechanisms
the DGP contains:

| rung | what it can express |
|---|---|
| `logreg_raw` | one hyperplane in the raw features — neither the interaction nor the quadratic |
| `logreg_interaction` | the same, plus the DGP's true $x_1x_2$ term, handed to it |
| `hgbt_default` | axis-parallel boxes summed stagewise (ref:friedman2001, ref:ke2017) — can approximate both terms without being told either |
| `hgbt_overcapacity` | the same family with ~5x the trees, 127 leaves, no shrinkage discipline and no early stopping |

## 4. When it pays / when it doesn't

Reading a known ceiling and a measured floor before opening a frontier:

| Regime | Data size | Signal | Verdict |
|---|---|---|---|
| the truth is nonlinear and the model class is linear | any | any | the gap is structural — pays to change the model class, not the hyperparameters |
| incumbent is many floors from the ceiling | any | any | pays — there is measurable room, keep climbing |
| incumbent is under one floor from the ceiling (`h < 1`) | any | any | doesn't — no keep is arithmetically possible; re-scope or shrink the floor |
| ceiling unknown, floor unmeasured | any | any | doesn't — every "improvement" is unfalsifiable; measure the floor first |
| small development partition | small | any | the floor is wide, so `h` collapses early: the honest ceiling is the one the measurement can see, not the one the model can reach |

Against the generic profile's doctrine — *measurement resolution before
comparison* — the order this study is obliged to follow is: anchor, floor,
headroom, and only then a comparison. Against the tabular doctrine
(ref:grinsztajn2022), a boosted tree is the right top rung for a 20 000-row,
8-column table; a network is not the thing to reach for here.

**Falsifiable priors this card commits to** (mirrored into `study.yaml:predictions`):

- **P1** — a logistic regression on the raw features cannot reach the ceiling:
  more than one measured floor of distance is left.
- **P2** — handing that model the DGP's true interaction beats it by at least one
  measured floor on the same rows.
- **P3** — a boosted tree, told none of the true terms, beats the hand-specified
  interaction rung by at least one measured floor on the same rows.
- **P4** — buying capacity on top of the boosted rung is within noise: the
  over-capacity model lands less than one floor from its own reference.
- **P5** — on the sealed partition the selected candidate lands within two
  measured floors of that partition's ceiling.

The card's own expectation, recorded so SYNTHESIZE can hold it to account: P1,
P2, P3 and P5 hold; P4 is the one genuinely open question, because "loses a
little" and "loses more than a floor" are both plausible for an over-capacity
learner on 12 000 rows, and the card declines to guess which.

## 5. Verified references

Every row below was checked on 2026-09-03 against the publisher or arXiv page —
none is quoted from memory. Machine-readable entries with locators and dates:
`references.yaml`.

| Reference | Where | Verified? |
|---|---|---|
| Hanley & McNeil 1982, *The meaning and use of the area under a receiver operating characteristic (ROC) curve* | Radiology 143(1), 29-36 · doi:10.1148/radiology.143.1.7063747 | verified (`ref:hanley1982`) |
| Friedman 2001, *Greedy function approximation: a gradient boosting machine* | Annals of Statistics 29(5), 1189-1232 · doi:10.1214/aos/1013203451 | verified (`ref:friedman2001`) |
| Ke et al. 2017, *LightGBM: a highly efficient gradient boosting decision tree* | NeurIPS 30, 3146-3154 | verified (`ref:ke2017`) |
| Grinsztajn, Oyallon & Varoquaux 2022, *Why do tree-based models still outperform deep learning on tabular data?* | NeurIPS 2022 Datasets & Benchmarks · arXiv:2207.08815 | verified (`ref:grinsztajn2022`) |

Triad: **Theory** — §2's notation table and four display equations; **Papers** —
all four references verified, `refs_verified: true`; **Practice** — §3's
from-scratch plan for both the ceiling and the floor, which `train.py` and
`sweeps/noise_floor.py` realize line for line.
