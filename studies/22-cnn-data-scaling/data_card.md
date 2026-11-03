---
type: data-card
domain: "deep-learning scaling (image classification)"
modality: image
status: no-go
concepts: []
related: []
---

# Data card — 22-cnn-data-scaling

> Gate 1 (DATA). Written before any modeling. Protocol:
> `.claude/skills/klein/references/data-gate-protocol.md` (image card). The auditor read
> only `study.yaml`, `prepare.py`, `scouting_ledger.md`, the prepared artifact and the
> profile (not `program.md`). Nothing was trained or scored; the sealed test rows were
> only counted, hashed and summarized by pixel statistics.

## Source & shape

Fashion-MNIST (Xiao, Rasul, Vollgraf 2017, Zalando Research), four IDX `.gz` files from
`raw.githubusercontent.com/zalandoresearch/fashion-mnist` (master), each pinned by sha256 in
`study.yaml` (`data.source` + `data.inputs`); `klein doctor --study` reports all four cached
and pin-verified (`pin present=True`). Licence: MIT (repository LICENSE, scouting ledger S1).
No pretrained weights are involved (the study trains a small CNN from scratch).

`prepare.py` is deterministic and writes `data/prepared/images.npy` (uint8, shape
(70000, 28, 28), sha256 `2dab991a2061b345cf0dd827d566abc6328807faa576f3cb2fa2d71cccca79db`)
and `data/prepared/index.csv` (`id,label,split`, sha256
`400b7f7b19120b98bce6be2fd1ef70812d2e74a42f6ae22b9bf400296d387380`). Partitions are
POSITIONS under `split.kind: predefined`; `prepare.py` contains no random state, seed or
`train_test_split` (the `seed: 42` in `study.yaml` is declared inert):

| partition | rows | ids |
|---|---|---|
| train | 50,000 | `tr00000`..`tr49999` (official train rows 0-49,999) |
| development | 10,000 | `tr50000`..`tr59999` (official train rows 50,000-59,999) |
| test (SEALED) | 10,000 | `te00000`..`te09999` (official t10k) |

Ids are unique; no missing values in `id`, `label`, `split`; `label` is int64 0..9.

## Ranked go / no-go issues

1. **BLOCKER (mechanized, open) — near-duplicate audit FAILs.** `--near-dup image` reports
   5,649/10,000 development images (56.49%) and 5,576/10,000 test images (55.76%) with a
   train image within 4 bits of 64-bit dHash, against `--max-rate 0.00`. Any FAIL is a BLOCKER.
   **Diagnosis: a tooling defect (dHash is far too coarse for 28x28 silhouette thumbnails),
   not a data defect.** Byte-identical copies: 0. Genuinely near-identical pairs by pixel
   L2 <= 100 (0-255 scale): 8 development (0.08%) and 4 test (0.04%). Recommended action for
   the lead (not done by this auditor): add a pixel-space criterion or declare a justified
   `--max-rate` with its reason on this card, or obtain a user-recorded risk acceptance.
   `prepare.py` cannot remove the hits; the data are the official files.
2. **WARN — dev rows come from the train file, sealed rows from t10k.** They are not one
   draw by construction. Measured: development vs test standardized difference of per-image
   mean intensity +0.015 SD, per-pixel max |SMD| 0.038 (mean 0.012), class-mix chi-square
   p = 0.91. No detectable first-order shift, which is not proof of none.
3. **WARN — no group ids.** Fashion-MNIST ships no product/colourway identifier, so
   same-product leakage across partitions cannot be audited directly; only the pixel-space
   proxy below was run.
4. **NOTE — checklist row 4 chance check is not mechanizable in index mode** (auditor prints
   N/A); reproduce it from the study's own evaluation path (preflight / noise floor). No
   model was scored here.
5. **NOTE — class balance.** Test exactly 1,000 per class; train 4,950-5,045; development
   955-1,050. Development is taken by position, not stratified.
6. **NOTE — exact duplicates: none.** SHA-256 of each image's bytes: 0 duplicate groups
   within or across partitions, so no conflicting labels; no all-zero images.

## Go / no-go

**NO-GO**, solely because of issue 1: the machine audit FAILs and a BLOCKER is never
silently downgraded. Every other check is clean (exact duplicates 0; index audit 8/8; split
realizable from positions; pins verified). Issue 1 is, on the evidence below, a tooling false
positive, so GO-WITH-CAUTIONS (cautions: WARN 2, WARN 3) is the expected outcome once the lead
records a justified criterion or the user accepts the risk. That choice is not the auditor's.

## Profile summary

All partitions: uint8, min 0, max 255, 28x28 single channel, identical resolution (no
per-partition resize).

| partition | n | mean (0-1) | std (0-1) | zero-pixel fraction | per-class n min..max |
|---|---|---|---|---|---|
| train | 50,000 | 0.2855 | 0.3528 | 0.5025 | 4,950..5,045 |
| development | 10,000 | 0.2887 | 0.3542 | 0.4996 | 955..1,050 |
| test (sealed) | 10,000 | 0.2868 | 0.3524 | 0.4999 | 1,000..1,000 |

Per-class counts (label: train / development / test): 0: 4977/1023/1000; 1: 5012/988/1000;
2: 4992/1008/1000; 3: 4979/1021/1000; 4: 4950/1050/1000; 5: 5004/996/1000;
6: 5030/970/1000; 7: 5045/955/1000; 8: 5032/968/1000; 9: 4979/1021/1000.

Standardized mean differences (per-image mean intensity; per-pixel max/mean |SMD|):

| contrast | per-image SMD | per-pixel SMD | class-mix chi-square p |
|---|---|---|---|
| development vs test | +0.015 | 0.038 / 0.012 | 0.91 |
| train vs development | -0.026 | 0.037 / 0.014 | 0.38 |
| train vs test | -0.011 | 0.030 / 0.008 | not run |

