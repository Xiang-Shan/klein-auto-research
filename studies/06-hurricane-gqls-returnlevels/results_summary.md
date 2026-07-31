# Results Summary

- source: `studies/06-hurricane-gqls-returnlevels/results.tsv`
- metric column: `primary_metric`
- metric name: `return_level_instability_pct`
- track: `decision`
- minimum delta: 1 (= 9.6x measured seed std 0.104, k=5)
- goal: `lower`
- total experiments: 5
- keep: 3
- discard: 2 (of which 1 sealed final-test confirmation)
- crash: 0

## Overview

- baseline metric: 58.063948
- best metric: 27.584597
- total improvement: 30.479351 (293.1x noise-floor std)
- best commit: `5e05c8022a7892663a21d448e27a6085ebde32fa`
- best description: RQ4/RQ6: gQLS lognormal at the WIDEST trim (0.10,0.90), breakdown point 0.10 > 3/30 - all three leave-top-k stresses now sit inside the breakdown guarantee (k=3: 0.10 <= 0.10 boundary); prediction: instability monotone decreasing in min{a,1-b}, beating E0008's 41.3 by > 1.0pp, at a GoF cost < 1x the W floor (published W p 0.73 at this trim); frontier improvement over 41.325245 with minimum_delta=1

## Frontier

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| E0006 | `bcc56e2854de8d1e50186653d1a620215e35fcf9` | 58.063948 | keep | RQ5 baseline: MLE-lognormal 1-in-100 instability under the adaptive stress set (leave-top-1/2/3, 5x max) - audit preview says leave-1 alone moves -25.7%; prediction: instability_pct > 40; w_pvalue guardrail from the clean fit; first valid result on this track |
| E0008 | `9a6562f582bdb3baa7143564cb59f1786e9d6d5b` | 41.325245 | keep | RQ6: gQLS lognormal (0.05,0.95) - a GoF-passing family (W p 0.52) with a LIGHT quantile transform (z_0.99 = 2.326, not 31.8): prediction - materially more stable 1-in-100 than both log-Cauchy (62.9) and MLE-lognormal (58.1); trimmed quantile estimation + bounded transform = the robustness that actually reaches the decision; frontier improvement over 58.063948 with minimum_delta=1 |
| E0009 | `5e05c8022a7892663a21d448e27a6085ebde32fa` | 27.584597 | keep | RQ4/RQ6: gQLS lognormal at the WIDEST trim (0.10,0.90), breakdown point 0.10 > 3/30 - all three leave-top-k stresses now sit inside the breakdown guarantee (k=3: 0.10 <= 0.10 boundary); prediction: instability monotone decreasing in min{a,1-b}, beating E0008's 41.3 by > 1.0pp, at a GoF cost < 1x the W floor (published W p 0.73 at this trim); frontier improvement over 41.325245 with minimum_delta=1 |

## Recent Runs

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| E0006 | `bcc56e2854de8d1e50186653d1a620215e35fcf9` | 58.063948 | keep | RQ5 baseline: MLE-lognormal 1-in-100 instability under the adaptive stress set (leave-top-1/2/3, 5x max) - audit preview says leave-1 alone moves -25.7%; prediction: instability_pct > 40; w_pvalue guardrail from the clean fit; first valid result on this track |
| E0007 | `6f91dc8ac14114676d29ebd78060b6cdec4c1a7f` | 62.941400 | discard | RQ5 live question: gQLS log-Cauchy (0.05,0.95) - the best-FITTING family (W p 0.82) whose quantile transform amplifies sigma by tan(0.49pi)=31.8 at p=0.99; registered prediction: instability < 1/3 of MLE-lognormal's (i.e. < 19.4); the metrology floor already warns its 1-in-100 carries a 3.6 log-SE - REFUTATION would be the seminar punchline (robust parameters, unstable decisions); did not improve track frontier 58.063948 by minimum_delta=1 |
| E0008 | `9a6562f582bdb3baa7143564cb59f1786e9d6d5b` | 41.325245 | keep | RQ6: gQLS lognormal (0.05,0.95) - a GoF-passing family (W p 0.52) with a LIGHT quantile transform (z_0.99 = 2.326, not 31.8): prediction - materially more stable 1-in-100 than both log-Cauchy (62.9) and MLE-lognormal (58.1); trimmed quantile estimation + bounded transform = the robustness that actually reaches the decision; frontier improvement over 58.063948 with minimum_delta=1 |
| E0009 | `5e05c8022a7892663a21d448e27a6085ebde32fa` | 27.584597 | keep | RQ4/RQ6: gQLS lognormal at the WIDEST trim (0.10,0.90), breakdown point 0.10 > 3/30 - all three leave-top-k stresses now sit inside the breakdown guarantee (k=3: 0.10 <= 0.10 boundary); prediction: instability monotone decreasing in min{a,1-b}, beating E0008's 41.3 by > 1.0pp, at a GoF cost < 1x the W floor (published W p 0.73 at this trim); frontier improvement over 41.325245 with minimum_delta=1 |
| E0011 | `0f00ed4a73fcd9b02c98f9dd2273df149ab6d36a` | 0.000000 | discard | sealed decision confirmation: the incumbent (gQLS lognormal, trim (0.10,0.90)) under the thesis's EXACT 10x modification (72.303 -> 723.03) - the one contamination never used adaptively (adaptive stress capped at 5x); MLE-lognormal moves +99.4% under this same stress per the audit preview; the incumbent's trimmed quantiles are predicted to sit at 0.0%; sealed final-test evidence; excluded from the adaptive frontier |

## Phase Telemetry

| Phase | Experiments (used/max) | Seconds (used/budget) | Status |
| --- | --- | --- | --- |
| adaptive-1 | 1/1 | 0.6/1800 | within budget |
| adaptive-2 | 4/4 | 3.5/3600 | within budget |
| adaptive-3 | 4/4 | 2.4/3600 | within budget |
| confirmation | 2/2 | 1.2/900 | within budget |

