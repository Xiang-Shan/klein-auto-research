---
type: findings
domain: "botany"
profile: "generic"
kind: "predict"
status: complete
concepts: [metric-pegging, zero-noise-floor, tie-reads-as-keep, floor-versus-effect-size, duplicate-row-leakage, registered-predictions]
related: [15-iris-90years-relaunch]
---

# Findings — 15-iris-90years-relaunch

> SYNTHESIZE stage output. Every claim cites evidence ids from the immutable run
> manifests, the registered sweeps and the replication records. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`; the lock and the numbers
> law: `references/claims-protocol.md`.
>
> **The one-paragraph result.** Twelve notarized runs across three tracks asked whether
> ninety years of classification research separates iris *versicolor* from *virginica*
> better than Fisher's own 1936 linear discriminant. None of the four post-1936
> challengers cleared the incumbent by any resolvable amount: on the development block
> three of them tied it exactly at ROC-AUC `1.000000` and the fourth lost, and in the
> one sealed access the selected challenger lost `-0.012821` val_auc. But the study's
> most useful output is a failure of its own instrument. The primary metric **pegged at
> its ideal** — Fisher's LDA scores a perfect ROC-AUC on the development block and again
> on the sealed block — so every Phase-0 floor recipe on two of the three tracks
> measured a spread of exactly zero, `minimum_delta` came out at `0`, seven of the
> sixteen registered predictions became structurally unadjudicable, the headroom law
> was disarmed, and the disposition rule `primary_metric >= incumbent + 0` read four
> ties as four frontier `keep`s. The third track, whose floor was real (`0.28125`),
> answered its question cleanly on both partitions: the two petal measurements carry
> essentially all the separating signal and the two sepal measurements carry a real,
> large, but floor-uncleared amount less.

## ① Research-question verdicts

One row per verdict; `Verdict` describes the fate of the RQ's registered prior in
`study.yaml`, not a re-decision of any registered prediction (those are §② and are
copied from the ledger).

| Claim | RQ | Track | Verdict | Strength | Class | Evidence | Delta + uncertainty |
|---|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | modern | supported in substance | exploratory | empirical-description | E0002, E0003, E0004, E0005, E0006, `sweep:floor_modern` | On the 25 development flowers, no post-1936 challenger exceeded Fisher's LDA refit in the same cell. `logreg_l2` (E0003), `svm_rbf` (E0005) and `hgbt` (E0006) each printed val_auc `1.000000` against the same printed reference `1.000000` — `delta_vs_reference` `0.0`, `0.0` and `-0.0`; `knn5` (E0004) printed `0.990385`, `delta_vs_reference` `-0.009615`. Development-only, therefore exploratory; and no delta here is certifiable against a bar, because the track's measured floor is `0`. |
| **[C2]** | RQ1 | modern | refuted on the letter of "zero keeps" | confirmed | procedural-verdict | E0002, E0003, E0004, E0005, E0006, E0011, `art:results` | The parade's five development cells on the `modern` track filed 4 keeps and 1 discard (the track's sixth row, E0011, is the sealed run, which the notary records as a discard by the sealed-evidence convention, not because it lost a comparison), so the prior's literal wording ("zero of the four families earns a keep") is false by direct count — and zero of the four challengers beat the incumbent by any amount the contract can resolve. `choose_disposition`'s frontier rule at `minimum_delta` `0` is `primary_metric >= incumbent + 0` evaluated on the printed six-decimal block, so a tie satisfies it. Read the parade as **4 printed keeps, 0 resolvable wins**. |
| **[C3]** | RQ3 | fisher, modern | refuted — right conclusion, wrong mechanism | confirmed | empirical-description | E0001, E0010, `sweep:floor_fisher`, `sweep:floor_modern`, `sweep:fit_noise_svm_rbf`, `sweep:fit_noise_hgbt`, `rep:E0001@20260904T174249Z` | The prior expected a paired floor of `0.02`–`0.10` val_auc against an incumbent distance-to-perfection under `0.05`. Measured: Fisher's LDA scores val_auc `1.000000` on the development block (E0001) **and** `1.000000` on the sealed block (E0010), so the distance to the declared ideal `1.0` is `0`; the paired-bootstrap floor over 1000 replicates on `(lda_all4, hgbt)` has std `0` and range `0`; the marginal split-lottery floor over 5 redraws has std `0` and range `0`. `minimum_delta` is `0` on both tracks and `kleinlib.decision.track_headroom` returns no number at all. "Which classifier wins" is unanswerable on this data with this metric — as the prior concluded, but because the metric saturated, not because the ruler was coarse. |
| **[C4]** | RQ2 (petal half) | ablation | supported | confirmed | empirical-description | E0007, E0009, E0012, `sweep:floor_ablation`, `rep:E0007@20260904T174632Z` | Petal length and petal width alone carry essentially all the separation. Development: `lda_petal` `1.000000` against `lda_all4` `1.000000` in the same cell, `delta_vs_reference` `0.0`, `delta_in_floors` `0.0` (E0007); the same comparison with `hgbt` instead of LDA gives `delta_in_floors` `0.0` (E0009), so it is a property of the flowers, not of the model family. Sealed: `0.987179` against `1.0`, `delta_vs_reference` `-0.012821`, `delta_in_floors` `-0.0456` — inside the measured floor `0.28125` by more than an order of magnitude. |
| **[C5]** | RQ2 (sepal half) | ablation | supported in substance, refuted on the registered rule | confirmed | empirical-description | E0008, E0012, `sweep:floor_ablation`, `rep:E0008@20260904T174817Z` | Sepal length and sepal width alone carry a real, large, correctly-directed amount less — and still fail the pre-registered "at least one measured floor below" bar, twice. Development: `lda_sepal` `0.814103` against `lda_all4` `1.000000`, `delta_vs_reference` `-0.185897`, `delta_in_floors` `-0.661` (E0008). Sealed: `sepal_delta_in_floors` `-0.8547` (E0012). The track's floor was measured at `0.28125` from the paired-bootstrap spread of this very contrast (mean `-0.190092`, std `0.0952175`, range `0.5625`), which is why a genuinely large effect lands under one floor. "Refuted" here means the bar was not cleared, never that no difference was found. |
| **[C6]** | RQ1 (sealed) | modern | measured | confirmed | empirical-description | E0010, E0011 | The `modern` track's one sealed access: the selected challenger `hgbt`, refit on the 74 train+development rows, scores val_auc `0.987179` on the 25 sealed flowers against Fisher's LDA refit on the same rows in the same run at `1.0` — `delta_vs_reference` `-0.012821`, exactly `2 / 156` of the block's ordered pairs. It misclassifies 3 of 25 sealed flowers (accuracy `0.88`) where the same LDA on the same sealed rows misclassifies 2 of 25 (accuracy `0.92`, E0010). This is the only non-tied, correctly-signed challenger-versus-Fisher comparison the study produced, and the contract cannot certify it: P11's rule needs `delta_in_floors`, which a zero floor never prints. |
| **[C7]** | RQ4 | fisher, ablation | supported in substance, refuted on the metric it named | confirmed | empirical-description | E0001, E0010, E0008, E0012 | The two 25-flower blocks agree on ranking and disagree on counts. Fisher's LDA: development val_auc `1.000000` with 1 of 25 misclassified (accuracy `0.96`); sealed val_auc `1.000000` with 2 of 25 misclassified (accuracy `0.92`). The sealed-minus-development distance in the metric the prior named is exactly `0` val_auc, not the predicted one-to-two floors — but the threshold-`0.5` error count doubled, and the sepal-only shortfall widened from `-0.661` to `-0.8547` floors between the two blocks. No single block should be read as this species pair's true separability. |

**Strength note.** `confirmation.require` for every track is `[sealed, replicate]`.
All three sealed accesses were spent (E0010 `fisher`, E0011 `modern`, E0012
`ablation`) and the development run each sealed cell rests on was replicated exactly
(`rep:E0001@20260904T174249Z`, `rep:E0006@20260904T174449Z`,
`rep:E0007@20260904T174632Z`, `rep:E0008@20260904T174817Z`, every one
`difference` `0.0`). A sealed run cannot itself be replicated — `klein replicate`
refuses a `final_test` run with no override, because that would be a second look at
the sealed partition — so the replicate leg is filed against the development run, as
the CLI's own guidance directs. **[C1]** stays exploratory because the four
development-side parade comparisons have no sealed counterpart except `hgbt`'s;
**[C6]** carries that one sealed comparison and is confirmed.

**How the sealed error counts in [C6] and [C7] are compared.** E0011's in-run LDA
reference printed only its val_auc (`1.0`), not its error count, so the error
comparison is read across the two sealed cells: E0010 and E0011 fit the same
`lda_all4` recipe on the same 74 train+development rows and score the same 25 sealed
rows, and LDA with `solver="svd"` is deterministic, so E0010's `val_errors` is the
reference's error count. Like for like, the sealed challenger makes one more error
than Fisher's discriminant (3 of 25 against 2 of 25). `program.md`'s own E0011 entry
says "2 extra errors"; that compares the sealed challenger's 3 against the
*development* LDA's 1 (E0001/E0002), across two different partitions. This document
carries the like-for-like number, and the discrepancy is recorded in `program.md`'s
dated SYNTHESIZE decision line rather than quietly corrected.

**Two evidence records deliberately not cited above, and why.** `E0001`'s first
replication attempt (`rep:E0001@20260904T174103Z`) is on file as **not** reproduced:
the child process timed out at the default budget with no output at all, a cold
first-invocation cost in a freshly created detached worktree (the successful retry's
own `wall_seconds` was `0.787251` at run time). It is a record of a harness timeout,
not of a failed reproduction, and it is superseded by
`rep:E0001@20260904T174249Z`. The three `sealed_dryrun` rehearsals under `sweeps/`
spent no sealed data by construction and adjudicate nothing.

## ② Registered predictions (from the ledger)

Copied verbatim from `klein predict list --study studies/15-iris-90years-relaunch`;
nothing here is re-decided or re-worded. **Ledger summary: 5 supported, 4 refuted,
7 inconclusive, 0 open.** All sixteen were registered in `study.yaml` before any run
existed and hashed into the consult gate record.

The seven inconclusive rows are not an accounting gap — they are the study's central
finding wearing its procedural clothes. Each one's own `inconclusive_if` clause,
written at CONSULT, names the exact condition that came to pass: "the contract still
carries `minimum_delta` `0`, so `train.py` prints no `gap_in_floors` line". The clause
was written expecting an *unmeasured* zero; what happened is that the floor was
measured, honestly, and came back zero.

| P# | Statement (abridged) | Rule | Observed | Verdict (ledger) | Evidence | Decision |
|---|---|---|---|---|---|---|
| P0 | identity anchor: the raw loader hands back the flowers the study claims to study | `all_of[raw_rows == 100, raw_versicolor == 50, raw_virginica == 50, raw_features == 4, partition_sum_matches == 1]` | all five exact, `\|Δ\|` `0` on each | **supported** | E0001 | — |
| P1 | Fisher's LDA reaches development ROC-AUC at least `0.90` | `{key: primary_metric, op: ">=", value: 0.90}` | `primary_metric` `1` | **supported** | E0001 | — |
| P2 | counted the way Fisher counted, it misses at most 3 of 25 development flowers | `{key: val_errors, op: "<=", value: 3}` | `val_errors` `1` | **supported** | E0001 | — |
| P3 | 25 flowers cannot pin the separation: the 95% bootstrap interval is wider than `0.05` val_auc | `{key: ci_width, op: ">", value: 0.05}` | `ci_width` `0` | **refuted** | E0001 | `program.md` 2026-09-04, "Decision: P3 refuted" |
| P4 | the headroom door is shut before the parade starts, `h` below one floor | `{key: gap_in_floors, op: "<", value: 1}` | `gap_in_floors` was not printed by this run | **inconclusive** (a missing number is not a refutation) | E0002 | — |
| P5 | L2 logistic regression does not beat Fisher's LDA by one measured floor | `{key: delta_in_floors, op: "<", value: 1}` | `delta_in_floors` was not printed by this run | **inconclusive** | E0003 | — |
| P6 | 5-nearest-neighbours does not beat Fisher's LDA by one measured floor | `{key: delta_in_floors, op: "<", value: 1}` | `delta_in_floors` was not printed by this run | **inconclusive** | E0004 | — |
| P7 | an RBF-kernel SVM does not beat Fisher's LDA by one measured floor | `{key: delta_in_floors, op: "<", value: 1}` | `delta_in_floors` was not printed by this run | **inconclusive** | E0005 | — |
| P8 | a histogram gradient-boosted tree lands at least one measured floor **below** Fisher's LDA | `{key: delta_in_floors, op: "<=", value: -1}` | `delta_in_floors` was not printed by this run | **inconclusive** | E0006 | — |
| P9 | ninety years produced no keep: zero `modern` rows carry status `keep` | manual count on `results.tsv` | count `4`, not `0` (E0002 `lda_all4`, E0003 `logreg_l2`, E0005 `svm_rbf`, E0006 `hgbt`); only E0004 `knn5` discarded | **refuted** | E0002, E0003, E0004, E0005, E0006, `art:results` | `program.md` 2026-09-04, "Decision: **P9 REFUTED**" |
| P10 | the sealed score lands within two measured floors of the development score | `{key: sealed_shift_in_floors, op: "abs_le", value: 2}` | `sealed_shift_in_floors` was not printed by this run | **inconclusive** | E0011 | — |
| P11 | **the sealed gap**: challenger and Fisher's LDA within one measured floor on the same sealed rows | `{key: delta_in_floors, op: "abs_lt", value: 1}` | `delta_in_floors` was not printed by this run | **inconclusive** | E0011 | — |
| P12 | petal-only lands within one measured floor of all-four | `{key: delta_in_floors, op: "abs_lt", value: 1}` | `delta_in_floors` `0` | **supported** | E0007 | — |
| P13 | sepal-only lands at least one measured floor **below** all-four | `{key: delta_in_floors, op: "<=", value: -1}` | `delta_in_floors` `-0.661` | **refuted** | E0008 | `program.md` 2026-09-04, "Decision: **P13 refuted, and the surprise is instructive rather than a reversal of RQ2's direction**" |
| P14 | the petal verdict is a property of the flowers, not of LDA | `{key: delta_in_floors, op: "abs_lt", value: 1}` | `delta_in_floors` `0` | **supported** | E0009 | — |
| P15 | both halves of the ablation survive the sealed partition | `all_of[{delta_in_floors, abs_lt, 1}, {sepal_delta_in_floors, "<=", -1}]` | `delta_in_floors` `-0.0456` (first clause supported); `sepal_delta_in_floors` `-0.8547` (second clause refuted) | **refuted** | E0012 | `program.md` 2026-09-04, "Decision: **P15 refuted, and it is E0008's own H6 wrinkle reproducing on data nobody had looked at before this run**" |

Every refuted prediction carries its dated `Decision:` line in `program.md`, as the
loop contract requires; `klein verify` reports 0 refutations without a recorded
decision.

## ③ Surprises and why

Three things defied the registered priors. Each mechanism below is a
`mechanism-interpretation` claim and is therefore exploratory however convincing it
reads — an interpretation is confirmed only by a later study that tests it.

**[C8]** *The metric pegged at its own ideal, and every measuring instrument inherited
the saturation.* *(exploratory, mechanism-interpretation; evidence: E0001, E0010,
`sweep:floor_fisher`, `sweep:floor_modern`, `sweep:fit_noise_svm_rbf`,
`sweep:fit_noise_hgbt`)* Nothing in the contract anticipated this. The study chose
ROC-AUC over accuracy precisely for resolution — on a 25-flower block accuracy moves
in steps of `0.04`, one whole flower, while ROC-AUC over 156 ordered pairs resolves to
`0.0064` — and that reasoning is sound and still is. What it missed is that a finer
ruler is worthless against a quantity that has already reached its bound. On this
partition the 25 development flowers are **perfectly rank-separated**: hand-inspection
of the probability dump at E0001 found all 13 development versicolor scoring below
`0.02` and all 12 virginica above `0.45`, with the lone threshold-`0.5` miss (one
virginica at `0.4507`) still ranking above every versicolor. Once a sample is cleanly
rank-separated, *every* resample of it with replacement is also cleanly rank-separated
— that is arithmetic, not a coding artifact — so the percentile bootstrap returns
`ci_width` `0` (refuting P3), the paired bootstrap returns a delta of exactly `0` on
all 1000 replicates, the seed sweeps return `0` spread, and the split lottery returns
`0` spread over 5 redraws. The measured `minimum_delta` is therefore `0`; every
floor-normalized key stops printing (`lib.iris.frontier_extra`'s zero-guard);
`track_headroom` returns no number; and seven predictions become unadjudicable. The
mechanism is that a bounded metric plus a separable small sample gives a
**degenerate** measurement problem, and no amount of resampling rigor recovers from
it: the resampling instrument can only report variation that the sample contains.
Because the sealed block reproduces the peg (E0010, val_auc `1.000000` again on 25
flowers nobody had looked at), this is a property of the species pair under these four
measurements at this sample size, not one lucky draw.

**[C9]** *The disposition arithmetic turned ties into keeps.*
*(exploratory, mechanism-interpretation; evidence: E0002, E0003, E0005, E0006,
`art:results`)* The frontier rule is `primary_metric >= incumbent + minimum_delta`,
evaluated on the printed, six-decimal-rounded block. With `minimum_delta` measured at
`0`, the `+ minimum_delta` term vanishes and the comparison degenerates to
`printed >= printed` — which a *tie* satisfies. `logreg_l2` (E0003), `svm_rbf` (E0005)
and `hgbt` (E0006) each tied Fisher's own LDA refit in the same cell and each was
filed as a frontier improvement — the fourth keep, E0002, is the run that seeded the
track with Fisher's LDA itself and fires on the "first valid result on this track"
branch, not on any comparison; `hgbt`'s raw val_auc is `0.9999999999999999`, a
floating-point hair *below* the reference, and it still read as a keep because the
printed block rounds it to `1.000000` and `delta_vs_reference` prints `-0.0`. The
surprise is not that the engine is wrong — the rule is exactly what the contract
declared — but that a *measured* floor of zero silently converts a strict frontier
into a non-strict one. A ledger reader who counts `keep` rows without reading
`delta_vs_reference` would conclude that three of four post-1936 methods improved on
Fisher. None did. This is why P9, whose rule is a literal count, is recorded as
refuted while RQ1's substance is supported: the count and the science point opposite
ways, and both belong on the record.

**[C10]** *A large, real, correctly-directed effect failed a registered rule — twice —
because the floor was measured from the effect's own spread.* *(exploratory,
mechanism-interpretation; evidence: E0008, E0012, `sweep:floor_ablation`)* The
`ablation` track is the one track whose floor is not degenerate, and it produced the
opposite pathology. `floor_ablation` measured the paired-bootstrap spread of exactly
the contrast the track was built to test — `(lda_all4, lda_sepal)` — obtaining mean
`-0.190092`, std `0.0952175`, range `0.5625`. Klein's schema-3 bar is
`max(2 × std, range / 2)`, and at 1000 replicates the `range / 2` term binds: the
resulting `minimum_delta` `0.28125` is nearly a third of the whole `0`-to-`1` val_auc
scale, and it is *larger than the effect it was set to detect*. So sepal-only's
genuine `-0.185897` val_auc shortfall on development reads as `-0.661` floors and P13
is refuted; on the sealed block the shortfall is larger still (`-0.8547` floors, about
`-0.24` val_auc <!-- klein:numbers-ok: derived = sepal_delta_in_floors (-0.8547, aux_metrics.tsv) x the ablation floor (0.28125, study.yaml); no run printed the sealed sepal AUC as its own key -->) and P15 is refuted on the same clause. The mechanism is that when the range statistic of a heavy-tailed paired-bootstrap distribution sets the bar, the bar tracks the *tail* of the effect rather than the noise around it, and a one-floor rule then demands roughly one and a half times the effect's own mean magnitude. The lesson generalizes past this dataset: a floor measured on the contrast under test is conservative in a way that a one-floor threshold may make unreachable, and the study anticipated it — the playbook's H6 was written before E0012 ran and predicted exactly this outcome on the sealed rows.

**A fourth surprise, from `aux_metrics.tsv` rather than from a prediction: the
calibration reversal.** On development, `hgbt` was not merely tied on ranking, it was
the **best-calibrated** model in the parade by a wide margin — Brier `0.000945` and
log-loss `0.012827`, against Fisher's LDA at Brier `0.017482` and log-loss `0.061537`.
On the sealed rows the same recipe collapses to Brier `0.118994` and log-loss
`0.750798`, two orders of magnitude worse than its own development calibration and
worse than any development cell in the study, while its ranking only slipped by
`-0.012821` val_auc. The sealed LDA-family cell that scored the same rows (E0012, the
petal comparison) sits at Brier `0.057828` and log-loss `0.164260`. Read that as the
textbook signature of a high-capacity learner memorizing 74 rows: the boosted tree's
*confidence* was fitted to the training partition even where its *ordering* generalized.
A study whose primary metric had been log-loss instead of ROC-AUC would have had a
non-degenerate floor and a very different parade — see §⑦.

## ④ Practical advice

Concrete, in the best-practices voice, and each item is a claim about the process
rather than about irises.

**[C11]** *Before registering a bounded metric as a study's primary, check whether it
can peg.* *(exploratory, research-discipline; evidence: E0001, E0010,
`sweep:floor_modern`, `sweep:floor_fisher`)* On a small, highly separable
classification problem, ROC-AUC can reach its bound `1.0` on the very first anchor run,
and once it does, the whole apparatus downstream of it — noise floor, headroom,
frontier arithmetic, floor-normalized prediction rules — degenerates at once. The
cheapest possible guard is one un-notarized smoke fit on the *training* rows scored on
the *training* rows before the contract is frozen: if the metric is already at or near
its ideal there, it will peg on a held-out block of 25 too. This study registered
`bound.ideal` `1.0` on the `modern` track, which is the right instinct, but a bound
only arms the headroom audit — it does not warn you at CONSULT that the incumbent will
start at the bound.

**[C12]** *A `minimum_delta` of exactly `0` is a contract state that needs its own
handling, not a silent pass-through.* *(exploratory, research-discipline; evidence:
E0002, E0003, E0005, E0006, `art:results`)* A measured floor of `0` is a legitimate
measurement — it means "no instrument tried at Phase 0 saw any spread" — but it turns
`primary_metric >= incumbent + minimum_delta` into a rule a tie passes, and it silences
every floor-normalized key. If your floor measures at zero, do at least one of: (a)
require a strict inequality on the frontier when `minimum_delta <= 0`; (b) declare the
metric's own printing resolution as the floor (the study's `exactness` field exists for
this) — here one ordered pair out of 156, `0.0064`; or (c) go back to Phase 0 and
measure a floor on a metric that is not saturated. Doing none of the three is how a
ledger ends up reporting four keeps and zero wins.

**[C13]** *Write registered rules on keys that always print, and keep a raw-effect-size
twin for every floor-normalized rule.* *(exploratory, research-discipline; evidence:
E0004, E0006, E0011)* Seven of this study's sixteen predictions read inconclusive for
one reason: their rules name `delta_in_floors` / `gap_in_floors` / `sealed_shift_in_floors`,
keys that a zero floor never prints. Meanwhile the raw keys printed on every single
run and told the story cleanly — `knn5` at `-0.009615`, the sealed `hgbt` at
`-0.012821`. A prediction pair costs nothing to register: one rule in floors (the
resolvable claim) and one on the raw delta (the fallback that survives a degenerate
floor). Had P5–P8 carried a `delta_vs_reference` twin, this study would report four
adjudicated challenger verdicts instead of four inconclusive ones on the same evidence.

**[C14]** *Report the registered verdict and the raw effect size side by side, always.*
*(exploratory, research-discipline; evidence: E0008, E0012, E0011)* Three of this
study's four refutations, and every one of its inconclusives, would mislead a reader
who saw only the verdict word. "P13 refuted" alongside a `-0.185897` val_auc gap;
"P15 refuted" alongside a larger sealed gap in the same direction; "P11 inconclusive"
alongside the study's single clearest challenger loss. The verdict answers "did the
pre-registered bar clear?"; only the raw number answers "how big is it?". A findings
document that prints one without the other is not shorter, it is wrong.

**[C15]** *Run the duplicate-row straddle audit before you trust any small-table split.*
*(exploratory, research-discipline; evidence: `art:data_card`)* This study's DATA gate
mechanically found one exact-duplicate row pair in the 100-row hard pair — two
*virginica* flowers identical on all four measurements at `(5.8, 2.7, 5.1, 1.9)` —
whose two copies land on **opposite sides of the train/development boundary** under
the declared stratified split. On a table this small, a memorization-capable
challenger (`knn5` most directly) scores the development copy for free from a
byte-identical training copy, in exactly the paired comparisons the parade's
predictions are decided on. The fix cost one row and no contract change: drop the
second copy in `prepare.py` before the table is written, then re-profile, re-split and
re-audit. The check must be unconditional — this one was found by a mechanized audit
that runs on every table, not by anyone suspecting this table.

## ⑤ Implications — what changes if this holds

**What a reader should do differently.** If the confirmed claims here hold, the
practical consequence is about *instrument design*, not about irises. **[C3]** and
**[C8]** say that a 100-row, four-feature, two-class problem with a near-linear
boundary can put a bounded ranking metric at its ceiling on every partition you look
at, and that this failure is invisible until Phase 0 measures the floor. The response
is to check for saturation before the contract is hashed, and to pick a metric with
headroom when it is found — not to declare the comparison answered. **[C4]** and
**[C5]** say that a feature ablation on the *same* data remains perfectly answerable
even while the model comparison is not: a study whose headline question dies on the
instrument can still return a clean secondary answer, and it is worth designing a
track that survives such a death.

**What should NOT be concluded from the exploratory claims.** **[C1]** is a
development-partition measurement of four challengers against one incumbent on 25
flowers. It does not license "LDA is as good as modern machine learning", nor
"boosting fails on small data". It licenses exactly this: on these 25 development
flowers, under this metric, none of these four named recipes produced a difference
this study can resolve — and the study is explicit that its resolving power was zero.
**[C8]**, **[C9]** and **[C10]** are mechanism interpretations: they explain what was
observed, and a later study would have to test them. **[C6]**, the one sealed gap,
is a single number from a single access on a single 25-row block; it is signed and
correctly directed, and it has no uncertainty estimate at all, because the only
uncertainty machinery the contract had measured zero. Do not read `-0.012821` val_auc
as a measurement of how much worse boosting is than LDA on this species pair. Read it
as: the one time these two were compared on flowers neither had seen, the 1936 method
was ahead by two of 156 ordered pairs and one misclassified flower.

**Nothing here is priced.** The study registered no `materiality:` block, deliberately
— the brief asked nothing about consequence or value. Every statement above is a
statement about whether a registered bar was cleared, and nothing more.

## ⑥ Literature tie-back

**The prior scorecard, and what is excluded from it.** `scouting_ledger.md` §S1–S3
disclose that the CONSULT protocol's own required reading names three earlier iris
studies in this repository together with their headroom values and keep counts. That
exposure is not independent of this study's headline question, so the ledger's own
rule tags RQ1's and RQ3's priors `(source: scouted)` and **excludes them from the
scorecard below**. This section therefore scores only the `(source: uninformed)`
priors: RQ2, RQ4, and the method card's own M2–M6. (M1 was resolved at the METHOD gate
before any evidence was spent and is reported for completeness.)

| Prior | Source | Stated | Observed | Score |
|---|---|---|---|---|
| RQ2 | uninformed | petal-only within one floor of all-four; sepal-only several floors below, "around `0.75` to `0.85`" against all-four "near `0.96`" | petal-only within one floor on both partitions (**[C4]**); sepal-only development val_auc `0.814103` — inside the stated `0.75`–`0.85` band — but all-four came in at `1.000000`, not near `0.96`, and the shortfall reads `-0.661` floors, not "several" | **half held**: the direction and the sepal level were called correctly; the all-four level and the floor multiple were not |
| RQ4 | uninformed | the incumbent's sealed-minus-development distance is between one and two measured floors — visible, but not enough to overturn the ranking | the distance is exactly `0` val_auc (both blocks `1.000000`); the ranking indeed did not overturn; the shift showed up instead in the threshold-`0.5` error count, 1 of 25 → 2 of 25 (**[C7]**) | **refuted on the metric it named, held on its substance** |
| M1 | method card | a from-scratch numpy LDA reproduces `LinearDiscriminantAnalysis(solver="svd")` to within `1e-12` on every coefficient | max absolute coefficient difference `7.105e-15`, cosine similarity `1.000000000000000` | **held**, by three orders of magnitude (resolved at the gate, no evidence spent) |
| M2 | method card | best-minus-worst spread of development ROC-AUC across the five recipes at most `0.12` val_auc | the five recipes run from `0.990385` to `1.000000`, a spread of `1.000000 - 0.990385` | **held**, by more than an order of magnitude — and for a reason the card did not state: the parade was tight because four of five recipes were *identical* at the printed precision |
| M3 | method card | `knn5` prints `proba_unique_values` at most 6 and lands strictly below `lda_all4` | `proba_unique_values` `6` exactly; val_auc `0.990385` against `1.000000` | **held on both clauses**, and the mechanism checks out: the `-0.009615` gap is `1.5 / 156` ordered pairs, i.e. three tied pairs each scoring half |
| M4 | method card | `hgbt` lands at least `0.01` val_auc **below** `lda_all4` on the same development rows | development `delta_vs_reference` `-0.0` (raw val_auc `0.9999999999999999` against `1.0`) | **refuted on development** — and then vindicated where it was not stated: on the sealed rows `hgbt` lands `-0.012821` below the same LDA (**[C6]**), clearing the card's own `-0.010` bar. The capacity cost the card predicted is real; it needed a partition the model had not been fit near to show up |
| M5 | method card | `lda_petal` within `0.02` val_auc of `lda_all4`; `lda_sepal` at least `0.10` below | development: `0.0` and `-0.185897`; sealed: `-0.012821` and about `-0.24` <!-- klein:numbers-ok: same derived sealed sepal gap as C10; sepal_delta_in_floors x the ablation floor, both pinned --> | **held on all four clauses, on both partitions** — the card's AUC-unit framing survived exactly where the floor-normalized registered rules P13/P15 failed |
| M6 | method card | the Phase-0 paired floor lands between `0.03` and `0.20` val_auc **and** exceeds `lda_all4`'s remaining distance to a perfect AUC | measured floor `0`; remaining distance `0` | **refuted on both clauses**, and it is the study's most instructive refutation: the card explicitly called M6 a real bet ("a prior that cannot lose is not a prior"), betting that a paired comparison might cancel enough correlation to make 25 flowers a usable ruler. It cancelled *all* of it |

**Uninformed priors versus the method card's.** The card's own AUC-unit priors (M2,
M3, M5) outperformed the research questions' uninformed ones (RQ2, RQ4) on this study,
and the reason is visible: M2/M3/M5 were stated in units that do not depend on a
quantity the study had not yet measured, exactly as the card said they were
("stated in AUC units rather than in floors, so that they remain checkable whatever
the Phase-0 floor turns out to be"). M4 and M6, the two the card itself flagged as
most at risk, are the two that were refuted. A card that names its own weakest priors
in advance and then loses precisely those is a card doing its job.

**Against the papers.** The parade's outcome sits squarely where the method card's
lit-scan placed it. `ref:grinsztajn2022` is the standard citation for trees still
outperforming deep learning on typical tabular data, but its "typical" is roughly ten
thousand rows with mixed types, irregular targets and uninformative features — and the
card read the paper's own explanation of *why* trees win as predicting they should do
**worse** here, on 99 smooth numeric rows with no uninformative column. That is what
happened: `hgbt` tied on development ranking, lost on the sealed block (**[C6]**), and
paid the price in calibration (§③). `ref:fernandezdelgado2014` — 179 classifiers over
121 datasets, with leader margins frequently smaller than dataset-to-dataset variation
— is the sober companion, and this study is one more row of that table: five recipes,
one small dataset, margins below the resolution of the data. `ref:coverhart1967`'s
nearest-neighbour analysis and the card's M3 both predicted `knn5`'s tie-driven loss,
and the observed `-0.009615` decomposes as exactly three tied pairs.
`ref:hanley1982`'s variance formula was the card's basis for expecting a bootstrap
interval on the order of `0.14` val_auc wide; the observed interval has width `0`,
because `ref:efron1979`'s percentile bootstrap has a known failure mode on a
perfectly rank-separated parent sample (§③, **[C8]**). `ref:hollmann2025` (TabPFN) is named by
the card as the live frontier for exactly this table size and was deliberately kept
**outside** the parade, since adding a sixth recipe after the gate would be a contract
change — so "ninety years of research" here means five named recipes fixed at CONSULT,
and nothing broader.

**Against Fisher himself.** `ref:fisher1936` was transcribed at the METHOD gate from
the original rather than from memory, and it settles a folklore question this study
must not get wrong: **Fisher reported no misclassification count for *versicolor*
versus *virginica* anywhere in the paper.** His famous "less than three per million"
figure is about the *setosa* pair. For the hard pair, his §VI compound gives a mean
separation of `15.31` units against within-species standard deviations of `4.342` and
`4.222`, which he characterized as "less than four times the standard deviation of
each species", concluding that "a certain diagnosis of these two species could not be
based solely on these four measurements of a single flower taken on a plant growing
wild". Ninety years later, on 25 flowers he never saw, his own discriminant ranks
every one of them correctly (**[C3]**) and misclassifies 2 of 25 at the `0.5`
threshold (**[C7]**) — which is both better than his own sentence suggests and
entirely consistent with it, because he was describing overlap in a population and
this study is measuring one small sample of it. The card's derived figures from his
Table IX — separation `3.575` pooled standard deviations, implied ROC-AUC `0.9943`,
implied error rate `3.7` per hundred flowers — are that card's arithmetic on his
published summary statistics under a Gaussian equal-covariance model, on all 100 of his
flowers, using a compound built for a three-species test. They are context, not a
comparison, and P2's bar of at most 3 misclassified flowers was the consultant's own
independent estimate registered before the transcription existed. Neither may be
described as "Fisher's number".

**Doctrine check.** The generic profile's doctrine is *measurement resolution before
comparison*: no delta discussed before the floor that would detect it is measured, and
no frontier opened before its headroom is disclosed. This study followed it exactly —
and following it is what produced the finding. The floors were measured at Phase 0,
before a single challenger ran; the pegging was discovered there rather than in
hindsight; the headroom was audited and found undefined; and the decision to run the
parade anyway was recorded at a phase boundary as an explicit user decision rather
than taken quietly. The doctrine did not save the comparison. It did convert an
unanswerable question into a documented one, which is the whole of what it promises.

## ⑦ What to try next

In priority order. Each is a self-contained next study or phase for a reader with no
memory of this one.

1. **Re-run the identical parade with a primary metric that cannot peg.** This is the
   direct repair of **[C3]** and **[C8]**. Log-loss or Brier score on the same 49/25/25
   partition is unbounded below only by perfection and — critically — was *already
   observed to vary widely across these same five recipes* while ROC-AUC sat frozen at
   `1.000000`: development log-loss ranges from `0.012827` (`hgbt`) to `0.172887`
   (`knn5`), and Brier from `0.000945` to `0.056`. A paired-bootstrap floor on
   `(lda_all4, hgbt)` under log-loss would almost certainly be non-degenerate, which
   restores `delta_in_floors`, restores the headroom law, and makes P5–P8-style rules
   adjudicable. The same twelve cells, one metric swap. Register both a floors rule and
   a raw-delta twin per **[C13]**.
2. **Measure how much of the pegging is the 25-row block and how much is the species
   pair.** A registered `estimate` track with a split-lottery over many more redraws
   (k in the hundreds rather than 5) inside the non-sealed rows, reporting the
   *distribution* of `lda_all4`'s development val_auc and of its threshold-`0.5` error
   count. This study's k=5 lottery returned val_auc `1` five times out of five; the
   honest question that leaves open is whether the perfect-separation event has
   probability near one or merely above one half. The error-count distribution is the
   informative one, since **[C7]** shows it moving (1 of 25 → 2 of 25) where the AUC
   does not.
3. **Retest the ablation with a floor recipe that is not measured on the contrast under
   test.** **[C10]** shows the `ablation` floor `0.28125` was set by the `range / 2`
   term of the very comparison it then had to adjudicate, making the one-floor bar
   unreachable for a genuinely large effect. Measure the floor instead on a *null*
   contrast — the same feature set against itself under two resamplings, or all-four
   against all-four across bootstrap draws — so the bar reflects noise rather than the
   effect's own tail. Then re-adjudicate P13's and P15's sepal clauses against it. This
   is the cheapest experiment in the list and it directly tests whether "refuted" was a
   statement about the flowers or about the ruler.
4. **Add the one recipe the contract deliberately excluded.** `ref:hollmann2025`
   (TabPFN) is the current frontier answer for tables under roughly ten thousand rows,
   which is precisely this regime, and the method card names it as outside the parade
   only because adding a sixth recipe after the gate would have been a contract change.
   A fresh study can register it at CONSULT. Under metric (1) above, it is the one
   candidate with a plausible route to a resolvable win — and if it too ties Fisher's
   1936 discriminant on a metric with headroom, that is a far stronger statement than
   this study was able to make.
