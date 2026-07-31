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

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| RQ2/M1 | LGBM ≈ HGBT at matched capacity — but E0003 shows HGBT stops at 67 effective trees vs LGBM's full 200; pre-loop delta −0.000276 = 0.96× paired SE | tie survives capacity accounting | E: lgbm_poisson candidate; verdict must cite effective_trees; M1-b if it breaks |
| RQ3/M2 | CatBoost CTR+symmetric package loses ~0.92× provisional floor at cardinality ≤22 (pre-loop 0.446332) | no pay | E: catboost_poisson candidate; M2-a isolation only if surprising |
| RQ4 | Scoped splines close ≥30% of gap — pre-loop signal says only ~16.8% (0.001705/0.010172), BELOW the leaky study-04 version's 18% | prior now DOUBTED — honest-no candidate | E: glm_scoped_splines candidate (formal); then surrogate interactions are the main hope for closure |
| RQ5 | +2 surrogate interactions add ≥2× glm floor | uninformed | forensics.surrogate_glm on train fold (off-ledger) → top pair into glm_interactions |
| RQ7/M3 | monotone BonusMalus costs <1× gbdt floor | cheap | E in adaptive-3; control = study-04 E0004 native 0.445343 (+ in-study native control if close) |
| RQ6 | gap collapses below 2× paired floor only under ~10-15% train | uninformed | sweeps/data_volume.py (measurement, off-ledger) |

## Metrology (fixed this phase — cite, don't remeasure)

- glm minimum_delta 0.000539 (2× paired SE; fit-seed floor EXACTLY 0 — deterministic solver, itself a finding)
- gbdt minimum_delta 0.000573 (max of 2× fit-seed 0.000420, 2× paired 0.000573)
- Headline-gap band: cross paired SE 0.000963 → dev gap +0.010172 = 10.6× SE (study 04 said 11.4× with its block-1-like SE 0.000893 — consistent)
- Three floors differ: 0 (glm seed) / 0.000210 (gbdt seed) / 0.000963 (cross paired) — the 25×-spread lesson, now per-track

## Next-best candidates (ranked — adaptive-2 slate to be scored at phase start)

1. [gbdt] lgbm_poisson formal run (RQ2; cite effective_trees 67 vs ~200)
2. [gbdt] catboost_poisson formal run (RQ3; wording = CTR+symmetric package)
3. [glm] glm_scoped_splines formal run (RQ4; prior doubted — either verdict informs)
4. [glm] glm_interactions with top surrogate pair (RQ5; provenance in description)
5. [glm] glm_interactions second pair + binned BM (RQ5 ceiling)
