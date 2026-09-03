---
type: findings
domain: "combinatorial geometry"
profile: "math"
kind: "optimize"
status: draft
concepts: [no-three-in-line, exact-verifier, iterated-local-search]
related: []
---

# Findings — 11-exact-verifier-construction

> SYNTHESIZE stage output. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`; the lock and the
> numbers law: `references/claims-protocol.md`.
>
> This is the exhibit for one sentence: **the checker is never the searcher.** The
> objective in every row below was computed by `verify.py`, a script that shares no
> code with the search, is outside the mutable surface, was hashed at the METHOD gate
> and never changed after. What the search thought it had found is recorded beside
> that number, never instead of it. One run was made to lie on purpose, to find out
> what the record does about it.
>
> A second thing is unusual here and should be said at the top: **no run in this study
> could have been a keep.** The best known value for the problem equals a proven upper
> bound at both sizes studied, so the frontier's headroom was exactly 0 before the
> first run, and the study acknowledged that closed door in advance instead of
> discovering it in a losing phase. Every one of the ten runs is a discard or a crash,
> by arithmetic, and that was registered rather than regretted.

## ① Research-question verdicts

| Claim | RQ | Track | Verdict | Strength | Class | Evidence | Delta + uncertainty |
|---|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | n_small | supported | exploratory | empirical-description | E0002, E0003, E0004, E0009 | on the 11 × 11 grid the verifier scored 20 points at 20000 addability tests, 21 at 200000 and 21 at 2000000 from the development seed block; from the sealed seed block, at the same largest budget, it scored 22 — the proven maximum 2n, `matched_external: true`. The objective is exact: `minimum_delta` is 1 and every value is an integer recomputed from the artifact's bytes |
| **[C2]** | RQ1 | n_large | supported | exploratory | empirical-description | E0005, E0006, E0007, E0010 | on the 31 × 31 grid the same search scored 50, 53 and 54 across the same budget ladder, and 55 from the sealed seed block: it did not reach 62 at either seed. The largest budget bought 19014 greedy completions at n = 11 and 2190 at n = 31, because one completion costs about n² addability tests |
| **[C3]** | RQ2 | n_small | supported | confirmed | procedural-verdict | E0001, E0002, E0003, E0004, E0005, E0006, E0007, E0008 | the declared verifier rejected 12 of 12 planted invalid objects and accepted the known-valid object at exactly 11, its value known in advance; on all seven honest runs the verifier-computed `claim_excess` was 0; and the one run made to report a single extra point was refused — `reported 21.0` against `verified 20.0`, disposition `crash`, reason `verifier_disagreement`, ledger row `NA` |
| **[C4]** | RQ1 | n_small | supported | confirmed | procedural-verdict | E0004, E0009 | the development lane and the sealed lane disagree about whether this search reaches 22, and they differ only in the seed: the seed 20260903 plateaued at 21 from evaluation 152572 onward, and the seed 20260917 reached 22 at evaluation 1612132. Two seeds, one success — a difference, not a rate |

`exploratory` on C1 and C2 is the honest label and it is not a formality: this study's
`confirmation.require` is `[verify]`, and the engine's confirmation check looks for a
re-verification record attached to a track's final **keep**. There are no keeps here,
by arithmetic, so no such record can exist and neither track can be labelled
`confirmed` by that route. What the two claims do have is a re-verification record for
every development run they cite (§②, P4) and a sealed cell each. C3 and C4 are
`procedural-verdict` claims — what the procedure decided — and every id they cite
resolves in the ledger, which is that class's ceiling.

**The controls, named.** Both directions were checked before anything was believed,
inside a notarized transaction, and the naming follows the data-gate protocol's
detector convention.

- **Positive control — the detector must FIRE.** Twelve invalid objects, frozen in
  `data/prepared/instances.json` at the DATA gate before the checker ever met them:
  seven geometric defects spanning the slopes `0, undefined, +1, -1, +2, +1/2` and a
  `+2` line with unequal lattice gaps; three well-formedness defects (a coordinate equal to n, a
  negative coordinate, a non-integer coordinate); a repeated lattice point; and one
  "almost valid" object — the eleven-point parabola set plus a single cell that
  creates exactly one collinear triple among its twelve points. E0001 ran the declared script on each and
  printed `rejected: 12` against `planted: 12`. **P3 supported.**
- **Negative control — the detector must stay silent.** The Erdős parabola set
  `{(x, x² mod 11)}`, whose validity is a theorem rather than a measurement and whose
  objective is therefore known before any code runs: exactly 11. E0001 handed it to the
  notary as its own artifact, so the acceptance was performed by the notary's own
  verifier invocation, and the ledger records `primary_metric` 11.

A checker that fired on everything would pass the first control and fail the second; a
checker that fired on nothing would do the reverse. Neither half alone is a check.

## ② Registered predictions (from the ledger)

Copied from `klein predict list`; every machine verdict was written by the notary from
the run's own printed block, and the arithmetic it used is reproduced verbatim.

| P# | Statement | Rule | Observed | Verdict (ledger) | Evidence | Decision |
|---|---|---|---|---|---|---|
| P1 | at the largest registered budget the verifier scores the 11 × 11 search at 22 points or more | `{key: primary_metric, op: ">=", value: 22}` | `primary_metric 21 >= 22 → refuted` | refuted | E0004 | `program.md` 2026-09-03 |
| P2 | at the same budget the 31 × 31 search is scored below 62 | `{key: primary_metric, op: "<", value: 62}` | `primary_metric 54 < 62 → supported` | supported | E0007 | — |
| P3 | the verifier rejects every one of the 12 planted invalid constructions | `{key: rejected, op: "eq", value: 12, tol: 0}` | `rejected 12 == 12 ± 0 → supported` | supported | E0001 | — |
| P4 | re-running the verifier on a pinned artifact reproduces its integer objective exactly | manual | seven `verify:` records, `reproduced: true` in each, tolerance 0.0 | supported | `verify:E0001@…` … `verify:E0007@…` | — |
| P5 | no run's own claimed objective is ever accepted above the verifier's | manual | `claim_excess` 0 on all seven honest runs; E0008 refused as `verifier_disagreement` | supported | E0001–E0008 | — |
| P6 | from the sealed seed block the 11 × 11 search is again scored at 22 or more | `{key: primary_metric, op: ">=", value: 22}` | `primary_metric 22 >= 22 → supported` | supported | E0009 | — |
| P7 | from the sealed seed block the 31 × 31 search is scored below 62 | `{key: primary_metric, op: "<", value: 62}` | `primary_metric 55 < 62 → supported` | supported | E0010 | — |

**Family size.** `n_comparisons = 7` — the seven registered predictions are the whole
comparison family. Five carry an arithmetic rule and were locked in `study.yaml` at the
first consult gate, before any evidence existed and before any reference had been
looked up; two (P4, P5) are `manual: true` and were locked in the same file at the same
time. Each is bound to exactly one run or one named set of records, and there was no
post-hoc selection among candidate comparisons: no prediction was added, removed or
re-worded after a result, and the two consult re-records on the event chain changed the
external incumbent, the bound and one phase id — never a rule. No registered sweep
exists in this study, so nothing else feeds a prediction. The guard is pre-registration
itself rather than an alpha correction, and the two magnitudes the rules quote, 22 and
62, are 2n — arithmetic, not a measurement, so there is no multiplicity in choosing
them either.

**Why two predictions are `manual: true`,** since the referee will ask. P4 is decided by
replication records, which are written outside a run transaction and print no block for
a rule to read. P5 is decided by a run that **crashes by design**: `klein run-one`
adjudicates `--tests` only after the verifier agrees with the searcher, so a cell whose
entire purpose is to make them disagree can never reach the adjudication step. A
prediction about a refusal cannot be decided by the machine that performs the refusal.
Both were adjudicated with `klein predict adjudicate`, which pinned their evidence ids
and filed a `prediction_adjudicated` event each, so the verdicts are receipts and not
prose.

Nothing is open, nothing is inconclusive, and the one refutation carries its dated
decision.

## ③ Surprises and why

**The sealed run reached the maximum the development lane had just failed to reach,
and the only difference was the seed.** This is the study's real result and it was not
expected: P1 was written expecting 22 at n = 11 and got 21; P6 was written expecting
the same thing from a block nobody had touched, and got 22. Same instance, same
algorithm, same 2000000-evaluation budget, same code at the same commit — one integer
different, and the outcomes fall on opposite sides of a theorem's ceiling.

The mechanism is not mysterious and that is the point. This search is an iterated local
search over always-valid configurations: it greedily completes, keeps improvements,
perturbs by `1-3` points, and restarts from empty after `2n` stale passes. Its outcome is a
draw from a distribution over random restarts, not a property of the algorithm. The
development trajectory found 21 at evaluation 152572 and then spent the rest of its
2000000-evaluation budget — 19014 greedy completions in all — without improving — so "more budget" was
demonstrably not the missing ingredient, and the honest reading of the development lane
alone ("this search plateaus at 21 here") was a statement about one draw wearing the
costume of a statement about the search.

**[C5]** *(mechanism-interpretation, exploratory)* A single run of a randomized
heuristic reports a draw, and reading it as a property is the most ordinary way to be
wrong about a search. The evidence is E0004 against E0009 — 21 against 22 at the same
budget on the same instance — plus the plateau structure inside E0004: the best object
was found at evaluation 152572 of the 2000000 the run was given, and nothing after it
improved.
What this study cannot say, and does not, is how often the search reaches 22: two seeds
and one success is a difference, not a rate, and a registered seed sweep is the first
item in §⑦.

**The larger instance was never searched as hard, and the budget unit hides it.** The
budget is counted in addability tests, which is the honest unit of *cost*: one test is
one call to the same function. But one greedy completion costs about n² of them, so
2000000 tests bought 19014 completions at n = 11 and 2190 at n = 31 — a large
difference in the number of restarts, on top of a far denser constraint set. "The same
budget" and "the same search effort" are not the same sentence, and a reader comparing
the two panels of `reach_vs_budget.png` should have the second pair of numbers in hand.

**Nothing about the checker surprised anyone, which is itself worth recording.** All
twelve planted objects were rejected on the first attempt, the known-valid object was
accepted at exactly its known value, all seven honest runs agreed with the checker to
the integer, all seven re-verifications reproduced exactly, and the deliberate
overclaim was refused. A study whose subject is a mechanism should say plainly when the
mechanism simply worked; the informative content is in *what the record looks like*
when it works, which is what §⑤ is about.

## ④ Practical advice

**[C6]** Write the checker as the dumbest correct thing you can, and let the searcher be
the clever one (evidence: E0001, E0002, E0003, E0004, E0005, E0006, E0007). This
study's search decides whether a point can join a configuration in O(k) by hashing
normalized directions; its checker enumerates every triple and applies an integer
cross-product test — 26235 of them on the largest object this study verified, and
still sub-millisecond. The
two implementations share no code and agreed on every one of the seven honest runs,
which is evidence precisely because they could have disagreed. One algorithm agreeing
with itself is a tautology, and a fast checker that sampled triples would have passed
the `parabola_plus_one` control, whose twelve points contain exactly one bad triple.

**[C7]** Freeze the controls before the checker meets them (evidence: E0001). The twelve
planted objects and the one known-valid object live in `data/prepared/instances.json`,
which the DATA gate hashed before any run existed. A positive control that can be
softened after it fails is not a control, and the difference costs nothing to arrange:
it is a file written by a deterministic script and a gate record naming its sha256.

**[C8]** Give the guard a test it can fail (evidence: E0008). One of the ten runs in this
study was spent making the searcher lie by exactly one point, and it is the run that
turned "the notary refuses a disagreement" from documentation into a receipt:
`manifest.metric` records `reported 21.0` against `verified 20.0`, the disposition is
`crash`, and `results.tsv` carries `NA` — the inflated number reaches no table
anywhere. A guard that has never fired is a guard nobody has tested, and the cost of
testing it was one phase slot.

**[C9]** When the best known value equals a proven bound, do the headroom arithmetic
before the first run, not after the fifth (evidence: E0004, E0007, E0009, E0010). Here
`h = (ideal − incumbent) / minimum_delta` is 0 on both tracks, so no run could ever be a
keep; the study acknowledged the closed door with `klein headroom ack` and rewrote what
success meant — attaining the known maximum rather than beating it — before spending
anything. Ten runs later, zero keeps, exactly as registered. The arithmetic is two
divisions and it changes what the whole study is for.

## ⑤ Consequences for the conjecture or bound

**What the found objects establish.** One object: a 22-point configuration on the
11 × 11 grid with no three collinear, found by E0009 and accepted by the declared
verifier, whose bytes are committed at `models/E0009/solution.json` and whose
collinearity was re-checked over every triple again by `figures/make_figures.py`.
Twenty-two is 2n at n = 11, and 2n is an upper bound for every n by the pigeonhole
argument (three points in a row are collinear, so each of the n rows holds at most 2).
The object therefore **attains the maximum**, and it matches the best known value for
this instance (`ref:flammenkamp_records`, `ref:mathworld_no3`). A second object, of 55
points on the 31 × 31 grid (E0010), is a lower bound on what this search reaches there
and nothing more: 55 < 62, and 62-point configurations at n = 31 are known
(`ref:flammenkamp_records` lists exhaustive enumerations of n = 31 solutions by
symmetry class).

**What they do not establish.** Nothing about the problem. In particular:

- The 21-point plateau at n = 11 from the development seed, and the 54- and 55-point
  results at n = 31, are **search limits**. They are facts about an iterated local
  search under a 2000000-evaluation budget from two named seeds, and the correct
  reading of every one of them is "did not reach", never "cannot". The study says so
  because the counterexample is inside the study: the same search reached 22 at n = 11
  from a different seed after failing to at another.
- No upper bound is established or improved. The only upper bound in play, 2n, was
  already a theorem before the study began and no run could interact with it — that is
  what headroom 0 means.
- Nothing here bears on the Guy–Kelly conjecture (`ref:guy1968`) that 2n is eventually
  unattainable. Both instances sit far inside the range where 2n is known attainable,
  and a heuristic missing a value in that range says nothing about a regime it never
  entered.

**Vocabulary, deliberately.** The words "proved", "optimal" and "impossible" do not
appear in this study's conclusions about its own results, and this paragraph is where a
reader can check that. There is no proof artifact pinned in `claims.lock`, so nothing is
proved here; the only proof invoked, the pigeonhole bound, is cited as a theorem from
the literature and used as an input. "Matched the proven maximum" is the strongest
verb this study's evidence supports for E0009, and "did not reach it under the
registered budget" is the strongest for every other row.

Nothing here is priced: this study registered no `materiality:` block, so clearing —
or missing — a registered bar means only that the bar was cleared or missed.

**One note for the machine reader.** `klein verify` scans this document against the
math profile's banned list and reports a `[WARN]` naming the three lines just above:
they are the only place in the study where those words are written down, and they are
mentioned there rather than used — the paragraph exists so that the ban is checkable
rather than merely asserted. §⑥ also writes "provably optimal" about a cited result of
`ref:ramanathan2025`, which is the qualified use the profile permits ("optimal" is
banned *without* a citation to the proof of optimality). A reader who wants to audit
the ban should read those four lines and nothing else will need checking.

## ⑥ Literature tie-back

Ten references, all verified against the publisher, arXiv or maintainer page on
2026-09-03 (`references.yaml`, `refs_verified: true`), none quoted from memory.

`ref:flammenkamp_records` and `ref:mathworld_no3` are what make this study's
`metric.incumbent_external` a number rather than a guess: the maintained record page
states that 2n-point solutions are known for every grid size up to 70, and MathWorld
independently states "For 2 ≤ n ≤ 32, it is possible to select 2n such points", which
covers both instances. Two independent sources for a number that seeds a frontier was a
deliberate choice; a single source is a single point of failure. `ref:roth1951` supplies
the negative control and, more importantly, supplies it with a *proof*, which is why
the control's expected objective could be written down before any code ran.
`ref:guy1968` is the reason this study's vocabulary is careful about large n, and
`ref:hall1975` is the constructive yardstick a heuristic should be read against.
`ref:lourenco2019` is the skeleton the search implements. `ref:dudeney1900` and
`ref:flammenkamp1992` / `ref:flammenkamp1998` are provenance: where the problem came
from and who pushed the computational record.

`ref:ramanathan2025` is the closest modern comparison and it lands almost exactly on
this study's result. That paper puts three methods on this same problem: integer linear
programming reaches provably optimal solutions to 19 × 19, a transformer (PatternBoost)
matches them to 14 × 14, and a PPO agent solves 10 × 10 but **fails at 11 × 11 on
constraint violations**. This study's general-purpose iterated local search failed at
11 × 11 from one seed and succeeded from another. Read together, the picture is that
n = 11 is not intrinsically hard — a dedicated exact method settles it — but it is
already past the point where general heuristics are reliable, which is a more useful
thing to know than either result alone. That paper was read at the METHOD gate, after
the consult gate had hashed P1–P7 and their magnitudes; it sharpened the reason to
expect P1 to be interesting and it changed no rule.

The method card's own regime table said the small instance "should pay" and the medium
one "should not". It was **wrong on the first and right on the second**, and it was
wrong in the informative direction: it had already recorded that a reinforcement-learning
agent fails at exactly n = 11, and it still predicted success. The card also explicitly
declined to predict *how far short* the n = 31 search would land, and that abstention
was correct — nothing in it could have produced 54.

**Prior scorecard.** Both research-question priors were `(source: uninformed)`; neither
rests on the scouting ledger, whose three entries verified the control object, timed one
addability test, and chose the two grid sizes without running a search. RQ1's prior was
**half right**: it said the search would reach 22 at n = 11 (wrong on the development
seed, right on the sealed one) and would stop short of 62 at n = 31 (right, twice). It
also gave a reason — that the same evaluation budget buys about ten times fewer greedy
completions on the larger grid — and the measured counts are 19014 against 2190, which
is the right magnitude. RQ2's prior was **fully correct**: no honest run disagreed with
the checker, and the overclaiming cell was recorded as a crash naming
`verifier_disagreement` rather than as a result. Two uninformed priors, one and a half
hits, and no knowledge-sourced prior in this study to compare them against — this study
adds a row to the scorecard rather than settling it. The knowledge row it does
contribute is the first entry in `knowledge/domains/math/`.

## ⑦ What to try next

1. **Register a seed sweep at n = 11 and the largest budget.** This is the first thing
   to fix and the cheapest. E0004 and E0009 differ only in the seed and land on opposite
   sides of the proven maximum, so the quantity this study could not measure is the
   success *rate* — and a rate is exactly what a registered measurement sweep is for
   (`klein sweep register`, every trial to a sidecar). Thirty seeds at about a second
   each would turn C5 from an observation into a number.
2. **Locate where the reach breaks.** The two instances are far apart: 22 is reachable,
   62 is not, and everything between is unmeasured. A third instance around n = 19 —
   the size at which integer programming is still provably optimal
   (`ref:ramanathan2025`) — would say whether the fall-off is a cliff or a slope. It
   needs a third track declared at CONSULT, which is exactly why this study did not add
   one after seeing its results.
3. **Budget in passes, not evaluations.** The evaluation unit is honest about cost and
   silent about effort: the same budget bought 19014 greedy completions at n = 11 and
   2190 at n = 31. A ladder registered in completions would compare the two instances at
   equal search effort, and the pair of ladders side by side would separate "the
   instance is harder" from "the budget bought less".
4. **Change the perturbation and re-run the same registered cells.** The current move
   removes `1-3` random points; a move that removes a whole row's pair respects the
   structure a 2n configuration must have. That is a change to `lib/`, which this study
   may not make mid-loop, so it belongs to a follow-up study whose predictions cite
   `11-exact-verifier-construction#C1` and `#C5`.
