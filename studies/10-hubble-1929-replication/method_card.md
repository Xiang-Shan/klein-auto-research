---
type: method-card
domain: "astronomy"
profile: "generic"
status: complete
concepts: [least-squares, regression-dilution, bootstrap, jackknife, distance-modulus, prospective-lock, derived-column]
related: [data_card.md, references.yaml, study.yaml, scouting_ledger.md]
refs_verified: true
triad:
  theory: true      # §2 carries the notation table and five display equations
  papers: true      # every entry of references.yaml was checked against its landing page
  practice: true    # §3 names lib/hubble.py function by function; it exists and prepare.py runs on it
---

# Method card — reproducing a 1929 least-squares constant, and estimating it honestly

> Gate 2 (METHOD). Written BEFORE modeling.
> Protocol: `.claude/skills/klein/references/method-gate-protocol.md`.

## 1. Intuition (for a practitioner)

Written for a scientist or data-literate reader who has **not** read the 1929 paper.

Hubble had 24 galaxies. For each he had two numbers: how fast it recedes (from a
spectrum — cheap, accurate, known to a few km/s) and how far away it is (from a
brightness argument — expensive, model-dependent, wrong by factors). He plotted one
against the other, drew a line through the origin, and reported its slope: about 465
kilometres per second for every million parsecs of distance. That slope is the
Hubble constant. Today's value is about 70. So the paper is "off" by a factor of
almost seven, and the interesting question is not *whether* but **which part** —
the data, the fit, or the distances.

Four ideas carry this study, and none is exotic:

**A line through a cloud of points is not one line.** Least squares of `v` on `r`
minimizes vertical distances and treats `r` as exact; least squares of `r` on `v`,
inverted, treats `v` as exact. When the x-variable is noisy the first is dragged
*toward zero* — the classic **regression dilution** of `ref:frost2000` — so the two
fits bracket the truth. Hubble's distances are far noisier than his velocities, so
the ordinary fit should *under*-state K. That is P5, and it is a measurement, not
a lecture.

**Hubble's own number came from a bigger model than most people remember.** He did
not simply regress `v` on `r`. The Sun is moving, which adds a direction-dependent
term to every observed velocity, so he solved for **four** parameters at once — the
constant K plus the three components of the solar motion — using each nebula's
position on the sky. Reproducing 465 therefore requires *inputs the paper never
printed*. That is the study's most useful discovery and it is registered as P2
before anyone looks.

**Uncertainty on 24 points is not a footnote.** Hubble quoted ±50. A modern reader
wants an interval that was *computed*, so the estimate track resamples the 24
galaxies (`ref:efron1979`) and reports a percentile interval — and then, because a
percentile interval on 24 points is exactly the case where the method is known to be
optimistic (`ref:diciccio1996`), the `simulate` track measures how often that
interval actually covers a known truth. If it under-covers, every interval in the
findings is downgraded to descriptive. That branch is pre-scripted, not decided
afterwards.

**A column computed from the answer cannot check the answer.** Hubble's Table 2 lists
22 more nebulae, and it has a distance column — but he *computed* those distances
from the velocities using his own adopted K ≈ 500. Comparing our K against that
column would be comparing our K against his K wearing a disguise. The DATA gate
proved the circularity by arithmetic and the sealed cell is barred from those
columns. This is the single most transferable lesson in the study: **before using a
column as evidence, ask what it was computed from.**

## 2. Math core

