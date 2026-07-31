---
type: data-card
domain: "insurance"
status: go-with-cautions
concepts: [loss-models, heavy-tails, quantile-least-squares, return-levels, small-sample]
related: [hurricane_top30_pl1998, adjieteh-2024-thesis, pielke-landsea-1998]
---

# Data card — 06-hurricane-gqls-returnlevels

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.
> Audited clean-room: this card was written from `study.yaml`, `prepare.py`, the bundled
> `datasets/hurricane_top30_pl1998/`, the prepared artifact, and `estimators.py` (consumption
> of the fitting column only). `program.md`, `research_plan.md`, `playbook.md`, and
> `method_card.md` were NOT read.

## Source & shape

- **Source:** `data_hub:hurricane_top30_pl1998` — Pielke & Landsea (1998) Table 8, "Top 30
  Damaging Hurricanes (1900–1995)", normalized to 1995 USD; transcribed from NOAA AOML/HRD.
  A byte-identical copy is bundled at `datasets/hurricane_top30_pl1998/` for standalone
  reproducibility (`sha256 868318b0c90f2f6e8e4ecb70a7b47caa490c49a3c487c7838f3dea1c5bf96445`
  == the data_hub full-data CSV).
- **Rows × cols:** 30 × 8 (6 source + 2 derived by `prepare.py`) · **Target:** `damage_bn_1995`
  · **Target mean / sd:** 11.7499 / 13.6251 bn 1995-USD (ddof=1) · **Range:** 2.266 – 72.303 bn.
- **Fitting column:** `log_damage_usd = log(damage_bn_1995 × 1e9)`, range 21.541282 – 25.004131
  nats. `estimators.py` consumes ONLY this column (via sorted order statistics / a quantile
  grid); nothing downstream re-derives it.
- **Prepared artifact:** `data/prepared/hurricane_top30.csv`,
  `sha256 a0e6a5d9c9370f6c729be0c6e272b779565e04aa66fb9c75e80f445f862db8fd` — byte-identical
  before and after a live re-run of `prepare.py`, so prep is deterministic.
- **Profiler used:** bundled value-pattern audit (below) + `kleinlib.leakage`. The global
  `dataset-profiler` skill targets feature/target modelling frames; this study has no feature
  matrix, so the mandatory per-column value check was run directly.

## Profile summary

| Column | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| `rank` | int-like by value, 1–30 contiguous, no sentinels | 0.0 | 30 / 30 | **YES** — a perfect row id | **YES as a covariate** | Deterministic bijection of the target: `rank == 31 − rankdata(damage)` exactly; Spearman(rank, target) = −1.000000. Harmless for distribution fitting, fatal as an input. |
| `name` | free-text, 0 embedded digits, 0 sentinels (`""`/`NA`/`unknown` all absent) | 0.0 | 28 / 30 | No | No | 19 named storms (`Name (region)`: Andrew, Betsy, Donna, Camille, Agnes, Diane, Hugo, Carol, Carla, Hazel, Frederic, Alicia, Celia, Dora, Opal, Cleo, Juan, Audrey, King); 11 pre-1950-era **region labels** for unnamed storms (`SW Florida`, `New England`, `NE US`, `S Texas`, …). Two labels repeat — `N Texas (Galveston)` (1900, 1915) and `SE Florida` (1945, 1949) — these are **distinct events, not duplicate records**; `(name, year)` is 30/30 unique. |
| `year` | int-like, 1900–1995 | 0.0 | 27 / 30 | No | No | 1944, 1954, 1964 each appear twice — genuine two-storm seasons. r(year, log target) = −0.42 (see checklist row 2). |
| `category` | int-like, values exactly {1,2,3,4,5} | 0.0 | 5 | No | No | Saffir-Simpson at landfall. Counts {1:3, 2:2, 3:12, 4:12, 5:1}. No 0 / −999 / NA sentinel. Unused by the study. |
| `damage_bn_1995` | float-like, 2.266–72.303, no zeros/negatives/ties | 0.0 | 30 / 30 | No | **is the target** | Billions of 1995 USD. Strictly decreasing in `rank` (verified all 29 adjacent pairs). |
| `pre1925_flag` | **int-like 0/1 — a true integer flag, NOT a `"Yes"`/`"No"` string** | 0.0 | 2 | No | No | The war-story trap is absent here. Sum = 3, exactly ranks 3/4/22, and exactly and only the three `year < 1925` rows (set equality verified). |
| `damage_usd` *(derived)* | float-like, 2.266e9–7.2303e10 | 0.0 | 30 / 30 | No | is the target ×1e9 | `= damage_bn_1995 × 1e9` to max\|dev\| **0.000e+00**. Row 6 stores `16629000000.000002` — an IEEE-754 artifact of `16.629 × 1e9` (relative 1.2e-16), cosmetic only. |
| `log_damage_usd` *(derived, THE fitting column)* | float-like, all finite, 21.541282–25.004131 | 0.0 | 30 / 30 | No | is the target, log-transformed | `= log(damage_bn_1995 × 1e9)` to max\|dev\| **0.000e+00**. Span 3.4628 nats. Skew drops 3.1849 (dollars) → 0.4400 (logs). |

