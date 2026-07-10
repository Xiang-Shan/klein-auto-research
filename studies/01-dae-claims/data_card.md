---
type: data-card
domain: "insurance"
status: go
concepts: [value-pattern-check, class-imbalance, rankgauss, swap-noise-eligibility, deterministic-derivative-columns]
related: [../../knowledge/best-practices-auto-insurance.md, ../../knowledge/encoder-comparison.md]
---

# Data card — 01-dae-claims

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.
> Same trusted dataset as study 00; this card adds the **DAE-specific column routing**
> (which columns enter the DAE, and how) that this study depends on.

## Source & shape

- **Source:** `data_hub:insurance-claims` (kaggle `litvinenko630/insurance-claims`,
  Apache-2.0), already on disk — loaded via `kleinlib.data.load_data_hub("insurance-claims")`,
  preprocessed by `prepare.py` (byte-identical output to study 00's prepare.py).
- **Rows × cols (prepared):** 58,592 × 45  ·  **Target:** `claim_status`  ·
  **Positive rate:** 6.40% (3,748 / 58,592).
- **Profiler:** `kleinlib.profile_fallback.profile_dataframe` on the prepared CSV
  (`--target claim_status`). Only flag raised: target imbalance (6.4% minority). 0% missing
  in every column.
- **DAE input encoded dim (measured at fit): `d = 94`** = 21 RankGauss numerics + 17 `is_*`
  passthrough + 56 one-hot categorical dims (see routing below).

## Profile summary (grouped)

| Group | Columns | Dtype (value-pattern) | Card. | Notes |
|---|---|---|---|---|
| Continuous numerics | `subscription_length`, `vehicle_age`, `customer_age`, `region_density`, `turning_radius`, `length`, `width`, `gross_weight`, `max_torque_nm`, `max_power_bhp`, `power_to_weight`, `torque_per_litre` | float/int, continuous | 8–140 | genuinely continuous; RankGauss-friendly |
| Low-card ordinal numerics | `airbags`, `displacement`, `cylinder`, `ncap_rating`, `max_torque_rpm`, `max_power_rpm`, `safety_features_count` | int | 2–9 | discrete but numeric |
| Binary maps (0/1) | `rear_brakes_type` (Disc/Drum), `transmission_type` (Manual/Auto), `cylinder`… | int {0,1} | 2 | were string 2-value cols; mapped in `prepare.py` |
| **17 `is_*` accessory flags** | `is_esc`, `is_adjustable_steering`, `is_tpms`, `is_parking_sensors`, `is_parking_camera`, `is_front_fog_lights`, `is_rear_window_wiper`, `is_rear_window_washer`, `is_rear_window_defogger`, `is_brake_assist`, `is_power_door_locks`, `is_central_locking`, `is_power_steering`, `is_driver_seat_height_adjustable`, `is_day_night_rear_view_mirror`, `is_ecw`, `is_speed_alert` | **`str` `{"Yes","No"}` → int {0,1}** | 2 | THE value-pattern war story (below); passthrough in the DAE |
| Categoricals (str) | `region_code` (22), `segment` (6), `model` (11), `fuel_type` (3), `engine_type` (11), `steering_type` (3) | str, nominal | 3–22 | low cardinality → safe for OHE |
| Target | `claim_status` | int {0,1} | 2 | 6.40% positive |

**Value-pattern check (mandatory war story) — reproduced live.** Under this environment's
pandas the 17 `is_*` columns and the two binary maps read in as **`str` dtype, not
`object`** — a naive `dtype == "object"` check would silently skip all 19, exactly the
ancestor campaign's ~2h war story. `prepare.py` detects them by VALUE SET
(`kleinlib.data.detect_yes_no_columns` for the Yes/No 17; explicit Drum/Disc and
Manual/Automatic maps for the other two), never by dtype label; all confirmed int {0,1}
post-conversion, 0 nulls.

## DAE-specific column routing (what enters the autoencoder, and how)

`dae.py` routes every prepared feature column into exactly one of three encoders and
records `input_dim_ = 94`:

| Route | Columns | Encoder | Swap-noise eligible? |
|---|---|---|---|
| **RankGauss numerics** (21) | all numeric columns EXCEPT `is_*` (the two continuous + ordinal + binary-map groups above) | `QuantileTransformer(output_distribution="normal")` after median-impute → 21 dims | **Yes** |
| **`is_*` passthrough** (17) | the 17 accessory flags | passed through as 0/1 → 17 dims | **NO — deliberately excluded** (corrupting a 0/1 accessory flag is not meaningful denoising signal) |
| **One-hot categoricals** (6) | `region_code`, `segment`, `model`, `fuel_type`, `engine_type`, `steering_type` | `OneHotEncoder(min_frequency=20, handle_unknown="ignore")` → **56 dims** (every category clears the 20-count floor at 58k rows, so no infrequent bucketing) | **Yes** (whole one-hot group swapped together via original-column corruption) |

Swap noise is applied at the **original-column level** then re-encoded, so a categorical
swap stays a valid single one-hot and a numeric swap gets RankGauss'd consistently
(`dae.py` docstring). The two binary-map columns (`rear_brakes_type`, `transmission_type`)
and `cylinder` are 2-valued but routed as numerics → RankGauss maps them to two quantile
points — valid, if degenerate; noted as informational, not a blocker.

## Ranked go / no-go issues

Severity: **BLOCKER** (fix before modeling) · **WARN** (proceed with care) · **NOTE**.

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | WARN | Target `claim_status` imbalanced: 6.40% positive. | **Calibration doctrine** (war story §4): for the DOWNSTREAM classifiers (LGBM/LR probes) prefer `class_weight=None` + isotonic calibration + threshold tuning over `class_weight='balanced'`, which wrecks calibration on weak-signal data. E1 uses `class_weight='balanced'` ONLY to reproduce the split-identity anchor — not a recommendation. The DAE itself is unsupervised, so imbalance does not affect representation learning; it bites only the classifiers on top. Rank quality (AUC) is the primary metric; calibration/lift go to `aux_metrics.tsv`. |
| 2 | NOTE | 7 columns are **near-deterministic functions of `model`** (`engine_type`, `displacement`, `cylinder`, `max_torque_nm`, `max_torque_rpm`, `max_power_bhp`, `max_power_rpm`) — 11 vehicle models, ≤11 values each. | Redundant, but for a DAE this redundancy is USEFUL (it is exactly the inter-column structure the denoiser learns to exploit — a corrupted `max_power` can be recovered from `model`). Kept for all experiments. A drop-candidate only if a future study wants a leaner input. |
| 3 | NOTE | RankGauss on the 2-valued numerics (`rear_brakes_type`, `transmission_type`, `cylinder`) is degenerate (two quantile points). | Harmless — the OHE path is reserved for the string categoricals; these binaries are numeric and their two-point RankGauss image is a valid (if trivial) scaling. No action. |

No BLOCKER: no leakage column (the ID `policy_id` is dropped in `prepare.py`), no unusable
split, no broken encoding once the value-pattern conversions are applied. Row/column/target
numbers match the campaign exactly — a first data-integrity signal ahead of the E1 gate,
which then confirms it bit-exactly (`val_auc = 0.625462`).

## Go / no-go

> **Decision:** **GO**
>
> **Rationale:** All open issues are WARN/NOTE with concrete, already-applied mitigations
> (calibration doctrine for the downstream classifiers; value-pattern conversion in
> `prepare.py`; `is_*` excluded from swap noise; documented DAE routing → 94-dim input). No
> BLOCKER. This is a trusted, pre-vetted `data_hub` dataset (the same one the 215-experiment
> campaign used); the full DATA gate protocol was followed — no `--fast-path` override
> needed. Modeling is unblocked.
