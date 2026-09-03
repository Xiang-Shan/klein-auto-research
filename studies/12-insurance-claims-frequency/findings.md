---
type: findings
domain: "insurance"
profile: "insurance"
kind: "predict"
status: complete
concepts: [port, measured-floor, paired-comparison, calibration-first, isotonic, duplicate-rows, reproducibility, prose-vs-commit]
related: [study.yaml, program.md, playbook.md, research_plan.md, scouting_ledger.md, data_card.md, method_card.md, references.yaml, results.tsv, aux_metrics.tsv, claims.lock, ../../knowledge/domains/insurance/README.md]
---

# Findings — 12-insurance-claims-frequency

> SYNTHESIZE stage output. Every claim cites evidence ids from the immutable run
> manifests, the registered sweeps and the replication record; no claim without
> evidence. Protocol: `.claude/skills/klein/references/synthesis-protocol.md`; the
> lock and the numbers law: `references/claims-protocol.md`.
>
> **What this study is.** A port. The v1 quickstart `00-glm-claims-quickstart`
> (readable at tag `v1.3.0`) ran a three-rung ladder on a 58,592-policy motor
> portfolio under rules that had no measured noise floor, no sealed partition and no
> claims lock, and recorded six keeps. This study re-runs that ladder under the
> schema-3 contract on the same rows and asks what survives.
>
> **Trajectory mined.** Five ledger rows (two keeps, two discards, one sealed run),
> eight registered predictions all adjudicated by the notary, seven registered
> measurement sweeps, one replication record, and a DATA gate that returned NO-GO and
> was overridden with the risk quantified on every run.

## ① Research-question verdicts

| RQ | Verdict | Claim | Evidence | Metric delta | Strength |
|---|---|---|---|---|---|
| **RQ1** — do the three v1 rungs reproduce within two standard deviations of the transfer? | **SUPPORTED**, all three | **[C1]** | E0001, E0002, E0003, P1, P2, P4 | residuals 0.011322 / 0.001612 / 0.001154 against a registered tolerance of 0.0225 | exploratory |
| **RQ2** — does a description that names its non-default kwargs reproduce as tightly as a committed file? | **SUPPORTED in direction, almost empty in size** | **[C2]** | E0002, E0003, art:derived | the verbatim rung is closer by 0.000458 of AUC | exploratory |
| **RQ3** — how large is the paired-comparison floor here, and how many of v1's six keeps clear it? | **ANSWERED**: the bar is 0.0375805 and the ladder yields one keep | **[C3]**, **[C4]**, **[C8]** | sweep:paired_bootstrap, E0001, E0005, art:verdicts | the bar is 0.9671 of the v1 ledger's entire spread | exploratory |
| **RQ4** — does the calibration-first doctrine reproduce? | **SUPPORTED** | **[C5]** | E0004, P6 | Brier improves by a factor of 4.055 for 0.0390 of a floor of AUC | exploratory |

**[C1]** All three v1 rungs reproduce on the ported contract: refitted on the identical
v1 training rows and graded on the development half of the v1 validation set, the raw
GLM anchor lands 0.011322 from the value the v1 ledger recorded, the spline + isotonic
rung 0.001612, and the boosted tree 0.001154 — every one inside the 0.0225 tolerance
that was derived from row counts and a class balance before any model was fitted.

**[C2]** The margin between reproducing a rung from a committed file and reproducing it
from a description that names its three non-default kwargs is 0.000458 of AUC: the
verbatim tree rung's residual is 0.001154 and the prose-recovered spline rung's is
0.001612.

**[C3]** The paired-comparison floor on this portfolio is 0.0375805, which is 0.9671 of
the v1 ledger's entire spread of 0.038860 — the smallest difference this instrument can
resolve between two candidate rungs on these rows is almost exactly as large as the
distance from the v1 study's worst recorded model to its best.

**[C4]** Under that measured bar the v1 ladder yields exactly one frontier improvement:
the boosted tree over the raw GLM anchor, 0.049911. The whole spline plus log1p plus
interaction plus isotonic chain is worth 0.9568 of a floor over the same anchor, and the
tree's edge over that calibrated GLM is 0.3714 of a floor — both real, both under the
bar, both recorded as discards.

