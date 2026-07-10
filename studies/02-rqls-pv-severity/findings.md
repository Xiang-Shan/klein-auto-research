---
type: findings
domain: insurance
status: complete
concepts: [quantile-least-squares, robust-severity-estimation, method-of-trimmed-moments, left-truncation-right-censoring, observable-window-fit, layer-map-cancellation, stopped-clock-pricing, cap-bounded-tail, mixture-misspecification, monte-carlo-floor, tvar-loaded-premium, efficiency-robustness-tradeoff]
related: [program.md, method_card.md, data_card.md, results.tsv, aux_metrics.tsv, sweeps/e3_breakdown.sidecar.tsv, sweeps/e7_decision.sidecar.tsv, ../../knowledge/method_cards/quantile-least-squares.md, report/index.html]
---

# Findings — 02-rqls-pv-severity

> SYNTHESIZE stage output. QUALITY BAR: every claim cites experiment IDs from
> `results.tsv` / `aux_metrics.tsv` / the two sweep sidecars; no claim without evidence.
> Contradictions with the method-card priors are called out explicitly. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`.
>
> Trajectory mined: 7 experiments — 7 `keep`, 0 `discard`, 0 `crash`. This is a
> known-truth synthetic lab, so the ledger is not a climb toward one best number: each
> experiment scores `premium_error_pct` against a DIFFERENT truth cell (single-family
> truth premium $25,341 for E1–E3; realistic-mixture $62,346 for E4/E5/E7; tail-on
> $62,455 for E6). The story is not "which run won" but "how wrong is the premium under
> each way real loss data breaks." Total ledger wall-clock ≈ 5.3 min of scipy (phase 0
> ≈ 1.3 s, phase 1 ≈ 108 s, phase 2 ≈ 206 s) against a 2.3 h budget.

## ① Research-question verdicts

One row per RQ in `study.yaml`. Every verdict cites evidence experiment IDs and the
signed, unit-bearing delta.

| RQ | Verdict | Evidence (exp IDs) | Metric delta |
|---|---|---|---|
| **RQ1** — what does robustness cost at ε=0 (clean data)? | **CONFIRMED** (prior held, lower edge) | E2 (keep, 1000 reps) | QLS-OLS **4.459 %** = **1.083×** the MLE floor 4.116 %; rel. eff **0.846** premium-MSE / **0.805** σ̂-MSE (prior band 1.05–1.18× / 85–95 % — landed at the low edge). GLS 1.123× (0.785); MTM 1.219× (0.653). |
| **RQ2** — does naive MLE's premium diverge under contamination while QLS/MTM stay bounded? | **CONFIRMED** (both falsification points cleared) | E3 (keep, 20 cells × 500 reps) | At ε=5 %: MLE **136.6 %** > 50 % vs QLS **20.3 %** / MTM **22.7 %** < 25 %. Over ε 0→10 %: MLE **4.21 → 352.19 %** vs trimmed-QLS **5.42 → 49.97 %**. Contamination biases premiums **UP**. |
| **RQ3** — does observable-window QLS recover truth under d=$5k trunc + u=$2M cens where naive MLE is biased? | **SPLIT** — recovery CONFIRMED, the "naive → >20 %" prior FALSIFIED | E4 (keep, 500 reps) | Window-QLS **4.834 %** ≈ incomplete-data floor; trunc-MLE 4.680 %. BUT naive-MLE premium error only **5.85 % (signed −5.2 %)**, not >20 % — despite μ̂ bias **+0.596** / σ̂ bias **−0.347** (both theory-exact). Param bias huge, pricing bias small: they cancel in the layer map. |
| **RQ4** — how do estimator errors flow to VaR/TVaR/premium; does an ignored GPD fire tail underprice? | **FALSIFIED, twice, instructively** | E6 (keep, 500 reps) | (a) the $2M cap bounds the WHOLE GPD tail to **+0.174 %** of premium (TVaR99 +0.219 %, VaR99 +0.000 %) — two orders below the ">10 %" prior. (b) POT tail-awareness estimates WORSE: ξ̂ **0.217** vs true 0.4 on hail-confounded exceedances → aware−blind |bias| **premium +1.86 pp / VaR99 +4.38 pp / TVaR99 +2.85 pp**. |

**RQ1 detail.** E2 is the clean paired-design efficiency measurement (single-family
lognormal(9.0, 1.1), ε=0, complete data, n=2,000 × 1,000 reps, seeds 42+r). The MLE
floor refined to **4.116 %** (the 1,000-rep version of E1's 4.279 % at 200 reps). The
efficiency cost of QLS-OLS is real but small — 8.3 % more premium error, or losing ~15 %
of the MLE's premium-MSE efficiency and ~20 % of its σ̂-MSE efficiency (aux
`rel_eff_premium_qls_ols_vs_mle=0.846`, `rel_eff_sigma_..=0.805`). **Two surprises worth
carrying (§③):** (i) the diagonal plug-in **GLS is *less* efficient than plain OLS**
(1.123× vs 1.083×; rel. eff 0.785 < 0.846) — the inverse-variance weights add noise, not
efficiency, at this 19-point grid; (ii) MTM's 10 % double trim is the priciest insurance
(1.219×, rel. eff 0.653, `err_ratio_mtm_vs_mle=1.2185` — outside the QLS prior band).
Compute is a non-issue: all four estimators ≈ 6 s / 1,000 fits incl. pricing (aux
`wall_seconds_*`).

**RQ2 detail.** E3 ran as the first sanctioned sweep (20 cells → `sweeps/e3_breakdown.sidecar.tsv`,
rep counts in `params_json`, one results row = the pre-registered trimmed-QLS-OLS @ ε=10 %
= 49.969892). The breakdown curve is the money picture (all single-family, contamination
only, no trunc/cens; MC floor ≈ 4.1–4.3 %):

| ε | MLE | trimmed QLS-OLS | QLS-GLS | MTM |
|---|---|---|---|---|
| 0 % | 4.21 | 5.42 | 5.52 | 5.06 |
| 1 % | 21.28 | 6.25 | 6.32 | 6.25 |
| 2 % | 45.47 | 8.58 | 8.56 | 9.13 |
| 5 % | **136.59** | **20.32** | 20.03 | 22.74 |
| 10 % | **352.19** | 49.97 | 48.95 | 57.55 |

Even ε=1 % — one bad record in a hundred — already puts the MLE at **5× the floor**.
Trimming bounds the damage but does NOT null it: the ε-mix (half ×10–100 gross
over-reports, half ×0.01 unit typos) shifts mid-sample quantile ranks
(Q̂(p) ≈ Q_clean((p−ε/2)/(1−ε))), so robust-estimator bias grows ~linearly in ε while
the MLE grows explosively. All estimators biased **UP** — gross over-reports inflate
σ̂ → TVaR99 → premium — i.e. this contamination mix **overcharges policyholders**.

**RQ3 detail.** E4 (d=$5k truncation + u=$2M censoring, ε=0, n=2,000 drawn × 500 reps;
observed ≈ 1,340/rep, coverage 67.01 % vs exact 1−F(d)=66.96 % ✓). The recovery half
held cleanly: window-QLS **4.834 %** (near-unbiased: μ̂ +0.00226, σ̂ −0.00273, premium
bias −0.02 %) and trunc-MLE **4.680 %** both sit at the incomplete-data floor (>E1's
4.28 % only because truncation cuts effective n to ~1,340; robustness costs ~3 % here,
QLS/trunc-MLE ratio 1.033). The **prior half was FALSIFIED**: the naive full-sample MLE's
parameter bias is enormous and theory-exact (μ̂ **+0.596** = σ·λ(α)=0.593 at
α=(ln d−μ)/σ=−0.439; σ̂ **−0.347** = the truncated-normal variance shrink; RMSE ≈ |bias|,
pure systematic distortion) — **yet its premium error is only 5.85 % (signed −5.2 %),
not >20 %.** The mechanism is §③(b): μ-up and σ-down cancel in this layer's premium map.
Censoring never binds at this cell (n_cens=0.000, S(u)≈3e-7) — the machinery is exercised
but bites only in E6's tail mode.

**RQ4 detail.** E6 (mixture, tail_mode ON: fire GPD ξ=0.4, β=$125k spliced above
t=$250k; ε=0; trunc+cens; 500 reps; n_exc ≈ 19.2/rep, POT fallback 0/500). The prior
falls on **both sides**. Truth-side: because the $2M limit caps the layer, the entire GPD
tail is worth **+0.174 %** of premium — a policy limit is *itself* tail protection, and
tail shape beyond the cap cannot move a capped TVaR. Estimation-side: fitting the tail
made it **worse**, because the exceedances above t are mostly HAIL lognormal mass, not
fire GPD — POT fits ξ̂ **0.217** (sd 0.264; **35.6 %** of fits clipped at the ξ≈0 floor),
a *lighter* tail than the lognormal it replaces, and restricting the body fit to (d, t)
deletes the beyond-t hail signal (VaR99 bias −30.07 % aware vs −25.69 % blind). **Emergent
finding (§③, and the study's biggest practical lesson):** at ε=0 every single-lognormal
estimator underprices this mixture layer by ~23–26 % (blind QLS −25.77 %, trunc-MLE
−23.39 %) — pure MIXTURE-MISSPECIFICATION bias from the un-modelled hail component. The
dominant "tail risk" in this lab is hail, not the GPD splice.

## ② Predictions to falsify (filled)

Levers copied from `study.yaml:predictions_to_falsify` / `program.md`; observed + verdict
from the trajectory. Tally: **1 held, 1 held-clean, 1 split, 1 falsified-twice.**

| Lever | Predicted Δ | Observed Δ (exp IDs) | Verdict |
|---|---|---|---|
| **QLS vs MLE at ε=0 (clean) — RQ1** | QLS ≈ 1.05–1.18× MLE (rel. eff 85–95 %); QLS slightly WORSE on clean data | E2: QLS-OLS **1.083×** MLE (4.459 % vs 4.116 %); rel. eff 0.846 prem / 0.805 σ̂ | **HELD** (low edge of band; QLS is slightly worse, as predicted) |
| **contamination ε=5 % (naive MLE vs QLS/MTM) — RQ2** | MLE diverges (>50 %); QLS/MTM bounded (<25 %) | E3: MLE **136.6 %** (>50 ✓); QLS **20.3 %**, MTM **22.7 %** (<25 ✓) | **HELD** — both thresholds cleared |
| **truncation d=$5k + censoring u=$2M (naive MLE vs window-QLS / trunc-MLE) — RQ3** | naive MLE-full large (>20 %, biased); window-QLS / trunc-MLE ≈ truth (<5 %) | E4: window-QLS **4.83 %**, trunc-MLE **4.68 %** (<5 ✓); naive-MLE only **5.85 %** (signed −5.2 %), NOT >20 % | **SPLIT** — recovery clause HELD; "naive >20 %" clause **FALSIFIED** (param bias ≫ pricing bias) |
| **GPD fire tail ξ=0.4 (tail-blind vs tail-aware) — RQ4** | ignoring the tail underprices TVaR99 → premium error material (>10 %); a tail-aware fit recovers | E6: whole tail worth **+0.174 %** of premium (truth, capped layer); tail-aware makes it WORSE (+1.86 pp premium, ξ̂ 0.22 vs 0.4) | **FALSIFIED TWICE** — the cap bounds the truth impact; POT tail-awareness hurts estimation |

The two overturned clauses carry mechanism, not just a miss (both in §③): RQ3's naive
premium error is small because the μ̂/σ̂ biases cancel in the layer map; RQ4's tail is
neutralized by the policy cap AND its POT estimate is corrupted by hail-confounded
exceedances. The real underpricing this lab exposes is **mixture misspecification**
(−23 to −42 % at ε=0, E5/E6/E7), a hazard neither prior named.

## ③ Surprises and why

The study's three crown jewels, each a mechanism, not just a delta.

**Surprise 1 — "stopped-clock pricing": the low-error cells are two wrongs cancelling,
not skill (E7).** E7 ran the consolidated realistic-lab decision grid as the second
sanctioned sweep (`sweeps/e7_decision.sidecar.tsv`: mixture, tail off, trunc d=$5k +
cens u=$2M; 4 estimators × ε∈{0,1,2,5,10}% × 500 reps; truth premium $62,346.20). Here is
the filing-memo table **verbatim** — signed premium bias % vs truth (negative =
UNDERcharge, positive = OVERcharge); |bias| ≈ mean |error| except near zero:

| Estimator (single-lognormal fit) | ε=0 % | ε=1 % | ε=2 % | ε=5 % | ε=10 % |
|---|---|---|---|---|---|
| naive MLE (no corrections) | −33.9 | −20.0 | **−3.5** | +57.5 | **+188.9** |
| truncated/censored MLE | −23.3 | −17.6 | −12.3 | **+2.1** | +15.9 |
| window-QLS, trimmed [0.15,0.85] | −31.5 | −29.2 | −26.9 | −18.6 | **−0.6** |
| MTM (trim 0.10) | −42.3 | −40.5 | −38.6 | −31.9 | −16.2 |

Read it as **two errors of opposite sign**. At ε=0 every single-family estimator
underprices by 23–42 % — that is pure mixture-misspecification bias (the un-modelled hail
tail), not estimation noise (mle_tc's −23.3 at tail-off ε=0 matches E6's tail-on −23.4;
the GPD tail itself is worth only +0.17 %). Contamination pushes premiums UP (§①-RQ2), so
as ε rises the two errors **cancel**: naive-MLE crosses zero near ε≈2 % (−3.5 %) then goes
catastrophically wrong (+188.9 % at ε=10); trunc-MLE sweet-spots at ε=5 (+2.1 %); trimmed
window-QLS — the most contamination-immune — drifts to near-exact at ε=10 (−0.6 %)
**by cancellation, not fit quality**. The memo caveat (carry it into any filing use):
**no cell on this grid reaches the 4.28 % MC floor by SKILL — every low-|error| cell is
mixture-misspecification undercharge cancelling contamination overcharge.** The structural
fix is modeling the mixture (per-peril fits), not choosing among single-family estimators.

**Surprise 2 — parameter bias ≠ pricing bias: "wrong parameters, nearly right layer"
(E4).** The naive full-sample MLE under truncation has a textbook-large, theory-exact
parameter bias: μ̂ **+0.596** (the conditional-mean lift σ·λ(α)=0.593 at α=−0.439) and
σ̂ **−0.347** (truncated-normal variance shrink), RMSE ≈ |bias| in both. Intuition says a
fit that wrong must price disastrously. It does not — premium error is only **5.85 %
(signed −5.2 %)**. Why: the naive fit approximates the *conditional* law of losses above
the deductible d, and a layer with deductible d **only pays above d**. The upward μ bias
inflates the layer expectation; the downward σ bias deflates the tail/TVaR; in this
layer's premium map the two nearly annihilate. The doctrine this sharpens: **parameter
RMSE is not pricing risk.** What truncation-ignorance corrupts materially is the
*ground-up* law and any functional below d or far past the cap — not necessarily the
same-layer premium you are actually selling.

**Surprise 3 — window ≫ trim: the observable window is the principled robustifier;
blind trimming deletes real signal (E5).** The pre-registered hypothesis was "trimming
matters most." The 2×2 QLS ablation at the realistic cell (mixture, ε=5 %, trunc+cens,
500 reps) **overturned it**:

| QLS variant | premium error % | signed |
|---|---|---|
| window-only (untrimmed, (d,u) window) | **8.90** | −5.52 |
| window + trim [0.15,0.85] | 18.78 | −18.55 |
| naive-QLS (no window, no trim) | 23.74 | −23.73 |
| trim-only (no window) | 35.90 | −35.90 |

`window-only 8.90 ≫ window+trim 18.78 ≫ naive-QLS 23.74 ≫ trim-only 35.90`. Mechanism:
under a misspecified single-lognormal fit of a heavy-tailed MIXTURE, the top quantiles
carry **real risk** (hail ×8, 8 % of claims), not just contamination — trimming p>0.85
deletes that signal and the fit underprices the tail (TVaR99 bias: trimmed-QLS −18.5 %,
MTM −48.8 %). The **(d,u) window** is the *principled* trimmer: unit-typos (×0.01) land
below d, gross errors (×10–100) mostly land above u, so the KNOWN policy terms screen
contamination without touching real mid-tail signal. That is why the two window-corrected
untrimmed estimators win the realistic cell — trunc-MLE 7.85 % (best, signed +2.10) and
window-QLS-untrimmed 8.90 % — while every blind-trimming variant underprices. Direction
worth the memo: naive OVERcharges (+57.5 %); every trimmed/robust variant UNDERcharges.

## ④ Practical advice

On your own severity data, in priority order (imperatives, best-practices voice):

1. **Fit the observable window; do not trim blind.** Use the *known* deductible and limit
   as the robustifier — fit QLS on the (d, u) window and let the policy terms screen the
   contamination that lands outside it. Blind symmetric trimming of the quantile grid
   costs you real tail signal: on the realistic cell, window-only QLS scored 8.90 % but
   trim-only 35.90 %, and adding a trim to the window *doubled* the error (8.90 → 18.78 %,
   E5). Trim only what the window cannot reach.
2. **Model the mixture BEFORE robustifying the estimator.** The dominant error in this lab
   is not contamination or truncation — it is fitting one lognormal to a peril mixture
   with a hail shoulder: −23 to −42 % underpricing at ε=0 across *every* single-family
   estimator (E6, E7). No choice of robust estimator fixes a misspecified family. Fit
   per-peril (or a mixture) first; reach for QLS/MTM to make *that* fit robust.
3. **Score functional-level error (premium, VaR, TVaR) — never stop at parameter RMSE.**
   E4's naive MLE had μ̂/σ̂ RMSE of 0.60/0.35 (enormous) yet a −5.2 % premium error
   (small), because the biases cancel in the layer map. A parameter-only evaluation would
   have red-flagged a fit that prices nearly right, or (elsewhere) greenlit one that
   prices wrong. Always push the fit through to the decision functional you sell.
4. **Treat a policy cap as a tail-risk control and quantify it before buying tail
   machinery.** The $2M limit bounded the entire GPD ξ=0.4 fire tail to +0.174 % of
   premium (E6). Before you fit a POT/EVT tail, compute what the capped layer can even
   *feel*: on a capped book, tail shape beyond the cap is often worth basis points, and a
   noisy POT fit (ξ̂ 0.22 vs 0.4, 36 % clipped) can make the estimate *worse* (+1.86 pp
   premium aware-vs-blind).
5. **Always report against the Monte-Carlo floor, never against zero.** At n=2,000 even a
   perfect, unbiased estimator shows ≈ 4.28 % mean premium error from finite-sample
   propagation through the nonlinear premium map (E1). "5 % error" is *excellent* here and
   "0 %" is impossible; the floor is the honest yardstick and the reference line on every
   figure.
6. **Buy the robustness insurance — it is cheap.** QLS costs 1.083× the MLE's premium
   error on clean data (E2) and in exchange bounds the ε=10 % blow-up from 352 % (MLE) to
   50 % (single-family, E3) — a ~7× smaller error for an 8 % premium on clean data. On the
   realistic lab the contrast is starker still (naive +188.9 % vs trimmed-QLS −0.6 % at
   ε=10, E7). Skip the diagonal plug-in GLS, though: it added noise, not efficiency
   (1.123× > OLS 1.083×, E2).

## ⑤ Business / actuarial value implications

- **The decision table is a filing-memo artifact — with a caveat that must ship with it.**
  E7's signed grid (§③, `sweeps/e7_decision.sidecar.tsv`) is exactly the exhibit a rate
  filing wants: for each estimator and each contamination level, how wrong is the premium
  and *in which direction* — underpricing is reserve/solvency risk, overpricing is a
  competitiveness and fairness problem (the naive MLE **overcharges policyholders by
  +57.5 % at ε=5 %**). The non-negotiable caveat: **no cell reaches the 4.28 % MC floor by
  skill — every low-|error| cell is two wrongs cancelling** (misspecification undercharge
  vs contamination overcharge). A memo that reports the +2.1 % trunc-MLE @ ε=5 cell as
  "accurate" without that footnote is reporting luck as competence. The structural fix
  (per-peril modeling) belongs in the same memo.
- **Robustness priced in dollars of premium error.** The clean-data cost of QLS is 8.3 %
  more premium error (4.459 % vs 4.116 %, E2); the payoff is a bounded response when the
  data misbehaves — 7× less error than the MLE at ε=10 % on the clean family (50 % vs
  352 %, E3), and the difference between a −0.6 % and a +188.9 % premium at ε=10 % on the
  realistic lab (E7). For a TVaR-loaded premium — the most tail-sensitive number an
  actuary files — that bounded response is the difference between a fileable rate and a
  blown one.
- **The synthetic-lab pattern is itself the deliverable.** There is no public PV
  loss-severity data with a known answer, so this study built the answer: a deterministic
  generator whose exact layer functionals (VaR/TVaR/premium, integration-computed and
  Monte-Carlo-verified within 1 %) let every estimator be scored against ground truth. The
  entire 7-experiment ladder — a frontier robust estimator, four falsifiable priors, a
  breakdown sweep, a decision grid — ran in **≈ 5.3 minutes of scipy** at ~$0 marginal
  compute. When you have no data, you can still quantify estimator behavior against a known
  truth; the alternative is shipping a robustness claim you cannot defend.

## ⑥ Literature tie-back

Four references, each verified during the METHOD gate (`method_card.md` §5, `refs_verified: true`):

- **Adjieteh, M. & Brazauskas, V. (2025).** *Quantile Least Squares: A Flexible Approach
  for Robust Estimation and Validation of Location-Scale Families.* Statistics and
  Computing **35**, Art. 106; DOI 10.1007/s11222-025-10626-6; arXiv:2402.07837.
- **Poudyal, C. & Brazauskas, V. (2022).** *Robust Estimation of Loss Models for Truncated
  and Censored Severity Data.* Variance **15**(2); arXiv:2202.13000.
- **Brazauskas, V., Jones, B. & Zitikis, R. (2009).** *Robust fitting of claim severity
  distributions and the method of trimmed moments.* JSPI **139**(6), 2028–2043.
- **Poudyal, C. (2021).** *Robust Estimation of Loss Models for Lognormal Insurance Payment
  Severity Data.* ASTIN Bulletin **51**(2); DOI 10.1017/asb.2021.4; arXiv:2103.02089.

**What our lab CONFIRMS from them.** The efficiency–robustness tradeoff is exactly the
"insurance purchase" the QLS/MTM literature describes: Adjieteh & Brazauskas's 85–95 %
relative-efficiency band held (we measured 0.846 premium / 0.805 σ̂ at the low edge, E2),
and the bounded-influence breakdown behavior — trimmed grid/moments stay linear-in-ε while
the MLE diverges — is precisely their doctrine landing on a known-truth premium (E3). The
truncation/censoring identifiability that lets window-QLS and the conditional-likelihood
MLE recover the truth (E4) is the Poudyal & Brazauskas 2022 / Poudyal 2021 framework
working as advertised. MTM as the trimmed-moment cousin (Brazauskas, Jones & Zitikis 2009)
behaved as its older-sibling status predicts — robust but the priciest on clean data
(1.219×, E2) and the worst underpricer under mixture misspecification (TVaR99 −48.8 %, E5).

**What our lab ADDS.** Those papers are location-scale, single-family results. Our lab
grafts them onto a **peril MIXTURE under a product layer**, and two observations fall out
that the location-scale theory does not cover: (i) the **layer-map cancellation** — a
theory-exact truncation parameter bias that nearly vanishes in same-layer premium (E4),
i.e. robustness measured in parameter space overstates the pricing stakes when the payout
is a bounded layer; and (ii) the **cap-bounded tail** — a policy limit caps how much any
tail (even ξ=0.4 GPD) can move a TVaR-loaded premium (+0.174 %, E6), so tail-aware
machinery can *lose* to a tail-blind window fit when the exceedances are confounded by an
un-modelled component. We also observed that the **diagonal plug-in GLS disappoints** at a
fine grid (1.123× > OLS 1.083×, E2) — the full off-diagonal Σ⁻¹ is the efficiency ceiling,
but the stable diagonal form the card implemented does not reach it.

**PV-novelty honesty note (carried verbatim in spirit from `method_card.md`).** No
published paper applies QLS to photovoltaic risk — the PV bridge is this study's original
construction. The QLS/MTM/truncated-MLE methods and their asymptotics are from the
peer-reviewed severity-modeling literature above; grafting them onto a PV loss-severity
generator (peril mix, hail concentration, fire GPD tail) is our own synthetic lab. The PV
loss-concentration figures motivating the peril mix are industry-reported (pv-magazine
2025) and used as **market context only** — not validated model parameters. The
generator's numbers are illustrative and plausible, not fitted to any PV book.

## ⑦ What to try next

In priority order:

1. **Model the mixture (per-peril fits) — the structural fix.** Every finding in §③–⑤
   points here: the −23 to −42 % ε=0 underpricing (E6, E7) is misspecification, not
   estimation. Fit each peril (or a lognormal mixture with a heavy hail component)
   separately, price the layer on the mixture, and re-run the E7 decision grid. Prediction
   to falsify: the ε=0 column collapses toward the 4.28 % floor and the "stopped-clock"
   cancellation disappears.
2. **An MLE-tc + window-QLS ensemble.** trunc-MLE won the realistic cell (7.85 %, E5) but
   is slow (Nelder-Mead, 13.6 s of E4's 20.7 s) and less contamination-immune at high ε;
   window-QLS is fast and contamination-bounded. A blend (e.g. window-QLS body + trunc-MLE
   as a cross-check, or a robustified conditional likelihood) may dominate both across the
   ε grid. Target: beat the best per-cell |error| in the E7 table.
3. **An ε-contamination stress-test template for filings.** Package the E3/E7 sweep harness
   as a reusable exhibit: given a fitted severity model and a layer, report the signed
   premium/VaR/TVaR error across ε∈{0,1,2,5,10}% and flag any cancellation cell. This turns
   the study's method into a standard robustness appendix for a rate filing.
4. **Acquire real PV loss-severity data.** The lab is calibrated to *illustrative* PV
   shape, not a real book. Even a modest real dataset (deductible/limit-layered claims)
   would let the estimators be compared on genuine severity — with the synthetic lab as
   the known-truth control that says what "recovered the truth" should look like.
5. **GLS with the full covariance on coarser grids.** The diagonal plug-in GLS added noise
   at 19 points (E2). The off-diagonal Σ⁻¹ is the efficiency ceiling but ill-conditions on
   fine grids; a coarser 7–9 point grid with the full covariance may finally beat OLS.
   Prediction: full-Σ GLS < OLS error only when the grid is coarse enough to invert stably.