**Value-pattern check (mandatory war story):** run on all 8 columns by VALUE, never by dtype.
Result: **0 missing cells out of 240**, **0 sentinels** (`""`, `NA`, `null`, `?`, `-`, `unknown`,
`-999`, `-1`, `9999`, `nan` all absent), **0 string-encoded booleans**, **0 numbers-in-strings**,
**0 mixed-type columns**, **0 exact duplicate rows**. `pre1925_flag` — the one column shaped like
the string-boolean trap — holds genuine integers 0/1. `name` is the only free-text column and
contains no embedded digits, so no `"120bhp@3000rpm"` pattern. Nothing here needs re-encoding.

## Ranked go / no-go issues

Severity: **BLOCKER** (must fix before modeling) · **WARN** (proceed with care) ·
**NOTE** (informational). Order most-severe first. **No BLOCKERs found.**

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | **WARN** | **n = 30, and one observation dominates every tail fit.** max = 72.303 is **2.185×** the second-largest (33.094) and 2.716× the third (26.619); it is 20.5% of the total damage mass (top-3 = 37.5%). Deleting it alone moves the mean −17.8% (11.7499 → 9.6619) and the sd −44.7% (13.6251 → 7.5369). Propagated to the decision unit, the MLE-lognormal 1-in-100 moves **−25.7% / −36.5% / −44.6%** under leave-top-1/2/3-out, and **+99.4%** under the thesis's 10× modification. Parametric bootstrap at n=30 puts σ̂ = 0.8339 in a 95% interval of **[0.617, 1.034]** — a **±25% relative** sampling band on the single parameter that drives the tail. | Proceed — this fragility IS the research object (RQ4/RQ5/RQ6), not a defect. But: (a) never report a return level without its sampling band, or the study will attribute to *estimator choice* a movement that is inside *sampling noise*; (b) the declared `return_level_instability_pct` `minimum_delta` of 1.0 pp is far smaller than the ±25% band on the estimand — treat it as an ordering device between estimators on a *fixed* sample, never as a claim about the population; (c) the Phase-0 paired-bootstrap floor measurement is load-bearing, not a formality. |
| 2 | **WARN** | **The decision functional is out-of-sample by construction.** The largest of 30 sits at plotting position p = 0.9667 ≈ 1-in-30. Every 1-in-100 quantile is therefore pure parametric extrapolation: p = 0.99 lies 0.49 sd beyond the largest-of-30 position. Concretely, the fitted lognormal 1-in-100 (**55.52 bn**) is *below* the largest observation actually seen (72.303 bn) — the "100-year loss" is an artifact of the assumed family, not a data-supported number. Heavier families diverge violently here: `estimators.py` documents log-Cauchy's `tan(0.49π) = 31.8` amplification at p = 0.99. | Proceed, and word every return-level claim as **family-conditional**. In `findings.md`, report return levels for the GoF-passing families side-by-side with the empirical 1-in-30 anchor, so a reader can see how much of the answer is data and how much is distributional assumption. Do not present a single 1-in-100 number as "the" answer. |
| 3 | **WARN** | **The sealed evidence is independent TARGETS, not independent DATA** (`split.kind: none`, n = 30). The pre-registered confirmation compares against published third-party numbers (Adjieteh 2024 Tables 6.9/6.10) rather than a held-out fold — the same 30 observations underlie both the adaptive and the sealed evaluation. | Proceed — the design is sound and honestly the best available at n = 30 (full assessment in checklist row 3). Constrain the *wording* of the confirmation claim: it establishes **implementation fidelity + within-sample robustness**, never out-of-sample generalization. Sampling error is fully common-mode between adaptive and sealed evaluation and the sealed test cannot detect it. |
| 4 | NOTE | **`rank` is a deterministic function of the target** (Spearman exactly −1.000000; `rank == 31 − rankdata(damage)`). So are `damage_usd` and `log_damage_usd` (exact transforms). Four of eight columns are the target under different encodings. | Standing rule for the whole study: **only `log_damage_usd` is consumed, and only as the sample being fitted.** `rank` must NEVER enter any design matrix — a regression of damage on rank is an identity (R² = 1). Non-issue for distribution fitting (see checklist row 1). |
| 5 | NOTE | **The "1925–1995" period label is a mislabel — confirmed, and load-bearing.** Three rows fall outside that window: rank 3 (1900 N Texas/Galveston, 26.619), rank 4 (1915 N Texas/Galveston, 22.602), rank 22 (1919 S Texas, 5.368). They are 15.5% of total damage and two of them are the **#3 and #4 largest events in the sample**. Removing them moves mean 11.7499 → 11.0337 and sd 13.6251 → 13.8539 — i.e. the published Table 6.8 statistics reproduce **only with them included**, which is precisely why the R `extRemes::damage` top-30 (a genuinely 1925–1995 set) does not reproduce the thesis. | No action — already handled. `pre1925_flag` identifies the three rows exactly (set equality with `year < 1925` verified), and `prepare.py`'s identity gate makes substitution of the wrong 30-row set impossible to miss. Cite the mislabel in `findings.md` so a replicator does not "fix" the period and silently break reproduction. |
| 6 | NOTE | **Two quantile conventions coexist in one thesis chapter — a LIVE methodological sensitivity the study explicitly studies, not a data defect.** The *descriptive* Table 6.8 quartiles reproduce **only** under Hazen (max\|dev\| 0.0000); every alternative misses — `normal_unbiased` 0.0851, `median_unbiased` 0.1134, `linear` 0.3280, `weibull` 0.3402, `inverted_cdf` 0.6195. But `estimators.py` records that the thesis *defines* its fitting convention as `F̂⁻¹(p) = X_(⌈np⌉)` = `inverted_cdf`, which reproduces the 96 QLS cells at mean \|dev\| 0.0020 (max 0.0052) versus Hazen's 0.0084 (max 0.0318) — i.e. Hazen breaches the study's own 0.02 `max_abs_param_deviation` guardrail on the estimator tables. | No action at the data gate. `prepare.py` correctly uses `hazen` for the descriptive identity gate and exports `THESIS_QUANTILE_METHOD = "inverted_cdf"` separately; the two are not confused. The convention sweep is pre-registered in `study.yaml` (`predictions_to_falsify`) — this card confirms the sensitivity is real and larger than the 0.005 reporting resolution, which is the sweep's own prediction. |
| 7 | NOTE | **Unit chain billions → log-dollars (×1e9) verified end-to-end, not assumed.** `log(1e9) = 20.723266`. `mean(log_damage_usd) = 22.800182` equals the published MLE-lognormal μ̂ = 22.8002, and `sd(ddof=0) = 0.833868` equals σ̂ = 0.8339 — both to ≤1e-4. A millions-vs-billions misread would place μ̂ at 15.8924, off by `log(1000) = 6.9078`. | None. The anchor pins the scale; a unit error is not silently survivable. |
| 8 | NOTE | Provenance chain is byte-verified. Bundled CSV == data_hub full-data CSV (identical sha256). The data_hub `sample.csv` differs only in trailing-zero formatting (`9.380`→`9.38`, `3.000`→`3.0`) and is numerically identical, so even a silent sample-fallback load cannot change any fitted number. | None — recorded so the equivalence is not re-derived later. |
| 9 | NOTE | `prepare.py`'s module docstring says "the **six** published Table-6.8 statistics"; the gate actually checks **eight** (n, min, q1, q2, q3, max, mean, std_dev) plus **four** MLE-anchor scalars = 12 quantities, and its own final line prints "all 8". Docstring drift only — the gate is stricter than advertised. | Optional one-word docstring fix ("six" → "eight"). Not a gate concern; no behaviour depends on it. |