**[C5]** The insurance profile's calibration-first doctrine reproduces: replacing
`class_weight="balanced"` with `class_weight=None` plus a cross-fitted isotonic wrapper
improves the Brier score by a factor of 4.055, from 0.240641 to 0.059337, and pays
0.001465 of AUC for it — 0.0390 of one measured floor.

**[C6]** The DATA gate's overridden BLOCKER is real as a fact and small as an effect:
615 row-content hashes straddle the contract's partitions, and 0.051203 of development
rows have a byte-identical twin in training — but every rung's AUC on the twin-free rows
differs from its headline AUC by at most 0.001415, and on three of the four development
rungs the twin-free number is higher.

**[C7]** The frontier incumbent's level holds on evidence it never saw: fitted on train
plus development and evaluated once on the sealed half of the v1 validation set, it
scores 0.657739 against a development score of 0.664051 — a shift of 0.1680 of one
measured floor.

**[C8]** The v1 ledger's sixth row is a keep that a measured bar would have refused: its
recorded lift of 0.001425 is 0.0379 of this study's floor.

## ② Registered predictions (from the ledger)

Copied from `klein predict list`, not re-decided here.

| P# | Rule | Observed | Verdict | Evidence | Decision line |
|---|---|---|---|---|---|
| P1 | `primary_metric` within 0.0225 of 0.625462 | 0.614140 | **supported** | E0001 | — |
| P2 | `primary_metric` within 0.0225 of 0.651707 | 0.650095 | **supported** | E0002 | — |
| P3 | `delta_in_floors >= 1` | 0.9568 | **refuted** | E0002 | `program.md`, "Decision: P3 stands REFUTED on the registered bar" |
| P4 | `primary_metric` within 0.0225 of 0.662897 | 0.664051 | **supported** | E0003 | — |
| P5 | `delta_in_floors >= 1` | 0.3714 | **refuted** | E0003 | `program.md`, "Decision: P5 stands REFUTED on the registered bar" |
| P6 | `brier_delta_vs_reference` below 0 and `abs(delta_in_floors)` below 1 | -0.181304 and 0.0390 | **supported** | E0004 | — |
| P7 | `abs(sealed_shift_in_floors) <= 2` | 0.1680 | **supported** | E0005 | — |
| P8 | manual: the v1 sweep's lift is under the measured floor | 0.0379 floors | **supported** | sweep:paired_bootstrap, sweep:paired_bootstrap_b1000 | — |

**`n_comparisons`.** Eight registered predictions in three families, every rule fixed in
the `study.yaml` the consult gate hashed before any evidence existed, each bound in
advance to one named run or one named sidecar, with **no post-hoc selection** among
candidate comparisons:

- the ANCHOR family, `n_comparisons` = 3 (P1, P2, P4) — `within` rules whose targets are
  v1 ledger values and whose common tolerance was derived from row counts and a class
  balance, not chosen after a residual was seen;
- the FLOOR family, `n_comparisons` = 4 (P3, P5, P6, P7) — thresholds written as integer
  counts of a floor that did not exist when they were written;
- the ARITHMETIC family, `n_comparisons` = 1 (P8) — a scouted constant against a Phase 0
  sidecar, adjudicated with `klein predict adjudicate`.

The guard here is pre-registration rather than an alpha correction. At residuals of
0.001154 to 0.011322 against a 0.0225 tolerance, and at 0.0390 to 0.9568 floors against
one-floor thresholds, a Bonferroni correction over eight comparisons would change no
verdict.

**Controls.** Both fired, and both are named as controls. The **negative control** is the
DATA gate's mechanized eval-harness row: a constant predictor scored `val_auc` 0.5 and a
label-shuffled predictor 0.5114 against a chance anchor of 0.5 — a pipeline that cannot
score chance at chance cannot be trusted to score 0.664051. The **positive control** is
E0001, which had to recover a number an independent study recorded on the identical
training rows, and did, to 0.011322; the plan registered in advance that a miss there
stops the study rather than being absorbed into the ladder.

