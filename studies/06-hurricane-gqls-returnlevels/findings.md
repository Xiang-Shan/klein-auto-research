---
type: findings
domain: "insurance"
status: final
concepts:
  [
    quantile-least-squares,
    generalized-least-squares,
    log-location-scale-families,
    breakdown-point,
    return-level,
    heavy-tail-decision-instability,
    plotting-position-convention,
    chi-square-goodness-of-fit,
    parametric-bootstrap,
    reproduction-study,
    small-sample,
  ]
related: [02-rqls-pv-severity, 05-fremtpl2-gap-forensics, ../../knowledge/method_cards/quantile-least-squares.md]
---

# Findings — 06-hurricane-gqls-returnlevels

> SYNTHESIZE output. Claim IDs are stable (`06-hurricane-gqls-returnlevels#C<n>`) and are
> never renumbered. Every delta is stated in the units of its track's metric AND against
> the floor that governs that comparison. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`.
>
> **The floors this study measured** (cite, never re-derive):
>
> | Floor | Value | Governs |
> |---|---|---|
> | numerical (solver-route) | **8.8e-17** | nothing — recording ≈0 IS the finding: every disagreement with the published tables is a MODELING choice, not arithmetic |
> | reporting resolution | **0.005** = `minimum_delta`, reproduction | half the last published digit; what "reproduces" means on this track |
> | quantile-convention spread (k=5 sidecar) | **0.018498** range on the track metric (3.7× resolution) | a SPECIFICATION spread, deliberately NOT folded into `minimum_delta` — constant once a kept candidate fixes the convention |
> | paired log-return-level bootstrap SE | **3.461** (block spread 0.104) | the decision track's stated uncertainty band. Driven almost entirely by the log-Cauchy arm (3.59 alone); its literal 2×SE on the return-level scale exceeds the metric's own range |
> | decision `minimum_delta` | **1.0 pp** | an ORDERING DEVICE on the fixed 30-event sample (data-card WARN 1), never a population claim — kept at the measured floor's resolution rather than quietly shrunk |
>
> Sources: `study.yaml`, `sweeps/noise_floor_repro.sidecar.tsv`,
> `sweeps/noise_floor_decision.py`, `program.md` (adaptive-1 entry).
>
> **Confirmation status.** Both sealed accesses are spent: `reproduction` at **E0010**
> (the full published Table 6.10 grid, 120 parameters never touched adaptively),
> `decision` at **E0011** (the thesis's exact 10× modification, 72.303 → 723.03).
> Per data-card WARN 3, sealing here supplies independent **published targets**, not
> independent **data** — every "confirmed" label below means *implementation fidelity +
> within-sample robustness*, and never out-of-sample generalization.

## ① Research-question verdicts

| Claim | RQ | Track | Verdict | Evidence level | Evidence (exp IDs) | Metric delta + uncertainty |
|---|---|---|---|---|---|---|
| **[C1]** | RQ1 — does a from-scratch gQLS reproduce all 36 parameters of Table 6.9 within the 0.005 reporting resolution? | reproduction | **supported** | **confirmed** (sealed access spent, E0010) | E0003 (KEEP); E0010 (sealed); contrast E0001, E0002 | Adaptive: mean \|Δθ\| = **0.002754** over 36 parameters = **0.55× the resolution**, with **35/36** inside it and all three guardrails passing (max \|Δθ\| 0.018687, max \|ΔW\| 0.005007, max \|Δp\| 0.004857). The single exception is the μ̂ of the (0.10,0.90) log-Gumbel cell — see ③.2: our 22.3587 sits **0.0013** from Table 6.10's print of the *same* fit (22.36), so all 18 cells reproduce once Table 6.9's own internal inconsistency is resolved against Table 6.10. Sealed: **0.002026** over **120** parameters (5 estimator arms × 6 families × original **and** 10×-modified = 60 cells), **119/120** inside the resolution, max 0.005195. Prerequisite, on ledger: the *convention* must be the thesis's own ch.2 definition `F̂⁻¹(p) = X_(⌈np⌉)` (`inverted_cdf`) — under the contract's registered `hazen` default the same code gives 0.009303 with max 0.031279, breaching the 0.02 guardrail (E0002). |
| **[C2]** | RQ2 — is the thesis's B=1000 parametric bootstrap for `W_out` necessary, or are its published p-values indistinguishable from a χ²_{r−2} reference? | reproduction | **the registered prediction is refuted; a revised, two-sided finding replaces it** | exploratory | E0004 | Two measurements, pulling opposite ways. (i) **The bootstrap is not numerically redundant.** An honest B=1000 parametric bootstrap (seed 20260731, r = 25) departs from the χ²₂₃ reference by mean **0.0814** and max **0.2869** across the 18 cells — far beyond the prediction's 0.02 tolerance. (ii) **Yet 16/18 published p-values sit within 0.005 of the χ² reference** — tighter than a B=1000 bootstrap's own Monte-Carlo standard error (≈0.016 near p = 0.5) can be. The remaining **2/18** diverge materially: (0.02,0.98) log-Logistic prints 0.16 against χ² 0.5939 (our bootstrap 0.534), and (0.10,0.90) log-Laplace prints 0.55 against χ² 0.4496 (our bootstrap 0.486). **Wording discipline:** this is an observation about the *reproducibility of the printed numbers*, and nothing more. The published `W_out` **statistics** reproduce essentially exactly (e.g. 20.7905 vs a printed 20.79; 23.1927 vs 23.19), so the fits and the test statistic are reproduced; it is the *route from statistic to p-value* that we cannot reconstruct from the text as prescribed. A reader wishing to re-derive Table 6.9's p-column needs one more sentence of method than §5.2 supplies — see ⑦.5. |
| **[C3]** | RQ3 — does the thesis's 10× contamination move gQLS parameters by less than the reporting resolution while MLE-lognormal σ̂ moves 0.83 → 1.10? | reproduction | **supported** | **confirmed** (sealed access spent, E0010) | E0010 (sealed); E0005 (the original-data arms it is differenced against) | **gQLS/oQLS parameters are unchanged, exactly.** Every starred (contaminated) QLS arm in E0010's sealed grid reproduces its unstarred twin to the printed precision: `o2*`, `o3*` and `g3*` are **byte-identical** to `o2`, `o3`, `g3` (arm mean \|dev\| 0.0019355 / 0.0014666 / 0.0019513 in both columns), and `g2*` differs from `g2` only through the published print (0.0026218 vs 0.0025893). **MLE moves as published:** MLE\*/lognormal reproduces at μ̂ **22.876935** (printed 22.88) and σ̂ **1.097494** (printed 1.10, dev 0.002506) against the clean 22.800182 / 0.833868 — a **+31.6% move in σ̂ from one corrupted record in thirty**. The one over-resolution cell of 120 is `g2*`/log-Gumbel at 0.005195: our unchanged σ̂ = 0.734805 is printed as **0.73** in Table 6.10's original column and **0.74** in its modified column — a last-digit rounding boundary on an estimate that did not move, not a disagreement (③.6). |
| **[C4]** | RQ4 — under leave-top-k-out (k = 1,2,3), a stress the thesis never runs, does gQLS stability degrade where the breakdown point predicts? | decision | **supported on direction and ordering; the predicted *cliff* is not there, for a reason** | exploratory | E0008, E0009; contrast E0006, E0007 | Instability is **monotone decreasing in the breakdown point** at every k: leave-1 **19.02% → 5.66%**, leave-2 **30.66% → 26.96%**, leave-3 **41.33% → 27.58%** as the trim widens from (0.05,0.95) (BP 0.05) to (0.10,0.90) (BP 0.10). On the track metric that is **41.33 → 27.58 = −13.74 pp = 13.7× the 1.0 pp ordering delta**. But the registered "k = 2 breaches (0.05,0.95) and not (0.10,0.90)" does **not** appear as a cliff: crossing 2/30 = 0.067 past BP = 0.05 costs only **+3.70 pp** relative to the wider trim (30.66 vs 26.96). **Mechanism:** `BP = min{a, 1−b}` guarantees an estimate cannot be driven *arbitrarily* by **corruption in place**; deletion is a different stress, because dropping the top k **re-indexes every order statistic**, so the estimator is asked for the same probability levels of a genuinely different sample. The cliff-shaped guarantee shows up on the stress BP actually governs — under 5× inflation of the maximum, both gQLS trims sit at **exactly 0.0%** while MLE moves **+58.06%** (E0006 vs E0008/E0009). |
| **[C5]** | RQ5 — among configurations that PASS the in-sample GoF test (W p ≥ 0.10), which estimator × family gives the most stable 1-in-100 event loss? | decision | **the registered prediction is REFUTED — and the refutation is the study's punchline** | exploratory (the ranking is a development comparison; the *winner's* contamination number is confirmed at E0011) | E0006, E0007, E0008, E0009 | The prediction was that gQLS log-Cauchy — the **best-fitting** family on this data (W p **0.8176**, the highest of six) — would be under ⅓ of MLE-lognormal's instability, i.e. below 19.35. It came in at **62.94**, which is **3.25× the predicted ceiling** and **1.08× MLE-lognormal's own 58.06**: the worst of the four contenders. The refutation has **three parts that must be quoted together**, because any one alone misleads: (i) **perfect parameter robustness** — 0.0% movement under 5× contamination, the trim never reads the corrupted maximum; (ii) **an absurd family-conditional level** — a clean 1-in-100 of **4.08e7 $bn** (≈ $4.1e16, some 5.6e5× the largest event ever recorded), because `tan(0.49π) = 31.82` multiplies σ̂ in the exponent; (iii) **the worst resample instability of the four** — 62.94% under leave-top-1-out, 47.21% at k = 2, 61.32% at k = 3. The metrology agrees before the ranking does: the decision track's paired log-return-level bootstrap SE is 3.461 with **3.59 of it from the log-Cauchy arm alone**, i.e. at n = 30 this family's 1-in-100 **is not estimable to useful precision**. Robust-to-outliers ≠ robust-to-resampling, and the best-**fitting** family here is the least decision-stable. |
| **[C6]** | RQ6 — does robustness at the parameter level transfer to robustness at the decision (return-level) level? | decision | **refined: yes, if and only if the quantile transform is bounded — and the trim is the knob** | **confirmed for the incumbent** (E0011); exploratory for the general statement | E0007 vs E0008/E0009; E0011 (sealed) | The transform is the whole story. At `p = 0.99` the lognormal standard quantile is **2.326**; the log-Cauchy's is **31.82** — a 13.7× amplifier on the same σ̂. Holding the *estimator* fixed (gQLS, trim (0.05,0.95)) and changing only the family from log-Cauchy to lognormal takes instability **62.94 → 41.33 = −21.62 pp = 21.6× the ordering delta** (E0007 → E0008), and widening the trim to (0.10,0.90) takes it to **27.58** (E0009), for a total of **−35.36 pp**. The sealed run closes it: under the thesis's exact 10× modification the incumbent's μ̂/σ̂ and all three return levels are **bit-identical** to the clean fit (22.739331 / 0.868760; 1-in-10 22.8609, 1-in-25 34.3634, 1-in-100 56.6620 $bn), for **0.0%** movement (E0011), against **+99.4%** for MLE-lognormal under the same single corrupted record (55.522 → 110.700 $bn, formed from E0006's clean fit and E0010's sealed MLE\* parameters). Parameter robustness reached the decision because the transform did not undo it. |

**Evidence-level note.** [C1] and [C3] are `confirmed` — the reproduction track's single
sealed access (E0010) was spent on exactly those two questions, against 120 published
parameters that adaptive work never touched. [C6]'s *incumbent* statement is confirmed by
the decision track's single sealed access (E0011); its general "iff bounded transform"
form, and the whole of [C4] and [C5], are development-stress comparisons and stay
exploratory. [C2] is exploratory by construction — it is a statement about published
p-values, not about a frontier. Nothing here is a population claim: n = 30 with one
observation at 2.185× the runner-up, and σ̂ carries a ±25% bootstrap band (data-card
WARN 1).

## ② Predictions to falsify (filled)

The eight levers registered in `study.yaml`, plus the k-sensitivity sub-lever that
`research_plan.md` assigned to adaptive-2 and the ladder amendment moved off-ledger.

| # | Lever | Predicted delta | Observed delta | Verdict | Evidence |
|---|---|---|---|---|---|
| 1 | full 18-cell gQLS grid vs Table 6.9 (RQ1) | mean \|Δθ\| ≤ 0.01 **and** max ≤ 0.02 → KEEP | Under the thesis's own `inverted_cdf`: **0.002754 / 0.018687**, KEEP. Under the contract's registered `hazen` default: **0.009303 / 0.031279** — the mean passes, the max **breaches** 0.02 and the W/p guardrails blow out (1.2855 / 0.15813) | **held under the thesis's convention; falsified under the registered default** | E0003 (KEEP), E0002 (discard) |
| 2 | `W_out` bootstrap vs χ²₂₃ (RQ2) | **all** published p-values within 0.02 of the χ² reference → the B=1000 bootstrap is redundant on this data | 16/18 within **0.005**; 2/18 out by **0.434** and **0.100**. Our own bootstrap vs χ²: mean **0.0814**, max **0.2869** | **falsified** (the "all" fails; and the bootstrap is not numerically redundant either) — replaced by [C2]'s two-sided reading | E0004 |
| 3 | oQLS/MLE arms, original data — the Σ★ falsifier | o2 log-Cauchy σ̂ 0.23 vs g2 0.49 reproduced within 0.005, else Σ★ is mis-specified → **STOP** | o2 **0.229912** (dev 8.84e-05), g2 **0.485055** (dev 0.004945); ratio ours **2.1097** vs published **2.1304**; whole-arm means vs Table 6.10 originals 0.0019 (o2) / 0.0026 (g2) | **held** — the study's hardest specification gate, passed exactly | E0005 |
| 4 | quantile-convention sweep | convention spread **exceeds** the 0.005 reporting resolution → at n = 30 the quantile *definition* is the dominant reproduction uncertainty | Track-metric spread across 5 conventions **0.018498 = 3.7× resolution** (`inverted_cdf` 0.002754 · `hazen` 0.009303 · `normal_unbiased` 0.011024 · `median_unbiased` 0.012036 · `weibull` 0.021252). Per-parameter movement across 6 conventions: max **0.1040 = 20.8× resolution** (lognormal) | **held, overwhelmingly** | `sweeps/noise_floor_repro.sidecar.tsv`; E0001/E0002/E0003; off-ledger sensitivity re-verified at synthesis |
| 5 | MLE-lognormal 1-in-100 under **leave-top-1-out** (RQ5 baseline) | moves **> 40%** | leave-top-1-out alone moves **−25.68%** (55.522 → 41.263 $bn). The >40% level is first reached at leave-top-3 (**−44.56%**) and by 5× contamination (**+58.06%**), so the *run-level* restatement "instability_pct > 40 over the whole stress set" held at **58.06** | **falsified as registered** (leave-1 specifically); held in its ledger restatement over the stress set | E0006 |
| 6 | gQLS log-Cauchy decision stability (RQ5) | instability **< ⅓** of MLE-lognormal's (< 19.35); refutation is the seminar punchline | **62.94** — 3.25× the predicted ceiling, and **1.08×** MLE-lognormal's own 58.06. Worst of the four contenders | **REFUTED — the study's headline** | E0007 (vs E0006) |
| 7 | lighter-tailed GoF-passing families (RQ6) | **materially more stable** 1-in-100 than log-Cauchy despite slightly worse fit → fit quality and decision stability are different axes | gQLS-lognormal (0.05,0.95) **41.33** vs log-Cauchy **62.94** = **−21.62 pp = 21.6× the ordering delta**, at a W p of 0.5153 vs 0.8176 (a worse fit, a much better decision). At the wider trim, **27.58** = −35.36 pp | **held** | E0008, E0009 (vs E0007) |
| 8 | instability vs breakdown point across the three trims (RQ4/RQ6) | **monotone decreasing** in `min{a, 1−b}`, at a GoF cost **< 1× the W floor** | Monotone on both stress axes: primary **58.06 (BP 0) → 41.33 (0.05) → 27.58 (0.10)**; deletion-only **44.56 → 41.33 → 27.58**. GoF cost is **negative** — W p *rose* 0.5153 → 0.7310 as the trim widened (published p 0.73 at the wide trim), so the wider trim bought stability and a better in-sample fit at once | **held** (and the cost came out the *good* way — see ③.6) | E0006, E0008, E0009 |
| 9 | k-sensitivity sub-lever (`research_plan.md` adaptive-2: "estimates move less than resolution across k, MORE across conventions") | k ∈ {8,10,15,25} moves parameters by **< 0.005**; conventions move them by more | Max parameter movement across k = **0.1223** (log-Laplace) = **24.5× the resolution**; across conventions = **0.1040** = 20.8×. **k moves things MORE than the convention does**, and neither is a nuisance | **REFUTED on both halves** — at n = 30 the grid size *and* the quantile definition are load-bearing specification choices. The thesis pins k = 8 with `inverted_cdf`, and under that pin reproduction is exact | off-ledger (`analysis.sensitivity`, recorded in `program.md`'s adaptive-2 entry; **re-verified at synthesis**, values reproduce exactly) |

**Score: 5 held (3, 4, 7, 8, and lever 1 under the thesis's own convention), 3 refuted
(2, 6, 9), 1 falsified-as-registered-but-held-in-restatement (5), 1 split by convention
(1).** As in study 05, the priors were far better at predicting *what the loop would
decide* than *how much*: every stakeable magnitude prior on the decision track (5, 6) came
out wrong, and the two specification priors pre-verified at the method gate (3, 4) came out
exactly right.

**One scope note, recorded rather than smoothed.** `study.yaml`'s lever 4 names the sweep
set as `hazen/linear/weibull/median_unbiased/normal_unbiased`; the executed k=5 sidecar
substituted **`inverted_cdf` for `linear`**. The substitution is visible in `program.md`'s
adaptive-1 entry and was consequential in the right direction — it is what surfaced the
thesis's own convention and produced the track's only KEEP — and `linear` is covered by the
off-ledger sensitivity table (lever 9). Recorded here because the sweep executed is not
literally the sweep registered.

## ③ Surprises and why

1. **The thesis uses two different quantile conventions in one chapter, and never says
   so.** Table 6.8's descriptive quartiles (q1 = 4.0560, q3 = 12.4340) reproduce **only**
   under Hazen plotting positions — MATLAB's `quantile` default — while Chapter 2's opening
   paragraph *defines* the estimator's empirical quantile as `F̂⁻¹(p) = X_(⌈np⌉)`, which is
   NumPy's `inverted_cdf`. The study registered Hazen as its default because that is what
   the identity gate demanded, and paid for it on the ledger: E0001 passed the 12-quantity
   identity gate at max deviation 3.53e-05 and still **discarded**, on a
   `max_abs_w_deviation` of 0.4940 against a 0.10 guardrail; E0002 then breached the
   parameter guardrail outright at 0.031279. Switching **one configuration line** to
   `inverted_cdf` produced E0003's KEEP at 0.002754. **Mechanism:** at n = 3,000 the nine
   NumPy conventions agree to four decimals; at **n = 30** they disagree in the second —
   exactly the decimal a paper reporting `22.79 / 0.82` is claiming. The descriptive table
   is the tell, because it silently identifies the software that produced it. **The
   generalizable form is [C7].**

2. **The reproduction localized a typo in the published table — and proved it was a typo.**
   The single parameter of 36 outside the resolution is the (0.10,0.90) log-Gumbel μ̂:
   Table 6.9 prints **22.34**, our fit gives **22.3587** (deviation 0.018687). The
   discriminating evidence is internal to the thesis: **Table 6.10's `g3` column prints
   22.36 for the same fit**, which is 0.0013 from ours. So the reproduction does not
   disagree with the thesis — it disagrees with *one printing* of it and agrees with the
   other. **Why this is worth stating:** a replicator without a max-deviation guardrail
   would have averaged this cell away (it moves the mean by 0.0005, one tenth of the
   resolution) and never seen it. The guardrail that "stops one broken cell hiding behind a
   good average" earned its keep on a cell that turned out not to be ours.

3. **The published p-values are *too close* to a χ² reference to have come from the
   prescribed bootstrap.** 16 of 18 sit within 0.005 of χ²₂₃ evaluated at the published
   `W_out`; a B=1000 parametric bootstrap has a Monte-Carlo standard error near 0.016 at
   p ≈ 0.5, and our own honest bootstrap wanders from χ² by mean 0.0814 (E0004). Agreement
   that tight is not something a bootstrap *can* produce. **Mechanism (a hypothesis about
   the printed numbers, not a claim about the work):** the most economical explanation is
   that the p-column was computed from the χ² reference while §5.2 describes the bootstrap
   as the intended route — and the two remaining cells (0.434 and 0.100 away) are consistent
   with ordinary transcription noise rather than with a third method. The `W_out`
   **statistics** themselves reproduce to ≤0.005 across all 18 cells, so nothing about the
   fits or the test is in question. This is a reproducibility observation about printed
   numbers; ⑦.5 turns it into a one-line question for the author rather than a correction.

4. **The best-fitting family is perfectly contamination-robust and catastrophically
   resample-unstable at the same time.** gQLS log-Cauchy moves **0.0%** when the largest
   loss is inflated 5× (or 10×) — its parameters genuinely do not see the corrupted point —
   and **62.94%** when that point is deleted (E0007). **Mechanism:** the two stresses act
   through different channels. Inflation changes a value the trimmed grid never reads, so
   nothing propagates. Deletion changes *which order statistics the fixed probability levels
   land on*, so σ̂ moves a little — and then `tan(0.49π) = 31.82` sits in the exponent and
   turns "a little" into a factor: a 0.04 move in σ̂ multiplies the return level by ~3.6.
   The metrology saw this before the ranking did (the paired log-return-level SE is 3.461,
   of which 3.59 is this arm alone), which is why the floor block calls RQ5 "metrology
   arriving first". The practical form: **a bounded influence function protects the
   parameters; only a bounded quantile transform protects the decision.**

5. **k — the number of quantile levels — moves the estimates more than the convention does,
   and both are ~20× the reporting resolution.** The registered expectation was that k is a
   nuisance (< 0.005) and the convention is the story. Measured: max parameter movement
   **0.1223** across k ∈ {8,10,15,25} versus **0.1040** across six conventions.
   **Mechanism:** at n = 30, asking for k = 25 distinct quantile levels on `(0.05,0.95)`
   requests more resolution than 30 order statistics contain — levels collapse onto repeated
   order statistics and the design matrix starts describing ties rather than the
   distribution. (The measurement is honest about this: it reports the k ≤ 15 restriction
   separately, and it is the same **0.1223**, so the effect is not a k = 25 artefact.) The
   consequence for practice is [C7]: a gQLS specification is `(family, a, b, k, quantile
   convention)`, and three of those five are usually left implicit.

6. **Widening the trim made the in-sample fit *better*, not worse — and one "over-resolution"
   sealed cell turned out to be a rounding boundary.** Prediction 8 budgeted a GoF *cost*
   for the wider trim; instead W p rose from **0.5153** at (0.05,0.95) to **0.7310** at
   (0.10,0.90) (E0008 → E0009, matching the published 0.73). **Mechanism:** `W` is scored
   only on the estimation grid, so a wider trim scores a *wider* interval — the very
   structural flaw §5.3's universal `W_out` grid exists to fix — and the extreme levels a
   narrow trim reaches are precisely where a 30-point sample is noisiest. Separately, the
   sealed grid's worst cell (`g2*`/log-Gumbel, 0.005195) is an artefact of the *printing*,
   not the fit: our σ̂ = 0.734805 does not move under contamination, and Table 6.10 prints
   that same unchanged estimate as **0.73** in one column and **0.74** in the next. Two
   different reproduction "failures", both resolved by looking at what was typeset.

   A pleasing confirmation in the same grid: **Pareto I's contaminated σ̂ moves by exactly
   `log(10)/30 = 0.076753`** (1.258900 → 1.335653, E0010), with μ̂ = 21.541282 unchanged
   because its MLE is the boundary estimator `min(x)`. That is robustness by accident of
   parametrization — the method card predicted the number before the sealed run produced it.

## ④ Practical advice

1. **[C7]** **Pin the quantile convention AND k in any filing, paper, or model document
   whose parameters come from a quantile-based fit — and reproduce the descriptive table
   first to find out which convention your source used.** A gQLS specification is five
   things — `(family, a, b, k, quantile convention)` — and the last two are usually left to
   a library default. At n = 30 the convention alone moves a fitted parameter by up to
   **0.1040** and k by up to **0.1223**, i.e. **20.8× and 24.5× the 0.005 reporting
   resolution**, and swapping `hazen` for `inverted_cdf` is the whole difference between a
   discard at 0.009303 with a breached guardrail and a keep at 0.002754. If you must
   reproduce someone else's numbers, fit their *descriptive* table first: Table 6.8's
   quartiles identified MATLAB's Hazen default and Chapter 2's own definition identified
   `inverted_cdf` for the estimators — two different answers that only a reproduction
   attempt could have separated (evidence: E0001, E0002, E0003,
   `sweeps/noise_floor_repro.sidecar.tsv`, ② lever 9).

2. **[C8]** **Price a moment-free fit through quantiles only — and make the code refuse the
   rest.** log-Cauchy fits this data best of the six families (W p 0.8176) and has **no
   finite mean**: `mean_loss()` and `cte()` raise `NotImplementedError` by design, because a
   numerical CTE would return a large float that is an artefact of where the quadrature was
   truncated and would look exactly like an estimate. An actuary who follows the
   goodness-of-fit test into a TVaR-loaded premium gets a confident number with no meaning.
   The refusal is the control: cheap to write, it fires at the moment of misuse, and it
   converts a silent pricing error into a stack trace. Note the corollary — a moment-based
   robust estimator (MTM, MWM, Winsorized moments) has *nothing to trim* on a family with no
   moments, which is precisely the gap the quantile grid fills (evidence: E0007
   `moment_note`; method card §3).

3. **[C9]** **Treat the trim as the robustness knob, price it explicitly, and buy it before
   you need it — here it cost nothing at all.** Moving from (0.05,0.95) to (0.10,0.90) cut
   1-in-100 instability from **41.33 to 27.58** (−13.74 pp = 13.7× the ordering delta) and
   *raised* the in-sample GoF from W p 0.5153 to **0.7310**. The knob has a directly readable
   meaning: `BP = min{a, 1−b}` is *the number of corrupted records you are buying protection
   against* — 5% of 30 events is 1.5, so one bad record is tolerated and two are not, while
   10% tolerates three. Because the breakdown point is a **guarantee with a cliff, not a
   slope**, widen the trim while the sample is still clean; past the cliff there is no
   partial credit. And check the cost on *your* data rather than assuming it: the classical
   efficiency argument says a wider trim must cost fit, and on this sample it did not
   (evidence: E0008, E0009; ② lever 8).

4. **[C10]** **State family-conditionality next to every return level, and anchor it to the
   empirical support.** With n = 30 the largest observation sits at plotting position
   p = 0.9667 ≈ 1-in-30, so **every** 1-in-100 in this study is parametric extrapolation.
   The numbers make the point better than the caveat does: on the same data and the same
   estimator, the 1-in-100 is **53.04 $bn** (gQLS-lognormal, 0.05/0.95), **56.66 $bn**
   (gQLS-lognormal, 0.10/0.90), **55.52 $bn** (MLE-lognormal) — and **4.08e7 $bn** (gQLS
   log-Cauchy). All four fits pass the in-sample GoF test; three sit *below* the largest
   event actually observed ($72.303bn) and one sits five orders of magnitude above any loss
   in recorded history. Report the GoF-passing families **side by side with the empirical
   1-in-30 anchor**, never a single number as "the" answer (evidence: E0006, E0007, E0008,
   E0009; data-card WARN 2).

5. **[C11]** **When your "held-out" evidence is published targets rather than held-out data,
   say exactly that in the claim, not in a footnote.** This study's sealed evidence is
   unusually strong on one axis — 120 third-party parameters fixed in print before the study
   existed, unmovable by anything the study does, with adaptive work contractually confined
   to Table 6.9 — and structurally blind on another: **the same 30 observations underlie both
   evaluations**, so sampling error is fully common-mode and the sealed test cannot detect
   it. The permitted claim is therefore *"our implementation reproduces their published
   numbers on their sample, and the estimator is robust within that sample"* —
   implementation fidelity plus within-sample robustness. The forbidden claim is any
   statement about generalization to another hurricane sample, another period, or predictive
   accuracy. Carry the wording verbatim into slides and verdict cards, where it is most
   likely to erode (evidence: E0010, E0011; data-card WARN 3, standing rule (e)).

## ⑤ Business / actuarial value implications

**The two-panel story: what one corrupted record is worth.** Take a single record out of
thirty — the 1926 Great Miami hurricane at $72.303bn — and multiply it by ten, the way a
decimal-point slip or a double-counted recovery does. On the incumbent method of practice,
maximum likelihood on a lognormal, the fitted 1-in-100 event loss goes from **$55.5bn to
$110.7bn, +99.4%** (E0006 clean fit; E0010's sealed MLE\* parameters). On the study's gQLS
incumbent — a lognormal fitted by generalized quantile least squares at trim (0.10,0.90) —
the same corruption produces **$56.7bn → $56.7bn, 0.0%**, bit-identical in μ̂, σ̂ and all
three return levels (E0011, sealed). That is the value proposition stated as one number a
committee can act on: **the difference between the two methods is a doubling of the
modelled 100-year loss, caused by one bad row that no data-quality process caught.** For a
catastrophe layer, a capital charge, or a solvency return, a 100% error in the 1-in-100 is
not a modelling nuance; it is the difference between two different companies. Quantile
trimming is, in this specific and quantifiable sense, **data-quality insurance**: it costs a
defined amount of statistical efficiency and it pays out exactly when a record is wrong.

**Both figures are within-sample orderings, and the honest version is more useful than the
inflated one.** The +99.4% and the 0.0% are properties of *this* fixed 30-event sample under
*this* stress (data-card WARN 1); σ̂ carries a ±25% bootstrap band at n = 30, and the
decision track's `minimum_delta` of 1.0 pp is an ordering device, not a confidence
statement. What transfers is not "gQLS gives you a 0.0% number", it is the **structure**: an
estimator that never reads the corrupted observation cannot be moved by it, and an estimator
that reads every observation can be moved arbitrarily. The first statement is a theorem
(bounded influence function, positive breakdown point); the second is arithmetic. The sizing
of the effect on your own book is a measurement you must repeat.

**The counter-lesson is worth as much as the headline, and costs more to learn the hard
way.** The best-fitting family by the thesis's own goodness-of-fit test produces a 1-in-100
of **$4.08e7bn** — roughly 400× world GDP — while passing every diagnostic an analyst would
normally run and while being *perfectly* robust at the parameter level (E0007). An analyst
who selects a severity family by GoF p-value and then quotes its 1-in-100 has done
everything the textbook asks and produced a number with no economic content. Three
guardrails, all cheap, would have caught it: refuse moments on moment-free families ([C8]);
print the return level next to the empirical maximum ([C10]); and treat any extrapolation
more than an order of magnitude beyond observed support as a modelling failure rather than a
tail estimate. The GoF test answers "does this shape fit the middle of my data"; it does not
answer "is the tail I am about to sell defensible".

**Adoption economics — what the study itself cost.** A method published in an August 2024
dissertation was implemented from scratch (six families, two estimators, two goodness-of-fit
tests, a parametric bootstrap), validated against **156 published parameters** (36 adaptive +
120 sealed) to a mean deviation of ~0.002, stressed beyond anything the source publishes,
carried into the decision unit the source explicitly names as future work, and closed with a
full audit trail — inside **one session and 11 experiments**, with total measured compute of
**7.7 seconds** across all four phases (`results_summary.md` phase telemetry; every fit is a
2-parameter least-squares solve on 8 points). The transferable claim is not that gQLS is
cheap to run — it is that **the evaluation of a frontier method is now cheap enough that "we
don't know if it works on our data" has stopped being a reason to defer it**. The binding
constraint on adopting a 2024 estimator is not compute and is not implementation effort; it
is whether anyone writes down, in advance, what would have to be true for the method to be
rejected. That is what the eight registered predictions and the two sealed accesses bought,
and three of the eight came back refuted — including the one the study existed to ask.

## ⑥ Literature tie-back

- **Adjieteh (2024), *Robust-Efficient Fitting of Loss Models via Quantile Least Squares*
  (PhD, UW–Milwaukee; advisor Brazauskas) — §6.2.2, Tables 6.8/6.9/6.10, Fig. 6.8.** The
  reproduction is essentially exact under the thesis's own stated convention: 35/36 adaptive
  parameters and 119/120 sealed parameters inside the reporting resolution, W statistics and
  p-values to ≤0.005, and the Σ★ falsifier (o2 vs g2 log-Cauchy σ̂, 0.23 vs 0.49) passing at
  8.8e-05 ([C1], [C3]). Three findings sit *alongside* the thesis rather than against it: the
  two-conventions-in-one-chapter subtlety (③.1), the Table 6.9 log-Gumbel μ̂ typo that Table
  6.10 itself corrects (③.2), and the `W_out` p-value route we could not reconstruct as
  prescribed ([C2]). The thesis's §7.2 names extending the estimators to risk measures as
  open, and §6.2.2 stops at parameters and p-values — **RQ4, RQ5 and RQ6 are therefore
  genuinely new, and RQ5 came back refuted**: on this data the method's parameter-level
  headline does *not* survive contact with the 1-in-100 for the family the thesis's own GoF
  test ranks first ([C5]).
- **Adjieteh & Brazauskas (2025), *Statistics and Computing* 35:106 (DOI
  10.1007/s11222-025-10626-6).** The peer-reviewed form of the estimator. Its ARE table is
  why the "generalized" matters, and it was corroborated in the direction it predicts: the
  oQLS/gQLS split on log-Cauchy is a factor of **2.11** in σ̂ here (0.2299 vs 0.4851, E0005)
  against the published 2.13 — the weighting, not the trimming, is the large effect for a
  heavy standard member.
- **The Brazauskas robust-loss-models line — Brazauskas & Serfling (2000, *Extremes*
  3(3):231–249), MTM (Brazauskas–Jones–Zitikis 2009), MWM (Zhao–Brazauskas–Ghorai 2018),
  Poudyal–Zhao–Brazauskas (2024).** These trim or Winsorize **moments**; QLS trims the
  **quantile grid**. This study supplies the sharpest available demonstration of why the
  distinction is structural rather than stylistic: the family that fits best here has **no
  moments at all**, so every moment-based robust estimator in that line is inapplicable to it
  by construction, while gQLS fits it without complaint — and then [C5] shows that fitting it
  is not the same as being able to price it. The right reading is that the two families of
  method fail differently, not that one dominates.
- **Serfling (2002a), *Approximation Theorems of Mathematical Statistics*, Theorem B; and
  Serfling (2002b), *NAAJ* 6(4):95–109.** Theorem B is what makes Σ★ writable in closed form
  before any data is seen, and it is the load-bearing import: reproducing the o2/g2 split *is*
  an empirical check on the Σ★ built from it ([C3], ② lever 3). The bounded sample-quantile
  influence function from the same source is the formal content of "one bad record cannot
  move it far" — and [C5] is the precise statement of what that guarantee does **not** cover,
  because the influence function bounds the *parameter*, not `exp(μ̂ + σ̂ · F★⁻¹(0.99))`.
- **Study 02 (`02-rqls-pv-severity`, archived at tag v1.0.0) — the wind tunnel.** Continuity
  holds and the numbers line up in the same shape. On synthetic known-truth severity, study 02
  measured a **1.083× clean-data robustness cost** and, at 10% contamination, a naive-MLE
  premium error of **352%** against **50%** for the trimmed estimator (`research_plan.md`
  lineage; `knowledge/method_cards/quantile-least-squares.md`). On real data with a real
  published contamination, this study finds **+99.4% vs 0.0%** on the 1-in-100 — the same
  qualitative gap, on a decision unit, against third-party published targets rather than a
  generator. **One inherited verdict is corrected, as the method card flagged in advance:**
  study 02 concluded "skip the diagonal plug-in GLS — it added noise". Here Σ★ is exact, full
  and parameter-free rather than a plug-in, and the GLS weighting is the single largest effect
  in the method (ARE 0.232 → 0.995 for the Cauchy member; the 2.11× split reproduced at
  E0005). The correction belongs in the knowledge card at promotion: *plug-in diagonal GLS ≠
  closed-form full-covariance GLS, and the ARE table says exactly where the difference lives.*
- **Study 05 (`05-fremtpl2-gap-forensics`) — protocol continuity.** Two disciplines carried
  over and paid: **measure the floor that governs your comparison** (its [C11] → the five
  floors tabled at the head of this document, including a floor whose *pathology* became the
  RQ5 finding), and **report the structure, not the level** (its [C9] → [C10] here). The F2
  framework defect study 05 filed is echoed at ⑦.4; this study avoided it only because
  `program.md` records applying the lesson **at scaffold time**, topping up
  `final_holdout_access` with a generator-shape zero entry before any gate or run.
- **Pielke & Landsea (1998), *Weather and Forecasting* 13(3):621–631 — the data provenance
  trap.** The "1925–95" label on Table 8 is a mislabel: three supplemental pre-1925 storms
  (1900 and 1915 Galveston, 1919 S Texas) are in the top 30, they are 15.5% of total damage,
  and two of them are the #3 and #4 largest events. The published Table 6.8 statistics
  reproduce **only with them included** — which is why R's `extRemes::damage` top-30, a
  genuinely 1925–95 set, does not reproduce the thesis. A replicator who "fixes" the period
  silently breaks the reproduction; `pre1925_flag` identifies the three rows exactly and
  `prepare.py`'s identity gate makes the substitution impossible to miss (data-card issue 5).
- **Priors' scorecard.** The `knowledge/`-sourced prior (study 02's GLS verdict, carried
  through the method card) was **corrected before the loop**, and correctly so. The two
  specification priors pre-verified at the method gate (Σ★ falsifier; convention dominance)
  **held exactly**. The three `uninformed` priors — RQ5's log-Cauchy stability, RQ4's cliff,
  and the k-nuisance assumption — went **0 for 3**. Where a prior came from reading the source
  carefully it was right; where it came from theory applied to an unfamiliar regime it was
  wrong, and in every case the mechanism (transform amplification; deletion vs corruption;
  grid resolution against n) was available in advance and simply not reasoned through.

### Limitations

1. **n = 30, and one observation dominates every tail fit** (data-card WARN 1, verbatim):
   *"max = 72.303 is 2.185× the second-largest (33.094) … Parametric bootstrap at n = 30 puts
   σ̂ = 0.8339 in a 95% interval of [0.617, 1.034] — a ±25% relative sampling band on the
   single parameter that drives the tail."* Consequently the declared 1.0 pp `minimum_delta`
   is *"far smaller than the ±25% band on the estimand — treat it as an ordering device
   between estimators on a fixed sample, never as a claim about the population."* Every
   decision-track number in this document is such an ordering.
2. **The decision functional is out-of-sample by construction** (data-card WARN 2, verbatim):
   *"The largest of 30 sits at plotting position p = 0.9667 ≈ 1-in-30. Every 1-in-100 quantile
   is therefore pure parametric extrapolation … the fitted lognormal 1-in-100 (55.52 bn) is
   below the largest observation actually seen (72.303 bn) — the '100-year loss' is an
   artifact of the assumed family, not a data-supported number."*
3. **The sealed evidence is independent TARGETS, not independent DATA** (data-card WARN 3,
   verbatim): *"the same 30 observations underlie both the adaptive and the sealed
   evaluation … it establishes implementation fidelity + within-sample robustness, never
   out-of-sample generalization. Sampling error is fully common-mode between adaptive and
   sealed evaluation and the sealed test cannot detect it."* A residual soft coupling also
   remains — a specification tuned until it hits Table 6.9 has thereby made much of Table 6.10
   predictable — which the design bounds but does not eliminate.
4. **Stationarity is inherited, not established** (data-card leakage-audit row 2): the 30
   events span 1900–1995 and are treated as exchangeable draws from one severity distribution
   *solely* because of the Pielke-Landsea normalization for inflation, wealth and coastal
   population. Anything that normalization fails to remove — building codes, warning lead
   times, insurance penetration, any trend in storm intensity — is absorbed silently into σ̂
   and therefore into every return level here. The observed r(year, log damage) = −0.42 is
   equally consistent with sampling noise and with over-normalization, and cannot be
   distinguished at n = 30.
5. **The MLE baseline's GoF gate is heuristic.** The decision track's `w_pvalue ≥ 0.10`
   guardrail admitted E0006 on W p = 0.5374 with `w_chi2_calibrated = 0`: the χ²_{k−2}
   calibration of eq. (5.2) is established for gQLS residuals, and `estimators.py` correctly
   flags that it is *not* established for an MLE fit. The MLE arm therefore passed a
   comparable-looking screen rather than a calibrated one. This does not affect [C5]'s
   ordering (log-Cauchy loses on its own calibrated fit), but the MLE row of any comparison
   table should carry the flag.
6. **The k-sensitivity result (② lever 9) is off-ledger.** It is a `program.md`-recorded
   measurement with no run manifest, carrying no experiment-level uncertainty. It was
   re-verified at synthesis and reproduces exactly (0.12227960638 across k; 0.10393799264
   across conventions), but it is descriptive evidence and no ① verdict rests on it alone.
7. **`playbook.md` was never filled.** All four of its tables remain at their scaffolded
   headers, so the pre-clustered discard map the synthesis protocol expects to mine did not
   exist; this synthesis reconstructed the clusters from `program.md`'s decision log and the
   ledgers instead. The record is silent on why, and nothing is inferred — but a future study
   on this ladder should treat the playbook as load-bearing, since the three phase
   acknowledgements all recorded the same (scaffold) hash.
8. **Two GoF-passing families were never carried into the decision track.** log-Logistic and
   log-Laplace pass comfortably (W p 0.5349 and 0.5965 at (0.05,0.95)) and their standard
   quantiles at p = 0.99 are bounded (4.60 and 3.91), so they are plausible middle rungs
   between lognormal (2.33) and log-Cauchy (31.82). The adaptive-3 budget went to the trim
   ladder instead. [C6]'s "iff bounded" is therefore supported by a two-point contrast, not
   by a curve.

## ⑦ What to try next

1. **Full-sample replication on `extRemes::damage` (n = 144) — the highest-information
   follow-up, and the one that converts every claim here from within-sample to
   out-of-sample.** This study's structural limitation is that sealing gave independent
   targets and not independent data (limitation 3). R's `extRemes::damage` carries the
   complete Pielke-Landsea normalized series, not just the top 30 — a genuinely larger sample
   from the same generating process, on which the *same* estimators can be refitted and the
   *same* stresses re-run. **Predictions to falsify:** (a) the gQLS→MLE efficiency gap becomes
   visible at n = 144, so the trim's cost stops being free (② lever 8 came out the *good* way
   at n = 30 and should not at n = 144); (b) the convention and k sensitivities fall by
   roughly √(30/144) ≈ 0.46 in parameter units, testing ③.5's mechanism directly; (c) the
   log-Cauchy 1-in-100 stays economically absurd, because that is a property of the transform
   and not of the sample size. Note the sample is *not* the thesis's — the identity gate will
   and should fail — so this is a new study, not an extension of this ledger.
2. **A GPD / peaks-over-threshold arm on the same data — the comparison an EVT reviewer asks
   for first.** Every fit here is a full-sample log-location-scale law extrapolated to
   p = 0.99; the standard alternative models only exceedances over a threshold with a
   generalized Pareto tail and *estimates* the shape ξ rather than choosing it by family
   selection. **Prediction to falsify:** a GPD tail fitted above the ~1-in-10 threshold gives
   a 1-in-100 within a factor of 2 of the gQLS-lognormal $56.7bn — i.e. the lognormal answer
   is the defensible one and log-Cauchy's is an artefact of forcing one family to describe
   both body and tail. If instead the GPD lands an order of magnitude higher, [C10]
   strengthens sharply: family-conditionality is not a caveat but the dominant term. Pair it
   with the robust-GPD estimators from the same Brazauskas line so the comparison is
   robust-vs-robust rather than robust-vs-MLE.
3. **Frequency × severity: the annual `Rsum` series and a compound model (Katz 2002).** The
   1-in-100 *event* loss is not the 1-in-100 *year* — and the year is what a reinsurance
   programme or a capital model needs. The Pielke-Landsea data supports the annual aggregate
   series that Katz (2002, *J. Applied Meteorology* 41:754–762) models as a compound
   Poisson–lognormal. **Prediction to falsify:** the annual-aggregate 1-in-100 is *less*
   sensitive to the single corrupted record than the per-event 1-in-100, because frequency
   uncertainty (a Poisson count over ~96 years) dominates severity uncertainty at the
   aggregate level — which would make the +99.4% headline an upper bound on what data quality
   costs a real capital number, and would mean [C9]'s trim advice matters most for per-event
   layers.
4. **Framework fix F2 — `load_state` should top up per-track sealed-access maps from the
   contract (echoes `05-fremtpl2-gap-forensics` ⑦.4).** `klein new` scaffolds one track and
   derives `final_holdout_access` keys at scaffold time; a second track added by editing
   `study.yaml` — still the only way to build a two-track study — leaves that map stale and
   the sealed run is refused. Study 05 lost a real experiment slot to it. This study avoided
   it only because a human remembered the lesson and hand-topped the map before Gate 0
   (`program.md`, 2026-07-31), which is a workaround, not a fix. **Do:** have `load_state`
   reconcile the map against the current contract, **or** let `klein new` accept repeated
   `--track`. Cheap, and it is now two studies deep.
5. **Send the author one gentle question about the `W_out` p-value route.** [C2] and ③.3
   should reach the source as a question, not as an erratum: the `W_out` **statistics**
   reproduce to ≤0.005 across all 18 cells, and 16/18 p-values match a χ²₂₃ reference more
   closely than a B=1000 bootstrap's own Monte-Carlo error permits, while §5.2 prescribes the
   bootstrap. The useful message is one sentence — *"could you confirm which reference
   distribution produced the Table 6.9 p-column, so that replicators can reproduce it?"* —
   plus an offer of the two divergent cells ((0.02,0.98) log-Logistic and (0.10,0.90)
   log-Laplace) and the log-Gumbel μ̂ that Table 6.10 already corrects. This is exactly the
   small, citable clarification a reproduction study exists to generate, and the tone is the
   point: the thesis reproduced, in full, at the resolution it reports.
