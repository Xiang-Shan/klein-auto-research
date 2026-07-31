# Results Summary

- source: `studies/05-fremtpl2-gap-forensics/results.tsv`
- metric column: `primary_metric`
- metric name: `val_poisson_deviance`
- track: `gbdt`
- minimum delta: 0.000573 (= 2.7x measured seed std 0.000210143, k=5)
- goal: `lower`
- total experiments: 6
- keep: 1
- discard: 5 (of which 1 sealed final-test confirmation)
- crash: 0

## Overview

- baseline metric: 0.444689
- best metric: 0.444689
- total improvement: 0.000000 (0.0x noise-floor std)
- best commit: `9e25b0692d9d5cbf06f3836515ee4fe0e573e60a`
- best description: HGBT-OHE anchor (seed 0, lr 0.1, 200 iters, 31 leaves): registry val_poisson_deviance must reproduce study-04's 0.444689 to 1e-9; effective_trees logged per method-card R1 (early_stopping auto engages >10k rows); first valid result on this track

## Frontier

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| E0003 | `9e25b0692d9d5cbf06f3836515ee4fe0e573e60a` | 0.444689 | keep | HGBT-OHE anchor (seed 0, lr 0.1, 200 iters, 31 leaves): registry val_poisson_deviance must reproduce study-04's 0.444689 to 1e-9; effective_trees logged per method-card R1 (early_stopping auto engages >10k rows); first valid result on this track |

## Recent Runs

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| E0003 | `9e25b0692d9d5cbf06f3836515ee4fe0e573e60a` | 0.444689 | keep | HGBT-OHE anchor (seed 0, lr 0.1, 200 iters, 31 leaves): registry val_poisson_deviance must reproduce study-04's 0.444689 to 1e-9; effective_trees logged per method-card R1 (early_stopping auto engages >10k rows); first valid result on this track |
| E0005 | `336b4054732518e1b879db23761d9a038b73ea03` | 0.444413 | discard | RQ2/M1: LightGBM poisson at nominal-matched config (31 leaves, lr .1, 200 rounds) lands within 2x gbdt floor 0.000573 of HGBT 0.444689 - tie predicted DISCARD; capacity confound acknowledged: HGBT effective_trees=67 (early stopping) vs LGBM full 200; M1-b matched-capacity lever fires in adaptive-3 only if this breaks the tie; did not improve track frontier 0.444689 by minimum_delta=0.000573 |
| E0006 | `d1285986164e88736ef4cebc9b57f5608fbc4abb` | 0.446332 | discard | RQ3/M2: CatBoost Poisson (CTR categorical statistics + symmetric trees, boosting_type=Plain on CPU, depth 6, 200 iters, Exponent predictions) vs HGBT-OHE incumbent at cardinality <=22 (Region 22, VehBrand 11): prior says NO pay - pre-loop deficit +0.001643 = 2.9x gbdt floor; wording per method-card R3: this tests the CTR+symmetric package, NOT ordered boosting; did not improve track frontier 0.444689 by minimum_delta=0.000573 |
| E0009 | `b87d6a5e470e6db69fd2fdf4370ef5cd4810460f` | 0.447455 | discard | RQ7/M3: monotone +1 BonusMalus on the NATIVE-categorical HGBT. Constraint cost read TWO ways per method-card R2: vs same-encoding unconstrained control (study-04 E0004 native 0.445343, tag v1.0.0, same split/prep) and vs the OHE incumbent 0.444689 (total cost incl. encoding). Prediction: constraint component < 1x gbdt floor 0.000573 - filability nearly free; did not improve track frontier 0.444689 by minimum_delta=0.000573 |
| E0010 | `35c5de935ca29f9f4698db6a7a6548e33011ba1d` | 0.444431 | discard | M1-b: LightGBM poisson at n_estimators=67 - matched to HGBT's EFFECTIVE capacity (E0003 early-stopped at 67 trees). Prediction: |delta| vs 0.444689 stays < 2x gbdt floor 0.000573 -> the RQ2 tie is algorithmic, not an early-stopping artefact; did not improve track frontier 0.444689 by minimum_delta=0.000573 |
| E0012 | `bf7677d47c0b15aa8315157574d323411da0834c` | 0.449667 | discard | sealed confirmation of the gbdt incumbent (E0003 hgbt_ohe, seed 0, lr .1, nominal 200 iters) + holdout prediction export for the off-ledger sealed-gap computation; sealed final-test evidence; excluded from the adaptive frontier |

## Phase Telemetry

| Phase | Experiments (used/max) | Seconds (used/budget) | Status |
| --- | --- | --- | --- |
| adaptive-1 | 3/3 | 8.9/1800 | within budget |
| adaptive-2 | 5/5 | 18.0/3600 | within budget |
| adaptive-3 | 2/3 | 5.5/2400 | within budget |
| confirmation | 2/2 | 6.9/900 | within budget |

