---
title: "Research discipline — what studies 07, 08 and 09 taught the framework"
type: synthesis
domain: science
status: promoted
concepts: [noise-floor, estimand, headroom, positive-control, selection-guard, pre-registration, crashes-as-data, errata, materiality, evidence-use]
related: [README.md, domains/README.md, ../docs/design/klein-2-design.md]
claims: [07-iris-90years#C12, 07-iris-90years#C13, 07-iris-90years#C14, 07-iris-90years#C15, 07-iris-90years#C16, 07-iris-90years#C17, 07-iris-90years#C18, 07-iris-90years#C19, 08-iris-rematch#C1, 08-iris-rematch#C2, 08-iris-rematch#C6, 08-iris-rematch#C7, 08-iris-rematch#C8, 08-iris-rematch#C13, 08-iris-rematch#C15, 08-iris-rematch#C16, 08-iris-rematch#C17, 08-iris-rematch#C18, 08-iris-rematch#C19, 08-iris-rematch#C20, 08-iris-rematch#C21, 09-iris-first-lesson#C1, 09-iris-first-lesson#C2, 09-iris-first-lesson#C3, 09-iris-first-lesson#C4, 09-iris-first-lesson#C5, 09-iris-first-lesson#C9, 09-iris-first-lesson#C11, 09-iris-first-lesson#C13, 09-iris-first-lesson#C14, 09-iris-first-lesson#C15]
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
