# Profile: math

For studies whose evidence is a construction, a bound, or a computation checked by an
exact verifier — combinatorial designs, packings, extremal objects, algorithm outputs,
conjecture probes.

## 1. Audience
A mathematician or algorithm designer who will ask "who checked it?" before "how good
is it?", and who distinguishes a found object from a proved statement without being
reminded — the study's prose must make the same distinction on its own.

## 2. §⑤ heading
**⑤ Consequences for the conjecture or bound.** Prompt: state exactly what the found
objects establish (a lower bound on the best value; a counterexample; a match of the
best known), what they do not establish (any upper bound, any impossibility), and
which published value each result is compared against, with its source.

## 3. Doctrine
The verifier is the only judge: the objective enters the ledger from the declared
verifier script, never from the search (`tracks.<id>.verifier` is required for
`optimize`). A construction is evidence; a search failure is never evidence of
impossibility. The best known value seeds the frontier (`metric.incumbent_external`);
matching it is recorded and disclosed, not counted as a keep. Exact objectives declare
`metric.exactness: exact` and a resolution, not a noise floor.

## 4. Figures
None by default. When a figure is useful: the objective against search budget with the
external incumbent as a horizontal reference; the verified object itself when it can
be drawn. Tutorial §⑥ heading: **Search and verifier coding advice**.

## 5. Knowledge
`knowledge/domains/math/` (seeded by study 11) and `knowledge/research-discipline.md`.

## 6. Budgets
| Run-cost class | Starting `max_run_seconds` |
|---|---|
| sub-second verifier, seconds of search | 120 |
| minutes of search | 1 800 |
| hours of search | set explicitly; report the budget in evaluations, not seconds |
The verifier's own cost is printed (`verifier.wall_seconds`) and never counted against
the search budget.

## 7. Vocabulary
Banned: "proved" / "proof" unless a proof artifact is pinned by alias and the referee
checked it; "optimal" without a citation to the proof of optimality; "impossible" /
"cannot exist" from a search result. Must be qualified: "best" (best known, with
source, or best found, with budget). Honest verbs: found, verified, matched the best
known, improved the best found under budget B, did not reach.

## 8. CONSULT hints
`optimize` when there is an objective and a checker; `test` for a finite exhaustive
check of a statement up to N ("holds for all n ≤ N" is a computation, not a proof);
`replicate` when the goal is to reproduce a published object or value. Modality is
`none` unless the study reads a dataset of objects.