| Symbol | Meaning |
|---|---|
| $r_i$ | distance of object $i$, in Mpc (Table 1's `r_mpc`) |
| $v_i$ | observed radial velocity of object $i$, in km/s (`v_kms`) |
| $K$ | the velocity–distance constant, km/s/Mpc — the estimand |
| $c$ | a free intercept, km/s |
| $\alpha_i,\ \delta_i$ | right ascension and declination of object $i$ |
| $X, Y, Z$ | the three rectangular components of the solar motion, km/s |
| $m_i$ | total apparent magnitude (`m_t`) |
| $M_i$ | absolute magnitude (`M_t`) |
| $\sigma$ | residual standard deviation about the fitted line, km/s |
| $B$ | number of bootstrap resamples |

**(1) The one-parameter fit — the line through the origin.** The relation Hubble
argued for has no intercept: zero distance means zero recession.

$$ \hat K_0 \;=\; \frac{\sum_i r_i v_i}{\sum_i r_i^{2}} $$

**(2) The two-parameter fit.** Freeing the intercept lets the data say whether the
line really passes through the origin; $\hat K_1$ and $\hat c$ solve the normal
equations $(A^{\top}A)\beta = A^{\top}v$ with $A = [\,r \;\; \mathbf{1}\,]$.

$$ (\hat K_1,\ \hat c) \;=\; \arg\min_{K, c} \sum_i \bigl(v_i - K r_i - c\bigr)^{2} $$

**(3) Hubble's actual model — four parameters.** Quoted from the paper itself
(`ref:hubble1929`), in his notation:

$$ r K \;+\; X \cos\alpha \cos\delta \;+\; Y \sin\alpha \cos\delta \;+\; Z \sin\delta \;=\; v $$

Four unknowns $(K, X, Y, Z)$, one equation per object, solved by least squares. The
solar motion it recovers is reported as an apex direction and speed. **This equation
is why P2 is registered with an `inconclusive_if`:** it needs $(\alpha_i, \delta_i)$
for all 24 objects, and the paper prints none. His two published solutions are
$K = 465 \pm 50$ (24 objects individually; apex $A = 286^\circ$, $D = +40^\circ$,
$V_0 = 306$ km/s) and $K = 513 \pm 60$ (nine groups; $A = 269^\circ$,
$D = +33^\circ$, $V_0 = 247$ km/s), with an adopted intermediate $K = 500$.

**(4) The distance modulus.** With $r$ in Mpc,

$$ M_i \;=\; m_i \;-\; 5\log_{10} r_i \;-\; 25 $$

This is the *only* photometric equation in the study, and it is used twice: on
Table 1 against the paper's printed $M_t$ (P9), and inside the sealed Table-2 cell
with $r_i = v_i / \hat K$ (P8). Same function, so the development cell is a genuine
rehearsal of the sealed one.

**(5) The percentile bootstrap interval.** Resample the 24 *pairs* with replacement
$B$ times, refit, and take the empirical quantiles of the $B$ slopes:

$$ \bigl[\,\hat K^{*}_{(\alpha/2)},\ \hat K^{*}_{(1-\alpha/2)}\,\bigr],\qquad \alpha = 0.05 $$

Case resampling (pairs, not residuals) is the honest choice here: the 24 galaxies
are a *sample* of objects, not a designed grid, so what varies between hypothetical
repetitions is which galaxies you got.

## 3. Minimal from-scratch implementation plan

Everything below is numpy on normal equations — no `statsmodels`, no
`scipy.optimize`, no `sklearn.linear_model`. It lives in **`lib/hubble.py`**, which
is stable library code written once and complete before E0001 and is **not** in
`entrypoint.mutable`. Each cell composes these and prints its block, so a
per-experiment diff is always a measurement, never a new method.

| Function | Realizes | Notes |
|---|---|---|
| `ols_through_origin(r, v)` | eq. (1) | `np.dot(r, v) / np.dot(r, r)` |
| `ols_free_intercept(r, v)` | eq. (2) | builds $A$, solves $(A^{\top}A)\beta = A^{\top}v$ with `np.linalg.solve` — the normal equations spelled out, not `lstsq` |
| `inverse_regression_k(r, v)` | §1's second idea | same solver on $r \sim v$, then $1/\text{slope}$ |
| `residual_sd_free_intercept`, `analytic_slope_se`, `probable_error` | $\sigma$, $\mathrm{SE}(\hat K)$, and the 1929 convention $\text{PE} = 0.6745\,\mathrm{SE}$ | lets the study compare its own SE with Hubble's quoted ±50 |
| `bootstrap_k(r, v, n_boot, seed, estimator)` | eq. (5) | one seeded `Generator`; index draws of shape `(B, n)`; refit per draw |
| `paired_bootstrap_k(..., estimators)` | the P5 comparison | **common random numbers**: both estimators see the SAME resample on every draw, so the difference carries no independent noise |
| `percentile_ci(values, level)` | eq. (5) | `np.quantile` at $\alpha/2$, $1-\alpha/2$ |
| `jackknife_k`, `jackknife_se` | `ref:efron1979` | leave-one-out; the influence of each of the 24 objects |
| `absolute_magnitude(m, r)` | eq. (4) | one function, used on both blocks |
| `simulate_velocities`, `coverage_experiment` | the DGP and P6 | analytic and percentile-bootstrap intervals under the declared truth |
| `load_block(name)` | the seal | the single data door — see below |
| `write_table(path, columns, rows)` | every `artifact:` | fixed column order, `%.6f`, LF endings, no index, so a detached-worktree re-run hashes identically |

**The one piece of machinery that is not statistics: `load_block()`.** Because
`data.split.kind` is `none`, `kleinlib.data.contract_split` refuses to realize
partitions and `load_partition` cannot be used. `load_block` therefore
re-implements the same three obligations for a partition that is two files:

1. resolve `KLEIN_EVALUATION_KIND` (set by `klein run-one`), and **raise** if the
   sealed block is requested outside a `--final-test` run;
2. honour `KLEIN_SEALED_DRYRUN=1` by serving the development block and printing
   `sealed_dryrun: 1`, so `klein run-one --final-test --dry-run` rehearses the whole
   path and spends nothing;
3. print `split_fingerprint:` for the block actually served.

It also drops `TABLE2_FORBIDDEN_COLUMNS` from the sealed block, so the exclusion
cannot be forgotten by a cell that is thinking about something else.

**No verifier is declared.** A verifier is required for `optimize` and recommended
for checkpoint-scored studies; here every cell is a closed-form computation with no
search, so there is no searcher for a checker to be independent of. The role a
verifier plays is filled instead by three mechanisms already in the contract: the
E0001 identity anchor (a hard STOP on the bytes), the pinned `artifact:` tables
(hashed into each manifest, so every number has a home a stranger can re-hash), and
`confirmation.require: [sealed, replicate]` on all three tracks (every cited
development cell must re-execute in a detached worktree and reproduce).

## 4. When it pays / when it doesn't

| Regime | Data size | Signal | Verdict |
|---|---|---|---|
| Reproducing a printed constant from the paper's own printed table | any | any | **Pays** — it is the cheapest possible test of whether a result is even *checkable*, and the failures are the informative part |
| Ordinary least squares of `v` on `r` when `r` is the noisy variable | any | any | **Doesn't** — regression dilution biases the slope toward zero (`ref:frost2000`); report the inverse fit beside it or use an errors-in-variables method |
| Percentile bootstrap for a slope | n ≳ 100 | moderate | **Pays** — simple, assumption-light, close to nominal |
| Percentile bootstrap for a slope | **n = 24** | noisy predictor | **Doubtful** — only first-order accurate, so expect under-coverage (`ref:diciccio1996`). Do not assert nominal coverage; **measure it** under a declared DGP, which is what this study's `simulate` track does |
| Jackknife for the influence of individual points | small n | any | **Pays** — with 24 objects, leave-one-out is exhaustive and cheap, and it names *which* galaxies carry the constant |
| Jackknife for a *variance* of a non-smooth statistic | small n | any | **Doesn't** — the jackknife is inconsistent for non-smooth functionals (`ref:efron1979`); here the statistic is a linear-algebra slope, which is smooth |
| A "fresh holdout" bootstrapped from rows already seen | any | any | **Never** — see below |

### Two things this card exists to teach

**(a) Why a derived column can never be confirmation evidence for the quantity it was
derived from.** Table 2 prints a distance column. It looks like exactly what a
replication wants: 22 more galaxies with distances *and* velocities, an independent
check on K. It is not. The DATA gate showed that
`r = (v − v_s)/500` holds to floating-point exactness on 20 of the 21 rows where both
are printed, and misses by one unit in the last printed decimal on the 21st. So the
column is Hubble's adopted $K = 500$ applied to the velocity, and "checking our K
against Table 2's `r_mpc`" would return, up to rounding, the ratio of our K to his —
a tautology dressed as a test. The general rule: **a column is evidence about a
quantity only if it was measured independently of it.** The sealed statistic
therefore uses only `v_kms` and `m_t`, the two columns Table 2 measured directly,
and the contract names both the allowed and the forbidden lists
(`study.yaml:sealed_lock`).

**(b) Why a "fresh bootstrap block" seal was rejected, and what a lock actually is.**
The driving agent read all 22 sealed rows before the contract existed
(`scouting_ledger.md` §0). One tempting repair is to bootstrap a "fresh block" out of
the 46 rows and call *that* the holdout. It is rejected here, before any run,
because **resampling rows an analyst has already seen creates no new information**:
every resample is a function of the same bytes, so the "holdout" is a rearrangement
of the training set with holdout vocabulary attached. What protects a sealed
comparison is not the analyst's ignorance of the rows — which cannot be restored —
but the fact that the *analysis* was fixed before the comparison ran and the
comparison was made once. That is a **prospective analysis lock**:
`study.yaml:sealed_lock` names the statistic, the columns, the source of K and the
tolerance; the CONSULT gate hashed it; `klein run-one --final-test` spends the access
once and `study_state.json` counts it. It is not blindness, and the `generic`
profile bans the word "blind" for exactly this confusion. Say **"locked before"**.

### Falsifiable priors this card commits to

Each is registered in `study.yaml:predictions` with an arithmetic rule; SYNTHESIZE
holds each to account, and `scouting_ledger.md` says in the open which were already
foreseeable.

1. **No two-parameter fit reaches 465 within ±10** (P1). Because 465 came from the
   four-parameter model (eq. 3), not from eq. (1) or (2).
2. **The four-parameter refit cannot be attempted from the paper's own data** (P2,
   via `inconclusive_if`). The card asserts the *reason*: missing $(\alpha_i,
   \delta_i)$, verified absent from the article text (`references.yaml:hubble1929`).
