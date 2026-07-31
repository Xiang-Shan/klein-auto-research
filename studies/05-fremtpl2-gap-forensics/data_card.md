---
type: data-card
domain: "insurance"
status: go-with-cautions        # draft | go | no-go | go-with-cautions
concepts: []
related: []
---

# Data card — 05-fremtpl2-gap-forensics

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.

## Source & shape

- **Source:** `data_hub:freMTPL2` → `data/prepared/fremtpl2_frequency.csv`
  (SHA-256 `db82e80291bcaf1a7487e6ecb9353d1eebaacf776c6a2cc389d4a4a94c1cf948`,
  **measured in this audit and identical to `data/prepared/reference_cell.json:prepared_sha256`**
  — the bytes audited are the bytes `prepare.py` wrote, so prep was verified by hash
  identity rather than re-executed; re-running would need `$DATA_HUB` and would rewrite
  the frozen artifact).
- **Rows × cols:** 678,013 × 12  ·  **Target:** `ClaimNb`  ·  **Target mean:** 0.038946
  claims/row; 96.321% of rows are zero-claim; exposure-weighted frequency
  26,406 / 358,360.11 = **0.073686 claims per exposure-year**.
- **Modeled response:** `ClaimNb / Exposure` with `Exposure` as the Poisson sample weight
  (`pipeline.frequency`, `pipeline.fit_model`). Features are the **9** columns in
  `pipeline.NUMERIC + pipeline.CATEGORICAL`; `IDpol`, `ClaimNb`, `Exposure` never enter `X`.
- **Split:** `kleinlib.data.three_way_split(task="regression", strategy="random",
  development_size=0.2, test_size=0.2, seed=42)` → train 406,807 / development 135,603 /
  sealed test 135,603. Re-run twice in-audit: byte-identical index sets, fully disjoint.
- **Profiler used:** bundled `kleinlib.profile_fallback` output (`profile.txt`), every
  line re-verified **by value** in this clean-room pass (raw-token read with
  `dtype=str, na_filter=False`, so nothing is hidden behind dtype inference).

## Profile summary

| Column | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| `IDpol` | int64 — 678,013/678,013 int tokens, no mixed kinds | 0.0% | 678,013 | **YES** (unique = rows) | none (excluded) | Monotone increasing 1→6,114,330; r=−0.0396 vs `ClaimNb`. Never enters `X`. |
| `ClaimNb` | int64 — int tokens only; full value set {0:653069, 1:23570, 2:1299, 3:62, 4:13} | 0.0% | 5 | no | **TARGET** | 0 rows above the cap of 4 → `prepare.py`'s `clip(upper=4)` is a no-op on this hub table (`capped_claim_rows=0`); 13 rows sit at the cap. |
| `Exposure` | float64 — decimal tokens only; 106 distinct; decimals-per-token {1:217894, 2:453242, 16:5817, 19:1060} | 0.0% | 106 | no | none (weight, not a feature) | min 0.0027378508 = `1/365.25`, max 1.0000000000; 0 rows outside (0,1]; 169,349 rows at exactly 1.0. |
| `VehPower` | int64 — int tokens only | 0.0% | 12 | no | none | 4–15, skew 1.17; effectively an ordinal rating band. |
| `VehAge` | int64 — int tokens only | 0.0% | 78 | no | none | 0–100 (8,322 rows > 20); p99=21, p999=33 — long thin tail. |
| `DrivAge` | int64 — int tokens only | 0.0% | 83 | no | none | 18–100, no under-18 rows, 401 rows > 90. Splined config member. |
| `BonusMalus` | int64 — int tokens only | 0.0% | 115 | no | **watch — ex-ante, not post-outcome** | 50–230; 1.15% > 100. Strongest surviving signal (r=+0.0667 vs `ClaimNb`); frequency gradient 0.051→0.568 across BM bands. Set from PRIOR-year experience at renewal; does not encode this period's `ClaimNb`. |
| `Density` | int64 — int tokens only (the `999` substring hit is a sentinel false-positive inside 4-digit values) | 0.0% | 1,607 | no | none | 1–27,000, median 393, skew 4.65 (0.05 after `log1p`); **10,515 rows (1.55%) pinned at exactly 27,000** — p99 == max, a real ceiling. |
| `Area` | **str, non-numeric strings only** — {C,D,E,A,B,F} | 0.0% | 6 | no | none | Ordered-looking A→F but handled nominally via OHE. Rarest level F = 17,954 rows. |
| `VehBrand` | **str, digits-inside-string** (`B12`, `B6`, …) — never numeric, no split needed | 0.0% | 11 | no | none | Rarest B14 = 4,047 rows. |
| `VehGas` | **str binary-as-string** — exactly {`Regular`: 345,877, `Diesel`: 332,136}; NOT `Yes`/`No`, NOT 0/1 | 0.0% | 2 | no | none | The war-story shape: a two-level string column. It IS listed in `pipeline.CATEGORICAL`, so OHE picks it up — no dtype-based skip. |
| `Region` | **str, digits-inside-string** (`R24`, `R82`, …) | 0.0% | 22 | no | none | Rarest R43 = 1,326 rows — every level clears `OneHotEncoder(min_frequency=20)`, so no level is silently collapsed into `infrequent`. |

