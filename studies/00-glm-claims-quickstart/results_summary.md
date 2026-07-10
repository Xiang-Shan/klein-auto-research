# Results Summary

- source: `studies/00-glm-claims-quickstart/results.tsv`
- metric column: `primary_metric`
- goal: `higher`
- total experiments: 6
- keep: 6
- discard: 0
- crash: 0

## Overview

- baseline metric: 0.625462
- best metric: 0.664322
- total improvement: 0.038860
- best commit: `3f3822f`
- best description: HGBT learning_rate sweep via kleinlib.sweep.SweepRunner: 5 trials {0.03,0.06,0.1,0.15,0.2} on exp-3's exact preprocessing/drops (OHE min_freq=20, drop 7 model-derivative cols, class_weight=balanced), see sweeps/hgbt_lr.sidecar.tsv; winner learning_rate=0.06 val_auc=0.664322, +0.001425 vs exp-3 baseline 0.662897; NEW study best (models/best_6_0.6643.pkl)

## Frontier

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| 1 | `7c3a25b` | 0.625462 | keep | split-identity anchor: LR+OHE(min_freq=20)+cw=balanced, seed42/0.2/stratified; GATE |0.625462-0.6255|=0.000038<=0.001 PASS; brier=0.240153 logloss=0.672617 |
| 2 | `ae552d5` | 0.625533 | keep | Phase-1 LR: splines(5,3)+log1p(density)+2 interactions+isotonic(cv=3), cw=balanced; RECONSTRUCTED (exp40-48 all discard in campaign, no commit survived); target 0.6528 missed by -0.027, ceiling found ~0.641 across 7 tried variants; brier=0.059307 logloss=0.232177 near-matches campaign's own reported 0.059/0.229 |
| 3 | `b1389ca` | 0.662897 | keep | campaign Phase-0 HGBT: OHE(min_freq=20)+drop 7 model-derivative cols+shrinkage(lr=0.05,max_iter=500,leaf=31,early_stopping); cw=balanced; recovered verbatim via git show exp6+exp7; GATE-tight |0.662897-0.6629|=0.000003; brier=0.222561 logloss=0.631887 lift10=2.04 |
| 6 | `3f3822f` | 0.664322 | keep | HGBT learning_rate sweep via kleinlib.sweep.SweepRunner: 5 trials {0.03,0.06,0.1,0.15,0.2} on exp-3's exact preprocessing/drops (OHE min_freq=20, drop 7 model-derivative cols, class_weight=balanced), see sweeps/hgbt_lr.sidecar.tsv; winner learning_rate=0.06 val_auc=0.664322, +0.001425 vs exp-3 baseline 0.662897; NEW study best (models/best_6_0.6643.pkl) |