3. **The nine-group solution cannot be reconstructed either** (P3). The paper says
   the groups were formed "according to proximity in direction and in distance" but
   never lists the membership.
4. **The inverse fit returns a larger K than the forward fit, by more than one
   paired bootstrap SE** (P5). Regression dilution, `ref:frost2000`. This is the
   card's most exposed prior: if the two fits agree, the claim that Hubble's
   distances dominate the error budget loses its cheapest support.
5. **The percentile interval under-covers at n = 24** — the card expects coverage in
   0.90–0.94 (`ref:diciccio1996`), and P6 asks only whether it clears 0.90. If P6 is
   refuted, every interval in the findings is downgraded to descriptive.
6. **The 1929-vs-today gap is a distance-SCALE error, not a shape error** (P7).
   `ref:sandage1958` recalibrated the ladder and the constant fell by a factor of
   seven without anyone re-measuring a velocity.
7. **Table 1's printed `M_t` reproduces from eq. (4) to within 0.06 mag** (P9). If it
   does not, the sealed cell's machinery is wrong and the study says so before
   spending the seal.

## 5. Verified references

Every row was checked against the publisher, arXiv or archive landing page on
2026-09-03; full entries with locators and notes are in `references.yaml`.

| Reference | Where | Verified? |
|---|---|---|
| Hubble, E. (1929), *A relation between distance and radial velocity among extra-galactic nebulae* | PNAS 15(3):168–173 · doi:10.1073/pnas.15.3.168 | ✅ (DOI resolves; text read via the APOD transcription that is source (b) of the dataset diff) |
| Lemaître, G. (1927), *Un Univers homogène de masse constante…* | Ann. Soc. Sci. Bruxelles A47:49–59; English republication doi:10.1007/s10714-013-1548-3 | ✅ |
| Sandage, A. R. (1958), *Current Problems in the Extragalactic Distance Scale* | ApJ 127:513–526 · doi:10.1086/146483 | ✅ |
| Planck Collaboration (2020), *Planck 2018 results. VI. Cosmological parameters* | A&A 641:A6 · arXiv:1807.06209 | ✅ |
| Riess, A. G. et al. (2022), *A Comprehensive Measurement of the Local Value of the Hubble Constant…* | ApJL 934(1):L7 · doi:10.3847/2041-8213/ac5c5b | ✅ |
| Efron, B. (1979), *Bootstrap Methods: Another Look at the Jackknife* | Ann. Statist. 7(1):1–26 · doi:10.1214/aos/1176344552 | ✅ |
| DiCiccio, T. J. & Efron, B. (1996), *Bootstrap confidence intervals* | Statist. Sci. 11(3):189–228 · doi:10.1214/ss/1032280214 | ✅ |
| Frost, C. & Thompson, S. G. (2000), *Correcting for regression dilution bias…* | JRSS-A 163(2):173–189 · doi:10.1111/1467-985X.00164 | ✅ |

**Lit-scan note.** None of these methods is frontier — least squares, the bootstrap
and the jackknife are settled — so the scan is deliberately narrow and aimed at the
two places where a careless study would go wrong: the *direction* of the
least-squares bias when the predictor is noisy (`ref:frost2000`), and the
*small-sample accuracy* of the plain percentile interval (`ref:diciccio1996`). The
astronomy references are there to keep the replication honest about what the number
means: `ref:lemaitre1927` shows the same constant derived two years earlier from
overlapping data, and `ref:sandage1958` shows it falling by a factor of seven when
the distance ladder — not the fit — was corrected. `ref:planck2018` and
`ref:riess2022` bracket the modern value; the round 70 this study compares against
sits between them, and their mutual disagreement (the "Hubble tension", ~5.6
km/s/Mpc) is an order of magnitude smaller than the gap under study, which is why
70 is an adequate reference here and would not be for a cosmology paper.
