---
modality: tabular
status: go-with-cautions
---

# Data card — 23 LaLonde / Dehejia-Wahba causal replication

Recipe `ds-causal`. Audited 2026-11-03 on the PREPARED table
`data/prepared/prepared.csv` (re-profiled after `prepare.py`). Sealed-lane discipline
held: nothing involving `re78` was computed on the CPS-1 (test) lane.

## Source & shape

Three pinned NBER files (Dehejia's data page), each sha256-verified by `klein doctor`
(`pin present=True`, all three cached and pin-verified): `nsw_dw.dta`, `psid_controls.dta`,
`cps_controls.dta`. `prepare.py` keeps the source columns, renames nothing numerical, imputes
and trims nothing, and adds `id` (`<sample>-NNNNN`), `sample`, `partition`.

| Lane (`partition`) | Sample | Rows | Treated | Matches published size |
|---|---|---|---|---|
| train | NSW experimental (DW subsample) | 445 | 185 | yes: 185 treated + 260 controls (DW Table 1) |
| development | PSID-1 | 2,490 | 0 | yes: 2,490 |
| test (SEALED) | CPS-1 | 15,992 | 0 | yes: 15,992 |
| total | | 18,927 | 185 | |

Split: `kind: predefined`, `split_column: partition`; nothing is partitioned by a seed
(`seed: 42` in the contract is inert; the only seed literal in `prepare.py`, `analyze.py`
and `lib/` is `BOOTSTRAP_SEED` for the bootstrap in `lib/lalonde.py`, which does not decide
any partition). Realized fingerprints from `partition_fingerprints(study)`:
development `301cc9c3c8cd5418...`, final_test `b2409a22372d6caee501b263c218947569e4f3b2b827a227c10b0008831680a4`.
Dollars: the files are Dehejia-Wahba's, earnings in 1982 dollars (not rescaled by
`prepare.py`); the PSID-1 `re74`/`re75`/`re78` means ($19,429 / $19,063 / $21,554) and the
CPS-1 `re74`/`re75` means ($14,017 / $13,651) agree with the published DW Table 1 values, a
file-identity check.

## Ranked go / no-go issues

No BLOCKER on the data. One audit-tool defect found at this gate (WARN-1) was fixed in
`kleinlib/leakage.py` before the gate was recorded; the audit now passes.

