---
type: data-card
domain: "deep-learning scaling (image classification)"
modality: image
status: go-with-cautions
concepts: []
related: []
---

# Data card — 22-cnn-data-scaling

> Gate 1 (DATA). Written before any modeling. Protocol:
> `.claude/skills/klein/references/data-gate-protocol.md` (image card). The auditor read
> only `study.yaml`, `prepare.py`, `scouting_ledger.md`, the prepared artifact and the
> profile (not `program.md`). Nothing was trained or scored; the sealed test rows were
> only counted, hashed, compared in pixel space and summarized by pixel statistics.
> Revision 2 (2026-11-03): after the lead's resolution of the first card's BLOCKER (program.md,
> "Lead decisions after the DATA/METHOD review"), `prepare.py` was re-run and every audit
> repeated on the new prepared artifact.

## Source & shape

Fashion-MNIST (Xiao, Rasul, Vollgraf 2017, Zalando Research), four IDX `.gz` files from
`raw.githubusercontent.com/zalandoresearch/fashion-mnist` (master), each pinned by sha256 in
`study.yaml` (`data.source` + `data.inputs`); `klein doctor --study` reports all four cached
and pin-verified (`pin present=True`). Licence: MIT (repository LICENSE, scouting ledger S1).
No pretrained weights are involved (the study trains a small CNN from scratch).

`prepare.py` is deterministic and writes `data/prepared/images.npy` (uint8, shape
(69987, 28, 28), sha256 `363157a97ce6fc555e814457b5cd67775ee4b7deb3fba3cdda2d07862944f172`)
and `data/prepared/index.csv` (`id,label,split`, sha256
`08fcd32c6b20a62795b79525fa61578882bce039f6599c9f2da8bd5b2c8ef972`). Partitions are
POSITIONS under `split.kind: predefined`; `prepare.py` contains no random state, seed or
`train_test_split` (the `seed: 42` in `study.yaml` is declared inert). After the positional
lanes are cut, `prepare.py` removes pixel-level copies (see Near-duplicate audit): development
images within 4 grey levels RMS of a train image, and test images within 4 grey levels RMS of a
train or kept development image. Train is never touched.

| partition | rows | ids |
|---|---|---|
| train | 50,000 | `tr00000`..`tr49999` (official train rows 0-49,999) |
| development | 9,992 | `tr50000`..`tr59999` minus 8 removed (official train rows 50,000-59,999) |
| test (SEALED) | 9,995 | `te00000`..`te09999` minus 5 removed (official t10k) |

The sealed fit pool (train + development) is 59,992. Ids are unique; no missing values in
`id`, `label`, `split`; `label` is int64 0..9. `prepare.py` was re-run through the logged runner (exit 0); the output is byte-deterministic.

## Ranked go / no-go issues

No BLOCKER is open. The first revision's BLOCKER (dHash near-duplicate audit FAIL, 56% of
held-out images flagged) was a tooling false positive and is resolved by the lead's framework
fix: the exact pixel-space criterion `--pixel-rmse 4`, plus removal of the genuine copies in
`prepare.py`. Resolved, with evidence in the Near-duplicate audit section.

1. **WARN - development rows come from the train file, sealed rows from t10k.** They are not
   one draw by construction. Measured on the prepared artifact (full sets): development vs
   test standardized difference of per-image mean intensity +0.015 SD, per-pixel max |SMD|
   0.038 (mean 0.012), class-mix chi-square p = 0.90. No detectable first-order shift, which
   is not proof of none.
2. **WARN - no group ids.** Fashion-MNIST ships no product/colourway identifier, so
   same-product leakage across partitions cannot be audited directly; only the pixel-space
   proxy below was run (it removes pixel-level copies, not same-product different-view twins).
3. **NOTE - checklist row 4 chance check is not mechanizable in index mode** (auditor prints
   N/A); reproduce it from the study's own evaluation path (preflight / noise floor). No
   model was scored here.
4. **NOTE - class balance.** Test 998..1,000 per class; train 4,950..5,045; development
   954..1,048. Development is taken by position, not stratified.
5. **NOTE - exact duplicates: none.** SHA-256 of each prepared image's bytes: 0 duplicate
   groups within or across partitions (so no conflicting labels); no all-zero images.
6. **NOTE - the dHash audit remains a known false positive.** It still FAILs if run without
   `--pixel-rmse` (see below); it is reported verbatim and is not a data defect. The pixel-space
   audit is the criterion of record.

## Go / no-go

**GO-WITH-CAUTIONS.** The pixel-space audit passes 10/10 (0 held-out images within 4 grey levels
RMS of any fit-pool image), the plain index audit passes 8/8, exact duplicates are 0, the split
is realizable from positions, and pins are verified. Cautions: WARN 1 (development rows from
the train file, the sealed rows from t10k) and WARN 2 (no group ids). Not a risk acceptance:
no user-recorded acceptance was needed because no BLOCKER remains.

