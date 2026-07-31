---
type: data-card
domain: "insurance"
status: go
concepts: [claim-frequency, exposure, poisson]
related: [../00-glm-claims-quickstart/data_card.md]
---

# Data card — 04-fremtpl2-frequency

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.

## Source & shape

- **Source:** `data_hub:freMTPL2` — resolved through `$DATA_HUB` →
  `loaders.python.hub.load_dataset("freMTPL2")` (provenance line printed by
  `kleinlib.data.load_data_hub`). French Motor TPL, 678,013 policies, 26,406
  claims, 358,360 exposure-years. Hub provenance: Kaggle mirror of the
  CASdatasets table ("GLM example" variant).
- **Prepared artifact:** `data/prepared/fremtpl2_frequency.csv` — 678,013 × 12
  raw columns. The hub table ships **46 extra columns that must not survive
  prep**: pre-baked patsy dummies (`Area[T.B]`…), duplicate numerics
  (`VehPower.1`…), and five derived/leakage columns — `ClaimAmount`,
  `PurePremium`, `AvgClaimAmount`, `Intercept`, and **`Frequency`, which IS the
  target** (ClaimNb/Exposure). All dropped in `prepare.py`.
- **Target:** `ClaimNb` (counts), modeled as frequency with `Exposure` as the
  Poisson weight. **Profiler:** `kleinlib.profile_fallback`.

## Profile summary

| Column | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| IDpol | int, all unique | 0 | 678,013 | **yes** | row identity | excluded from features by `pipeline.py` |
| ClaimNb | int 0–4 | 0 | 5 | no | target | 96.32% zeros; 3.48% ones; 0.20% ≥2 |
| Exposure | float (0, 1] | 0 | many | no | weight | already clipped in this variant (0 rows needed the literature caps — pre-cleaned upstream, note the provenance) |
| VehPower/VehAge/DrivAge/BonusMalus | int, sane ranges | 0 | low | no | no | BonusMalus 50–230 |
| Density | int, heavy right tail | 0 | high | no | no | log-shaping candidate (RQ2) |
| Area/VehBrand/VehGas/Region | str | 0 | 6/11/2/22 | no | no | OHE-friendly cardinality |

**Value-pattern check:** all columns hold what they claim; no sentinels, no
strings-in-numbers. The one surprise is upstream pre-cleaning (see Exposure).

## Ranked go / no-go issues

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | WARN | The raw hub table contains the target in disguise (`Frequency`) plus four more derived columns — any prep that keeps "all numeric columns" silently trains on the answer | Prep keeps an explicit 12-column allowlist; the clean-room audit re-checks below |
| 2 | WARN | Extreme class imbalance in counts (96.3% zero) — deviance is the right loss, but single-split deltas need the measured floor before being believed | Phase-0 noise floor sets `minimum_delta`; calibration ratio tracked in aux |
| 3 | NOTE | This Kaggle variant is pre-clipped (0 rows hit the literature's ClaimNb/Exposure caps) — numbers will differ slightly from papers using raw CASdatasets | Disclosed here and in findings §⑥ |

## Clean-room leakage audit

`python -m kleinlib.leakage` **could not run** (it rejects the simulation
task-label this study was forced into by the missing deviance metrics — soak
friction F3); checks 3–4 were reproduced by hand with the same mechanics,
reading only `study.yaml`, `prepare.py`, `pipeline.py`, and the artifact:

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage | PASS | The five derived columns (incl. `Frequency`) are dropped by prepare's allowlist; no surviving feature is post-outcome |
| 2. Lookahead | PASS | Single preprocessing pipeline fit on train only (`pipeline.fit_and_deviance`); no temporal features |
| 3. Split contamination | PASS | Split reproduces deterministically (two independent reproductions byte-agree); 4,872 duplicate FEATURE profiles straddle train/dev (3.7% of dev) — coarse rating factors legitimately repeat and IDpol (unique) is excluded, so this is profile coincidence, not row identity |
| 4. Eval-harness sanity | PASS | Direction real: null 0.473037 > GLM 0.454861 (lower=better); shuffled-target GLM scores 0.467837 ≈ null (within 1.1% — at chance; the small dip is regularized shrinkage toward the mean) |

## Go / no-go

> **Decision:** GO
>
> **Rationale:** Clean 12-column artifact with the target-in-disguise columns
> provably removed, a deterministic reproducible split, and a harness that
> scores shuffled targets at chance. The imbalance is the study's subject, not
> a blocker.
