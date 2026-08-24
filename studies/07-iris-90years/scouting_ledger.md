---
type: scouting-ledger
study: "07-iris-90years"
scouted_on: "2026-08-24"
status: frozen-before-consult-gate
---

# Scouting ledger — 07-iris-90years

> **Why this file exists.** On 2026-08-24, before this study was pre-registered, a design
> panel measured the actual dataset. The pre-registration in `study.yaml` was therefore
> authored *with answers in context*. klein's hash-freeze proves "unchanged after the
> gate"; it cannot prove "written blind". This ledger closes that gap by disclosing, in
> advance, **every number that was scouted and every way the scouting shaped the design.**
>
> **Committed to this study directory BEFORE `klein gate record consult`.** Nothing in
> this file may ever be told on stage as a discovery.
>
> Stage framing: 「我们先侦察过；侦察到的都记在案。登记的预测，只算没侦察过的部分。」
> ("We scouted first, and everything we scouted is on the record. The registered
> predictions only count for the part we did not scout.")

## 0. What Tuesday's study IS and IS NOT

This study is a **prospectively locked, sealed confirmation run after documented
scouting**. It is **never** described as an independent, blind, untouched, or virgin
replication (`独立复现` / blind / untouched / virgin data are banned words —
`study.yaml:claims_discipline`).

A fresh split seed does **not** restore blindness. The scouting adaptively shaped the
metric, the candidate set, the twin ruling, the floor recipe, and both narratives — all on
this same finite dataset. The fresh seed's honest value is narrower, and is stated as
such:

> **The specific partition drawn by seed 20260828 — and therefore the specific 20 sealed
> rows — was never scored during scouting.** That is the whole of what the fresh seed
> buys.

## 1. Scouted numbers (design inputs only — never a stage discovery)

All from the 2026-08-24 panel probes. **Conditions differ from Tuesday's contract:**
n = 100 *with the duplicate treated as an ordinary row*, plain stratified/random splits,
**seed 42** — including a seed-42 sealed partition that WAS scored. Every value below is
therefore obsolete in detail under group-aware splitting at seed 20260828. What is known
is the **order of magnitude**, and that is exactly what made the design adaptive.

| # | Scouted quantity | Value | Conditions |
|---|---|---|---|
| S1 | Anchor (LDA, 4 features) development AUC | **1.000**, pegged on 14 of 20 lottery splits | n=100 w/ duplicate, seed 42 family |
| S2 | Anchor development Brier | **≈ 0.019** | as above |
| S3 | Development errors out of 20 | LDA **0** · LOGIT **1** · SVM **1** · HGBT **1** · kNN **3** | as above |
| S4 | Lottery paired 2σ spread (Brier), by family | **≈ 0.035 – 0.074** | 20-seed lottery, non-group |
| S5 | Sepal-only LDA degradation | **≈ 2.4×** the S4 spreads | as above |
| S6 | Sealed partition at **seed 42** (WAS SCORED) | **0 errors** for LDA / LOGIT / SVM | seed 42 sealed rows — this is why seed 42 is retired |
| S7 | From-scratch Fisher direction vs sklearn LDA | **cosine = 1.0** across svd / eigen / lsqr | all 100 hard-pair rows |
| S8 | Fisher's PRINTED 1936 discriminant coefficients vs ours | **cosine 0.981 / 0.956** under the two plausible conventions | a measured discrepancy, not a match |
| S9 | Group means vs Fisher's published table | reproduce **exactly to 3 decimal places** | all 100 hard-pair rows |
| S10 | Twin rows (102/143) straddling train/eval | **16 of 20 seeds** under a non-group split | this is the leakage mechanism the group split removes |
| S11 | sklearn iris vs UCI `iris.data` diff | **exactly rows 35 and 38** — six numbers | full 150-row table; both rows are setosa |
| S12 | Design-phase paired bootstrap CIs on the 20-row development | **all six comparison intervals wider than the floor band** | the documented impossibility, adopted as a limitation |

## 2. Adaptive influences — how the scouting shaped the design

Disclosing the numbers alone is not enough. These are the **design choices that would have
been different** had the scouting not happened.

| # | Design element | Shaped by | How |
|---|---|---|---|
| A1 | **Primary metric = `val_brier`** | S1, S2 | AUC was chosen against *because it was measured pegging at 1.000*. This is the single largest adaptive influence in the study. |
| A2 | **`val_logloss` rejected as primary** | kNN probe | Its scouted value was ~92 % clipping epsilon — a machine constant. Rejected on a measured property of this data. |
| A3 | **The candidate set** (logistic / kNN / SVM-RBF / HGBT, and the two LDA ablations) | S3 | The four challengers were selected knowing roughly how they place. HGBT's sizing (min_samples_leaf 5, max_leaf_nodes 4, early stopping off) was chosen for n≈60 after seeing it overfit unsized. |
| A4 | **Twin ruling → group-aware split, no deletion** | S10 | The duplicate was found by scouting; the group ruling was designed knowing it straddles most splits and would hard-FAIL the clean-room audit. |
| A5 | **Floor recipe** (split-lottery, k=20, 2×std of the anchor's development Brier, rounded up to 3 dp) | S4 | Both the *form* and the *rounding* were chosen after seeing the magnitude of the spreads. |
| A6 | **RQ3 as a positive control with a ≥2× prior** | S5 | The control was designed because sepal-only was already known to degrade by roughly that much. |
| A7 | **Both pre-committed narratives** (Branch A / Branch B) | S3, S6 | Branch B ("measurably worse on this draw") exists because the scouted point deltas leaned that way. Pre-committing *both* is the mitigation, not a claim of blindness. |
| A8 | **Sealed-look scope = the incumbent's LEVEL only** | S6 | Decided knowing what a seed-42 sealed look showed. One track, one seal, gap exploratory by construction. |
| A9 | **Registered crash rung (E0002)** | source reading | `kleinlib.eval.evaluate` refuses a target that is not exactly `{0, 1}`. Read from code, not measured on data — see § 4. |
| A10 | **Provenance diff scoped to 6 numbers** | S11 | The diff was already run; Tuesday re-derives it, it does not discover it. **No Fisher Table I transcription.** |
| A11 | **Equivalence-CI disposition rejected** | S12 | The refuter's interval analysis was executed at design time and is ADOPTED as documentation of impossibility, not discarded. |
| A12 | **Fresh split seed 20260828** | pre-committed rule | Chosen as the talk date — a rule the scouting never touched. Seed 42 is retired *because* it was scouted, sealed rows included. |

## 3. What was NOT scouted (the honest residual)

- The partition drawn by **seed 20260828** under a group-aware split — its train /
  development / sealed membership, and therefore every number computed on it.
- The **identity of the 20 sealed rows** under this contract, and any value on them.
- The **value** of `minimum_delta` under the new recipe (group-aware re-draws of the 80
  non-sealed rows). Only the order of magnitude of the *old* non-group spreads is known.
- The outcome of the **printed-coefficient convention investigation** (S8 records the
  discrepancy; the explanation is open).
- The **provenance question on rows 102/143** — whether Fisher's printed virginica columns
  or UCI `iris.names` / Bezdek 1999 say anything about them. Recorded as undecidable
  unless evidence turns up; the grouping stands either way.

## 4. Prior-scoring rule (binds findings § ⑥)

`findings.md` § ⑥ scores **only** priors tagged `(source: uninformed)`. Consequence, stated
in advance so it cannot be quietly avoided:

> **All three research-question priors (RQ1, RQ2, RQ3) are tagged
> `(source: scouting-2026-08-24 (measured))` and are therefore EXCLUDED from the
> prior scorecard.** This study contributes zero rows to the uninformed-prior tally from
> its RQs, and findings § ⑥ must say exactly that rather than score a scouted prior as a
> hit.

The predictions that § ⑥ **may** score are the ones the scouting could not inform:

| Prediction | Source tag | Why it is not scouting-informed |
|---|---|---|
| E0002 crashes with `requires target labels exactly {0, 1}` | `(source: derived — kleinlib.eval source)` | A fact about the framework's code, read not measured. |
| k-seed fit-noise std is **exactly 0** | `(source: derived — LDA is closed-form)` | A mathematical property of the estimator, not a measurement of these flowers. |
| Sealed `val_brier` within ±2× the floor of the development value | `(source: uninformed)` | This partition and these sealed rows were never scored. |
| The measured floor's magnitude under the group-aware recipe | `(source: uninformed)` | The recipe's scope (80 non-sealed rows, group-aware) was never run. |

## 5. Provenance of this ledger

Compiled 2026-08-24 from the design brief `study07_design_brief_v2.md` §§ 0, 2, 3, 5, 8
(itself synthesized from the baseline design, an external model review, an 8-agent design
panel with two refuters and three red-teams, and local probes). The panel's full outputs
live outside this repository with the presentation task.

Every number in § 1 is a **design input only**. No value here may appear in `findings.md`,
the report, the deck, or the script: those must be re-derived from ledgered study
artifacts and traced through `claims.lock`.