Reading: the official t10k set is distributed like the held-out train rows to within 0.04
SD at every pixel and 0.015 SD overall, so the sealed extrapolation is not expected to be
moved by a dev-vs-test covariate shift (caveat: WARN 2).

Value-pattern check: `id` strings `trNNNNN`/`teNNNNN` (unique, no sentinels), `label`
integers 0-9 (no strings, no NA), `split` exactly `train|development|test`; the payload
holds raw uint8 pixels with no sentinel (0 is background, about 50% of pixels).

## Clean-room leakage audit

Mechanized: `uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study .`
gave `8/8 checks passed: clean`.

| # | Row | Verdict | Evidence |
|---|---|---|---|
| 1 | Target leakage | PASS (judgment) | The model input is the pixel array; the label lives only in `index.csv`; `prepare.py` derives no input from the label. |
| 2 | Lookahead | PASS (judgment) | `prepare.py` fits, scales and normalizes nothing; pixels are written raw (the /255 is a fixed constant applied later). `lib/protocol.py` is outside the clean-room reading list and was not checked. |
| 3 | Split contamination | PASS for ids and exact bytes; near-copies see next section | `[OK] index-table: 70000 rows partitioned by the split column (train=50000 development=10000 test=10000)`; `[OK] duplicate-rows: no id straddles partitions`; `[OK] group-overlap: N/A`; `[OK] time-order: N/A`. 0 shared SHA-256 image hashes across any pair of partitions. Split is positional, so reproducible from `study.yaml` plus the pinned files. |
| 4 | Eval-harness sanity | PASS for direction; chance check deferred | `[OK] metric-direction[primary]: val_mlogloss: contract direction 'lower' matches the canonical registry`; `[OK] metric-direction[exponent]: ... 'higher' accepted`; `[OK] chance-level[...]: N/A — index-table mode carries no target or features`. See NOTE 4. |

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

Command (threshold 4 bits of 64-bit dHash, default `--max-rate 0.0`):

```
uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study . \
    --near-dup image --payload data/prepared/images.npy
```

Output verbatim:

```
[OK]   index-table: 70000 rows partitioned by the `split` column (train=50000 development=10000 test=10000); the index IS the realized split — this audit does not re-derive it
[OK]   duplicate-rows: no id straddles partitions
[OK]   group-overlap: N/A — the index declares no group column
[OK]   time-order: N/A — the index declares no time column
[OK]   metric-direction[primary]: val_mlogloss: contract direction 'lower' matches the canonical registry
[OK]   chance-level[primary]: N/A — index-table mode carries no target or features; reproduce checklist row 4 from the study's own evaluation path
[OK]   metric-direction[exponent]: scaling_exponent: contract-declared direction 'higher' accepted (custom metric of the scalar family)
[OK]   chance-level[exponent]: N/A — index-table mode carries no target or features; reproduce checklist row 4 from the study's own evaluation path
[FAIL] near-duplicates (image, development vs train): 5649/10000 development images (56.49%) have a train image within 4 bits of dHash (max rate 0.00%)
[FAIL] near-duplicates (image, test vs train): 5576/10000 test images (55.76%) have a train image within 4 bits of dHash (max rate 0.00%)
8/10 checks passed: 2 FAIL — any FAIL is a BLOCKER at the DATA gate
```

**Status: FAIL on 2 rows = BLOCKER, open.** Diagnosis, measured on the prepared artifact
(no model involved):

- **Byte-identical copies: 0.** SHA-256 over each image's 784 bytes finds no duplicate group
  within train, development or test, or across any pair. Of the flagged images, 970 (dev) and
  918 (test) share an identical dHash (0 bits) with some train image, which does not mean
  identical pixels.
- **The hash is the defect.** A 64-bit dHash of a 28x28 image keeps a coarse gradient-sign
  map; Fashion-MNIST items are centred high-contrast garment silhouettes, so only 64,099
  distinct hashes exist among 70,000 images (46,048 among the 50,000 train images). Same-shape
  items collide systematically, and a 4-bit radius in so crowded a hash space matches over
  half of each held-out set.
- **Pixel-space check on the flagged pairs** (random 400 flagged per partition; nearest train
  image by L2 on 0-255 pixels over all 784): median L2 785 (dev) and 788 (test), about 28 grey
  levels mean absolute difference; 10th percentile 537/552; none at L2 = 0. For reference,
  unflagged held-out images have median nearest-train L2 about 1,070, and a train image's nearest
  other train image (400 sampled) has median 886, 10th percentile 577. The flagged pairs sit in
  the ordinary nearest-neighbour range, not in the copy regime.
- **Genuine near-copies (full held-out sets, nearest train image):** L2 <= 50: 3 dev, 1 test;
  L2 <= 100: 8 dev (0.08%), 4 test (0.04%); minimum L2 43.2 (dev), 20.8 (test); the 1st
  percentile is about 400 in both. Near-twins also exist inside train (minimum nearest-other
  L2 22 in the 400-image sample), so this is a property of the dataset.
- **Label agreement** of flagged images with their pixel-space nearest train image: 0.87 (dev),
  0.88 (test); with the dHash-nearest train image: 0.79 / 0.77, so the hash neighbour is often
  the wrong class, further evidence that the hash hits are not copies.

**Cause: tooling defect** (a descriptor too coarse for 28x28 thumbnails). Quantified: 0
byte-identical, about 0.04-0.08% genuinely near-identical, 55-56% flagged by dHash. I did not
alter `prepare.py` or the audit tool; the lead decides between a pixel-space criterion or a
declared `--max-rate` with its reason recorded here, and a user-recorded risk acceptance.

> **Decision:** **NO-GO**