## ③ Surprises and why

**Surprise 1 — the floor is nearly the size of the thing it measures, and that is a
property of the pair, not of the arithmetic.** The paired-comparison spread between the
raw GLM and the boosted tree is 0.013942 at 1000 replicates — essentially the same size
as the MARGINAL spread of the anchor's own score under a re-split, 0.017964. Doctrine
and this study's own method card both expect a paired floor to be several times smaller
than a marginal one, because pairing cancels the shared sampling error. Here it barely
does. **Mechanism**: cancellation requires the two scores to move together, and these two
models rank the same policies differently enough that they largely do not; the shared
part of their error is small, so subtracting one from the other removes little of it. The
pair-specific sweeps make it quantitative: the widest paired standard deviation in this
study is 10.92 times the narrowest, on the same rows with the same instrument. **[C9]**

**Surprise 2 — a verdict flipped between two defensible floors, and the study had
pre-committed to saying so.** P3's lift is 0.035956. Against the bar declared at Phase 0
— measured on the ladder's most dissimilar pair, with the pair and the replicate count
recorded before the measurement — that is 0.9568 floors, and P3 is refuted. Against the
floor of the comparison P3 actually makes it is 1.0926 floors, and it would have been
supported. The registered verdict stands, because a bar chosen after the measurement is
not a bar; but the honest description of that refutation is *instrument-limited*, and
this study says so rather than reporting only the number that was declared. P5 (0.3714
against 0.4624) and P6 (0.0390 against 0.3229) do not flip. **[C10]**

**Surprise 3 — the duplicated rows the DATA gate blocked on do not flatter anybody.**
The prior behind the override was that a boosted tree could memorise a duplicated rating
cell and a linear model could not, so the tree's headline number would be the inflated
one. It is not: on the twin-free rows the tree scores 0.001018 higher, the raw GLM
0.001198 higher, the doctrine rung 0.001106 higher, and only the spline rung is lower, by
0.001415. Four rungs, four twin-free gaps, three of them positive.
**Mechanism**: the rows are duplicated because the rating structure is coarse, and a
coarse cell is exactly what every one of these models prices as a group anyway — there is
nothing individual left in the row for a tree to memorise. The playbook's H1 is recorded
as refuted. **[C6]**

**Surprise 4 — AUC held across the seal and top-decile lift did not.** The incumbent's
AUC moved 0.1680 of a floor from development to the sealed rows. Its top-decile lift fell
by 0.5101, from 2.2167 to 1.7067, at a portfolio claim rate of 0.063968.
**Mechanism**: AUC integrates over every threshold and 5860 rows, while a top-decile lift
rests on a tenth of them, of which a claim rate of 0.063968 leaves a few dozen positives;
it is a statistic with an order of magnitude less data behind it. A triage list sized
from the development decile would have promised more than the sealed rows delivered.
**[C11]**

**Surprise 5 — the spline rung reproduced its v1 value while both fits failed to
converge.** E0002 and the reference refit inside E0003 emit scikit-learn's
`ConvergenceWarning`: the `saga` solver reached its iteration cap on the widened spline
design matrix. The plain anchor E0001 converges and emits none. The rung nevertheless
lands 0.001612 from the v1 number, which means the v1 fit was equally unconverged. What
reproduced was an *implementation*, not an ideal — a distinction worth naming, because a
study that "fixed" the convergence would have failed the anchor it was trying to hit.

**Surprise 6 — the accepted risk needed measuring on every run, not asserting once.**
The DATA gate returned NO-GO and the gate was overridden. What made that lawful rather
than convenient is that the override shipped with an instrument: three printed keys on
every run, and a partition-level table that measured the same contamination in the v1
study's own validation partition, where it was 0.052223 and had never been checked. The
override's reasoning would have been identical without those numbers, and it would have
been worth nothing. **[C12]**

**A prior of this study's own method card, contradicted.** Its falsifiable prior 3 said
the tree would beat the calibrated GLM by at least one measured floor, and flagged itself
as the card's least confident. It was refuted at 0.3714 floors — and the card's own
hedge, that a floor of that order would make the comparison inconclusive rather than a
win, is exactly what happened.

