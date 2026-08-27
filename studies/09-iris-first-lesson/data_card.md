<!--
DATA gate artifact (Gate 1 hashes this file). Draft was committed pre-CONSULT;
every slot below is now filled from prepare.py / kleinlib.leakage output,
run 2026-08-27 under the registered split seed 20260912.
-->

# Data card — 09-iris-first-lesson

## Source & shape

- Modeling frame: `data/prepared/iris_hard_pair.csv` — 100 rows × 7 columns
  (sepal_length_cm, sepal_width_cm, petal_length_cm, petal_width_cm, species,
  is_virginica, group_id), versicolor + virginica only, positive rate exactly
  50/100. Built by `prepare.py` from `sklearn.datasets.load_iris` (sklearn
  1.9.0, the locked env). Committed copy: `fixtures/iris_hard_pair.csv`,
  byte-identical to studies 07/08 (sha256
  9d67302e0fcd71bcfeb0d4cbeb739c5612f0b7d97c488842d1f8903c35f23f05, asserted
  in-script and re-verified by `--check` this run). `species` (3-class code) is
  retained but NEVER a feature — the registered perfect-proxy lineage from 07;
  features are the 4 measurement columns only.
- Setosa is dropped by registration: the audit measures the separability fact —
  setosa max petal_length 1.9 cm vs 3.0 cm minimum for the other two species, a
  clean 1.1 cm one-feature gap — with it in frame every method looks perfect and
  no method question gets asked. The three-class problem and the 100-row hard
  pair answer DIFFERENT questions; this study registers only the second.

## Full-150 audit (the study's data-quality exhibit; `prepare.py --audit`)

`fixtures/full150_audit.json` (sha256 66871dae…236702; byte-identical across
independent processes). Measured 2026-08-27:

- Full-150 canonical CSV sha256 `3a6fc062…c77287a0`; classes exactly 50/50/50.
- **Precision:** every one of the 600 measurement values sits on the 0.1 cm
  grid (all-one-decimal true per feature). Distinct tenths per feature —
  full 150: sepal_length 35 · sepal_width 23 · petal_length 43 · petal_width 22;
  hard pair: 28 · 16 · 34 · 16 (matches 07's profile). petal_width has only 22
  distinct values over 150 flowers: the "continuous" features are coarse
  lattices.
- **Exact duplicates:** in the FULL 150 exactly one duplicated row-content
  group — 0-based rows [101, 142] = iris rows 102/143, both virginica — i.e.
  the twin pair, and nothing else. Within the hard pair: the same single pair.
- **Near-duplicates** (identical in three features, exactly 0.1 cm apart in the
  fourth): 5 pairs in the full 150 (four setosa–setosa, one virginica–virginica),
  and exactly 1 inside the hard pair (virginica positions 78/82, petal_width) —
  distinct flowers one lattice step apart; grouped-twin treatment is NOT
  extended to them (they differ in a recorded measurement; registered ruling).
- **UCI-vs-sklearn provenance diff**, recomputed from study 07's committed
  read-only bytes (`../07-iris-90years/reference/uci_iris.data`): exactly
  3 cells differ, on 0-based rows 34 and 37 (classic errata rows 35/38), both
  setosa; 148/150 rows byte-agree. The errata cannot touch a single hard-pair
  row — re-verified, not merely cited.

## Provenance (inherited rulings, re-verified where mechanical)

Resolved and documented in study 07 (claims 07#C9/#C10/#C17) with committed UCI
evidence: sklearn ships the R/Fisher-corrected copy; UCI's classic file differs
in 3 setosa cells (re-verified above); the twin pair is printed twice in
**Fisher's own 1936 Table I** (scope qualifier binding: "in the forensic
sources we checked", never "nobody ever noticed").

## The twin rows — grouped, never deleted (inherited ruling, re-enforced)

Hard-pair positional rows 51/92 = iris rows 102/143, both virginica,
(5.8, 2.7, 5.1, 1.9). One `group_id = twins102-143`; 99 groups / 100 rows.
At 0.1 cm resolution identical measurements do not prove duplicate entry; we do
not delete historical data — the pair travels together through the outer split,
all 20 metrology redraws, all arena folds and rung subsets, and every inner CV
(group-aware by construction this study; see method card).

## Declared split — materialized (seed 20260912, group-aware 60/20/20; 20260909 RETIRED pre-gate, scouting_ledger S10)

Measured this run via the contract's `three_way_split`:

- train n=60 (28 virginica / 32 versicolor) · development n=20 (11/9) ·
  sealed n=20 (11/9) — the group machinery landed exactly on 60/20/20 this
  time (no ±1 wobble under this seed).
- **Twins landed in TRAIN** ⇒ a multi-row group (`twins102-143`) SITS IN THE
  NON-SEALED POOL. Consequence, exactly as pre-registered: study 08's
  "row-level cv=3 is lawful because no multi-row group is in the pool" argument
  does NOT hold here; every inner CV in this study is group-aware by
  construction (method card §2/§4), and that amendment is load-bearing, not
  decorative.
- Split fingerprint + prepared-data sha256: recorded by the DATA gate ack
  itself (study_state.json `fingerprints`).

## Ranked go / no-go issues

1. Fully scouted data (third study) — mitigated by the prospective lock, the
   disclosure header, and the procedurally-fresh-seal language. GO-able.
2. Twin rows — ruled (grouped). 3. Sealed class mix 11/9 under a group split —
   documented consequence, not a defect (07 precedent). 4. TabPFN checkpoint
   availability — spike PASSED pre-consult (scouting S7).

## Clean-room leakage audit

`uv run --no-sync python -m kleinlib.leakage data/prepared/iris_hard_pair.csv
--target is_virginica --study .` → **9/9 checks passed, exit 0** (both tracks):
split-reproduces (60/20/20 deterministic from study.yaml) · duplicate-rows
(no row content straddles partitions) · group-overlap (99 normalized ids each
in one partition) · metric-direction (val_brier lower, both tracks) ·
constant-chance val_brier 0.2544 · shuffled-chance val_brier 0.5000 (primary
stream) / 0.3000 (challenger stream; per-track RNG streams differ — tool
output recorded as printed). Judgment rows 1–2: no target leakage (features
are physical measurements; `species` excluded by the frozen feature list); no
lookahead (no time axis).

## Go / no-go

> **Decision:** GO — lineage re-verified from committed bytes (3-cell UCI diff,
> setosa-only), the single exact-duplicate group ruled and enforced at every
> split, leakage audit 9/9, fixture byte-identical to 07/08, fingerprints
> frozen at this ack.
