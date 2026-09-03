---
type: scouting-ledger
study: "00-known-truth-quickstart"
status: closed        # closed at the CONSULT gate; later entries are a gate re-record
---

# Scouting ledger — 00-known-truth-quickstart

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`;
> the gate hashes it.

## §0 Disclosure

This study's evidence is generated, not found, so the generator itself had to be
designed before the contract could be written — a data-generating process with no gap
between a linear model and the truth would leave the study with no question in it.
Design-time work was therefore confined to the DGP and its closed-form properties:
`prepare.py`'s coefficients were chosen so the positive rate lands in the declared
20–30 % band and so the truth is not linearly expressible. **No classifier was fitted,
no partition was drawn, and no noise floor existed** while any of this was looked at.
Every number below is a property of the generating process, computable from
`prepare.py` alone; none of them is a candidate's score, and none of them is the value
of any registered prediction's rule — every rule in `study.yaml` is a threshold in
units of the *measured* floor, which did not exist at design time and could not have
been anticipated here.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | 2026-09-03 | `prepare.simulate(20260903)` under the frozen coefficients: class balance and the whole-table Bayes AUC | positive rate 0.2412; Bayes AUC 0.883874 over all 20 000 rows | design-time; the whole table, not a contract partition; no model, no floor, no ledger row | the DGP is frozen and becomes the generator the DATA gate hashes; the **development-partition** Bayes AUC (a different number, computed only after the gate) becomes `tracks.primary.metric.bound.ideal` |
| S2 | 2026-09-03 | the linear-oracle diagnostic: least-squares projection of the TRUE log-odds onto `[1, x1…x8]`, then onto that plus `x1·x2`, then plus `x3²` | AUC 0.807679 → 0.838248 → 0.883874 | a property of the generating process (no classifier is fitted, no data is split, no metric is scored against a bar) | confirms the ladder has room to climb; RQ1's prior rests on it and is labelled `(source: scouted)` |
| S3 | 2026-09-03 | two earlier coefficient settings for the same DGP | see Retirements | retired before the contract existed | retired |
| S4 | 2026-09-03 | `KLEIN_SMOKE=1 python train.py` — the one sanctioned off-loop syntax/shape check, run on the anchor recipe before the CONSULT gate was recorded | the canonical block printed cleanly; `primary_metric` 0.806201, `bayes_auc` 0.884116, `gap_to_ideal` 0.077916 on the development partition | smoke mode writes no sidecar, no snapshot, no manifest and no ledger row — it is explicitly not evidence; and with `minimum_delta` still 0 no floor existed, so `gap_in_floors` was not printed and no rule could have been read off it | disclosed here rather than left silent; every prediction's rule numeral was already fixed in `study.yaml` as an integer count of floors before this ran, and none of them rests on a value in this row |

## Retirements

- **Interaction 1.30 / quadratic 0.90 / intercept −2.10.** Gave a positive rate of
  0.3026 — outside the 20–30 % band the study declares — and a linear-oracle gap of
  0.111171, wide enough to make the ladder theatrical rather than instructive.
  Retired before the contract was written.
- **The anchor's own development score (S4) as a prediction target.** Seen during
  the smoke check and deliberately not used: every registered rule is a threshold in
  units of the measured floor, which did not exist when the rules were written.
- **A DGP with no noise features.** Dropped in favour of keeping `x7` and `x8` as pure
  noise, so the study can watch a high-capacity model spend budget on columns that
  carry nothing. Never generated.

## Prior-scorecard eligibility

RQ1's prior rests on S2 and is labelled `(source: scouted)` in `study.yaml`; it is
excluded from the knowledge-vs-uninformed scorecard in findings §⑥. RQ2's prior rests
on nothing seen here — the noise floor is measured at Phase 0, after this ledger
closes — and is labelled `(source: uninformed)`.