## ④ Practical advice

1. **Measure the floor of the comparison you are actually going to make.** On this
   portfolio the paired standard deviation ranges over a factor of 10.92 depending on
   which two models are compared — 0.001276 for two rungs differing by one lever,
   0.013942 for a GLM against a tree. One global keep bar on a ladder that spans model
   classes will be conservative for the near comparisons and about right for the far
   ones; that is a defensible choice, but make it deliberately and report the
   pair-specific numbers beside it.
2. **Never let a seed sweep become the keep bar.** Five fit seeds moved this study's
   anchor by a standard deviation of 0.0000025099. A bar built from that would have kept
   every candidate that moved the fifth decimal.
3. **Calibrate, do not reweight.** `class_weight=None` plus
   `CalibratedClassifierCV(method="isotonic", cv=5)` bought a factor of 4.055 on Brier
   for 0.001465 of AUC. If the number you ship is a probability, that trade is not close.
4. **Spend two words of a ledger description on the non-default kwargs.** The v1 study's
   own advice, tested here for the first time: naming `knots="quantile"`,
   `include_bias=False` and `cv=5` let a stranger reproduce that rung to within 0.000458
   of what a committed file achieved. A description that names only the lever does not.
5. **Report the metric on the rows that have no twin in training.** It cost four lines in
   the entrypoint and turned an accepted BLOCKER into a measured quantity of at most
   0.001415 per rung. An accepted risk that is never measured is an excuse.
6. **Do not read a top-decile lift as if it were as stable as an AUC.** Here it fell
   0.5101 between two halves of the same original validation set while the AUC moved
   0.1680 of a floor.

## ⑤ Business / actuarial value implications

Calibration first, because that is where the money is attached.

- **A filable probability is available at a rank cost this study cannot resolve.** The
  calibrated GLM rung carries a Brier score of 0.058994 against the boosted tree's
  0.223529 — the tree's is worse by a factor of 3.789 — while the tree's rank advantage
  over it is 0.013956 of AUC, which is 0.3714 of the measured floor and 0.4624 of that
  comparison's own floor. A technical premium is a claim probability multiplied by a
  severity and attached policy by policy, so it lives in the level, not the rank; on this
  portfolio the level argument is unambiguous and the rank argument is below the
  resolution of the instrument. The registered keep-sized bar was not cleared by the tree
  over the calibrated GLM, and this study does not claim a difference there.
- **`class_weight="balanced"` should not reach a rate filing.** It costs a factor of
  4.055 on Brier and buys 0.0390 of a floor of rank, which is nothing measurable.
  Reweighting shifts the training prior and inflates every fitted probability; isotonic
  calibration puts the level back without touching the order.
- **A fourth decimal of AUC is not a rate change.** The v1 ledger's sweep row was a keep
  on 0.001425 — 0.0379 of the floor measured here. Under a measured bar it is a discard.
  Nothing in the registered contract of this study prices a decision and no
  `materiality:` block is registered, so the honest statement is exactly that: the
  registered keep-sized bar was not cleared.
- **Two scope limits an underwriter should carry.** First, every number here — and every
  number in the v1 ledger it is compared against — was measured on a partition where
  0.051203 of development rows and 0.053242 of sealed rows have a byte-identical twin in
  training, a property of the coarse rating structure that the v1 study never checked
  (0.052223 of its own validation partition). The twin-free columns bound the consequence
  at 0.001415 per rung. Second, only the incumbent's LEVEL is confirmed: one track has
  one sealed access, so every rung-to-rung gap quoted above is development evidence and
  is exploratory by construction, as `research_plan.md` registered before the first run.
- **Where the transparency argument now stands.** The usual trade — a filable GLM gives
  up rank to a tree — was not measurable on 5859 development rows at a claim rate of
  0.063968. That is not the same as saying the trade is zero; it says this portfolio and
  this partition cannot price it, and a study that wants to should declare each model
  family its own track so the gap gets two sealed numbers instead of one.

## ⑥ Literature tie-back