## Clean-room leakage audit

Performed in a FRESH context (separate agent, no prior study context), reading ONLY `study.yaml`,
`prepare.py`, the prepared artifact, the bundled dataset README/CSV, and `estimators.py` for
consumption of the fitting column — never `program.md`, `research_plan.md`, `playbook.md`, or
`method_card.md`. Rows 3–4 mechanized with:

```
uv run --no-sync python -m kleinlib.leakage data/prepared/hurricane_top30.csv \
  --target damage_bn_1995 --study .
```

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage — no feature is a proxy/derivative of the target or post-outcome information | **PASS (with a standing rule)** | **The target IS the object of study.** This is univariate loss-model fitting: `estimators.py` consumes `log_damage_usd` as a *sample* (sorted order statistics / a quantile grid), with no features, no design matrix over covariates, and nothing to predict damage *from*. `rank` is a deterministic bijection of the target (Spearman = −1.000000 exactly; `rank == 31 − rankdata(damage)`). **Why that is a non-issue here:** the estimators already use the full sorted sample, and rank is exactly that sort order — it carries no information the sample does not already contain, so its presence in the CSV cannot leak anything into a distribution fit. **Why it must never be a covariate:** any model regressing damage on rank recovers an identity (R² = 1) and would report a triumphant, meaningless fit. Same for `damage_usd` and `log_damage_usd` — four of eight columns are the target re-encoded. `year` (r = −0.42), `category` (+0.38), and `pre1925_flag` (+0.25 on the log scale) do carry real association with severity but are **unused by every estimator**. Standing rule recorded as issue #4. |
| 2. Lookahead — encoders/imputers/scalers fit on train only; time-derived features precede the cut | **N/A as designed — one assumption inherited** | **Mechanically nothing to check:** no encoder, imputer, or scaler exists anywhere in the pipeline (`prepare.py` performs one monotone transform, `log(x × 1e9)`, and no fitted preprocessing object is created); no time index enters any estimator; and with `split.kind: none` there is no cut for a feature to precede. The fits are iid loss-model fits. **But the data is not time-free and the assumption must be stated:** `year` spans 1900–1995 and the 30 events are treated as exchangeable draws from ONE severity distribution. That exchangeability rests entirely on **Pielke-Landsea's 1995-dollar normalization** — each damage figure has been adjusted for inflation, personal-property increase, and coastal-county population change, which is the sole reason a 1900 Galveston loss and a 1992 Andrew loss may sit in one iid sample. **Consequence:** any non-stationarity the normalization fails to remove (building codes, wealth composition, warning lead times, insurance penetration, and any trend in storm intensity) is absorbed silently into σ̂ and therefore into every return level. This cannot be tested at n = 30, and the observed r(year, log damage) = −0.42 — later storms slightly *smaller* in normalized terms — is equally consistent with sampling noise or with over-normalization. **Report this as an inherited assumption in `findings.md`; do not claim a stationary severity process was established.** |
| 3. Split contamination — no duplicate rows straddling partitions; group ids never cross partitions; the split reproduces from `study.yaml` | **N/A (mechanized: 3/3 N/A, clean)** | Verbatim: `[OK]   split-reproduces: N/A — split kind 'none' (simulation lab): no partitions to audit` · `[OK]   duplicate-rows: N/A — no partitions` · `[OK]   group-overlap: N/A — no partitions`. Independently confirmed: 0 exact duplicate rows; `(name, year)` unique 30/30 — the two repeated name labels (`N Texas (Galveston)` 1900/1915; `SE Florida` 1945/1949) are distinct events, so there is no hidden group id either. `seed: 42` is declared but unused (no partitioning occurs). **Honest assessment of the substitute design — sealed PUBLISHED targets in place of a held-out fold: STRENGTH** — the targets are third-party numbers fixed in print before this study existed. They cannot be moved by anything the study does, and they cannot be *adaptively* overfit, because the contract restricts adaptive work to Table 6.9 while the sealed reproduction target is the full Table 6.10 grid and the sealed decision target is the exact 10× modification (72.303 → 723.03). That is a stronger anti-peeking guarantee than a random fold, which an analyst can in principle inspect. **WEAKNESS, stated plainly** — the *same 30 observations* underlie both evaluations. There is independence of targets, not of data. Therefore the sealed pass confirms "our implementation reproduces their published numbers on their sample" — an **implementation-fidelity** claim — and confirms nothing about generalization to another hurricane sample, another period, or predictive accuracy. Sampling error is **fully common-mode**: if these 30 draws are unrepresentative, the adaptive and sealed evaluations are wrong together, identically, and the sealed test is structurally blind to it. A residual soft coupling also remains — a specification tuned until it hits Table 6.9 has thereby made much of Table 6.10 predictable — which the design bounds but does not eliminate. **Verdict: appropriate and honest for a reproduction + robustness study; the claim wording is the control that must not slip.** |
| 4. Eval-harness sanity — metric direction matches the contract; constant and shuffled predictors score at chance | **PASS (identity gate verified live) + N/A (chance probe)** | Verbatim: `[OK]   metric-direction[reproduction]: mean_abs_param_deviation: contract-declared direction 'lower' accepted (custom simulation metric)` · `[OK]   chance-level[reproduction]: N/A — split kind 'none': no development partition to score` · `[OK]   metric-direction[decision]: return_level_instability_pct: contract-declared direction 'lower' accepted (custom simulation metric)` · `[OK]   chance-level[decision]: N/A — split kind 'none': no development partition to score` · `7/7 checks passed: clean`. Both metric directions are `lower`-is-better and both name a deviation/instability quantity, so direction and semantics agree. The constant/shuffled-predictor probe is inapplicable — there is no predictor and no scored partition; **the identity gate is what plays its role**, and it was re-run LIVE for this audit (all deviations ≤ 1e-4, gate PASS): `n 0.00e+00` · `min 0.00e+00` · `q1 0.00e+00` · `q2 8.88e-16` · `q3 0.00e+00` · `max 0.00e+00` · `mean 3.33e-05` · `std_dev 2.82e-05`; **both MLE anchors exact at 0.00e+00** — `mle_lognormal_original` μ 22.8002 / σ 0.8339 and `mle_lognormal_modified` μ 22.8769 / σ 1.0975. The prepared artifact re-wrote to the identical `sha256 a0e6a5d9…62db8fd`, proving prep is deterministic. Note the gate covers **8** Table-6.8 statistics plus **4** anchor scalars (12 quantities), not the six named in `prepare.py`'s docstring (issue #9). |

