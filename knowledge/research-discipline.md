---
title: "Research discipline — what studies 07–10 and 20–23 taught the framework"
type: synthesis
domain: science
status: promoted
concepts: [noise-floor, estimand, headroom, positive-control, selection-guard, pre-registration, crashes-as-data, errata, materiality, evidence-use]
related: [README.md, domains/README.md, ../docs/design/klein-2-design.md]
claims: [07-iris-90years#C12, 07-iris-90years#C13, 07-iris-90years#C14, 07-iris-90years#C15, 07-iris-90years#C16, 07-iris-90years#C17, 07-iris-90years#C18, 07-iris-90years#C19, 08-iris-rematch#C1, 08-iris-rematch#C2, 08-iris-rematch#C6, 08-iris-rematch#C7, 08-iris-rematch#C8, 08-iris-rematch#C13, 08-iris-rematch#C15, 08-iris-rematch#C16, 08-iris-rematch#C17, 08-iris-rematch#C18, 08-iris-rematch#C19, 08-iris-rematch#C20, 08-iris-rematch#C21, 09-iris-first-lesson#C1, 09-iris-first-lesson#C2, 09-iris-first-lesson#C3, 09-iris-first-lesson#C4, 09-iris-first-lesson#C5, 09-iris-first-lesson#C9, 09-iris-first-lesson#C11, 09-iris-first-lesson#C13, 09-iris-first-lesson#C14, 09-iris-first-lesson#C15, 20-llm-cot-contamination#C3, 20-llm-cot-contamination#C5, 20-llm-cot-contamination#C6, 20-llm-cot-contamination#C9, 20-llm-cot-contamination#C10, 20-llm-cot-contamination#C12, 20-llm-cot-contamination#C13, 20-llm-cot-contamination#C16, 20-llm-cot-contamination#C17, 20-llm-cot-contamination#C18, 21-bloodmnist-cnn#C3, 21-bloodmnist-cnn#C7, 21-bloodmnist-cnn#C12, 21-bloodmnist-cnn#C17, 22-cnn-data-scaling#C1, 22-cnn-data-scaling#C3, 22-cnn-data-scaling#C4, 22-cnn-data-scaling#C11, 22-cnn-data-scaling#C14, 23-lalonde-causal-replication#C13, 23-lalonde-causal-replication#C14, 23-lalonde-causal-replication#C18, 23-lalonde-causal-replication#C19, 23-lalonde-causal-replication#C20, 23-lalonde-causal-replication#C26, 23-lalonde-causal-replication#C27, 23-lalonde-causal-replication#C28, 23-lalonde-causal-replication#C30]
---

# Research discipline — the lessons that transfer

> Promoted 2026-09-02 from the findings of studies 07 (`07-iris-90years`), 08
> (`08-iris-rematch`) and 09 (`09-iris-first-lesson`). Every lesson cites the claims
> that earned it; the mechanism column names what Klein 2.0 built in response. These
> studies asked whether ninety years of classifiers beat Fisher's 1936 discriminant on
> Fisher's 150 irises; what they found about *how to ask* is what generalizes.

## The lessons

### 1. Measure the floor that will judge the comparison before the first challenger runs
A `minimum_delta` is measured, never guessed — and the measurement must be of the
right thing. Study 07 set its delta from twenty group-aware split draws before any
challenger (supports 07-iris-90years#C12); study 09 measured a per-candidate paired
floor and found it exceeded the marginal one (supports 09-iris-first-lesson#C3);
study 08's three challengers beat the anchor's raw score and the floor laughed
(supports 08-iris-rematch#C15). **Mechanism:** `klein noise-floor --recipe --estimand`;
the schema-3 bar `minimum_delta ≥ max(2×std, range/2)`; preflight refuses a delta
inside its own floor.

### 2. Name the estimand of the floor; neither the marginal nor the paired spread is sharper a priori
Fit noise, marginal re-split noise and paired-comparison noise can differ by an order
of magnitude on the same data; the honest floor for a comparison is the paired one,
measured under common random numbers (supports 07-iris-90years#C12; supports
09-iris-first-lesson#C3). **Mechanism:** `noise_floor.estimand` is required beside a
declared bound; `metrology.paired_bootstrap` enforces common random numbers by
construction.

### 3. Pre-register which quantity decides
The declared-split delta and the lottery mean can disagree; deciding after the loop
which one counts is how sealed vocabulary gets stretched (supports
07-iris-90years#C13). Study 09 registered a two-level verdict — permission first,
contest second — and reported both (supports 09-iris-first-lesson#C5).
**Mechanism:** predictions carry a declarative rule on a named printed key; the rule
is hashed at the consult gate.

### 4. Audit headroom before spending a challenger budget
Study 07 ran a four-challenger parade with the keep bar below zero and found out by
hand (supports 07-iris-90years#C12). Study 08 registered the arithmetic first: the
door stood ajar at h = 1.015 (supports 08-iris-rematch#C1) and twenty-one challengers
produced zero keeps (supports 08-iris-rematch#C2; supports 08-iris-rematch#C17).
Study 09 closed the door at h = 0.33 before any arena number existed (supports
09-iris-first-lesson#C1) and built a 42-cell permission map in which no cell cleared
(supports 09-iris-first-lesson#C2; supports 09-iris-first-lesson#C4). `h ≥ 1` means
"not excluded", never "plausible". **Mechanism:** `metric.bound.ideal`, headroom
disclosed at preflight and verify, `klein headroom ack`; the permission map as one
registered cell with a pinned table.

### 5. Put a positive control on the ladder, sized to fail
A control that must fire proves the instrument is alive at every sample size (supports
07-iris-90years#C14; supports 08-iris-rematch#C8; supports 09-iris-first-lesson#C9).
**Mechanism:** referee check 4 refuses a study with neither a positive nor a negative
control unless their absence is declared with a reason.

### 6. A selection guard is not a significance test — name it what it is
Of 113 cells in study 08 exactly one cleared the sign-flip max-t guard, a quadratic
discriminant at eight rows, and the registered fragility exhibit did not confirm it
(supports 08-iris-rematch#C6; supports 08-iris-rematch#C19). In study 09, 0 of 42
cells cleared (supports 09-iris-first-lesson#C4). The guard limits family-wise false
detection; it says nothing about the size of what it detects. **Mechanism:**
`metrology.family_maxt` ported from the study-08 reference implementation;
`evaluate_test` prints `n_comparisons`; an unguarded family's claims cap at
exploratory.

### 7. Pre-script the branch you think will not fire
The door-ajar branch in study 08 had a prior of about 0.2 and fired against the
majority prior; because it was scripted, it ran as registered with no redraw (supports
08-iris-rematch#C18; supports 08-iris-rematch#C1). Study 09's sealed run crashed and
the pre-registered Branch B closed the study exploratory without an argument
(supports 09-iris-first-lesson#C14). **Mechanism:** predictions with rules and an
`inconclusive_if` clause; the `stop:` block; the mandatory sealed dry-run.

### 8. Keep the crash rows
One hundred and sixty arena crashes and three parade crashes in study 08 are data
about where methods break, not noise to be cleaned (supports 08-iris-rematch#C21); a
registered crash rung on the ladder measures the breaking point on purpose (supports
07-iris-90years#C18); one wiring crash, owned in the ledger, is worth more than a
silent retry (supports 08-iris-rematch#C13). **Mechanism:** `crash` is a retained
disposition with a resolvable candidate commit; `klein sweep register` keeps crash
sidecars as evidence; the notary never retries.

### 9. The ledger catches its operator — let it
Study 09's evaluator hardcoded a retired split seed; the lock's unsourced-numeral
scan found it a study later and erratum E1 re-scoped the affected claims without
deleting a number (supports 09-iris-first-lesson#C15). Seed schemes registered outside
the numeric domain of the library that consumes them silently change the experiment
(supports 07-iris-90years#C19); a calibration lane that ignores the split law is a
different experiment (supports 08-iris-rematch#C20); the provenance diff — twins,
duplicate rows, a retired scouting entry — is run before the first model (supports
07-iris-90years#C17; supports 09-iris-first-lesson#C13). **Mechanism:**
contract-driven splits with a printed `split_fingerprint:` compared at run-one;
`klein verify --numbers`; the append-only claims lock with errata; the scouting
ledger hashed at the consult gate.

### 10. Detectable is not actionable
A gain of 0.29× the floor at n = 8 is detectable and not actionable (supports
08-iris-rematch#C6); measurement resolution is never business materiality, and no
Klein artifact may call a cleared floor "material" without a priced consequence on the
record (supports 09-iris-first-lesson#C13). **Mechanism:** the optional `materiality:`
block with its own provenance; the profile vocabulary scan.

## Two lessons about methods that also transfer

- **At small n, the modern method loses to the 1936 family, and the family captures
  the gain.** The best small-n improvement over Fisher's LDA was, to within 2 %,
  available by adjusting Fisher's own family (supports 08-iris-rematch#C7); a
  foundation model landed mid-pack (supports 08-iris-rematch#C16); sizing the modern
  method for the sample does not save it at n ≈ 60 (supports 07-iris-90years#C16).
- **Score a proper score; keep ranking metrics as auxiliaries** (supports
  07-iris-90years#C15). Under a known truth, the simulation lane showed which
  decomposition terms the anchor's standing came from (supports
  09-iris-first-lesson#C11).

## What did not transfer

Study 09 asked this question of itself (09-iris-first-lesson#C13): the *numbers* — the
floor of 0.08 Brier, the 42-cell map, the rung where fog outruns ceiling — belong to
150 irises with twin rows and a nearly linear boundary and travel nowhere. What
transfers is the order of operations: provenance diff, floor, headroom, permission,
contest, one sealed look, errata. Klein 2.0 encodes the order, not the numbers.

### 11. A lock that never verified still has a history — retract on the record, never rewrite
Study 10 recorded a number whose value its pinned artifact did not hold; the claims law then
failed the lock (check 5) and forbade repointing it (check 6), and the study reset the lock's
git history to re-author it. The reset was disclosed in program.md, the discarded revision was
tagged (`discarded/10-claims-lock-draft`) so a clone can see it, and the referee judged it a
note. **Mechanism:** `klein claims number` now refuses at write time a value its artifact does
not hold (engine commit b35acc4); a disclosed retraction verb is the open follow-up. The lesson
is about the framework, not the data, so it carries no claim citation.

## Lessons from studies 20–23

> Promoted 2026-11-03 from the findings and claims locks of studies 20
> (`20-llm-cot-contamination`), 21 (`21-bloodmnist-cnn`), 22 (`22-cnn-data-scaling`) and
> 23 (`23-lalonde-causal-replication`). They were the first exhibits of four profiles:
> llm, cv, ml-research and data-science. Their field lessons live in `domains/llm/`,
> `domains/cv/`, `domains/ml-research/` and `domains/data-science/`. Each study's
> `referee_report.md` records the same arc: a FAIL in round 1 and PASS-WITH-NOTES in
> round 2. Study 20 failed on controls and multiple comparisons. Studies 21, 22 and 23
> failed on a mechanism stated as a finding. Lessons 12 and 13 are about those two
> failure modes.

### 12. Controls and `n_comparisons` are where a first referee round fails — fix both at CONSULT
A null headline needs evidence that the instrument would have seen an effect had one been
there. Study 20's confirmed results were nulls, and both of its controls had to be computed
after Gate 3's first round, offline from the committed ledger. Re-scoring the recorded replies
against permuted golds dropped exact-match to chance (a mean of 0.0126) and left no gain
(supports 20-llm-cot-contamination#C16). A planted gain of 0.10 was recovered in every gain
cell, but each plant is one seeded realization, not a power estimate (supports
20-llm-cot-contamination#C17; see 20-llm-cot-contamination erratum E2). Its family-wise guard
arrived the same way: Bonferroni intervals at `n_comparisons` 4 and 2 moved no verdict
(supports 20-llm-cot-contamination#C18). A guard that only widens cannot flatter a result, but
inquiry-model.md asks a `test` study to fix the family, `n_comparisons` and the guard at
CONSULT, and this one had not. Study 21 never ran the label-shuffled harness control its data
card asked for. It disclosed the gap, and the referee passed it as disclosed, not as a control
(supports 21-bloodmnist-cnn#C17). A declared absence passes. A silent one fails.
**Mechanism:** referee check 4 (controls) and check 5 (multiple comparisons). The cheaper fix
sits upstream: name the positive control, the negative control and each family's
`n_comparisons` in the research plan before the first run.

### 13. A mechanism is a claim class, not a tone — the hedge travels with every sentence that uses it
Each repair re-scoped a locked mechanism with an erratum and never rewrote it. In study 20,
"near-unmeasurable" overreached. The gain was measured with a tight interval, and what the
ceiling removed was headroom (supports 20-llm-cot-contamination#C6; see
20-llm-cot-contamination erratum E1). In study 22, "an easier test set is unlikely" became:
the evidence fails to show the test partition easier and does not show it harder (supports
22-cnn-data-scaling#C11; see 22-cnn-data-scaling erratum E2). Study 23's overlap explanation of
its sealed gap was re-scoped twice. Only then did it say what the evidence allows: better
overlap is one candidate reason, and one sealed draw cannot separate any mechanism from luck
(supports 23-lalonde-causal-replication#C28; see 23-lalonde-causal-replication errata E3 and
E7). Study 23's round-1 failure was a section heading, not a claim sentence. The hedge has to
reach headings and the summary paragraph too. **Mechanism:** the `mechanism-interpretation`
class stays exploratory; referee check 1 re-reads the prose for mechanisms stated as fact;
errata re-scope and never rewrite.

### 14. Cells that share ledger entries are one measurement — and so is a crash and its rerun
The call ledger de-duplicates requests. That makes a study cheap and replayable, and it also
couples cells. Study 20's sealed contamination cell made no new model call. It re-scored the
50 original and 200 sealed chain-of-thought answers that two earlier cells had recorded, so
its agreement with them holds by construction, and an independent check needs a salted
re-query (supports 20-llm-cot-contamination#C12). The same coupling applies to a rerun after
an infrastructure crash. Study 20's anchor crashed on HTTP 429, and its rerun answered all but
one request from the crashed run's pinned shard. That was a sound recovery, and it was one
measurement, not two. That crash and rerun are recorded in study 20's caveats, not in a claim
of their own, so this part of the lesson rests on the principle 20-llm-cot-contamination#C12
states. Findings must say which cells are coupled. **Mechanism:** each manifest
records `calls_cached` against `calls_total`; the coupling is disclosed in findings by hand.

### 15. A replay is not a replication, and an exact re-execution is determinism, not robustness
Three operations get called "replicated", and they answer three different questions. A ledger
replay re-scores recorded answers. Study 20's replay reproduced with a difference of 0, while a
salted re-query of the same cell changed 9 of 600 item-arm scores (supports
20-llm-cot-contamination#C13). The replay audits parsing, scoring and aggregation. Only the
re-query says anything about the model. An exact re-execution (same commit, data, environment
and seed) reproduced study 23's cells with a difference of 0 on every compared key except the
timing fields. That shows the pipeline is deterministic and says nothing about robustness to
code, seed or specification (supports 23-lalonde-causal-replication#C27; see
23-lalonde-causal-replication erratum E5). Robustness needs different code, a different seed or
a re-query. **Mechanism:** `klein replicate --replay` records `mode: replay` under its own
evidence id (`replay:E####@<ts>`), and findings must not count it toward
`confirmation.require: [replicate]`.

### 16. An attested run needs an observed re-execution, and the claim must say which cells had one
A detached transaction is judged locally but recorded as attested. The notary did not watch
it run. Study 22's six fit cells all ran detached (`observed_by_notary: false`). Its confirmed
exponent rests on them, on one observed re-execution of one attested cell (difference 0), and
on a replication of the fit's arithmetic over the pinned cells, which re-measures nothing
(supports 22-cnn-data-scaling#C1). The findings state exactly that. The referee accepted it
because the protocol takes either an observed replication or a sentence scoping the claim to
attested evidence, and here both existed. **Mechanism:** `execution.mode: detached` and
`observed_by_notary` in each manifest; `klein replicate` re-executes an attested cell under
observation; referee check 1.

### 17. A collapsed candidate is a bug until its inference path has been checked
Study 21's first batch-normalization candidate scored 0.3005. The same layers, with running
statistics recomputed on the training set before evaluation, scored +0.5955 higher (supports 21-bloodmnist-cnn#C12). Working batch
normalization was then the only single change to earn a keep (supports 21-bloodmnist-cnn#C3). The study's explanation,
that running averages lag weights still moving at a constant learning rate, is an exploratory
interpretation resting on an off-loop diagnostic (supports 21-bloodmnist-cnn#C7). The
discipline does not depend on that explanation. A catastrophic number from a well-known
technique is first a question about the evaluation path: train mode against eval mode, cached
statistics, the checkpoint actually loaded. Do not put the lever in the playbook's ruled-out
table until that check is done. **Mechanism:** the discard row and its candidate commit are
retained, so the broken run stays citable as the bug it was.

### 18. Check that the control arm is the arm you registered, and that the registered effect can fit
Study 20's "direct" arm was told to answer with the number only. Only 4 of 300 public replies
complied, and chain-of-thought wrote only 1.85 times the direct arm's tokens, so the contrast
had silently become chain-of-thought against a terse chain-of-thought (supports
20-llm-cot-contamination#C5; supports 20-llm-cot-contamination#C9). Its registered gain of at
least 0.10 also could not be reached at a direct score of 0.95, because a gain cannot exceed
one minus the baseline (supports 20-llm-cot-contamination#C10). This is lesson 4's headroom
arithmetic applied to a registered effect size. Do it at CONSULT, from a pilot baseline.
**Mechanism:** the call ledger makes the compliance audit an offline count over pinned
replies; the threshold arithmetic is done by hand before the rule is hashed.

### 19. Hold a fitted law to a sealed extrapolation point
In-range fit statistics do not test a law. Study 22's six-cell power law missed the sealed
full-pool loss by a signed relative error of -0.2802 (supports 22-cnn-data-scaling#C3; see
22-cnn-data-scaling erratum E1). The miss ran opposite to the registered direction, so the law
was pessimistic, not optimistic (supports 22-cnn-data-scaling#C4). Even the most favourable
post-hoc refit missed by -0.0745 (supports 22-cnn-data-scaling#C14). A low R² would have
refuted the law without saying which way it misses. The sealed point said which way. Register
any alternative functional form before the sealed access, and never refit on the sealed point.
**Mechanism:** one `--final-test` access per track, after the mandatory sealed dry-run; the
fit is pinned as its own registered cell before the sealed run exists.

### 20. A single-source transcription of published targets is a single point of failure
Study 23 registered every published target from one document, the NBER working paper. Four of
its targets missed, and a transcription error in exactly those four values would read as the
same miss (supports 23-lalonde-causal-replication#C30). The confirmed content is what was
measured: the stated covariate list reproduces Table 2's column (4) on all three lanes, and
neither all-covariates reading recovers the printed Table 3 comparison values (supports
23-lalonde-causal-replication#C26). A locked claim that asserted the editorial reading
(that Table 3 mixes two Table 2 columns) at `confirmed` was downgraded to exploratory (see
23-lalonde-causal-replication erratum E4). The headline reproduction claim was re-scoped to name
its single source (see 23-lalonde-causal-replication erratum E9). Cross-reading every target
against the paper's other tables at METHOD explained both refutations before any cell ran
(supports 23-lalonde-causal-replication#C14). For a replication: name the source of every target
in the claim sentence, cross-read within the paper, and get a second source before calling an
inconsistency the paper's. **Mechanism:** the profile's replicate hint asks for two sources;
errata re-scope a claim that outruns its source.

### 21. A registered rule must be able to fail for the reason it was written
Study 23's sensitivity prediction said that IPW without 1974 earnings misses the benchmark by
more than $1000. IPW already missed by more than that with 1974 earnings, so the rule would
have been supported had the covariate been irrelevant. A rule stated against the baseline cell
discriminates (supports 23-lalonde-causal-replication#C13; see 23-lalonde-causal-replication
erratum E1). The same blind spot appears with point-estimate rules. Study 20's "gap at most
0.05" was supported at the point estimate while both interval upper ends exceeded 0.05
(supports 20-llm-cot-contamination#C3). Before hashing a rule, ask what outcome would refute
it and whether that outcome is the one the question cares about. **Mechanism:** none checks
discriminating power. Rules are hashed at the consult gate, so the check has to happen before
the hash.

### 22. The driver's own failures spend real budget
Study 23 lost two of its four estimator slots to driver errors, not science: a wrapper timeout
shorter than the run's `max_run_seconds`, then a relaunch on the wrong cell (supports
23-lalonde-causal-replication#C18). A lead's reset in a checkout where a run was finishing
removed filed evidence commits. Repairing that was a recovery, not a routine (supports
23-lalonde-causal-replication#C19). The sealed rehearsal earned its place: the first dry run hit
its 900-second limit (exit 124), the sealed cell later took 1227.74 seconds, and launching at
the old limit would most likely have spent the track's only sealed access on a timeout (supports
23-lalonde-causal-replication#C20). Give the driver's tool timeout more room than the run's,
set the cell before launching, and never commit, cherry-pick or reset in a checkout with a
run-one in flight. **Mechanism:** retained `crash` rows; `klein recover`; the mandatory sealed
dry-run, whose exit code is a budget measurement.

## Lesson → mechanism, in one table

| Lesson | Mechanism in Klein 2.0 |
|---|---|
| 1–2 floor and estimand | `klein noise-floor --recipe --estimand`; schema-3 floor bar; `metrology` |
| 3 pre-registered decider | predictions with rules, hashed at the consult gate |
| 4 headroom | `metric.bound`, disclosure, `klein headroom ack`, registered permission cells |
| 5 positive control | referee check 4 |
| 6 selection guard | `metrology.family_maxt`; exploratory ceiling for unguarded families |
| 7 pre-scripted branches | rules with `inconclusive_if`; `stop:`; sealed dry-run |
| 8 crash rows | retained `crash`; `klein sweep register`; no retries |
| 9 operator-catching | contract splits + printed fingerprint; `verify --numbers`; append-only lock; scouting ledger |
| 10 detectable ≠ actionable | `materiality:` block; vocabulary scan |
| 11 retract on the record | `klein claims number` refuses at write time; append-only lock; a tagged discarded revision |
| 12 controls and `n_comparisons` | referee checks 4 and 5; declare both before the first run |
| 13 mechanism is a class | `mechanism-interpretation` stays exploratory; referee check 1; errata re-scope |
| 14 coupled cells | `calls_cached` / `calls_total` in each manifest; disclosure in findings |
| 15 replay ≠ replication ≠ robustness | `klein replicate --replay` records `mode: replay`; re-execution records; a re-query or independent code for robustness |
| 16 attested runs | `execution.mode: detached`, `observed_by_notary`; an observed `klein replicate`; referee check 1 |
| 17 bug before verdict | retained discard rows with resolvable candidate commits |
| 18 control-arm compliance and effect headroom | the call ledger's pinned replies; headroom arithmetic before the rule is hashed |
| 19 sealed extrapolation | one `--final-test` access per track; sealed dry-run; the fit pinned as a registered cell |
| 20 single-source targets | the profile's two-source replicate hint; errata re-scope |
| 21 rules that can fail | none in the engine — the check precedes the consult-gate hash |
| 22 driver failures | retained `crash`; `klein recover`; sealed dry-run exit code |
