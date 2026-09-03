---
type: findings
domain: "astronomy"
profile: "generic"
kind: "replicate"
status: draft
concepts: [replication, prospective-lock, derived-column, regression-dilution, interval-coverage]
related: [program.md, playbook.md, data_card.md, method_card.md, scouting_ledger.md, claims.lock]
---

# Findings — 10-hubble-1929-replication

> SYNTHESIZE output. Every claim cites evidence ids from the immutable manifests;
> track frontiers stay separate; conclusions carry a class and a strength.
> Protocol: `.claude/skills/klein/references/synthesis-protocol.md`.

**The study in one paragraph.** Hubble's 1929 paper printed two tables and one
number, K = 465 km/s/Mpc. Thirteen registered cells across three tracks asked
three separate questions of it: does the number come back out of the table
(reproduction), what do those objects actually estimate (estimate), and does the
interval machinery work at n = 24 (simulate). The reproduction track reproduced
**one of five** declared targets. Two of the four failures are not failures of
arithmetic but of *availability*: the paper's headline number came from a model
whose inputs the paper never printed. Meanwhile the estimate track measured what
those 24 objects actually support: a 95 % interval for K of width 287.056180
km/s/Mpc. Set beside the ±50 Hubble quoted that looks damning, until his figure
is read as the *probable error* his era meant by it — converted to a common
convention it is very nearly this study's own interval, which is why §③.1
records his uncertainty statement as reproducing even though his constant does
not. The sharper finding is elsewhere: simply swapping which variable is called
the response moves the constant by a factor of 1.603771. The phrase "we
replicated Hubble" does not appear here, and
`references/replication-protocol.md` is why: findings report target by target.

## ① Research-question verdicts

| Claim | RQ | Track | Verdict | Strength | Class | Evidence | Result + uncertainty |
|---|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | reproduction | **supported** | confirmed | empirical-description | E0002, rep:E0002@20260903T063133Z, art:fits | Neither two-parameter fit returns 465: through the origin 423.937323, free intercept 454.158441; the nearer gap is 10.841559 against a registered tolerance of 10 |
| **[C2]** | RQ2 | reproduction | **supported** | confirmed | empirical-description | E0004, E0005, rep:E0004@20260903T063326Z, rep:E0005@20260903T064003Z, art:solar, art:groups | The headline is unreproducible for missing INPUTS, not method: 0 of 24 per-object coordinates and 0 of 9 group memberships are obtainable from the tables, the article text or any offline catalogue |
| **[C3]** | RQ3 | estimate | **supported** | confirmed | empirical-description | E0006, E0012, rep:E0006@20260903T064440Z, art:boot | The 24 objects support K = 454.158441 with a 95 % percentile-bootstrap interval of [316.648582, 603.704762], width 287.056180 — and that interval contains 465 |
| **[C4]** | RQ4 | simulate | **supported** | confirmed | known-dgp-teaching | E0013, E0009, E0010, rep:E0009@20260903T065111Z, art:covc | Under the declared DGP the percentile interval covers the truth 0.925000 of the time on the sealed block, against a nominal 0.95 and a registered bar of 0.90 |
| **[C5]** | RQ5 | estimate | **supported** | confirmed | empirical-description | E0012, art:sealed_modern | One common distance factor of 6.056247 carries both two-parameter fits to within 4.990073 of the modern 70 — the 1929-to-today gap behaves as a pure scale error |

`known-dgp-teaching` scope for **[C4]**, carried wherever it is quoted: *measured
in a known-truth lab where the velocity–distance relation is exactly linear with
Gaussian scatter at Hubble's 24 design points; it describes the behaviour of the
interval machinery under that process, not the behaviour of the real universe or
of Hubble's actual measurement errors.*

Four further measured verdicts, from cells that answered no single RQ alone:

| Claim | Track | Strength | Class | Evidence | Statement |
|---|---|---|---|---|---|
| **[C6]** | reproduction | confirmed | empirical-description | E0001, rep:E0001@20260903T063009Z, art:anchors | The identity anchor holds exactly: Table 1's published sums reproduce with a maximum absolute deviation of 0.000000, and the two tables carry 24 and 22 rows |
| **[C7]** | reproduction | confirmed | empirical-description | E0003, rep:E0003@20260903T063853Z, art:mags | Table 1's printed absolute magnitudes do NOT reproduce to half the paper's own printed precision: the maximum deviation is 0.071213 against a registered 0.06, with 3 of the 24 objects outside |
| **[C8]** | reproduction | confirmed | empirical-description | E0011, art:sealed_mags | On the sealed block, this study's own K puts the nebulae at a mean absolute magnitude of -15.524998, within 0.224998 of Hubble's printed -15.3 — his internal cross-check survives the substitution |
| **[C9]** | estimate | confirmed | empirical-description | E0007, E0008, rep:E0007@20260903T064658Z, rep:E0008@20260903T064844Z, art:invfwd, art:jack | Two choices nobody discusses move K more than the data does: inverse regression returns 728.366015 against the forward 454.158441 (a factor of 1.603771), and dropping the four Virgo rows that share one assigned distance moves it by 77.188826 — more than the analytic standard error of 75.237105 |

## ② Registered predictions (from the ledger)

Copied from `klein predict list`, never re-decided here. **7 supported, 1
refuted, 2 inconclusive, 0 open.**

| P# | Statement (short) | Rule | Observed | Verdict | Evidence | Foreseeable? | Decision |
|---|---|---|---|---|---|---|---|
| P0 | identity anchor: Table 1's sums and both row counts | `all_of[sum_r within 0.001 of 21.873; sum_v within 1 of 8955]` | deviation 0.000000 on both | supported | E0001 | **yes** (ledger S1/S2) — an anchor is meant to be | — |
| P1 | no two-parameter fit reaches 465 ± 10 | `min_abs_gap_465 > 10` | 10.841559 | supported | E0002 | **yes** (ledger S1) | — |
| P2 | four-parameter solar-motion refit recovers 465 ± 50 | `k_solar within 50 of 465`; `inconclusive_if coords_available < 24` | coords_available 0.000000 | **inconclusive** | E0004 | no | — |
| P3 | nine-group solution returns 513 ± 60 | `k_ninegroup within 60 of 513`; `inconclusive_if groups_reconstructed < 9` | groups_reconstructed 0.000000 | **inconclusive** | E0005 | no | — |
| P4 | the interval's lower bound clears the modern 70 | `ci_low > 70` | 316.648582 | supported | E0012 (sealed) | direction only (ledger S1); the width was not | — |
| P5 | inverse regression exceeds forward by > 1 paired SE | `inverse_minus_forward_se_units > 1` | 2.447419 | supported | E0007 | no | — |
| P6 | coverage under the declared DGP is at least 0.90 | `primary_metric >= 0.90` | 0.925000 | supported | E0013 (sealed) | **yes, by Phase 0** — see the disclosure below | — |
| P7 | one distance factor brings both fits within ±15 of 70 | `max_abs_gap_70 <= 15` | 4.990073 | supported | E0012 (sealed) | **yes, arithmetically** (ledger S1) | — |
| P8 | sealed: Table 2's implied mean absolute magnitude within ±0.3 of -15.3 | `mean_abs_mag within 0.3 of -15.3` | -15.524998 (deviation 0.224998) | supported | E0011 (sealed) | no | — |
| P9 | Table 1's printed `M_t` reproduces to ±0.06 mag on all 24 | `max_abs_mag_dev <= 0.06` | 0.071213 | **refuted** | E0003 | no | `program.md` 2026-09-03, "Decision: P9 is REFUTED (E0003), and the sealed registration STANDS" |

**Four of ten verdicts were foreseeable when they were written, and the study
says so rather than pretending otherwise.** `scouting_ledger.md` §Foreseeability
was written before any cell ran and carries the same column. A `replicate` study
registers predictions about numbers that are already in print, so foreseeability
is structural, not sloppy: what a registered rule buys is that the arithmetic is
on the record and adjudicated by the notary rather than asserted in prose.

**P6's foreseeability was created by the study itself, and that is the
uncomfortable one.** The Phase-0 floor `sweep:coverage_floor` had to measure the
spread of the very quantity P6's rule reads, so by the time P6 was adjudicated
its answer was visible in the floor's five blocks. This was recorded in
`program.md` the day it happened, the floor's seeds are disjoint from the sealed
block, and the refutation branch stayed live until block C was read — but the
honest summary is that measuring a floor for a predicted quantity partly spends
the prediction. **[C15]** below is the lesson.