**Value-pattern check (mandatory war story):** performed on **all 12 columns** against raw
CSV tokens, not dtypes. Findings: **zero** missing values, **zero** empty/whitespace cells,
**zero** whitespace-padded tokens, **zero** mixed-type columns, **zero** true sentinels
(the only `SENTINEL` regex hits were the substring `999` inside legitimate `IDpol`/`Density`
integers and the letter `F` as an `Area` level — both dismissed by inspecting the full value
set). The four string columns hold what they claim: `VehGas` is a genuine two-level string
binary and `VehBrand`/`Region` are alphanumeric codes that must never be coerced to numbers.
No string-encoded booleans, no numbers-in-strings, no `NA`/`unknown`/`-999`.

## Ranked go / no-go issues

Severity: **BLOCKER** (must fix before modeling) · **WARN** (proceed with care) ·
**NOTE** (informational). Order most-severe first.

**No BLOCKER is open.** (A blocker here would be a target-derived column surviving the
`RAW_KEEP` allowlist, a non-reproducing split, or an eval-harness sanity failure — all three
were tested and all three are clean.)

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | WARN | **Duplicate FEATURE profiles straddle the split.** The 9 modeled features repeat: 528,765 distinct profiles over 678,013 rows; 149,248 duplicate rows (`duplicated(keep="first")`, matching `reference_cell.json`); 108,663 groups with >1 row covering 257,911 rows (38.04%); largest group 22 rows. Under the seed-42 split, **31,798 profile groups span train & development** and 31,591 span train & test, so **35,985 / 135,603 = 26.54% of development rows have a feature-identical twin in train** (test: 35,763 / 135,603 = **26.37%**). 95.0% of straddling groups carry a constant `ClaimNb`, and only 1,420 / 31,798 also share a constant `Exposure` — the twins are *not* full row duplicates, so the mechanized full-row check correctly passes. | **Recorded as a limitation; prep frozen for anchor comparability** — do NOT deduplicate or switch to a group split. Both tracks consume the identical contamination, so the GLM↔GBDT *gap* (the study's actual estimand) is unbiased by it; what is optimistic is the *absolute* deviance level versus a fresh-portfolio deployment. Twin rows are also claim-poor (1.85% claim-bearing inside straddling groups vs 3.68% overall; 1.97% among the 35,985 dev twin-rows), which bounds the memorization upside. State this verbatim in `findings.md` limitations and in the report's data-story section. |
| 2 | WARN | **Interaction-pair provenance is not fixed by the frozen library.** `pipeline.make_model("glm_interactions", interactions=…)` takes the pairs as a *caller-supplied argument*; the transform itself (`_transform_frame`) is stateless and safe, but a pair chosen after looking at development deviance is a lookahead that no static check can catch. | Select the pairs from a surrogate fit on **train rows only**, before any development scoring; record the selection provenance (surrogate config + fold) in the run manifest; never re-select after seeing a dev number. This is the one live lookahead surface in an otherwise train-only pipeline. |
| 3 | WARN | **The modeled response has a 365× tail.** `ClaimNb/Exposure` reaches 365.0; 104 rows exceed 50 and 42 exceed 100; 332 rows carry a claim on under 0.05 exposure-years. | No data fix — `pipeline.fit_model` already passes `sample_weight=Exposure`, which down-weights exactly these rows by construction (a 1-day policy gets 1/365 of a full-year policy's weight). Do not filter: filtering breaks the study-04 anchor identity. Watch for GBDT leaf instability at `max_leaf_nodes=31` and for GLM `PoissonRegressor` convergence warnings at `max_iter=300`. |
| 4 | NOTE | **The exposure lower clip silently binds and the hygiene counter under-reports it.** 1,060 rows hold exactly `repr(1/365.25)` = `0.0027378507871321013` (19 decimals) while every source value is a 1–2 decimal or a 16-decimal day-fraction — the fingerprint of `prepare.py`'s `clip(lower=1/365.25)`. `reference_cell.json:clipped_exposure_rows = 0` counts only rows outside (0,1] and therefore never reports these 1,060 lower-clip binds. The upper clip did not bind (0 rows > 1). | **Recorded, not fixed — prep frozen for anchor comparability.** The clip is protective (it forecloses divide-by-zero in `y/Exposure`) and moves 0.16% of rows by <0.3% of their weight. If the counter is ever revised in a successor study, count the lower-clip bind as its own statistic. |
| 5 | NOTE | **The `ClaimNb` cap at 4 is a no-op on this hub table.** 0 rows exceed 4 pre-clip (`capped_claim_rows = 0`), so the hub table already arrives capped; 13 rows (0.0019%) sit at the cap value. | None. Keep the cap as a documented guard so the prep stays byte-identical to study 04. Note in findings that the cap is inherited, not applied here. |
| 6 | NOTE | **`Density` is a censored heavy tail.** Skew 4.65, median 393, max 27,000, and p99 == max because 1.55% of rows are pinned at exactly 27,000. | `pipeline._transform_frame` already `log1p`s `Density` for the shaped GLM configs (skew 4.65 → 0.05) and `SPLINED` includes it. The 27,000 plateau is a genuine ceiling in the source, **not** a sentinel — never treat it as missing. Trees are scale-free and need nothing. |
| 7 | NOTE | **`IDpol` is a perfect row identifier** (678,013/678,013 unique, monotone increasing, r=−0.0396 with `ClaimNb` — i.e. it weakly encodes portfolio vintage/row order). | Already excluded by construction: `pipeline.load_split` builds `X` from `NUMERIC + CATEGORICAL` only. Keep it in the prepared file for traceability, keep it out of every feature frame. |
| 8 | NOTE | **Sparse-level plateaus that look leak-like but are not.** 225 `Density` values, 39 `VehAge` values, 5 `DrivAge` values and 25 `BonusMalus` values map to a single `ClaimNb` — but they cover 0.93% / 0.06% / 0.015% / 0.011% of rows respectively, with row counts of 1–190, and essentially all of them are all-zero-target. This is sparsity, not memorizable signal. | None. OHE `min_frequency=20` and the spline basis absorb them; no binning needed for the frozen configs. |
| 9 | NOTE | **No time column exists** in the prepared artifact (12 columns, none temporal), so a temporal split is impossible and the frozen random 60/20/20 seed-42 split is the only realizable design. | None — but record that RQ1's sealed gap is an *in-period* statement about this portfolio, not a forward-in-time generalization claim. |
| 10 | NOTE | **A few numeric levels appear in development but not in train**: `VehAge` {55, 62, 66, 71} and `BonusMalus` {135, 136, 151}. All 4 categorical columns have every level present in all three partitions. | Spline/scaler extrapolation only, on a handful of rows; `OneHotEncoder(handle_unknown="ignore")` never fires because no unseen categorical level exists. No action. |

## Clean-room leakage audit

Performed in a FRESH context (separate agent/session, or self-performed only after the
profile is finished), reading ONLY `study.yaml`, `prepare.py`, the prepared artifact,
and the profile — never `program.md`. Rows 3–4 are mechanized:
`uv run --locked python -m kleinlib.leakage <prepared> --target <col> --study <dir>`.
Any FAIL is a **BLOCKER** (NO-GO until fixed and re-audited).

Clean-room inputs actually read: `study.yaml`, `prepare.py`, `pipeline.py` (split + scoring
definitions), `data/prepared/fremtpl2_frequency.csv`, `profile.txt`,
`data/prepared/reference_cell.json`. `program.md`, `research_plan.md`, `playbook.md`,
`train.py` and every other study's files were **not** opened.

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage — no feature is a proxy/derivative of the target or post-outcome information | **PASS** | `prepare.py`'s `RAW_KEEP` is an **allowlist**, not a denylist: it admits exactly the 12 canonical raw columns and drops everything else — `reference_cell.json:dropped_columns = 46`, i.e. the hub's 58-column table was cut to 12, taking the hub's derived `Frequency` column (the target in disguise) with it. Verified **by value**, not by trusting the code: the prepared header is exactly `['IDpol','ClaimNb','Exposure','VehPower','VehAge','DrivAge','BonusMalus','Density','Area','VehBrand','VehGas','Region']` — no `Frequency`, no rate, no dummy, no post-outcome column survives. Models see fewer still: `pipeline.load_split` sets `X = NUMERIC + CATEGORICAL` (9 columns), so `IDpol`, `ClaimNb` and `Exposure` are structurally unreachable as features. Leak-signature contrast: a surviving `Frequency` column would correlate **+0.3055** with `ClaimNb` and **+1.0000** with the modeled rate; the strongest *surviving* feature is `BonusMalus` at **+0.0667** — two orders of magnitude away from a leak, and legitimate ex-ante (the bonus-malus coefficient is fixed from PRIOR years at renewal, so it cannot encode this period's `ClaimNb`). No feature is a deterministic function of the target (issue 8 shows every apparent one-to-one mapping is a <1%-of-rows sparse level). `anchor_targets` and `null_dev_deviance` in `reference_cell.json` are **identity-check constants, not features** — they are read by `pipeline.read_reference()` for the E0001/E0002 reproduction assertion and never join `X`. |
| 2. Lookahead — encoders/imputers/scalers fit on train only; time-derived features precede the cut | **PASS** (with issue 2 as a live caution) | Every **stateful** transformer — `StandardScaler`, `SplineTransformer`, `OneHotEncoder(min_frequency=20)`, and CatBoost's ordered target statistics — lives *inside* the estimator that `pipeline.fit_model` fits, and it fits on `X_fit = _transform_frame(X_tr, …)`, i.e. **train rows only** (`load_split` returns `(X_tr, …), (X_ev, …)` and only `X_tr` reaches `.fit`). The evaluation frame is passed exclusively to `ClippedRegressor.predict`, which replays the **stateless, row-wise** `_transform_frame` (`log1p(Density)` and numeric products — no fitted state, so nothing can be learned from the eval fold) and then calls the train-fitted `inner.predict`; there is no refit, no imputation, and no target encoding anywhere outside train. The split-identity anchor is train-only too: `null_dev_deviance()` takes `lam = sum(y_tr)/sum(w_tr)`. **Time features: N/A** — the prepared artifact has no date/time column at all (issue 9), so there is no temporal ordering to violate. The one surface a static read cannot certify is the caller-supplied `interactions` argument (issue 2), which must be selected on train folds only. |
| 3. Split contamination — no duplicate rows straddling partitions; group ids never cross partitions; the split reproduces from `study.yaml` | **PASS** (mechanized) | `[OK]   split-reproduces: kind=random reproduces deterministically from study.yaml (train=406807 development=135603 test=135603 rows)`<br>`[OK]   duplicate-rows: no duplicate row content straddles partitions`<br>`[OK]   group-overlap: N/A — split kind is not 'group'`<br>Independently re-derived by value: `three_way_split(task="regression", strategy="random", development_size=0.2, test_size=0.2, seed=42)` run twice returns identical index sets; the three index sets are pairwise disjoint and sum to 678,013; `IDpol` has 0 duplicates so no row identity repeats. Partition balance is even — train/dev/test exposure-weighted frequency 0.073900 / 0.072375 / 0.074350 and zero-claim share 96.312% / 96.396% / 96.274%. **Caveat recorded, not a FAIL:** full-row duplicates are impossible (unique `IDpol`, varying `Exposure`), but *feature-profile* twins do straddle — 26.54% of dev rows, 26.37% of test rows (issue 1). Recorded as a limitation; prep frozen for anchor comparability. |
| 4. Eval-harness sanity — metric direction matches the contract; constant and shuffled predictors score at chance | **PASS** (mechanized) | `[OK]   metric-direction[glm]: val_poisson_deviance: contract direction 'lower' matches the canonical registry`<br>`[OK]   constant-chance[glm]: val_poisson_deviance=0.2554 for the constant predictor (no-information baseline)`<br>`[OK]   shuffled-chance[glm]: val_poisson_deviance=1.5327 for the label-shuffled predictor (no-information baseline)`<br>`[OK]   metric-direction[gbdt]: val_poisson_deviance: contract direction 'lower' matches the canonical registry`<br>`[OK]   constant-chance[gbdt]: val_poisson_deviance=0.2554 for the constant predictor (no-information baseline)`<br>`[OK]   shuffled-chance[gbdt]: val_poisson_deviance=1.5296 for the label-shuffled predictor (no-information baseline)`<br>Full run: **9/9 checks passed: clean**. Both tracks declare the same metric name and the same `lower` direction in `study.yaml`, and both resolve against the same registry. |

## Go / no-go

> **Decision:** **GO-WITH-CAUTIONS**
>
> **Rationale:** All four clean-room checklist rows PASS and the mechanized auditor
> returns **9/9 checks passed: clean** — no target-derived column survives `prepare.py`'s
> `RAW_KEEP` allowlist (46 hub columns dropped, including the `Frequency` target-in-disguise;
> verified by value, and the strongest surviving feature correlates +0.0667 with the target
> against a +0.3055 leak signature), the seed-42 60/20/20 split reproduces deterministically
> and disjointly from `study.yaml` alone, every stateful transformer is fit on train rows
> only, and the metric direction plus both no-information baselines are sane on both tracks.
> The prepared artifact is byte-identical to what `prepare.py` recorded
> (SHA-256 match against `reference_cell.json`), 678,013 × 12, with zero missingness, zero
> sentinels, zero mixed-type columns, and no dtype trap — `VehGas` is a genuine two-level
> string binary and is correctly enumerated in `pipeline.CATEGORICAL`.
>
> The cautions are **recorded, not fixed, by design**: this is a two-track comparison study
> whose prep is FROZEN byte-for-byte to its archived predecessor so that E0001/E0002 can
> reproduce the published anchors (0.454861 / 0.444689) to 1e-9. Changing the prep to
> deduplicate straddling feature profiles (issue 1) or to re-report the exposure clip
> (issue 4) would destroy exactly the anchor comparability the study exists to exploit.
> Both tracks consume the identical contamination, so the GLM↔GBDT gap — the estimand — is
> unbiased by it; only absolute deviance levels are optimistic relative to a fresh portfolio.
>
> **Cautions the modeling stage must carry:** (1) 26.54% of development rows and 26.37% of
> sealed-test rows have a feature-identical twin in train — report the gap, not the level,
> and state this limitation in `findings.md`; (2) `glm_interactions`' interaction pairs must
> be selected from a **train-only** surrogate and their provenance recorded in the manifest,
> since that argument is the pipeline's one live lookahead surface; (3) the response tail
> reaches 365 claims/year on sub-week exposures — keep `Exposure` as the Poisson sample
> weight and never filter these rows.
>
> If NO-GO or any BLOCKER is open, modeling is HARD-BLOCKED. A v2 override must be
> recorded with `klein gate override data --acknowledged-by <actor> --reason <reason>`;
> also explain it in `program.md`. A prose-only fast path does not unlock modeling.