1. **WARN-1 (resolved at the gate) - the dataframe-mode leakage audit could not reproduce
   this split.** The auditor's run returned `[FAIL] split-reproduces: … task must be explicitly
   'classification' or 'regression'`: `kleinlib/leakage.py:_split_partitions` passed
   `task_type: scalar` to `three_way_split` and had no branch for `kind: predefined`. That was
   a harness defect, not a data defect, and it was fixed in the framework rather than waived
   (lead, 2026-11-03: scalar maps to the regression-shaped split as `contract_split` already
   does; a predefined split reproduces from its column; two regression tests added). The
   re-run below passes 7/7.
2. **WARN-2 - the comparison groups are not comparable to the treated group by construction.**
   Standardized mean differences (NSW treated minus comparison, over pooled SD) are reported in
   the Profile summary; PSID-1 and CPS-1 are off by more than 0.8 SD on 6 of 8 covariates
   (|SMD| up to 2.43 for `black`, 1.84 for `married`, 1.77 for `re75`). This is the reason the
   study exists, not a defect to repair; positivity/overlap and extreme odds weights are the
   expected failure modes of IPW/AIPW here. Nothing is trimmed in `prepare.py`; common support
   is a specification choice in `analyze.py`.
3. **WARN-3 - heavy zero mass and long right tail in earnings.** Zero share in NSW:
   `re74` 73.3%, `re75` 64.9%, `re78` 30.8%. Earnings are non-negative everywhere (min 0, no
   negative or sentinel values), but zeros are real "not working" values, not missing codes. A
   Gaussian or log model of earnings is a specification risk; heavy tails (PSID-1 `re78` max
   $121,174; NSW max $60,308) make means outlier-sensitive.
4. **WARN-4 - small treated n.** 185 treated units; matching/weighting uncertainty is wide.
   Registered tolerances for the reproduction track are +-1 dollar, so a miss may come from
   the standard-error formula rather than the data.
5. **NOTE-1 - within-lane and cross-lane covariate duplicates are expected, not leakage.**
   Full-row duplicates (all 10 outcome and covariate columns) inside lanes: NSW 15, PSID-1 154.
   On CPS-1 only the 9 non-outcome columns were compared (sealed discipline): 2,378 rows repeat
   a covariate vector. Across lanes, identical pre-treatment covariate vectors (8 columns) are
   few: train/development 7, train/test 40, development/test 76 distinct vectors. These are
   coincidences of low-dimensional integer covariates plus many zero earnings, not copied
   people (the files are independent samples; ids are unique). `prepare.py` deliberately does
   not deduplicate, which matches the published estimators. No row id repeats anywhere (0 of
   18,927 duplicated).
6. **NOTE-2 - `re74` is complete for every NSW row.** The DW subsample is defined by it:
   0 nulls in `re74`, `re75`, `re78` in any lane.
7. **NOTE-3 - floats are written with `%.6f`.** Earnings carry cents-level decimals (not
   integers); no precision loss relevant to the +-1 dollar tolerance is expected, but the
   reproduction cell reads the CSV, not the .dta.
8. **NOTE-4 - `treat` is 0 for every development and test row.** Those lanes contain only
   comparison units by design; the treated group is always the NSW treated 185. Modeling
   code must pool NSW treated with the lane's controls; the lanes are not self-contained
   treatment-control datasets.
9. **NOTE-5 - the `id` column is a row label (`nsw-00000` etc.) and carries no information.**
   It encodes sample membership, which equals `partition`; do not use as a feature.

## Go / no-go

Rationale: the three lanes have the exact published sizes, fixed provenance (pinned bytes),
no missingness, no sentinels or string-encoded values, non-negative earnings, no id overlap and
a split realizable from the contract alone (fingerprints printed, index-table audit 8/8 clean).
The substantive hazards (covariate imbalance, zero-heavy earnings, small treated n) are the
object of study and are disclosed as WARN. The one `[FAIL]` (WARN-1) is a tool incompatibility
with `task_type: scalar` in the dataframe mode, traced to the auditor's code path, and is left
as an explicit caution for the lead to accept or fix before recording.

Cautions: (a) the lead records WARN-1 in the gate note or fixes the auditor; (b) CPS-1
`re78` remains unseen until the sealed run; (c) comparison-group imbalance is expected and
must not be "fixed" in `prepare.py`.

## Profile summary

Value-pattern check: every column inspected by VALUE, not dtype. `id`, `sample`, `partition`
are strings (unique ids; 3 sample labels; partitions `train|development|test` only). `treat`,
`black`, `hispanic`, `married`, `nodegree` hold only {0, 1} integers (no `"Yes"/"No"`, no
`-999`, no blanks). `age` and `education` are integers in plausible ranges. `re74`, `re75`,
`re78` are non-negative floats with exact zeros as the "no earnings" value; no negative or
sentinel codes anywhere. Missing values: 0 in every column and lane.

| Lane | n | treated | age (min-max, mean) | educ (mean) | black | hisp | married | nodegree | re74 mean (zero %) | re75 mean (zero %) | re78 mean (zero %) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NSW (train) | 445 | 185 | 17-55, 25.4 | 10.20 | 0.83 | 0.09 | 0.17 | 0.78 | 2,102 (73.3) | 1,377 (64.9) | 5,301 (30.8) |
| PSID-1 (dev) | 2,490 | 0 | 18-55, 34.9 | 12.12 | 0.25 | 0.03 | 0.87 | 0.31 | 19,429 (8.6) | 19,063 (10.0) | 21,554 (11.5) |
| CPS-1 (test, sealed) | 15,992 | 0 | 16-55, 33.2 | 12.03 | 0.07 | 0.07 | 0.71 | 0.30 | 14,017 (12.0) | 13,651 (10.9) | not examined |

Ranges: `re74` max NSW 39,571 / PSID-1 137,149 / CPS-1 25,862; `re75` max 25,143 / 156,653 /
25,244; `re78` max NSW 60,308 / PSID-1 121,174. (CPS-1 `re78`: sealed, not computed.)

NSW treated vs control balance (the experiment itself): re74 SMD 0.00, re75 0.08, age 0.11,
education 0.14, black 0.04, married 0.09, hispanic -0.17, nodegree -0.30 (treated minus control);
largest imbalance is `nodegree`, modest, consistent with randomization in a sample of 445.

Standardized mean differences, NSW treated (n=185) minus comparison lane, pooled-SD
denominator (pre-treatment covariates only):

| Covariate | vs NSW controls | vs PSID-1 | vs CPS-1 |
|---|---|---|---|
| age | 0.11 | -1.01 | -0.80 |
| education | 0.14 | -0.68 | -0.68 |
| black | 0.04 | 1.48 | 2.43 |
| hispanic | -0.17 | 0.13 | -0.05 |
| married | 0.09 | -1.84 | -1.23 |
| nodegree | -0.30 | 0.88 | 0.90 |
| re74 | 0.00 | -1.72 | -1.57 |
| re75 | 0.08 | -1.77 | -1.75 |

NSW treated means: age 25.8, education 10.35, black 0.84, hispanic 0.06, married 0.19,
nodegree 0.71, re74 2,096, re75 1,532.

## Clean-room leakage audit

Read for this audit: `study.yaml`, `prepare.py`, `lib/lalonde.py`, the prepared artifact, the
profile. `program.md` was NOT read for the audit (protocol: its hopes and priors are the context
that makes a leak look plausible); `scouting_ledger.md` was read only for disclosures.

| Row | Check | Verdict | Evidence |
|---|---|---|---|
| 1 | Target leakage | PASS | Target is `re78`. Every other column is pre-program (`re74`, `re75`, demographics) or the treatment indicator, which is the estimand's exposure, not a proxy of the outcome. No derived or post-outcome column; `prepare.py` derives only `id`/`sample`/`partition`. `id` and `partition` encode lane membership only. |
| 2 | Lookahead / fit-on-train | PASS | `prepare.py` fits and imputes nothing; squares, zero flags and propensity scores are made in `analyze.py` per cell. Reviewing `analyze.py` is a METHOD/EXPERIMENT concern, but the card notes the propensity logit must be fit on the lane's own rows by the cell. |
| 3 | Split contamination | PASS | No id appears in two lanes (index-table audit: "no id straddles partitions"); no duplicate row content straddles lanes (dataframe audit); the split reproduces from `study.yaml` alone (fingerprints above). The dataframe-mode tooling defect of WARN-1 was fixed and re-run. |
| 4 | Eval-harness sanity | N/A in this audit | Index mode reports chance rows as N/A; `metric-direction` rows pass for both tracks (`lower` for `targets_outside_tolerance`, `higher` for `att_usd`, scalar family). The constant and label-shuffled predictors are a regression idea; this study's metrics are a reproduction count and a point estimate, and the harness (`lib/lalonde.py`) is audited at METHOD/EXPERIMENT. |

Mechanized output, index-table mode
(`uv run --no-sync python -m kleinlib.leakage --index data/prepared/prepared.csv --study .`):

```
[OK]   index-table: 18927 rows partitioned by the `split` column (train=445 development=2490 test=15992); the index IS the realized split
[OK]   duplicate-rows: no id straddles partitions
[OK]   group-overlap: N/A - the index declares no group column
[OK]   time-order: N/A - the index declares no time column
[OK]   metric-direction[reproduction]: targets_outside_tolerance: contract-declared direction 'lower' accepted (custom metric of the scalar family)
[OK]   chance-level[reproduction]: N/A - index-table mode carries no target or features
[OK]   metric-direction[att]: att_usd: contract-declared direction 'higher' accepted (custom metric of the scalar family)
[OK]   chance-level[att]: N/A - index-table mode carries no target or features
8/8 checks passed: clean
```

Mechanized output, dataframe mode, as first run by the auditor
(`uv run --no-sync python -m kleinlib.leakage data/prepared/prepared.csv --target re78 --study .`):

```
[FAIL] split-reproduces: declared split does not reproduce: task must be explicitly 'classification' or 'regression'
0/1 checks passed: 1 FAIL - any FAIL is a BLOCKER at the DATA gate
```

Re-run by the lead after the WARN-1 fix (same command):

```
[OK]   split-reproduces: kind=predefined reproduces deterministically from study.yaml (train=445 development=2490 test=15992 rows)
[OK]   duplicate-rows: no duplicate row content straddles partitions
[OK]   group-overlap: N/A — split kind is not 'group'
[OK]   metric-direction[reproduction]: targets_outside_tolerance: contract-declared direction 'lower' accepted (custom metric of the scalar family)
[OK]   chance-level[reproduction]: N/A — no bundled chance scorer for custom metric 'targets_outside_tolerance'; reproduce checklist row 4 by hand
[OK]   metric-direction[att]: att_usd: contract-declared direction 'higher' accepted (custom metric of the scalar family)
[OK]   chance-level[att]: N/A — no bundled chance scorer for custom metric 'att_usd'; reproduce checklist row 4 by hand
7/7 checks passed: clean
```

The cautions WARN-2 to WARN-4 stand and travel to METHOD and EXPERIMENT: overlap and weight
concentration are what the `att` cells pin (`max_weight_share`), and the standard-error formula
is what P1 can miss on.

> **Decision:** **GO** (with the cautions WARN-2 to WARN-4)
