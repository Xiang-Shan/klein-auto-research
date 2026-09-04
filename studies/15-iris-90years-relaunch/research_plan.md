# Research plan — 15-iris-90years-relaunch

## Question

Ninety years after Fisher published his linear discriminant on this exact problem,
does any modern post-1936 classification method actually beat Fisher's LDA at
separating iris *versicolor* from *virginica*, under a proper held-out evaluation?
And is the separating signal really in all four measurements, or do the two petal
measurements alone carry essentially all of it?

*Setosa is trivially separable and is out of scope. The 100 flowers of the hard pair
are the whole study.*

## Contract

- Domain: botany · `kind: predict` · `modality: tabular` · `profile: generic`
- Data: `sklearn:load_iris`, restricted to targets 1 and 2 → `data/prepared/iris_hardpair.csv`
- Tracks: `fisher` (registered / estimate) · `modern` (frontier / predict) · `ablation` (registered / test)
- Metric on every track: `val_auc` (ROC-AUC, higher is better), `bound.ideal: 1.0` on `modern`
- `minimum_delta`: **0.0 in the shipped contract — measured at Phase 0, never guessed**
- Method depth: full · Per-run maximum: 60 seconds

### Why three tracks

The headline question is a comparison. A track gets exactly one sealed access, so a
single-track study could confirm the incumbent's *level* but never the *gap* — and
deciding after the loop which of those a sealed number was is how sealed vocabulary
gets stretched. So each side of the comparison owns a track and produces its own
sealed number, and the gap is a difference of two of them. The ablation asks a
different question and gets the third.

### Why ROC-AUC

Decided before any byte was read:

1. It is threshold-free, so it measures *separation* — which is what a discriminant
   function does and what Fisher's question was about.
2. Resolution. On a 25-flower block, accuracy moves in steps of 1/25 = 0.04 — the
   frontier could only advance one whole flower at a time. ROC-AUC over 12 × 13 = 156
   ordered pairs resolves to 0.0064, about six times finer.
3. It is the canonical primary of `kleinlib.eval.evaluate`, which brings the
   collapsed-probability guard and the aux block with it.

Accuracy is not thrown away. `val_accuracy` and `val_errors` (misclassified flowers
at threshold 0.5) print in every block, land in `aux_metrics.tsv`, and carry the
human-legible number Fisher himself reported. The tutorial will lead with them.

### Why 50 / 25 / 25

