---
type: verdict-card
domain: "insurance"
status: final
method: "generalized quantile least squares (gQLS) for log-location-scale loss models"
source_paper: "Adjieteh (2024), PhD thesis, UW-Milwaukee — §6.2.2; Adjieteh & Brazauskas (2025), Stat. Comput. 35:106"
study: 06-hurricane-gqls-returnlevels
related: [findings.md, method_card.md, ../../knowledge/method_cards/quantile-least-squares.md]
---

# Verdict card — generalized quantile least squares (gQLS)

> The transferable adopt/reject artifact. Every row cites the claim IDs in
> `findings.md` (`06-hurricane-gqls-returnlevels#C<n>`) that earned it; read that file to
> audit any row. **Scope of the evidence, stated once and binding on every row below:**
> n = 30 normalized US hurricane losses (Pielke-Landsea 1998 Table 8, 1995 USD). The
> sealed evidence is 120 independent PUBLISHED TARGETS, not independent data — these rows
> establish *implementation fidelity plus within-sample robustness*, never out-of-sample
> generalization (**[C11]**).

## The rows

| Dimension | Verdict | Evidence and numbers | Claims |
|---|---|---|---|
| **Reproducibility** | **Excellent — the strongest row on the card**, conditional on pinning the quantile convention | A from-scratch implementation reproduced **35/36** adaptive Table-6.9 parameters and **119/120** sealed Table-6.10 parameters inside the 0.005 reporting resolution (mean \|Δθ\| 0.002754 adaptive, **0.002026 sealed**), with W statistics and p-values to ≤0.005 and the Σ★ falsifier passing at 8.8e-05. Both remaining cells are artefacts of the *printing*, not of the fit: a Table-6.9 log-Gumbel μ̂ typo that Table 6.10 itself corrects (0.0013 away from ours), and a last-digit rounding boundary (0.73 vs 0.74 for one unchanged estimate). **The condition is not optional:** under the wrong quantile convention the same code misses by 0.031279 and breaches the guardrail. | **[C1]**, **[C3]**, **[C7]** |
| **Implementation cost** | **Low — one focused sitting**, but it is *your* sitting: no library ships this | ~970 lines of numpy/scipy (`estimators.py` 802 + `stress.py` 171) covering six standard members, oQLS + gQLS + MLE, both goodness-of-fit tests and the B=1000 parametric bootstrap, backed by **20/20 tests in 0.64 s**. The mathematical core is ~15 lines (grid → design matrix → known Σ★ → Cholesky-whitened least squares). Two implementation rules are load-bearing rather than stylistic: **never form Σ★⁻¹** (factor and whiten — Σ★'s condition number reaches 2.7e4 for log-Cauchy on the estimation grid), and **log the condition number on every fit**. There is no released R or Python package for gQLS; adoption means owning the code and its tests. | **[C1]**, **[C7]** |
| **Robustness delivered (parameters)** | **Delivered in full, exactly as advertised — this is a theorem, and it held** | Under the thesis's exact 10× contamination of the largest of 30 losses, every QLS arm's parameters are **unchanged**: `o2*`, `o3*`, `g3*` byte-identical to their clean twins across all six families, `g2*` differing only in the published print. The same corruption moves MLE-lognormal σ̂ **0.833868 → 1.097494 (+31.6%)**. The guarantee is cliff-shaped and readable: `BP = min{a,1−b}` is the number of corrupted records bought protection against (1 of 30 at (0.05,0.95); 3 of 30 at (0.10,0.90)), and at 5× inflation both trims sit at **exactly 0.0%** against MLE's **+58.06%**. | **[C3]**, **[C4]** |
| **Robustness delivered (decisions)** | **Conditional — delivered if and only if the family's quantile transform is bounded at your target return period.** This is the row the study exists to add | Same estimator, same data, same GoF gate; only the family changes. gQLS-lognormal at (0.10,0.90): 1-in-100 instability **27.58**, and **0.0%** under the sealed 10× modification (bit-identical μ̂, σ̂ and all three return levels) against **+99.4%** for MLE-lognormal (55.522 → 110.700 $bn). gQLS log-**Cauchy** at (0.05,0.95): also 0.0% under contamination — and **62.94** instability under deletion, the worst of four contenders, on a clean 1-in-100 of **4.08e7 $bn**. The mechanism is arithmetic: the standard quantile at p = 0.99 is **2.326** for the lognormal and **31.82** for the log-Cauchy. A bounded influence function protects the *parameters*; only a bounded transform protects the *decision*. | **[C5]**, **[C6]**, **[C10]** |
| **Efficiency cost** | **On this sample: negligible, and inside the sampling noise.** Do not generalize the "free" part | On clean data the three lognormal fits give σ̂ = 0.833868 (MLE), 0.818165 (gQLS 0.05/0.95), 0.868760 (gQLS 0.10/0.90) — an estimator-choice spread of **6.1%**, against a **±25%** bootstrap sampling band on σ̂ at n = 30. Clean 1-in-100s bracket accordingly: 55.52 / 53.04 / 56.66 $bn. The GoF cost of the wider trim came out **negative** (W p 0.5153 → 0.7310), because `W` scores only the estimation grid. External calibration: the thesis's ARE for gQLS is 0.89–1.00 across standard members at k = 25 (0.911 for the normal), and study 02 measured a **1.083× clean-data premium cost** on synthetic severity. **The asymmetry is the decision:** the efficiency cost is inside the noise band; the robustness gain (+99.4% vs 0.0%) is far outside it. | **[C9]**, ② lever 8 |
| **Tooling maturity** | **Research-grade. Specification-complete but under-specified in print; nothing productionized** | The published specification is complete enough to reproduce exactly — once you supply three things the papers leave implicit: the quantile convention (Ch. 2 defines `X_(⌈np⌉)` while the descriptive table is Hazen — two conventions in one chapter), k (the thesis's 8; movement across k ∈ {8,10,15,25} is **0.1223** = 24.5× the reporting resolution), and the reference distribution behind the published `W_out` p-column (the statistics reproduce to ≤0.005; the p-values match a χ²₂₃ reference more tightly than a B=1000 bootstrap can — see **[C2]**). No package, no reference implementation, no CI. Budget for writing the tests that pin your Σ★, because a wrong Σ★ fails silently and only the o2-vs-g2 split catches it. | **[C2]**, **[C7]** |
| **VERDICT** | **ADOPT, scoped** — as a robust *estimator of parameters* for small contaminated heavy-tailed severity samples, and as a decision method only through bounded quantile transforms, with the trim chosen in advance | The method does exactly what it claims at the parameter level, reproduces to publication precision, and costs almost nothing to run (11 experiments, **7.7 s** total compute). It does **not** automatically deliver a stable decision: the family its own goodness-of-fit test ranks first turns perfect parameter robustness into the least stable and least meaningful 1-in-100 on the card. Adopt it with the family fixed on decision-stability grounds, not on GoF grounds, and with the trim treated as a priced knob. | **[C1]**, **[C3]**, **[C5]**, **[C6]**, **[C9]** |

## ADOPT-FOR

1. **Small, contaminated, heavy-tailed severity samples** where a handful of records can be
   wrong and n is too small to average the error away — the regime where "the estimator's
   failure modes are the entire game". One corrupted record in thirty moves MLE σ̂ by 31.6%
   and gQLS by nothing (**[C3]**).
2. **Quantile-based decisions** — VaR, a return level, a layer attachment, a rate at a
   fixed percentile — where the target probability sits inside or close to the fitted trim
   and the transform from σ̂ to the decision is bounded (**[C6]**).
3. **Wide trims, chosen before you need them.** `(0.10, 0.90)` beat `(0.05, 0.95)` on
   1-in-100 instability by **13.7× the ordering delta** *and* fitted better in-sample. The
   breakdown point is a cliff, not a slope: buy the wider trim while the sample is still
   clean (**[C9]**, **[C4]**).
4. **Families with no moments** — log-Cauchy and relatives — which every moment-trimming
   robust estimator (MTM, MWM, Winsorized moments) is structurally unable to fit at all.
   gQLS fits them; price them through quantiles only (**[C8]**).
5. **Reproduction and audit work on published loss models**, where "does our implementation
   match the printed table, to the resolution the table is printed at" is the actual
   question. The two-track design (distance-to-published + a decision unit) transfers
   directly (**[C1]**, **[C2]**).

## DO-NOT-ADOPT-FOR

1. **Moment-based pricing off a moment-free fit.** Never take a mean, a CTE, or a TVaR
   loading from a log-Cauchy (or any no-moment) fit, however well it passes goodness-of-fit.
   The integral diverges; any number returned is an artefact of where the quadrature
   stopped. Make the code raise rather than return (**[C8]**).
2. **Decision claims that reach beyond the fixed sample.** Every instability figure here is
   an ordering device on 30 events with a ±25% bootstrap band on σ̂ and a paired
   log-return-level SE of 3.461. "gQLS gives a 0.0% movement" is a statement about *this*
   sample under *this* stress; the transferable content is the structure, not the number
   (**[C11]**, and the head-of-file floors in `findings.md`).
3. **Families whose quantile transform is unbounded at your target return period.** At
   p = 0.99 the log-Cauchy amplifier is `tan(0.49π) = 31.82`, so a 0.04 wobble in σ̂ moves
   the return level by a factor of ~3.6 and the clean 1-in-100 lands five orders of
   magnitude above any loss in recorded history. Robust parameters do not rescue this;
   nothing does except changing the family or the target (**[C5]**, **[C10]**).
4. **Clean, light-tailed, correctly-specified data.** MLE is efficient by construction there,
   and gQLS gives up ~9% ARE for protection that is never exercised — ordinary QLS is
   marginally better than gQLS for a normal standard member. Robustness you do not use is a
   pure cost (method card §4 regime table; **[C9]**).
5. **Any filing or paper that does not state its quantile convention and k.** At n = 30 both
   move fitted parameters by ~20× the resolution those parameters are printed at, so an
   unstated convention makes the second decimal of your own numbers irreproducible — by a
   reviewer, by a regulator, or by you next year (**[C7]**).
