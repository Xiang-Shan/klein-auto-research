---
type: method-card
domain: "optimization"
status: final
concepts: [spsa, stochastic-approximation, derivative-free-optimization]
related: [nelder-mead, random-restarts]
refs_verified: true    # both references verified against publisher indexes, 2026-07-30
triad:
  theory: true         # §2: notation table + the two load-bearing equations
  papers: true         # refs_verified: true (Spall 1992; Spall 1998)
  practice: true       # §3 names the runnable implementation train.py drives (optimizers.spsa)
---

# Method card — SPSA (Simultaneous Perturbation Stochastic Approximation)

> Gate 2 (METHOD). The unfamiliar method in this study is SPSA; Nelder-Mead and
> random restarts are assumed background. Written BEFORE any SPSA experiment runs.

## 1. Intuition (for a practitioner)

Finite-difference gradient estimation in d dimensions costs 2d function
evaluations per step. SPSA's trick: perturb ALL coordinates at once with a random
±1 vector and use just TWO evaluations — the resulting single "slope" is a wrong
gradient at every step, but its wrongness has mean zero, so averaged over many
small steps it behaves like the true gradient. Think "drunk gradient descent":
each step staggers, the walk goes downhill. The price is a delicate gain
sequence — step sizes must shrink at tuned rates, and a too-aggressive start
diverges violently rather than gracefully (we exploit exactly that failure mode
as this study's engineered crash).

## 2. Math core

| Symbol | Meaning |
|---|---|
| θ_k | parameter iterate at step k |
| a_k, c_k | gain sequences: a_k = a₀/(k+1+A)^α, c_k = c₀/(k+1)^γ |
| Δ_k | random perturbation vector, i.i.d. Rademacher ±1 per coordinate |
| y(·) | one NOISY objective evaluation |
| ĝ_k | the two-point simultaneous-perturbation gradient estimate |

$$ \hat g_k(\theta_k) = \frac{y(\theta_k + c_k \Delta_k) - y(\theta_k - c_k \Delta_k)}{2 c_k}\,\Delta_k $$

$$ \theta_{k+1} = \theta_k - a_k\, \hat g_k(\theta_k) $$

Two evaluations per iteration, regardless of dimension; E[ĝ_k] → ∇f under mild
conditions (Spall 1992, Prop. 1-2). Standard asymptotically-optimal decay rates
α = 0.602, γ = 0.101, with A ≈ 10% of the expected iteration count (Spall 1998).

## 3. Minimal from-scratch implementation plan

Already realized as `optimizers.spsa()` in this study (~20 lines, numpy only):
draw Δ ∈ {−1,+1}², evaluate y(θ±cΔ) through the budgeted noisy objective, step
θ ← θ − a·ĝ. No gradient clipping BY DESIGN — divergence under an aggressive a₀
must surface as an honest crash, not be silently clamped. `train.py` selects it
via `OPTIMIZER = "spsa"` and `SPSA_A0`.

## 4. When it pays / when it doesn't

| Regime | Verdict | Why |
|---|---|---|
| High-dimensional, expensive noisy evaluations | pays | 2 evals/step vs 2d for finite differences |
| d=2, tiny 200-eval budget (THIS study) | prior: does NOT pay | only ~100 iterations for a gain sequence that needs hundreds to settle; dimension advantage is nil at d=2 |
| Aggressive a₀ on a steep landscape (Rosenbrock walls ~10²·x³) | diverges | ĝ magnitudes ~10²–10³; a₀·ĝ overshoots into ever-steeper territory → overflow |

Falsifiable priors registered in `study.yaml`: tuned SPSA (a₀=0.1) lands within
2× the noise-floor std of restarted NM (DISCARD); aggressive SPSA (a₀=50)
produces a non-finite mean gap (CRASH).

## 5. References (verified)

1. Spall, J.C. (1992). "Multivariate stochastic approximation using a
   simultaneous perturbation gradient approximation." *IEEE Transactions on
   Automatic Control*, 37(3):332–341. ✅ verified 2026-07-30 (publisher/index
   listings agree on venue, volume, pages).
2. Spall, J.C. (1998). "Implementation of the simultaneous perturbation algorithm
   for stochastic optimization." *IEEE Transactions on Aerospace and Electronic
   Systems*, 34(3):817–823. ✅ verified 2026-07-30 (ADS + Semantic Scholar; source
   of the α=0.602, γ=0.101, A≈10%·iterations guidance).
