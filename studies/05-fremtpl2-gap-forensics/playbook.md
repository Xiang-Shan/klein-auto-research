# Playbook — 05-fremtpl2-gap-forensics

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| glm | E0002 | 0.454861 | PoissonRegressor α=1e-4, OHE, exposure-weighted rate | 2026-07-31 |
| gbdt | E0003 | 0.444689 | HGBT poisson, OHE, lr .1, nominal 200 iters (effective 67 — early stopping) | 2026-07-31 |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| Guardrail metrics via aux-tsv only | E0001 | wall_seconds must be PRINTED (extra) — runner reads the printed block; F1 in program.md |
| LGBM as a better GBDT here | E0005 | 0.444413 = 0.48× floor better than HGBT — a tie, even at 200 vs 67 effective trees (conservative) |
| CatBoost CTR+symmetric package | E0006 | 0.446332 = +2.9× floor deficit at cardinality ≤22 — does not pay |
| Raw-product interactions into the GLM | E0007, E0008 | best pair 0.43× floor, both pairs 0.45× floor — sub-floor; screened 10, adopted 0 |
| RQ4's 30–45% closure prior | E0004 | scoped splines close 16.8% (≈ study-04's leaky 17.6%) — additive shaping tops out ~17% |
| M4-a "gap is mostly additive" | forensics | surrogate R²_main 0.66 < 0.90 — the gap IS non-additive |
| M4-b "DrivAge×BonusMalus first" | forensics | ranks 8/10; VehAge×BonusMalus (0.154) and BM×logDensity (0.099) lead |
| M5-a concentration prior | forensics | gap is DIFFUSE: BM top-3 bins = 87% of gap on 89% of exposure (proportional, not localized) |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| RQ1 | sealed gap within 2 sealed-paired SEs of dev gap 0.010172 | yes | confirmation NOW: E0011 glm sealed (incumbent E0004 scoped splines), E0012 gbdt sealed (incumbent E0003 hgbt_ohe) + off-ledger join |

## Closed this phase (adaptive-3 + off-ledger)

RQ7 REFUTED: monotone BM costs 3.7× floor vs same-encoding control (E0009) —
because BM is monotone on the MARGIN (100% of exposure, M3-a) but not in
conditioning contexts (VehAge×BM, surrogate rank 1). M1-b CONFIRMED: LGBM ties
HGBT at matched-67 AND 200 trees (E0010, E0005). RQ6 CONFIRMED: crossover
20–40k rows; GLM WINS at ~20k (gap −0.0019); gap grows monotonically to 0.0102
at 678k (data_volume sidecar).

## Waterfall (dev fold — the study's central artifact, pending sealed confirmation)

anchor 0.454861 → +scoped splines 0.453156 (16.8% of gap, 3.2× floor, KEEP) →
[+products: sub-floor, rejected ×2] → HGBT 0.444689. **Irreducible non-additive
residue ≈ 83% of the gap**; corroborated by surrogate R²_main 0.66 and the
diffuse M5 profile. GLM ceiling = E0004.

## Metrology (fixed — cite, don't remeasure)

- glm minimum_delta 0.000539 (2× paired SE; fit-seed floor EXACTLY 0 — deterministic solver, itself a finding)
- gbdt minimum_delta 0.000573 (max of 2× fit-seed 0.000420, 2× paired 0.000573)
- Headline-gap band: cross paired SE 0.000963 → dev gap +0.010172 = 10.6× SE (study 04 said 11.4× with its block-1-like SE 0.000893 — consistent)
- Three floors differ: 0 (glm seed) / 0.000210 (gbdt seed) / 0.000963 (cross paired) — the 25×-spread lesson, now per-track

## Next-best candidates (ranked — adaptive-3)

1. [gbdt] hgbt_monotone (RQ7; cost vs incumbent 0.444689 AND vs study-04 native 0.445343 — encoding confound stated)
2. [gbdt] lgbm_poisson n_estimators=67 (M1-b matched effective capacity)
3. (slot spare — confirmation follows)