Stratified, seed `20260904` (the study's start date, fixed before any byte was read).

- Development and test are the same size and the same construction, so they are
  *exchangeable*: the paired floor measured on development transfers to the sealed
  block, and "the sealed number landed within X floors of the development number"
  becomes a clean statement instead of an apples-to-oranges one.
- Train 50 is ample for a four-feature, two-class discriminant.
- "Half train, a quarter decides, a quarter is sealed" is teachable — which the
  tutorial needs and the DATA gate can check in one line.

Partitions come from `kleinlib.data.contract_split` and nowhere else. A literal seed
in an evaluator is a BLOCKER at Gate 1.

## Stable library versus mutable surface

`lib/iris.py` is stable library code, written once and complete before E0001:

- the loader and the three feature sets (`all4`, `petal`, `sepal`);
- the five model recipes (below), each a `(name) -> estimator` factory;
- the paired bootstrap of the ROC-AUC difference under common random numbers;
- the assembly of the `extra={...}` dictionary each cell prints.

`train.py` is the only mutable file. It composes those primitives into ONE cell per
experiment and branches on `KLEIN_TRACK` and `KLEIN_EVALUATION_KIND`, which
`run-one` sets. The per-experiment diff is therefore always "which model / which
feature set / which reference", never "a new method". No verifier is declared: this
is not `optimize` and nothing is checkpoint-scored, so `lib/iris.py` is stable code
rather than a hashed checker.

## The recipes (fixed here, so a later "tweak" is visible as a contract change)

| id | recipe | first published |
|---|---|---|
| `lda_all4` | `LinearDiscriminantAnalysis(solver="svd")`, raw features | Fisher 1936 — the incumbent |
| `logreg_l2` | `StandardScaler` → `LogisticRegression(penalty="l2", C=1.0, max_iter=1000)` | Berkson 1944 / Cox 1958 |
| `knn5` | `StandardScaler` → `KNeighborsClassifier(n_neighbors=5)` | Fix & Hodges 1951 / Cover & Hart 1967 |
| `svm_rbf` | `StandardScaler` → `SVC(kernel="rbf", C=1.0, gamma="scale", probability=True, random_state=20260904)` | Boser-Guyon-Vapnik 1992 / Cortes & Vapnik 1995 |
| `hgbt` | `HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, random_state=20260904)`, raw features | Friedman 2001 / Ke et al. 2017 |

`probability=True` on the SVM adds an internal Platt fit; ROC-AUC is rank-based, so
it touches the number only through ties, and the seed dependence it introduces is
exactly what the Phase-0 `fit_noise` sweep documents. LDA is scale-equivariant and
trees are scale-invariant, so neither is scaled — that is a property of the method,
not a hyperparameter choice.

## Validation policy

Adaptive work uses train + development only. Each track gets **one** sealed
final-test evaluation, spent through `klein run-one --final-test` and **rehearsed
first** with `klein run-one --final-test --dry-run`, which spends nothing and is
mandatory. Confirmation evidence never re-enters the adaptive frontier.
`confirmation.require: [sealed, replicate]` — a confirmed claim on any track needs
both its sealed access and a `klein replicate E####` record, which here costs
milliseconds.

## Experiment ladder

### Phase `anchor-and-floor` — before anything is compared, know the instrument

1. **E0001 (`fisher`) — the identity anchor and the incumbent's level, in one cell.**
   Asserts on the RAW loader that there are 100 rows, 50 per species and 4 measurement
   columns, and that the three partitions sum back to the prepared row count; then
   fits `lda_all4` on the 50 training flowers, scores the 25 development flowers, and
   prints a 2000-replicate bootstrap interval for the AUC. Adjudicates **P0 P1 P2 P3**.
   A P0 mismatch is a hard STOP — every later number would be measured on the wrong
   bytes. The counts are asserted on the raw load and not on the prepared table, so a
   lawful DATA-gate row drop cannot manufacture a false refutation.

2. **Four registered Phase-0 sweeps** (`sweeps/noise_floor.py`, each registered with
   `klein sweep register` so findings can cite `sweep:<name>`):

   | sweep | recipe | estimand | what it measures | lands under |
   |---|---|---|---|---|
   | `fit_noise` | seed-sweep, k=5 | `fit-noise` | how much `svm_rbf` and `hgbt` move on the same rows with only the seed changed | `metric.fit_noise` — **provenance, never a bar** |
   | `floor_modern` | paired-bootstrap, 1000 | `paired-comparison` | the spread of the AUC DIFFERENCE between `lda_all4` and `hgbt` on the same development rows | `tracks.modern.metric` |
   | `floor_ablation` | paired-bootstrap, 1000 | `paired-comparison` | the same for `lda_all4` versus `lda_sepal` | `tracks.ablation.metric` |
   | `floor_fisher` | split-lottery, k=5 | `marginal-resplit` | how much `lda_all4`'s own AUC moves when train/development is redrawn **inside the 75 non-sealed rows only** | `tracks.fisher.metric` |

   The sealed 25 flowers are never touched by any lottery. Each floor's *pair* and
   *replicate count* are already declared in `study.yaml`, before the measurement, so
   neither can be chosen after seeing which answer it produces.

3. **Paste and re-record.** `klein noise-floor --study . --recipe <r> --estimand <e>`
   prints each block; paste verbatim; then
   `klein gate record consult --reason "minimum_delta set from the measured noise floor"`.
   **No challenger may run before this re-record.** A seed-only spread is recorded as
   `fit_noise` and is never pasted as the bar.

4. **Audit the headroom.** `klein preflight` discloses
   `h = (1.0 - incumbent) / minimum_delta` on `modern`. Read `h >= 1` as "not
   excluded", never as "plausible".

### Phase `parade` — the ninety-year rematch

5. **E0002 (`modern`) — Fisher's LDA again, this time seeding the frontier's
   incumbent** and printing `gap_in_floors`. Adjudicates **P4**. Its number must equal
   E0001's to floating point; if it does not, the two tracks are not looking at the
   same rows and the study stops.
   - **P4 supported (the door is shut):** `klein headroom ack` with the reason
     recorded — *the parade IS this study's registered question, and four
     dispositioned discards are the evidence the brief asked for* — then run it anyway.
   - **P4 refuted (the door is ajar):** run the frontier normally and report `h`
     alongside every candidate.

6. **E0003 – E0006** — `logreg_l2`, `knn5`, `svm_rbf`, `hgbt`. Each refits
   `lda_all4` on the SAME development rows inside the SAME run and prints
   `delta_vs_reference` and `delta_in_floors`, so every comparison is paired by
   construction. Adjudicates **P5 P6 P7 P8**.

7. **P9** is adjudicated by counting keeps in `results.tsv` with
   `klein predict adjudicate`, whose evidence hash goes on the record.

### Phase `ablation-map` — which measurements carry it

8. **E0007** petal-only LDA versus all-four LDA, paired, same development rows → **P12**.
9. **E0008** sepal-only LDA versus all-four LDA, paired, same rows → **P13**.
10. **E0009** the petal comparison repeated with the parade's best modern family → **P14**.

Three cells rather than one three-row table, deliberately: each comparison then gets
its own manifest, its own candidate commit and its own dated `Decision:` line.

### Phase `confirmation` — three sealed numbers, one per track

11. `klein run-one --final-test --dry-run` for each track first. Then:
    - **`fisher` sealed** — the incumbent's sealed level with its bootstrap interval.
    - **`modern` sealed** — the selected challenger *and* `lda_all4` on the same 25
      sealed flowers under common random numbers → **P10 P11**. (Restore the selected
      candidate's configuration into `train.py` before the run: a non-keep restored the
      surface, and the candidate commit stays resolvable.)
    - **`ablation` sealed** — all three feature sets on the 25 sealed flowers, printing
      both `delta_in_floors` and `sepal_delta_in_floors` → **P15**.
12. `klein replicate E####` for the run behind each confirmed claim.

## What the gates must settle (do not decide these here)

**DATA (Gate 1), `TO-VERIFY`:**

- exact per-class counts in each partition after the stratified split;
- the four-row clean-room leakage audit via `python -m kleinlib.leakage`;
- the value-pattern check on every column — never `dtype == "object"`;
- **duplicate and near-duplicate rows**, and the group policy that follows if any
  exist. Nothing in this contract presumes an answer, and P0 is written on the raw
  load precisely so that a lawful row drop cannot break it;
- the prepared file's sha256, `sklearn.__version__`, and whether this copy of the
  table differs from Fisher's 1936 printed table in any versicolor/virginica cell
  (the UCI copy is documented as differing from the original in a small number of
  places — the card must say whether that touches the hard pair);
- the frozen `split_fingerprint`, which the notary then checks on every run.

**METHOD (Gate 2):**

- teach LDA from scratch for a numerate non-specialist: the between/within scatter
  ratio, the pooled-covariance solution, why it is optimal under equal covariances,
  and a from-scratch implementation checked against sklearn's;
- brief treatment of each challenger and *when it pays / when it does not*;
- `references.yaml` with Fisher 1936 verified, plus one primary reference per family;
- **transcribe Fisher's own reported misclassification count for the hard pair from
  the primary source, with its citation.** It is reported in findings *descriptively*
  and is deliberately **not** a scored prediction — a target nobody has verified yet
  could only manufacture a fake refutation. P2's bar of 3 errors is my own estimate,
  not a transcription.

## Figures (generic profile, `task_type: classification`)

ROC curve per family; precision-recall; reliability; score histogram by species;
confusion at the best threshold; the decision trajectory per track; and one figure
this study needs specifically — **the measured floor drawn against the incumbent's
whole distance to a perfect AUC**, which is what `h < 1` looks like.

## Out of scope, deliberately

Comparing this study against any earlier iris study in this repository. That
comparison is the *reader's* exercise and belongs outside this contract; performing
it inside the study would contaminate the very independence that makes it worth
doing. Nothing in this study reads `studies/07-iris-90years/`,
`studies/08-iris-rematch/` or `studies/09-iris-first-lesson/`, and the disclosure of
what leaked in anyway is in `scouting_ledger.md`.
