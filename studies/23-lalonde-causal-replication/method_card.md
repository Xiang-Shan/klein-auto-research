---
type: method-card
domain: "program evaluation (labor economics)"
profile: "data-science"
status: complete
concepts: [estimand, att, experimental-benchmark, selection-on-observables, propensity-score, balancing-property, odds-weights, ipw, doubly-robust, aipw, nearest-neighbour-matching, common-support, weight-concentration, bootstrap-failure, specification-sensitivity, placebo-test]
related: [study.yaml, research_plan.md, scouting_ledger.md, data_card.md, lib/lalonde.py, analyze.py, references.yaml, ../../knowledge/method_cards/causal-propensity-methods.md]
refs_verified: true     # all 18 rows of references.yaml checked 2026-11-03; `klein refs verify`: 18 references, 0 failed
triad:
  theory: true          # §2: notation table + five display equations (estimand/gap, identification, IPW, DR, matching)
  papers: true          # refs_verified is true; every row checked against Crossref plus a landing page
  practice: true        # §3: the from-scratch plan, realized function by function in lib/lalonde.py (exists, outside the mutable surface) and selected per cell in analyze.py
---

# Method card — propensity-score estimators audited against an experimental benchmark

> Gate 2 (METHOD), written BEFORE any estimator was run. No number on this card was
> computed on the study's data. Each number is copied from a cited paper (mostly the
> Dehejia-Wahba working paper, `ref:dehejia1998nber`), from `study.yaml`, or from
> `scouting_ledger.md`. Protocol: `.claude/skills/klein/references/method-gate-protocol.md`.
> Builds on the seed card `knowledge/method_cards/causal-propensity-methods.md`.

## 1. Intuition (for a practitioner)

*Written for an applied data scientist who has fit propensity models but has never
had to check one against an experiment.*

**You already know this method. It is covariate-shift correction.** If you have ever
trained a "domain classifier" to tell target rows from source rows, then reweighted the
source rows by p/(1-p) so they look like the target, you have done the core of ATT
propensity weighting. Here the *target* population is the 185 men who took the NSW
job-training programme. The *source* is 2,490 PSID survey men who did not. The quantity
we cannot observe is what the trainees would have earned in 1978 without training.
Propensity methods estimate it from the source rows, reweighted or matched to look like
the trainees. The effect on the treated (ATT) is then "what they earned" minus "what
they would have earned".

**What makes this study unusual is that the answer key exists.** NSW was a randomised
experiment, so 260 men were randomised *out* of the programme. Their mean 1978 earnings
are an unbiased estimate of the trainees' untreated earnings. That gives the
experimental benchmark of about $1,794 (Dehejia-Wahba Table 3; `scouting_ledger.md` S2).
In practice you almost never have a labelled test set for a counterfactual. LaLonde
(`ref:lalonde1986`) built one, and showed that the standard nonexperimental estimators
of 1986 failed against it. Dehejia and Wahba (`ref:dehejia1999`) then reported that
propensity-score methods on the same files give estimates from $1,473 to $1,774
(`ref:dehejia1998nber`, §6).

**One identity frames the whole audit.** The study's `att_gap_usd` is the estimate
minus the experimental estimate, both computed in the same run. Both use the same 185
trainees' outcomes, so those outcomes **cancel**:

> gap = (mean 1978 earnings of the 260 NSW controls) − (the estimator's prediction of
> that mean, built from PSID men).

So P2–P5 do not test "did we estimate the programme effect". They test "can PSID men,
weighted or matched on the trainees' covariates, predict what the randomised-out
controls earned?". The trainees' covariates choose which PSID men count. Their outcomes
never enter the gap.

**Three things decide whether this works, and only two can be checked:**

1. **Selection on observables** (unconfoundedness). Everything that made trainees
   differ from PSID men in untreated earnings is captured by the covariates: age,
   schooling, race, marriage, degree, and earnings in 1974 and 1975. This cannot be
   checked from the data. The benchmark is what lets this study check it from outside.
2. **Overlap.** For every kind of trainee there must be some PSID men like him. This can
   be checked, and PSID-1 fails it badly at the top. Dehejia and Wahba report that 98 of
   the 185 trainees have an estimated score above 0.8, against only **7** PSID men
   (`ref:dehejia1998nber`, §4). Half the counterfactual has to come from a handful of
   people.
3. **Specification.** The score is a logit someone wrote down. If it is wrong, the
   weights are wrong. This can be partly checked through covariate balance. Smith and
   Todd (`ref:smith2005`) showed that the agreement with the benchmark depends on which
   variables go into the score and which sample is used.

**The three estimators are three ways to borrow PSID men:**

- **IPW (odds weighting)** gives every PSID man inside the support a weight
  e/(1-e). This is the covariate-shift weight. It is smooth and uses everyone, but one
  man with e = 0.97 counts as much as about 32 men with e = 0.5.
