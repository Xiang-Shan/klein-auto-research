# Results Summary

- source: `studies/02-rqls-pv-severity/results.tsv`
- metric column: `primary_metric`
- goal: `lower`
- total experiments: 7
- keep: 7
- discard: 0
- crash: 0

## Overview

- baseline metric: 4.278819
- best metric: 4.278819
- total improvement: 0.000000
- best commit: `762e77d`
- best description: E1 truth-gate PASS: naive MLE unbiased on single-family lognormal n=2000x200reps

## Frontier

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| 1 | `762e77d` | 4.278819 | keep | E1 truth-gate PASS: naive MLE unbiased on single-family lognormal n=2000x200reps |

## Recent Runs

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| 1 | `762e77d` | 4.278819 | keep | E1 truth-gate PASS: naive MLE unbiased on single-family lognormal n=2000x200reps |
| 2 | `57e503e` | 4.458722 | keep | E2 efficiency eps=0: QLS-OLS 4.459% = 1.083x MLE floor 4.116%; GLS 1.123x, MTM 1.219x; 1000 reps |
| 3 | `72d9c8b` | 49.969892 | keep | E3 breakdown sweep 20 cells x 500 reps (sweeps/e3_breakdown.sidecar.tsv); reported trimmed-QLS-OLS@eps=10%; MLE 352% vs QLS 50% |
| 4 | `4a36b4e` | 4.834350 | keep | E4 trunc+cens recovery: window-QLS 4.834% ~= floor, trunc-MLE 4.680%; naive param bias huge but premium -5.2% (prior >20% falsified); 500 reps |
| 5 | `c006944` | 18.783886 | keep | E5 realistic cell: qls_window_trim 18.78% (-18.6 signed); mle_tc 7.85% best; ablation window>>trim (trim deletes hail tail); 500 reps |
| 6 | `e57c799` | 25.813827 | keep | E6 tail mode: blind-QLS 25.81% vs aware 27.96% (POT hurts, xi_hat 0.22 vs 0.4); truth tail delta only +0.17% (capped layer); 500 reps |
| 7 | `bfdef87` | 18.783886 | keep | E7 decision table 20 cells x 500 reps (sweeps/e7_decision.sidecar.tsv); reported qls_window_trim@eps=5 reproduces E5; misspecification floor ~23% |

## Phase Telemetry

| Phase | Experiments | Budget (h) | Actual (h) | Status |
| --- | --- | --- | --- | --- |
| 0 | 1-1 | 0.30 | 0.00 | under budget |
| 1 | 2-4 | 1.00 | 0.03 | under budget |
| 2 | 5-7 | 1.00 | 0.06 | under budget |

