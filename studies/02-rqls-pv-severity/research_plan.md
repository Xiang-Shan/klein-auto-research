---
type: research-plan
domain: insurance
status: draft
concepts: [quantile-least-squares, robust-estimation, severity-modeling, truncation, censoring]
related: [method_card.md, program.md]
---

# Research plan — 02-rqls-pv-severity

> CONSULT (Gate 0) companion to `study.yaml`. A known-truth synthetic lab, so the usual
> data-availability interview is short — the "data" is the generator, and its truth is
> exact by construction. Protocol: `.claude/skills/klein/references/consult-protocol.md`.

## The question

Robust Quantile Least Squares (QLS) for PV loss severity under contamination and
incomplete data (deductible-truncated, limit-censored) — a known-truth synthetic lab.

**As a decision:** when your severity data is dirty (data-entry errors) or incomplete
(deductibles hide small losses, limits cap large ones), *which estimator should price the
layer?* The study tells you, in dollars of premium error, when to reach for QLS / MTM /
truncated-MLE instead of the textbook MLE — and what robustness costs you when the data is
in fact clean. A rate you can file depends on getting this right.

## Why now / why this method

- Robust severity estimation is a live actuarial frontier (Adjieteh & Brazauskas 2025;
  Poudyal & Brazauskas 2022) but its guarantees are asymptotic and abstract. A known-truth
  lab makes the behavior *visible in premium dollars*, which is the CAS-seminar payload.
- **Honest prior:** QLS will *cost* a little on clean data (85–95% efficiency) and *pay*
  a lot under contamination/incompleteness. We expect the naive MLE to break dramatically
  (a budget probe already shows ~139% premium error at ε=5% vs ~21% for QLS). Priors are
  recorded per-RQ in `study.yaml:research_questions`.

## Data

- **Source:** `synthetic:pv_losses_v1` — `generator.py::PVLossGenerator`. Peril mix
  (inverter/storm/degradation/fire/hail), lognormal body (+gamma variant), optional GPD
  fire tail, contamination ε, deductible/limit incompleteness. Exact truth functionals via
  numeric integration (verified vs 10⁶-draw Monte-Carlo in `tests/test_rqls.py`).
- `prepare.py` emits a reference cell (`data/prepared/pv_losses_v1_refcell.csv`) + its
  exact truth for the DATA gate to profile.

## Method

- **Under study:** observable-window QLS (OLS/GLS). **Baselines it must beat where the
  data is broken:** naive full-sample MLE, proper truncated/censored MLE, method of
  trimmed moments (MTM). Full pedagogy: `method_card.md`.

## Metric & decision use

- **Primary metric:** `premium_error_pct` (lower is better) — the absolute risk-loaded
  premium error % vs known truth. Maps directly to rate adequacy: a 100%+ premium error is
  an unfileable rate; a <5% error is a defensible one. (Uniform metric contract, rule b.)

## Experiment ladder (sketch — the loop ADAPTS; full table in program.md)

1. **E1** — truth-recovery gate: naive MLE must recover a KNOWN single family (STOP if not).
2. **E2** — efficiency at ε=0: what does QLS cost on clean data? (RQ1)
3. **E3** — breakdown sweep ε∈{0,1,2,5,10}%: MLE diverges, QLS/MTM bounded? (RQ2)
4. **E4** — trunc+cens recovery: naive-MLE vs trunc-MLE vs window-QLS. (RQ3)
5. **E5** — realistic cell (ε=5% + trunc + cens) — everything at once.
6. **E6** — GPD fire tail: VaR/TVaR under-pricing. (RQ4)
7. **E7** — premium-error decision table (the money slide).

## Budgets & stop rule

- Per-phase budgets in `study.yaml:phases` (0.3 h / 1.0 h / 1.0 h) — ample; a budget probe
  clocks a 3-estimator × 100-rep cell at ~1.6 s. Acks after E1, after E4, at end.

## Deliverables

- `findings.md` (7-section synthesis) and `report/index.html` (tutorial) — ALWAYS.

## Risks & unknowns

- **Inconclusive if:** MC reps too few (premium error is tail-sensitive — E1 shows a ~4%
  floor at n=2000; use enough reps per cell to separate estimators). Fixed seeds per cell.
- **Abandon early if:** the E1 truth-recovery gate fails — a lab whose *known* truth the
  naive MLE cannot recover on clean, complete data cannot be trusted for anything downstream.