- **1-NN matching with replacement** works like k-nearest-neighbour imputation with
  k = 1 on a one-dimensional embedding, the score. Each trainee borrows the single PSID
  man closest in score, and popular PSID men are reused. This is the design of
  Dehejia-Wahba Table 3 column (7).
- **Doubly robust AIPW** works like "model prediction plus a weighted residual
  correction". An OLS model fitted on PSID men predicts each trainee's untreated
  earnings. The odds-weighted PSID residuals then correct that model's average error.
  It is consistent if either the logit or the regression is right. It is not immune
  when both are a little wrong and a few weights are huge (`ref:kang2007`).

## 2. Math core

| Symbol | Meaning |
|---|---|
| $i \in T$, $N_1 = 185$ | the NSW treated men (`nsw`, `treat = 1`) |
| $C^{\text{NSW}}$, $N_0^{\text{NSW}} = 260$ | the NSW randomised-out controls (`nsw`, `treat = 0`); used ONLY for the benchmark |
| $j \in C$ | the nonexperimental comparison men: PSID-1 (2,490, development) or CPS-1 (15,992, sealed) |
| $Y = $ `re78` | 1978 earnings, 1982 dollars; $Y(1), Y(0)$ the potential outcomes with / without training |
| $X$ | pre-programme covariates: age, education, black, hispanic, married, nodegree, `re74`, `re75` and the derived terms of `lib/lalonde.py:features` |
| $e(x) = P(T=1 \mid X=x)$ | the propensity score **in the pooled file** (NSW treated ∪ comparison men); $\hat e$ its logit estimate |
| $w(x) = e(x)/(1-e(x))$ | the ATT odds weight on a comparison man |
| $S$ | the common-support set of comparison men (eq. 3) |
| $\hat\mu_0(x)$ | an outcome model for $E[Y(0) \mid X=x]$; here OLS on $S$ with Table 3 note a's covariates |
| $m(i)$, $K_j$ | the matched comparison man of treated $i$; the number of treated men matched to $j$ |
| gap | $\hat\tau - \hat\tau_{\text{exp}}$, printed as `att_gap_usd` |

**(1) Estimand, benchmark, and the gap identity.**

$$
\tau_{\text{ATT}} = E\big[Y(1)-Y(0)\mid T=1\big],\qquad
\hat\tau_{\text{exp}} = \bar Y_T - \bar Y_{C^{\text{NSW}}},\qquad
\text{gap} = \hat\tau - \hat\tau_{\text{exp}} = \bar Y_{C^{\text{NSW}}} - \hat\mu_{0\mid T}
$$

Each estimator below has the form $\hat\tau = \bar Y_T - \hat\mu_{0\mid T}$, where
$\hat\mu_{0\mid T}$ is its estimate of the trainees' mean untreated earnings, so the
treated mean cancels in the gap. Randomisation identifies $E[Y(0)\mid T=1]$ by
$E[Y \mid C^{\text{NSW}}]$. The nonexperimental estimators must identify the same
quantity from $C$.

**(2) Identification from comparison men: selection on observables, overlap, balancing.**

$$
Y(0)\perp T \mid X,\;\; e(x)<1
\;\;\Longrightarrow\;\;
E\big[Y(0)\mid T=1\big] = \frac{E\big[w(X)\,Y \mid T=0\big]}{E\big[w(X)\mid T=0\big]},
\qquad
\frac{p(x\mid T=1)}{p(x\mid T=0)} = w(x)\,\frac{P(T=0)}{P(T=1)}
$$

The second identity is the covariate-shift fact. Odds-weighting the comparison men
reshapes their covariate distribution into the trainees' distribution. The **balancing
property** (`ref:rosenbaum1983`) is $X \perp T \mid e(X)$. So unconfoundedness given $X$
implies unconfoundedness given the scalar $e(X)$, which is why one can match or weight
on one number instead of 13. Two consequences for this design:

- Nobody "assigned" PSID men to anything. Here $e$ is a sample-composition probability in
  a pooled file. Changing how many comparison men are pooled moves only the intercept
  of a correctly specified logit, which multiplies every odds by one constant. Normalised weights (eq. 3) are
  unchanged and the score's rank order is unchanged. Matching *distances* do change,
  which is one reason matching and weighting can disagree.
- Overlap is the condition $e(x) < 1$ on the support of the *treated*. Where it nearly
  fails, $w$ explodes. That is the weight-concentration diagnostic below.

**(3) Odds-weighted IPW on common support (Dehejia-Wahba Table 3 note g).**

$$
S = \Big\{\, j\in C:\ \min_{i\in T}\hat e_i \le \hat e_j \le \max_{i\in T}\hat e_i \,\Big\},
\qquad
\hat\tau_{\text{IPW}} = \frac{1}{N_1}\sum_{i\in T} Y_i \;-\; \frac{\sum_{j\in S}\hat w_j\,Y_j}{\sum_{j\in S}\hat w_j},
\quad \hat w_j = \frac{\hat e_j}{1-\hat e_j}
$$

