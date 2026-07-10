---
type: data-card
domain: "insurance"
status: go
concepts: [value-pattern-check, class-imbalance, deterministic-derivative-columns]
related: [../../knowledge/best-practices-auto-insurance.md, ../../knowledge/encoder-comparison.md]
---

# Data card — 00-glm-claims-quickstart

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.

## Source & shape

- **Source:** `data_hub:insurance-claims` (kaggle `litvinenko630/insurance-claims`,
  license Apache-2.0 — full text + attribution in `datasets/insurance-claims/DATA_LICENSE`),
  loaded via `kleinlib.data.load_data_hub("insurance-claims")`, which resolves an
  external `$DATA_HUB` when set and otherwise the raw CSV bundled in this repo at
  `datasets/insurance-claims/`.
- **Rows × cols (raw):** 58,592 × 41  ·  **Rows × cols (prepared, `prepare.py` output):**
  58,592 × 45  ·  **Target:** `claim_status`  ·  **Positive rate:** 6.40% (3,748 / 58,592).
- **Profiler used:** `kleinlib.profile_fallback.profile_dataframe` on the **RAW** loaded
  frame (target=`claim_status`); the global `dataset-profiler` skill was not invoked (not
  needed — the fallback is the documented default and its output is sufficient here).

## Profile summary

| Column | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| `policy_id` | `str`, unique per row (`POLxxxxxx`) | 0% | 58,592 (100%) | **Yes** | none (dropped) | Primary key — `prepare.py` drops it (`DROP_COLUMNS`); near-unique values carry no generalizable signal |
| `subscription_length`, `vehicle_age` | `float64`, continuous | 0% | 140 / 49 | No | none | Years; genuinely continuous |
| `customer_age` | `int64` | 0% | 41 | No | none | Years, range ~35–75 |
| `region_code` | `str`, categorical (`C1`–`C22`) | 0% | 22 | No | none | Low-cardinality nominal, safe for OHE |
| `region_density` | `int64`, continuous | 0% | 22 (one value per region) | No | none | Population density per region — right-skewed, log1p-friendly (used in E2) |
| `segment`, `model`, `fuel_type`, `steering_type` | `str`, categorical | 0% | 6 / 11 / 3 / 3 | No | none | Low-cardinality nominal |
| `max_torque`, `max_power` | `str`, **numbers-in-strings** (`"113Nm@4400rpm"`) | 0% | 9 each | No | none | **NOT free text** — `prepare.py` regex-parses to `max_torque_nm`/`max_torque_rpm`/`max_power_bhp`/`max_power_rpm`, then drops the originals |
| `engine_type`, `displacement`, `cylinder`, plus the 4 parsed `max_torque_*`/`max_power_*` cols | `str`/`int64`/`float64` | 0% | ≤11 each | No | **near-deterministic function of `model`** | See ranked issue #2 below — each of the 11 vehicle models has (almost) one fixed engine spec |
| **17 `is_*` columns** (`is_esc`, `is_adjustable_steering`, `is_tpms`, `is_parking_sensors`, `is_parking_camera`, `is_front_fog_lights`, `is_rear_window_wiper`, `is_rear_window_washer`, `is_rear_window_defogger`, `is_brake_assist`, `is_power_door_locks`, `is_central_locking`, `is_power_steering`, `is_driver_seat_height_adjustable`, `is_day_night_rear_view_mirror`, `is_ecw`, `is_speed_alert`) | **`str` dtype, value set exactly `{"Yes","No"}`** | 0% | 2 each | No | none once converted | **THE value-pattern war story, live in this exact environment** — see ranked issue #1 |
| `rear_brakes_type` (Disc/Drum), `transmission_type` (Automatic/Manual) | `str`, 2-valued, non-Yes/No | 0% | 2 each | No | none once converted | Same value-pattern risk class as the `is_*` columns but a different value pair — `prepare.py` maps both explicitly (not caught by `detect_yes_no_columns`, which only matches `{"Yes","No"}`) |
| `airbags`, `turning_radius`, `length`, `width`, `gross_weight`, `ncap_rating` | `int64`/`float64`, continuous/ordinal | 0% | 3–10 | No | none | Vehicle physical specs |
| `claim_status` (target) | `int64`, {0,1} | 0% | 2 | — | — | 6.40% positive — see ranked issue #3 |

