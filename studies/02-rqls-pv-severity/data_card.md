---
type: data-card
domain: "insurance"
status: go
concepts: [synthetic-known-truth, left-truncation, right-censoring, contamination, tvar-premium-loading, monte-carlo-floor]
related: [method_card.md, ../../knowledge/best-practices-auto-insurance.md]
---

# Data card — 02-rqls-pv-severity

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.
> **Synthetic study:** there is no external dataset — the "data" IS the generator
> (`generator.py`, `synthetic:pv_losses_v1`). This card therefore documents the
> generator as the data source, and the DATA gate's go/no-go question becomes:
> *is the generator itself validated against its own ground truth?* (Answered by
> the E1 truth-recovery gate — a bias ≈ 0 check under the clean single-family cell.)

## Source & shape

- **Source:** `synthetic:pv_losses_v1` — `PVLossGenerator` in `generator.py`. Fully
  deterministic per seed (test-pinned). No download, no license constraints.
- **One sample = one loss year of a PV portfolio:** default `n = 2,000` observed claims
  per replication; experiments use 200–1,000 Monte-Carlo replications.
- **Observed columns per claim** (`SampleResult`): `losses` (recorded $ value — censored
  values capped at `u`; contamination applied), `censored` (bool: true loss ≥ `u`,
  recorded as `u`), `contaminated` (bool, oracle flag — available to EVALUATION only,
  never to estimators).
- **Truth oracle:** `truth_functionals(d, u)` — exact mean layer payout, VaR95/99,
  TVaR99 by 1-D numeric integration of the mixture survival function, verified against a
  10⁶-draw Monte Carlo within 1% (pinned in `tests/test_rqls.py`).

## The generative truth (what estimators must recover)

| Component | Specification |
|---|---|
| Severity body | lognormal μ=9.0, σ=1.1 (median ≈ $8.1k) · gamma(k=1.5, θ=$9,000) variant |
| Peril mix | inverter 45% · storm 20% · degradation 15% · fire 12% · **hail 8%** |
| Peril adjustments | hail: ×8 location shift (low-freq / high-sev) · fire: GPD tail ξ=0.4 spliced above $250k when `tail_mode` on |
| Incompleteness | **left-truncation** at deductible d = $5,000 (below-deductible losses UNOBSERVED) · **right-censoring** at limit u = $2,000,000 (recorded as u, flagged) |
| Contamination ε | {0, 1, 2, 5, 10}% of records replaced by gross errors (×10–100 multiplier) or unit typos (×0.01); censoring is applied to the TRUE loss first — an admin records the limit, not the mis-key |
| Premium convention | `premium = E[Y] + 0.10·(TVaR99(Y) − E[Y])` on the layer payout Y = (min(X,u) − d)₊ — documented in method_card §2 |
| Truth premiums | single-family E1 cell **$25,341** · realistic mixture reference cell **$62,346** |

**Value-pattern check (mandatory war story):** trivially satisfied here — all columns are
generated numpy arrays with declared dtypes; no string-encoded booleans or sentinel values
can occur. The war-story risk for a synthetic lab is different and listed below (#2):
*silently divergent truth*, i.e. the generator drifting from the documented parameters.
That is why truth functionals are integration-computed AND Monte-Carlo-verified in tests,
and why E1 is a hard gate.

## Ranked go / no-go issues

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | WARN | **Monte-Carlo sampling floor:** at n=2,000 even a perfect estimator shows ≈ 4.28% mean premium error (sd 3.03) from finite-sample propagation through the nonlinear premium map (measured in the E1 dry-run). | Report every E2–E7 premium error AGAINST this floor, never against 0. The floor is the "perfect play" reference line in figures. |
| 2 | WARN | **Synthetic-truth drift risk:** if generator params and documented truth ever diverge, every conclusion is silently wrong (the synthetic-lab analogue of GIGO). | E1 truth-recovery gate (bias < 2·MC-SE) MUST pass before any other experiment; `tests/test_rqls.py` pins truth-vs-MC within 1%; parameters are frozen in this card + study.yaml. |
| 3 | NOTE | **External realism is contextual, not calibrated:** the peril mix and hail loss-concentration pattern reproduce industry-REPORTED shape (pv-magazine 2025, non-peer-reviewed); no claim of calibration to a real PV book. | Present as "stylized but recognizable" in the tutorial; the study's claims are about ESTIMATOR behavior under known truth, which does not depend on mix realism. |
| 4 | NOTE | Estimators never see the `contaminated` oracle flag (no leakage by construction); it exists only for evaluation diagnostics. | Keep it that way — enforced by `estimators.py` signatures (flags not accepted). |

## Verdict

**GO.** The generator is deterministic, truth-verified against independent Monte Carlo,
and gate-checked for bias at E1 (μ̂ bias +0.00037, σ̂ bias −0.00043, both < 2·MC-SE).
Proceed to the METHOD gate and the E1 ledger run on the `experiments/02-rqls` branch.
