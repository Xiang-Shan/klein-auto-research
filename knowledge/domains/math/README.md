---
title: "Mathematics — domain knowledge"
type: reference
domain: math
status: seed
concepts: [math, doctrine-anchor, exact-verifier, search-limit]
related: [../README.md, ../../research-discipline.md]
---

# Mathematics

Seeded by study 11 (exact-verifier construction). Doctrine anchor: the verifier is the only judge; a found construction is a lower bound and nothing more; a search failure is never evidence of impossibility; "proved" needs a pinned proof artifact.

## Typed citations

- **The checker should be the dumbest correct implementation, and it must share no code with the search.** Two independent implementations of the same predicate agreeing is evidence; one implementation agreeing with itself is a tautology. In the seeding study the search decided collinearity in O(k) by hashing normalized directions while the checker enumerated every triple with an integer cross product, at a cost of 26235 tests on the largest object it verified — still sub-millisecond, and it caught a planted object whose twelve points contained exactly one bad triple, which a checker that sampled triples would have passed. `(supports 11-exact-verifier-construction#C6)`
- **Freeze a verifier's controls before the verifier meets them, and give the disagreement guard a test it can fail.** The seeding study hashed twelve planted invalid objects and one known-valid object into its DATA gate record before any run existed, then spent one of ten runs making the searcher overclaim by a single point: the notary recorded `reported 21.0` against `verified 20.0` as a crash with an `NA` ledger row, so the inflated number reached no table. A control that can be softened after it fails is not a control, and a guard that has never fired is a guard nobody has tested. `(supports 11-exact-verifier-construction#C7)` `(supports 11-exact-verifier-construction#C8)`
- **A heuristic search that misses a known-attainable value has told you about that run, not about the problem — and often not even about the search.** In the seeding study the same iterated local search, on the same instance at the same budget, scored 21 from one seed block and 22 — the proven maximum — from another. Report "did not reach it under budget B", never "cannot"; and treat one run's outcome as a draw from a distribution until a registered seed sweep turns it into a rate. `(supports 11-exact-verifier-construction#C5)` `(supports 11-exact-verifier-construction#C4)`
- **When the best known value for a problem equals a proven bound, the frontier is closed before the first run — do that arithmetic first.** The seeding study's two tracks both had `metric.bound.ideal` equal to `metric.incumbent_external.value` (22 at n = 11, 62 at n = 31), so headroom was exactly zero and no run could ever be a keep. It acknowledged the closed door with `klein headroom ack` and redefined success as attaining the known maximum rather than beating it, before spending anything. `(supports 11-exact-verifier-construction#C9)`

## Open questions this domain inherits

- How often does a budgeted iterated local search reach 2n on the no-three-in-line problem at a given n? The seeding study measured a difference between two seeds and explicitly declined to call it a rate; a registered seed sweep is the first item in its `findings.md` §⑦.
- Where does a general heuristic's reach break as n grows? The seeding study measured n = 11 and n = 31 and nothing between.