## Profile summary

All partitions: uint8, min 0, max 255, 28x28 single channel, identical resolution (no
per-partition resize). All figures below are full-set (no sampling).

| partition | n | mean (0-1) | std (0-1) | zero-pixel fraction | per-class n min..max |
|---|---|---|---|---|---|
| train | 50,000 | 0.2855 | 0.3528 | 0.5025 | 4,950..5,045 |
| development | 9,992 | 0.2888 | 0.3542 | 0.4996 | 954..1,048 |
| test (sealed) | 9,995 | 0.2868 | 0.3524 | 0.4999 | 998..1,000 |

Per-class counts (label: train / development / test): 0: 4977/1023/998; 1: 5012/985/999;
2: 4992/1008/1000; 3: 4979/1021/1000; 4: 4950/1048/999; 5: 5004/996/1000;
6: 5030/968/999; 7: 5045/954/1000; 8: 5032/968/1000; 9: 4979/1021/1000.

Standardized mean differences (full sets; per-image mean intensity; per-pixel max/mean |SMD|,
pixels with zero variance in both partitions excluded; class-mix chi-square on the 2x10 table):

| contrast | per-image SMD | per-pixel SMD max / mean | class-mix chi-square p |
|---|---|---|---|
| development vs test | +0.015 | 0.038 / 0.012 | 0.90 |
| train vs development | -0.026 | 0.037 / 0.014 | 0.37 |
| train vs test | -0.011 | 0.029 / 0.008 | 1.00 |

Reading: the official t10k set is distributed like the held-out train rows to within 0.04
SD at every pixel and 0.015 SD overall, so the sealed extrapolation is not expected to be
moved by a dev-vs-test covariate shift (caveat: WARN 1).

Value-pattern check: `id` strings `trNNNNN`/`teNNNNN` (unique, no sentinels), `label`
integers 0-9 (no strings, no NA), `split` exactly `train|development|test`; the payload
holds raw uint8 pixels with no sentinel (0 is background, about 50% of pixels).

## Clean-room leakage audit

Mechanized: `uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study .`
gave `8/8 checks passed: clean` (index-table: 69987 rows; train=50000 development=9992 test=9995).

| # | Row | Verdict | Evidence |
|---|---|---|---|
| 1 | Target leakage | PASS (judgment) | The model input is the pixel array; the label lives only in `index.csv`; `prepare.py` derives no input from the label (the near-copy removal uses pixels only). |
| 2 | Lookahead | PASS (judgment) | `prepare.py` fits, scales and normalizes nothing; pixels are written raw (the /255 is a fixed constant applied later). `lib/protocol.py` is outside the clean-room reading list and was not checked. |
| 3 | Split contamination | PASS | `[OK] index-table`, `[OK] duplicate-rows: no id straddles partitions`, `[OK] group-overlap: N/A`, `[OK] time-order: N/A`; 0 shared SHA-256 image hashes across any pair; pixel-space audit 0/9992 and 0/9995 within 4 grey levels RMS. Split is positional, reproducible from `study.yaml` plus the pinned files. |
| 4 | Eval-harness sanity | PASS for direction; chance check deferred | `[OK] metric-direction[primary]: val_mlogloss ... 'lower'`; `[OK] metric-direction[exponent]: ... 'higher' accepted`; `[OK] chance-level[...]: N/A` in index mode. See NOTE 3. |

## Group policy

- **Unit of leakage.** The unit that would leak is the product (one article in several
  colourways or views), not the file. Fashion-MNIST ships no product id, so the index has no
  group column (`group-overlap: N/A`). The dataset paper describes each image as a front-look
  thumbnail of a Zalando product, converted to 28x28 greyscale, with an official 60,000/10,000
  train/test split. I could not confirm from the files whether same-product twins straddle the
  official split, and this card does not claim they do not.
- **Handling.** None available; the contract uses the official positional split. The
  pixel-space neighbour analysis below is the only proxy for same-product leakage.
- **Label provenance.** From the dataset's construction (per the paper, assigned from
  Zalando's product-category data and checked by in-house experts). Inter-rater agreement is
  not in the files and label noise is not quantified here; expect a small irreducible error floor.
- **Augmentation twins.** None: `prepare.py` makes no augmented copies.
- **Resolution/channels.** 28x28x1 uint8 for every partition.

## Near-duplicate audit

Reference sets: development is audited against train; the sealed test is audited against
train + development, the pool a sealed run fits on. Distances below are RMS differences in
grey levels on the 0-255 scale, i.e. L2 / sqrt(784) = L2 / 28 (an RMS, not a mean absolute
difference).

### Criterion of record: pixel-space RMS

Command:

```
uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study . \
    --near-dup image --payload data/prepared/images.npy --pixel-rmse 4
```

Output verbatim:

```
[OK]   index-table: 69987 rows partitioned by the `split` column (train=50000 development=9992 test=9995); the index IS the realized split — this audit does not re-derive it
[OK]   duplicate-rows: no id straddles partitions
[OK]   group-overlap: N/A — the index declares no group column
[OK]   time-order: N/A — the index declares no time column
[OK]   metric-direction[primary]: val_mlogloss: contract direction 'lower' matches the canonical registry
[OK]   chance-level[primary]: N/A — index-table mode carries no target or features; reproduce checklist row 4 from the study's own evaluation path
[OK]   metric-direction[exponent]: scaling_exponent: contract-declared direction 'higher' accepted (custom metric of the scalar family)
[OK]   chance-level[exponent]: N/A — index-table mode carries no target or features; reproduce checklist row 4 from the study's own evaluation path
[OK]   near-duplicates (image, development vs train): 0/9992 development images (0.00%) have a train image within 4 grey levels RMS (pixel space; max rate 0.00%)
[OK]   near-duplicates (image, test vs train+development): 0/9995 test images (0.00%) have a train+development image within 4 grey levels RMS (pixel space; max rate 0.00%)
10/10 checks passed: clean
```

### Removed by `prepare.py` (RMS <= 4 grey levels; nearest reference by exact pixel search)

Measured on the raw (pre-removal) arrays. All 13 were label-consistent with their nearest
reference and none was byte-identical (minimum RMS 0.743). 12 nearest references are train
images; the 13th (te09867) has a kept development image, tr58762, as its nearest reference.

| removed id | label | nearest reference id | ref label | RMS |
|---|---|---|---|---|
| tr50759 (dev) | 4 | tr12981 | 4 | 2.739 |
| tr51488 (dev) | 6 | tr11932 | 6 | 1.608 |
| tr51503 (dev) | 1 | tr31061 | 1 | 2.991 |
| tr51970 (dev) | 1 | tr24633 | 1 | 3.404 |
| tr53657 (dev) | 6 | tr03350 | 6 | 3.398 |
| tr54953 (dev) | 4 | tr46517 | 4 | 3.072 |
| tr56201 (dev) | 1 | tr31061 | 1 | 1.736 |
| tr59812 (dev) | 7 | tr45497 | 7 | 1.542 |
| te02115 (test) | 1 | tr18494 | 1 | 3.564 |
| te02605 (test) | 6 | tr11932 | 6 | 2.757 |
| te04998 (test) | 0 | tr13360 | 0 | 0.743 |
| te06210 (test) | 4 | tr19456 | 4 | 3.396 |
| te09867 (test) | 0 | tr58762 | 0 | 2.347 |

### What remains after removal (full held-out sets, nearest fit-pool image)

| held-out set vs reference | min RMS | 1st pct | 5th pct | median | count <= 8 | label agreement with nearest |
|---|---|---|---|---|---|---|
| development vs train | 5.34 | 14.64 | 18.25 | 31.96 | 8 | 0.846 |
| test vs train + development | 4.58 | 14.27 | 17.94 | 31.54 | 6 | 0.850 |

For scale, train leave-one-out nearest-other distance (seeded sample: `numpy.random.default_rng(0)`,
2,000 train images; not the full set): min 5.30, 1st pct 14.51, median 31.51, 0 at <= 4. Held-out
images sit in the same range as train-vs-train neighbours. Residual image pairs between 4 and 8
grey levels (8 development, 6 test) are retained; the threshold and its rationale are the lead's.

### Known false positive: 64-bit dHash (4-bit radius), run without `--pixel-rmse`

Command: `uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study . --near-dup image --payload data/prepared/images.npy`
(default `--max-rate 0.0`). Output verbatim (the two near-duplicate rows; the 8 index rows were
the same `[OK]` lines as above):

```
[FAIL] near-duplicates (image, development vs train): 5641/9992 development images (56.46%) have a train image within 4 bits of dHash (max rate 0.00%)
[FAIL] near-duplicates (image, test vs train+development): 5728/9995 test images (57.31%) have a train+development image within 4 bits of dHash (max rate 0.00%)
8/10 checks passed: 2 FAIL — any FAIL is a BLOCKER at the DATA gate
```

This is reported, not hidden: it is a tooling false positive, not a data defect. A 64-bit dHash
keeps a coarse gradient-sign map of a centred high-contrast silhouette, so same-shape garments
collide systematically; the same rows pass the exact pixel criterion above (0 within 4 grey
levels RMS; nearest-neighbour median 31.5-32.0 grey levels RMS; nearest-neighbour labels agree
only 0.85). The dHash result is not the criterion of record and does not make the card NO-GO.

> **Decision:** **GO-WITH-CAUTIONS**
