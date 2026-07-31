---
type: findings
domain: "insurance"
status: final
concepts: [claim-frequency, poisson-deviance, glm, hgbt, paired-bootstrap, noise-floor]
related: [03-noisy-rosenbrock-dfo]
---

# Findings — 04-fremtpl2-frequency

> Claim IDs are stable (`04-fremtpl2-frequency#C<n>`). Deltas are stated against
> the measured floors: fit-seed std 0.000210 (k=5), paired-difference bootstrap
> SE 0.000893 (the comparison floor; `minimum_delta` = 2× it), marginal fold SE
> 0.005391. The incumbent's LEVEL is **confirmed** by the sealed run; the
> GLM-vs-GBDT GAP is exploratory-by-construction (one sealed access per track —
> see ⑥ and the soak log).

## ① Research-question verdicts

| Claim | RQ | Track | Verdict | Evidence level | Evidence (exp IDs) | Metric delta + uncertainty |
|---|---|---|---|---|---|---|
| **[C1]** | RQ1 (HGBT beats GLM) | primary | **supported** | level confirmed; gap exploratory | E0001, E0003, E0006 | 0.454861 → 0.444689 dev (Δ 0.010172 = 11.4 paired SEs, 5.7× minimum_delta); sealed test 0.449667 replicates the level (0.65× fold SE from dev) |
| **[C2]** | RQ2 (shaping closes a large part of the gap) | primary | **refuted in magnitude** | exploratory | E0002 | shaping closed 0.001788 = 18% of the gap — a keep by 0.000002 over the floor, not "a large part" (scope caveat: splines hit the dummies too; program.md) |
| **[C3]** | RQ3 (native cats ≈ OHE) | primary | **supported** | exploratory | E0004 | 0.445343 vs 0.444689 — 0.37× floor apart; the predicted tie |

## ② Predictions to falsify (filled)

| Lever | Predicted delta | Observed delta | Verdict | Evidence |
|---|---|---|---|---|
| GLM → HGBT baseline | ≥ 3× floor (KEEP) | 5.7× minimum_delta (11.4 paired SEs) | **held** | E0003 |
| GLM → GLM + shaping | > floor but > 2× floor short of HGBT | +0.001788 (1.001× floor, kept by 2e-6); still 4.7× floor short of HGBT | held on direction, **refuted on "large part"** | E0002 |
| HGBT OHE → native cats | within 2× floor (DISCARD) | 0.37× floor | held | E0004 |

## ③ Surprises and why

1. **The floor is three floors** — fit-seed spread (0.0004), marginal fold SE
   (0.0108), paired-difference SE (0.0018) differ by 25×. Under the naive
   marginal floor the study's headline gap (0.0102) looks borderline; under the
   correct paired floor it is 11.4 SEs. Shared shot noise cancels in paired
   comparison — most published freMTPL2 comparisons quote no error bar at all.
2. **A keep by two millionths** (E0002): the shaping gain landed at 1.001× the
   floor. The arithmetic held a case no hand-waved judgment would call
   consistently.
3. **An accidental exact replication** (E0005): a driver error ran an empty
   candidate diff — the framework reproduced the incumbent bit-identically
   (0.444689) and filed an honest discard. Determinism proven by mistake.
4. **The hub's table carries the answer key**: the raw freMTPL2 variant ships
   `Frequency` (= the target) plus four more derived columns; a naive
   keep-all-numerics prep would have trained on the label. The DATA gate's
   allowlist + clean-room audit is where this died.

## ④ Practical advice

1. **[C4]** For model COMPARISON on one fold, measure the paired-difference
   bootstrap SE — the marginal fold SE overstated comparison noise 6× here
   (evidence: program.md floor analysis, E0001/E0003).
2. **[C5]** Fit frequency models on y = ClaimNb/Exposure with
   `sample_weight = Exposure`; both `PoissonRegressor` and HGBT's Poisson loss
   accept it natively — no offset plumbing needed (evidence: pipeline.py, E0001–E0006).
3. **[C6]** At ≤ 22 categorical levels, do not spend a slot on native-vs-OHE for
   HGBT — 0.37× floor apart (evidence: E0004).
4. **[C7]** Allowlist your prepared columns; never keep-all-numerics on shared
   actuarial datasets — this variant shipped the target in disguise
   (evidence: data_card issue 1).

## ⑤ Business / actuarial value implications

The confirmed level (test deviance 0.4497, calibration ratio ≈ 1.0 in aux)
says the boosted model prices this book better than the raw GLM by an amount
that survives fresh data — but the shaped-GLM result warns that a rate-filing
GLM rebuilt with proper feature engineering recovers only a fraction of that
gap at this effort level; the rest is interactions a linear score cannot see
(consistent with the case-study literature, ⑥).

## ⑥ Literature tie-back

- Noll–Salzmann–Wüthrich (SSRN 3164764): boosting beats GLM on freMTPL2 with
  interactions as the mechanism — direction reproduced here under an error bar
  they did not publish. Absolute values differ (this hub variant is pre-clipped;
  data card issue 3).
- Wüthrich–Merz (2022, Ch. 2/5): the exposure-weight equivalence used
  throughout ([C5]) is their Proposition-level standard treatment.
- Priors' scorecard: knowledge-sourced priors 2/3 fully held (RQ1 gbdt-tabular,
  RQ3 encoder-comparison); glm-pricing's "shaping closes most of the gap"
  over-promised at this effort level (RQ2) — the card should gain a caveat at
  promotion. Uninformed priors: none registered.
- Protocol note: the GLM-vs-GBDT gap cannot be sealed-confirmed under
  one-access-per-track; a two-track design would seal both levels (soak F6).

## ⑦ What to try next

1. Column-scoped splines (fix the E0002 caveat) — does proper shaping close
   more than 18%?
2. Capacity/learning-rate sweep via `SweepRunner` (the slate's probe that
   E0005's rerun consumed).
3. Two-track redesign (glm / gbdt as separate tracks) to seal the gap itself.
4. Tweedie pure-premium track once severity joins (blocked on registry deviance
   metrics — soak F1).