## Go / no-go

> **Decision: GO-WITH-CAUTIONS**
>
> **Rationale:** Zero BLOCKERs. The prepared artifact is as clean as tabular data gets — 30 × 8
> with 0/240 missing cells, 0 sentinels, 0 mixed types, 0 string-encoded booleans, 0 duplicate
> rows, both derived columns exact to 0.000e+00, and a deterministic prep (identical sha256 across
> re-runs). Provenance is byte-verified against the data_hub source, and the live data-identity
> gate reproduces all 12 published quantities at ≤ 3.33e-05 — including both MLE-lognormal anchors
> exactly — which pins the sample, the period trap, the quantile convention, and the ×1e9 unit
> chain simultaneously. The mechanized leakage audit returns 7/7 clean. The four columns that are
> the target re-encoded pose no risk to distribution fitting and are governed by an explicit
> standing rule.
>
> **The three cautions are properties of the research object, not defects to fix:**
> **(1)** n = 30 with one observation at 2.185× the runner-up — σ̂ carries a ±25% bootstrap band,
> so every instability number must be read as an ordering device on a fixed sample, never as a
> population claim. **(2)** The 1-in-100 decision functional is extrapolation beyond the ~1-in-30
> empirical support (the fitted lognormal 1-in-100 of 55.5 bn is *below* the largest observation) —
> report it as family-conditional. **(3)** Sealing supplies independent targets, not independent
> data; the confirmation claim is implementation fidelity plus within-sample robustness, and must
> never be worded as out-of-sample generalization.
>
> Modeling may proceed. These cautions belong in `findings.md` and in the claim wording of the
> verdict card, and must be carried into the confirmation-phase language verbatim.
>
> If NO-GO or any BLOCKER is open, modeling is HARD-BLOCKED. A v2 override must be
> recorded with `klein gate override data --acknowledged-by <actor> --reason <reason>`;
> also explain it in `program.md`. A prose-only fast path does not unlock modeling.
