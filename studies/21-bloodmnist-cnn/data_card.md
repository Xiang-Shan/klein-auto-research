---
type: data-card
domain: "medical image classification (hematology microscopy)"
modality: image
status: go-with-cautions   # draft | go | no-go | go-with-cautions
concepts: []
related: []
---

# Data card — 21-bloodmnist-cnn

Recipe `cv-classify`. Audited on the PREPARED artifact (`data/prepared/images.npy` + `index.csv`). No model was trained or scored; the sealed test split was touched only for row counts, label counts, pixel range, and the duplicate / near-duplicate hash audit.

## Source & shape

- Source: MedMNIST v2 `bloodmnist.npz` (Zenodo record 10519652), `url:` pin with sha256 `062023e1...7bddc`; `klein doctor` reports it cached and pin-verified (pin present = True).
- Prepared: `images.npy` uint8 (17092, 28, 28, 3), row i = index row i; `index.csv` (id, label, split), 17,092 unique ids, no missing cells. Splits: the OFFICIAL partitions, `data.split.kind: predefined` (train 11,959 / development 1,712 = MedMNIST val / test 3,421 = SEALED).
- Pixel range 0-255 in every split (no rescaling in prepare.py). Per-channel mean (RGB, /255) on train: 0.7943 / 0.6597 / 0.6962; std 0.2156 / 0.2416 / 0.1179. Development means are within 0.0002 of train (no covariate shift).
- Literal-seed grep over prepare.py / train.py / model.py: the only hits are `seed_everything(SEED)` (model init, not a partition) and docstrings. No `random_state`, no `train_test_split`. The partition comes from the contract only. OK.
- Label provenance: expert-annotated cell classes (8 classes) from the Acevedo et al. 2020 source dataset, carried over directly by MedMNIST. Inter-rater agreement is not stated in the MedMNIST paper. Licence: MedMNIST v2 states its sources are Creative Commons licensed (BloodMNIST: CC BY 4.0 per the dataset page; confirm before redistribution). No pretrained weights are declared.
- Resolution: all splits share one pipeline (centre-crop 200x200 from 360x363, cubic-spline resize to 28x28, per Yang et al. 2023), so there is no per-split resize difference.

## Ranked go / no-go issues

1. **BLOCKER (resolved at the gate) - near-duplicates across partitions.** The auditor's
   `--near-dup image` run (dHash, threshold 4 bits, max-rate 0.00%) FAILed: 3/1712 development
   (0.18%) and 7/3421 test (0.20%) images had a train image within 4 bits — a DATA defect in the
   source (9 byte-identical groups span splits: 3 development-train, 5 test-train, 1
   development-test; one cross-split pair carries conflicting labels). Lead's decision
   (2026-11-03): option (b), remove them — a leak is removed, not given a tolerance.
   `prepare.py` now drops a development item with a near-copy in train and a test item with a
   near-copy in train or in the kept development items, by the audit's own rule (dHash <= 4
   bits). Dropped: development `val00896`, `val00956`, `val01485`; test `test00289`,
   `test01323`, `test02491`, `test02664`, `test02837`, `test02966`, `test03126`, `test03218`
   (prepare.py prints the list). Train is untouched. Counts become development 1,709 and test
   3,413 — published MedMNIST numbers are on 1,712 / 3,421 images, a difference findings must
   state when it compares. The re-run audit passes 8/8 (Near-duplicate audit below).
2. **WARN - the official split is image-level, not grouped by patient/slide; overlap is UNKNOWN and cannot be audited.** The MedMNIST v2 paper (Yang et al., arXiv 2110.14795) says of BloodMNIST only: "We split the source dataset with a ratio of 7 : 1 : 2 into training, validation and test set" - a random image-level split; patient-level splitting is stated only for other datasets (e.g. AdrenalMNIST3D, and generically for datasets with patient ids and no official split). The source (Acevedo et al. 2020) provides no patient or slide identifier I could find, so the index has no `group` column. Likely consequence: one donor's smears sit in train, development and test alike, inflating development AND sealed scores relative to a new-patient deployment. Claims must not say "generalizes to new patients".
3. **WARN - class imbalance (moderate).** Train max/min = 2330/849 = 2.74; development 333/122 = 2.73. Macro-F1 (the primary metric) fits; report per-class F1. Classes 0 and 4 have only 122 development items each, so per-class estimates are noisy.
4. **WARN - exact-duplicate and label-noise hygiene.** 8 byte-identical pairs inside train (all same-label). One cross-split pair has conflicting labels (train01018 label 1 vs test03126 label 6), so at least one is mislabelled; negligible at n = 1 but evidence of source label noise.
5. **NOTE - unnormalized 28x28 uint8.** Normalization is a training choice. Channel stds differ (blue 0.12 vs green 0.24), so per-channel and global normalization are not equivalent.
6. **NOTE - sealed split.** Test label counts (rows only, nothing scored): 244 / 624 / 311 / 579 / 243 / 284 / 666 / 470 for classes 0-7; proportions match train.

## Go / no-go

**GO with cautions.** The one BLOCKER (cross-split near-duplicates) was removed in
`prepare.py` before the gate and the re-run audit is clean. The cautions travel with every
claim: WARN 2 (the official split is image-level, not patient-grouped — scores are
image-level and claims must not say "new patients") and WARN 3 (2.7x class imbalance; two
development classes have about 120 items, so per-class recall is coarse).

## Profile summary