Note g trims **only comparison men**: those scored outside the treated range. Every
trainee is kept, so the estimand remains the ATT over all 185 men and the benchmark
stays comparable. The cost is that no comparison man is ADDED where overlap is thin.
The trainees above 0.8 are still served by about 7 men. The
Crump et al. rule (`ref:crump2009`) keeps units with $\hat e \in [0.1, 0.9]$. It trims
*treated* men too, which changes the estimand, and the benchmark then has to be
recomputed on the same trimmed trainees. Imbens and Xu's trimmed LDW-PSID benchmark is
$306, not $1,794 (`ref:imbens2025`). This study keeps note g, so the $1,794 benchmark is
the right comparison.

**(4) Doubly robust ATT (augmented IPW).**

$$
\hat\tau_{\text{DR}} = \frac{1}{N_1}\sum_{i\in T}\big(Y_i-\hat\mu_0(X_i)\big)
\;-\; \frac{\sum_{j\in S}\hat w_j\,\big(Y_j-\hat\mu_0(X_j)\big)}{\sum_{j\in S}\hat w_j},
\qquad \hat\mu_0(x) = x^\top\hat\beta,\;\; \hat\beta = \text{OLS of } Y \text{ on } X_{\text{note a}} \text{ over } S
$$

Why it is doubly robust (`ref:robins1994`, `ref:bang2005`; the ATT form with
odds-weighted comparison units is that of `ref:santanna2020`):

- If $\hat\mu_0$ is correct, the comparison residuals have mean zero under *any* weights.
  The first term alone is then the ATT.
- If the weights are correct, the weighted residual mean equals
  $E[Y(0)-\hat\mu_0(X)\mid T=1]$. Subtracting it removes $\hat\mu_0$'s error for the
  treated, whatever $\hat\mu_0$ is.

With a linear $\hat\mu_0$, eq. (4) equals eq. (3) plus
$\hat\beta^\top(\bar X_{\text{w-comparison}} - \bar X_T)$. AIPW shifts IPW by the
outcome slope times whatever covariate imbalance the weights leave behind. That is the
mechanism behind card prior M4.

**(5) 1-NN matching on the score, with replacement (Table 3 column (7)).**

$$
m(i) = \arg\min_{j\in S}\big|\hat e_i-\hat e_j\big|,\qquad
\hat\tau_{\text{M}} = \frac{1}{N_1}\sum_{i\in T}\big(Y_i - Y_{m(i)}\big) = \bar Y_T - \sum_{j\in S}\frac{K_j}{N_1}\,Y_j,
\qquad K_j = \#\{i: m(i)=j\}
$$

Matching is weighting with integer weights $K_j/N_1$.

**The weight-concentration diagnostic.** Every att cell prints `max_weight_share`. For
IPW and AIPW it is $\max_j \hat w_j / \sum_{j\in S}\hat w_j$. For matching it is
$\max_j K_j / N_1$. It is the fraction of the whole counterfactual that rests on one
comparison man. `n_controls_used` is $|S|$ for IPW and AIPW, and the number of distinct
matched men $\#\{j: K_j>0\}$ for matching. Together they are the overlap evidence a
referee needs to tell "agreement" from "agreement by accident" (`research_plan.md`,
"What would change the conclusion").

**Why the bootstrap interval is not the same thing for every cell.** `lib/lalonde.py:bootstrap`
resamples treated and comparison men separately, **re-fits the logit in every draw**, and
reports the 2.5/97.5 percentiles of $\hat\tau$. Four things follow:

- *Matching (P4).* The standard bootstrap is in general **not valid** for nearest-neighbour
  matching with replacement and a fixed number of matches, even with one continuous
  covariate (`ref:abadie2008`). The estimator is a highly nonsmooth function of the
  data (`ref:abadie2006`). Valid alternatives are Abadie and Imbens's analytic variance
  or subsampling. With an *estimated* score, the ATT variance adjustment can have either
  sign (`ref:abadie2016`). Re-fitting the score in each draw is necessary but does not
  repair the matching problem. **The P4 interval is descriptive, not a confidence
  interval.** Registered rules read only the point gap, so no adjudication depends on it.
- *IPW / AIPW (P2, P3, P5).* These are smooth, so the bootstrap is the conventional
  choice. Two cautions apply. The support boundary is a sample minimum and maximum, and
  bootstrapping extremes is irregular in general. And with a few huge weights, the
  distribution of draws is dominated by whether each draw contains the heaviest men.
- *What the interval is FOR.* The NSW controls are never resampled, so the interval
  describes $\hat\tau$ with the benchmark held fixed. **It is not an interval for the
  gap.** The gap's noise includes the sampling error of the 260-man control mean. The
  overlap claim "the interval contains $1,794" and the registered rule
  "|gap| ≤ $1,000" are different statements.
