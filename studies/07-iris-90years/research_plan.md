# Research plan — 07-iris-90years

> CONSULT (Gate 0) output. `study.yaml` is the machine contract; this file is the
> human-readable plan. Protocol:
> `.claude/skills/klein/references/consult-protocol.md`.

## Question

On Fisher's 100 hard-pair iris rows (versicolor vs virginica, target
`is_virginica`), does any of four pre-registered post-1936 challengers — logistic
regression, kNN, SVM-RBF, HGBT — improve `val_brier` over the 1936 Fisher/LDA
anchor by at least the measured split-lottery floor on the declared group-aware
split, and is petal-only LDA within that floor of the all-four-feature LDA?

## What this study IS and IS NOT

This is a **prospectively locked, sealed confirmation run after documented
scouting**. On 2026-08-24 the design panel measured this same dataset: dev
AUC/logloss/Brier ladders, 20-seed lotteries, the seed-42 sealed rows, the twin
rows, the Fisher-coefficient gap. Those measurements adaptively shaped the metric
(Brier, chosen because scouted AUC saturated), the candidate set, the floor
recipe, and both pre-committed narratives. Every scouted number and every
adaptive influence is disclosed in `scouting_ledger.md`, which is committed to
this directory **before** the CONSULT gate is recorded.

A fresh split seed does not restore blindness. Its honest value is narrower and
is stated as such: **this specific partition — and therefore these specific
sealed 20 rows — was never scored during scouting.** The words *independent
replication*, *blind*, *untouched*, *virgin data* are banned from every
deliverable (`study.yaml:claims_discipline`).

## Contract

| Field | Value |
|---|---|
| Domain | statistics-history |
| Data | `csv:data/prepared/iris_hard_pair.csv` (built by `prepare.py`; fixture committed under `fixtures/`) |
| Track | `primary` (one track) |
| Primary metric | `val_brier`, **lower** is better |
| `minimum_delta` | **TO BE MEASURED at Phase 0** — currently 0, the only honest pre-measurement value |
| Auxiliary metrics | `val_auc`, `val_logloss` (+ pr_auc, lift, f1) — recorded every run, never guardrails |
| Guardrails | `wall_seconds` max 30 |
| Method depth | full (5-part method card) |
| Per-run maximum | 60 seconds |

### Why `val_brier` and not AUC or logloss

- **AUC pegs.** A 20-row development partition at 10/10 gives AUC a 101-point
  lattice; the anchor scouted 1.000 on 14 of 20 lottery draws. A gauge that reads
  full scale cannot rank challengers.
- **Logloss is version-bound here.** kNN's scouted value was ~92 % clipping
  epsilon — a machine constant, not a property of the flowers.
- **Brier** is proper, bounded, and moves on 20 rows without pegging.

Both rejected metrics are still recorded on every run, so `aux_metrics.tsv`
carries the whole picture rather than the flattering slice. The metric is locked
at CONSULT and never switched mid-run: `study.yaml` is a hash-frozen gate
artifact.

## Data & split

100 rows × 7 columns: four 1936 measurements, `species` (sklearn's 3-class code,
kept from the first write for the registered crash rung), `is_virginica`
(target), `group_id`.

Split: `kind: group`, seed **20260828**, development 0.20, test 0.20.
Materialized sizes at this seed (measured 2026-08-24):

| Partition | Rows | virginica / versicolor |
|---|---|---|
| train | 60 | 33 / 27 |
| development | 20 | 10 / 10 |
| sealed test | 20 | 7 / 13 |

A group split is not stratified — the sealed partition's 7/13 base rate is a
documented consequence and is carried into how the sealed number is read.

**The twin rows.** Hard-pair rows 51 and 92 (iris rows 102/143, both virginica)
carry identical measurements (5.8, 2.7, 5.1, 1.9) and are the only duplicated
row-content in the hard pair. Identical values at 0.1 cm resolution do not prove
duplicated record entry, and no provenance evidence has been found either way. We
do not delete historical data. Both rows share one `group_id`, so they can never
straddle a partition — the leakage mechanism is removed regardless of which
explanation is true, the clean-room audit passes without deletion and without an
override, and n stays 100.

## Validation policy

Adaptive work uses train + development only. The track's single sealed access is
`klein run-one --final-test` at E0009.

**Pre-registered sealed scope (one track, one seal — declared here, not after the
loop):** the sealed look confirms the **incumbent's LEVEL** on 20 untouched rows.
The ladder gap is **exploratory by construction** — the losing families never get
a sealed value — and the verdict card says so.

