# Results Summary

- source: `studies/04-fremtpl2-frequency/results.tsv`
- metric column: `primary_metric`
- metric name: `val_poisson_deviance`
- track: `primary`
- minimum delta: 0.001786 (= 8.5x measured seed std 0.000210143, k=5)
- goal: `lower`
- total experiments: 6
- keep: 3
- discard: 3
- crash: 0

## Overview

- baseline metric: 0.454861
- best metric: 0.444689
- total improvement: 0.010172 (48.4x noise-floor std)
- best commit: `116fd1b0da805e2ed4e536cfffebfd23b237902c`
- best description: HGBT poisson baseline (OHE, seed 0, lr .1, 200 iters) — RQ1: prediction >=3x floor; frontier improvement over 0.453073 with minimum_delta=0.001786

## Frontier

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| E0001 | `093f398748bcd24f9a974a98efa6f66443de7907` | 0.454861 | keep | GLM baseline (OHE): anchor asserts null-deviance identity, then plain PoissonRegressor; first valid result on this track |
| E0002 | `251f119696b1c60e019aeb0ecfffd6c571bd9fe7` | 0.453073 | keep | GLM + shaping: log-density + cubic splines on standardized numerics — RQ2; frontier improvement over 0.454861 with minimum_delta=0.001786 |
| E0003 | `116fd1b0da805e2ed4e536cfffebfd23b237902c` | 0.444689 | keep | HGBT poisson baseline (OHE, seed 0, lr .1, 200 iters) — RQ1: prediction >=3x floor; frontier improvement over 0.453073 with minimum_delta=0.001786 |

## Recent Runs

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| E0001 | `093f398748bcd24f9a974a98efa6f66443de7907` | 0.454861 | keep | GLM baseline (OHE): anchor asserts null-deviance identity, then plain PoissonRegressor; first valid result on this track |
| E0002 | `251f119696b1c60e019aeb0ecfffd6c571bd9fe7` | 0.453073 | keep | GLM + shaping: log-density + cubic splines on standardized numerics — RQ2; frontier improvement over 0.454861 with minimum_delta=0.001786 |
| E0003 | `116fd1b0da805e2ed4e536cfffebfd23b237902c` | 0.444689 | keep | HGBT poisson baseline (OHE, seed 0, lr .1, 200 iters) — RQ1: prediction >=3x floor; frontier improvement over 0.453073 with minimum_delta=0.001786 |
| E0004 | `4693d77a62e2799c7c8e1387ec270dc20e9919b7` | 0.445343 | discard | HGBT native categoricals vs OHE — RQ3: prediction within 2x floor (discard); did not improve track frontier 0.444689 by minimum_delta=0.001786 |
| E0005 | `78ab8c5fb6f62e63a35142b5be95c8c165b61ac1` | 0.444689 | discard | HGBT capacity probe: max_leaf_nodes 31 -> 63 — expect small; decided by the paired floor; did not improve track frontier 0.444689 by minimum_delta=0.001786 |
| E0006 | `237507c20adeaff1aaf82d128d3aff587cc1f1b9` | 0.449667 | discard | sealed confirmation: incumbent hgbt_ohe on the untouched test fold; sealed final-test evidence; excluded from the adaptive frontier |

## Phase Telemetry

| Phase | Experiments (used/max) | Seconds (used/budget) | Status |
| --- | --- | --- | --- |
| adaptive-1 | 5/5 | 22.3/3600 | within budget |
| confirmation | 1/1 | 3.8/600 | within budget |