- *The clamp.* `analyze.py` passes `min(ci_low, att)` and `max(ci_high, att)`, because
  `kleinlib.eval.evaluate_estimate` refuses an interval that excludes its own point. If a
  printed `ci_low` or `ci_high` *equals* `att_usd`, the clamp was used. That means the
  percentile distribution sat entirely on one side of the point estimate, which is a
  symptom of weight concentration or nonsmoothness. Report it as such.

## 3. Minimal from-scratch implementation plan

The smallest honest version is two least-squares solves, one unpenalised logit, a sort,
and a weighted mean. No causal-inference library is involved. The plan below is the math
skeleton. `lib/lalonde.py` is its realization. It sits outside the mutable surface, and
a cell in `analyze.py` only **chooses** (estimator, specification). The skeleton is not
repeated as code here. Read it next to the library.

```text
pool   = NSW treated (T=1) ∪ comparison men (T=0)          # never the NSW controls
e      = unpenalised_logit(T ~ spec_terms(pool)).predict()  # eq. (2): the score
S      = comparison men with min(e_T) <= e <= max(e_T)      # eq. (3): note g, controls only
w      = e_S / (1 - e_S)                                    # ATT odds weights
ipw    = mean(Y_T) - sum(w*Y_S)/sum(w)                      # eq. (3)
beta   = lstsq([1, X_noteA(S)], Y_S)                        # outcome model on S
aipw   = mean(Y_T - mu0(X_T)) - sum(w*(Y_S - mu0(X_S)))/sum(w)   # eq. (4)
match  = mean(Y_T - Y_S[nearest_by_score(e_T, e_S)])        # eq. (5), with replacement
bench  = mean(Y_T) - mean(Y_NSWcontrols)                    # eq. (1)
gap    = estimate - bench;  share = max weight / total weight
draws  = repeat B: resample T and comparison separately, REFIT the logit, re-estimate
```

| `lib/lalonde.py` | Realizes | What an implementer must get right |
|---|---|---|
| `features` | the derived terms: age², educ², re74², re75², u74, u75, u74·black | `u74`/`u75` are *zero-earnings* flags (`re7x == 0`). This is the files' only proxy for Dehejia-Wahba's "unemployed in 197x". All terms are pre-programme. |
| `PROPENSITY["dw_psid"]` | Table 3 note c, the PSID-1 logit (13 terms) | Matches note c term for term (checked against `ref:dehejia1998nber`). On CPS-1 (P7) this PSID spec is deliberately kept. Dehejia-Wahba used a different CPS logit (note e: adds u74, u75, educ·RE74, age³). |
| `PROPENSITY["no_re74"]` | the P5 sensitivity | **Not exactly Dehejia-Wahba's Table 5 Spec 7.** Spec 7 is note c with RE74 removed. This spec removes re74, re74² and u74·black, **and adds u75**. Compare P5 with Spec 7 as an approximation. |
| `propensity` | eq. (2) | `penalty=None` is load-bearing. sklearn's default L2 penalty (C = 1) would shrink the logit and change every score. Standardising the columns does not change an unpenalised logit's fitted probabilities. The score is fitted on treated ∪ the lane's comparison men only. |
| `att(..., "ipw")` | eq. (3) | The trim is on comparison men only. Weights are self-normalised (`np.average`). Clipping $\hat e$ to $[10^{-12}, 1-10^{-12}]$ prevents division by zero but does nothing about large weights. |
| `att(..., "aipw")` | eq. (4) | $\hat\mu_0$ is fitted **unweighted** on $S$ with note a's covariates (no `married`), then predicted for the treated. The residual correction uses the same odds weights as IPW. |
| `att(..., "match")` | eq. (5) | Uses `searchsorted` over the sorted scores in $S$. Ties go to the lower score. Matching is with replacement. Matching happens AFTER the note-g trim. Dehejia-Wahba describe matching to the closest comparison unit and then discarding unmatched ones, so a comparison man just above the top treated score is unavailable here. That is a small, disclosed difference. |
| `bootstrap` | the interval | Treated and comparison men are resampled separately. The score is re-fitted in each draw. The seed is fixed (`BOOTSTRAP_SEED`). NSW controls are held fixed. See §2 for what the interval means. |
| `ols_treat`, `contrast` | Table 3 columns (1)-(2) | Classical homoskedastic OLS standard errors. Column (2) uses `ADJUSTMENT` = Table 3 note a. The §4 expectation for P1/P6 explains why this list may not reproduce the comparison-group rows. |
| `write_table` | pinned `tables/*.tsv` | Deterministic (`%.6f`, LF). Not written under `KLEIN_SMOKE=1`. |

**kleinlib helpers the cells lean on.**

- `kleinlib.data.load_partition`: the contract's predefined lanes. Train is the NSW
  experiment, development is PSID-1, test is CPS-1 (sealed). The notary chooses the lane.
  A cell never does.