**Multiplicity posture** (added in answer to referee note N4, which observed that a
reader had to infer it). Every prediction above was registered before any evidence
existed and every one is reported, so there is no selected family to guard against:
nothing was chosen after seeing a result, and no verdict rests on a p-value; this
study performs no significance test at all. The reproduction comparisons
(P0–P3, P8, P9) are deterministic arithmetic on printed table values against
tolerances fixed in the contract; they have no null distribution, so no multiplicity
correction is even defined for them. The stochastic quantities — the intervals of
E0006–E0008 and the coverages of E0009, E0010 and E0013 — are each a single
pre-registered estimate. `n_comparisons` is therefore 1 for every family in this
study, which is why `study.yaml` declares no `metrology:` block and why
`kleinlib.metrology.family_maxt` is not used: there is no family being screened. The
one place selection could have entered is P6, whose Phase-0 floor partly spent it;
that is disclosed above and carried as **[C15]**.

## ③ Surprises and why

**1. Hubble's ±50 reproduces almost exactly — from a fit he did not run.** The
analytic probable error of the free-intercept slope is 50.747428 km/s/Mpc
(E0002), against the ±50 the paper quotes for a four-parameter solution this
study could not reproduce at all. This is the passage the opening paragraph
defers to, and the two say one thing: **his constant does not reproduce and his
uncertainty does.** A reader who compares this study's 95 % interval width of
287.056180 against a bare "±50" is comparing a full modern interval with a
nineteenth-century half-width at a different confidence level, and will conclude
that 1929 was overconfident. It was not: on a like-for-like conversion the two
uncertainties are practically the same size, and what separates the eras is the
distance ladder (**[C5]**), not the error bar. **[C10]** *(mechanism-interpretation,
exploratory, evidence E0002, art:aux)* — the most likely explanation is that the
probable error is dominated by the residual scatter about the line, 232.910670
km/s, which is a property of the data rather than of the model form; adding the
three solar-motion parameters changes the fitted line without changing the
scatter much. It is an interpretation, and it stays exploratory: confirming it
would need the four-parameter fit, which is exactly what is unobtainable.

**2. Which variable you call the response matters more than anything else in the
analysis.** The inverse fit returns 728.366015 against the forward 454.158441
(E0007), and the paired bootstrap puts the difference at 282.639496 ± 115.484712,
i.e. 2.447419 standard errors — with Hubble's own 465 sitting between the two.
**[C11]** *(mechanism-interpretation, exploratory, evidence E0007, ref:frost2000)*
— this is textbook regression dilution: Hubble's distances carry far more error
than his velocities, so the ordinary fit of v on r is biased toward zero and is a
LOWER bound on the slope, not a best estimate. The prior was on the method card
and it held; what surprised is the size, a factor of 1.603771 rather than a few
per cent.

**3. Four galaxies with one assigned distance outweigh the standard error.**
Dropping the Virgo-cluster rows moves K from 454.158441 to 531.347267, a shift of
77.188826 against an analytic standard error of 75.237105 (E0008). Hubble himself
attributed the difference between his two published solutions "largely to the four
Virgo-cluster nebulae"; that attribution is the one part of his uncertainty
discussion this study *could* reproduce, and it reproduces from his own numbers.

**4. The Phase-0 floor was optimistic about its own quantity.** The five floor
blocks put coverage between 0.925000 and 0.932000 and gave a `minimum_delta` of
0.0060663; the development block then measured 0.911000 — below every floor
block. **[C12]** *(research-discipline, exploratory, evidence sweep:coverage_floor,
E0009)* — a k = 5 spread of a Monte-Carlo *proportion* can easily come in below
that proportion's own binomial standard error, and the recipe's
`max(2 × std, range/2)` guard did not save it. A floor for a proportion should be
sized against the binomial standard error as well as against the observed spread.

**5. Nothing crashed, and that is worth one sentence.** Thirteen cells, zero
crashes — but only because two defects were caught by the mandatory sealed
rehearsal instead of by a sealed run. See ④.

## ④ Practical advice

