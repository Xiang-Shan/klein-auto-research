---
type: data-card
domain: "insurance"
modality: "tabular"
status: no-go
concepts: ["tabular-classification", "duplicate-row-leakage", "class-imbalance", "value-pattern-check"]
related: ["00-glm-claims-quickstart"]
---

# Data card — 12-insurance-claims-frequency

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.

**Auditor identity & clean-room disclosure.** Written by a Claude Code
`klein-data-auditor` subagent (Sonnet), fresh context, no prior turns in this study.
Files read **inside the study**: `study.yaml`, `prepare.py`, `fixtures/README.md`,
`data/prepared/insurance_claims_prepared.csv` (the prepared artifact — already present
on disk, not regenerated). Files read **outside the study**:
`.claude/skills/klein/references/data-gate-protocol.md`,
`.claude/skills/klein/assets/data-card-template.md`,
`.claude/skills/klein/references/profiles/insurance.md`, `kleinlib/schema.py`, and
(narrowly, to interpret the mechanized audit's own printed numbers) `kleinlib/leakage.py`
lines 1-60 (module docstring) and 130-179 (the split-check and duplicate-rows-check
functions) — not read contiguously, not read for anything beyond what those two
checks compute. `program.md`, `research_plan.md`, `scouting_ledger.md`, `playbook.md`,
`references.yaml`, `results.tsv`, `aux_metrics.tsv`, `study_state.json`, `events.jsonl`
and everything under `runs/`, `models/`, `sweeps/`, `figures/`, `report/` were **not**
read. `train.py` was read only via two greps narrowly scoped to seed/partition-literal
patterns (`random_state|seed|train_test_split|RANDOM_SEED|FIT_SEED|np.random|
numpy.random|load_partition|contract_split`), per the protocol's war-story-8 exception
— never for its modelling logic, and only after this card's target-leakage and
lookahead judgments (below) were already formed from `prepare.py` and the profile.
**Accidental exposure, disclosed as instructed:** partway through this audit,
`train.py` was edited on disk by a concurrent process (its size and content changed
between the first and second grep below), and a system file-change notification
surfaced its full contents to this agent unbidden — not via a deliberate Read call.
That content was not used to inform any judgment on this card; the only fact drawn
from it is independently reconfirmed by the second (current-file) narrow grep quoted
in issue #8 below.

## Source & shape

- **Source tag:** `bundled:insurance-claims` — `klein doctor --study` resolves it
  offline: `[OK] data source: 'bundled:insurance-claims' (bundled): found at
  datasets/insurance-claims/insurance_claims.csv.gz`. **Pin:** no `data.sha256` in
  `study.yaml`; acceptable for a `bundled:` source since the bytes are pinned by git
  tracking of the repo-local file rather than a declared digest — not independently
  re-verified against the upstream Kaggle listing.
- **Modality:** tabular · **Rows × cols:** 58,592 × 45 (44 features + 1 target) ·
  **Target:** `claim_status` (binary: ≥1 claim on the policy) · **Positive rate:**
  6.3968% (3,748 / 58,592; matches `fixtures/README.md`'s stated portfolio rate
  exactly).
- **Split policy:** `data.split`: `kind: stratified`, `seed: 42`,
  `development_size: 0.10`, `test_size: 0.10` → train 46,873 / development 5,859 /
  test 5,860 rows (80.00% / 10.00% / 10.00%). By `study.yaml`'s explicit design this
  row set is index-identical to the v1 quickstart's train/validation partition.
  **Fingerprints frozen at this gate** (measured with `kleinlib.data.
  partition_fingerprints`, twice, identical both times):
  `development=7e3d3ff85e624821037ef0c360f9e67451c1fd06976db440f86682ca9a892ac3`,
  `final_test=06d18ee16624e7e0d12f0ece4f08cc37321bc61802ff155e08d07e23b2cb0631`.
  Verified disjoint **by row index** (0/0/0 pairwise overlap, union = all 58,592
  rows) — but **not** disjoint by row content; see BLOCKER #1.
- **Profiler used:** global `dataset-profiler` skill
  (`~/.claude/skills/dataset-profiler/scripts/profile.py`), run directly against the
  prepared CSV with `--target claim_status`. Completed cleanly; no fallback needed.

## Profile summary

Every column below was inspected by ACTUAL VALUE, never by `dtype` alone (mandatory
war-story-1 check). Similar columns are grouped into one row with every member column
named; the "Value-pattern findings" prose after the table gives the group-level
evidence. Missing % is 0.0 for **all 45 columns** — confirmed twice: once by the
profiler's missingness pass, once by an independent full-table scan for `NaN`,
whitespace-only strings, and common sentinels (`-999`, `-1`, `9999`, `999`, empty
string) across every column.

| Column / field | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| **A.** `is_esc`, `is_adjustable_steering`, `is_tpms`, `is_parking_sensors`, `is_parking_camera`, `is_front_fog_lights`, `is_rear_window_wiper`, `is_rear_window_washer`, `is_rear_window_defogger`, `is_brake_assist`, `is_power_door_locks`, `is_central_locking`, `is_power_steering`, `is_driver_seat_height_adjustable`, `is_day_night_rear_view_mirror`, `is_ecw`, `is_speed_alert` (17 cols) | prepared `int64` {0,1}; RAW was string `"Yes"`/`"No"` (war story 1 — this dataset loads with pandas `str` dtype on this machine, never `object`); `prepare.py`'s `kleinlib.data.detect_yes_no_columns` + `yes_no_to_int` converted by VALUE PATTERN | 0.0 | 2 (all) | No | No — pre-existing equipment flags, none derived from the target | `is_speed_alert` is quasi-constant (99.38% = 1); see NOTE #5 |
| **B.** `rear_brakes_type`, `transmission_type` (2 cols) | prepared `int64` {0,1}; RAW was 2-level string (`"Drum"`/`"Disc"`, `"Manual"`/`"Automatic"`), mapped by an explicit `prepare.py` dict — a second, correct application of value-pattern discipline (not the Yes/No detector, since the text differs) | 0.0 | 2 (all) | No | No | — |
| **C.** `region_code`, `segment`, `model`, `fuel_type`, `engine_type`, `steering_type` (6 cols) | `str`, genuine nominal categorical text; correctly left un-encoded by `prepare.py` (encoding is a modeling-stage decision) | 0.0 | 22 / 6 / 11 / 3 / 11 / 3 | No | No | Below the profiler's high-cardinality threshold (max 22 ≪ 0.5·√58,592≈121). `region_code`↔`region_density` and `model`↔`engine_type`/`segment` are deterministic 1:1 mappings — redundancy, see WARN #4 |
| **D.** `max_torque_nm`, `max_torque_rpm`, `max_power_bhp`, `max_power_rpm` (4 cols) | `float64`/`int64`, regex-parsed by `prepare.py` (`extract_first_float`/`extract_rpm`) out of the two raw text-spec columns `max_torque`/`max_power` (e.g. `"113Nm@4400rpm"`); the two text columns are dropped after parsing | 0.0 | 8 / 8 / 9 / 5 | No | No | Numbers-in-strings pattern, confirmed correctly split into value + rpm |
| **E.** `power_to_weight`, `torque_per_litre`, `safety_features_count` (3 cols) | `float64`/`int64`, engineered by `prepare.py` from other columns of the **same row only** (`max_power_bhp/gross_weight`; `max_torque_nm/(displacement/1000)`; sum of the 17 group-A flags + `airbags`) | 0.0 | 10 / 9 / 9 | No | **No** — specifically checked (these are the three ratio/count features `study.yaml`'s brief flagged for scrutiny): all three derive exclusively from vehicle-spec inputs, never from `claim_status`; `|corr|` with target ≤ 0.0083 for all three | — |
| **F.** `subscription_length`, `vehicle_age`, `customer_age`, `region_density`, `airbags`, `displacement`, `cylinder`, `turning_radius`, `length`, `width`, `gross_weight`, `ncap_rating` (12 cols) | `float64`/`int64`, genuine numeric measurements | 0.0 | 140/49/41/22/3/9/2/9/9/10/10/5 | No (max 140 ≪ 58,592) | No — max `|corr|` with target 0.0787 (`subscription_length`) | `displacement`'s value 999 was flagged by an automated sentinel scan, then confirmed genuine (full sorted set `{796,998,999,1196,1197,1199,1493,1497,1498}` cc — all real small-car engine displacements); `customer_age` spans 35–75 with no gaps — see NOTE #6 |
| **G.** `claim_status` (target, 1 col) | `int64` {0,1} | 0.0 | 2 | No | N/A — this is the target | Positive rate 6.3968% (3,748 positive / 54,844 negative) |

**Value-pattern findings (mandatory war-story-1 check, summary):** every string-typed
raw column that actually encodes a boolean or a numeric spec was converted by
`prepare.py` using **value inspection**, never `dtype`-based branching — confirmed by
reading `prepare.py`'s `preprocess()` line by line and by checking, in the prepared
artifact itself, that all 19 boolean-pattern columns (groups A+B) now carry clean
`int64` {0,1} with zero missing. The 6 remaining `str` columns (group C) are genuine
multi-level nominal categories, not disguised booleans or numbers — their value sets
were printed and inspected individually (e.g. `fuel_type` = {Petrol, CNG, Diesel},
`steering_type` = {Power, Electric, Manual}); none contain a sentinel, a blank, or a
mixed-type cell. No column anywhere in the 45 carries `-999`/`-1`/`9999`/empty-string/
`"NA"`/`"unknown"` sentinels — a full-table scan for all of these returned zero hits
except the legitimate `displacement=999` value resolved above.

**Duplicate rows (dataset-wide, not yet split-aware):** 1,894 of 58,592 rows (3.23%)
are byte-identical to an earlier row across **all 45 columns including the target**;
1,709 distinct duplicate-content groups exist dataset-wide (3,603 rows total
involved). This is not a data-entry defect (no blank/sentinel values anywhere) but a
consequence of the coarse, heavily-binned feature space (22-level region, 11-level
model, 17 boolean flags, few numeric buckets) — genuinely distinct policies recur as
byte-identical rows. Whether this contaminates the SPLIT is checked mechanically in
the clean-room leakage audit below — it does, and that is BLOCKER #1.

## Ranked go / no-go issues

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | **BLOCKER** | **Split contamination (mechanized FAIL).** `kleinlib.leakage` row 3: 615 distinct row-content hashes span more than one partition (`train/development=297, train/test=310, development/test=32` — a hash can straddle more than one pair, so the union is 615, not the sum 639). At row level: 300/5,859 (5.12%) of development rows and 312/5,860 (5.32%) of test rows are exact byte-for-byte duplicates of a row already in the 46,873-row training partition (measured independently of the mechanized tool, by hashing the full prepared table and comparing against `kleinlib.data.contract_split`'s realized indices). Of those, 297/300 (dev) and 306/312 (test) are majority-class (`claim_status=0`); only 3 (dev) and 6 (test) are duplicated positives — so the likely AUC impact is smaller than the raw 5% contamination rate suggests, but the check is unconditional and the FAIL stands regardless of estimated severity. **Root cause is structural, not a seed pick:** `study.yaml` deliberately chooses the row-index split to be identical to the v1 quickstart's partition (stated goal: "the ported models are therefore the v1 models — same rows, same recipes"), so a reseed would not fix this — only a content-aware split (`kind: group` keyed on a row-content hash) or a dedup step in `prepare.py` would, and either breaks the study's explicit v1-row-identity design goal (and would make `P1`/`P2`/`P4`'s transfer comparison against the v1 ledger apples-to-oranges). This is a decision only the user/orchestrator can make: **(a)** accept the risk explicitly via `klein gate override data --acknowledged-by <actor> --reason "..."`, documenting that ~5% cross-partition duplication is inherited from the v1-identical split and is being knowingly reproduced for comparability, and treat every AUC number this study produces as carrying that known small upward bias; or **(b)** change `prepare.py`/`study.yaml` to deduplicate or content-group the split, accept the resulting break from v1 row-identity, and re-run this gate clean. This auditor cannot make that call and did not edit `prepare.py`. |
| 2 | WARN | 6 nominal categoricals (group C, `region_code`/`segment`/`model`/`fuel_type`/`engine_type`/`steering_type`) remain un-encoded text in the prepared artifact; correct handling requires an encoder fit **only on each split's training rows**. `prepare.py` itself does no fitting of any kind (confirmed by direct read — no `.fit(`, no `groupby`-based imputation, no scaler/encoder import anywhere in the file), which is correct because encoding belongs to the modeling stage, not prep. Whether the modeling code actually fits its encoder in-fold is a claim this auditor was asked to take on trust for `train.py` specifically (outside the clean-room read boundary) and could **not** independently verify beyond the narrow seed/partition grep in issue #8. | Confirm at METHOD gate / `klein preflight` that every encoder/scaler in the modeling code is fit inside a `Pipeline` (or equivalent) on training rows only, per split — do not assume from this card. |
| 3 | WARN | Severe class imbalance: `claim_status` positive rate 6.397% (3,748/58,592), stable within 0.01pp across train (6.396%) / development (6.400%) / test (6.399%) — the stratified split is working as intended. | Insurance-profile doctrine applies: `class_weight=None` + isotonic calibration + threshold tuning; never resample the development or test fold (war story 4). |
| 4 | WARN | Near-total categorical/numeric redundancy: `region_code` determines `region_density` 1:1 (every region code maps to exactly one density value, verified over all 22 codes), and `model` determines both `engine_type` and `segment` 1:1 (verified over all 11 models). Not leakage (no target involvement) but will inflate a GLM's coefficient standard errors / destabilize which of a correlated group a tree happens to split on. | Keep one representative of each redundant group for a coefficient-based (GLM) rung, or rely on a tree-based rung's native handling of collinearity; do not interpret per-column GLM coefficients from the redundant group as independent effects. |
| 5 | NOTE | `is_speed_alert` is quasi-constant: 99.38% of rows = 1 (profiler-flagged). Correlation with target is negligible (0.0073). | Unlikely to carry signal for a linear rung; safe to drop for a leaner GLM, harmless to keep for a tree. |
| 6 | NOTE | `customer_age` spans exactly 35–75 with no gaps and no rows below 35 anywhere in the 58,592-row portfolio (inherited from the raw source — `prepare.py` does no row filtering). `displacement`'s value 999 initially looked sentinel-like; confirmed genuine (see Profile summary group F). | Treat any inference below age 35 as extrapolation outside this portfolio's observed range; no action needed on `displacement`. |
| 7 | NOTE | 1,894/58,592 (3.23%) exact-duplicate rows dataset-wide (1,709 distinct duplicate-content groups); explained entirely by the coarse feature space (Profile summary), not by a data-quality defect — the full sentinel/blank/NaN scan found zero anomalous values anywhere in the 45 columns. | Informational; the split-relevant consequence of these duplicates is BLOCKER #1, not a separate action here. |
| 8 | NOTE | **War-story-8 check: clean.** Two narrow greps of `train.py` for seed/partition-literal patterns only (never its modelling logic) — first before, then after a concurrent on-disk edit mid-audit (disclosed above). Current file: the only seed present, `FIT_SEED = 42`, feeds exactly two `random_state=FIT_SEED` kwargs on sklearn estimator constructors (a model-fit seed, confirmed by grep context showing the assignment sites, not by reading the surrounding modelling code) and the partition itself is sourced from `load_partition(evaluation_kind, study_dir=".")` — the sanctioned `kleinlib.data.load_partition` contract API. No `train_test_split`, no other literal seed, no partition-deciding literal anywhere in `train.py`. `prepare.py` is likewise clean (only a docstring's prose use of the word "seed", no literal). | No action — record clean for the record; re-grep at every `klein preflight`/`run-one` since `train.py` is the mutable surface and is edited every experiment. |

## Clean-room leakage audit

Performed reading only `study.yaml`, `prepare.py`, the prepared artifact and the
profile (plus the narrow, disclosed `train.py` grep for row 3's war-story-8 half —
never `program.md`). Rows 3-4 mechanized:

```
KLEIN_OFFLINE=1 uv run --locked python -m kleinlib.leakage \
  studies/12-insurance-claims-frequency/data/prepared/insurance_claims_prepared.csv \
  --target claim_status --study studies/12-insurance-claims-frequency
```

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage — no feature is a proxy/derivative of the target or post-outcome information | **Pass** (judgment) | No feature is constructed from `claim_status`; the three engineered ratio/count features (`power_to_weight`, `torque_per_litre`, `safety_features_count`) derive exclusively from vehicle-spec columns of the same row (verified by reading `prepare.py`'s `preprocess()`). No claim-amount, claim-count, or other post-outcome column exists anywhere in the 45-column schema. Max `|corr|` of any feature with the target is 0.0787 (`subscription_length`); the profiler's own `|corr|>0.95` leakage scan reports none. The only ID-like column in the raw source, `policy_id`, is dropped by `prepare.py` (`DROP_COLUMNS`) and confirmed absent from the prepared table; no other column has cardinality > 1,000 (checked over all 45). |
| 2. Lookahead — encoders/imputers/scalers fit on train only; time-derived features precede the cut | **Pass** (judgment, prepare.py portion only) | `prepare.py` contains no `.fit(`, no scaler/encoder/imputer import, no `groupby`-based statistic, no whole-dataset aggregate of any kind — every transform (regex text-spec parsing, the Yes/No value-pattern map, the two explicit binary maps, the three ratio/count features) is a pure per-row function of that row's own raw values, so nothing computed in `prepare.py` could leak information across rows or partitions regardless of which rows land where. The task brief additionally asserted that the modeling code fits its own encoder inside a scikit-learn `Pipeline` on the training partition only — **this half of the claim is outside the clean-room read boundary and is not independently verified by this card** (disclosed; see WARN #2). Not a time-series study, so no time-cut applies. |
| 3. Split contamination — no duplicate rows straddling partitions; group ids never cross partitions; the split reproduces from `study.yaml` alone (fingerprint match) | **FAIL** (mechanized) | `[OK] split-reproduces: kind=stratified reproduces deterministically from study.yaml (train=46873 development=5859 test=5860 rows)`. `[FAIL] duplicate-rows: 615 duplicated row-content hash(es) straddle partitions (train/development=297, train/test=310, development/test=32)`. `[OK] group-overlap: N/A — split kind is not 'group'`. Supplementary evidence measured independently by this auditor: partitions are disjoint **by row index** (0/0/0 pairwise overlap; union = 58,592 rows) and `kleinlib.data.partition_fingerprints(study)` returns identical hashes on two successive calls (`development=7e3d3ff8…92ac3`, `final_test=06d18ee1…b0631` — stable/deterministic). The FAIL is entirely the content-duplication finding detailed in BLOCKER #1. |
| 4. Eval-harness sanity — metric direction matches the contract; constant and shuffled predictors score at chance | **Pass** (mechanized) | `[OK] metric-direction[primary]: val_auc: contract direction 'higher' matches the canonical registry`. `[OK] constant-chance[primary]: val_auc=0.5000 for the constant predictor (chance anchor 0.5)`. `[OK] shuffled-chance[primary]: val_auc=0.5114 for the label-shuffled predictor (chance anchor 0.5)` — within the tool's default `±0.15` chance margin and `--seed 0` default (both unmodified). CLI summary: `5/6 checks passed: 1 FAIL — any FAIL is a BLOCKER at the DATA gate` (exit code 1); the single FAIL is row 3's duplicate-rows sub-check, carried into this table above. |

## Go / no-go

> **Decision:** NO-GO
>
> **Rationale:** Row 3 of the mechanized clean-room leakage audit FAILS —
> `kleinlib.leakage` reports 615 distinct row-content hashes (exact feature+target
> duplicates) straddling partitions, contaminating 5.12% of development and 5.32% of
> test rows with a byte-identical twin already seen in training. Per protocol, any
> FAIL on any leakage-audit row is an unconditional BLOCKER regardless of estimated
> practical severity, and this auditor is not authorized to fix it (no `prepare.py` or
> `study.yaml` edits are in scope for the DATA gate — see BLOCKER #1's evidence for
> why a reseed cannot fix it, and for the two structural fixes available). Only the
> user, via the orchestrator, may accept this risk (`klein gate override data
> --acknowledged-by <actor> --reason "..."`, also explained in `program.md`) or direct
> a deterministic fix in `prepare.py`/`study.yaml` followed by a clean re-audit.
> Everything else on this card is WARN/NOTE-level and would not by itself have
> blocked a GO: the mandatory value-pattern check (war story 1) is correctly and
> completely applied, no engineered or raw feature is a target proxy, `prepare.py`
> performs no global fit/impute/target-dependent transform, the split is otherwise
> stratified and index-reproducible with stable fingerprints, the eval harness scores
> a constant and a shuffled predictor at chance, and no literal partition seed exists
> anywhere in `train.py` (war story 8 clean, reconfirmed after a concurrent on-disk
> edit mid-audit — disclosed above).
>
> Modeling is HARD-BLOCKED until this is resolved. A v2 override must be recorded
> with `klein gate override data --acknowledged-by <actor> --reason <reason>`; also
> explain it in `program.md`. A prose-only fast path does not unlock modeling.