## Recent Runs

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| 1 | `7c3a25b` | 0.625462 | keep | split-identity anchor: LR+OHE(min_freq=20)+cw=balanced, seed42/0.2/stratified; GATE |0.625462-0.6255|=0.000038<=0.001 PASS; brier=0.240153 logloss=0.672617 |
| 2 | `ae552d5` | 0.625533 | keep | Phase-1 LR: splines(5,3)+log1p(density)+2 interactions+isotonic(cv=3), cw=balanced; RECONSTRUCTED (exp40-48 all discard in campaign, no commit survived); target 0.6528 missed by -0.027, ceiling found ~0.641 across 7 tried variants; brier=0.059307 logloss=0.232177 near-matches campaign's own reported 0.059/0.229 |
| 3 | `b1389ca` | 0.662897 | keep | campaign Phase-0 HGBT: OHE(min_freq=20)+drop 7 model-derivative cols+shrinkage(lr=0.05,max_iter=500,leaf=31,early_stopping); cw=balanced; recovered verbatim via git show exp6+exp7; GATE-tight |0.662897-0.6629|=0.000003; brier=0.222561 logloss=0.631887 lift10=2.04 |
| 4 | `2e046bb` | 0.622859 | keep | doctrine smoke: E1 config with cw=None+isotonic(cv=3) instead of cw=balanced; val_auc delta=-0.002603 vs E1 (within +/-0.003); brier 0.240153->0.059279 (~4x better), logloss 0.672617->0.232385 (~3x better) -- RQ2 calibration-first doctrine confirmed |
| 5 | `1fb8ca6` | 0.651707 | keep | E2-redux: git-recovered TRUE base (campaign exp1 5a70203, last LR-family keep before Phase-1 spline block, all of exp9-48 discard/uncommitted) + exp40-47 delta chain: splines(5knots,deg3,quantile,no-bias) on subscription_length/vehicle_age/customer_age + log1p(region_density) + 2 interactions(density*vage, sublen*vage) + isotonic-calibrated LR cv=5 (per campaign's own best_practices doc, not cv=3); val_auc=0.651707 vs target 0.6528 (delta=-0.0011, within +/-0.003 GATE); vs exp2 delta=+0.0262; brier=0.058960 logloss=0.229111 near-matches campaign's reported exp47 0.059/0.229 |
| 6 | `3f3822f` | 0.664322 | keep | HGBT learning_rate sweep via kleinlib.sweep.SweepRunner: 5 trials {0.03,0.06,0.1,0.15,0.2} on exp-3's exact preprocessing/drops (OHE min_freq=20, drop 7 model-derivative cols, class_weight=balanced), see sweeps/hgbt_lr.sidecar.tsv; winner learning_rate=0.06 val_auc=0.664322, +0.001425 vs exp-3 baseline 0.662897; NEW study best (models/best_6_0.6643.pkl) |

## Aux Panels

### val_brier (lower) — top 10

| Run | Commit | val_brier | primary_metric | Status | Description |
| --- | --- | --- | --- | --- | --- |
| 5 | `1fb8ca6` | 0.058960 | 0.651707 | keep | E2-redux: git-recovered TRUE base (campaign exp1 5a70203, last LR-family keep before Phase-1 spline block, all of exp9-48 discard/uncommitted) + exp40-47 delta chain: splines(5knots,deg3,quantile,no-bias) on subscription_length/vehicle_age/customer_age + log1p(region_density) + 2 interactions(density*vage, sublen*vage) + isotonic-calibrated LR cv=5 (per campaign's own best_practices doc, not cv=3); val_auc=0.651707 vs target 0.6528 (delta=-0.0011, within +/-0.003 GATE); vs exp2 delta=+0.0262; brier=0.058960 logloss=0.229111 near-matches campaign's reported exp47 0.059/0.229 |
| 4 | `2e046bb` | 0.059279 | 0.622859 | keep | doctrine smoke: E1 config with cw=None+isotonic(cv=3) instead of cw=balanced; val_auc delta=-0.002603 vs E1 (within +/-0.003); brier 0.240153->0.059279 (~4x better), logloss 0.672617->0.232385 (~3x better) -- RQ2 calibration-first doctrine confirmed |
| 2 | `ae552d5` | 0.059307 | 0.625533 | keep | Phase-1 LR: splines(5,3)+log1p(density)+2 interactions+isotonic(cv=3), cw=balanced; RECONSTRUCTED (exp40-48 all discard in campaign, no commit survived); target 0.6528 missed by -0.027, ceiling found ~0.641 across 7 tried variants; brier=0.059307 logloss=0.232177 near-matches campaign's own reported 0.059/0.229 |
| 3 | `b1389ca` | 0.222561 | 0.662897 | keep | campaign Phase-0 HGBT: OHE(min_freq=20)+drop 7 model-derivative cols+shrinkage(lr=0.05,max_iter=500,leaf=31,early_stopping); cw=balanced; recovered verbatim via git show exp6+exp7; GATE-tight |0.662897-0.6629|=0.000003; brier=0.222561 logloss=0.631887 lift10=2.04 |
| 6 | `3f3822f` | 0.222681 | 0.664322 | keep | HGBT learning_rate sweep via kleinlib.sweep.SweepRunner: 5 trials {0.03,0.06,0.1,0.15,0.2} on exp-3's exact preprocessing/drops (OHE min_freq=20, drop 7 model-derivative cols, class_weight=balanced), see sweeps/hgbt_lr.sidecar.tsv; winner learning_rate=0.06 val_auc=0.664322, +0.001425 vs exp-3 baseline 0.662897; NEW study best (models/best_6_0.6643.pkl) |
| 1 | `7c3a25b` | 0.240153 | 0.625462 | keep | split-identity anchor: LR+OHE(min_freq=20)+cw=balanced, seed42/0.2/stratified; GATE |0.625462-0.6255|=0.000038<=0.001 PASS; brier=0.240153 logloss=0.672617 |

### val_lift_top10 (higher) — top 10

| Run | Commit | val_lift_top10 | primary_metric | Status | Description |
| --- | --- | --- | --- | --- | --- |
| 3 | `b1389ca` | 2.041568 | 0.662897 | keep | campaign Phase-0 HGBT: OHE(min_freq=20)+drop 7 model-derivative cols+shrinkage(lr=0.05,max_iter=500,leaf=31,early_stopping); cw=balanced; recovered verbatim via git show exp6+exp7; GATE-tight |0.662897-0.6629|=0.000003; brier=0.222561 logloss=0.631887 lift10=2.04 |
| 6 | `3f3822f` | 2.001537 | 0.664322 | keep | HGBT learning_rate sweep via kleinlib.sweep.SweepRunner: 5 trials {0.03,0.06,0.1,0.15,0.2} on exp-3's exact preprocessing/drops (OHE min_freq=20, drop 7 model-derivative cols, class_weight=balanced), see sweeps/hgbt_lr.sidecar.tsv; winner learning_rate=0.06 val_auc=0.664322, +0.001425 vs exp-3 baseline 0.662897; NEW study best (models/best_6_0.6643.pkl) |
| 5 | `1fb8ca6` | 1.788040 | 0.651707 | keep | E2-redux: git-recovered TRUE base (campaign exp1 5a70203, last LR-family keep before Phase-1 spline block, all of exp9-48 discard/uncommitted) + exp40-47 delta chain: splines(5knots,deg3,quantile,no-bias) on subscription_length/vehicle_age/customer_age + log1p(region_density) + 2 interactions(density*vage, sublen*vage) + isotonic-calibrated LR cv=5 (per campaign's own best_practices doc, not cv=3); val_auc=0.651707 vs target 0.6528 (delta=-0.0011, within +/-0.003 GATE); vs exp2 delta=+0.0262; brier=0.058960 logloss=0.229111 near-matches campaign's reported exp47 0.059/0.229 |
| 4 | `2e046bb` | 1.761353 | 0.622859 | keep | doctrine smoke: E1 config with cw=None+isotonic(cv=3) instead of cw=balanced; val_auc delta=-0.002603 vs E1 (within +/-0.003); brier 0.240153->0.059279 (~4x better), logloss 0.672617->0.232385 (~3x better) -- RQ2 calibration-first doctrine confirmed |
| 1 | `7c3a25b` | 1.667948 | 0.625462 | keep | split-identity anchor: LR+OHE(min_freq=20)+cw=balanced, seed42/0.2/stratified; GATE |0.625462-0.6255|=0.000038<=0.001 PASS; brier=0.240153 logloss=0.672617 |
| 2 | `ae552d5` | 1.574543 | 0.625533 | keep | Phase-1 LR: splines(5,3)+log1p(density)+2 interactions+isotonic(cv=3), cw=balanced; RECONSTRUCTED (exp40-48 all discard in campaign, no commit survived); target 0.6528 missed by -0.027, ceiling found ~0.641 across 7 tried variants; brier=0.059307 logloss=0.232177 near-matches campaign's own reported 0.059/0.229 |


## Phase Telemetry

| Phase | Experiments | Budget (h) | Actual (h) | Status |
| --- | --- | --- | --- | --- |
| 0 | 1-4 | 1.00 | 0.02 | under budget |
| 1 | 5-6 | 1.00 | 0.01 | under budget |