**[C13]** *(research-discipline, exploratory, evidence E0011, art:sealed_mags,
art:aux)* **Before you use a column as evidence, ask what it was computed from.**
Hubble's Table 2 has a distance column that looks exactly like what a replication
wants — 22 more galaxies with distances *and* velocities. It is not a
measurement: the DATA gate showed it is the velocity divided by his adopted
constant, holding to floating-point exactness on all but one of the rows where
both columns are printed, and rounding on that one. Comparing this study's K
against it would have returned the ratio of our constant to his, a tautology
dressed as a test. The sealed statistic uses only the two columns Table 2
actually measured, and `study.yaml:sealed_lock` names both the allowed and the
forbidden lists so a reader can check that it did.

**[C14]** *(research-discipline, exploratory, evidence E0011, E0012)* **Read the
sealed rehearsal's NUMBERS, not just its exit code.** This study's seals were
saved by `klein run-one --final-test --dry-run`, in two different ways. The
first rehearsal *failed loudly*: the sealed cell's own guard fired because the
library dropped Table 2's forbidden columns by the block it served rather than the
block requested, so the rehearsal handed the cell a different shape than the real
run would. The second rehearsal *passed* — exit 0, a well-formed printed block, a
pinned table — and was still wrong: the distance rescale had been applied as
`r / f` instead of `r * f`, which would have recorded P7 as refuted on a value of
2680.495911 and spent the estimate track's only access on a prediction that was
never actually tested. A sealed run can be wrong without crashing.

**[C15]** *(research-discipline, exploratory, evidence sweep:coverage_floor,
E0013)* **Measuring a floor for a quantity a prediction reads partly spends the
prediction — plan for it, or accept it in the open.** There is no way to size the
resolution of a coverage estimate without learning roughly what the coverage is.
The options are to floor a *different* quantity (and then the floor judges
nothing), to register the prediction after the floor (and lose the registration),
or to do what this study did: measure the floor, record the foreseeability the day
it is created, keep the refutation branch live, and take the verdict on evidence
the floor never touched.

**[C16]** *(research-discipline, exploratory, evidence E0007, ref:frost2000)*
**When the predictor is the noisy variable, report both regressions.** One number
from `v ~ r` is not an estimate of the slope; it is a lower bound. Reporting the
inverse fit beside it costs one line of code and, here, changes the headline by a
factor of 1.603771. If the error ratio is known, use an errors-in-variables fit;
if it is not — as here, where the paper prints neither error — say so and give the
bracket rather than inventing the ratio.

**[C17]** *(research-discipline, exploratory, evidence E0011, art:contract)* **A
prospective lock is a lock; disclose it as one and it still works.** The analyst
who ran this study had read all 22 sealed rows before the contract existed. What
protected the sealed comparison was not ignorance — which could not be restored —
but that the statistic, the columns, the source of K and the tolerance were
written into the contract and hashed before any cell ran, and the access was spent
once. Resampling the same rows into a "fresh block" would have created no
information and laundered a look into holdout vocabulary; it was rejected before
the contract and the rejection is on the record.

## ⑤ Implications — what changes if this holds

**If you cite "Hubble's constant, 500 km/s/Mpc", stop.** The value 500 is in
neither published solution. The article adopts it as an intermediate between
465 ± 50 (24 objects) and 513 ± 60 (nine groups), after attributing their
difference largely to four galaxies (E0005, `ref:hubble1929`). **[C18]**
*(empirical-description, exploratory — the provenance is read from the article
text, not measured by a cell; evidence E0005, art:groups, ref:hubble1929)*.

**If you plan to reproduce a historical result, budget for missing inputs rather
than for missing methods.** Both of this study's unreproducible targets failed on
availability, not on difficulty: the four-parameter fit is a few lines of numpy,
and it could not be run because the paper prints no coordinates (**[C2]**). A
replication plan that lists only the *methods* to re-implement will discover this
at the wrong end. Register an `inconclusive_if` on input availability at the
start, and a documented gap becomes a finding instead of a hole.

**What must NOT be concluded.** That Hubble was wrong: his 465 sits comfortably
inside this study's interval (**[C3]**), and the reproduction verdict is about
whether a number can be *recomputed*, not about whether it was *right*. That the
modern 70 refutes him: the two are separated by a distance-scale recalibration
(**[C5]**, `ref:sandage1958`), not by an error in his velocities. That the
coverage number describes real data: **[C4]** is scoped `in-silico` and says so
wherever it is quoted. And nothing here is priced: this study registered no
pricing block, and no claim asserts value of any kind beyond the registered bars
it cleared.

