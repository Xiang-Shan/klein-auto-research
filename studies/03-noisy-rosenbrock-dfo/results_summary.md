# Results Summary

- source: `studies/03-noisy-rosenbrock-dfo/results.tsv`
- metric column: `primary_metric`
- metric name: `mean_final_gap`
- track: `primary`
- minimum delta: 0.569532 (= 2.0x measured seed std 0.284766, k=5)
- goal: `lower`
- total experiments: 6
- keep: 2
- discard: 3
- crash: 1

## Overview

- baseline metric: 1.251208
- best metric: 0.407072
- total improvement: 0.844136 (3.0x noise-floor std)
- best commit: `350fc3557c3acea5c375e551de047a3469fb6f81`
- best description: 4 restarts x 50 evals, same 200-eval budget — RQ1: must clear minimum_delta 0.5695; the honest bar is also random-search 0.397; frontier improvement over 1.251208 with minimum_delta=0.569532

## Frontier

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| E0001 | `2dabc272fd596d91d3b38ba4126b06912c2907d4` | 1.251208 | keep | anchor: single-start Nelder-Mead, budget 200, dev block — must reproduce the prepared reference cell to 1e-9; first valid result on this track |
| E0003 | `350fc3557c3acea5c375e551de047a3469fb6f81` | 0.407072 | keep | 4 restarts x 50 evals, same 200-eval budget — RQ1: must clear minimum_delta 0.5695; the honest bar is also random-search 0.397; frontier improvement over 1.251208 with minimum_delta=0.569532 |

## Recent Runs

| Run | Commit | Metric | Status | Description |
| --- | --- | --- | --- | --- |
| E0001 | `2dabc272fd596d91d3b38ba4126b06912c2907d4` | 1.251208 | keep | anchor: single-start Nelder-Mead, budget 200, dev block — must reproduce the prepared reference cell to 1e-9; first valid result on this track |
| E0002 | `ca7d068bcea4126e3786b8768e08472227985948` | 1.251208 | discard | NM adaptive=True (Gao-Han) — calibration probe: prediction says within 2x floor std of the anchor; did not improve track frontier 1.251208 by minimum_delta=0.569532 |
| E0003 | `350fc3557c3acea5c375e551de047a3469fb6f81` | 0.407072 | keep | 4 restarts x 50 evals, same 200-eval budget — RQ1: must clear minimum_delta 0.5695; the honest bar is also random-search 0.397; frontier improvement over 1.251208 with minimum_delta=0.569532 |
| E0004 | `569bf832e7a3ed6a57efb9f5f9480541f2df3e9c` | 11155760522900000835037867593246821038466806263430450505544431676982102285133816303625773157367718946962685096575694782418666807315183416408169426909871509134135538322484211140999407634715613593600.000000 | discard | SPSA a0=50 aggressive gains — registered prediction: iterates diverge, objective overflows non-finite, honest crash; did not improve track frontier 0.407072 by minimum_delta=0.569532 |
| E0005 | `a9197c54167d90bb701056616ac16fad044ddde9` | n/a | crash | SPSA c0=0 — the estimator's own denominator: registered crash, mechanism corrected after E0004; process exit code 1 |
| E0006 | `8395ce73bae895434031ad97bf59cddc3ddbd754` | 18507098284400000505127373551076521068197799267852249336004572973231362251300864947343537581426479805203950546322114610295760044928520793566253074551862531878622517108014575517696.000000 | discard | SPSA tuned a0=0.1 c0=0.1 — RQ2: prediction says within 2x floor std of restarted NM (discard); did not improve track frontier 0.407072 by minimum_delta=0.569532 |

## Phase Telemetry

| Phase | Experiments (used/max) | Seconds (used/budget) | Status |
| --- | --- | --- | --- |
| adaptive-1 | 6/6 | 4.1/1500 | within budget |
| confirmation | 0/1 | 0.0/300 | untouched |