**Value-pattern check (mandatory war story) — reproduced live, not just historical:**
under this environment's pandas (3.0.3), every one of the columns above holding
`"Yes"`/`"No"`, `"Disc"`/`"Drum"`, or `"Automatic"`/`"Manual"` reads in with dtype
literally reported as **`str`** (pandas 3.0's default string storage) — *not* `object`.
A naive `dtype == "object"` check would silently skip **all 19 of them** (the 17 `is_*`
columns plus `rear_brakes_type` and `transmission_type`) exactly as it did in the
ancestor campaign, whose ~2-hour war story this gate exists to prevent (see
`war-stories.md` §1). `kleinlib.data.detect_yes_no_columns`/`yes_no_to_int` inspect the
**actual value set**, never the dtype label, and `prepare.py` verifies the post-conversion
dtype is `int64` for all 19 (see prepare.py's run output and the manual dtype check run
during this gate — 17 confirmed `int64` via `detect_yes_no_columns`, 2 more via explicit
Drum/Disc and Manual/Automatic maps).

## Ranked go / no-go issues

Severity: **BLOCKER** (must fix before modeling) · **WARN** (proceed with care) ·
**NOTE** (informational). Order most-severe first.

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | WARN | 17 `is_*` Yes/No columns (+2 more: `rear_brakes_type`, `transmission_type`) read in as **`str` dtype**, not `object` — a naive `dtype == "object"` check silently skips them (the campaign's ~2h war story, reproduced live in this pandas 3.0.3 environment). | Never key on dtype. Detect by VALUE PATTERN: `kleinlib.data.detect_yes_no_columns` for the 17 Yes/No columns (`yes_no_to_int` to map), explicit `{"Drum":0,"Disc":1}` / `{"Manual":0,"Automatic":1}` maps for the other two — all done in `prepare.py`, verified `int64` post-conversion (58,592 rows, 0 nulls). |
| 2 | WARN | 7 columns (`engine_type`, `displacement`, `cylinder`, `max_torque_nm`, `max_torque_rpm`, `max_power_bhp`, `max_power_rpm`) are near-deterministic functions of `model` (11 distinct vehicle models, ≤11 distinct values per column) — redundant information, and a source of near-collinearity for the GLM. | Kept for E1/E2 (LR) to reproduce the campaign's anchor exactly (its baseline did not drop them). **Dropped for E3** (the campaign's HGBT recipe explicitly drops these 7 as a documented ablation that gained +0.0008 AUC) — see `program.md` E3 log line. Drop candidates for any future study on this data too. |
| 3 | WARN | Target `claim_status` is imbalanced: 6.40% positive (3,748 / 58,592). | Calibration doctrine applies (war story §4): prefer `class_weight=None` + isotonic calibration + threshold tuning over naive `class_weight="balanced"` reweighting for probability quality. This study's RQ2/E4 is a direct test of that doctrine on these exact anchor configs — E1/E2/E3 replicate the campaign's historical `class_weight="balanced"` choice on purpose (split-identity requires it), E4 is the doctrine-corrected variant. |

No BLOCKER-severity issue was found: no leakage-risk column, no unusable split, no broken
encoding once the value-pattern conversions above are applied.

## Go / no-go

> **Decision:** **GO**
>
> **Rationale:** All three issues are WARN-severity, each with a concrete, already-applied
> mitigation (value-pattern conversion in `prepare.py`; documented drop-candidates for the
> HGBT recipe; calibration doctrine folded into RQ2/E4 rather than ignored). No BLOCKER is
> open. Row count (58,592), column count (45 prepared), and target rate (6.40%) all match
> the campaign's own documented numbers exactly, which is itself a first data-integrity
> signal ahead of the E1 split-identity gate.
>
> This is a trusted, pre-vetted `data_hub` dataset (already profiled once by the 215-exp
> campaign this study reproduces) — no `--fast-path` override was needed for this gate; the
> full DATA gate protocol was followed in full (profile → value-pattern check → ranked
> issues → verdict).
