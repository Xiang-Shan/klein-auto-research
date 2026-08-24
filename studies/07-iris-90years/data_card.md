---
type: data-card
domain: "statistics-history"
status: go-with-cautions        # draft | go | no-go | go-with-cautions
concepts: [fisher-iris, group-split, provenance-diff, duplicate-ruling]
related: [scouting_ledger.md, reference/PROVENANCE.md]
---

# Data card — 07-iris-90years

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.

> **DRAFT — pending user acknowledgement.** Authored 2026-08-24 so the Tuesday ack
> window is read-and-ack. Every mechanized result quoted below was produced by a real
> run on 2026-08-24 against the committed artifact (nothing here is a placeholder).
> **The clean-room leakage audit RE-RUNS on Tuesday, in a fresh isolated context that
> has not read `program.md`, immediately before `klein gate record data`** — that
> re-run, not this one, is the audit of record. If it disagrees with anything below,
> this card is corrected before the gate is recorded.

## Source & shape

- **Source:** `csv:data/prepared/iris_hard_pair.csv`, written by `prepare.py` from
  `sklearn.datasets.load_iris` (scikit-learn 1.9.0, the locked environment). A
  byte-identical fixture is committed at `fixtures/iris_hard_pair.csv`; `prepare.py
  --check` re-derives the frame and compares.
- **Rows × cols:** 100 × 7 · **Target:** `is_virginica` · **Positive rate:** 50.00 %
  (50 virginica / 50 versicolor)
- **Provenance:** Fisher's iris restricted to the versicolor/virginica **hard pair**.
  Setosa is dropped — it is linearly separable from both and would make every method
  look perfect.
- **Hashes** (two different functions — they are supposed to differ):
  raw content `sha256 = 9d67302e0fcd71bcfeb0d4cbeb739c5612f0b7d97c488842d1f8903c35f23f05`
  (identical for `data/prepared/iris_hard_pair.csv` and `fixtures/iris_hard_pair.csv`);
  klein's location-independent artifact fingerprint, which `study_state.json` records
  and preflight prints, `= 83b90f4d465f72027d38d04e0a6b83330347d976a8e7c478dc553cd388c9fc8f`
  (`kleinlib.workflow.fingerprint_path` hashes `b"file\0" + filename + b"\0" + content`).
- **Profiler used:** `kleinlib.profile_fallback` (no global `dataset-profiler` skill on
  this machine).

## Profile summary

`uv run --locked python -m kleinlib.profile_fallback data/prepared/iris_hard_pair.csv --target is_virginica`