- `kleinlib.eval.evaluate_estimate` (att track): prints the estimate, `ci_low` and
  `ci_high`, and the `extra=` keys (`att_gap_usd`, `experimental_att`,
  `n_controls_used`, `max_weight_share`). It refuses non-finite values and intervals
  that exclude the point.
- `kleinlib.eval.evaluate_table` (reproduction track): prints the count of targets
  missed and pins the target-by-target table.
- `kleinlib.torch_loop` and `kleinlib.encoders` are **not used**, by decision. There is
  no neural network and there are no categorical encodings, because every covariate is
  numeric or binary. Prediction-level checks for near-constant output do not apply to a
  scalar estimate. Their analogue here is the pair `max_weight_share` /
  `n_controls_used`.

**Cell map (what `analyze.py:CELL` is set to per registered prediction).**

| Prediction | Track | Lane | `estimator` | `spec` |
|---|---|---|---|---|
| P1 | reproduction | development (PSID-1) | — | — |
| P2 | att | development | `ipw` | `dw_psid` |
| P3 | att | development | `aipw` | `dw_psid` |
| P4 | att | development | `match` | `dw_psid` |
| P5 | att | development | `ipw` | `no_re74` |
| P6 | reproduction | sealed CPS-1 | — | — |
| P7 | att | sealed CPS-1 | the P2-P4 cell with smallest \|gap\| (ties: IPW < matching < AIPW) | `dw_psid` |

## 4. When it pays / when it doesn't

The profile's doctrine sets the rules: name the estimand before the estimator; report
the observational contrast beside the naive comparison and the experimental benchmark;
treat overlap diagnostics and specification sensitivity as evidence, not as an
appendix (`references/profiles/data-science.md` §3). LaLonde (`ref:lalonde1986`) is the
reason the naive and regression rows exist. Dehejia-Wahba (`ref:dehejia1999`) is the
reason the propensity rows are expected to do better.

