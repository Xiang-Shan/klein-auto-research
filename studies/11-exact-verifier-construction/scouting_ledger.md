---
type: scouting-ledger
study: "11-exact-verifier-construction"
status: closed        # open | closed (closed at the CONSULT gate; later entries are a gate re-record)
---

# Scouting ledger — 11-exact-verifier-construction

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed BEFORE `klein gate record consult`
> — not because the gate hashes it (it does not: the consult gate hashes `study.yaml`,
> `research_plan.md` and `program.md`) but because the commit that carries the
> `study.yaml` the gate DOES hash carries this ledger too, which freezes it one step
> removed. Studies 07, 08 and 09 kept this ledger by hand; it is the mechanism that
> keeps "pre-registered" honest.

## §0 Disclosure

Three things were computed at design time, before the contract was written, and all
three are recorded below. **None of them ran the search.** The two registered
magnitudes in this study's predictions — 22 and 62 — are 2n at n = 11 and n = 31, the
pigeonhole upper bound, which is arithmetic rather than a measurement: three points in
one row are collinear, so each of the n rows holds at most 2 points and no
configuration can exceed 2n. That argument was written down before any reference was
looked up and before any code existed. What the design-time work established is
(S1) that the known-valid control object really is valid, (S2) what one addability
test costs in microseconds, so the evaluation-budget ladder could be sized to fit the
per-run second budget, and (S3) which two grid sizes the study would use. Values seen
here may seed anchors and identity checks; they may never be scored predictions.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | 2026-09-03 | The Erdős parabola construction {(x, x² mod p)} at p = 7, 11, 13, 31, brute-forced over all C(p,3) triples with an exact integer cross-product test | 0 collinear triples and p distinct points at every one of the four primes | design-time, unregistered, no run and no verifier existed yet; and it is a check of a statement that has a one-line proof, not a measurement | becomes the study's **negative control**: the p = 11 set is frozen into `data/prepared/instances.json` as the known-valid object the declared verifier must accept and score at exactly 11 |
| S2 | 2026-09-03 | The cost of ONE addability test (does a candidate point stay non-collinear with every pair already placed) at n = 11 with 22 placed points and at n = 31 with 62 placed points, on random configurations, 20 000 timed calls each | 0.89 µs and 1.97 µs per test; 2 000 000 tests project to about 0.2 s and 0.4 s | a pure cost measurement on random configurations — it ran no search, produced no objective and could not have shown whether any target is reachable | sizes the registered budget ladder at 20 000 / 200 000 / 2 000 000 evaluations, so the largest budget still fits comfortably inside `max_run_seconds: 120` |
| S3 | 2026-09-03 | The choice of the two grid sizes | n = 11 (prime, so the parabola control exists) and n = 31 | a design decision, not a result; the study has no evidence about either size | `n_small` = 11 and `n_large` = 31, frozen in `prepare.py` and hashed at the DATA gate |

The script that produced S1 and S2 is `sweeps/scout_design_time.py`, committed with
this ledger and re-runnable; it prints exactly the numbers quoted above.

## Retirements

Nothing was scouted and dropped. One alternative problem was considered and NOT
scouted: equal-circle packing in the unit square, which the brief offered as a
fallback. It was rejected on design grounds before any computation — its objective is
a real number and its verifier would need a tolerance, and this study's whole point is
an objective whose verifier needs none.

## Prior-scorecard eligibility

Neither research-question prior rests on a value seen in this ledger: RQ1's prior is
about where a search's reach ends and no search was run; RQ2's prior is about what the
ledger records when a searcher overclaims and no such cell was run. Both are labelled
`(source: uninformed)` in `study.yaml` and both are eligible for the
knowledge-vs-uninformed scorecard in findings §⑥.
