<!--
DATA gate artifact (Gate 1 hashes this file). Draft committed pre-CONSULT;
every TBD-AT-GATE slot is filled from prepare.py / kleinlib.leakage output
before `klein gate record data`. No slot may survive the ack.
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
  in-script). `species` (3-class code) is retained but NEVER a feature — the
  registered perfect-proxy lineage from 07; features are the 4 measurement
  columns only.
- Setosa is dropped by registration: the full-150 audit records the separability
  fact (TBD-AT-GATE: setosa/others petal gap from `fixtures/full150_audit.json`)
  — with it in frame, every method looks perfect and no method question is
  asked. The three-class problem and the 100-row hard pair answer DIFFERENT
  questions; this study registers only the second.

## Full-150 audit (the study's data-quality question; `prepare.py --audit`)

`fixtures/full150_audit.json`, deterministic. TBD-AT-GATE summary to record
here after the run: full-150 sha256 · class counts · per-feature ranges +
distinct-value counts · decimal-precision profile (expected: every value one
decimal, 0.1 cm grid) · exact-duplicate row groups in the full table and in the
hard pair (expected: iris rows 102/143 only, within the hard pair) ·
near-duplicates (pairs differing in one feature by exactly 0.1) · UCI-vs-sklearn
cell diff (expected: exactly 3 cells, setosa rows 35/38, from the committed
07 reference bytes — errata cannot touch the hard pair).

## Provenance (inherited rulings + verification duty)

Resolved and documented in study 07 (claims 07#C9/#C10/#C17) with committed
UCI evidence at `../07-iris-90years/reference/` (read-only): sklearn ships the
R/Fisher-corrected copy; UCI's classic file differs in 3 setosa cells; the twin
pair is printed twice in **Fisher's own 1936 Table I** (scope qualifier binding:
"in the forensic sources we checked", never "nobody ever noticed"). 09's audit
RE-VERIFIES the mechanical parts from committed bytes rather than citing them.

## The twin rows — grouped, never deleted (inherited ruling, re-enforced)

Hard-pair positional rows 51/92 = iris rows 102/143, both virginica,
(5.8, 2.7, 5.1, 1.9). One `group_id = twins102-143`; 99 groups / 100 rows.
At 0.1 cm resolution identical measurements do not prove duplicate entry; we do
not delete historical data — the pair travels together through the outer split,
all 20 metrology redraws, all arena folds and rung subsets, and every inner CV
(group-aware by construction this study; see method card).

## Declared split — materialized (seed 20260912, group-aware 60/20/20; 20260909 RETIRED pre-gate, scouting_ledger S10)

TBD-AT-GATE from `prepare.py` + `three_way_split`: train n=? (class mix ?) ·
development n=? (?) · sealed n=? (?; ±1 group wobble expected) · twins landed
in: ? · **whether any multi-row group sits in the NON-SEALED pool: ?** (this
line decides nothing — every inner CV is group-aware regardless — but it is the
disclosure that 08's non-group cv=3 lawfulness argument does or does not port (under the retired 20260909 a staging measurement put the twins in TRAIN; 20260912 is measured fresh at this gate)).
Split fingerprint + prepared-data sha256: recorded by the gate itself.

## Ranked go / no-go issues

1. Fully scouted data (third study) — mitigated by the prospective lock, the
   disclosure header, and the procedurally-fresh-seal language. GO-able.
2. Twin rows — ruled (grouped). 3. Sealed class imbalance under a group split —
   documented consequence, not a defect (07 precedent). 4. TabPFN checkpoint
   availability — spike PASSED pre-consult (scouting S7).

## Clean-room leakage audit

Mechanized rows 3–4 via `uv run --no-sync python -m kleinlib.leakage
data/prepared/iris_hard_pair.csv --target is_virginica --study .`:
TBD-AT-GATE (expect 6/6 checks pass, exit 0 — split-reproduces, duplicate-rows
non-straddle, group-overlap, metric-direction, constant-chance ~0.25,
shuffled-chance ~0.5). Judgment rows 1–2: no target leakage (features are
physical measurements; `species` excluded by the frozen feature list); no
lookahead (no time axis).

## Go / no-go

TBD-AT-GATE — the line below is written only after every slot above is filled:
(expected form) **Decision: GO** — lineage re-verified from committed bytes,
twins ruling enforced at every split, leakage audit 6/6, fingerprints frozen.
