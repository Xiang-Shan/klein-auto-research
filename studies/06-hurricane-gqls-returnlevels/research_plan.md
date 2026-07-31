# Research plan — 06-hurricane-gqls-returnlevels

## Question

On the 30 most-damaging US hurricanes (Pielke-Landsea 1998, normalized 1995 USD),
does a from-scratch gQLS reproduce Adjieteh (2024) Table 6.9 within the published
reporting resolution; does its robustness advantage over MLE survive the thesis's
10× contamination and leave-top-k-out stress; and does that advantage carry into
per-event return levels — the thesis's own §7.2 declared future work?

## Lineage

Sequel to `02-rqls-pv-severity` (archived at tag v1.0.0): the robust-quantile
estimator family was studied there on SYNTHETIC known-truth severity ("the wind
tunnel": clean-data robustness cost 1.083×; 10% contamination exploded naive-MLE
premium error 352% vs 50% trimmed). This study takes the method to the REAL data
of the thesis that anchors the family, reproduces its published tables, stresses
beyond them, and extends into decision units. knowledge/method_cards/
quantile-least-squares.md carries study 02's promoted knowledge — extended, not
duplicated, by this study's method card.

## Contract

- Data: `hurricane_top30_pl1998` (data_hub + bundled copy — the repo's most
  reproducible exhibit; 30 rows IS the dataset). Fit on log-dollars (×1e9).
  Identity gate: six Table-6.8 statistics exact under Hazen quantiles + ddof=1.
- Tracks: `reproduction` (primary `mean_abs_param_deviation` over the 36
  published Table-6.9 parameters; guardrails max|Δθ| ≤ 0.02, max|ΔW| ≤ 0.10,
  max|Δp| ≤ 0.02 — the mean gives a fixable frontier, the max stops one broken
  cell hiding) and `decision` (primary `return_level_instability_pct` = max |%Δ|
  of the fitted 1-in-100 event loss across the adaptive stress set; guardrail
  `w_pvalue ≥ 0.10` blocks the degenerate predict-nothing winner — "among models
  that FIT, which gives the most stable 1-in-100").
- Sealed evidence = pre-registered THIRD-PARTY PUBLISHED truth (unusually
  strong): reproduction → the full Table 6.10 grid (MLE/o2/o3/g2/g3 arms,
  original AND modified — adaptive work touches Table 6.9 only); decision → the
  thesis's exact 10× modification (72.303 → 723.03 — adaptive work uses only
  leave-top-k-out and a 5× perturbation).
- Floors (adaptive-1, measured): reproduction — numerical (solver-route, expect
  ≈1e-12: recording ≈0 IS the finding, every disagreement is a modeling choice),
  reporting resolution 0.005, and the QUANTILE-CONVENTION sweep k=5
  (linear/hazen/weibull/median_unbiased/normal_unbiased — predicted to GOVERN:
  at n=30 the dominant reproduction uncertainty is which definition of a
  quantile you use); decision — paired bootstrap of the 30 events, B=1000 in
  5×200 blocks, CRN, minimum_delta = 2×SE.
- Runtime: every fit is a 2-parameter GLS solve on 8 points — microseconds;
  max_run_seconds 180 is generous.

## Experiment ladder

adaptive-1 (1 slot): E0001 data-identity anchor + single-cell gQLS lognormal
(0.05,0.95) within 0.005 of published 22.79/0.82 — STOP on miss. Then the two
floor sweeps (off-ledger measurement), delta update, consult re-record.

adaptive-2 (4): E0002 full 18-cell gQLS grid (mean|Δθ| ≤ 0.01); E0003 GoF
reimplementation (W ~ χ²₆ to ≤0.10; W_out bootstrap-vs-χ²₂₃ redundancy ≤0.02);
E0004 oQLS+MLE arms on original data (Σ★ falsifier: o2-vs-g2 log-Cauchy);
E0005 k ∈ {8,10,15,25} and convention sensitivity (estimates move less than
resolution across k, MORE across conventions).

adaptive-3 (4): E0006 MLE-lognormal 1-in-100 under leave-top-1-out (>40%
predicted); E0007 gQLS log-Cauchy instability (< ⅓ of MLE predicted — genuinely
uncertain, tan(0.49π) ≈ 31.8 amplification; refutation = the seminar punchline);
E0008 lighter-tailed GoF-passing families (fit quality vs decision stability are
different axes); E0009 instability vs breakdown point across the three trims.

confirmation (2): E0010 reproduction sealed vs the full Table 6.10 grid;
E0011 decision sealed vs the exact 10× modification.

Return levels reported at 1-in-10/25/100 with the extrapolation caveat (the
empirical support of 30 events tops out near 1-in-30).

## Deliverables

findings.md · report/index.html · verdict_card.md (ADOPT-FOR / DO-NOT-ADOPT-FOR,
claim-cited) · committed reference/thesis_tables.json · figures: return-level
dumbbell ($bn, clean → sealed-contaminated, GoF-passing rows only), 18-cell
reproduction scorecard vs the resolution floor, six Q-Q panels (thesis Fig. 6.8
visual reproduction), decision trajectories. These feed the CAS deck (2026-08-28)
but the study stands alone.

## Honest-no outcomes (pre-registered as valid findings)

- Log-Cauchy cells unreproducible → "the Σ★ specification is under-determined at
  extreme trims; here is exactly which choice is missing" — a documented
  reject-input, not a failure.
- gQLS log-Cauchy decision-UNSTABLE despite parameter robustness → "robust
  parameters ≠ robust decisions; the quantile transform undoes it" — arguably
  the most useful possible outcome for a pricing audience.
- W_out bootstrap NOT redundant → the thesis's computational caution was
  warranted; RQ2 flips to a validation of their choice.