| Regime | Comparison pool / size | Pre-programme signal | Verdict | Evidence |
|---|---|---|---|---|
| Randomised sample (NSW experiment) | 185 vs 260 | not needed | **pays trivially**: a difference in means is the answer; propensity methods add nothing | Table 3: $1,794 (s.e. 633) |
| Naive contrast, poor overlap (PSID-1, no adjustment) | 2,490, mostly unlike the trainees | ignored | **fails by about the effect's whole size, with the wrong sign** | Table 3 (1): −$15,205 |
| Regression on the full pool | 2,490 | linear in 2 years of earnings | **fails by about $1,000**: it extrapolates from men unlike the trainees | Table 3 (2): $731 |
| Propensity methods, 2 years of earnings, thin overlap at the top (PSID-1) | ~1,100 kept after note g; 7 men above score 0.8 (both per DW) | strong (RE74 + RE75, the earnings dip) | **contested**: estimator- and specification-dependent; agreement with the benchmark is plausible but rests on a few men | DW: stratification $1,608 (s.e. 1,571), matching $1,691 (s.e. 2,209); Imbens-Xu full LDW-PSID: $4 to $2,420 across ten modern estimators, which "fail to recover the ATT" there (`ref:imbens2025`); Smith-Todd sensitivity (`ref:smith2005`) |
| Same, with one year of earnings (no RE74) | PSID-1 | weaker | **weighting-type estimators fail; matching may not** | DW Table 5 B, Spec 7: stratification −$869 / −$1,023, matching $1,727 / $1,340 |
| Propensity methods, large pool with better overlap (CPS-1) | 15,992; ~3,400-3,900 kept after the trim (under DW's own CPS logit) | strong | **pays in point estimates, but that does not validate it**: estimates land near the benchmark while placebo tests reject unconfoundedness | DW: $1,713 / $1,582; Imbens 2015 on CPS (`ref:imbens2015`); Imbens-Xu LDW-CPS: all positive, NN matching closest, placebo fails (`ref:imbens2025`) |
| Both nuisance models a little wrong, a few large weights | any | any | **DR is no rescue**: AIPW can do worse than plain regression | `ref:kang2007` |
| Small treated group (N₁ = 185) with heavy-tailed earnings | — | — | **every estimate is noisy**: published propensity s.e. on PSID-1 range from $809 to $2,209, so a ±$1,000 band reaches about 0.45 to 1.24 s.e. on each side | DW Table 3 (4)-(8) |

**Verdict for this study's regime.** PSID-1 is the hard lane, where the literature
disagrees with itself. The trainees are mostly young, Black, unmarried and without a degree,
with low earnings in 1974-75 (means of $2,096 and $1,532). The PSID-1 men average about $19,000 in each of those
years (Table 1). Note g discards the clearly irrelevant men, but it cannot add men where
the trainees are. Expect estimates that depend on the estimator, weights concentrated
on a handful of men, and gaps whose sign leans negative: the residual comparison men
earn too much. CPS-1 is the easy lane, but "easy" means "agrees with the benchmark", not
"the assumption holds". Imbens 2015 and Imbens-Xu both find failed placebo tests there.
A P7 that holds is therefore **not** evidence that unconfoundedness holds. A
`re75`-as-outcome placebo cell would be the next test (§⑦ material). It is not
registered in this study.

### The card's expectations for each registered prediction

These are expectations, not adjudications. The notary adjudicates P1-P7 by their
registered rules. The probabilities are this card's priors. SYNTHESIZE compares them
with the outcomes and with the CONSULT priors in `study.yaml` (RQ1-RQ5).

| Pred. | Expectation | P(holds) | Why |
|---|---|---|---|
| P1 (anchor, context) | **likely refuted, with `targets_outside_tolerance` = 2**: `psid1_adjusted` and `psid1_adjusted_se`, reproduced near **218** and **866** instead of 731 and 886 | 0.25 | Reading of the published tables: Table 3 column (2) does not look like one regression. Its NSW row (1,672 / 638) equals Table 2 Panel C column (4), whose covariates (RE75 + age, age², schooling, dropout, race, RE74) are note a's list, if "race" means black and hispanic. Its PSID-1 row (731 / 886) and CPS-1 row (972 / 550), and every other comparison row, equal Table 2 Panel C column (5), "controls for all pre-treatment covariates" (`ref:dehejia1998nber`). For PSID-1, column (4) is 218 / 866. Table 5 column (2) prints the same 218 / 866 next to NSW 1,672 / 638. `ADJUSTMENT` = note a, so the reproduction should hit the NSW row and miss the comparison rows. The unadjusted values and counts should all reproduce: Table 3 consistently prints 1 below Table 2 where they differ (1,154 vs 1,155; 1,069 vs 1,070), which looks like flooring, and ±1 covers flooring. This was not visible at CONSULT: scouting ledger S3 transcribed Table 3 only. |
| P2 IPW, PSID-1 | **about even, leaning refuted**; if it misses, the gap is negative | 0.45 | IPW is the continuous relative of Dehejia-Wahba's stratification ($1,608, a gap of −$186, with the same score). But odds weights put the 98 trainees above 0.8 onto about 7 men, each weighted ≥ 4, and plausibly one weighted 20 or more. The point estimate then depends on those few men's 1978 earnings. Stratification's own s.e. (1,571) exceeds the $1,000 band. |
| P3 AIPW, PSID-1 | **about even** | 0.50 | The outcome model is fitted on the trimmed (more similar) men, so it extrapolates less than the full-pool regression ($731). The weighted residual correction inherits IPW's concentrated weights, though. Expected to move IPW by the outcome slope times the leftover imbalance (prior M4). Imbens-Xu's AIPW-GRF was the closest estimator on full LDW-PSID, but with flexible nuisance models, not this linear one. |
| P4 1-NN matching, PSID-1 | **leaning holds** | 0.60 | This cell re-implements Dehejia-Wahba column (7) on the same files with the same logit: $1,691, a gap of about −$103. An unpenalised logit's estimate is unique (absent separation), so the scores should reproduce. Risks: 1-NN on a few reused men is a high-variance function of the score (DW s.e. 2,209), and the trim-before-match and tie rules can re-route matches. Most likely to be the estimator P7 selects (about 0.45). |
| P5 IPW without RE74 | **leaning holds** (the miss is real), with a **negative** gap | 0.70 | Dehejia-Wahba's no-RE74 PSID-1 weighting-type estimates fell to −$869 and −$1,023 (gaps of about −$2,700), while matching stayed at $1,727 (Table 5 B, Spec 7). Mechanism: without 1974 earnings, the score cannot tell a man in a temporary 1975 dip, who rebounds by 1978, from a persistently low earner. That inflates the counterfactual. Caveat: this spec adds u75, which Spec 7 does not have. |
| P6 CPS-1 reproduction (sealed) | **likely refuted, with 2 misses**: `cps1_adjusted` near **739** (not 972) and `cps1_adjusted_se` near **547** (not 550) | 0.25 | Same reading as P1: Table 2 Panel C column (4) for CPS-1 is 739 / 547, and Table 5 prints 738 / 547. The unadjusted −8,498 / 712 and the count 15,992 should reproduce. If P1 lands as predicted (218 / 866), P6's outcome is nearly determined before the sealed run. If P1 instead reproduces 731, this expectation is wrong for P6 too. |
| P7 selected estimator, CPS-1 (sealed) | **leaning holds** | 0.60 | CPS-1 has more comparison men at every score level ("for most bins there are at least a few", DW §4), so weights are less concentrated. Across four specifications, Dehejia-Wahba's CPS-1 matching estimates are 1,582, 835, 1,103 and 1,402, all within $1,000, one by only $41 (Tables 3, 5). Against: the PSID-1 logit was never balanced on CPS-1. Re-specifying per comparison group is Dehejia-Wahba's own procedure, and Smith-Todd showed the answer moves with the specification. A hold is consistency with the benchmark, not validation (placebo tests fail there, per `ref:imbens2015` and `ref:imbens2025`). |

### Falsifiable priors this card stakes (beyond P1-P7)

Each names a lever, a direction, and a magnitude with units. Each is decided from values
the registered cells already print or pin (`max_weight_share` and `n_controls_used` in
the printed block and `aux_metrics.tsv`; `att_usd` and `att_gap_usd`; the pinned
`tables/*.tsv`). None needs an extra run. SYNTHESIZE records each as held or falsified.

```yaml
# Card priors (method_card.md §4). NOT written to study.yaml: CONSULT hashes study.yaml,
# and this worker was scoped to method_card.md + references.yaml. Mirroring them into
# study.yaml:predictions_to_falsify is the orchestrator's decision (a consult re-record).
card_priors:
  - id: M1
    lever: "odds weights e/(1-e) on PSID-1 with the dw_psid logit (P2 cell)"
    claim: "max_weight_share >= 0.05 — one PSID man carries at least 5% of the odds-weight mass (likely 0.10-0.40)"
  - id: M2
    lever: "1-NN matching with replacement on PSID-1 (P4 cell)"
    claim: "n_controls_used between 40 and 75 distinct PSID men (Dehejia-Wahba Table 4: 56) AND max_weight_share >= 0.05 (some man is the match for >= 10 of 185 trainees)"
  - id: M3
    lever: "note-g common-support trim on PSID-1 with dw_psid (P2/P3 cells)"
    claim: "n_controls_used between 1,000 and 1,300 of 2,490 (DW report 1,070 by Table 3 col. 6 and 1,157 by the Figure 1 caption; their two counts disagree)"
  - id: M4
    lever: "adding the OLS outcome model to the same odds weights (P3 vs P2)"
    claim: "|att_usd(AIPW) - att_usd(IPW)| <= 500 dollars"
  - id: M5
    lever: "residual dissimilarity of PSID-1 comparison men"
    claim: "every P2-P4 gap that falls outside +-1,000 dollars is negative (the counterfactual is too high)"
  - id: M6
    lever: "dropping the 1974-earnings terms (P5 vs P2)"
    claim: "att_usd(P5) <= att_usd(P2) - 1,000 dollars — removing the 1974-earnings terms moves the IPW estimate DOWN by more than 1,000 dollars (DW Spec 1 -> Spec 7 stratification: 1,608 -> -869)"
  - id: M7
    lever: "Table 3 note a's covariate list applied to every row (P1, P6)"
    claim: "reproduction misses are confined to the comparison-group adjusted estimate and its s.e.: P1 misses exactly {psid1_adjusted, psid1_adjusted_se}, P6 exactly {cps1_adjusted, cps1_adjusted_se}; every unadjusted value, NSW value and count reproduces within +-1"
  - id: M8
    lever: "better overlap on CPS-1 (P7 vs the same estimator's PSID-1 cell)"
    claim: "max_weight_share on CPS-1 < the selected estimator's max_weight_share on PSID-1"
```

**What would surprise this card, and what to do with it.** If P2-P4 all land within $100
of the benchmark while M1 and M2 hold, the agreement rests on a few heavily weighted men.
Say so in findings ⑤. It is consistency, not recovery. If M7 fails because P1
reproduces 731 / 886 with note a's list, then the Table 2 / Table 3 reading above is
wrong. That points either to the JASA version (not accessed, see `ref:dehejia1999`) or
to a misreading of Lalonde's column (4) covariates. Record it as a surprise in findings
③.

## 5. Verified references

Every row was checked on 2026-11-03 against its Crossref record (title, venue, volume,
pages, year), plus a landing page (RePEc/IDEAS, Econometric Society, OUP, arXiv, or the
authors' own NBER/IZA working-paper PDF) for the content cited.
`uv run --no-sync klein refs verify --study studies/23-lalonde-causal-replication --record`:
**18 references, 0 failed, recorded 17**. `lalonde1986` has no DOI, so it is URL-only and
checked by a reader. Keys resolve in `references.yaml`.

| Key | Reference | Where | Verified? |
|---|---|---|---|
| `lalonde1986` | LaLonde 1986, Evaluating the Econometric Evaluations of Training Programs with Experimental Data | AER 76(4):604-620; JSTOR 1806062 (no DOI) | ✅ RePEc + JSTOR listing |
| `dehejia1999` | Dehejia & Wahba 1999, Causal Effects in Nonexperimental Studies: Reevaluating the Evaluation of Training Programs | JASA 94(448):1053-1062; doi:10.1080/01621459.1999.10473858 | ✅ Crossref. The article text was not accessed; tables were read in w6586 |
| `dehejia1998nber` | Dehejia & Wahba 1998, NBER WP 6586 (same title, hyphenated) | doi:10.3386/w6586 | ✅ Crossref + PDF read in full |
| `dehejia2002` | Dehejia & Wahba 2002, Propensity Score-Matching Methods for Nonexperimental Causal Studies | ReStat 84(1):151-161; doi:10.1162/003465302317331982 | ✅ |
| `rosenbaum1983` | Rosenbaum & Rubin 1983, The central role of the propensity score in observational studies for causal effects | Biometrika 70(1):41-55; doi:10.1093/biomet/70.1.41 | ✅ |
| `smith2005` | Smith & Todd 2005, Does matching overcome LaLonde's critique of nonexperimental estimators? | J. Econometrics 125(1-2):305-353; doi:10.1016/j.jeconom.2004.04.011 | ✅ |
| `dehejia2005` | Dehejia 2005, Practical propensity score matching: a reply to Smith and Todd | J. Econometrics 125(1-2):355-364; doi:10.1016/j.jeconom.2004.04.012 | ✅ (bibliographic only; no arguments attributed) |
| `abadie2006` | Abadie & Imbens 2006, Large Sample Properties of Matching Estimators for Average Treatment Effects | Econometrica 74(1):235-267; doi:10.1111/j.1468-0262.2006.00655.x | ✅ |
| `abadie2008` | Abadie & Imbens 2008, On the Failure of the Bootstrap for Matching Estimators | Econometrica 76(6):1537-1557; doi:10.3982/ECTA6474 | ✅ |
| `abadie2016` | Abadie & Imbens 2016, Matching on the Estimated Propensity Score | Econometrica 84(2):781-807; doi:10.3982/ECTA11293 | ✅ |
| `imbens2004` | Imbens 2004, Nonparametric Estimation of Average Treatment Effects Under Exogeneity: A Review | ReStat 86(1):4-29; doi:10.1162/003465304323023651 | ✅ |
| `imbens2015` | Imbens 2015, Matching Methods in Practice: Three Examples | JHR 50(2):373-419; doi:10.3368/jhr.50.2.373 | ✅ (+ IZA DP 8049 §6.3 read) |
| `robins1994` | Robins, Rotnitzky & Zhao 1994, Estimation of Regression Coefficients When Some Regressors are not Always Observed | JASA 89(427):846-866; doi:10.1080/01621459.1994.10476818 | ✅ |
| `bang2005` | Bang & Robins 2005, Doubly Robust Estimation in Missing Data and Causal Inference Models | Biometrics 61(4):962-973; doi:10.1111/j.1541-0420.2005.00377.x | ✅ |
| `santanna2020` | Sant'Anna & Zhao 2020, Doubly robust difference-in-differences estimators | J. Econometrics 219(1):101-122; doi:10.1016/j.jeconom.2020.06.003; arXiv:1812.01723 | ✅ |
| `kang2007` | Kang & Schafer 2007, Demystifying Double Robustness | Stat. Sci. 22(4):523-539; doi:10.1214/07-STS227 | ✅ |
| `crump2009` | Crump, Hotz, Imbens & Mitnik 2009, Dealing with limited overlap in estimation of average treatment effects | Biometrika 96(1):187-199; doi:10.1093/biomet/asn055 | ✅ |
| `imbens2025` | Imbens & Xu 2025, Comparing Experimental and Nonexperimental Methods: What Lessons Have We Learned Four Decades after LaLonde (1986)? | JEP 39(4):173-201; doi:10.1257/jep.20251440; arXiv:2406.00827 | ✅ (+ arXiv v3 read) |

No row is unverified.

**Lit-scan and positioning.** The method is not frontier, but its *audit* is a live
literature, so the scan was done anyway.

- **Seminal:** `rosenbaum1983` (the score), `lalonde1986` (the benchmark design and the
  negative result), `dehejia1999` / `dehejia1998nber` (the positive re-analysis).
- **Key follow-ups:** `smith2005` and the reply `dehejia2005` (sample and specification
  sensitivity); `abadie2006` / `abadie2008` / `abadie2016` (what matching's uncertainty
  really is); `robins1994`, `bang2005` and `santanna2020` (doubly robust estimation,
  with `kang2007` as its caution); `crump2009` (trimming chosen by overlap).
- **Resonant applications on these very files:** `imbens2015` and `imbens2025`.

The trend since 1999 runs in a clear direction: overlap first, by design and before any
outcome is looked at; flexible nuisance models inside doubly robust or debiased
estimators; and **validation by placebo outcomes**, because agreement with one benchmark
can be luck.

This study deliberately uses the 1999 toolkit: a hand-specified logit, odds-weighted
IPW, linear AIPW and 1-NN matching. That is the honest instrument for a *replication*,
not a frontier recommendation. What the study can add to the trend is the audit
discipline: registered gaps, pinned weight diagnostics, a sealed second comparison
group, and a disclosed reason, from the published tables themselves, why an "exact"
reproduction may miss.