| Item | Value |
|---|---|
| Items | 17,092 (28x28x3 uint8), 8 classes |
| Split (official, predefined) | train 11,959 / development 1,712 / test 3,421 (sealed) |
| Missing / duplicate ids | 0 / 0 |
| Pixel range | 0-255 in all splits |
| Train channel mean (RGB, /255) | 0.7943, 0.6597, 0.6962 |
| Train channel std (RGB, /255) | 0.2156, 0.2416, 0.1179 |
| Imbalance (max/min class) | train 2.74, development 2.73 |
| Exact duplicates within split | train 8, development 0, test 0 |
| Exact duplicates across splits | 9 hash groups (dev-train 3, test-train 5, dev-test 1) |

Per-class counts (test = label counts only):

| class | train | development | test |
|---|---|---|---|
| 0 | 852 | 122 | 244 |
| 1 | 2181 | 312 | 624 |
| 2 | 1085 | 155 | 311 |
| 3 | 2026 | 290 | 579 |
| 4 | 849 | 122 | 243 |
| 5 | 993 | 143 | 284 |
| 6 | 2330 | 333 | 666 |
| 7 | 1643 | 235 | 470 |

Value-pattern check (index.csv): `id` = string `trainNNNNN` / `valNNNNN` / `testNNNNN`; `label` = integers 0-7 only (no sentinel); `split` = exactly {train, development, test}. The payload is a numeric uint8 array with full 0-255 range and no missing values.

## Clean-room leakage audit

| # | Row | Verdict | Evidence |
|---|---|---|---|
| 1 | Target leakage | OK | Features are raw pixels only; the label is a separate column; ids encode only the source split name and a row number, not the class. `prepare.py` derives nothing from the label. |
| 2 | Lookahead | OK | `prepare.py` fits nothing: no scaler, encoder or augmentation. Normalization/augmentation live in train.py/model.py and must be fit on train only. |
| 3 | Split contamination | **FAIL (near-dup only)** | `[OK] index-table: 17092 rows partitioned by the split column (train=11959 development=1712 test=3421)`; `[OK] duplicate-rows: no id straddles partitions`; `[OK] group-overlap: N/A - the index declares no group column`; near-duplicate rows FAIL (below). Fingerprint reproduction is frozen when the gate records. |
| 4 | Eval-harness sanity | OK (index mode) | `[OK] metric-direction[primary]: val_macro_f1: contract direction 'higher' matches the canonical registry`; `[OK] chance-level[primary]: N/A - index-table mode carries no target or features; reproduce checklist row 4 from the study's own evaluation path`. The constant / label-shuffled check must be reproduced from train.py at EXPERIMENT. |

Plain index audit, verbatim: `6/6 checks passed: clean` (command: `uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study .`).

## Group policy

- **Unit of leakage:** the donor/patient (and slide/capture session) - the unit that would leak if it straddled partitions.
- **How the group id is computed:** it cannot be. No patient or slide id is available, so the index declares no `group` column and the group-overlap row is N/A, not a pass.
- **What the official split is:** a random image-level 7:1:2 split (Yang et al. 2023, BloodMNIST section), not grouped. Patient overlap is UNKNOWN and probably non-zero. Ranked WARN 2.
- **Augmentation twins:** none generated before the split (prepare.py does no augmentation).
- **Implication for claims:** development and sealed scores measure image-level, within-donor-population generalization. Published MedMNIST baselines use the same split, so the comparison (P5, RQ4) is like-for-like but not a new-patient estimate.

## Near-duplicate audit

Command: `uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study . --near-dup image --payload data/prepared/images.npy` (dHash, 8x9 grey bins, **threshold 4 bits** (default), **max-rate 0.00%** (default)). Output, verbatim (ASCII hyphens in place of em dashes):

```
[OK]   index-table: 17092 rows partitioned by the `split` column (train=11959 development=1712 test=3421); the index IS the realized split - this audit does not re-derive it
[OK]   duplicate-rows: no id straddles partitions
[OK]   group-overlap: N/A - the index declares no group column
[OK]   time-order: N/A - the index declares no time column
[OK]   metric-direction[primary]: val_macro_f1: contract direction 'higher' matches the canonical registry
[OK]   chance-level[primary]: N/A - index-table mode carries no target or features; reproduce checklist row 4 from the study's own evaluation path
[FAIL] near-duplicates (image, development vs train): 3/1712 development images (0.18%) have a train image within 4 bits of dHash (max rate 0.00%)
[FAIL] near-duplicates (image, test vs train): 7/3421 test images (0.20%) have a train image within 4 bits of dHash (max rate 0.00%)
6/8 checks passed: 2 FAIL - any FAIL is a BLOCKER at the DATA gate
```

Interpretation: data defect, not tooling. The development hits (3) equal exactly the 3
byte-identical development-train pairs; the test hits (7) are the 5 byte-identical test-train
pairs plus 2 near-copies.

Re-run by the lead after `prepare.py` dropped them (same command), verbatim:

```
[OK]   index-table: 17081 rows partitioned by the `split` column (train=11959 development=1709 test=3413); the index IS the realized split — this audit does not re-derive it
[OK]   duplicate-rows: no id straddles partitions
[OK]   group-overlap: N/A — the index declares no group column
[OK]   time-order: N/A — the index declares no time column
[OK]   metric-direction[primary]: val_macro_f1: contract direction 'higher' matches the canonical registry
[OK]   chance-level[primary]: N/A — index-table mode carries no target or features; reproduce checklist row 4 from the study's own evaluation path
[OK]   near-duplicates (image, development vs train): 0/1709 development images (0.00%) have a train image within 4 bits of dHash (max rate 0.00%)
[OK]   near-duplicates (image, test vs train): 0/3413 test images (0.00%) have a train image within 4 bits of dHash (max rate 0.00%)
8/8 checks passed: clean
```

The development-vs-test pair is not an audit row; `prepare.py` removes it by construction
(test is compared against train plus the kept development items).

> **Decision:** **GO** (with the cautions WARN 2 and WARN 3)