## ⑥ Literature tie-back

Every reference in `references.yaml` was checked against its publisher or arXiv
landing page on 2026-09-03; all of them are `verified: true`. Two of them stand
behind `confirmed` claims — `ref:hubble1929` (C2) and `ref:sandage1958` (C5) —
and the rest sit behind `exploratory` claims (C11, C16, C18) or appear in this
section's prose only. An unverified reference behind a confirmed claim is what
the claims law warns about; there are none.

- **`ref:hubble1929` — the object of study.** The article text settled two things
  no amount of arithmetic could: that it prints no per-object coordinates, and
  that it never lists the nine groups' membership. Those two sentences are what
  turned P2 and P3 from "we failed to reproduce" into "the inputs are not there",
  which is a different and more useful finding.
- **`ref:frost2000` — held, larger than expected.** Regression dilution predicted
  the direction of the inverse/forward gap; the method card's prior 4 was the
  study's most exposed and it survived (**[C11]**).
- **`ref:diciccio1996` — held.** The percentile interval is only first-order
  accurate, and at n = 24 it under-covered: 0.911000 on the development block
  against the analytic interval's 0.938000 on the same block and the same DGP
  (E0009, E0010). Both fall short of nominal, so *some* of the shortfall is n; the
  gap between them is the method's own contribution.
- **`ref:sandage1958` — the frame for [C5].** The constant fell steeply when the
  distance ladder was corrected, not when anyone re-measured a velocity; this
  study's single-factor rescale of 6.056247 is the same story told with Hubble's
  own rows. (Sandage's own recalibration factor is not quoted here: no cell of
  this study measured it, so it has no pinned home.)
- **`ref:planck2018` and `ref:riess2022` — why a round 70 is honest here.** They
  bracket it, and their mutual disagreement is an order of magnitude smaller than
  the gap this study measures. A cosmology paper could not use a round figure; a
  replication measuring a factor of 6.487978 can.
- **`ref:lemaitre1927` — the caution behind the study's title.** The same relation
  and a rate of the same era's magnitude were derived two years earlier from
  overlapping data. "Hubble's constant" names a quantity whose 1929 value is a
  product of the distance scale of its time, not of one paper.

**Priors' scorecard.** Of the five research questions, RQ1, RQ3 (centre) and RQ5
rested on scouted values and are excluded by the ledger's own rule. That leaves
two `uninformed` priors, and **both held**: RQ2 predicted that the failures would
be missing inputs rather than missing method (they were), and RQ4 predicted
coverage in the low nineties (measured 0.925000 sealed, 0.911000 development). No
prior came from a `knowledge/` document, because there was no physics domain
directory when this study started — the first citation into
`knowledge/domains/physics/README.md` is this study's, so the
knowledge-versus-uninformed comparison begins with the next one.

## ⑦ What to try next

1. **Fetch the objects' coordinates from a documented catalogue, with the epoch
   stated, and finish P2.** This study declined at design time because
   hand-transcribing that many positions at an unstated epoch is a fabrication
   risk. A follow-up that bundles a catalogue as a dataset — with its own README,
   licence and two-source diff, exactly as `datasets/hubble1929/` was built —
   turns the gap into a measurement and would settle whether the four-parameter
   model really is what separates 423.937323 from 465.
2. **Re-run the coverage lane with a split generator so two interval methods
   share replicates.** The amendment recorded before E0010 explains why this study
   could not: the bootstrap consumes draws, so the two methods diverge after the
   first replicate. Common random numbers would sharpen the 0.911000-versus-0.938000
   comparison from two independent estimates into a paired one.
3. **Vary the DGP the audit runs under.** Sweep the scatter, and swap the Gaussian
   error law for a heavy-tailed one. Both were declined here as questions about a
   *different* declared truth than the one the DATA gate hashed; a study that
   registers them up front can ask whether the under-coverage is about n or about
   the error law.
4. **Register the errors-in-variables fit that this study declined.** A Deming fit
   needs the ratio of velocity to distance variance, which Hubble does not print —
   but a follow-up could register a *range* of plausible ratios and report the
   resulting range of K, which is the honest version of the number **[C11]** says
   the forward fit under-states.