## Noise floor — ONE study-level scalar

Committed as `sweeps/split_lottery.py` **before any ladder run**; parameters in
`study.yaml:noise_floor_protocol`.

1. `sweeps/kseed_floor.py` runs FIRST (the protocol-prescribed k-seed fit-noise
   sweep). LDA is closed-form, so its expected output is **std exactly 0** — a
   degenerate floor, committed as the documented deviation rather than skipped.
2. `sweeps/split_lottery.py`: k = 20 group-aware re-draws of the **80 non-sealed
   rows** into 60 train / 20 development. The sealed 20 are frozen out of every
   draw. Per draw: fit the anchor and each family, record every development Brier
   and every paired delta.
3. `minimum_delta = 2 × std(anchor development Brier across the 20 draws)`,
   rounded **up** to 3 decimal places.
4. Paste the measured `noise_floor:` block into `study.yaml`, set
   `minimum_delta`, and re-record CONSULT with
   `--note "minimum_delta set from the measured split-lottery floor"`.

The floor is an **actionability threshold** — "the incumbent's own score wobbles
this much when only the split changes", conditional on these 100 flowers. It is
not a confidence interval and not a significance test.

The ledger judges the **declared-split** delta (that is what klein's one scalar
does). Findings report the declared-split delta **and** the lottery spread,
labelled, so ledger and chart agree by construction.

## Experiment ladder (~9 transactions)

| # | Phase | Rung | What it tests |
|---|---|---|---|
| E0001 | adaptive-1 | LDA 1936, four features, fit on train only | split-identity anchor; sets the frontier |
| — | adaptive-1 | `sweeps/kseed_floor.py` | registered-degenerate fit-noise floor |
| — | adaptive-1 | `sweeps/split_lottery.py` | the study-level `minimum_delta` |
| E0002 | adaptive-2 | 3-class `species` handed to the binary evaluator | **registered crash** — an evidenced framework boundary |
| E0003 | adaptive-2 | logistic regression (1944/58) | RQ1 |
| E0004 | adaptive-2 | kNN, k=7, distance-weighted (1951/67) | RQ1 |
| E0005 | adaptive-2 | SVM-RBF (1995) | RQ1 |
| E0006 | adaptive-2 | HGBT sized for n=60 (2001/19) | RQ1 |
| E0007 | adaptive-2 | petal-only LDA | RQ2 |
| E0008 | adaptive-2 | sepal-only LDA | RQ3 positive control |
| E0009 | confirmation | sealed `--final-test` | the incumbent's level on 20 untouched rows |

E0002 is a **registered** crash, not an accident: `kleinlib.eval.evaluate` refuses
a target that is not exactly `{0, 1}`, so the multiclass column exits non-zero
with an `NA` metric. It converts "we dropped setosa" from a hand-wave into
evidence about where the framework's binary-only evaluator stops.

## Research questions & priors

Priors carry source tags; findings § ⑥ scores **only** priors tagged
`(source: uninformed)` — every scouting-informed prior is excluded from the
scorecard by construction.

- **RQ1** — do any of the four pre-registered challengers earn a `keep`?
  Prior: **no** *(source: scouting-2026-08-24 (measured))*.
- **RQ2** — is petal-only LDA within the floor of all-four LDA?
  Prior: **yes** *(source: scouting-2026-08-24 (measured))*. Reported as a
  protocol-scoped non-degradation **observation**, never "as good as".
- **RQ3** — does sepal-only LDA degrade by ≥ 2× the floor (positive control)?
  Prior: **yes** *(source: scouting-2026-08-24 (measured))*. **Pre-registered
  failure interpretation:** if it does not clear the floor, the instrument cannot
  resolve differences of this size at n=100, every within-floor claim is
  downgraded, and that becomes the honest headline.

## Estimand & claims discipline

Every headline claim is a **protocol-level decision claim**: *under this
pre-registered contract, challenger X did / did not improve `val_brier` by ≥ δ
over the 1936 anchor.* klein's one-sided keep/discard rule answers exactly that.

Population-level equivalence is **never** claimed. At 20 development rows it is
unanswerable — the design-phase paired bootstrap produced intervals wider than the
floor band for all six comparisons — so that impossibility is carried as a stated
limitation rather than quietly answered anyway. Banned and sanctioned vocabulary:
`study.yaml:claims_discipline`.

## Deliverables

`findings.md` · `report/index.html` · `scouting_ledger.md` · `claims.lock`
(claim_id → value → artifact path → sha256, emitted at finalize; every number in
any downstream deliverable must trace to it).