| Column | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| `sepal_length_cm` | float64; 28 distinct values, all one-decimal, 4.9–7.9 | 0.0 % | 28 | no | no | a 1936 measurement at 0.1 cm resolution |
| `sepal_width_cm` | float64; 16 distinct, one-decimal, 2.0–3.8 | 0.0 % | 16 | no | no | as above |
| `petal_length_cm` | float64; 34 distinct, one-decimal, 3.0–6.9 | 0.0 % | 34 | no | no | as above |
| `petal_width_cm` | float64; 16 distinct, one-decimal, 1.0–2.5 | 0.0 % | 16 | no | no | as above |
| `species` | int64, value set exactly `{1, 2}` (sklearn's 3-class code; 0 = setosa is absent) | 0.0 % | 2 | no | **YES — perfect proxy** | see issue 1 |
| `is_virginica` | int64, value set exactly `{0, 1}` | 0.0 % | 2 | no | — | the target |
| `group_id` | str; 99 distinct over 100 rows (`row051`…`row150`, plus `twins102-143` twice) | 0.0 % | 99 | **yes** | no | split key, never a feature; see issue 2 |

**Value-pattern check (mandatory war story):** every column was checked by VALUE, not
by dtype. No string-encoded booleans, no numbers-in-strings, no sentinels (`-999`,
`""`, `"NA"`, `"unknown"`), no mixed types, no missing values anywhere. `species` and
`is_virginica` are genuine small-integer codes and their value SETS were asserted in
`prepare.py` (`{1, 2}` and `{0, 1}` respectively), not merely their dtypes.
`group_id` is a true string column and is the only non-numeric column.

## Provenance diff — sklearn vs UCI (scoped to a cell diff, 2 rows)

Committed evidence: `reference/uci_iris.data` (SHA-256
`6f608b71a7317216319b4d27b4d9bc84e6abd734eda7872b71a458569e2656c0`, retrieved
2026-08-24T19:11:06Z, HTTP 200, 4551 bytes) and `reference/uci_iris.names`
(`71a09fb…5eea3`). Full retrieval record: `reference/PROVENANCE.md`.

Cell-level diff of the two 150×4 measurement matrices → **exactly rows 35 and 38
differ, and nothing else.** Three cells differ; shown against both sources that is
**six numbers**:

| Row | Field | UCI `iris.data` | sklearn 1.9.0 | Species |
|---|---|---|---|---|
| 35 | petal width | **0.1** | **0.2** | setosa |
| 38 | sepal width | **3.1** | **3.6** | setosa |
| 38 | petal length | **1.5** | **1.4** | setosa |

Both sources agree on the other 597 cells.

**This is documented errata, not a discovery.** UCI's own `iris.names` — header line
`Updated Sept 21 by C.Blake - Added discrepency information` — states it verbatim:

> This data differs from the data presented in Fishers article (identified by Steve
> Chadwick, spchadwick@espeedaz.net). The 35th sample should be:
> `4.9,3.1,1.5,0.2,"Iris-setosa"` where the error is in the fourth feature. The 38th
> sample: `4.9,3.6,1.4,0.1,"Iris-setosa"` where the errors are in the second and third
> features.

sklearn's `DESCR` states the other side: *"The dataset is taken from Fisher's paper.
Note that it's the same as in R, but not as in the UCI Machine Learning Repository,
which has two wrong data points."* The two statements agree, and our diff matches both:
sklearn carries the corrected values named in `iris.names`.

**Consequence for this study: none, provably.** Both affected rows are **setosa**, which
`prepare.py` drops before the artifact is written. The errata cannot touch a single row
of the hard pair. That is the point of running the check *before* the first model, not
after.

Side effect worth recording: in the UCI file rows 10, 35 and 38 are three identical
setosa rows (`4.9,3.1,1.5,0.1`) precisely *because* of the errata; in sklearn they are
three distinct rows. Also setosa; also outside this study.

## The twin rows — undecidable, ruled, not deleted

Hard-pair positions 51 and 92 — **rows 102 and 143 of the full 150-row table, both
virginica** — carry identical measurements **(5.8, 2.7, 5.1, 1.9)**. Verified: they are
the **only** duplicated row-content in the hard pair (asserted in `prepare.py`), and
they are identical in **both** sources, so the duplication predates scikit-learn's
correction and is not an artifact of it.

**We cannot tell which of two explanations is true.** At 0.1 cm resolution, identical
measurements do **not** prove duplicated record entry — two distinct flowers can round
to the same four numbers. And they are not asserted to be an ERROR: no provenance
evidence exists either way.

Provenance check performed (scoped, 2 rows — **not** a Fisher Table I transcription):
UCI `iris.names` was searched for any mention of rows 102/143, duplication, or
identical records. **No mention found**; its only discrepancy note is the rows-35/38
errata quoted above. Bezdek 1999 remains to be checked and is flagged
citation-verification-pending. **Result: undecidable. The ruling below stands either
way.**

**Ruling: group, do not delete.** Both rows share one `group_id`
(`twins102-143`); the split is declared `kind: group`, so the two rows always travel
into the same partition. Every other row is its own group — 99 groups over 100 rows,
and **n stays 100**.

Why this is the right instrument rather than deletion:

- The harm is a specific mechanism — a memorized twin scored on the other side of a
  split. Grouping removes that mechanism **regardless of which explanation is true**.
- Deleting a row would require asserting the duplicate-entry explanation, which the
  evidence does not support.
- The clean-room duplicate check is **straddle-only**: co-located duplicates pass. So
  the audit passes **without deletion and without an override**.
- Counterfactual, re-derived 2026-08-24 from the committed artifact: under a
  **stratified** split the twins land in different partitions in **16 of 20 seeds** —
  i.e. the leak would have been the normal case, not the unlucky one. Under the
  declared group split at seed 20260828 both twins are in `train`.

## Declared split — materialized

`kind: group`, `group_column: group_id`, seed **20260828**, `development_size 0.20`,
`test_size 0.20`. Reproduced twice, identically, by the mechanized audit:

| Partition | Rows | virginica / versicolor | Note |
|---|---|---|---|
| train | 60 | 33 / 27 | contains the twin group |
| development | 20 | 10 / 10 | the adaptive surface |
| sealed test | 20 | 7 / 13 | never touched until E0009 |

The seed is fresh and pre-committed (the talk date), chosen by a rule the 2026-08-24
scouting never touched. Seed 42 is retired **because** it was scouted — sealed rows
included (`scouting_ledger.md` S6).

## Ranked go / no-go issues

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | **WARN** | **`species` is a perfect proxy for the target.** `species ∈ {1,2}` maps one-to-one onto `is_virginica ∈ {0,1}`; `prepare.py` asserts exactly that. Any model handed the whole frame minus the target would score perfectly. | **Deliberate and mitigated.** The column exists so E0002's registered crash is real evidence rather than a story, and it had to be present from the FIRST write or the DATA fingerprint would move when it was added. Mitigation: feature columns are named literally in `families.py` (`FEATURE_COLUMNS` / `PETAL_COLUMNS` / `SEPAL_COLUMNS`); no code path passes the frame wholesale. The anchor asserts its feature set. The mechanized chance probes are unaffected — they ignore features by construction. |
| 2 | **WARN** | **`group_id` is ID-like** (99/100 unique) and high-cardinality — the profiler flags it on both counts. | Correct and expected: it is the split key, not a feature. Same mitigation as issue 1 — never in any model's column list. |
| 3 | **WARN** | **n = 100, with a 20-row development partition.** Every adaptive decision in this study rests on 20 rows. | Structural, accepted, and it is half the study's subject. Consequences are pre-registered rather than discovered: `val_brier` was chosen because AUC pegs at this n; `minimum_delta` is MEASURED by the split lottery, never guessed; population-level claims are excluded by the registered estimand (`study.yaml:estimand`). |
| 4 | **WARN** | **The sealed partition is 7/13, not 10/10.** A group split is not stratified, so class balance drifts between partitions. | Documented, not fixed — forcing balance would break the group constraint that the twin ruling depends on. The sealed value is read against a 7/13 base rate, and the verdict card says so. Wobble of ±1 row is expected in the lottery draws too. |
| 5 | **NOTE** | The twin rows are **undecidable** (duplicate entry vs two identical flowers). | Ruled by grouping, above. Re-open only if provenance evidence appears; the grouping stands either way. Bezdek 1999 check is pending citation verification. |
| 6 | **NOTE** | `minimum_delta` is still **0** — the floor has not been measured yet. | By design. Phase 0 measures it (`sweeps/kseed_floor.py`, then `sweeps/split_lottery.py`), then `study.yaml` is amended and the CONSULT gate is re-recorded. Both sweep scripts **refuse to run** until all three gates are recorded. No challenger rung may run before that re-record. |

No BLOCKER is open.

## Clean-room leakage audit

Rows 1–2 are judgment calls read out of `prepare.py` plus the profile. Rows 3–4 are
mechanized:

```
uv run --locked python -m kleinlib.leakage data/prepared/iris_hard_pair.csv \
    --target is_virginica --study .
```

Run 2026-08-24, **exit code 0, 6/6 checks passed: clean.**

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage — no feature is a proxy/derivative of the target or post-outcome information | **PASS, conditional** | The four measurement columns are Fisher's raw 1936 observations; none is derived from the target. The artifact DOES contain one perfect proxy, `species` (issue 1) — retained deliberately for the registered crash rung and excluded from every model's feature list by explicit naming in `families.py`. The condition is: any future `train.py` that passes the frame wholesale voids this row. |
| 2. Lookahead — encoders/imputers/scalers fit on train only; time-derived features precede the cut | **PASS** | No time dimension exists. `prepare.py` performs no fitting of any kind — it selects, renames, derives `is_virginica` from `species` row-wise, and assigns `group_id` row-wise. Every scaler lives INSIDE a `sklearn.Pipeline` in `families.py`, so it is fitted on the training partition only, inside each fit. |
| 3. Split contamination — no duplicates straddle partitions; group ids never cross; the split reproduces from `study.yaml` | **PASS** | `[OK] split-reproduces: kind=group reproduces deterministically from study.yaml (train=60 development=20 test=20 rows)` · `[OK] duplicate-rows: no duplicate row content straddles partitions` · `[OK] group-overlap: 99 normalized group ids each stay in one partition` |
| 4. Eval-harness sanity — metric direction matches the contract; constant and shuffled predictors score at chance | **PASS** | `[OK] metric-direction[primary]: val_brier: contract direction 'lower' matches the canonical registry` · `[OK] constant-chance[primary]: val_brier=0.2525 for the constant predictor` · `[OK] shuffled-chance[primary]: val_brier=0.5000 for the label-shuffled predictor`. Both are at chance for a 50/50 target (a constant at the base rate scores ≈0.25; a random permutation scores ≈0.50), so the harness carries no label information. |

**Isolation status of THIS run:** self-performed after the profile was finished, reading
only `study.yaml`, `prepare.py`, the prepared artifact, and the profile. It is a
pre-check, not the audit of record. **A fresh isolated context re-runs rows 3–4 and
re-reads rows 1–2 on Tuesday, immediately before `klein gate record data`**, without
reading `program.md`.

## Go / no-go

> **Decision:** GO-WITH-CAUTIONS
>
> **DRAFT pending user acknowledgement** — the decision line above is the card's ruling;
> the acknowledgement is the user's and is recorded by `klein gate record data`.
>
> **Rationale:** No BLOCKER is open. The artifact is 100 rows of one-decimal
> measurements with zero missingness, every column checked by value, a deterministic
> group split that reproduces twice from the contract alone, and a mechanized audit that
> passes 6/6. The provenance question was closed before the first model ran — the errata
> are documented, verified against two primary sources, and provably cannot touch the
> hard pair. The duplicate question was ruled without deleting historical data and
> without an override.
>
> **Cautions accepted:** (1) `species` is a perfect target proxy retained on purpose for
> the registered crash rung, mitigated by explicit feature naming; (2) `group_id` is
> ID-like by construction and is the split key, never a feature; (3) n = 100 with a
> 20-row development partition bounds every adaptive claim, which is why the metric,
> the measured floor, and the registered estimand are all chosen for that regime;
> (4) the sealed partition is 7/13, not 10/10 — a group split is not stratified, and the
> sealed number is read against its own base rate.
>
> Suggested `--note` for the gate record:
> `"cautions accepted: species is a deliberate target proxy for the registered crash rung (never a feature); group_id is ID-like by construction; n=100 with a 20-row development partition; sealed partition is 7/13"`