- **Hanley & McNeil (1982) earned its keep before the study ran.** The closed-form AUC
  variance fixed the anchor tolerance at 0.0225 from row counts alone. The three observed
  residuals (0.011322, 0.001612, 0.001154) all landed inside it, and the largest is
  within a whisker of the 0.011226 the formula predicted for a transfer of exactly this
  shape (`scouting_ledger.md` S5) — a prediction made before any fitting, and the reason
  this study did not need to invent a tolerance after seeing a miss (ref:hanley1982).
- **DeLong et al. (1988) is the doctrine that did NOT hold here.** Their point is that
  two AUCs on the same rows are correlated, so their difference is much better resolved
  than either level. It is true for near neighbours in this study (paired standard
  deviation 0.001276 for the doctrine A/B) and nearly false for the far ones (0.013942
  against a marginal 0.017964). The correlation is an empirical quantity, not a
  guarantee, and a study that assumes it will help should measure it (ref:delong1988).
- **Dal Pozzolo et al. (2015) predicted the mechanism and the direction.** Reweighting a
  class changes the training prior and biases the posterior upward while leaving the
  ranking largely intact — measured here as a factor of 4.055 on Brier for 0.0390 of a
  floor of rank (ref:dalpozzolo2015). Niculescu-Mizil & Caruana (2005) predicted the
  other half: the boosted rung ranks best and is calibrated worst, Brier 0.223529 against
  the calibrated GLM's 0.058994 (ref:niculescumizil2005).
- **Grinsztajn et al. (2022) holds on rank and is silent on resolution.** The tree is the
  best-ranking rung here, as the doctrine anchor says it should be on a table this size —
  and its margin over a well-specified calibrated GLM is 0.3714 of a measured floor. The
  benchmark literature reports such margins without a floor; this study's contribution to
  that conversation is that the margin and the resolution belong in the same sentence
  (ref:grinsztajn2022).
- **Zadrozny & Elkan (2002) and Ayer et al. (1955) describe what was observed exactly.**
  A monotone calibration map cannot reorder, so the AUC cost of isotonic calibration
  should be near zero and slightly negative from cross-fitting and ties: 0.001465
  observed (ref:zadrozny2002, ref:ayer1955). Brier (1950) supplies the level-sensitive
  score the doctrine test was decided on (ref:brier1950), Efron (1979) the resampling
  argument behind every floor here (ref:efron1979), and Perperoglou et al. (2019) the
  published grounding for quantile knot placement (ref:perperoglou2019).
- **Prior scorecard.** This is a port, so the scorecard is nearly empty by construction
  and says so rather than implying more: RQ1, RQ2 and RQ4's priors rest on the scouting
  ledger and are excluded as `(source: scouted)`. RQ3's prior is the study's one
  `(source: uninformed)` prior — "a few thousandths of AUC is expected, which would leave
  the v1 sweep's lift below the bar". It was right about the sweep and badly wrong about
  the size: the bar came in at 0.0375805, an order of magnitude above a few thousandths.
  One uninformed prior, half right, recorded as such.

## ⑦ What to try next

1. **Declare each model family its own track.** The one question this study could not
   answer — is the calibrated GLM's rank shortfall real? — needs the gap to be a
   difference of two SEALED numbers, which requires two tracks declared at CONSULT. That
   is the single highest-information change to this design.
2. **Re-measure the floor at a larger development partition.** The bar here is 0.0375805
   on 5859 rows. A study willing to give up the v1 row identity could take a development
   partition twice the size and roughly halve the sampling variance; whether that is
   worth losing the anchor is a design choice this study made in the other direction and
   recorded.
3. **Test the duplicate-row question directly rather than bounding it.** Fit on a
   deduplicated training partition and evaluate on the same development rows. This study
   bounded the effect at 0.001415 without ever separating "the duplicates do not help"
   from "these models cannot exploit them".
4. **Threshold tuning and a decile-stability study for the triage use case.** The
   doctrine is `class_weight=None` plus isotonic plus threshold tuning, and only the
   first two were tested here; the sealed drop of 0.5101 in top-decile lift says the
   third deserves its own registered measurement.
